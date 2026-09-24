"""Tests for braid/eval/criterion3.py (Task 33).

Acceptance criteria:
- Definition stated and enforced: graph-win = fused top-10 with non-zero graph prov,
  absent from dense top-10
- A test asserts row count equals the number of multi-hop queries (exhaustive)
- Count below 5 is flagged; render_markdown includes the CAUTION alert
"""

from __future__ import annotations

import pytest

from braid.eval.criterion3 import (
    GRAPH_WIN_THRESHOLD,
    PassageVerdict,
    QueryVerdict,
    analyse_query,
    count_graph_wins,
    render_markdown,
    run_criterion3,
)
from braid.eval.queryset.schema import LabeledQuery
from braid.query.base import Hit

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _make_query(
    query_id: str = "mh-001",
    text: str = "multi-hop question",
    relevant: dict[str, int] | None = None,
) -> LabeledQuery:
    return LabeledQuery(
        query_id=query_id,
        text=text,
        category="multi-hop-relational",
        relevant=relevant or {"gold1": 1, "gold2": 1},
        origin="hotpotqa",
    )


def _make_non_multihop_query(query_id: str = "et-001") -> LabeledQuery:
    return LabeledQuery(
        query_id=query_id,
        text="exact term question",
        category="exact-term",
        relevant={"p1": 1},
        origin="hotpotqa",
    )


def _hit(passage_id: str, rank: int, graph_prov: float = 0.0) -> Hit:
    return Hit(
        passage_id=passage_id,
        score=1.0 / rank,
        rank=rank,
        provenance={"bm25": 0.3, "dense": 0.5, "graph": graph_prov},
    )


class _ListRetriever:
    """Mock retriever returning a fixed list of Hits."""

    def __init__(self, name: str, hits: list[Hit]) -> None:
        self.name = name
        self._hits = hits

    def search(self, query: str, k: int = 10) -> list[Hit]:
        return self._hits[:k]


# ---------------------------------------------------------------------------
# Unit: analyse_query
# ---------------------------------------------------------------------------


def test_analyse_query_graph_win_detected():
    """gold1 is in fused top-10 with graph prov > 0 and absent from dense top-10."""
    query = _make_query(relevant={"gold1": 1, "gold2": 1})
    dense_hits = [_hit("gold2", 1)]  # gold1 absent from dense
    fused_hits = [
        _hit("gold1", 1, graph_prov=0.15),  # graph-win candidate
        _hit("gold2", 2, graph_prov=0.0),
    ]

    verdict = analyse_query(query, dense_hits, fused_hits)

    assert verdict.query_id == "mh-001"
    assert len(verdict.passage_verdicts) == 2

    gold1_v = next(v for v in verdict.passage_verdicts if v.passage_id == "gold1")
    gold2_v = next(v for v in verdict.passage_verdicts if v.passage_id == "gold2")

    assert gold1_v.graph_win is True
    assert gold1_v.dense_rank is None
    assert gold1_v.fused_rank == 1
    assert gold1_v.graph_provenance == pytest.approx(0.15)

    assert gold2_v.graph_win is False  # graph_prov is 0.0
    assert verdict.any_graph_win is True


def test_analyse_query_no_win_when_dense_also_has_passage():
    """If gold1 is in both dense and fused top-10 (with graph prov), it is NOT a graph-win."""
    query = _make_query(relevant={"gold1": 1})
    dense_hits = [_hit("gold1", 1)]
    fused_hits = [_hit("gold1", 1, graph_prov=0.2)]

    verdict = analyse_query(query, dense_hits, fused_hits)
    v = verdict.passage_verdicts[0]
    assert v.graph_win is False  # dense also surfaced it


def test_analyse_query_no_win_when_zero_graph_provenance():
    """Fused hit with graph_prov == 0 is not a graph-win even if absent from dense."""
    query = _make_query(relevant={"gold1": 1})
    dense_hits = []  # gold1 absent from dense
    fused_hits = [_hit("gold1", 1, graph_prov=0.0)]  # zero graph contribution

    verdict = analyse_query(query, dense_hits, fused_hits)
    assert verdict.passage_verdicts[0].graph_win is False


def test_analyse_query_neither_when_not_in_either():
    """Gold passage absent from both dense and fused → neither."""
    query = _make_query(relevant={"gold1": 1})
    verdict = analyse_query(query, [], [])

    v = verdict.passage_verdicts[0]
    assert v.dense_rank is None
    assert v.fused_rank is None
    assert v.graph_win is False


# ---------------------------------------------------------------------------
# Unit: run_criterion3
# ---------------------------------------------------------------------------


def test_run_criterion3_covers_all_multi_hop_queries():
    """run_criterion3 returns exactly one verdict per multi-hop query (no subset)."""
    multi_hop_queries = [_make_query(f"mh-{i:03d}", f"q{i}") for i in range(5)]
    non_mh = [_make_non_multihop_query("et-001")]
    all_queries = non_mh + multi_hop_queries

    dense = _ListRetriever("dense", [])
    fused = _ListRetriever("fused", [])

    verdicts = run_criterion3(all_queries, dense, fused)
    assert len(verdicts) == 5, (
        f"Expected exactly 5 multi-hop verdicts, got {len(verdicts)}"
    )
    verdict_ids = {v.query_id for v in verdicts}
    assert verdict_ids == {f"mh-{i:03d}" for i in range(5)}


