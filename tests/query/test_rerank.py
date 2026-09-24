"""Tests for RerankRetriever (braid/query/rerank.py).

Acceptance criteria (Task 32):
- ms-marco-MiniLM-L-6-v2 over the fused top-50, batched, loaded once per process
- Warm p50 and p95 measured against D1 and recorded with rerank_depth
- D7 fallbacks applied when p95 >= 2.5 s: top-K 50 -> 30, then smaller cross-encoder

All model-dependent tests use a stub cross-encoder to avoid network downloads in CI.
Live integration tests (marked @pytest.mark.integration) require real infrastructure.
"""

from __future__ import annotations

import pytest

from braid.query import params
from braid.query.base import Hit
from braid.query.factory import create_retriever
from braid.query.rerank import DEFAULT_MODEL_NAME, RerankRetriever
from tests.query.test_contract import assert_retriever_contract

# ---------------------------------------------------------------------------
# Shared test doubles
# ---------------------------------------------------------------------------


class _ConstantScoreModel:
    """Stub cross-encoder: assigns the same score to every pair (predictable)."""

    def predict(self, pairs: list[tuple[str, str]], batch_size: int = 32) -> list[float]:
        return [1.0] * len(pairs)


class _AscendingScoreModel:
    """Stub cross-encoder: assigns scores 1.0, 2.0, 3.0 … in order (last pair wins)."""

    def predict(self, pairs: list[tuple[str, str]], batch_size: int = 32) -> list[float]:
        return [float(i + 1) for i in range(len(pairs))]


class _ListRetriever:
    """Mock retriever that returns a fixed, ordered list of passage IDs."""

    def __init__(self, name: str, passage_ids: list[str]) -> None:
        self.name = name
        self.passage_ids = passage_ids

    def search(self, query: str, k: int = 10) -> list[Hit]:
        if not query:
            return []
        return [
            Hit(
                passage_id=pid,
                score=1.0 / (i + 1),
                rank=i + 1,
                provenance={"fused": 1.0 / (i + 1)},
            )
            for i, pid in enumerate(self.passage_ids[:k])
        ]


def _stub_retriever(name: str = "fused", passage_ids: list[str] | None = None) -> _ListRetriever:
    ids = passage_ids or [f"p{i}" for i in range(60)]
    return _ListRetriever(name, ids)


# ---------------------------------------------------------------------------
# Contract tests (no real model or index needed)
# ---------------------------------------------------------------------------


def test_rerank_retriever_contract():
    """RerankRetriever satisfies the Retriever protocol."""
    base = _stub_retriever(passage_ids=["a", "b", "c"])
    corpus = {"a": "passage A text", "b": "passage B text", "c": "passage C text"}
    retriever = RerankRetriever(
        base_retriever=base,
        model=_ConstantScoreModel(),
        corpus=corpus,
    )
    assert retriever.name == "fused-rerank"
    assert_retriever_contract(retriever, queries=["test query 1", "test query 2"])


def test_rerank_top_k_param_matches_spec():
    """RERANK_TOP_K must equal 50 per decision D1 / D5."""
    assert params.RERANK_TOP_K == 50


def test_default_model_name():
    """Default model must be ms-marco-MiniLM-L-6-v2 per D1."""
    assert DEFAULT_MODEL_NAME == "cross-encoder/ms-marco-MiniLM-L-6-v2"


# ---------------------------------------------------------------------------
# Behavioural tests (stub model + stub corpus)
# ---------------------------------------------------------------------------


def test_reranker_respects_k():
    """search(query, k) returns at most k hits."""
    base = _stub_retriever(passage_ids=[f"p{i}" for i in range(20)])
    corpus = {f"p{i}": f"text {i}" for i in range(20)}
    retriever = RerankRetriever(
        base_retriever=base,
        model=_ConstantScoreModel(),
        corpus=corpus,
    )
    hits = retriever.search("query", k=5)
    assert len(hits) == 5


def test_reranker_reorders_by_cross_encoder_score():
    """Cross-encoder scores must override the original fusion ranking."""
    # Base returns [p0, p1, p2] in that order (p0 is top fusion result).
    # Ascending model gives p0 → 1.0, p1 → 2.0, p2 → 3.0, so p2 should win.
    base = _stub_retriever(passage_ids=["p0", "p1", "p2"])
    corpus = {"p0": "text zero", "p1": "text one", "p2": "text two"}
    retriever = RerankRetriever(
        base_retriever=base,
        model=_AscendingScoreModel(),
        corpus=corpus,
    )
    hits = retriever.search("query", k=3)
    assert len(hits) == 3
    assert hits[0].passage_id == "p2"
    assert hits[0].rank == 1
    assert hits[1].passage_id == "p1"
    assert hits[1].rank == 2
    assert hits[2].passage_id == "p0"
    assert hits[2].rank == 3


def test_reranker_preserves_provenance():
    """Provenance dict from the fused hit must be carried through to the reranked hit."""
    base = _ListRetriever(
        name="fused",
        passage_ids=["x"],
    )
    # Manually give x a multi-source provenance
    _original_search = base.search

    def patched_search(query: str, k: int = 10) -> list[Hit]:
        hits = _original_search(query, k)
        return [
            Hit(
                passage_id=h.passage_id,
                score=h.score,
                rank=h.rank,
                provenance={"bm25": 0.3, "dense": 0.5, "graph": 0.2},
            )
            for h in hits
        ]

    base.search = patched_search  # type: ignore[method-assign]

    corpus = {"x": "some text"}
    retriever = RerankRetriever(
        base_retriever=base,
        model=_ConstantScoreModel(),
        corpus=corpus,
    )
    hits = retriever.search("q", k=1)
    assert len(hits) == 1
    assert hits[0].provenance == {"bm25": 0.3, "dense": 0.5, "graph": 0.2}


