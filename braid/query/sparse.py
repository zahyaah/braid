"""BM25 sparse retriever configuration over OpenSearch (SPEC-query.md).

Implements the Retriever Protocol using OpenSearch BM25 search.
Candidate K before fusion is pinned to 100 (Decision D5).

Official client reference:
- https://docs.opensearch.org/latest/clients/python-low-level/
- https://docs.opensearch.org/latest/query-dsl/full-text/multi-match/
"""

from __future__ import annotations

from typing import Any

from braid.index.bm25 import INDEX_NAME, _client
from braid.query import params
from braid.query.base import Hit


class BM25Retriever:
    """Retriever implementation using OpenSearch BM25 full-text search."""

    name: str = "bm25"

    def __init__(
        self,
        client: Any = None,
        index_name: str = INDEX_NAME,
        candidate_k: int = params.BM25_CANDIDATE_K,
    ) -> None:
        self._client = client
        self.index_name = index_name
        self.candidate_k = candidate_k

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = _client()
        return self._client

    def search(self, query: str, k: int | None = None) -> list[Hit]:
        """Search OpenSearch using BM25 across title and text fields.

        Parameters
        ----------
        query : str
            Query text to search for.
        k : int, optional
            Number of top results to return. If None, defaults to candidate_k (100).

        Returns
        -------
        list[Hit]
            Ranked list of Hit objects with provenance={"bm25": score}.
        """
        top_k = self.candidate_k if k is None else k
        if not query or not query.strip():
            return []

        client = self._get_client()
        # OpenSearch multi_match query over title and text.
        # Source: https://docs.opensearch.org/latest/query-dsl/full-text/multi-match/
        body = {
            "size": top_k,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title", "text"],
                }
            },
        }
        response = client.search(index=self.index_name, body=body)
        raw_hits = response["hits"]["hits"]

        hits: list[Hit] = []
        for i, raw in enumerate(raw_hits):
            score = float(raw["_score"])
            hits.append(
                Hit(
                    passage_id=raw["_id"],
                    score=score,
                    rank=i + 1,
                    provenance={"bm25": score},
                )
            )
        return hits
