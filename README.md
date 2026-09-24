# Braid — hybrid retrieval, measured honestly

Braid fuses **BM25 (OpenSearch)**, **dense vectors (BGE-small + FAISS)** and **entity-graph traversal (spaCy → Neo4j)** with reciprocal rank fusion, reranks with a **cross-encoder**, and then measures — per query category, with paired-bootstrap 95% confidence intervals — whether the fusion actually helps. Everything runs locally; no paid APIs.

## Headline: the hybrid did not beat dense retrieval alone

The project's premise was that fusing three signals would beat any one. **In this configuration it did not.**

- Pooled ndcg@10: `dense` **0.832**, `fused-rerank` 0.829, `fused-rerank-ft` 0.805, plain `fused` (RRF, no rerank) **0.516**. `fused-rerank` is not significantly better than the best single method in any category, and is significantly *worse* than `dense` on paraphrase ndcg@10 (−0.093, CI [−0.178, −0.016]).
- Where hybrid helps: exact-term queries, where `bm25` and `fused-rerank` are near-perfect (ndcg@10 0.977 / 0.990) — but that gain over BM25 is not statistically significant.
- Graph traversal surfaced a gold passage that dense retrieval missed on only **2 of 60** multi-hop queries (criterion 3 asks for ≥ 5). That count is capped by how little headroom dense left: only **6 of 60** multi-hop queries had *any* gold passage outside dense's top-10.
- Fine-tuning the reranker **helped multi-hop** (recall@5 +0.067, ndcg@10 +0.025; both CIs exclude zero, the ndcg@10 one only barely, lower bound 0.0002) and **hurt** exact-term ndcg@10/mrr, paraphrase recall@10 and pooled recall@10. Net pooled effect: none.

These are reported at the same prominence as any positive result would be.

## What it does

| Stage | Implementation |
|---|---|
| Corpus | 1,000 passages / 102 questions from HotpotQA (distractor, validation), deduplicated, then **frozen** with a content hash before any label was written |
| Sparse | OpenSearch 2.19 BM25, explicit analyzer |
| Dense | `BAAI/bge-small-en-v1.5` → FAISS `IndexFlatIP` (exact) |
| Graph | spaCy `en_core_web_trf` NER + 5 dependency-parse patterns → 4954 triples → Neo4j (6,862 entities, 4,943 edges) |
| Fusion | 3-way reciprocal rank fusion (k = 60) |
| Rerank | `cross-encoder/ms-marco-MiniLM-L-6-v2` over the fused top-50 |
| Fine-tune | same cross-encoder, trained on 300 HotpotQA questions **disjoint** from the evaluation set |

## Hardware

Apple M1, 8 cores, **8 GiB** unified memory, macOS (Darwin 25.2.0), Docker for OpenSearch and Neo4j (JVM heaps capped at 512 MB each). CPU/MPS only.

## Results

All tables below are copied verbatim from `reports/`, which `scripts/reproduce.sh` regenerates. Evaluation set: **180 hand-reviewed queries, 60 per category**.

### Per-configuration metrics (criterion 1)

| Config | Category | recall@5 | recall@10 | ndcg@10 | mrr |
|---|---|---|---|---|---|
| bm25 | exact-term | 1.0000 | 1.0000 | 0.9772 | 0.9694 |
| bm25 | paraphrase | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| bm25 | multi-hop-relational | 0.7167 | 0.9000 | 0.7731 | 0.8817 |
| bm25 | pooled | 0.5722 | 0.6333 | 0.5834 | 0.6170 |
| dense | exact-term | 0.9167 | 0.9333 | 0.8953 | 0.8835 |
| dense | paraphrase | 0.7833 | 0.9333 | 0.6772 | 0.5975 |
| dense | multi-hop-relational | 0.9250 | 0.9500 | 0.9229 | 0.9875 |
| dense | pooled | 0.8750 | 0.9389 | 0.8318 | 0.8228 |
| fused | exact-term | 0.9333 | 0.9667 | 0.8064 | 0.7546 |
| fused | paraphrase | 0.0333 | 0.0500 | 0.0205 | 0.0116 |
| fused | multi-hop-relational | 0.6667 | 0.8917 | 0.7199 | 0.7526 |
| fused | pooled | 0.5444 | 0.6361 | 0.5156 | 0.5062 |
| fused-rerank | exact-term | 1.0000 | 1.0000 | 0.9905 | 0.9875 |
| fused-rerank | paraphrase | 0.7000 | 0.8500 | 0.5837 | 0.5015 |
| fused-rerank | multi-hop-relational | 0.8917 | 0.9750 | 0.9116 | 0.9806 |
| fused-rerank | pooled | 0.8639 | 0.9417 | 0.8286 | 0.8232 |
| fused-rerank-ft | exact-term | 1.0000 | 1.0000 | 0.9528 | 0.9372 |
| fused-rerank-ft | paraphrase | 0.6000 | 0.7333 | 0.5260 | 0.4616 |
| fused-rerank-ft | multi-hop-relational | 0.9583 | 0.9833 | 0.9364 | 0.9722 |
| fused-rerank-ft | pooled | 0.8528 | 0.9056 | 0.8051 | 0.7903 |

