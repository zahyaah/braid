# Braid — Implementation Plan

Derived from the approved `CAPABILITY-MAP.md` and `SPEC.md` (approved
2026-09-23) plus the seven module specs. Phase 2 of spec-driven development.

## Dependency graph

```
                            ┌── queryset ──> eval ──────┐
ingest ──> FREEZE (D6) ─────┤                           ├──> query ──> finetune
                            └── extract ──> index ──────┘
                                              ^
                                    (index also needs ingest)
```

The freeze is a node, not a detail. Nothing may author a relevance judgment
against an unfrozen corpus (decision D6), so it sits on the only path between
`ingest` and `queryset`.

`eval` depends only on `queryset`, not on any retriever — it is built and
tested against a stub. That is what allows the harness to exist before the code
it judges, which acceptance criteria 1 through 4 require.

## Sequencing, and why this order

1. **ingest** — everything addresses passages by its IDs. Nothing can be
   labeled or indexed before IDs are stable.
1a. **freeze (D6)** — dedupe runs, the manifest records a `corpus_hash` over
   sorted `(passage_id, text)` pairs, and the corpus is frozen in a
   single-purpose commit. After this point a gold-passage remap is a judgment
   change and therefore ask-first, not an ingest fix.
2. **queryset** — labels must be committed before any retrieval code, and the
   git history is the proof (decision D4, and criterion-3/4 credibility).
   Drafting and review are split per category, so one category can be reviewed
   and committed while another is still being drafted. Decision D3's size is
   locked at **Checkpoint B1, before drafting begins**, because the size
   determines how many queries get drafted; D3's end-of-module fallback stays
   available until Checkpoint B.
3. **eval** — the harness and its statistics are verified against stubs and
   synthetic data with known answers. No configuration may be called "better"
   before this exists.
4. **extract** — offline batch, no containers running (8 GiB constraint).
   Produces the quality report that de-risks criterion 3 early.
5. **index** — BM25, then FAISS, then Neo4j. One store at a time, each with a
   `health()` check, so the three-service stack's boring failures are isolated.
6. **query** — `bm25` scored, then `dense` scored, then graph candidates, then
   RRF, then rerank. Each stage scored by `eval` before the next starts.
7. **finetune** — last, because it needs both a working `fused-rerank` baseline
   and a trustworthy comparison harness.

Steps 2–3 and 4 are independent after step 1 and could run in parallel; the
serial order above is the default, since debugging two unfamiliar surfaces at
once is the thing workflow step 4 exists to prevent.

## Task list

40 tasks in `tasks/todo.md`, ordered by dependency, each sized S or M, with
nine human-reviewed checkpoints. Two hard gates:

- **Checkpoint B1** — the D3 size lock, its own gate rather than part of a
  task, because it decides how much drafting happens.
- **Checkpoint B** — no retrieval code before the labeled query set is
  committed. Its git audit covers three hashes in order (corpus freeze, query
  set, first retrieval commit) and whitelists interface-only commits to
  `braid/query/`: the `Retriever` Protocol and `Hit` dataclass, no function
  body beyond `...`, checked mechanically.

## Verification checkpoints

| After | Gate |
|---|---|
| ingest | Rerun produces byte-identical corpus; no dangling supporting-passage IDs |
| freeze | `frozen: true`; `corpus_hash` recorded; freeze commit touches only the manifest; a write to a frozen passage aborts |
| size lock (B1) | Final size committed — 180 or 90 — before any query is drafted; README limitation text written now if 90 |
| queryset | Validator exits 0; labels committed; every query's `corpus_hash` matches the manifest; 100% review coverage per drafted category |
| eval | Bootstrap passes known-answer synthetic tests, including the paired-vs-unpaired test |
| extract | `reports/extraction-quality.md` exists with Wilson intervals; triple-count histogram reviewed against criterion-3 risk |
| index | `index health` reports populated for all three; incremental add verified |
| query | Each configuration scored by `eval` before the next is started; D5 parameters read from one constants module; D1 latency measured with warm-up count, concurrency 1, rerank depth, and swap samples; any D7 fallback recorded |
| finetune | Leakage assertion passes on real data and aborts on the contaminated fixture |
| release | `./scripts/reproduce.sh` regenerates every README number from a clean checkout |

## Risks and mitigations

| Risk | Mitigation | Owner phase |
|---|---|---|
| 8 GiB RAM with two JVMs + torch | Capped heaps; `extract` runs offline with containers down; separate processes for embedding and indexing | index, extract |
| Extraction yield too low for criterion 3 | Quality report at extraction time, before the graph is built; documented pattern expansion or reported negative finding | extract |
| Bootstrap pairing bug produces plausible wrong CIs | Known-answer synthetic tests + paired-vs-unpaired test + fresh-context adversarial review | eval |
| Rerank latency breaks D1 p95 | Measure early in `query`; levers are rerank depth (reported), batching, MPS; threshold change is ask-first | query |
| Fine-tune leakage | Assertion on question and passage IDs, tested with a contaminated fixture | finetune |
| Wide per-category CIs at n=30 | Decision D3 primary target of 60/category; limitation stated in README if the minimum is used | queryset |
| A gold passage needs remapping after judgments exist | Freeze makes it impossible to do silently; it becomes an ask-first judgment change (D6) | freeze |
| Fusion/graph parameters tuned into the eval set | D5 pins every value a priori, in one constants module, asserted by test; tuning happens only on the D2 training slice | query |
| Criterion 3 met by picking favorable queries | Amendment 3 makes the count exhaustive over all multi-hop queries, with the denominator and losing queries in the same table | eval |
| Latency passes only because the machine is swapping | Swap and memory-pressure samples captured alongside every latency figure | eval |
| Distractor-passage leakage into fine-tuning | Excluded set is the union of evaluation gold and distractor passages; a distractor-only contaminated fixture must abort the run | finetune |
| Near-duplicate removal deletes gold evidence | Remap-or-drop assertion, counted in the manifest | ingest |

## Deliverable at the end

`./scripts/reproduce.sh` on a clean checkout: builds indexes, runs all five
configurations, regenerates every table, CI, latency figure, and the
extraction-quality and fine-tuning reports — matching the README exactly
(criterion 6).
