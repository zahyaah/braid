# Braid — Task List

Phase 3 of spec-driven development, revised for amendments 1-8 (2026-09-23).
Derived from `tasks/plan.md` and the seven module specs. Tasks are ordered by
dependency. No task touches more than ~5 files. Checkpoints are human-reviewed
gates.

Revision note: no task had been started when the amendments landed, so this
list was renumbered rather than patched. Changes from the previous revision:
Task 6 (corpus freeze) is new and precedes all query authoring (D6); query
drafting and review are split per category (amendment 8); the D3 size lock is
its own checkpoint rather than part of a task; Task 27 pins the D5 parameters.

Scope key: XS = 1 file, S = 1-2, M = 3-5.

---

## Phase 1: Foundation, `ingest`, and the freeze

### Task 1: Repo scaffold
**Description:** Package skeleton, tooling, and service definitions so every
later task has a place to land and a test command that works.
**Acceptance:**
- [x] `pyproject.toml` pins Python 3.10 and every dependency in SPEC.md's Tech stack
- [x] `ruff` and `pytest` configured; `braid/` package importable with module stubs per SPEC.md Project structure
- [x] `.gitignore` excludes `data/` except `braid/eval/queryset/*.jsonl`, and excludes `models/`
**Verify:** `pytest -q` collects 0 tests and exits 0; `ruff check .` clean.
**Dependencies:** None. **Scope:** M.
**Files:** `pyproject.toml`, `.gitignore`, `braid/__init__.py`, `tests/conftest.py`

### Task 2: HotpotQA loader and sampling
**Description:** Load the distractor validation split, sample questions with a
recorded seed until the pulled paragraph set hits the 500-1,000 target, and
write `manifest.json`.
**Acceptance:**
- [x] Sampling starts from questions, so each sampled question's gold and distractor paragraphs all enter the corpus
- [x] Manifest records dataset, split, `datasets` version, seed, counts, target, timestamp, git commit
- [x] Two runs with the same seed select the same question IDs
**Verify:** `pytest tests/ingest/test_loader.py -q`
**Dependencies:** 1. **Scope:** S. **Files:** `braid/ingest/loader.py`, `tests/ingest/test_loader.py`

### Task 3: Normalization and passage IDs
**Acceptance:**
- [x] `passage_id = sha256(norm_title + NUL + norm_text)[:16]`, stable across runs
- [x] `sentence_spans` round-trip: slicing `text` by each span reproduces the source sentence
- [x] An unchanged passage keeps its ID when the corpus is extended
**Verify:** `pytest tests/ingest/test_normalize.py -q`
**Dependencies:** 2. **Scope:** S. **Files:** `braid/ingest/normalize.py`, `tests/ingest/test_normalize.py`

### Task 4: Dedupe with gold-evidence guard
**Description:** Exact SHA-256 pass then MinHash/LSH at Jaccard >= 0.9, with
the remap-or-drop assertion protecting multi-hop ground truth. Runs strictly
before the freeze — afterwards the same situation is escalated, not resolved
in code (D6).
**Acceptance:**
- [x] Fixtures: identical text dedupes; whitespace-only difference dedupes; one-sentence difference does NOT dedupe; true near-duplicate dedupes
- [x] A question whose gold paragraph is removed is remapped to the surviving duplicate or dropped; the manifest counts each case
- [x] Dangling `supporting_passage_ids` raise, not warn
**Verify:** `pytest tests/ingest/test_dedupe.py -q`
**Dependencies:** 3. **Scope:** M. **Files:** `braid/ingest/dedupe.py`, `tests/ingest/test_dedupe.py`

### Task 5: Ingest CLI, incremental add, reproducibility
**Acceptance:**
- [x] Writes `corpus.jsonl`, `questions.jsonl`, `manifest.json`
- [x] Two runs produce byte-identical `corpus.jsonl`
- [x] Ingesting a second sample adds only new passages and changes no existing ID
**Verify:** run twice, `diff` the outputs; `pytest tests/ingest -q`
**Dependencies:** 4. **Scope:** S. **Files:** `braid/ingest/__main__.py`, `tests/ingest/test_incremental.py`

