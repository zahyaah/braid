import pytest

from braid.ingest.loader import sample
from tests.conftest import FakeDataset, make_row, paragraph


def test_sampling_is_deterministic_for_a_seed(fake_dataset):
    first_passages, first_questions, _ = sample(fake_dataset, seed=7, target_passages=40)
    second_passages, second_questions, _ = sample(fake_dataset, seed=7, target_passages=40)
    assert [p.passage_id for p in first_passages] == [p.passage_id for p in second_passages]
    assert [q.question_id for q in first_questions] == [q.question_id for q in second_questions]


def test_different_seeds_select_different_questions(fake_dataset):
    _, first, _ = sample(fake_dataset, seed=1, target_passages=30)
    _, second, _ = sample(fake_dataset, seed=2, target_passages=30)
    assert [q.question_id for q in first] != [q.question_id for q in second]


def test_every_sampled_question_pulls_all_ten_of_its_paragraphs(fake_dataset):
    passages, questions, _ = sample(fake_dataset, seed=3, target_passages=25)
    # Each fake question owns 10 distinct paragraphs, so the corpus grows in
    # blocks of 10: gold and distractors both enter.
    assert len(passages) == 10 * len(questions)


def test_supporting_passages_are_present_in_the_corpus(fake_dataset):
    passages, questions, _ = sample(fake_dataset, seed=4, target_passages=40)
    ids = {p.passage_id for p in passages}
    for question in questions:
        assert set(question.supporting_passage_ids) <= ids
        assert len(question.supporting_passage_ids) == 2


def test_sentence_ids_are_remapped_when_a_source_sentence_is_empty():
    # HotpotQA's sent_id indexes the raw sentence list. Dropping an empty
    # sentence shifts every later index, so the loader must remap, not pass through.
    paragraphs = [("Gold", ["   ", "Real first sentence.", "Real second sentence."])]
    paragraphs += [paragraph(i) for i in range(1, 3)]
    row = make_row(
        question_id="q-empty",
        question="Which?",
        answer="that",
        paragraphs=paragraphs,
        supporting=[("Gold", 2)],
    )
    passages, questions, _ = sample(FakeDataset([row]), seed=0, target_passages=100)
    question = questions[0]
    passage = next(p for p in passages if p.passage_id == question.supporting_passage_ids[0])
    pid, index = question.supporting_sentences[0]
    assert index == 1, "raw index 2 must map to kept index 1"
    assert passage.sentence(index) == "Real second sentence."


def test_supporting_fact_past_the_end_keeps_the_passage_and_drops_the_pointer():
    paragraphs = [("Gold", ["Only sentence."])] + [paragraph(i) for i in range(1, 3)]
    row = make_row(
        question_id="q-overflow",
        question="Which?",
        answer="that",
        paragraphs=paragraphs,
        supporting=[("Gold", 0), ("Gold", 9)],
    )
    _, questions, _ = sample(FakeDataset([row]), seed=0, target_passages=100)
    question = questions[0]
    assert len(question.supporting_passage_ids) == 1
    assert question.supporting_sentences == ((question.supporting_passage_ids[0], 0),)


def test_question_without_resolvable_support_is_skipped():
    row = make_row(
        question_id="q-bad",
        question="Which?",
        answer="that",
        paragraphs=[paragraph(1), paragraph(2)],
        supporting=[("Absent Title", 0)],
    )
    _, questions, report = sample(FakeDataset([row]), seed=0, target_passages=100)
    assert questions == []
    assert report.questions_skipped == 1


@pytest.mark.slow
def test_real_hotpotqa_schema_matches_what_the_loader_expects():
    from braid.ingest.loader import load_hotpotqa

    dataset = load_hotpotqa()
    passages, questions, _ = sample(dataset, seed=1, target_passages=30)
    assert passages and questions
    ids = {p.passage_id for p in passages}
    assert all(set(q.supporting_passage_ids) <= ids for q in questions)
