"""Tests for DenseRetriever (braid/query/dense.py).

Acceptance criteria (Task 29):
- implements Retriever
- passes the contract suite
- candidate K = 100 per D5
- scored by eval with per-category numbers recorded before fusion is started
"""

from pathlib import Path

import numpy as np
import pytest

from braid.query import params
from braid.query.dense import DenseRetriever
from braid.query.factory import create_retriever
from tests.query.test_contract import assert_retriever_contract


class MockFaissIndex:
    """Mock FAISS index for fast unit testing."""

    def __init__(self, ntotal: int = 5):
        self.ntotal = ntotal

    def search(self, query_vec: np.ndarray, k: int):
        count = min(k, self.ntotal)
        scores = np.array([[1.0 - 0.1 * i for i in range(count)]], dtype="float32")
        indices = np.array([[i for i in range(count)]], dtype="int64")
        return scores, indices


def test_dense_retriever_attributes_and_contract(monkeypatch):
    mock_index = MockFaissIndex(ntotal=5)
    mock_ids = [f"p_dense_{i}" for i in range(5)]

    # Mock embed_query to return a dummy vector without loading sentence-transformers
    monkeypatch.setattr(
        "braid.query.dense.embed_query",
        lambda text: np.zeros((1, 384), dtype="float32"),
    )

    retriever = DenseRetriever(index=mock_index, ids=mock_ids)

    assert retriever.name == "dense"
    assert retriever.candidate_k == params.DENSE_CANDIDATE_K
    assert retriever.candidate_k == 100

    assert_retriever_contract(retriever)


def test_dense_empty_query_returns_empty_list():
    retriever = DenseRetriever(index=MockFaissIndex(ntotal=3), ids=["p1", "p2", "p3"])
    assert retriever.search("") == []
    assert retriever.search("   ") == []


def test_dense_search_results_and_provenance(monkeypatch):
    mock_index = MockFaissIndex(ntotal=5)
    mock_ids = [f"p_dense_{i}" for i in range(5)]

    monkeypatch.setattr(
        "braid.query.dense.embed_query",
        lambda text: np.zeros((1, 384), dtype="float32"),
    )

    retriever = DenseRetriever(index=mock_index, ids=mock_ids, candidate_k=10)
    hits = retriever.search("sample query", k=3)

    assert len(hits) == 3
    assert hits[0].passage_id == "p_dense_0"
    assert hits[0].rank == 1
    assert pytest.approx(hits[0].score) == 1.0
    assert hits[0].provenance == {"dense": pytest.approx(1.0)}

    assert hits[1].passage_id == "p_dense_1"
    assert hits[1].rank == 2
    assert pytest.approx(hits[1].score) == 0.9
    assert hits[1].provenance == {"dense": pytest.approx(0.9)}


def test_factory_creates_dense_retriever():
    retriever = create_retriever("dense")
    assert isinstance(retriever, DenseRetriever)
    assert retriever.name == "dense"


@pytest.mark.slow
def test_dense_real_index_search():
    index_path = Path("data/dense.faiss")
    ids_path = Path("data/dense-ids.json")
    if not index_path.exists() or not ids_path.exists():
        pytest.skip("Deliverable dense index not found on disk")

    retriever = DenseRetriever(index_path=index_path, ids_path=ids_path)
    hits = retriever.search("Scott Derrickson film", k=5)
    assert len(hits) == 5
    assert hits[0].provenance.get("dense") is not None
    assert hits[0].score <= 1.01  # cosine / inner product normalized
