"""Cross-encoder fine-tuning (SPEC-finetune.md, Task 36).

Fine-tunes ``cross-encoder/ms-marco-MiniLM-L-6-v2`` on the disjoint pairs produced
by ``braid.finetune.pairs``. Early stopping / best-checkpoint selection uses a
validation split carved from the training sample only (decision D2): the
evaluation query set is never touched until the final before/after comparison.

Every hyperparameter and both seeds are recorded in ``reports/finetune.md``.
"""

from __future__ import annotations

import json
import platform
import random
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import torch
from sentence_transformers import CrossEncoder, InputExample
from sentence_transformers.cross_encoder.evaluation import CEBinaryAccuracyEvaluator
from torch.utils.data import DataLoader

from braid.finetune.pairs import FINETUNE_SEED, Pair
from braid.ingest.models import read_jsonl
from braid.query.rerank import DEFAULT_MODEL_NAME

# Hyperparameters (recorded verbatim in reports/finetune.md).
# Batch size and sequence length are kept small because this fine-tune runs on
# an 8 GB machine that is also hosting the OpenSearch and Neo4j containers.
EPOCHS = 3
BATCH_SIZE = 8
LEARNING_RATE = 2e-5
WARMUP_STEPS = 100
MAX_SEQ_LEN = 256
LOSS = "BinaryCrossEntropyLoss"
SCHEDULER = "WarmupLinear"
WEIGHT_DECAY = 0.01
MAX_GRAD_NORM = 1.0
EVAL_STEPS = 50
VALIDATION_FRACTION = 0.1
TRAIN_SEED = 20260925  # distinct from pairs seed 20260924 and ingest 20260923

DEFAULT_OUTPUT = Path("models/ce-braid")
DEFAULT_PAIRS = Path("data/finetune-pairs.jsonl")


@dataclass(frozen=True)
class TrainingReport:
    """Everything a reviewer needs to reproduce the training run."""

    base_checkpoint: str
    output_dir: str
    epochs: int
    batch_size: int
    learning_rate: float
    warmup_steps: int
    max_seq_len: int
    loss: str
    scheduler: str
    weight_decay: float
    max_grad_norm: float
    eval_steps: int
    validation_fraction: float
    train_seed: int
    pairs_seed: int
    num_train_pairs: int
    num_dev_pairs: int
    num_positives: int
    num_negatives: int
    wall_clock_seconds: float
    hardware: str
    best_val_accuracy: float
    dev_majority_baseline: float = 0.0
    dev_pairs_dropped_for_passage_overlap: int = 0
    dev_history: tuple = ()


