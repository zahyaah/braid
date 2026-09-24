"""Pinned query, fusion, and graph parameters (Decision D5).

These values are canonical per SPEC-query.md and SPEC.md (Decision D5).
They are fixed a priori and are never tuned against the evaluation set.
Tuning any of them, if it occurs, uses a validation slice carved from the D2 training sample.
A test in tests/query/test_params.py asserts that all values here match SPEC-query.md.
"""

from __future__ import annotations

# RRF smoothing constant k.
# Source: Cormack, Clarke & Buettcher (2009), "Reciprocal rank fusion outperforms
# Condorcet and individual machine learning methods", SIGIR '09.
# https://doi.org/10.1145/1571941.1572114
RRF_K: int = 60

# Candidate depths before fusion:
# BM25 and Dense are symmetric at 100 (10x reporting depth) so neither has a depth advantage.
BM25_CANDIDATE_K: int = 100
DENSE_CANDIDATE_K: int = 100
# Graph candidates are sparser and noisier; bounded to 50 to limit noise injection.
GRAPH_CANDIDATE_K: int = 50

# Fusion arity: 3-way (BM25 + dense + graph)
FUSION_ARITY: int = 3
FUSION_SOURCES: tuple[str, ...] = ("bm25", "dense", "graph")

# Graph traversal parameters:
# HotpotQA questions are 2-hop by construction.
GRAPH_TRAVERSAL_DEPTH: int = 2
GRAPH_FAN_OUT_CAP: int = 50
GRAPH_HUB_DEGREE_THRESHOLD: int = 200

# Entity linking rule:
# Exact match on case-folded, normalized Entity.name. No fuzzy matching.
ENTITY_LINKING_RULE: str = "exact_case_folded"

# Rerank depth:
# Top-K passages passed from fusion to cross-encoder reranking (pinned by D1).
RERANK_TOP_K: int = 50
