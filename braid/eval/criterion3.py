"""Criterion-3 exhaustive count (SPEC-eval.md, decision D3).

Definition (stated here per acceptance requirement):
    A graph-win for a multi-hop evaluation query is a gold passage that:
      1. appears in the ``fused`` top-10 with non-zero graph provenance, AND
      2. is absent from the ``dense`` top-10 (i.e., dense rank > 10 or not returned).

The count covers **every** multi-hop query in the queryset — no subset selection.
A count below 5 is reported as the finding it is, alongside extraction-yield figures.

Outputs:
    - A structured list of :class:`QueryVerdict` objects (one per multi-hop query).
    - :func:`render_markdown` converts these to the ``reports/graph-vs-vector.md`` table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from braid.eval.queryset.schema import LabeledQuery
from braid.query.base import Hit

TOP_K = 10
GRAPH_WIN_THRESHOLD = 5  # below this, the finding is flagged prominently


@dataclass(frozen=True)
class PassageVerdict:
    """Per-passage verdict for a single multi-hop query."""

    passage_id: str
    is_gold: bool
    dense_rank: int | None  # None → not in dense top-10
    fused_rank: int | None  # None → not in fused top-10
    graph_provenance: float  # 0.0 if not in fused results or no graph provenance
    graph_win: bool  # True iff this passage is a graph-sourced addition over dense


@dataclass
class QueryVerdict:
    """Per-query verdict for criterion-3 analysis."""

    query_id: str
    text: str
    gold_passage_ids: list[str]
    passage_verdicts: list[PassageVerdict]

    @property
    def any_graph_win(self) -> bool:
        """True if at least one gold passage is a graph-win for this query."""
        return any(v.graph_win for v in self.passage_verdicts)


def _rank_map(hits: list[Hit]) -> dict[str, int]:
    """Map passage_id → rank (1-indexed) for the given hit list."""
    return {h.passage_id: h.rank for h in hits}


def _provenance_graph(hit: Hit) -> float:
    """Extract the graph provenance contribution from a hit's provenance dict."""
    return float(hit.provenance.get("graph", 0.0))


def analyse_query(
    query: LabeledQuery,
    dense_hits: list[Hit],
    fused_hits: list[Hit],
) -> QueryVerdict:
    """Produce a :class:`QueryVerdict` for a single multi-hop query.

    Parameters
    ----------
    query:
        The labeled evaluation query (must be multi-hop-relational).
    dense_hits:
        Top-k results from the dense-only retriever.
    fused_hits:
        Top-k results from the fused (or fused-rerank) retriever,
        with provenance dicts that include a ``"graph"`` key.

    Returns
    -------
    QueryVerdict
        One row of the criterion-3 report.
    """
    gold_ids = set(query.relevant.keys())
    dense_ranks = _rank_map(dense_hits)
    fused_ranks = _rank_map(fused_hits)
    fused_prov: dict[str, float] = {h.passage_id: _provenance_graph(h) for h in fused_hits}

    # Analyse every gold passage
    verdicts: list[PassageVerdict] = []
    for pid in sorted(gold_ids):
        d_rank = dense_ranks.get(pid)
        f_rank = fused_ranks.get(pid)
        g_prov = fused_prov.get(pid, 0.0)

        in_fused_with_graph = f_rank is not None and g_prov > 0.0
        not_in_dense = d_rank is None

        verdicts.append(
            PassageVerdict(
                passage_id=pid,
                is_gold=True,
                dense_rank=d_rank,
                fused_rank=f_rank,
                graph_provenance=g_prov,
                graph_win=in_fused_with_graph and not_in_dense,
            )
        )

    return QueryVerdict(
        query_id=query.query_id,
        text=query.text,
        gold_passage_ids=sorted(gold_ids),
        passage_verdicts=verdicts,
    )


