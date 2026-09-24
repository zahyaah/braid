"""Leakage assertion tests (SPEC-finetune.md, Task 35).

The evaluation set is quarantined: no training question ID and no training
passage ID — gold *or* distractor (amendment 4) — may overlap it. These tests
prove the assertion aborts on both kinds of contamination, and that a
gold-only check would miss the distractor-only case.
"""

from __future__ import annotations

import pytest

from braid.eval.queryset.schema import LabeledQuery
from braid.finetune.pairs import (
    ExclusionSets,
    LeakageError,
    Pair,
    PassageRef,
    QuestionPassages,
    _row_passages,
    assert_no_leakage,
    build_pairs,
    build_training_questions,
    compute_exclusion_sets,
)
from braid.ingest.normalize import join_sentences, passage_id


def _pid(title: str, sentences: list[str]) -> str:
    text, _ = join_sentences(list(sentences))
    return passage_id(title, text)


def _passage_ids(row: dict) -> list[str]:
    return [
        _pid(title, sentences)
        for title, sentences in zip(
            row["context"]["title"], row["context"]["sentences"], strict=True
        )
    ]


# --- Assertion aborts on contamination -------------------------------------


def test_gold_passage_overlap_aborts():
    excl = ExclusionSets(frozenset(), frozenset({"p_gold"}))
    qp = QuestionPassages(
        question_id="q1",
        question="a question?",
        gold=(PassageRef("p_gold", "T", "gold text"),),
        distractors=(),
    )
    with pytest.raises(LeakageError):
        assert_no_leakage([qp], excl)


def test_question_id_overlap_aborts():
    excl = ExclusionSets(frozenset({"q1"}), frozenset())
    qp = QuestionPassages(
        question_id="q1",
        question="a question?",
        gold=(PassageRef("p_other", "T", "text"),),
        distractors=(),
    )
    with pytest.raises(LeakageError):
        assert_no_leakage([qp], excl)


def test_distractor_only_overlap_aborts():
    """The case a gold-only check misses: the shared passage is a distractor."""
    excl = ExclusionSets(frozenset(), frozenset({"p_dist"}))
    qp = QuestionPassages(
        question_id="q1",
        question="a question?",
        gold=(PassageRef("p_gold", "T", "gold text"),),
        distractors=(PassageRef("p_dist", "D", "distractor text"),),
    )
    # A gold-only check would not flag this question.
    assert "p_dist" not in {r.passage_id for r in qp.gold}
    with pytest.raises(LeakageError):
        assert_no_leakage([qp], excl)


def test_disjoint_training_passes():
    excl = ExclusionSets(frozenset({"eval_q"}), frozenset({"p_eval"}))
    qp = QuestionPassages(
        question_id="train_q",
        question="a question?",
        gold=(PassageRef("p_train_gold", "T", "text"),),
        distractors=(PassageRef("p_train_dist", "D", "text"),),
    )
    assert_no_leakage([qp], excl)  # does not raise


# --- Exclusion set covers distractors, not gold only (amendment 4) ---------


def test_exclusion_set_includes_distractors(fake_dataset):
    row = fake_dataset[0]  # q000
    pids = _passage_ids(row)
    assert len(pids) == 10

    query = LabeledQuery(
        query_id="mh-test-0",
        text="a multi-hop question?",
        category="multi-hop-relational",
        relevant={pids[0]: 1, pids[1]: 1},  # the two supporting passages
        origin="hotpotqa",
        source_question_id="q000",
    )

    exclusion = compute_exclusion_sets([query], {"q000": row})

    assert exclusion.question_ids == frozenset({"q000"})
    # Gold (2) + distractors (8) = all 10 passages of q000.
    assert exclusion.passage_ids == frozenset(pids)
    # The distractor passages are present even though they are not in `relevant`.
    assert set(pids[2:]) <= exclusion.passage_ids


# --- Pool construction records sizes and stays disjoint --------------------


def test_build_training_questions_records_sizes_and_is_disjoint(fake_dataset):
    row0 = fake_dataset[0]  # q000
    pids = _passage_ids(row0)

    query = LabeledQuery(
        query_id="mh-test-0",
        text="a multi-hop question?",
        category="multi-hop-relational",
        relevant={pids[0]: 1, pids[1]: 1},
        origin="hotpotqa",
        source_question_id="q000",
    )

    questions, report = build_training_questions(
        fake_dataset, [query], seed=42, num_questions=5
    )

    # q000 excluded: 1 question id + all 10 of its passages (gold + distractors).
    assert report.excluded_question_count == 1
    assert report.excluded_passage_count == 10
    assert report.remaining_pool_size == 11  # 12 fake questions minus q000
    assert report.num_train_questions == 5

    # Nothing selected may overlap the exclusion set.
    assert_no_leakage(questions, ExclusionSets(frozenset({"q000"}), frozenset(pids)))
    assert all(qp.question_id != "q000" for qp in questions)


# --- Pair construction -----------------------------------------------------


def test_build_pairs_labels_and_guids():
    qp = QuestionPassages(
        question_id="q1",
        question="who?",
        gold=(PassageRef("g1", "G", "gold text"),),
        distractors=(PassageRef("d1", "D", "dist text"), PassageRef("d2", "D2", "dist text 2")),
    )
    pairs = build_pairs([qp])

    assert isinstance(pairs[0], Pair)
    gold = [p for p in pairs if p.label == 1]
    neg = [p for p in pairs if p.label == 0]
    assert len(gold) == 1
    assert len(neg) == 2
    assert gold[0].guid == "q1:pos:0"
    assert {p.guid for p in neg} == {"q1:neg:0", "q1:neg:1"}
    # Passages carry the `title: text` display form the cross-encoder consumes.
    assert gold[0].passage == "G: gold text"


