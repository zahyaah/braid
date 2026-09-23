
from braid.eval.queryset.build_paraphrase import (
    build,
    sample_passages,
    used_passage_ids,
)
from braid.eval.queryset.schema import LabeledQuery
from braid.ingest.models import Passage


def passage(pid: str, title: str, text: str) -> Passage:
    return Passage(pid, title, text, ((0, len(text)),), "test")


def test_used_passage_ids_covers_exact_term_and_multihop_only():
    queries = [
        LabeledQuery("et-1", "t", "exact-term", {"p1": 1}, "agent-drafted"),
        LabeledQuery("mh-1", "t", "multi-hop-relational", {"p2": 1, "p3": 1}, "hotpotqa", "q1"),
        LabeledQuery("pp-1", "t", "paraphrase", {"p4": 1}, "agent-drafted"),
    ]
    assert used_passage_ids(queries) == {"p1", "p2", "p3"}


def test_sample_passages_excludes_used_ids():
    corpus = [passage(f"p{i}", f"T{i}", f"text {i}") for i in range(10)]
    sampled = sample_passages(corpus, exclude={"p0", "p1", "p2"}, limit=5, seed=1)
    assert {p.passage_id for p in sampled}.isdisjoint({"p0", "p1", "p2"})
    assert len(sampled) == 5


def test_sample_passages_is_deterministic_for_a_seed():
    corpus = [passage(f"p{i}", f"T{i}", f"text {i}") for i in range(10)]
    first = sample_passages(corpus, exclude=set(), limit=5, seed=3)
    second = sample_passages(corpus, exclude=set(), limit=5, seed=3)
    assert [p.passage_id for p in first] == [p.passage_id for p in second]


def test_build_produces_one_relevant_passage_per_query():
    passages = [passage("p1", "T", "Scott Derrickson directed a film.")]
    drafts = {"p1": "Who made a 2016 superhero movie about a neurosurgeon?"}
    queries, failures = build(passages, drafts)
    assert failures == {}
    assert len(queries) == 1
    assert queries[0].relevant == {"p1": 1}
    assert queries[0].category == "paraphrase"
    assert queries[0].origin == "agent-drafted"


def test_build_flags_a_draft_that_shares_content_words():
    passages = [passage("p1", "T", "Scott Derrickson directed a film.")]
    drafts = {"p1": "Which director named Scott Derrickson made this?"}
    queries, failures = build(passages, drafts)
    assert "p1" in failures
    assert "derrickson" in failures["p1"]


def test_build_skips_passages_with_no_draft():
    passages = [passage("p1", "T", "text"), passage("p2", "T2", "text2")]
    drafts = {"p1": "A description with no overlap at all."}
    queries, _ = build(passages, drafts)
    assert [q.query_id for q in queries] == ["pp-p1"]