def run_criterion3(
    queries: list[LabeledQuery],
    dense_retriever: Any,
    fused_retriever: Any,
    k: int = TOP_K,
) -> list[QueryVerdict]:
    """Run criterion-3 analysis over *every* multi-hop query.

    Parameters
    ----------
    queries:
        The full labeled queryset; non-multi-hop queries are filtered out here.
    dense_retriever:
        A retriever satisfying the Retriever protocol (``search(text, k) → list[Hit]``).
    fused_retriever:
        A fused retriever whose hits carry a ``"graph"`` key in their provenance dicts.
    k:
        Retrieval depth (default 10, per acceptance criterion).

    Returns
    -------
    list[QueryVerdict]
        One verdict per multi-hop query, in queryset order.
        The list length equals the number of multi-hop queries — never a subset.
    """
    multi_hop = [q for q in queries if q.category == "multi-hop-relational"]
    verdicts: list[QueryVerdict] = []
    for query in multi_hop:
        dense_hits = dense_retriever.search(query.text, k)
        fused_hits = fused_retriever.search(query.text, k)
        verdicts.append(analyse_query(query, dense_hits, fused_hits))
    return verdicts


def count_graph_wins(verdicts: list[QueryVerdict]) -> int:
    """Count queries where at least one gold passage is a graph-win."""
    return sum(1 for v in verdicts if v.any_graph_win)


def render_markdown(verdicts: list[QueryVerdict]) -> str:
    """Render ``reports/graph-vs-vector.md`` content.

    The table lists every multi-hop query with:
    - Query ID, query text
    - Gold passage IDs
    - Dense rank (or "—" if absent)
    - Fused rank (or "—" if absent)
    - Graph provenance
    - Verdict (graph-win / dense-wins / neither)

    A summary header states the definition, denominator, and count.
    A count below GRAPH_WIN_THRESHOLD is flagged prominently.
    """
    n_queries = len(verdicts)
    n_wins = count_graph_wins(verdicts)
    low_count_flag = n_wins < GRAPH_WIN_THRESHOLD

    lines: list[str] = [
        "# Criterion-3: Graph-sourced additions over dense retrieval",
        "",
        "## Definition",
        "",
        (
            "A **graph-win** for a multi-hop evaluation query is a gold passage that "
            "(1) appears in the `fused` top-10 with **non-zero graph provenance**, and "
            "(2) is **absent from the `dense` top-10** (dense rank > 10 or not returned)."
        ),
        "",
        "The count covers **every** multi-hop query in the queryset — no subset selection.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Multi-hop queries (denominator) | {n_queries} |",
        f"| Queries with ≥ 1 graph-win | {n_wins} |",
        f"| Graph-win rate | {n_wins / n_queries:.1%} |",
        "",
    ]

    if low_count_flag:
        lines += [
            "> [!CAUTION]",
            f"> Graph-win count is **{n_wins}**, which is below the reporting threshold of "
            f"{GRAPH_WIN_THRESHOLD}. This is the finding: graph traversal contributes "
            f"fewer unique gold passages over dense retrieval than expected for this queryset. "
            f"See extraction-yield figures below.",
            "",
        ]

    lines += [
        "## Per-query verdict table",
        "",
        "| Query ID | Query text | Gold passage ID | Dense rank | Fused rank "
        "| Graph prov. | Verdict |",
        "|---|---|---|---|---|---|---|",
    ]

    for verdict in verdicts:
        qid = verdict.query_id
        text = verdict.text.replace("|", "\\|")
        for pv in verdict.passage_verdicts:
            d_rank = str(pv.dense_rank) if pv.dense_rank is not None else "—"
            f_rank = str(pv.fused_rank) if pv.fused_rank is not None else "—"
            g_prov = f"{pv.graph_provenance:.4f}"
            if pv.graph_win:
                verdict_str = "**graph-win**"
            elif pv.dense_rank is not None and (
                pv.fused_rank is None or pv.dense_rank < (pv.fused_rank or 999)
            ):
                verdict_str = "dense-wins"
            elif pv.fused_rank is not None and pv.dense_rank is None:
                verdict_str = "fused-only (no graph)"
            else:
                verdict_str = "neither"
            lines.append(
                f"| {qid} | {text} | {pv.passage_id} | {d_rank} | {f_rank} "
                f"| {g_prov} | {verdict_str} |"
            )

    lines += [
        "",
        "## Extraction-yield note",
        "",
        "Graph provenance of 0.0 in a fused result means the passage reached the top-10 "
        "exclusively through BM25 or dense paths; graph traversal contributed no candidates "
        "for that passage. A passage absent from fused results was not retrieved by any path.",
        "",
    ]

    return "\n".join(lines) + "\n"
