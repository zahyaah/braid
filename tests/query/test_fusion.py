"""Tests for FusedRetriever (braid/query/fusion.py).

Acceptance criteria (Task 31):
- 1 / (k_rrf + rank), k_rrf = 60, source cited; 3-way over bm25, dense, graph per D5
- Hand-computed test on constructed rank lists
- Zero-BM25-match test: a query with no lexical match but a strong semantic match
  still returns the correct passage, with non-zero dense provenance and zero bm25 provenance
"""

import pytest

from braid.query import params
from braid.query.base import Hit
from braid.query.factory import create_retriever
from braid.query.fusion import FusedRetriever
from tests.query.test_contract import assert_retriever_contract


class ListRetriever:
    """Mock retriever returning a fixed list of passage IDs."""

    def __init__(self, name: str, passage_ids: list[str]):
        self.name = name
        self.passage_ids = passage_ids

    def search(self, query: str, k: int = 10) -> list[Hit]:
        if not query:
            return []
        ids = self.passage_ids[:k]
        return [
            Hit(
                passage_id=pid,
                score=1.0 / (i + 1),
                rank=i + 1,
                provenance={self.name: 1.0 / (i + 1)},
            )
            for i, pid in enumerate(ids)
        ]


def test_fused_retriever_contract():
    bm25 = ListRetriever("bm25", ["doc1", "doc2", "doc3"])
    dense = ListRetriever("dense", ["doc2", "doc3", "doc4"])
    graph = ListRetriever("graph", ["doc1", "doc5"])

    retriever = FusedRetriever(
        bm25_retriever=bm25,
        dense_retriever=dense,
        graph_retriever=graph,
    )

    assert retriever.name == "fused"
    assert retriever.k_rrf == params.RRF_K
    assert retriever.k_rrf == 60
    assert retriever.bm25_k == 100
    assert retriever.dense_k == 100
    assert retriever.graph_k == 50

    assert_retriever_contract(retriever, queries=["q1", "q2"])


def test_hand_computed_rrf_scoring():
    """Verify exact hand-computed RRF values for k_rrf = 60.

    Inputs:
    - bm25: [d1 (rank 1), d2 (rank 2)]
    - dense: [d2 (rank 1), d3 (rank 2)]
    - graph: [d1 (rank 1)]

    Analytical scores with k=60:
    - d1: 1/(60+1) [bm25] + 1/(60+1) [graph] = 2/61 = 0.0327868852...
    - d2: 1/(60+2) [bm25] + 1/(60+1) [dense] = 1/62 + 1/61 = 0.0325224677...
    - d3: 1/(60+2) [dense] = 1/62 = 0.0161290322...

    Expected order: d1 (rank 1), d2 (rank 2), d3 (rank 3).
    """
    bm25 = ListRetriever("bm25", ["d1", "d2"])
    dense = ListRetriever("dense", ["d2", "d3"])
    graph = ListRetriever("graph", ["d1"])

    retriever = FusedRetriever(
        bm25_retriever=bm25,
        dense_retriever=dense,
        graph_retriever=graph,
        k_rrf=60,
    )

    hits = retriever.search("test query", k=10)

    assert len(hits) == 3

    assert hits[0].passage_id == "d1"
    assert hits[0].rank == 1
    expected_d1 = 2.0 / 61.0
    assert pytest.approx(hits[0].score, rel=1e-6) == expected_d1
    assert pytest.approx(hits[0].provenance["bm25"], rel=1e-6) == 1.0 / 61.0
    assert hits[0].provenance["dense"] == 0.0
    assert pytest.approx(hits[0].provenance["graph"], rel=1e-6) == 1.0 / 61.0

    assert hits[1].passage_id == "d2"
    assert hits[1].rank == 2
    expected_d2 = (1.0 / 62.0) + (1.0 / 61.0)
    assert pytest.approx(hits[1].score, rel=1e-6) == expected_d2
    assert pytest.approx(hits[1].provenance["bm25"], rel=1e-6) == 1.0 / 62.0
    assert pytest.approx(hits[1].provenance["dense"], rel=1e-6) == 1.0 / 61.0
    assert hits[1].provenance["graph"] == 0.0

    assert hits[2].passage_id == "d3"
    assert hits[2].rank == 3
    expected_d3 = 1.0 / 62.0
    assert pytest.approx(hits[2].score, rel=1e-6) == expected_d3
    assert hits[2].provenance["bm25"] == 0.0
    assert pytest.approx(hits[2].provenance["dense"], rel=1e-6) == 1.0 / 62.0
    assert hits[2].provenance["graph"] == 0.0


def test_zero_bm25_match_preserves_dense_hit():
    """Zero-BM25-match test: a query with no lexical match but a strong semantic match
    still returns the correct passage, with non-zero dense provenance and zero bm25 provenance.
    """
    bm25 = ListRetriever("bm25", [])  # no lexical match
    dense = ListRetriever("dense", ["p_semantic_match", "p_other"])
    graph = ListRetriever("graph", [])

    retriever = FusedRetriever(
        bm25_retriever=bm25,
        dense_retriever=dense,
        graph_retriever=graph,
        k_rrf=60,
    )

    hits = retriever.search("semantic query with no lexical match", k=5)

    assert len(hits) == 2
    top = hits[0]
    assert top.passage_id == "p_semantic_match"
    assert top.rank == 1
    assert pytest.approx(top.score, rel=1e-6) == 1.0 / 61.0
    assert top.provenance["bm25"] == 0.0
    assert pytest.approx(top.provenance["dense"], rel=1e-6) == 1.0 / 61.0
    assert top.provenance["graph"] == 0.0


def test_factory_creates_fused_retriever():
    retriever = create_retriever("fused")
    assert isinstance(retriever, FusedRetriever)
    assert retriever.name == "fused"


@pytest.mark.integration
def test_live_fused_retriever_search(require_opensearch, require_neo4j):
    retriever = create_retriever("fused")
    hits = retriever.search("Who directed Sinister?", k=10)

    assert len(hits) > 0
    first = hits[0]
    assert first.rank == 1
    assert first.score > 0.0
    assert "bm25" in first.provenance
    assert "dense" in first.provenance
    assert "graph" in first.provenance