### `fused-rerank` vs best single-method baseline (criterion 2)

Baseline = whichever of `bm25`/`dense` scores higher on that category, read off the table above (not chosen after seeing the comparison). Paired bootstrap, 1,000 resamples, 95% percentile interval, resampling *queries*. **Only one row excludes zero, and it is negative.**

| Category | Metric | Baseline | Baseline value | Target value | Diff | 95% CI | Excludes zero |
|---|---|---|---|---|---|---|---|
| exact-term | recall@5 | bm25 | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | no |
| exact-term | recall@10 | bm25 | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | no |
| exact-term | ndcg@10 | bm25 | 0.9772 | 0.9905 | +0.0133 | [-0.0190, 0.0456] | no |
| exact-term | mrr | bm25 | 0.9694 | 0.9875 | +0.0181 | [-0.0250, 0.0639] | no |
| paraphrase | recall@5 | dense | 0.7833 | 0.7000 | -0.0833 | [-0.1833, 0.0167] | no |
| paraphrase | recall@10 | dense | 0.9333 | 0.8500 | -0.0833 | [-0.1833, 0.0000] | no |
| paraphrase | ndcg@10 | dense | 0.6772 | 0.5837 | -0.0934 | [-0.1781, -0.0161] | yes |
| paraphrase | mrr | dense | 0.5975 | 0.5015 | -0.0959 | [-0.1897, 0.0020] | no |
| multi-hop-relational | recall@5 | dense | 0.9250 | 0.8917 | -0.0333 | [-0.0917, 0.0250] | no |
| multi-hop-relational | recall@10 | dense | 0.9500 | 0.9750 | +0.0250 | [-0.0083, 0.0667] | no |
| multi-hop-relational | ndcg@10 | dense | 0.9229 | 0.9116 | -0.0113 | [-0.0418, 0.0185] | no |
| multi-hop-relational | mrr | dense | 0.9875 | 0.9806 | -0.0069 | [-0.0445, 0.0292] | no |
| pooled | recall@5 | dense | 0.8750 | 0.8639 | -0.0111 | [-0.0611, 0.0361] | no |
| pooled | recall@10 | dense | 0.9389 | 0.9417 | +0.0028 | [-0.0361, 0.0444] | no |
| pooled | ndcg@10 | dense | 0.8318 | 0.8286 | -0.0032 | [-0.0418, 0.0346] | no |
| pooled | mrr | dense | 0.8228 | 0.8232 | +0.0004 | [-0.0408, 0.0468] | no |

### Fine-tuned vs pretrained reranker (criterion 4)

`after` = `fused-rerank-ft` (models/ce-braid), `before` = `fused-rerank` (cross-encoder/ms-marco-MiniLM-L-6-v2). Both rerank the identical `fused` top-50 candidate list. A positive diff means the fine-tuned model scores higher; a null or negative result is reported at the same prominence as a positive one.

