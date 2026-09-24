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
        for title, sentences in zip(row["context"]["title"], row["context"]["sentences"], strict=True)
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