class _RecordingEvaluator(CEBinaryAccuracyEvaluator):
    """CEBinaryAccuracyEvaluator that also records its best dev accuracy.

    Subclasses the real evaluator (rather than wrapping it) so that the
    trainer's ``isinstance(evaluator, SentenceEvaluator)`` check passes and the
    evaluator is NOT wrapped in a ``SequentialEvaluator`` (which would treat the
    single evaluator as an iterable and raise ``TypeError``).
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.best = -1.0
        # (epoch, steps, accuracy) at every evaluation, so the reported best
        # dev accuracy is verifiable from an artifact rather than only from a
        # step-level number the evaluator's own CSV never records.
        self.history: list[tuple[float, int, float]] = []

    def __call__(self, model, output_path=None, epoch=-1, steps=-1):
        metrics = super().__call__(model, output_path=output_path, epoch=epoch, steps=steps)
        # metrics are name-prefixed, e.g. {"dev_accuracy": ..., "dev_f1": ...}
        for key, value in metrics.items():
            if key.endswith("accuracy"):
                self.best = max(self.best, float(value))
                self.history.append((float(epoch), int(steps), round(float(value), 4)))
        return metrics


def _pick_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _hardware(device: str) -> str:
    return f"{platform.platform()} ({platform.machine()}); torch device={device}"


def read_pairs(path: Path = DEFAULT_PAIRS) -> list[Pair]:
    """Read the JSONL pair file produced by ``braid.finetune.pairs``."""
    return [Pair(**row) for row in read_jsonl(path)]


def split_pairs(
    pairs: Sequence[Pair],
    *,
    validation_fraction: float = VALIDATION_FRACTION,
    seed: int = TRAIN_SEED,
) -> tuple[list[Pair], list[Pair]]:
    """Split by question ID so no query text spans both train and dev.

    The guid is ``"{question_id}:pos:{i}"`` / ``"{question_id}:neg:{i}"``; the
    prefix is the HotpotQA question id (a hex string, no colons).
    """
    qids = sorted({p.guid.split(":")[0] for p in pairs})
    rng = random.Random(seed)
    rng.shuffle(qids)
    n_val = max(1, int(round(len(qids) * validation_fraction)))
    val_qids = set(qids[:n_val])
    train = [p for p in pairs if p.guid.split(":")[0] not in val_qids]
    dev = [p for p in pairs if p.guid.split(":")[0] in val_qids]
    # Question-level split alone does not stop a *passage* appearing in both
    # halves (HotpotQA reuses paragraphs across questions; 13 such passages, and
    # 2 texts labelled both gold and distractor, exist in the shipped pairs).
    # A dev pair whose passage the model trained on would inflate the dev score
    # that picks the checkpoint, so such dev pairs are dropped.
    train_passages = {p.passage for p in train}
    dev = [p for p in dev if p.passage not in train_passages]
    return train, dev


def train(
    pairs: Sequence[Pair],
    *,
    output_dir: Path = DEFAULT_OUTPUT,
    base_checkpoint: str = DEFAULT_MODEL_NAME,
    epochs: int = EPOCHS,
    batch_size: int = BATCH_SIZE,
    learning_rate: float = LEARNING_RATE,
    warmup_steps: int = WARMUP_STEPS,
    max_seq_len: int = MAX_SEQ_LEN,
    scheduler: str = SCHEDULER,
    weight_decay: float = WEIGHT_DECAY,
    max_grad_norm: float = MAX_GRAD_NORM,
    eval_steps: int = EVAL_STEPS,
    validation_fraction: float = VALIDATION_FRACTION,
    train_seed: int = TRAIN_SEED,
    device: str | None = None,
) -> TrainingReport:
    """Fine-tune a cross-encoder, saving the best checkpoint to ``output_dir``."""
    if len(pairs) == 0:
        raise ValueError("cannot train on an empty pair set")

    device = device or _pick_device()
    train_pairs, dev_pairs = split_pairs(
        pairs, validation_fraction=validation_fraction, seed=train_seed
    )
    n_dev_before_guard = len(
        [p for p in pairs if p.guid.split(":")[0] in {q.guid.split(":")[0] for q in dev_pairs}]
    )
    # Seeds every RNG the loop draws from (python/numpy/torch): batch shuffle,
    # dropout, classifier-head init. NB the legacy `CrossEncoder.fit` builds its
    # own trainer with HF's default seed (42), which this cannot override, and
    # MPS kernels are not bit-deterministic -- see the report's Reproducibility
    # section for what that means for rerunning.
    from transformers import set_seed

    set_seed(train_seed)

    train_examples = [
        InputExample(guid=p.guid, texts=[p.query, p.passage], label=p.label)
        for p in train_pairs
    ]
    model = CrossEncoder(base_checkpoint, max_length=max_seq_len, device=device)
    train_dataloader = DataLoader(
        train_examples, shuffle=True, batch_size=batch_size, collate_fn=lambda batch: batch
    )

    recording = _RecordingEvaluator(
        sentence_pairs=[[p.query, p.passage] for p in dev_pairs],
        labels=[p.label for p in dev_pairs],
        name="dev",
        batch_size=32,
    )

    start = time.monotonic()
    model.fit(
        train_dataloader=train_dataloader,
        evaluator=recording,
        epochs=epochs,
        scheduler=scheduler,
        warmup_steps=warmup_steps,
        optimizer_params={"lr": learning_rate},
        weight_decay=weight_decay,
        max_grad_norm=max_grad_norm,
        evaluation_steps=eval_steps,
        output_path=str(output_dir),
        save_best_model=True,
        show_progress_bar=True,
    )
    wall = time.monotonic() - start

    dev_positive_rate = sum(p.label for p in dev_pairs) / max(1, len(dev_pairs))
    majority_baseline = max(dev_positive_rate, 1.0 - dev_positive_rate)
    history = tuple(recording.history)
    hist_path = Path(output_dir) / "dev-history.json"
    hist_path.write_text(
        json.dumps({"dev_accuracy_history": history, "majority_baseline": majority_baseline}),
        encoding="utf-8",
    )

    return TrainingReport(
        base_checkpoint=base_checkpoint,
        output_dir=str(output_dir),
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        warmup_steps=warmup_steps,
        max_seq_len=max_seq_len,
        loss=LOSS,
        scheduler=scheduler,
        weight_decay=weight_decay,
        max_grad_norm=max_grad_norm,
        eval_steps=eval_steps,
        validation_fraction=validation_fraction,
        train_seed=train_seed,
        pairs_seed=FINETUNE_SEED,
        num_train_pairs=len(train_pairs),
        num_dev_pairs=len(dev_pairs),
        num_positives=sum(1 for p in pairs if p.label == 1),
        num_negatives=sum(1 for p in pairs if p.label == 0),
        wall_clock_seconds=round(wall, 1),
        hardware=_hardware(device),
        best_val_accuracy=round(recording.best, 4),
        dev_majority_baseline=round(majority_baseline, 4),
        dev_pairs_dropped_for_passage_overlap=n_dev_before_guard - len(dev_pairs),
        dev_history=history,
    )


def render_report(pair_report, training: TrainingReport) -> str:
    """Render ``reports/finetune.md`` from the pair and training reports."""
    p = pair_report
    return f"""# Fine-tuning report (Task 36)

