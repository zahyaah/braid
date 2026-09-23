# Spec: Braid — Hybrid Retrieval Engine

Status: **approved 2026-09-23**. Derived from the Build Spec v2 supplied by
the author. Where this document differs from that text, the difference was
raised as an open question and resolved by the author; see "Resolved
decisions" below. Nothing has been silently reinterpreted.

## Objective

Fuse sparse lexical retrieval (BM25), dense semantic retrieval (FAISS), and
entity-graph traversal (Neo4j) into a single ranked result, and demonstrate
with statistically defensible numbers that the fusion helps on the specific
failure modes it is meant to fix.

The user is someone issuing a natural-language query over a corpus that mixes
structured and unstructured data, who wants correct results on queries that
any single retrieval method handles badly.

Success is a benchmark report, not a demo: per-category metrics for four
configurations, every cross-configuration comparison carrying a 95% confidence
interval, all of it reproducible from one script.

### Non-goals (unchanged from the supplied spec)

- Not a production-scale search engine. Single-node OpenSearch, FAISS, Neo4j.
- No UI. CLI plus benchmark report is the deliverable.
- No paid embedding or reranking API. Self-hosted only.
- Not a general-purpose entity extractor. A documented, fixed pipeline for
  this corpus is sufficient.

## Tech stack

| Concern | Choice | Version | Note |
|---|---|---|---|
| Language | Python | 3.10.1 (installed) | pinned via `.python-version`; `uv` or `venv` |
| Corpus | HotpotQA distractor, validation split | via `datasets` | CC BY-SA 4.0 |
| Sparse index | OpenSearch | 2.x, single node, Docker | JVM heap capped (see Hardware) |
| Dense embeddings | `BAAI/bge-small-en-v1.5` | 384-dim | CPU/MPS; E5-small is the fallback |
| Dense index | FAISS | `faiss-cpu` | `IndexFlatIP` at this corpus size; exact, no training step |
| NER + parse | spaCy `en_core_web_trf` | 3.7.x | transformer pipeline, run offline before services start |
| Graph store | Neo4j | 5.x Community, Docker | heap capped |
| Reranker (baseline) | `cross-encoder/ms-marco-MiniLM-L-6-v2` | — | |
| Reranker (tuned) | same checkpoint, fine-tuned | sentence-transformers `CrossEncoder` trainer | |
| Stats | numpy | — | paired bootstrap, 1,000 resamples, fixed seed |
| Tests | pytest | — | |

### Hardware (stated, because every number depends on it)

Apple M1, 8 cores, 8 GiB unified memory, macOS 25.2.0 (Darwin), Docker 29.2.1.

8 GiB is the binding constraint. Two JVMs plus a torch process do not coexist
comfortably. Mitigations, which are part of the design rather than an
afterthought:

- OpenSearch heap `-Xms512m -Xmx512m`; Neo4j heap 512m, pagecache 256m.
- `extract` runs as an offline batch and writes triples to disk. spaCy
  `en_core_web_trf` and the databases are never resident at the same time.
- Embedding and reranking run in a separate process from indexing.
- Benchmark runs happen with both containers up, because that is the
  configuration the reported latency numbers must describe.

## Commands

```
Setup:      uv venv && uv pip install -e ".[dev]"
Services:   docker compose up -d          # OpenSearch + Neo4j
Ingest:     python -m braid.ingest build --out data/corpus.jsonl
Freeze:     python -m braid.ingest freeze        # decision D6
Verify:     python -m braid.ingest verify        # corpus vs frozen hash
Extract:    python -m braid.extract      --corpus data/corpus.jsonl --out data/triples.jsonl
Index:      python -m braid.index build  --all
Query:      python -m braid.query "who directed the film that..." --config fused-rerank
Finetune:   python -m braid.finetune     --out models/ce-braid
Eval:       python -m braid.eval         --all-configs --bootstrap 1000
Reproduce:  ./scripts/reproduce.sh       # the one script behind acceptance criterion 6
Test:       pytest -q
Lint:       ruff check . && ruff format --check .
```

## Project structure

```
braid/ingest/     Corpus loader, chunker, dedupe, passage IDs
braid/extract/    NER + SVO relation extraction, extraction quality report
braid/index/      BM25, FAISS, Neo4j builders; incremental add
braid/query/      Retriever interface, RRF fusion, rerank, graph traversal; CLI
braid/eval/       Metrics, stratification, bootstrap CIs, comparison table
braid/eval/queryset/  Labeled queries + relevance judgments + schema validator
braid/finetune/   Cross-encoder training, before/after comparison
tests/            pytest, mirroring the package layout
data/             Generated corpus, triples, indexes (gitignored except labels)
reports/          Generated tables and the extraction-quality report
scripts/          reproduce.sh, docker compose
tasks/            plan.md, todo.md
```

## Code style

Typed, dataclass-carried results; retrieval components share one interface so
`eval` and the CLI call the same code path.

