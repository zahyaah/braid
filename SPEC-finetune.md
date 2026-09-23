# Spec: `finetune`

Module id `finetune`. Directory `/finetune` → `braid/finetune/`. Depends on:
`query`, `eval`.

## Objective

Fine-tune the cross-encoder on data disjoint from the evaluation set, and
compare it against the pretrained baseline on the held-out evaluation set with
the same confidence-interval treatment as criterion 2.

## Decision D2 is the whole design constraint

The evaluation query set is never used for training, early stopping, or model
selection. Training data comes from a disjoint HotpotQA question sample.

- Training sample is drawn with a recorded seed from HotpotQA questions **not**
  in the evaluation set.
- Positives: the question's gold supporting paragraphs. Hard negatives: that
  question's distractor paragraphs. Ratio and count recorded.
- **Leakage check is an assertion, not a review step.** Before training, the
  pipeline asserts an empty intersection on question IDs *and* on passage IDs
  between the training pairs and the evaluation set. A non-empty intersection
  aborts the run. The check's output is written into the report.
- **Passage-overlap scope is every referenced passage, not gold only**
  (amendment 4). The excluded set is the union, over every evaluation question,
  of its gold supporting passages **and** its distractor passages. All of them
  are removed from the training pool. Training on an evaluation question's
  distractor teaches the model that that exact passage is a negative for a
  near-identical query, which is test-set information even though the passage
  is not a gold answer. The assertion is against this full union, and any
  intersection aborts the run.
- Early stopping and checkpoint selection use a validation split carved from
  the training sample. The evaluation set is untouched until the final
  comparison.

## In scope

- Pair construction from the disjoint sample, written to
  `data/finetune-pairs.jsonl` with the seed and counts.
- Training via sentence-transformers' `CrossEncoder` trainer. Every
  hyperparameter recorded in `reports/finetune.md`: base checkpoint, epochs,
  batch size, learning rate, warmup, max sequence length, loss, seed, wall
  clock, hardware.
- Before/after comparison on the held-out evaluation set: `fused-rerank`
  versus `fused-rerank-ft`, all four metrics, per category and pooled, each
  difference with a paired-bootstrap 95% CI from `eval.compare`, and an
  explicit statement per category of whether the interval excludes zero.

## Out of scope

Training any other model. Tuning retrieval parameters against the evaluation
set (an explicit "never" in SPEC.md).

## Acceptance

- [ ] Leakage assertion implemented against the full union of evaluation gold
      **and** distractor passage IDs, plus question IDs.
- [ ] Tested with two deliberately contaminated fixtures that must each abort
      the run: one sharing a gold passage, one sharing only a distractor
      passage. The second is the one a gold-only check would miss.
- [ ] The excluded-set size and the remaining training-pool size are both
      recorded in the report, so an over-aggressive exclusion is visible.
- [ ] `reports/finetune.md` records every hyperparameter and both seeds.
- [ ] Before/after numbers reported for all four metrics, per category and
      pooled, each with a CI, each with "excludes zero: yes/no".
- [ ] Rerunning with the recorded seed reproduces the reported numbers.
- [ ] A result where fine-tuning does not help is reported as a finding at the
      same prominence as a positive one (SPEC.md Boundaries).

## Verify

`pytest tests/finetune -q`, then `python -m braid.finetune --out models/ce-braid`,
then `python -m braid.eval --all-configs --bootstrap 1000`.

## Risks

Per workflow step 7 this module gets an adversarial fresh-context review before
its numbers are trusted. Most likely silent failures, in order: the leakage
check passing because it compares the wrong ID fields, or because it was scoped
to gold passages only (amendment 4); a training run that
improves training loss and degrades held-out ranking; a comparison that reports
the fine-tuned model's numbers against a baseline evaluated under different
rerank depth or candidate pool. The last is prevented by both configurations
sharing the `fused` candidate list and rerank depth exactly.