| Category | Metric | Before (pretrained) | After (fine-tuned) | Diff | 95% CI | Excludes zero |
|----------|--------|--------------------:|-------------------:|-----:|--------|:-------------:|
| exact-term | recall@5 | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | no |
| exact-term | recall@10 | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | no |
| exact-term | ndcg@10 | 0.9905 | 0.9528 | -0.0377 | [-0.0741, -0.0083] | yes |
| exact-term | mrr | 0.9875 | 0.9372 | -0.0503 | [-0.0961, -0.0119] | yes |
| paraphrase | recall@5 | 0.7000 | 0.6000 | -0.1000 | [-0.2333, 0.0333] | no |
| paraphrase | recall@10 | 0.8500 | 0.7333 | -0.1167 | [-0.2167, -0.0167] | yes |
| paraphrase | ndcg@10 | 0.5837 | 0.5260 | -0.0577 | [-0.1470, 0.0409] | no |
| paraphrase | mrr | 0.5015 | 0.4616 | -0.0400 | [-0.1530, 0.0675] | no |
| multi-hop-relational | recall@5 | 0.8917 | 0.9583 | +0.0667 | [0.0167, 0.1250] | yes |
| multi-hop-relational | recall@10 | 0.9750 | 0.9833 | +0.0083 | [0.0000, 0.0250] | no |
| multi-hop-relational | ndcg@10 | 0.9116 | 0.9364 | +0.0248 | [0.0002, 0.0490] | yes |
| multi-hop-relational | mrr | 0.9806 | 0.9722 | -0.0083 | [-0.0335, 0.0250] | no |
| pooled | recall@5 | 0.8639 | 0.8528 | -0.0111 | [-0.0611, 0.0333] | no |
| pooled | recall@10 | 0.9417 | 0.9056 | -0.0361 | [-0.0750, -0.0028] | yes |
| pooled | ndcg@10 | 0.8286 | 0.8051 | -0.0236 | [-0.0613, 0.0093] | no |
| pooled | mrr | 0.8232 | 0.7903 | -0.0329 | [-0.0727, 0.0069] | no |

Both rerank the identical fused top-50 at the identical `max_length` (512). One training run, on MPS, whose kernels are not bit-deterministic — **not an average over runs**. There are 16 intervals per table with **no multiplicity correction**, so isolated "excludes zero" rows deserve caution.

### Graph vs vector, multi-hop (criterion 3)

**2 / 60 (3.3%)** multi-hop queries have a gold passage that appears in the fused top-10 with graph provenance and is absent from dense's top-10 — below the threshold of 5, reported as the finding it is. Ceiling: 6 / 60. Graph provenance is non-zero on a gold passage in 46 / 60 queries, so the graph contributes signal; it rarely contributes a passage dense had missed. Every query, with dense rank, fused rank and verdict, is in `reports/graph-vs-vector.md`.

### Latency and throughput (criterion 5)

| Config | Rerank depth | Warm-up | N timed | Concurrency | p50 (s) | p95 (s) | Throughput (q/s) | D1 pass |
|---|---|---|---|---|---|---|---|---|
| fused-rerank | 50 | 10 | 170 | 1 | 0.9905 | 1.1947 | 1.00 | yes |

### Memory pressure (before / after each pass)

| Config | Swapins before->after | Swapouts before->after | Compressor pages before->after |
|---|---|---|---|
| fused-rerank | 27123400->27174541 | 27738470->27812182 | 158242->187273 |

p50 0.99 s and p95 1.19 s, against a target of p50 < 1.2 s and p95 < 2.5 s: **pass**, at rerank depth 50, concurrency 1, 10 warm-up queries discarded, 170 timed. Throughput is a concurrency-1 figure, not a capacity claim. **Memory caveat:** during this pass swap-outs rose by ~74k pages (the machine was also hosting the containers), so it was not measured on an idle machine; an earlier pass with no swap-out growth gave p50 1.03 s / p95 1.21 s.

### Extraction quality