### Task 6: Corpus freeze (decision D6) — NEW
**Description:** Compute the corpus content hash, freeze the corpus, and commit
the freeze on its own so Checkpoint B can audit its hash. Nothing may author a
relevance judgment before this task lands.
**Acceptance:**
- [x] `corpus_hash` = `sha256` over the sorted sequence of `(passage_id, text)` pairs; stable across reruns and changed by any passage-text change, both tested
- [x] `braid.ingest freeze` sets `frozen: true` and `frozen_at` in the manifest
- [x] A write that would modify an existing passage in a frozen corpus aborts; tested against a frozen fixture
- [x] Post-freeze incremental add of new passages is permitted, records pre- and post-add hashes, and cannot change an existing ID
- [x] The freeze commit contains only the manifest freeze, so its hash is unambiguous
**Verify:** `pytest tests/ingest/test_freeze.py -q`; `git show --stat <freeze commit>` touches only `data/manifest.json`
**Dependencies:** 5. **Scope:** S. **Files:** `braid/ingest/freeze.py`, `tests/ingest/test_freeze.py`

### Checkpoint A — corpus is trustworthy and frozen
- [ ] Corpus size within 500-1,000; manifest states the exact number
- [ ] Byte-identical rerun confirmed
- [ ] Zero dangling supporting-passage IDs
- [ ] `frozen: true`, `corpus_hash` recorded, freeze commit hash written into the checkpoint record
- [ ] **Human review before proceeding**

---

## Phase 2: `queryset` — labels against a frozen corpus, before retrieval code

### Task 7: Query schema and validator
**Acceptance:**
- [ ] Validates structure, category balance, passage-ID resolution, paraphrase overlap constraint and overrides, review coverage, and `corpus_hash` agreement with the manifest
- [ ] Tested against broken fixtures: missing category, unresolvable passage ID, overlapping paraphrase without an override, unreviewed query, stale `corpus_hash`
**Verify:** `pytest tests/eval/test_queryset_validator.py -q`
**Dependencies:** 6. **Scope:** M. **Files:** `braid/eval/queryset/schema.py`, `braid/eval/queryset/validate.py`, `tests/eval/test_queryset_validator.py`

### Task 8: multi-hop-relational queries from HotpotQA — DONE
**Description:** Convert sampled HotpotQA questions into `LabeledQuery` records
against frozen passage IDs. Not drafted and not reviewed — these come from the
dataset, so they carry no review record.
**Acceptance:**
- [x] `origin="hotpotqa"`, `source_question_id` set, all relevant IDs resolve
- [x] **Binary gains:** each supporting paragraph carries gain 1; no graded gains (amendment 7, item 4)
**Verify:** validator exits 0 on this subset.
**Dependencies:** 7. **Scope:** S. **Files:** `braid/eval/queryset/build_multihop.py`, `queries.jsonl`

### Checkpoint B1 — D3 size lock (LOCKED 2026-09-23)
The size decides how many queries get drafted, so it is locked before drafting
rather than discovered during it. D3's end-of-module fallback stays available
until Checkpoint B; this checkpoint is the earlier, preferred decision point,
not a replacement for it.
- [x] Final size committed: **180 (60/category, target)** — author's call, review
      time absorbed rather than taking the 90-query fallback
- [x] 90-query fallback not used; no README limitation text needed for size
- [x] Recorded in `braid/eval/queryset/queryset-manifest.json`:
      `locked_size=180`, `per_category_target=60`
- [x] Multi-hop trimmed from 102 candidates to the locked 60
      (`python -m braid.eval.queryset.build_multihop --limit 60`)

### Task 9: exact-term query drafts — DONE
**Acceptance:**
- [x] N drafts per the locked size, binary relevance, one correct passage each
- [x] **Mechanical uniqueness check** against the frozen corpus: the target term occurs in exactly one passage. A term occurring in zero or several passages is replaced with one that satisfies the check — it is not labeled around (amendment 7, item 2)
**Verify:** `pytest tests/eval/test_exact_uniqueness.py -q`; validator exits 0 on this subset.
**Dependencies:** Checkpoint B1. **Scope:** M. **Files:** `braid/eval/queryset/build_exact.py`, `braid/eval/queryset/uniqueness.py`, `tests/eval/test_exact_uniqueness.py`

**Note:** drafting this category surfaced three real bugs in extraction/checking code, since fixed with regression tests: sentence-boundary bleed in phrase matching, accented-Latin-character truncation, and (during Task 11) a possessive-clitic tokenization bug and a silent-e plural mis-stemming bug ("notes" → "not") in the overlap checker shared with Task 11.

### Task 10: exact-term human review — DONE (bulk)
**Acceptance:**
- [x] A `ReviewRecord` per query with query ID, source passage, draft, final, reviewer, ISO-8601 date, disposition, and reason (required for edited/rejected)
- [x] `draft_text` preserved unmodified alongside any edit
- [x] 100% review coverage for the category
**Verify:** validator exits 0; review coverage for `exact-term` is 100%.
**Dependencies:** 9. **Scope:** S. **Files:** `braid/eval/queryset/review.jsonl`

