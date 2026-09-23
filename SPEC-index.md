# Spec: `index`

Module id `index`. Directory `/index` → `braid/index/`. Depends on: `ingest`,
`extract`.

## Objective

Build and maintain the three indexes — BM25 in OpenSearch, dense vectors in
FAISS, entity triples in Neo4j — behind one builder interface, with
incremental add, not just full rebuild.

## In scope

- **BM25 (OpenSearch 2.x, single node):** index mapping with `title` and
  `text` analyzed fields and `passage_id` as document ID. Analyzer settings
  stated explicitly, not defaulted implicitly, because BM25 numbers depend on
  them. Bulk indexing with refresh control.
- **Dense (FAISS):** `BAAI/bge-small-en-v1.5`, 384-dim, normalized vectors,
  `IndexFlatIP` — exact search, no training step, correct at this corpus size
  and removes an entire class of approximate-recall confounds from the
  benchmark. Query-side prefix handling follows the model card, not habit.
  A sidecar `ids.json` maps FAISS ordinals to passage IDs; the two are written
  in one operation and their lengths asserted equal on load.
- **Graph (Neo4j 5.x Community):** `(:Entity {name, type})` nodes and
  `[:RELATION {relation, passage_id, sentence_index}]` edges from
  `data/triples.jsonl`. Uniqueness constraint on `Entity.name`. Loaded with
  batched `UNWIND` + `MERGE`.
- **Incremental add:** `index add --since <manifest>` adds new passages to all
  three stores without rebuilding, and is verified to leave existing entries
  unchanged.
- Heap caps per SPEC.md Hardware live in `docker-compose.yml` in this module.

## Out of scope

Querying and ranking (that is `query`).

## Interface

```python
class IndexBuilder(Protocol):
    name: str
    def build(self, passages: Iterable[Passage]) -> BuildReport: ...
    def add(self, passages: Iterable[Passage]) -> BuildReport: ...
    def health(self) -> HealthStatus: ...
```

## Acceptance

- [ ] All three builders implement the same protocol and are exercised by one
      shared contract test suite.
- [ ] `health()` distinguishes "container not running", "reachable but empty",
      and "populated with N documents". The boring failure modes of a
      three-service local stack must be diagnosable from one command.
- [ ] Document counts after build equal the corpus size, asserted per store.
- [ ] Incremental add verified: build on 10 passages, add 5, confirm 15 present
      and the original 10 byte-identical. For FAISS, confirm ordinal-to-ID
      mapping still resolves correctly after the add.
- [ ] Every OpenSearch, FAISS, and Neo4j call is grounded in current official
      documentation and the source cited in a code comment (author workflow
      step 5). Three unfamiliar client libraries is exactly where plausible
      method signatures get invented.
- [ ] Integration tests skip cleanly with a stated reason when containers are
      down, rather than failing.

## Verify

`docker compose up -d && python -m braid.index build --all && python -m braid.index health`

## Risks

FAISS ordinal-to-passage-ID drift after incremental add silently returns
wrong passages with plausible scores. The length assertion on load and the
post-add resolution test are the guards.
