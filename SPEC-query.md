# Spec: `query`

Module id `query`. Directory `/query` → `braid/query/`. Depends on: `index`.

## Objective

One retrieval interface, implemented by every configuration under test, called
identically by the CLI and by `eval`. Designing this interface once and
properly is what keeps the benchmark honest: `eval` cannot accidentally give
one configuration a different code path.

## The interface

```python
@dataclass(frozen=True)
class Hit:
    passage_id: str
    score: float
    rank: int
    provenance: dict[str, float]   # per-source contribution: bm25, dense, graph

class Retriever(Protocol):
    name: str
    def search(self, query: str, k: int) -> list[Hit]: ...
```

`provenance` exists so criterion 3 — graph answers where vector fails — is read
off recorded per-source contributions rather than re-derived later by rerunning
configurations and comparing by hand.

## Configurations

Named, constructed by one factory, and the names are what the README's tables
use:

| Name | Composition |
|---|---|
| `bm25` | OpenSearch BM25 only |
| `dense` | FAISS only |
| `fused` | 3-way RRF over bm25 + dense + graph (decision D5) |
| `fused-rerank` | `fused` top-50, reordered by the pretrained cross-encoder |
| `fused-rerank-ft` | `fused` top-50, reordered by the fine-tuned cross-encoder |

## In scope

- **RRF:** `score(d) = sum over sources of 1 / (k_rrf + rank_s(d))`. A document
  ranked by only one source still receives that source's contribution — the
  zero-BM25-match edge case must not be zeroed out, and there is a test for
  exactly that.
- **Graph candidates:** entities are linked from the query text, the graph is
  traversed, and passages attached to the traversed edges enter fusion as a
  third ranked source. The graph is a retrieval signal, not a separate
  answering system (SPEC.md assumption 5).

## Pinned parameters (decision D5)

These are fixed before Task 1 and are **never** tuned against the evaluation
set. Tuning any of them, if it happens at all, uses a validation slice carved
from the D2 training sample. Changing a pinned value is an "ask first" action.
This table is canonical; SPEC.md's D5 mirrors it.

| Parameter | Value | Rationale | Status |
|---|---|---|---|
| RRF `k` | 60 | The value from Cormack, Clarke & Buettcher (2009), cited in code. Not chosen by us, so not tunable by us. | pinned |
| BM25 candidate K | 100 | 10x the reporting depth, so fusion sees beyond the top-10 without making rerank's input pool depend on corpus size. | **pending sign-off** |
| Dense candidate K | 100 | Symmetric with BM25, so neither source enters fusion with a structural depth advantage. | **pending sign-off** |
| Graph candidate K | 50 | Graph candidates are sparser and noisier than either ranked list; a smaller pool limits how much noise a 2-hop expansion can inject. | **pending sign-off** |
| Fusion arity | 3-way: BM25 + dense + graph | See D5 — Build Spec v2 is internally divided between 2-way and 3-way. 3-way is required for criterion 3's primary definition. | **pending sign-off** |
| Graph traversal depth | 2 hops | HotpotQA is 2-hop by construction. Depth 1 cannot answer the questions; depth 3 expands the candidate pool without a question type that needs it. | pinned |
| Relation filter | None — all relation types traversed. Fan-out cap 50 edges per node; entities with degree > 200 skipped as hubs. | A type filter would need to be chosen against data we have not extracted yet. The caps bound blow-up without encoding a guess about which relations matter. | **pending sign-off** |
| Entity-linking rule | Exact match on case-folded, normalized `Entity.name`. No fuzzy matching, so no similarity threshold exists to tune. | The strictest rule is the one whose failures are legible: a missed link is a missed link, not a silently wrong one. If recall proves too low, loosening it is a spec change made on the D2 training slice. | **pending sign-off** |
| Rerank top-K | 50 | Set by D1. | pinned by D1; changeable only via D7 |

A test asserts these values are read from one constants module, so no
configuration can silently diverge from the table.
- **Rerank:** cross-encoder over the fused top-50, batched, model loaded once
  per process.
- **CLI:** `python -m braid.query "<text>" --config fused-rerank --k 10`,
  printing ranked passage IDs, scores, provenance, and timing.

## Acceptance

- [ ] All five configurations implement `Retriever` and pass one shared
      contract test suite.
- [ ] Zero-BM25-match test: a query with no lexical match but a strong semantic
      match still returns the correct passage in `fused`, with non-zero dense
      provenance and zero bm25 provenance.
- [ ] RRF verified on constructed rank lists against hand-computed scores.
- [ ] CLI and `eval` are proven to call the same code path — the CLI
      constructs its retriever through the same factory `eval` uses, and a test
      asserts identical results for the same query and seed.
- [ ] Warm p50 < 1.2 s and p95 < 2.5 s for `fused-rerank` (decision D1),
      measured by `eval`'s latency harness.
- [ ] Every D5 parameter is read from one constants module, asserted by test.
- [ ] Every client call grounded in official docs and cited (workflow step 5).

## Build order within the module

`bm25` alone, tested and scored by `eval` → `dense`, tested and scored →
graph candidates → RRF fusion → rerank. Each step is scored before the next is
started. Do not debug three unfamiliar systems at once (workflow step 4).

## Risks

Reranking 50 pairs on an M1 CPU is the dominant latency term and the main
threat to D1. If p95 exceeds 2.5 s, decision D7 governs: rerank top-K 50 -> 30
first, then a smaller cross-encoder, with the fallback recorded and the
criterion-1 table regenerated at the new depth. Lowering D1's thresholds is not
one of the pre-authorized fallbacks and remains "ask first".
