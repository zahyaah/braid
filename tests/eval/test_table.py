from braid.eval.metrics import RankedHit
from braid.eval.queryset.schema import LabeledQuery
from braid.eval.result import METRICS, POOLED, evaluate
from braid.eval.table import (
    GROUPS,
    criterion2_comparisons,
    pick_baseline,
    render_markdown,
)


class StubRetriever:
    name = "stub"

    def __init__(self, name: str, hit_rate: float):
        self.name = name
        self._hit_rate = hit_rate

    def search(self, query: str, k: int):
        # Deterministic: "hits" the gold passage iff a hash-derived value is
        # below hit_rate, otherwise returns an unrelated passage.
        import hashlib

        digest = int(hashlib.sha256(query.encode()).hexdigest(), 16)
        hit = (digest % 100) / 100 < self._hit_rate
        pid = "gold" if hit else "distractor"
        return [RankedHit(pid, rank=1, score=1.0)]


def make_query(qid: str, category: str) -> LabeledQuery:
    return LabeledQuery(qid, f"query {qid}", category, {"gold": 1}, "agent-drafted")


def make_queries(n_per_category: int = 8) -> list[LabeledQuery]:
    out = []
    for category in ("exact-term", "paraphrase", "multi-hop-relational"):
        for i in range(n_per_category):
            out.append(make_query(f"{category[:2]}{i}", category))
    return out


def test_table_covers_every_category_plus_pooled_for_every_config():
    queries = make_queries()
    results = {
        "bm25": evaluate(queries, StubRetriever("bm25", 0.9)),
        "dense": evaluate(queries, StubRetriever("dense", 0.2)),
        "fused": evaluate(queries, StubRetriever("fused", 0.5)),
        "fused-rerank": evaluate(queries, StubRetriever("fused-rerank", 0.95)),
    }
    for result in results.values():
        table = result.table()
        assert set(table) == set(GROUPS)
        for group in GROUPS:
            assert set(table[group]) == set(METRICS)


def test_pick_baseline_is_descriptive_not_post_hoc():
    queries = make_queries()
    results = {
        "bm25": evaluate(queries, StubRetriever("bm25", 0.9)),  # strong on exact-term-ish hash
        "dense": evaluate(queries, StubRetriever("dense", 0.1)),
        "fused": evaluate(queries, StubRetriever("fused", 0.5)),
        "fused-rerank": evaluate(queries, StubRetriever("fused-rerank", 0.95)),
    }
    for category in GROUPS:
        winner = pick_baseline(results, category, "mrr")
        assert winner in ("bm25", "dense")
        bm25_val = results["bm25"].aggregate(category, "mrr")
        dense_val = results["dense"].aggregate(category, "mrr")
        expected = "bm25" if bm25_val >= dense_val else "dense"
        assert winner == expected


def test_criterion2_comparisons_cover_every_category_and_pooled_and_every_metric():
    queries = make_queries()
    results = {
        "bm25": evaluate(queries, StubRetriever("bm25", 0.5)),
        "dense": evaluate(queries, StubRetriever("dense", 0.5)),
        "fused": evaluate(queries, StubRetriever("fused", 0.6)),
        "fused-rerank": evaluate(queries, StubRetriever("fused-rerank", 0.9)),
    }
    comparisons = criterion2_comparisons(results, resamples=200, seed=1)
    seen = {(c.category, c.metric) for c in comparisons}
    expected = {(g, m) for g in GROUPS for m in METRICS}
    assert seen == expected
    for c in comparisons:
        assert isinstance(c.comparison.excludes_zero, bool)


def test_render_markdown_includes_excludes_zero_and_baseline_columns():
    queries = make_queries()
    results = {
        "bm25": evaluate(queries, StubRetriever("bm25", 0.5)),
        "dense": evaluate(queries, StubRetriever("dense", 0.5)),
        "fused": evaluate(queries, StubRetriever("fused", 0.6)),
        "fused-rerank": evaluate(queries, StubRetriever("fused-rerank", 0.9)),
    }
    comparisons = criterion2_comparisons(results, resamples=100, seed=1)
    markdown = render_markdown(results, comparisons)
    assert "Excludes zero" in markdown
    assert "Baseline" in markdown
    assert POOLED in markdown
    for category in ("exact-term", "paraphrase", "multi-hop-relational"):
        assert category in markdown
