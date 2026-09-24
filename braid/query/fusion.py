"""Reciprocal Rank Fusion (RRF) 3-way retriever (SPEC-query.md).

Combines BM25, dense vector, and graph candidate lists into a single ranked list.
Score formula:
    score(d) = sum_{s in sources} 1 / (k_rrf + rank_s(d))

Pinned constant:
    k_rrf = 60 (Decision D5)
Source:
    Cormack, Clarke & Buettcher (2009), "Reciprocal rank fusion outperforms
    Condorcet and individual machine learning methods", SIGIR '09.
    https://doi.org/10.1145/1571941.1572114
"""

from __future__ import annotations

from typing import Any

from braid.query import params
from braid.query.base import Hit, Retriever
from braid.query.dense import DenseRetriever
from braid.query.graph import GraphRetriever
from braid.query.sparse import BM25Retriever


def rrf_score(rank: int, k_rrf: int = params.RRF_K) -> float:
    """Compute RRF contribution for a 1-indexed rank: 1 / (k_rrf + rank)."""
    return 1.0 / (k_rrf + rank)


class FusedRetriever:
    """3-way Reciprocal Rank Fusion over BM25, dense vectors, and graph candidates."""

    name: str = "fused"

    def __init__(
        self,
        bm25_retriever: Retriever | None = None,
        dense_retriever: Retriever | None = None,
        graph_retriever: Retriever | None = None,
        k_rrf: int = params.RRF_K,
        bm25_k: int = params.BM25_CANDIDATE_K,
        dense_k: int = params.DENSE_CANDIDATE_K,
        graph_k: int = params.GRAPH_CANDIDATE_K,
        **_kwargs: Any,
    ) -> None:
        self.k_rrf = k_rrf
        self.bm25_k = bm25_k
        self.dense_k = dense_k
        self.graph_k = graph_k
        self._bm25 = bm25_retriever
        self._dense = dense_retriever
        self._graph = graph_retriever

    def _get_bm25(self) -> Retriever:
        if self._bm25 is None:
            self._bm25 = BM25Retriever(candidate_k=self.bm25_k)
        return self._bm25

    def _get_dense(self) -> Retriever:
        if self._dense is None:
            self._dense = DenseRetriever(candidate_k=self.dense_k)
        return self._dense

    def _get_graph(self) -> Retriever:
        if self._graph is None:
            self._graph = GraphRetriever(candidate_k=self.graph_k)
        return self._graph

    def search(self, query: str, k: int = 10) -> list[Hit]:
        """Perform 3-way RRF fusion across BM25, dense, and graph sources.

        Parameters
        ----------
        query : str
            Query text to search for.
        k : int
            Number of top fused results to return.

        Returns
        -------
        list[Hit]
            Top-k fused hits with provenance containing per-source contributions.
        """
        if not query or not query.strip():
            return []

        bm25_hits = self._get_bm25().search(query, k=self.bm25_k)
        dense_hits = self._get_dense().search(query, k=self.dense_k)
        graph_hits = self._get_graph().search(query, k=self.graph_k)

        source_hits: list[tuple[str, list[Hit]]] = [
            ("bm25", bm25_hits),
            ("dense", dense_hits),
            ("graph", graph_hits),
        ]

        scores: dict[str, float] = {}
        provenance: dict[str, dict[str, float]] = {}

        for source_name, hits in source_hits:
            for hit in hits:
                pid = hit.passage_id
                contrib = rrf_score(hit.rank, self.k_rrf)

                scores[pid] = scores.get(pid, 0.0) + contrib

                if pid not in provenance:
                    provenance[pid] = {"bm25": 0.0, "dense": 0.0, "graph": 0.0}
                provenance[pid][source_name] = contrib

        if not scores:
            return []

        # Sort descending by fused score, breaking ties by passage_id asc
        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]

        return [
            Hit(
                passage_id=pid,
                score=score,
                rank=i + 1,
                provenance=provenance[pid],
            )
            for i, (pid, score) in enumerate(ordered)
        ]
