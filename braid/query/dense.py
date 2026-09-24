"""Dense retriever configuration over FAISS (SPEC-query.md).

Implements the Retriever Protocol using FAISS IndexFlatIP with
BAAI/bge-small-en-v1.5 embeddings.
Candidate K before fusion is pinned to 100 (Decision D5).

Sources:
- Model card: https://huggingface.co/BAAI/bge-small-en-v1.5
- FAISS Getting Started: https://github.com/facebookresearch/faiss/wiki/Getting-started
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from braid.index.dense import (
    DEFAULT_IDS_PATH,
    DEFAULT_INDEX_PATH,
    embed_query,
    load,
)
from braid.query import params
from braid.query.base import Hit


class DenseRetriever:
    """Retriever implementation using FAISS IndexFlatIP dense vector search."""

    name: str = "dense"

    def __init__(
        self,
        index_path: Path = DEFAULT_INDEX_PATH,
        ids_path: Path = DEFAULT_IDS_PATH,
        candidate_k: int = params.DENSE_CANDIDATE_K,
        index: Any = None,
        ids: list[str] | None = None,
    ) -> None:
        self.index_path = Path(index_path)
        self.ids_path = Path(ids_path)
        self.candidate_k = candidate_k
        self._index = index
        self._ids = ids

    def _ensure_loaded(self) -> None:
        if self._index is None or self._ids is None:
            self._index, self._ids = load(self.index_path, self.ids_path)

    def search(self, query: str, k: int | None = None) -> list[Hit]:
        """Search the FAISS index using dense embeddings.

        Parameters
        ----------
        query : str
            Query text to search for.
        k : int, optional
            Number of top results to return. If None, defaults to candidate_k (100).

        Returns
        -------
        list[Hit]
            Ranked list of Hit objects with provenance={"dense": score}.
        """
        top_k = self.candidate_k if k is None else k
        if not query or not query.strip():
            return []

        self._ensure_loaded()
        assert self._ids is not None
        assert self._index is not None

        query_vec = embed_query(query)
        scores, indices = self._index.search(query_vec, top_k)

        hits: list[Hit] = []
        for i, (score, ordinal) in enumerate(zip(scores[0], indices[0], strict=True)):
            if ordinal == -1:  # fewer vectors in index than top_k
                continue
            pid = self._ids[ordinal]
            s = float(score)
            hits.append(
                Hit(
                    passage_id=pid,
                    score=s,
                    rank=i + 1,
                    provenance={"dense": s},
                )
            )
        return hits