# --- The real pipeline path, against contaminated datasets -------------------
# Added after adversarial review: the tests above only exercised the assertion
# on hand-built objects with fake ids, while in the real pipeline the filter in
# `build_training_questions` removes overlapping questions first, so the
# assertion is never reached. These prove the *filter* (and its reporting)
# actually keeps contaminated questions out, end to end.

from tests.conftest import FakeDataset, make_row, paragraph  # noqa: E402


def _row(qid: str, paragraphs: list) -> dict:
    return make_row(
        question_id=qid,
        question=f"Question {qid}?",
        answer="a",
        paragraphs=paragraphs,
        supporting=[(paragraphs[0][0], 0), (paragraphs[1][0], 1)],
    )


def _eval_query(qid: str, row: dict) -> LabeledQuery:
    pids = _passage_ids(row)
    return LabeledQuery(
        query_id=f"mh-{qid}",
        text="eval question?",
        category="multi-hop-relational",
        relevant={pids[0]: 1, pids[1]: 1},
        origin="hotpotqa",
        source_question_id=qid,
    )


def _base_rows():
    eval_paras = [paragraph(i) for i in range(10)]
    clean_paras = [paragraph(100 + i) for i in range(10)]
    return eval_paras, clean_paras


def test_pipeline_drops_question_sharing_an_eval_gold_passage():
    eval_paras, clean_paras = _base_rows()
    eval_row = _row("eval", eval_paras)
    # Contaminated: its first paragraph IS the eval question's gold paragraph.
    dirty_row = _row("dirty_gold", [eval_paras[0], *clean_paras[1:]])
    clean_row = _row("clean", [paragraph(200 + i) for i in range(10)])
    ds = FakeDataset([eval_row, dirty_row, clean_row])

    queries = [_eval_query("eval", eval_row)]
    questions, report = build_training_questions(ds, queries, num_questions=5)

    assert [qp.question_id for qp in questions] == ["clean"]
    assert report.dropped_id_overlap == 1
    assert report.dropped_text_overlap == 0


def test_pipeline_drops_question_sharing_only_an_eval_distractor():
    """The case a gold-only exclusion would miss, through the real filter."""
    eval_paras, clean_paras = _base_rows()
    eval_row = _row("eval", eval_paras)
    # Contaminated only via a distractor: eval_paras[5] is not supporting.
    dirty_row = _row("dirty_dist", [*clean_paras[:9], eval_paras[5]])
    clean_row = _row("clean", [paragraph(200 + i) for i in range(10)])
    ds = FakeDataset([eval_row, dirty_row, clean_row])

    queries = [_eval_query("eval", eval_row)]
    questions, report = build_training_questions(ds, queries, num_questions=5)

    assert [qp.question_id for qp in questions] == ["clean"]
    assert report.dropped_id_overlap == 1


def test_pipeline_drops_same_text_under_a_different_id():
    """Same body text, different title => different passage_id, so an ID-only
    exclusion set lets it through. The text-level key must catch it."""
    eval_paras, clean_paras = _base_rows()
    eval_row = _row("eval", eval_paras)
    title, sentences = eval_paras[0]
    renamed = (f"{title} (renamed)", [s.upper() for s in sentences])  # case + title differ
    dirty_row = _row("dirty_text", [renamed, *clean_paras[1:]])
    clean_row = _row("clean", [paragraph(200 + i) for i in range(10)])
    ds = FakeDataset([eval_row, dirty_row, clean_row])

    # ID-only exclusion would not flag it:
    excl_ids_only = compute_exclusion_sets([_eval_query("eval", eval_row)], {"eval": eval_row})
    dirty_ids = {r.passage_id for r in _row_passages(dirty_row).gold}
    assert not (dirty_ids & excl_ids_only.passage_ids)

    queries = [_eval_query("eval", eval_row)]
    questions, report = build_training_questions(ds, queries, num_questions=5)
    assert [qp.question_id for qp in questions] == ["clean"]
    assert report.dropped_text_overlap == 1


def test_unresolvable_source_question_fails_closed():
    eval_paras, _ = _base_rows()
    eval_row = _row("eval", eval_paras)
    query = _eval_query("eval", eval_row)
    with pytest.raises(LeakageError, match="not in the dataset"):
        compute_exclusion_sets([query], {})  # source row missing => must not silently shrink


def test_relevant_passage_missing_from_corpus_fails_closed():
    eval_paras, _ = _base_rows()
    eval_row = _row("eval", eval_paras)
    query = _eval_query("eval", eval_row)
    with pytest.raises(LeakageError, match="not in the corpus"):
        compute_exclusion_sets([query], {"eval": eval_row}, corpus_texts={})


def test_assertion_catches_text_overlap_with_a_different_id():
    from braid.finetune.pairs import text_key

    keys = frozenset({text_key("Same body text.")})
    excl = ExclusionSets(frozenset(), frozenset({"p_eval"}), keys)
    qp = QuestionPassages(
        question_id="q1",
        question="q?",
        gold=(PassageRef("p_other", "T2", "SAME   body TEXT."),),
        distractors=(),
    )
    with pytest.raises(LeakageError, match="same normalized text"):
        assert_no_leakage([qp], excl)
