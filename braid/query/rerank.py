"""Cross-encoder rerank retriever (SPEC-query.md).

Reranks the top-50 candidates from fused retrieval using a pretrained or fine-tuned
cross-encoder:
    ms-marco-MiniLM-L-6-v2 (Decision D1 / D5).

Grounded in sentence-transformers CrossEncoder documentation:
https://sbert.net/docs/package_reference/cross_encoder.html
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from braid.query import params
from braid.query.base import Hit, Retriever
from braid.query.fusion import FusedRetriever

DEFAULT_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DEFAULT_CORPUS_PATH = Path("data/corpus.jsonl")
# Inference max_length, stated explicitly and applied identically to the
# pretrained and the fine-tuned reranker. Found by adversarial review: the
# fine-tuned checkpoint was trained (and its tokenizer saved) at 256 while the
# pretrained model silently scored at sentence-transformers' 512 default, so
# `fused-rerank` vs `fused-rerank-ft` differed in truncation as well as
# weights (74 of 1000 passages exceed ~170 words). 512 is kept so the
# pretrained baseline's reported numbers do not change; the fine-tuned model
# is scored at 512 as well (its position embeddings support it).
INFERENCE_MAX_LENGTH = 512

_cross_encoder_cache: dict[str, Any] = {}
_corpus_cache: dict[str, dict[str, str]] = {}


def _load_corpus(path: Path = DEFAULT_CORPUS_PATH) -> dict[str, str]:
    """Load passage texts from corpus.jsonl, cached at module level."""
    key = str(path)
    if key not in _corpus_cache:
        if not path.exists():
            # Fail closed: a missing corpus used to yield an empty mapping, so
            # every candidate silently scored against "" with no error.
            raise FileNotFoundError(f"corpus not found at {path}; cannot rerank without text")
        mapping: dict[str, str] = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    pid = row["passage_id"]
                    title = row.get("title", "")
                    text = row.get("text", "")
                    mapping[pid] = f"{title}: {text}" if title else text
        _corpus_cache[key] = mapping
    return _corpus_cache[key]


def _get_cross_encoder(
    name_or_path: str = DEFAULT_MODEL_NAME, max_length: int = INFERENCE_MAX_LENGTH
) -> Any:
    """Load CrossEncoder model once per process, keyed by (model, max_length)."""
    key = f"{name_or_path}@{max_length}"
    if key not in _cross_encoder_cache:
        from sentence_transformers import CrossEncoder

        _cross_encoder_cache[key] = CrossEncoder(name_or_path, max_length=max_length)
    return _cross_encoder_cache[key]


class RerankRetriever:
    """Retriever implementation that reranks candidates using a cross-encoder model."""

    def __init__(
        self,
        name: str = "fused-rerank",
        base_retriever: Retriever | None = None,
        rerank_k: int = params.RERANK_TOP_K,
        model_name: str = DEFAULT_MODEL_NAME,
        model: Any = None,
        corpus: dict[str, str] | None = None,
        corpus_path: Path = DEFAULT_CORPUS_PATH,
        **_kwargs: Any,
    ) -> None:
        self.name = name
        self.rerank_k = rerank_k
        self.model_name = model_name
        self.corpus_path = corpus_path
        self._base = base_retriever
        self._model = model
        self._corpus = corpus

    def _get_base(self) -> Retriever:
        if self._base is None:
            self._base = FusedRetriever()
        return self._base

    def _get_model_instance(self) -> Any:
        if self._model is None:
            self._model = _get_cross_encoder(self.model_name)
        return self._model

    def _get_corpus_mapping(self) -> dict[str, str]:
        if self._corpus is None:
            self._corpus = _load_corpus(self.corpus_path)
        return self._corpus

    def search(self, query: str, k: int = 10) -> list[Hit]:
        """Rerank candidates using cross-encoder predictions.

        Parameters
        ----------
        query : str
            Query string.
        k : int
            Number of top results to return.

        Returns
        -------
        list[Hit]
            Top-k reranked hits, preserving source provenance from fusion.
        """
        if not query or not query.strip():
            return []

        base_hits = self._get_base().search(query, k=self.rerank_k)
        if not base_hits:
            return []

        corpus = self._get_corpus_mapping()
        missing = [h.passage_id for h in base_hits if h.passage_id not in corpus]
        if missing:
            raise KeyError(f"candidate passage ids missing from corpus: {missing[:5]}")
        pairs = [(query, corpus[h.passage_id]) for h in base_hits]

        model = self._get_model_instance()
        scores = model.predict(pairs, batch_size=32)

        scored_candidates = []
        for hit, ce_score in zip(base_hits, scores, strict=True):
            scored_candidates.append(
                (
                    hit.passage_id,
                    float(ce_score),
                    hit.provenance,
                )
            )

        # Sort descending by cross-encoder score, tie-break by passage_id asc
        ordered = sorted(scored_candidates, key=lambda item: (-item[1], item[0]))[:k]

        return [
            Hit(
                passage_id=pid,
                score=score,
                rank=i + 1,
                provenance=prov,
            )
            for i, (pid, score, prov) in enumerate(ordered)
        ]