```python
@dataclass(frozen=True)
class Hit:
    passage_id: str
    score: float
    rank: int


class Retriever(Protocol):
    """Every configuration under test implements this and nothing more."""

    name: str

    def search(self, query: str, k: int) -> list[Hit]:
        ...
```

Conventions: `snake_case` functions, `PascalCase` classes, module-level
constants uppercase. No bare `except`. Every stochastic step (bootstrap,
sampling, fine-tuning) takes an explicit `seed` argument with a recorded
default. Public functions carry type hints; `ruff` enforces formatting.

## Testing strategy

pytest, tests under `tests/` mirroring the package layout.

- **Unit:** metric functions verified against hand-computed values (a known
  ranking with a known nDCG, not a golden file generated by the code itself);
  RRF fusion verified on constructed rank lists, including the zero-BM25-match
  edge case; dedupe verified on near-duplicate fixtures.
- **Contract:** every `Retriever` implementation runs against the same suite.
- **Statistical:** the bootstrap is tested on synthetic data with a known
  answer — two identical score vectors must produce an interval containing
  zero, and a constant offset must produce an interval excluding it.
- **Integration:** ingest → index → query on a 20-passage fixture corpus,
  against real OpenSearch and Neo4j containers, skipped when unavailable.

Coverage expectation: every metric and statistics function is unit-tested.
These are the functions where a bug yields a plausible wrong number instead of
a crash, which is exactly the failure this project cannot afford.

## Boundaries

**Always**

- Write relevance judgments before the retrieval code they will judge.
- Report a confidence interval with every cross-configuration comparison.
- Report negative and null results in the README, at the same prominence as
  positive ones.
- Pin seeds and record them in generated reports.
- Run `pytest -q` before every commit.

**Ask first**

- Changing the query set or any relevance judgment after retrieval code exists.
- Adding a dependency not listed in Tech stack.
- Changing a model checkpoint.
- Altering an acceptance criterion or its threshold.

**Never**

- Auto-generate relevance labels, or derive them from retriever output.
- Fine-tune on queries that appear in the evaluation set.
- Report a point estimate without uncertainty for an acceptance criterion.
- Tune any parameter against the held-out query set and then report that set's
  numbers as held-out.
- Commit secrets or index binaries.

## Success criteria

Restated from the supplied spec, unchanged in substance:

1. recall@5, recall@10, nDCG@10, MRR for four configurations (BM25, dense,
   fused, fused+reranked), broken out per category and pooled.
2. Per category: difference between fused+reranked and the best single-method
   baseline, with a 95% CI from paired bootstrap (1,000 resamples) over
   query-level scores; plainly stated whether each interval excludes zero.
3. Graph store answers at least 5 multi-hop queries correctly where pure
   vector search fails on the same queries, by direct comparison.
4. Fine-tuned cross-encoder benchmarked against the pretrained baseline on the
   full held-out evaluation set, with the same CI treatment as criterion 2.
   The evaluation set is never used for training, early stopping, or model
   selection (decision D2).
5. Query latency p50 and p95 and throughput measured on the hardware stated
   above. Pass condition: warm p95 < 2.5 s and p50 < 1.2 s for
   retrieve -> fuse -> rerank over the fused top-50. Throughput
   (queries/sec) is measured and reported, with no threshold (decision D1).
6. Every number in the README reproducible by `./scripts/reproduce.sh`.

## Assumptions

Correct any of these now; otherwise the plan proceeds on them.

1. **Corpus:** HotpotQA distractor validation split, sampled to 500–1,000
   passages, seeded and recorded. Sampling starts from questions, then pulls
   their gold and distractor paragraphs, so multi-hop questions have complete
   supporting evidence in the corpus.
2. **Passage granularity:** one HotpotQA paragraph = one passage = one chunk.
   No sub-chunking. Supporting-fact sentence annotations are retained as
   metadata but relevance is judged at passage level.
3. **Dedupe:** exact-hash plus MinHash near-duplicate detection at a stated
   Jaccard threshold, applied before indexing.
4. **Services:** OpenSearch and Neo4j via `docker compose`, single node,
   security plugin disabled, local only.
5. **Graph queries:** the graph is a retrieval signal contributing candidates
   to fusion, not a separate answering system. Criterion 3 is evaluated as
   "graph-sourced candidates surface the correct passage where dense retrieval
   does not."
6. **Latency budget:** the per-query budget covers retrieve → fuse → rerank,
   with indexes already built and models already loaded ("warm"). Ingest and
   index builds are reported separately as one-time costs. Thresholds in
   decision D1.
7. **Metrics:** relevance is binary everywhere. Exact-term and paraphrase have
   one relevant passage per query; multi-hop has several — each supporting
   paragraph carries gain 1, not a graded gain (amendment 7, item 4). What
   makes nDCG@10 meaningful for multi-hop is the multiple relevant passages,
   not graded gains.

## Resolved decisions

Raised as open questions against Build Spec v2 and answered by the author on
2026-09-23. These are binding; changing one is an "ask first" action.

**D1 — Latency thresholds.** End-to-end warm query latency must be p95 < 2.5 s
and p50 < 1.2 s for retrieve → fuse → rerank over the fused top-50, on the
hardware stated above. Throughput is measured and reported separately, with no
threshold. This makes criterion 5 pass/fail on latency and
measurement-only on throughput.