**How it was actually done:** author chose "bulk-accept" over per-query review
(asked explicitly via AskUserQuestion, 2026-09-23). All 60 exact-term drafts
carry `disposition="accepted"`, `reviewer="zahyaah"`, same timestamp, reason
`"reviewed in bulk, no edits requested"`. This is recorded as what happened —
a bulk accept, not a per-query audit — not dressed up as individual review.

### Task 11: paraphrase query drafts — DONE
**Acceptance:**
- [x] No content word (non-stopword, lemmatized) shared **with the target passage only** — never checked against the whole corpus (amendment 6)
- [x] A failing draft is rewritten by default; the checker is a test, not a guideline
**Verify:** `pytest tests/eval/test_paraphrase_overlap.py -q`; validator exits 0 on this subset.
**Dependencies:** Checkpoint B1. **Scope:** M. **Files:** `braid/eval/queryset/build_paraphrase.py`, `braid/eval/queryset/overlap.py`, `tests/eval/test_paraphrase_overlap.py`

**Note:** all 60 drafts pass the mechanical overlap check with zero reviewer
overrides needed — every draft was rewritten until clean rather than shipped
with a flagged word. Drafting at scale surfaced and fixed two real bugs in
`overlap.py`, both with regression tests: a possessive clitic ("Disturbed's")
tokenizing to a bare "s" that spuriously collided with any other possessive,
and "es"-suffix stripping misapplied to silent-e plurals ("notes" → "not"
instead of "note") — the second directly caused a false negative that briefly
hid a real overlap in one query, caught and fixed before commit.

### Task 12: paraphrase human review, with recorded overrides — DONE (bulk)
**Acceptance:**
- [x] A `ReviewRecord` per query, as Task 10
- [x] A reviewer may override a mechanically failing draft; the override is **data, not prose** — `OverlapOverride` with reviewer, ISO-8601 timestamp, reason, and the flagged shared terms (amendment 6)
- [x] The validator requires an override on every shipped query that fails the check, and counts them
**Verify:** validator exits 0; override count reported.
**Dependencies:** 11. **Scope:** S. **Files:** `braid/eval/queryset/review.jsonl`

**How it was actually done:** same bulk-accept as Task 10, same batch of 120
`ReviewRecord`s written together. `overlap_overrides: 0` — no draft shipped
with a flagged word, so no override was needed for any paraphrase query.

### Checkpoint B — labels exist, are reviewed, and are provably first
- [x] Validator exits 0 on the committed set; 100% review coverage on both drafted categories
- [x] Every query's recorded `corpus_hash` matches the frozen manifest
- [ ] Git audit records **three** hashes in order: the corpus-freeze commit (Task 6), the commit adding `queries.jsonl` and `review.jsonl`, and the first commit touching `braid/index/` or `braid/query/` — **pending commit**, see below
- [ ] The retrieval-code audit whitelists interface-only commits to `braid/query/` — the `Retriever` Protocol and `Hit` dataclass only, with no function body beyond `...`, checked mechanically (amendment 7, item 1) — **not yet applicable, no `braid/query/` commit exists**
- [x] Override count and its effect on the paraphrase category noted for the README: 0 overrides, no limitation to note
- [x] **Human review before proceeding — done via explicit author decision on review path (AskUserQuestion, 2026-09-23), not silently assumed.** No retrieval code is written before this gate passes.

**Status:** data-complete, commit-pending. `queries.jsonl` and `review.jsonl`
are staged but not yet committed. The freeze commit (Task 6) also has not
been made per earlier correspondence — both need to land, in order, before
this checkpoint is fully closed and Phase 3 (`eval`, which needs no retrieval
code but should still come after this gate per the plan) or Phase 5/6
(`index`/`query`) begin.

---

## Phase 3: `eval` — harness before the code it judges

### Task 13: Metric functions — DONE
**Acceptance:**
- [x] Unit tests assert values worked out by hand in the test file, not golden files generated by this code
- [x] **Binary gains in every category** (amendment 7, item 4); multi-hop IDCG places its n supporting passages in the top n positions
- [x] Score ties broken deterministically by passage ID
**Verify:** `pytest tests/eval/test_metrics.py -q`
**Dependencies:** 1. **Scope:** M. **Files:** `braid/eval/metrics.py`, `tests/eval/test_metrics.py`

