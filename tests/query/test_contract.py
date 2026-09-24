"""Contract tests for the Retriever Protocol and Hit dataclass (SPEC-query.md).

braid/query/base.py must stay interface-only: the whitelisted exception to
Checkpoint B's "no retrieval code before review" rule requires every function
body to be exactly `...` (amendment 7, item 1).

This module also provides the shared contract test suite (`assert_retriever_contract`)
used by all configuration tests to guarantee identical behavior across retrievers.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from braid.query.base import Hit, Retriever
from braid.query.factory import (
    SUPPORTED_CONFIGS,
    create_retriever,
    register_retriever,
    unregister_retriever,
)


def assert_retriever_contract(
    retriever: Retriever,
    queries: list[str] | None = None,
    test_ks: tuple[int, ...] = (1, 5, 10),
) -> None:
    """Shared contract test suite that runs against any Retriever implementation.

    Verifies:
    1. Has a non-empty string name.
    2. search(query, k) returns a list of Hit instances.
    3. Returned hits count is <= k.
    4. Hit ranks are strictly 1-indexed and contiguous (1, 2, ..., n).
    5. Hit scores are monotonically non-increasing.
    6. Hit provenance is a dictionary mapping str -> float.
    7. Hit passage_id is a non-empty string.
    """
    assert isinstance(retriever.name, str) and retriever.name, "Retriever must have non-empty name"

    if queries is None:
        queries = ["test query", "another sample question", ""]

    for query in queries:
        for k in test_ks:
            hits = retriever.search(query, k)
            assert isinstance(hits, list), f"Expected list of Hit, got {type(hits)}"
            assert len(hits) <= k, f"Expected at most {k} hits, got {len(hits)}"

            for i, hit in enumerate(hits):
                assert isinstance(hit, Hit), f"Item {i} is not a Hit instance: {type(hit)}"
                assert isinstance(hit.passage_id, str) and hit.passage_id, "Hit passage_id invalid"
                assert isinstance(hit.score, (int, float)), "Hit score must be numeric"
                assert hit.rank == i + 1, f"Expected rank {i + 1}, got {hit.rank}"
                assert isinstance(hit.provenance, dict), "Hit provenance must be a dict"
                for src, weight in hit.provenance.items():
                    assert isinstance(src, str), "Provenance source name must be str"
                    assert isinstance(weight, (int, float)), "Provenance weight must be numeric"

                if i > 0:
                    assert (
                        hits[i - 1].score >= hit.score
                    ), f"Scores must be non-increasing: {hits[i - 1].score} < {hit.score}"


class StubContractRetriever:
    """A minimal stub retriever for verifying the contract test suite."""

    def __init__(self, name: str = "stub"):
        self.name = name

    def search(self, query: str, k: int) -> list[Hit]:
        if not query:
            return []
        count = min(k, 3)
        return [
            Hit(
                passage_id=f"doc_{idx}",
                score=1.0 / (idx + 1),
                rank=idx + 1,
                provenance={self.name: 1.0 / (idx + 1)},
            )
            for idx in range(count)
        ]


def test_base_module_contains_no_function_bodies_beyond_ellipsis():
    source = Path("braid/query/base.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert len(node.body) == 1, f"{node.name} has more than one statement"
            stmt = node.body[0]
            is_ellipsis = (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and stmt.value.value is Ellipsis
            )
            assert is_ellipsis, f"{node.name} body is not '...'"


def test_hit_and_retriever_are_importable():
    hit = Hit(passage_id="p1", score=1.0, rank=1, provenance={"bm25": 1.0})
    assert hit.passage_id == "p1"
    assert hit.provenance == {"bm25": 1.0}
    assert hasattr(Retriever, "search")


def test_stub_retriever_passes_contract():
    stub = StubContractRetriever(name="test-stub")
    assert_retriever_contract(stub)


def test_factory_supported_configs():
    assert "bm25" in SUPPORTED_CONFIGS
    assert "dense" in SUPPORTED_CONFIGS
    assert "fused" in SUPPORTED_CONFIGS
    assert "fused-rerank" in SUPPORTED_CONFIGS
    assert "fused-rerank-ft" in SUPPORTED_CONFIGS


def test_factory_unknown_config_raises():
    with pytest.raises(ValueError, match="Unknown retriever configuration"):
        create_retriever("unsupported-config")


def test_factory_dispatch_registered():
    name = "fused"
    try:
        register_retriever(name, lambda **kw: StubContractRetriever(name=name))
        retriever = create_retriever(name)
        assert retriever.name == name
        assert_retriever_contract(retriever)
    finally:
        unregister_retriever(name)