**D2 — No test-set leakage in fine-tuning.** The cross-encoder is fine-tuned on
a disjoint HotpotQA question sample. The evaluation query set is never used for
training, early stopping, or model selection. Pretrained and fine-tuned
rerankers are compared only on the held-out evaluation set. Consequences that
the `finetune` module spec must honor: the disjoint sample is drawn with a
recorded seed and checked for question-id and passage-id overlap against the
evaluation set; any early stopping or checkpoint selection uses a validation
split carved from the *training* sample, never from the evaluation set.

**D3 — Evaluation set size.** Primary target is 180 queries, 60 per category.
Minimum acceptable is 90 queries, 30 per category, and falling back to it
requires the README to state the resulting limitation — wider per-category
confidence intervals, with a real few-point improvement likely to produce an
interval spanning zero. The final size is fixed and committed before any
retrieval code runs. The fallback decision point is the end of the `queryset`
module; it is not available afterward.

**D4 — Query authorship and review.** The hand-written exact-term and
paraphrase queries are agent-drafted and human-reviewed and edited before any
retrieval code runs. The review record ships with the query set: for each
query, who reviewed it, when, and whether it was accepted, edited, or
rejected. The README states the authorship and review process plainly, and
states that the multi-hop category comes from HotpotQA's own labeled questions
rather than being agent-drafted.

**D5 — Fusion and graph parameters are pinned a priori.** The values below are
documented defaults, fixed before Task 1, and are never tuned against the
evaluation set. If any value is tuned, it is tuned on a validation slice carved
from the D2 training sample. The canonical table, with rationale per row, lives
in SPEC-query.md.

| Parameter | Value | Status |
|---|---|---|
| RRF `k` | 60 | pinned |
| BM25 candidate K before fusion | 100 | **pending author sign-off** |
| Dense candidate K before fusion | 100 | **pending author sign-off** |
| Graph candidate K before fusion | 50 | **pending author sign-off** |
| Fusion arity | 3-way (BM25 + dense + graph as a third RRF list) | **pending author sign-off** |
| Graph traversal depth | 2 hops | pinned |
| Relation filter | none; all relation types traversed, with a fan-out cap of 50 edges per node and hub entities of degree > 200 skipped | **pending author sign-off** |
| Entity-linking rule | exact match on case-folded, normalized `Entity.name`; no fuzzy matching, hence no similarity threshold | **pending author sign-off** |
| Rerank top-K | 50 | pinned by D1; changeable only via D7 |

Fusion arity is marked pending because Build Spec v2 is internally divided on
it: its problem statement fuses all three signals, while its Architecture
section says "reciprocal rank fusion combining BM25 and dense results" — 2-way,
with the graph separate. This spec pins 3-way, because criterion 3 as defined
under amendment 3 reads graph contribution off the fused ranking. If the author
chooses 2-way instead, criterion 3's operational definition falls back to the
graph-only-retrieval form, which SPEC-eval.md documents as the alternate.

**D6 — Corpus freeze precedes judgment authoring.** The pipeline is
ingest → dedupe → manifest with content hash → **freeze** → author queries and
judgments against the frozen passage IDs. The manifest's `corpus_hash` is
`sha256` over sorted `(passage_id, text)` pairs. Nothing may author or edit a
relevance judgment against an unfrozen corpus. After the freeze, remapping a
gold passage is a judgment change, and therefore "ask first" under Boundaries —
it is not an ingest fix. Checkpoint B's git audit covers the corpus-freeze
commit as well as `queries.jsonl`. This extends D2's no-leakage discipline to
the labels themselves: labels cannot drift with the corpus if the corpus cannot
move.

**D7 — Pre-authorized latency fallbacks.** D1's thresholds stand unchanged. If
measured p95 >= 2.5 s on the stated hardware, the pre-authorized responses, in
order, are:

1. Reduce rerank top-K from 50 to 30.
2. If still failing, substitute a smaller cross-encoder
   (`ms-marco-MiniLM-L-2-v2`).

Any fallback used is recorded in the latency report and in the README. D1's
wording names the fused top-50; fallback 1 changes that depth, so every
reported latency number states the rerank depth it was measured at, and a pass
at depth 30 is never presented as a pass at depth 50. Reranking a shallower
candidate pool can also change retrieval quality, so triggering fallback 1
requires the criterion-1 table to be regenerated at the new depth rather than
carried over. Relaxing D1's thresholds is not in this list and remains "ask
first".

## Known risk (no decision required yet)

**Extraction yield for criterion 3.** SVO relation extraction over HotpotQA's
encyclopedic prose may yield sparse or noisy triples, putting "at least 5
multi-hop queries where graph beats vector" at risk. The extraction
precision/recall report in the `extract` module exists to catch this at
extraction time rather than as an unexplained downstream drop. If yield is too
low, the options are a documented pattern expansion or a reported negative
finding — not a quietly loosened criterion.
