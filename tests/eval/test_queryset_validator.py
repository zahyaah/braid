"""The validator is only worth having if it fails on broken data, so every check
here is exercised against a fixture that deliberately breaks it.
"""

from __future__ import annotations

import pytest

from braid.eval.queryset.schema import (
    MANIFEST_FILE,
    QUERIES_FILE,
    REVIEW_FILE,
    LabeledQuery,
    OverlapOverride,
    QuerySetManifest,
    ReviewRecord,
    write_queries,
    write_reviews,
)
from braid.eval.queryset.validate import validate
from braid.ingest.freeze import corpus_hash, freeze
from braid.ingest.manifest import Manifest
from braid.ingest.models import Passage, write_jsonl

GOLD_TEXT = "Scott Derrickson is an American film director and screenwriter."
OTHER_TEXT = "Ed Wood is a 1994 biographical film about a cult movie maker."


@pytest.fixture
def workspace(tmp_path):
    passages = [
        Passage("p1", "Scott Derrickson", GOLD_TEXT, ((0, len(GOLD_TEXT)),), "test"),
        Passage("p2", "Ed Wood", OTHER_TEXT, ((0, len(OTHER_TEXT)),), "test"),
    ]
    corpus_path = tmp_path / "corpus.jsonl"
    write_jsonl(corpus_path, passages)

    corpus_manifest_path = tmp_path / "manifest.json"
    Manifest(
        dataset="d", config="c", split="validation", datasets_version="0", seed=1,
        target_passages=2, questions_sampled=1, questions_out=1,
        passages_before_dedupe=2, passages_after_dedupe=2, dedupe={}, remap={},
    ).write(corpus_manifest_path)
    freeze(corpus_manifest_path, passages)

    queryset_dir = tmp_path / "queryset"
    queryset_dir.mkdir()
    QuerySetManifest(corpus_hash=corpus_hash(passages)).write(queryset_dir / MANIFEST_FILE)
    return {
        "dir": queryset_dir,
        "corpus": corpus_path,
        "corpus_manifest": corpus_manifest_path,
        "hash": corpus_hash(passages),
    }


def run(workspace) -> list[str]:
    return validate(workspace["dir"], workspace["corpus"], workspace["corpus_manifest"])


def good_paraphrase() -> LabeledQuery:
    return LabeledQuery(
        query_id="pp-1",
        text="Who helmed a 2016 superhero movie about a surgeon?",
        category="paraphrase",
        relevant={"p1": 1},
        origin="agent-drafted",
    )


def good_review(query: LabeledQuery, **overrides) -> ReviewRecord:
    fields = {
        "query_id": query.query_id,
        "source_passage_id": "p1",
        "draft_text": query.text,
        "final_text": query.text,
        "reviewer": "kzaydahmed",
        "reviewed_at": "2026-09-23T00:00:00+00:00",
        "disposition": "accepted",
        "reason": "",
    }
    fields.update(overrides)
    return ReviewRecord(**fields)


def good_multihop() -> LabeledQuery:
    return LabeledQuery(
        query_id="mh-1",
        text="Which director worked on a film about Ed Wood?",
        category="multi-hop-relational",
        relevant={"p1": 1, "p2": 1},
        origin="hotpotqa",
        source_question_id="q1",
    )


def write(workspace, queries, reviews=()):
    write_queries(workspace["dir"] / QUERIES_FILE, list(queries))
    write_reviews(workspace["dir"] / REVIEW_FILE, list(reviews))


def test_a_well_formed_set_validates(workspace):
    query = good_paraphrase()
    write(workspace, [query, good_multihop()], [good_review(query)])
    assert run(workspace) == []


def test_unknown_category_fails(workspace):
    query = LabeledQuery("x-1", "text", "typo-category", {"p1": 1}, "agent-drafted")
    write(workspace, [query])
    assert any("unknown category" in problem for problem in run(workspace))


def test_unresolvable_passage_id_fails(workspace):
    query = LabeledQuery("et-1", "term", "exact-term", {"ghost": 1}, "agent-drafted")
    write(workspace, [query], [good_review(query)])
    assert any("is not in the corpus" in problem for problem in run(workspace))