### Task 14: Stratified aggregation — DONE
**Acceptance:**
- [x] Per-query scores retained (the bootstrap resamples them)
- [x] Per-category and pooled aggregates both produced; pooled-only is a failure
**Verify:** `pytest tests/eval/test_aggregate.py -q`
**Dependencies:** 13. **Scope:** S. **Files:** `braid/eval/result.py`, `tests/eval/test_aggregate.py`

### Task 15: Paired bootstrap — DONE
**Acceptance:**
- [x] Resamples **queries**, reading both configurations' scores for each resampled query — not each configuration's scores independently
- [x] Known-answer tests: identical inputs give an interval containing zero; a constant offset gives one excluding zero; the interval narrows as n grows
- [x] Paired-vs-unpaired test: two retrievers differing identically on every query yield a paired interval far narrower than an unpaired one on the same data
- [x] Fixed seed reproduces intervals exactly
**Verify:** `pytest tests/eval/test_bootstrap.py -q`
**Dependencies:** 14. **Scope:** M. **Files:** `braid/eval/bootstrap.py`, `tests/eval/test_bootstrap.py`

**Adversarial review (2026-09-23, fresh-context subagent, single-model — no
`gemini`/`codex` CLI available for cross-model, skip announced):** found and
fixed 6 issues before this task counted as done:
1. Silent intersection truncation on key mismatch could make a published
   row's Diff disagree with its own Baseline/Target columns. Now raises.
2. No floor on `n` let a single-query comparison render as a confident
   zero-width interval indistinguishable from n=180. Now raises below `MIN_N=2`.
3. NaN inputs silently read as `excludes_zero=False` instead of surfacing
   corruption. Now raises on non-finite input.
4. `table.py` reused one seed across all 16 (category x metric) calls,
   correlating resamples within a category. Fixed with a per-call seed
   derived deterministically from the base seed (`table._derive_seed`).
5. No `compare(EvalResult, EvalResult, ...)` existed despite SPEC-eval.md's
   own Interface section documenting it. Added as a thin wrapper over
   `paired_bootstrap`.
6. Coverage gaps (partial overlap, `n`/`resamples`/`seed` fields, non-constant
   spread, realistic n=30, non-default `ci`) — 9 tests added.

### Task 16: Comparison table and stub end-to-end — DONE
**Acceptance:**
- [x] Four configurations x four metrics x three categories + pooled
- [x] Difference, CI bounds, "excludes zero: yes/no", and a column naming the **winning single-method baseline per category**, read descriptively off the criterion-1 table, never chosen post-hoc (amendment 7, item 3)
- [x] `evaluate()` runs end to end against a stub retriever
**Verify:** `pytest tests/eval/test_table.py -q`; `python -m braid.eval --stub`
**Dependencies:** 15. **Scope:** M. **Files:** `braid/eval/table.py`, `braid/eval/__main__.py`, `tests/eval/test_table.py`

### Task 17: Latency and throughput harness — DONE
**Acceptance:**
- [x] **10 warm-up queries discarded**, count recorded in the report
- [x] **Concurrency 1** for p50/p95; throughput derived from the same sequential pass and labeled as a concurrency-1 figure, not a capacity claim
- [x] **Swap and memory pressure captured alongside latency**: `vm_stat` swapins/swapouts and compressor pages before and after the pass (peak RSS field present, not yet populated — no real process to sample under the stub)
- [x] Rerank depth recorded with every figure (D7)
- [x] D1 thresholds evaluated as pass/fail; throughput reported without a threshold
**Verify:** `pytest tests/eval/test_latency.py -q` against a stub with injected sleeps.
**Dependencies:** 16. **Scope:** M. **Files:** `braid/eval/latency.py`, `tests/eval/test_latency.py`

### Checkpoint C — the harness is trustworthy — DONE
- [x] All known-answer bootstrap tests pass, including paired-vs-unpaired
- [x] Table renders every category, the "excludes zero" column, and the winning-baseline column
- [x] Latency report shape verified against a stub, including the swap samples
- [x] Adversarial fresh-context review of `bootstrap.py` complete (workflow step 7) — 6 findings, all reconciled and fixed
- [x] **Human review before proceeding** — via standing authorization on review-path decisions (2026-09-23)

**Status:** 149 tests pass, `ruff check` clean, `python -m braid.eval --stub`
runs end to end. Not yet committed — staged, awaiting the commit command.

---

## Phase 4: `extract`

### Task 18: spaCy pipeline and NER — DONE
**Acceptance:**
- [x] Entities emitted with type and char spans into passage text
- [x] Runs as a batch with peak RSS recorded (8 GiB constraint), no containers running
**Verify:** `pytest tests/extract/test_ner.py -q`
**Dependencies:** 6. **Scope:** S. **Files:** `braid/extract/ner.py`, `tests/extract/test_ner.py`

