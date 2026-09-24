"""Disjoint fine-tuning pair construction with a leakage assertion (SPEC-finetune.md).

Decision D2 quarantines the evaluation query set: no evaluation question ID and
no evaluation passage ID — gold *or* distractor (amendment 4) — may appear in
the training pairs. The leakage check is an assertion that aborts the run on any
overlap, not a review step.

Training questions are drawn with a recorded seed from HotpotQA questions that
are disjoint from the evaluation set. Positives are a question's gold supporting
paragraphs; hard negatives are its distractor paragraphs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from braid.eval.queryset.schema import (
    QUERIES_FILE,
    QUERYSET_DIR,
    LabeledQuery,
    read_queries,
)
from braid.ingest.loader import SPLIT, load_hotpotqa
from braid.ingest.models import write_jsonl
from braid.ingest.normalize import join_sentences, normalize_text, passage_id

# Distinct from the ingest seed (20260923) so the training sample is a genuinely
# different draw than the corpus sample, and reproducible on its own.
FINETUNE_SEED = 20260924
DEFAULT_NUM_TRAIN_QUESTIONS = 300

PAIRS_PATH = Path("data/finetune-pairs.jsonl")
PAIR_MANIFEST_PATH = Path("data/finetune-pairs-manifest.json")


class LeakageError(ValueError):
    """Raised when a training question or passage overlaps the evaluation set."""


@dataclass(frozen=True)
class PassageRef:
    """A content-addressed passage reference, mirroring the ingest loader."""

    passage_id: str
    title: str
    text: str

    def display(self) -> str:
        return f"{self.title}: {self.text}"


@dataclass(frozen=True)
class QuestionPassages:
    """One HotpotQA question with its gold and distractor passages resolved."""

    question_id: str
    question: str
    gold: tuple[PassageRef, ...]
    distractors: tuple[PassageRef, ...]


@dataclass(frozen=True)
class ExclusionSets:
    """IDs that must not appear in training pairs."""

    question_ids: frozenset[str]
    passage_ids: frozenset[str]
    # Normalized body-text keys of every excluded passage (see `text_key`).
    # ID-only exclusion fails open for a passage that is textually the same but
    # hashes to a different `passage_id` (title casing, an HTML entity, a
    # whitespace variant) -- found by adversarial review.
    passage_text_keys: frozenset[str] = frozenset()


def text_key(text: str) -> str:
    """Normalization for text-level leak detection: HTML-unescape, NFKC,
    casefold, collapse whitespace. Deliberately looser than `passage_id`."""
    import html
    import unicodedata

    folded = unicodedata.normalize("NFKC", html.unescape(text)).casefold()
    return " ".join(folded.split())


@dataclass(frozen=True)
class Pair:
    """One (query, passage, label) training example for a cross-encoder."""

    guid: str
    query: str
    passage: str
    label: int


@dataclass(frozen=True)
class PairReport:
    seed: int
    num_train_questions: int
    num_positives: int
    num_negatives: int
    excluded_question_count: int
    excluded_passage_count: int
    remaining_pool_size: int
    # Candidate questions removed because they overlapped the evaluation set.
    # Reported so the (otherwise silent) filter is visible, not just implied by
    # a smaller pool.
    dropped_id_overlap: int = 0
    dropped_text_overlap: int = 0

    @property
    def ratio(self) -> float:
        """Positives : negatives ratio (positives per negative)."""
        return self.num_positives / self.num_negatives if self.num_negatives else float("nan")

    def to_json(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "num_train_questions": self.num_train_questions,
            "num_positives": self.num_positives,
            "num_negatives": self.num_negatives,
            "pos_neg_ratio": self.ratio,
            "excluded_question_count": self.excluded_question_count,
            "excluded_passage_count": self.excluded_passage_count,
            "remaining_pool_size": self.remaining_pool_size,
            "dropped_id_overlap": self.dropped_id_overlap,
            "dropped_text_overlap": self.dropped_text_overlap,
        }


def _row_passages(row: dict[str, Any]) -> QuestionPassages:
    """Resolve one HotpotQA row into gold + distractor passage refs.

    Mirrors ``braid.ingest.loader._build_passages`` and ``_build_question`` so the
    content-addressed passage IDs are byte-identical to the committed corpus.
    """
    by_title: dict[str, PassageRef] = {}
    for title, sentences in zip(row["context"]["title"], row["context"]["sentences"], strict=True):
        text, _spans = join_sentences(list(sentences))
        if not text:
            continue
        ref = PassageRef(passage_id(title, text), normalize_text(title), text)
        # Overwrite to match loader._build_passages, which keeps the last entry
        # for a duplicate normalized title.
        by_title[normalize_text(title)] = ref

    gold_ids: list[str] = []
    for title in row["supporting_facts"]["title"]:
        ref = by_title.get(normalize_text(title))
        if ref is not None and ref.passage_id not in gold_ids:
            gold_ids.append(ref.passage_id)

    gold_set = set(gold_ids)
    gold = tuple(r for r in by_title.values() if r.passage_id in gold_set)
    distractors = tuple(r for r in by_title.values() if r.passage_id not in gold_set)
    return QuestionPassages(
        question_id=row["id"],
        question=normalize_text(row["question"]),
        gold=gold,
        distractors=distractors,
    )


def compute_exclusion_sets(
    queries: Sequence[LabeledQuery],
    row_by_id: dict[str, dict[str, Any]],
    corpus_texts: dict[str, str] | None = None,
) -> ExclusionSets:
    """The union of every evaluation question's IDs and referenced passage IDs.

    Amendment 4: the excluded passage set covers *every* passage referenced by an
    evaluation query — gold AND distractor — not gold alone. For the 60 multi-hop
    queries (origin=hotpotqa, source_question_id set) the distractors are not
    stored anywhere, so they are recomputed from the source row here.

    Fails closed: a multi-hop query whose source question cannot be found used to
    silently shrink the exclusion set (its distractors simply weren't added).
    That now raises, since an unresolvable source question means the exclusion
    set cannot be trusted. Likewise, when `corpus_texts` is given, a relevant
    passage id missing from it raises rather than being skipped.
    """
    question_ids: set[str] = set()
    passage_ids: set[str] = set()
    keys: set[str] = set()

    for query in queries:
        passage_ids.update(query.relevant.keys())
        if corpus_texts is not None:
            for pid in query.relevant:
                if pid not in corpus_texts:
                    raise LeakageError(
                        f"evaluation query {query.query_id} references passage {pid} "
                        "that is not in the corpus; cannot build its text exclusion key"
                    )
                keys.add(text_key(corpus_texts[pid]))
        if query.source_question_id:
            question_ids.add(query.source_question_id)
            row = row_by_id.get(query.source_question_id)
            if row is None:
                raise LeakageError(
                    f"evaluation query {query.query_id} has source_question_id "
                    f"{query.source_question_id!r} that is not in the dataset; "
                    "its distractors cannot be excluded"
                )
            qp = _row_passages(row)
            for ref in (*qp.gold, *qp.distractors):
                passage_ids.add(ref.passage_id)
                keys.add(text_key(ref.text))

    return ExclusionSets(frozenset(question_ids), frozenset(passage_ids), frozenset(keys))


def assert_no_leakage(questions: Sequence[QuestionPassages], exclusion: ExclusionSets) -> None:
    """Abort on any overlap between training questions/passages and the eval set."""
    problems: list[str] = []
    for qp in questions:
        if qp.question_id in exclusion.question_ids:
            problems.append(f"question id {qp.question_id} is an evaluation question")
        for ref in (*qp.gold, *qp.distractors):
            if ref.passage_id in exclusion.passage_ids:
                problems.append(
                    f"passage {ref.passage_id} (from question {qp.question_id}) "
                    "overlaps the evaluation set"
                )
            elif text_key(ref.text) in exclusion.passage_text_keys:
                problems.append(
                    f"passage {ref.passage_id} (from question {qp.question_id}) has the "
                    "same normalized text as an evaluation passage under a different id"
                )
    if problems:
        detail = "; ".join(problems[:10])
        raise LeakageError(
            f"training data overlaps the evaluation set ({len(problems)} overlaps): {detail}"
        )


def build_training_questions(
    dataset,
    queries: Sequence[LabeledQuery],
    *,
    seed: int = FINETUNE_SEED,
    num_questions: int = DEFAULT_NUM_TRAIN_QUESTIONS,
    corpus_texts: dict[str, str] | None = None,
) -> tuple[list[QuestionPassages], PairReport]:
    """Draw `num_questions` HotpotQA questions disjoint from the evaluation set."""
    row_by_id = {row["id"]: row for row in dataset}
    exclusion = compute_exclusion_sets(queries, row_by_id, corpus_texts)

    candidates: list[QuestionPassages] = []
    dropped_id = dropped_text = 0
    for row in dataset:
        if row["id"] in exclusion.question_ids:
            continue
        qp = _row_passages(row)
        if not qp.gold:
            continue  # no resolvable gold; cannot build positives
        refs = (*qp.gold, *qp.distractors)
        if {r.passage_id for r in refs} & exclusion.passage_ids:
            dropped_id += 1
            continue  # any gold OR distractor overlap → drop the whole question
        if any(text_key(r.text) in exclusion.passage_text_keys for r in refs):
            dropped_text += 1
            continue  # same text under a different id → drop the whole question
        candidates.append(qp)

    rng = np.random.default_rng(seed)
    order = rng.permutation(len(candidates))
    selected = [candidates[i] for i in order[:num_questions]]

    # Defense in depth: the filter above should already guarantee disjointness.
    assert_no_leakage(selected, exclusion)

    report = PairReport(
        seed=seed,
        num_train_questions=len(selected),
        num_positives=sum(len(qp.gold) for qp in selected),
        num_negatives=sum(len(qp.distractors) for qp in selected),
        excluded_question_count=len(exclusion.question_ids),
        excluded_passage_count=len(exclusion.passage_ids),
        remaining_pool_size=len(candidates),
        dropped_id_overlap=dropped_id,
        dropped_text_overlap=dropped_text,
    )
    return selected, report


def build_pairs(questions: Sequence[QuestionPassages]) -> list[Pair]:
    """Flatten questions into (query, passage, label) cross-encoder examples."""
    pairs: list[Pair] = []
    for qp in questions:
        for i, ref in enumerate(qp.gold):
            pairs.append(
                Pair(
                    guid=f"{qp.question_id}:pos:{i}",
                    query=qp.question,
                    passage=ref.display(),
                    label=1,
                )
            )
        for i, ref in enumerate(qp.distractors):
            pairs.append(
                Pair(
                    guid=f"{qp.question_id}:neg:{i}",
                    query=qp.question,
                    passage=ref.display(),
                    label=0,
                )
            )
    return pairs


def write_pairs(path: Path, pairs: Sequence[Pair]) -> int:
    """Write pairs as JSONL, returning the count."""
    rows = [
        {"guid": p.guid, "query": p.query, "passage": p.passage, "label": p.label}
        for p in pairs
    ]
    return write_jsonl(path, rows)


def write_manifest(path: Path, report: PairReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(path, [report.to_json()])


def build_pairs_from_disk(
    *,
    seed: int = FINETUNE_SEED,
    num_questions: int = DEFAULT_NUM_TRAIN_QUESTIONS,
    queryset_dir: Path = QUERYSET_DIR,
) -> tuple[list[Pair], PairReport]:
    """End-to-end: load HotpotQA + eval queries, build disjoint pairs, write files."""
    from braid.ingest.models import load_corpus

    queries = read_queries(queryset_dir / QUERIES_FILE)
    dataset = load_hotpotqa(SPLIT)
    corpus_texts = {p.passage_id: p.text for p in load_corpus(Path("data/corpus.jsonl"))}
    questions, report = build_training_questions(
        dataset, queries, seed=seed, num_questions=num_questions, corpus_texts=corpus_texts
    )
    pairs = build_pairs(questions)
    write_pairs(PAIRS_PATH, pairs)
    write_manifest(PAIR_MANIFEST_PATH, report)
    return pairs, report


if __name__ == "__main__":  # pragma: no cover - convenience entrypoint
    import sys

    seed = int(sys.argv[1]) if len(sys.argv) > 1 else FINETUNE_SEED
    num = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_NUM_TRAIN_QUESTIONS
    pairs, report = build_pairs_from_disk(seed=seed, num_questions=num)
    print(
        f"built {len(pairs)} pairs from {report.num_train_questions} questions "
        f"(pos {report.num_positives}, neg {report.num_negatives}, "
        f"ratio {report.ratio:.3f}); excluded {report.excluded_question_count} questions, "
        f"{report.excluded_passage_count} passages; pool {report.remaining_pool_size}"
    )
    print(f"pairs -> {PAIRS_PATH}")
    print(f"manifest -> {PAIR_MANIFEST_PATH}")
