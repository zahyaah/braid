# Capability Map: Braid — Hybrid Retrieval Engine

Status: **awaiting review**. No module spec is written and no code is
committed until this map is approved.

## Modules

| Module id | Responsibility | Directory | Depends on |
|---|---|---|---|
| `ingest` | HotpotQA subset loader, normalization, chunking, dedupe, stable passage IDs | `/ingest` | — |
| `queryset` | The 90+ hand-labeled queries and their relevance judgments, plus a schema validator | `/eval/queryset` | `ingest` |
| `eval` | Metrics (recall@k, nDCG@10, MRR), per-category stratification, paired bootstrap CIs, comparison table | `/eval` | `queryset` |
| `extract` | spaCy NER + dependency-parse SVO relation extraction, with its own precision/recall report against a hand-checked sample | `/extract` | `ingest` |
| `index` | BM25 (OpenSearch), dense (FAISS), graph (Neo4j) index builders; incremental add | `/index` | `ingest`, `extract` |
| `query` | Retrieval interface, RRF fusion, cross-encoder rerank, graph traversal; library + CLI | `/query` | `index` |
| `finetune` | Cross-encoder fine-tuning on labeled pairs, before/after comparison with CIs | `/finetune` | `query`, `eval` |

No cycles. `eval` imports the `query` module's interface at call time, not at
build time: it is written and tested against a stub retriever before any real
retriever exists.

## Build order

```
ingest
  → queryset → eval           (harness and labels exist before retrieval code)
  → extract
  → index (BM25 → FAISS → Neo4j, in that order)
  → query (BM25-only → +dense → +RRF → +graph → +rerank)
  → finetune
```

Each arrow is a checkpoint. A stage is not "done" until `eval` can score it.

## Why `queryset` is its own module

Acceptance criteria 1 through 4 are unverifiable without labeled queries that
were written before any retrieval code ran. Making the query set a separate,
separately-reviewed artifact is what makes "labels written first" an auditable
fact rather than a claim. It lives under `/eval` on disk but is gated on its
own.