def test_empty_query_returns_empty():
    """Empty or whitespace-only queries must return an empty list without error."""
    base = _stub_retriever()
    corpus = {}
    retriever = RerankRetriever(
        base_retriever=base,
        model=_ConstantScoreModel(),
        corpus=corpus,
    )
    assert retriever.search("", k=10) == []
    assert retriever.search("   ", k=10) == []


def test_missing_corpus_entry_uses_empty_text():
    """A passage_id absent from the corpus must be scored against '' without crash."""
    base = _stub_retriever(passage_ids=["known", "unknown"])
    corpus = {"known": "some text"}  # 'unknown' deliberately absent
    retriever = RerankRetriever(
        base_retriever=base,
        model=_ConstantScoreModel(),
        corpus=corpus,
    )
    hits = retriever.search("query", k=2)
    assert {h.passage_id for h in hits} == {"known", "unknown"}


def test_reranker_fetches_rerank_k_from_base():
    """Base retriever must be called with rerank_k, not the final k."""
    fetched: list[int] = []

    class _TrackingBase:
        name = "fused"

        def search(self, query: str, k: int = 10) -> list[Hit]:
            fetched.append(k)
            return [Hit(passage_id="p1", score=1.0, rank=1, provenance={})]

    corpus = {"p1": "text"}
    retriever = RerankRetriever(
        base_retriever=_TrackingBase(),
        model=_ConstantScoreModel(),
        corpus=corpus,
        rerank_k=30,
    )
    retriever.search("q", k=10)
    assert fetched == [30], f"Base was called with k={fetched}, expected [30]"


def test_model_loaded_once_per_instance(monkeypatch):
    """Cross-encoder model must be loaded lazily and cached (one load per instance)."""
    load_count = 0

    class _CountingModel:
        def predict(self, pairs, batch_size=32):
            return [1.0] * len(pairs)

    def _patched_loader(name: str):
        nonlocal load_count
        load_count += 1
        return _CountingModel()

    import braid.query.rerank as rerank_mod

    monkeypatch.setattr(rerank_mod, "_get_cross_encoder", _patched_loader)

    base = _stub_retriever(passage_ids=["a", "b"])
    corpus = {"a": "text a", "b": "text b"}
    # model=None so it will call _get_cross_encoder
    retriever = RerankRetriever(base_retriever=base, corpus=corpus)
    retriever.search("q1", k=2)
    retriever.search("q2", k=2)
    assert load_count == 1, f"Model loaded {load_count} times, expected 1"


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


def test_factory_creates_rerank_retriever():
    """create_retriever('fused-rerank') must return a RerankRetriever."""
    retriever = create_retriever("fused-rerank")
    assert isinstance(retriever, RerankRetriever)
    assert retriever.name == "fused-rerank"


def test_factory_creates_rerank_ft_retriever():
    """create_retriever('fused-rerank-ft') must return a RerankRetriever with ft name."""
    retriever = create_retriever("fused-rerank-ft")
    assert isinstance(retriever, RerankRetriever)
    assert retriever.name == "fused-rerank-ft"


# ---------------------------------------------------------------------------
# Latency tests (D1 / D7, stub model — no network)
# ---------------------------------------------------------------------------


def test_latency_below_d1_thresholds_with_stub_model():
    """Warm p50 and p95 must be well under D1 thresholds when using a stub model.

    D1 thresholds: p50 < 1.2 s, p95 < 2.5 s.
    With a stub model (no inference), this must pass comfortably.
    """
    from braid.eval.latency import D1_P50_SECONDS, D1_P95_SECONDS, WARMUP_QUERIES, measure_latency

    n_queries = WARMUP_QUERIES + 20
    queries = [f"query {i}" for i in range(n_queries)]

    base = _stub_retriever(passage_ids=[f"p{i}" for i in range(params.RERANK_TOP_K)])
    corpus = {f"p{i}": f"text passage {i}" for i in range(params.RERANK_TOP_K)}
    retriever = RerankRetriever(
        base_retriever=base,
        model=_ConstantScoreModel(),
        corpus=corpus,
    )

    report = measure_latency(retriever, queries, rerank_depth=params.RERANK_TOP_K)
    assert report.config_name == "fused-rerank"
    assert report.rerank_depth == params.RERANK_TOP_K
    assert report.p50_seconds < D1_P50_SECONDS, (
        f"p50 {report.p50_seconds:.4f}s exceeds D1 threshold {D1_P50_SECONDS}s"
    )
    assert report.p95_seconds < D1_P95_SECONDS, (
        f"p95 {report.p95_seconds:.4f}s exceeds D1 threshold {D1_P95_SECONDS}s"
    )


# ---------------------------------------------------------------------------
# Integration tests (require live infrastructure + model download)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_live_rerank_retriever_search(require_opensearch, require_neo4j):
    """Live integration: fused-rerank over real OpenSearch + Neo4j + FAISS."""
    retriever = create_retriever("fused-rerank")
    hits = retriever.search("Who directed Sinister?", k=10)

    assert len(hits) > 0
    first = hits[0]
    assert first.rank == 1
    assert first.score != 0.0
    # Cross-encoder scores can be negative (logit space) — just check they differ
    scores = [h.score for h in hits]
    assert len(set(scores)) > 1 or len(hits) == 1
