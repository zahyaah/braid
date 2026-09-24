"""Tests for braid/query/params.py.

Asserts that all D5 parameters live in one constants module and exactly match
the canonical table in SPEC-query.md.
"""

from pathlib import Path

from braid.query import params


def test_d5_parameters_match_canonical_values():
    assert params.RRF_K == 60
    assert params.BM25_CANDIDATE_K == 100
    assert params.DENSE_CANDIDATE_K == 100
    assert params.GRAPH_CANDIDATE_K == 50
    assert params.FUSION_ARITY == 3
    assert params.FUSION_SOURCES == ("bm25", "dense", "graph")
    assert params.GRAPH_TRAVERSAL_DEPTH == 2
    assert params.GRAPH_FAN_OUT_CAP == 50
    assert params.GRAPH_HUB_DEGREE_THRESHOLD == 200
    assert params.ENTITY_LINKING_RULE == "exact_case_folded"
    assert params.RERANK_TOP_K == 50


def test_d5_parameters_match_spec_query_table():
    """Verify that SPEC-query.md mentions each parameter value so code and spec cannot drift."""
    spec_text = Path("SPEC-query.md").read_text(encoding="utf-8")
    assert "| RRF `k` | 60 |" in spec_text
    assert "| BM25 candidate K | 100 |" in spec_text
    assert "| Dense candidate K | 100 |" in spec_text
    assert "| Graph candidate K | 50 |" in spec_text
    assert "3-way: BM25 + dense + graph" in spec_text
    assert "| Graph traversal depth | 2 hops |" in spec_text
    assert "50 edges per node" in spec_text
    assert "degree > 200" in spec_text
    assert "Exact match on case-folded, normalized `Entity.name`" in spec_text
    assert "| Rerank top-K | 50 |" in spec_text
