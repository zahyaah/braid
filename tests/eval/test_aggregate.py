from braid.eval.metrics import RankedHit
from braid.eval.queryset.schema import LabeledQuery
from braid.eval.result import POOLED, evaluate, score_query


class StubRetriever:
    """Retriever that always returns hits in a fixed order per query text."""

    name = "stub"

    def __init__(self, responses: dict[str, list[str]]):
        self._responses = responses

    def search(self, query: str, k: int):
        ids = self._responses.get(query, [])[:k]
        return [RankedHit(pid, rank=i + 1, score=1.0 / (i + 1)) for i, pid in enumerate(ids)]


def make_query(qid: str, category: str, relevant: dict[str, int], origin="agent-drafted"):
    return LabeledQuery(qid, f"text {qid}", category, relevant, origin)


def test_score_query_matches_metrics_module():
    query = make_query("q1", "exact-term", {"a": 1})
    hits = [RankedHit("b", 1), RankedHit("a", 2)]
    score = score_query(query, hits)
    assert score.query_id == "q1"
    assert score.category == "exact-term"
    assert score.values["mrr"] == 0.5


def test_per_query_scores_are_retained_not_just_aggregated():
    queries = [
        make_query("q1", "exact-term", {"a": 1}),
        make_query("q2", "paraphrase", {"b": 1}),
    ]
    retriever = StubRetriever({"text q1": ["a"], "text q2": ["x", "b"]})
    result = evaluate(queries, retriever, k=10)
    assert len(result.scores) == 2
    assert {s.query_id for s in result.scores} == {"q1", "q2"}


def test_aggregate_is_produced_per_category_and_pooled_not_pooled_only():
    queries = [
        make_query("q1", "exact-term", {"a": 1}),
        make_query("q2", "exact-term", {"a": 1}),
        make_query("q3", "paraphrase", {"b": 1}),
    ]
    # q1 hits first try (mrr=1), q2 never found (mrr=0), q3 hits first try (mrr=1)
    retriever = StubRetriever({"text q1": ["a"], "text q2": ["z"], "text q3": ["b"]})
    result = evaluate(queries, retriever, k=10)

    table = result.table()
    assert set(table) == {"exact-term", "paraphrase", "multi-hop-relational", POOLED}
    assert table["exact-term"]["mrr"] == 0.5  # (1 + 0) / 2
    assert table["paraphrase"]["mrr"] == 1.0
    multihop_mrr = table["multi-hop-relational"]["mrr"]
    assert multihop_mrr != multihop_mrr  # NaN: no multi-hop queries were scored
    # pooled averages across all 3 queries: (1 + 0 + 1) / 3
    assert abs(table[POOLED]["mrr"] - (2 / 3)) < 1e-9


def test_per_query_values_keys_by_query_id_for_the_bootstrap():
    queries = [make_query("q1", "exact-term", {"a": 1}), make_query("q2", "exact-term", {"a": 1})]
    retriever = StubRetriever({"text q1": ["a"], "text q2": ["a"]})
    result = evaluate(queries, retriever, k=10)
    values = result.per_query_values("exact-term", "mrr")
    assert values == {"q1": 1.0, "q2": 1.0}


def test_empty_category_aggregate_is_nan_not_a_crash():
    queries = [make_query("q1", "exact-term", {"a": 1})]
    retriever = StubRetriever({"text q1": ["a"]})
    result = evaluate(queries, retriever, k=10)
    value = result.aggregate("paraphrase", "mrr")
    assert value != value  # NaN