def test_run_criterion3_row_count_equals_multihop_query_count():
    """The exhaustive guarantee: row count == multi-hop query count, always."""
    from braid.eval.queryset.schema import QUERIES_FILE, QUERYSET_DIR, read_queries

    all_queries = read_queries(QUERYSET_DIR / QUERIES_FILE)
    multi_hop = [q for q in all_queries if q.category == "multi-hop-relational"]

    # Use empty-result retrievers so the test has no infrastructure dependency
    dense = _ListRetriever("dense", [])
    fused = _ListRetriever("fused", [])

    verdicts = run_criterion3(all_queries, dense, fused)
    assert len(verdicts) == len(multi_hop), (
        f"Table has {len(verdicts)} rows but queryset has {len(multi_hop)} multi-hop queries"
    )


# ---------------------------------------------------------------------------
# Unit: count_graph_wins
# ---------------------------------------------------------------------------


def test_count_graph_wins_zero():
    verdicts = [
        QueryVerdict(
            query_id="q1",
            text="t",
            gold_passage_ids=["p"],
            passage_verdicts=[
                PassageVerdict("p", True, 1, 1, 0.0, False)
            ],
        )
    ]
    assert count_graph_wins(verdicts) == 0


def test_count_graph_wins_counts_queries_not_passages():
    """Each query counts once regardless of how many passages win."""
    verdicts = [
        QueryVerdict(
            query_id="q1",
            text="t",
            gold_passage_ids=["p1", "p2"],
            passage_verdicts=[
                PassageVerdict("p1", True, None, 1, 0.2, True),
                PassageVerdict("p2", True, None, 2, 0.3, True),  # same query
            ],
        ),
        QueryVerdict(
            query_id="q2",
            text="t2",
            gold_passage_ids=["p3"],
            passage_verdicts=[
                PassageVerdict("p3", True, 1, 1, 0.0, False)
            ],
        ),
    ]
    assert count_graph_wins(verdicts) == 1  # only q1 has a win


# ---------------------------------------------------------------------------
# Unit: render_markdown
# ---------------------------------------------------------------------------


def test_render_markdown_contains_definition():
    verdicts = [
        QueryVerdict(
            query_id="mh-001",
            text="who did what?",
            gold_passage_ids=["g1"],
            passage_verdicts=[
                PassageVerdict("g1", True, None, 1, 0.1, True)
            ],
        )
    ]
    md = render_markdown(verdicts)
    assert "graph-win" in md
    assert "non-zero graph provenance" in md
    assert "absent from the `dense` top-10" in md


def test_render_markdown_row_count_matches():
    """Markdown table has one row per PassageVerdict, not per query."""
    verdicts = [
        QueryVerdict(
            query_id="mh-001",
            text="q1",
            gold_passage_ids=["g1", "g2"],
            passage_verdicts=[
                PassageVerdict("g1", True, None, 1, 0.1, True),
                PassageVerdict("g2", True, 2, 2, 0.0, False),
            ],
        )
    ]
    md = render_markdown(verdicts)
    # Two data rows (one per passage), plus the two header rows
    table_rows = [row for row in md.splitlines() if row.startswith("| mh-001")]
    assert len(table_rows) == 2


def test_render_markdown_low_count_caution():
    """When graph-win count < GRAPH_WIN_THRESHOLD, a CAUTION alert is included."""
    assert GRAPH_WIN_THRESHOLD == 5  # guard: test matches spec constant

    verdicts = [
        QueryVerdict(
            query_id=f"mh-{i:03d}",
            text=f"q{i}",
            gold_passage_ids=["g"],
            passage_verdicts=[
                PassageVerdict("g", True, 1, 1, 0.0, False)  # no wins
            ],
        )
        for i in range(10)
    ]
    md = render_markdown(verdicts)
    assert "CAUTION" in md


def test_render_markdown_no_caution_when_above_threshold():
    """No CAUTION when graph-win count >= GRAPH_WIN_THRESHOLD."""
    verdicts = [
        QueryVerdict(
            query_id=f"mh-{i:03d}",
            text=f"q{i}",
            gold_passage_ids=["g"],
            passage_verdicts=[
                PassageVerdict("g", True, None, 1, 0.1, True)  # all win
            ],
        )
        for i in range(GRAPH_WIN_THRESHOLD)
    ]
    md = render_markdown(verdicts)
    assert "CAUTION" not in md


def test_render_markdown_denominator_visible():
    """The denominator (number of multi-hop queries) must appear in the summary."""
    n = 7
    verdicts = [
        QueryVerdict(
            query_id=f"mh-{i:03d}",
            text=f"q{i}",
            gold_passage_ids=["g"],
            passage_verdicts=[PassageVerdict("g", True, 1, 1, 0.0, False)],
        )
        for i in range(n)
    ]
    md = render_markdown(verdicts)
    assert str(n) in md  # denominator visible