def test_graded_gain_fails_because_relevance_is_binary(workspace):
    query = LabeledQuery("et-1", "term", "exact-term", {"p1": 2}, "agent-drafted")
    write(workspace, [query], [good_review(query)])
    assert any("relevance is binary" in problem for problem in run(workspace))


def test_unreviewed_drafted_query_fails(workspace):
    write(workspace, [good_paraphrase()], [])
    assert any("no review record" in problem for problem in run(workspace))


def test_paraphrase_sharing_content_words_fails_without_an_override(workspace):
    query = LabeledQuery(
        query_id="pp-2",
        text="Which American film director wrote screenplays?",
        category="paraphrase",
        relevant={"p1": 1},
        origin="agent-drafted",
    )
    write(workspace, [query], [good_review(query)])
    problems = run(workspace)
    assert any("carries no reviewer override" in problem for problem in problems)


def test_paraphrase_overlap_passes_with_a_matching_override(workspace):
    query = LabeledQuery(
        query_id="pp-2",
        text="Which American film director wrote screenplays?",
        category="paraphrase",
        relevant={"p1": 1},
        origin="agent-drafted",
    )
    override = OverlapOverride(
        reviewer="kzaydahmed",
        overridden_at="2026-09-23T00:00:00+00:00",
        reason="no accurate synonym for the role term",
        shared_terms=("american", "director", "film"),
    )
    write(workspace, [query], [good_review(query, overlap_override=override)])
    assert run(workspace) == []


def test_override_that_does_not_match_the_flagged_terms_fails(workspace):
    query = LabeledQuery(
        query_id="pp-2",
        text="Which American film director wrote screenplays?",
        category="paraphrase",
        relevant={"p1": 1},
        origin="agent-drafted",
    )
    override = OverlapOverride("k", "2026-09-23T00:00:00+00:00", "why", ("director",))
    write(workspace, [query], [good_review(query, overlap_override=override)])
    assert any("but the check flags" in problem for problem in run(workspace))


def test_stale_corpus_hash_fails(workspace):
    QuerySetManifest(corpus_hash="deadbeef").write(workspace["dir"] / MANIFEST_FILE)
    query = good_paraphrase()
    write(workspace, [query], [good_review(query)])
    assert any("corpus_hash mismatch" in problem for problem in run(workspace))


def test_unfrozen_corpus_fails(workspace, tmp_path):
    manifest = Manifest.read(workspace["corpus_manifest"])
    manifest.frozen = False
    manifest.write(workspace["corpus_manifest"])
    query = good_paraphrase()
    write(workspace, [query], [good_review(query)])
    assert any("corpus is not frozen" in problem for problem in run(workspace))


def test_multihop_with_one_supporting_passage_fails(workspace):
    query = LabeledQuery("mh-2", "q?", "multi-hop-relational", {"p1": 1}, "hotpotqa", "q2")
    write(workspace, [query])
    assert any("is not multi-hop" in problem for problem in run(workspace))


def test_exact_term_with_two_relevant_passages_fails(workspace):
    query = LabeledQuery("et-2", "term", "exact-term", {"p1": 1, "p2": 1}, "agent-drafted")
    write(workspace, [query], [good_review(query)])
    assert any("expected exactly 1" in problem for problem in run(workspace))


def test_edited_review_without_a_reason_fails(workspace):
    query = good_paraphrase()
    write(workspace, [query], [good_review(query, disposition="edited", reason="  ")])
    assert any("requires a reason" in problem for problem in run(workspace))


def test_review_final_text_must_match_the_shipped_query(workspace):
    query = good_paraphrase()
    write(workspace, [query], [good_review(query, final_text="something else")])
    assert any("does not match the shipped query text" in problem for problem in run(workspace))


def test_duplicate_query_ids_fail(workspace):
    query = good_paraphrase()
    write(workspace, [query, query], [good_review(query)])
    assert any("duplicate query_id" in problem for problem in run(workspace))


def test_category_balance_is_checked_once_the_size_is_locked(workspace):
    manifest = QuerySetManifest.read(workspace["dir"] / MANIFEST_FILE)
    manifest.locked_size = 180
    manifest.per_category_target = 60
    manifest.write(workspace["dir"] / MANIFEST_FILE)
    query = good_paraphrase()
    write(workspace, [query], [good_review(query)])
    problems = run(workspace)
    assert any("the locked size requires 60" in problem for problem in problems)
