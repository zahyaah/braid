# Fine-tuning report (Task 36)

Cross-encoder fine-tuning on HotpotQA data disjoint from the evaluation set.

## Training data

- seed: `20260924`
- training questions: 300
- positives (gold paragraphs): 600
- negatives (distractor paragraphs): 2390
- pos:neg ratio: 0.251
- excluded evaluation questions: 60
- excluded evaluation passages (gold + distractor): 642
- remaining training-pool size: 7184
- questions dropped for overlapping the eval set: 161 by passage id,
  0 by normalized text only

## Hyperparameters

| Parameter | Value |
|-----------|-------|
| base checkpoint | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| epochs | 3 |
| batch size | 8 |
| learning rate | 2e-05 |
| warmup steps | 100 |
| max sequence length | 256 |
| loss | `BinaryCrossEntropyLoss` |
| scheduler | `WarmupLinear` |
| weight decay | 0.01 |
| max grad norm | 1.0 |
| eval steps | 50 |
| validation fraction | 0.1 |

## Seeds

- pairs seed: `20260924`
- train/dev split seed, and `transformers.set_seed` before training: `20260925`
- trainer seed inside the legacy `CrossEncoder.fit`: `42` (HF default; not settable through `fit`)

## Split

- train pairs: 2691
- dev pairs: 299
- split by question ID (no query text spans both splits)
- dev pairs dropped (passage also in train): 0

## Run

- best dev accuracy: 0.8930
  (majority-class baseline, same dev pairs: 0.7993)
- checkpoint selection: best-dev-accuracy checkpoint kept (`save_best_model`);
  **no early stopping**, all epochs run. Selection reads dev pairs carved from the
  training sample only; the evaluation set is never read.
- per-evaluation dev history: `models/ce-braid/dev-history.json`
  (23 evaluations)
- wall clock: 415.1s
- hardware: `macOS-26.2-arm64-arm-64bit (arm64); torch device=mps`
- output: `models/ce-braid`

## Reproducibility (read before trusting a rerun)

Training ran on MPS (Apple GPU), whose kernels are not bit-deterministic, and the
legacy `CrossEncoder.fit` seeds its own trainer with 42. Rerunning with the same
seeds reproduces the *training data* exactly (pairs seed, split seed) but **not**
the weights bit-for-bit; expect small run-to-run differences in the fine-tuned
scores. The before/after comparison in `reports/comparison.md` is therefore one
training run, not an average over runs. Dev accuracy near the majority-class
baseline would mean the classifier barely learned the task; compare the two
numbers above.
