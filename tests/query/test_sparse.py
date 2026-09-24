"""Tests for BM25Retriever (braid/query/sparse.py).

Acceptance criteria (Task 28):
- implements Retriever
- passes the contract suite
- candidate K = 100 per D5
- scored by eval with per-category numbers recorded
"""

import pytest

from braid.query import params
from braid.query.factory import create_retriever
from braid.query.sparse import BM25Retriever
from tests.query.test_contract import assert_retriever_contract


class MockOpenSearchClient:
    """Mock OpenSearch client for unit testing without live container."""

    def __init__(self):
        self.last_search_body = None
        self.last_search_index = None

    def search(self, index: str, body: dict):
        self.last_search_index = index
        self.last_search_body = body
        query_text = (
            body.get("query", {})
            .get("multi_match", {})
            .get("query", "")
        )
        if not query_text:
            return {"hits": {"hits": []}}

        size = body.get("size", 10)
        hits = [
            {
                "_id": f"p_bm25_{i}",
                "_score": float(100 - i * 5),
                "_source": {"title": f"Doc {i}", "text": f"Content {i}"},
            }
            for i in range(min(size, 4))
        ]
        return {"hits": {"hits": hits}}


def test_bm25_retriever_attributes_and_contract():
    client = MockOpenSearchClient()
    retriever = BM25Retriever(client=client)

    assert retriever.name == "bm25"
    assert retriever.candidate_k == params.BM25_CANDIDATE_K
    assert retriever.candidate_k == 100

    assert_retriever_contract(retriever)


def test_bm25_empty_query_returns_empty_list():
    client = MockOpenSearchClient()
    retriever = BM25Retriever(client=client)

    assert retriever.search("") == []
    assert retriever.search("   ") == []
    assert client.last_search_body is None


def test_bm25_search_payload_and_provenance():
    client = MockOpenSearchClient()
    retriever = BM25Retriever(client=client, candidate_k=50)

    hits = retriever.search("sample query", k=3)
    assert len(hits) == 3
    assert client.last_search_body == {
        "size": 3,
        "query": {
            "multi_match": {
                "query": "sample query",
                "fields": ["title", "text"],
            }
        },
    }

    first = hits[0]
    assert first.passage_id == "p_bm25_0"
    assert first.rank == 1
    assert first.score == 100.0
    assert first.provenance == {"bm25": 100.0}


def test_factory_creates_bm25_retriever():
    retriever = create_retriever("bm25")
    assert isinstance(retriever, BM25Retriever)
    assert retriever.name == "bm25"


@pytest.mark.integration
def test_bm25_live_search(require_opensearch):
    retriever = BM25Retriever()
    assert_retriever_contract(retriever, queries=["director", "film", "nonexistenttermxyz"])
    hits = retriever.search("film", k=5)
    assert len(hits) > 0
    assert hits[0].provenance.get("bm25") is not None
