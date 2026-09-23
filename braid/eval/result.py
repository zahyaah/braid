"""Per-query scores and their per-category / pooled aggregates.

Per-query scores are retained because the bootstrap (bootstrap.py) resamples
them. A pooled-only report fails acceptance criterion 1 -- every aggregate
here is produced per category *and* pooled, never one or the other.
"""

from __future__ import annotations

from dataclasses import dataclass

from braid.eval.metrics import RankedHit, mrr, ndcg_at_k, recall_at_k
from braid.eval.queryset.schema import CATEGORIES, Category, LabeledQuery

METRICS = ("recall@5", "recall@10", "ndcg@10", "mrr")
POOLED = "pooled"


@dataclass(frozen=True)
class QueryScore:
    query_id: str
    category: Category
    values: dict[str, float]  # metric name -> value, keys are METRICS


def score_query(query: LabeledQuery, hits: list[RankedHit]) -> QueryScore:
    values = {
        "recall@5": recall_at_k(hits, query.relevant, 5),
        "recall@10": recall_at_k(hits, query.relevant, 10),
        "ndcg@10": ndcg_at_k(hits, query.relevant, 10),
        "mrr": mrr(hits, query.relevant),
    }
    return QueryScore(query_id=query.query_id, category=query.category, values=values)


@dataclass(frozen=True)
class EvalResult:
    """Every per-query score for one retriever configuration, plus aggregates
    computed per category and pooled. Never pooled-only (criterion 1).
    """

    config_name: str
    scores: tuple[QueryScore, ...]

    def by_category(self, category: str) -> tuple[QueryScore, ...]:
        if category == POOLED:
            return self.scores
        return tuple(s for s in self.scores if s.category == category)

    def aggregate(self, category: str, metric: str) -> float:
        """Mean of `metric` over the queries in `category` (or POOLED for all)."""
        subset = self.by_category(category)
        if not subset:
            return float("nan")
        return sum(s.values[metric] for s in subset) / len(subset)

    def table(self) -> dict[str, dict[str, float]]:
        """{category_or_pooled: {metric: mean}} for every category plus pooled."""
        groups = (*CATEGORIES, POOLED)
        return {
            group: {metric: self.aggregate(group, metric) for metric in METRICS}
            for group in groups
        }

    def per_query_values(self, category: str, metric: str) -> dict[str, float]:
        """query_id -> value, for the bootstrap to resample by query_id."""
        return {s.query_id: s.values[metric] for s in self.by_category(category)}


def evaluate(queries: list[LabeledQuery], retriever, k: int = 10) -> EvalResult:
    """Score `retriever` against every query. Runs end to end against a stub
    retriever before any real retriever exists (SPEC-eval.md acceptance).
    """
    scores = []
    for query in queries:
        hits = retriever.search(query.text, k)
        ranked = [RankedHit(h.passage_id, h.rank, h.score) for h in hits]
        scores.append(score_query(query, ranked))
    return EvalResult(config_name=retriever.name, scores=tuple(scores))