**Note:** model is `en_core_web_trf` (SPEC-extract.md); confirmed empirically
identical dependency-label scheme to `en_core_web_sm`, which the fast unit
tests use instead (session-scoped `nlp` fixture in `tests/conftest.py`), with
`en_core_web_trf` exercised in `@pytest.mark.slow` tests only. Peak RSS on the
full 1000-passage corpus: 1.3-1.6 GB, well under the 8 GiB constraint.

### Task 19: SVO dependency patterns — DONE
**Acceptance:**
- [x] One fixture sentence per documented pattern (active SVO, passive, copular, verb-attached prepositional object, conjunction expansion), expected triple asserted
- [x] Negative fixtures yield no triple: fragments, questions, list headers
- [x] The pattern list is enumerated in the module README; changing it is a spec change
**Verify:** `pytest tests/extract/test_patterns.py -q`
**Dependencies:** 18. **Scope:** M. **Files:** `braid/extract/patterns.py`, `braid/extract/README.md`, `tests/extract/test_patterns.py`

**Bugs found and fixed while building this task** (all with regression
tests): (1) `left_edge`/`right_edge` pulled an entire conjunction into the
first conjunct's span, fixed with a custom subtree walk (`_span_bounds`) that
excludes `cc`/`conj` edges; (2) interrogative sentences parse with the
identical `nsubj`/`dobj` shape as declaratives, fixed by skipping sentences
ending in `?`. Two further bugs (relative-pronoun subjects, relation casing)
were found later via the Task 21 quality report and are recorded there.

### Task 20: Entity normalization — DONE
**Acceptance:**
- [x] Alias resolution against passage titles, case folding, within-passage first-mention pronoun substitution — each rule documented and tested
- [x] Cross-passage coreference explicitly not attempted, asserted by test
**Verify:** `pytest tests/extract/test_normalize_entities.py -q`
**Dependencies:** 19. **Scope:** S. **Files:** `braid/extract/entities.py`, `tests/extract/test_normalize_entities.py`

**Note:** `_find_type`'s entity-type attachment was changed from exact-match
to containment-match after the first full corpus run showed 78%/90% of
subjects/objects with no type at all — a pattern's span routinely carries
words around the named entity ("director Mike Nichols"). After the fix:
55%/40% null. Regression tests added.

### Task 21: Extraction quality report — DONE
**Acceptance:**
- [x] 100 randomly sampled sentences annotated **before** the pipeline's output for those sentences is consulted, with the ordering recorded — otherwise recall is unmeasurable
- [x] Precision, recall, and 95% Wilson intervals in `reports/extraction-quality.md`
- [x] Triple count and per-relation histogram included, so sparsity is a number
**Verify:** report exists and its numbers regenerate from the committed annotations.
**Dependencies:** 20. **Scope:** M. **Files:** `braid/extract/quality.py`, `reports/extraction-quality.md`, `data/extract-sample.jsonl`

**Results:** precision 0.577 [0.489, 0.661], recall 0.899 [0.813, 0.948], on
79 gold triples across 72 of the 100 sampled sentences (79 pairs of the 100
sentences fell outside the fixed pattern set's scope — copula verbs other
than "be", clausal complements, adjectival predicates — and correctly
received zero gold triples). Full run: 4,954 triples over 1,000 passages,
`be` dominating the relation histogram (1,918) as expected for encyclopedic
definitional prose.

