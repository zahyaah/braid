"""The shared IndexBuilder interface (SPEC-index.md), so BM25, FAISS, and
Neo4j can be exercised by one contract test suite.

**Interface adaptation, stated explicitly rather than forced silently.**
SPEC-index.md's `IndexBuilder.build(passages)` assumes every store builds
directly from passages. That's true for BM25 (indexes passage text) and FAISS
(embeds passage text), but Neo4j's graph is built from *triples*, extracted
separately (braid/extract). `GraphBuilder.build`/`.add` take the same
`passages` argument for interface uniformity, and internally filter the
already-extracted triple file down to the triples whose `passage_id` is in
that passage list -- so the graph builder's "build" still means "given these
passages, make sure the store reflects them," just via an indirection the
other two stores don't need.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from braid.index import bm25, dense, graph
from braid.index.health import StoreHealth, check_neo4j, check_opensearch
from braid.ingest.models import Passage

DEFAULT_TRIPLES_PATH = Path("data/triples.jsonl")


@dataclass(frozen=True)
class IndexBuildReport:
    count: int
    detail: str


class IndexBuilder(Protocol):
    name: str

    def build(self, passages: list[Passage]) -> IndexBuildReport: ...
    def add(self, passages: list[Passage]) -> IndexBuildReport: ...
    def health(self) -> StoreHealth: ...


class BM25Builder:
    name = "bm25"

    def __init__(self, index_name: str = bm25.INDEX_NAME):
        # Defaults to the real deliverable index; tests pass a distinct name
        # (see tests/index/conftest.py) so the shared contract test suite
        # can never overwrite the real corpus-scale index -- found by
        # running `python -m braid.index health` right after a test run and
        # seeing the real document count drop from 1000 to 15.
        self._index_name = index_name

    def build(self, passages: list[Passage]) -> IndexBuildReport:
        report = bm25.build(passages, index_name=self._index_name)
        return IndexBuildReport(report.indexed, f"{len(report.errors)} error(s)")

    def add(self, passages: list[Passage]) -> IndexBuildReport:
        report = bm25.add(passages, index_name=self._index_name)
        return IndexBuildReport(report.indexed, f"{len(report.errors)} error(s)")

    def health(self) -> StoreHealth:
        return check_opensearch(index=self._index_name)


class DenseBuilder:
    name = "dense"

    def __init__(
        self,
        index_path: Path = dense.DEFAULT_INDEX_PATH,
        ids_path: Path = dense.DEFAULT_IDS_PATH,
    ):
        # Explicit constructor args, not reliance on dense.py's module-level
        # defaults: those defaults are bound into build()/add()/load()'s own
        # signatures at function-definition time, so reassigning the module
        # attribute after import does *not* redirect an already-imported
        # function's default -- found when a test tried exactly that and the
        # build silently went to the real default path instead of a scratch
        # one, then health() (checking the reassigned attribute) reported
        # "down" for an index that existed, just at the other path.
        self._index_path = index_path
        self._ids_path = ids_path

    def build(self, passages: list[Passage]) -> IndexBuildReport:
        n = dense.build(passages, self._index_path, self._ids_path)
        return IndexBuildReport(n, "")

    def add(self, passages: list[Passage]) -> IndexBuildReport:
        n = dense.add(passages, self._index_path, self._ids_path)
        return IndexBuildReport(n, "")

    def health(self) -> StoreHealth:
        if not self._index_path.exists() or not self._ids_path.exists():
            return StoreHealth("dense", "down", None, "no index files on disk")
        _, ids = dense.load(self._index_path, self._ids_path)
        state = "populated" if ids else "empty"
        return StoreHealth("dense", state, len(ids), f"{len(ids)} vectors")


class GraphBuilder:
    name = "graph"

    def __init__(
        self,
        triples_path: Path = DEFAULT_TRIPLES_PATH,
        entity_label: str = graph.DEFAULT_ENTITY_LABEL,
        relation_type: str = graph.DEFAULT_RELATION_TYPE,
    ):
        # Defaults to the real `:Entity`/`:RELATION` labels; tests pass
        # distinct ones (see tests/index/conftest.py) since Neo4j Community
        # Edition has no multi-database isolation to fall back on -- a test
        # run previously wrote into the same graph as the real deliverable
        # build and dropped it from 6,862 nodes to 130.
        self._triples_path = triples_path
        self._entity_label = entity_label
        self._relation_type = relation_type

    def _triples_for(self, passages: list[Passage]):
        import json

        from braid.extract.models import Triple

        passage_ids = {p.passage_id for p in passages}
        with self._triples_path.open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                if row["passage_id"] in passage_ids:
                    yield Triple.from_json(row)

    def build(self, passages: list[Passage]) -> IndexBuildReport:
        return self.add(passages)

    def add(self, passages: list[Passage]) -> IndexBuildReport:
        # load_triples is MERGE-based (upsert), so there is no separate
        # drop-and-rebuild step the way BM25's build() has -- build and add
        # are the same operation for this store.
        triples = list(self._triples_for(passages))
        report = graph.load_triples(
            triples, entity_label=self._entity_label, relation_type=self._relation_type
        )
        return IndexBuildReport(report.edges, f"{report.nodes} nodes, {report.edges} edges total")

    def health(self) -> StoreHealth:
        return check_neo4j(entity_label=self._entity_label)