Hand-annotated sample of 100 sentences (annotated before the pipeline's output for them was consulted). Full run: **4954 triples**.

| Metric | Value | 95% Wilson CI | Correct | Total |
|---|---|---|---|---|
| Precision | 0.577 | [0.489, 0.661] | 71 | 123 |
| Recall | 0.899 | [0.813, 0.948] | 71 | 79 |

Precision is a **conservative lower bound**: spot-checking unmatched triples showed many are additional correct facts the one-representative-per-sentence annotation policy never recorded. See `reports/extraction-quality.md` for the gaps that are known and not fixed (conjoined verb phrases; parallel conjunctions).

## Why `fused` is so much worse than `dense`

On paraphrase queries `fused` puts the gold passage first for **0 / 60** queries versus 27 / 60 for `dense`. Paraphrase gold is invisible to BM25 (zero content-word overlap *by construction*, so BM25's paraphrase score of exactly 0.0 is an artifact of the query design, not a finding about BM25) and to entity-linked graph search, so it earns only `1/(60+rank)` from dense alone (≤ 0.016). A decoy present in all three lists at mid ranks earns roughly three times that. Unweighted RRF rewards consensus across sources, and here the gold passage is single-source. The parameters were pinned in advance and never tuned on the evaluation set, so this is reported as-is. The cross-encoder recovers most of the loss. A source-weighted fusion tuned on a held-out training slice is the obvious next experiment.

## Method and safeguards

- **Labels before code.** The corpus was frozen (`corpus_hash` recorded) and 180 queries + judgments were committed before any retrieval code existed; git history shows the order.
- **Query authorship.** The 60 multi-hop queries are HotpotQA's own labeled questions, with its supporting facts as ground truth. The 60 exact-term and 60 paraphrase queries were **drafted by an AI assistant** and **bulk-accepted** by the author without per-query edits (recorded per query in `braid/eval/queryset/review.jsonl`). Paraphrase drafts were mechanically checked to share no content word with their target passage; 0 reviewer overrides were needed.
- **No test-set leakage in fine-tuning.** Training questions are disjoint from every evaluation question; the excluded set is every evaluation passage — gold *and* distractor — and the guard fails closed. Independently verified on the real data: 0 overlapping questions, passages or query texts.
- **Pinned parameters (never tuned on the evaluation set).** RRF k = 60; candidate depth 100 (BM25), 100 (dense), 50 (graph); 3-way fusion; graph depth 2, fan-out cap 50, hub-degree cap 200; exact case-folded entity linking; rerank depth 50.
- **Statistics were adversarially reviewed** (bootstrap and fine-tuning paths, by a fresh-context reviewer). Findings fixed include a truncation mismatch that had made the first fine-tuned-vs-pretrained comparison invalid; the numbers above are from the corrected rerun.

## Limitations

- **Small evaluation set.** 60 queries per category gives wide intervals; a real few-point gain will often not exclude zero.
- **Paraphrase queries are agent-drafted and adversarially hard for BM25.** They may be systematically easier or harder than real user paraphrases for dense retrieval, and BM25 scoring 0.0 on them is by construction.
- **Extraction yield and quality.** Precision 0.58 (a lower bound), recall 0.90 on the fixed pattern set; graph links exactly matched entity names only (1 of 180 queries linked no entity).
- **One training run, one seed, non-deterministic hardware.** Fine-tuned weights are not bit-reproducible.
- **No multiplicity correction** across the 16 intervals per table.
- **Single machine, 8 GiB.** Latency numbers are for that machine, under the memory conditions noted.
- **Scope.** 1,000 passages of encyclopedic text; nothing here says how these methods scale.

## Reproduce

```bash
docker compose up -d
python -m venv .venv && .venv/bin/pip install -e ".[dev,extract,index]"
.venv/bin/python -m spacy download en_core_web_trf
./scripts/reproduce.sh   # ingest → freeze → extract → index → fine-tune → evaluate; seeds pinned and echoed
```

`reproduce.sh` refuses to evaluate if the rebuilt corpus hash differs from the one the query set was locked to. Fine-tuned weights will not match bit-for-bit (see above); retrieval numbers for the four non-fine-tuned configurations are deterministic. **Note:** a full clean run of this script has not yet been executed end to end; the script was reviewed and its defects fixed, but treat criterion 6 as reviewed, not proven, until you run it.

## Layout

`braid/ingest` corpus + freeze · `braid/extract` NER/relations/quality · `braid/index` BM25/FAISS/Neo4j · `braid/query` retrievers, RRF, rerank, CLI · `braid/eval` metrics, bootstrap, latency, criterion 3, query set · `braid/finetune` disjoint pairs, leakage guard, training · `reports/` every generated table · `SPEC*.md`, `tasks/` the specs and task list.

```bash
python -m braid.query "Who directed Sinister?" --config fused-rerank --k 5
```