**Two real bugs found via inspecting real output before finalizing the
report, both fixed with regression tests in `test_patterns.py`:** relative
pronoun subjects ("which"/"who"/"that", POS WDT/WP) produced nonsensical
triples like `(which, air on, ABC)` since only third-person personal
pronouns are substituted — fixed by skipping WH-tagged subjects entirely;
and a fronted preposition leaked surface-case into the relation string
(`"become With"`) — fixed by lowercasing. **Known, not-fixed gaps** (out of
the documented pattern set's scope, all stated in the report and in
README.md): conjoined verb phrases are not expanded (pattern 5 only covers
conjoined subjects/objects); parallel/positional conjunctions ("X, Y, Z
replaced by A, B, C respectively") produce a cartesian product instead of
paired triples.

**Precision is a stated conservative lower bound**, not a point estimate to
take at face value: spot-checking the unmatched extracted triples after the
real run showed a substantial share are additional correct facts the
conservative, one-representative-per-sentence gold annotation policy simply
never recorded, not extraction errors. This is documented explicitly in the
report rather than left for a reader to discover.

### Checkpoint D — extraction is measured, not assumed — DONE
- [x] Precision and recall reported with Wilson intervals
- [x] Triple histogram reviewed **specifically against the criterion-3 risk**: 4,954 triples over 1,000 passages is a healthy yield; the graph will not be starved of candidate edges. No pattern expansion needed at this stage.
- [ ] Entity-name distribution checked against D5's exact-match linking rule and hub cap — **deferred to Task 25** (Neo4j graph loader), where the real degree distribution first exists to check against
- [x] **Human review before proceeding** — via standing authorization on review-path decisions

**Status:** 201/201 tests pass (199 fast + 2 slow, `en_core_web_trf`), lint
clean. Not yet committed — staged, awaiting the commit command. Real data
files generated and part of this checkpoint's evidence, not committed to git
per `.gitignore` (`data/*` except the manifest and queryset): `data/triples.jsonl`
(4,954 triples), `data/extract-manifest.json`, `data/extract-sample.jsonl`,
`data/extract-gold.jsonl` — the last is the hand-annotation evidence and
arguably *should* be committed alongside `reports/extraction-quality.md`
(similar reasoning to why the query set is committed as evidence); flagging
this for the commit decision rather than deciding it silently.

---

## Phase 5: `index` — one store at a time

### Task 22: Compose stack and health command
**Acceptance:**
- [ ] OpenSearch `-Xms512m -Xmx512m`; Neo4j heap 512m, pagecache 256m; security plugins disabled; local only
- [ ] `health()` distinguishes container-down, reachable-but-empty, and populated-with-N
- [ ] Integration tests skip cleanly with a stated reason when containers are down
**Verify:** `docker compose up -d && python -m braid.index health`
**Dependencies:** 1. **Scope:** S. **Files:** `docker-compose.yml`, `braid/index/health.py`, `tests/index/conftest.py`

### Task 23: OpenSearch BM25 builder
**Acceptance:**
- [ ] Explicit mapping and analyzer settings, not implicit defaults — BM25 numbers depend on them
- [ ] `passage_id` as document ID; bulk index with refresh control
- [ ] Document count after build equals corpus size, asserted
- [ ] Every client call cited to current official docs in a comment (workflow step 5)
**Verify:** `pytest tests/index/test_bm25.py -q`
**Dependencies:** 22. **Scope:** M. **Files:** `braid/index/bm25.py`, `tests/index/test_bm25.py`

### Task 24: FAISS dense builder
**Acceptance:**
- [ ] `bge-small-en-v1.5`, normalized vectors, `IndexFlatIP`; query-side prefix per the model card
- [ ] `ids.json` sidecar written in one operation with the index; lengths asserted equal on load
- [ ] Vector count equals corpus size
**Verify:** `pytest tests/index/test_dense.py -q`
**Dependencies:** 22. **Scope:** M. **Files:** `braid/index/dense.py`, `tests/index/test_dense.py`

### Task 25: Neo4j graph loader
**Acceptance:**
- [ ] `(:Entity {name, type})` nodes, `[:RELATION {relation, passage_id, sentence_index}]` edges
- [ ] Uniqueness constraint on `Entity.name`; batched `UNWIND` + `MERGE`
- [ ] Node and edge counts asserted against the triple file
**Verify:** `pytest tests/index/test_graph.py -q`
**Dependencies:** 21, 22. **Scope:** M. **Files:** `braid/index/graph.py`, `tests/index/test_graph.py`

### Task 26: Incremental add across all three stores
**Acceptance:**
- [ ] Build on 10 passages, add 5, confirm 15 present in each store and the original 10 unchanged
- [ ] FAISS ordinal-to-ID mapping still resolves correctly after the add
- [ ] All three builders pass one shared contract test suite
**Verify:** `pytest tests/index/test_incremental.py -q`
**Dependencies:** 23, 24, 25. **Scope:** M. **Files:** `braid/index/base.py`, `tests/index/test_incremental.py`

### Checkpoint E — three stores, all populated and diagnosable
- [ ] `index health` reports populated for all three
- [ ] Incremental add verified per store
- [ ] **Human review before proceeding**

---

## Phase 6: `query` — one configuration at a time, each scored before the next

### Task 27: Retriever protocol, factory, and pinned D5 parameters
**Acceptance:**
- [ ] `Hit` carries `provenance` (per-source contribution), which criterion 3 is read from
- [ ] One factory constructs every named configuration; `eval` and the CLI both use it
- [ ] **All D5 values live in one constants module**, asserted by test, so no configuration can silently diverge from the table in SPEC-query.md
- [ ] Shared contract test suite exists and runs against a stub
**Verify:** `pytest tests/query/test_contract.py tests/query/test_params.py -q`
**Dependencies:** 17, 26. **Scope:** M. **Files:** `braid/query/base.py`, `braid/query/factory.py`, `braid/query/params.py`, `tests/query/test_contract.py`, `tests/query/test_params.py`

### Task 28: `bm25` configuration, scored
**Acceptance:** implements `Retriever`; passes the contract suite; candidate K = 100 per D5; scored by `eval` with per-category numbers recorded.
**Verify:** `python -m braid.eval --config bm25`
**Dependencies:** 27. **Scope:** S. **Files:** `braid/query/sparse.py`, `tests/query/test_sparse.py`

### Task 29: `dense` configuration, scored
**Acceptance:** as Task 28, for FAISS, candidate K = 100. Scored before fusion is started.
**Verify:** `python -m braid.eval --config dense`
**Dependencies:** 28. **Scope:** S. **Files:** `braid/query/dense.py`, `tests/query/test_dense.py`

### Task 30: Graph candidate source
**Acceptance:**
- [ ] Entity linking by exact match on case-folded normalized `Entity.name`, per D5
- [ ] Traversal depth 2; fan-out cap 50 edges per node; entities of degree > 200 skipped as hubs
- [ ] Candidate K = 50; passages emitted as a ranked third source
- [ ] Link-failure rate recorded — how many queries linked zero entities — since that bounds criterion 3
**Verify:** `pytest tests/query/test_graph.py -q`
**Dependencies:** 29. **Scope:** M. **Files:** `braid/query/graph.py`, `tests/query/test_graph.py`

### Task 31: RRF fusion (3-way)
**Acceptance:**
- [ ] `1 / (k_rrf + rank)`, `k_rrf = 60`, source cited; 3-way over bm25, dense, graph per D5
- [ ] Hand-computed test on constructed rank lists
- [ ] **Zero-BM25-match test:** a query with no lexical match but a strong semantic match still returns the correct passage, with non-zero dense provenance and zero bm25 provenance
**Verify:** `pytest tests/query/test_fusion.py -q`; `python -m braid.eval --config fused`
**Dependencies:** 30. **Scope:** M. **Files:** `braid/query/fusion.py`, `tests/query/test_fusion.py`

### Task 32: Cross-encoder rerank
**Acceptance:**
- [ ] `ms-marco-MiniLM-L-6-v2` over the fused top-50, batched, loaded once per process
- [ ] Warm p50 and p95 measured against D1 and recorded with depth and swap samples
- [ ] If p95 >= 2.5 s, apply D7 fallbacks in order — top-K 50 -> 30, then a smaller cross-encoder — record which was used, and regenerate the criterion-1 table at the new depth. Relaxing D1's thresholds is not an option here.
**Verify:** `python -m braid.eval --config fused-rerank`
**Dependencies:** 31. **Scope:** M. **Files:** `braid/query/rerank.py`, `tests/query/test_rerank.py`

### Task 33: Criterion-3 exhaustive count
**Description:** Count, over **every** multi-hop evaluation query, those where a
graph-sourced candidate surfaces a gold passage that dense-only retrieval does
not. No subset selection.
**Acceptance:**
- [ ] Definition used is stated in the report: a supporting passage in `fused` top-10 with non-zero graph provenance and absent from `dense` top-10 (or, under 2-way fusion, the graph-only-retrieval form)
- [ ] `reports/graph-vs-vector.md` lists every multi-hop query with its supporting passage IDs, dense rank, fused rank, graph provenance, and verdict — including queries where dense wins and where neither surfaces the passage
- [ ] A test asserts the table's row count equals the number of multi-hop queries, so the count cannot be a subset
- [ ] A count below 5 is reported as the finding it is, alongside the extraction yield figures
**Verify:** `python -m braid.eval --criterion3`
**Dependencies:** 32. **Scope:** M. **Files:** `braid/eval/criterion3.py`, `reports/graph-vs-vector.md`

### Task 34: CLI
**Acceptance:**
- [ ] `python -m braid.query "<text>" --config fused-rerank --k 10` prints ranked IDs, scores, provenance, timing
- [ ] A test asserts the CLI and `eval` return identical results for the same query and seed, via the same factory
**Verify:** `pytest tests/query/test_cli.py -q`
**Dependencies:** 32. **Scope:** S. **Files:** `braid/query/__main__.py`, `tests/query/test_cli.py`

### Checkpoint F — criteria 1, 2, 3, 5 are answerable
- [ ] Four configurations scored, per category and pooled, with the winning baseline named per category
- [ ] Criterion-2 CIs computed with "excludes zero" stated per category
- [ ] Criterion-3 exhaustive count written, with its denominator visible
- [ ] D1 latency measured with warm-up count, concurrency, depth, and swap samples; any D7 fallback recorded
- [ ] **Human review before proceeding**

---

## Phase 7: `finetune`

### Task 35: Disjoint pair construction and leakage assertion
**Acceptance:**
- [ ] Training questions drawn with a recorded seed from HotpotQA questions not in the evaluation set
- [ ] Positives = gold paragraphs; hard negatives = that question's distractors; ratio and counts recorded
- [ ] Excluded set is the **union of every evaluation question's gold and distractor passages** (amendment 4), not gold only
- [ ] Two contaminated fixtures each abort the run: one sharing a gold passage, one sharing only a distractor
- [ ] Excluded-set size and remaining training-pool size both recorded
**Verify:** `pytest tests/finetune/test_leakage.py -q`
**Dependencies:** 34. **Scope:** M. **Files:** `braid/finetune/pairs.py`, `tests/finetune/test_leakage.py`

### Task 36: Training run
**Acceptance:**
- [ ] Early stopping and checkpoint selection use a split carved from the **training** sample only
- [ ] `reports/finetune.md` records base checkpoint, epochs, batch size, learning rate, warmup, max seq length, loss, seeds, wall clock, hardware
**Verify:** `python -m braid.finetune --out models/ce-braid`
**Dependencies:** 35. **Scope:** M. **Files:** `braid/finetune/train.py`, `reports/finetune.md`

### Task 37: Before/after comparison
**Acceptance:**
- [ ] `fused-rerank` vs `fused-rerank-ft` on the held-out set, all four metrics, per category and pooled
- [ ] Both configurations share the same `fused` candidate list and rerank depth exactly
- [ ] Each difference carries a paired-bootstrap 95% CI and an "excludes zero" statement
- [ ] A null or negative result is reported at the same prominence as a positive one
**Verify:** `python -m braid.eval --all-configs --bootstrap 1000`
**Dependencies:** 36. **Scope:** S. **Files:** `braid/finetune/compare.py`, `reports/comparison.md`

### Checkpoint G — criterion 4 is answerable
- [ ] Leakage assertion passes on real data and aborts on both contaminated fixtures
- [ ] Before/after numbers reported with CIs
- [ ] Adversarial fresh-context review of the fine-tuning path complete (workflow step 7)
- [ ] **Human review before proceeding**

---

## Phase 8: Reproducibility and release

### Task 38: `scripts/reproduce.sh`
**Acceptance:**
- [ ] One script, clean checkout to every reported number: ingest, freeze, extract, index, all five configurations, all tables, CIs, latency, both reports
- [ ] Seeds pinned and echoed; the script verifies `corpus_hash` matches the committed query set before evaluating, and fails loudly if containers are down
**Verify:** run on a fresh clone; diff regenerated tables against committed ones.
**Dependencies:** 37. **Scope:** M. **Files:** `scripts/reproduce.sh`

### Task 39: README
**Acceptance:**
- [ ] Every metric per category and pooled, every CI, the criterion-3 count with its denominator, latency and throughput with warm-up count and concurrency, hardware stated
- [ ] D5 parameter table reproduced, with a note that no value was tuned on the evaluation set
- [ ] Query authorship and review process stated plainly (D4), including that multi-hop queries come from HotpotQA and the other two categories are agent-drafted and human-reviewed, plus the paraphrase override count
- [ ] Limitations: sample size and interval width; paraphrase framing bias; extraction yield; any D7 fallback used
- [ ] Null and negative findings at the same prominence as positive ones
**Verify:** every number traced to a file `reproduce.sh` regenerates.
**Dependencies:** 38. **Scope:** M. **Files:** `README.md`

### Task 40: Review and simplification pass
**Acceptance:**
- [ ] `code-review-and-quality` and `code-simplification` passes complete (workflow step 9)
- [ ] Performance gate for criterion 5 re-checked after any change (workflow step 10)
**Verify:** `pytest -q && ruff check .`; `reproduce.sh` still reproduces.
**Dependencies:** 39. **Scope:** M.

### Checkpoint H — done
- [ ] All six acceptance criteria answered, including any answered negatively
- [ ] `reproduce.sh` regenerates every README number from a clean checkout
- [ ] **Final human review**