Cross-encoder fine-tuning on HotpotQA data disjoint from the evaluation set.

## Training data

- seed: `{p.seed}`
- training questions: {p.num_train_questions}
- positives (gold paragraphs): {p.num_positives}
- negatives (distractor paragraphs): {p.num_negatives}
- pos:neg ratio: {p.ratio:.3f}
- excluded evaluation questions: {p.excluded_question_count}
- excluded evaluation passages (gold + distractor): {p.excluded_passage_count}
- remaining training-pool size: {p.remaining_pool_size}
- questions dropped for overlapping the eval set: {p.dropped_id_overlap} by passage id,
  {p.dropped_text_overlap} by normalized text only

## Hyperparameters

| Parameter | Value |
|-----------|-------|
| base checkpoint | `{training.base_checkpoint}` |
| epochs | {training.epochs} |
| batch size | {training.batch_size} |
| learning rate | {training.learning_rate} |
| warmup steps | {training.warmup_steps} |
| max sequence length | {training.max_seq_len} |
| loss | `{training.loss}` |
| scheduler | `{training.scheduler}` |
| weight decay | {training.weight_decay} |
| max grad norm | {training.max_grad_norm} |
| eval steps | {training.eval_steps} |
| validation fraction | {training.validation_fraction} |

## Seeds

- pairs seed: `{training.pairs_seed}`
- train/dev split seed, and `transformers.set_seed` before training: `{training.train_seed}`
- trainer seed inside the legacy `CrossEncoder.fit`: `42` (HF default; not settable through `fit`)

## Split

- train pairs: {training.num_train_pairs}
- dev pairs: {training.num_dev_pairs}
- split by question ID (no query text spans both splits)
- dev pairs dropped (passage also in train): {training.dev_pairs_dropped_for_passage_overlap}

## Run

- best dev accuracy: {training.best_val_accuracy:.4f}
  (majority-class baseline, same dev pairs: {training.dev_majority_baseline:.4f})
- checkpoint selection: best-dev-accuracy checkpoint kept (`save_best_model`);
  **no early stopping**, all epochs run. Selection reads dev pairs carved from the
  training sample only; the evaluation set is never read.
- per-evaluation dev history: `{training.output_dir}/dev-history.json`
  ({len(training.dev_history)} evaluations)
- wall clock: {training.wall_clock_seconds}s
- hardware: `{training.hardware}`
- output: `{training.output_dir}`

## Reproducibility (read before trusting a rerun)

Training ran on MPS (Apple GPU), whose kernels are not bit-deterministic, and the
legacy `CrossEncoder.fit` seeds its own trainer with 42. Rerunning with the same
seeds reproduces the *training data* exactly (pairs seed, split seed) but **not**
the weights bit-for-bit; expect small run-to-run differences in the fine-tuned
scores. The before/after comparison in `reports/comparison.md` is therefore one
training run, not an average over runs. Dev accuracy near the majority-class
baseline would mean the classifier barely learned the task; compare the two
numbers above.
"""
