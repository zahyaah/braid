import pytest

from braid.ingest.dedupe import (
    JACCARD_THRESHOLD,
    assert_no_dangling,
    dedupe,
    jaccard,
    remap_questions,
    shingles,
)
from braid.ingest.models import Passage, Question
from braid.ingest.normalize import join_sentences, passage_id


def make_passage(title: str, sentences: list[str]) -> Passage:
    text, spans = join_sentences(sentences)
    return Passage(
        passage_id=passage_id(title, text),
        title=title,
        text=text,
        sentence_spans=spans,
        source="test",
    )


def body(n: int) -> str:
    return " ".join(f"word{i}" for i in range(n))


def test_identical_text_dedupes():
    first = make_passage("A", ["The same body text here.", body(40)])
    second = make_passage("B", ["The same body text here.", body(40)])
    kept, report = dedupe([first, second])
    assert len(kept) == 1
    assert report.exact_removed == 1
    assert report.near_removed == 0


def test_whitespace_only_difference_dedupes():
    first = make_passage("A", ["One   two three.", body(40)])
    second = make_passage("A", ["One two    three.", body(40)])
    # Normalization already collapses these to the same text, hence the same id.
    assert first.passage_id == second.passage_id
    kept, _ = dedupe([first, second])
    assert len(kept) == 1


def test_one_sentence_difference_does_not_dedupe():
    shared = [f"Sentence {i} of the paragraph." for i in range(6)]
    first = make_passage("A", shared)
    second = make_passage("B", [*shared[:5], "A completely different closing line entirely."])
    assert jaccard(shingles(first.text), shingles(second.text)) < JACCARD_THRESHOLD
    kept, report = dedupe([first, second])
    assert len(kept) == 2
    assert report.near_removed == 0


def test_true_near_duplicate_dedupes():
    long_body = [f"Sentence {i} carries some distinctive filler words here." for i in range(40)]
    first = make_passage("A", long_body)
    tail = "Sentence 39 carries some distinctive filler words there."
    second = make_passage("B", [*long_body[:39], tail])
    assert jaccard(shingles(first.text), shingles(second.text)) >= JACCARD_THRESHOLD
    kept, report = dedupe([first, second])
    assert len(kept) == 1
    assert report.near_removed == 1


def test_dedupe_is_deterministic_and_keeps_lowest_id():
    first = make_passage("A", ["Shared body text.", body(40)])
    second = make_passage("B", ["Shared body text.", body(40)])
    expected = min(first.passage_id, second.passage_id)
    for ordering in ([first, second], [second, first]):
        kept, _ = dedupe(list(ordering))
        assert [p.passage_id for p in kept] == [expected]


def test_replacements_resolve_to_a_surviving_passage():
    passages = [make_passage(title, ["Shared body text.", body(40)]) for title in "ABC"]
    kept, report = dedupe(passages)
    kept_ids = {p.passage_id for p in kept}
    assert len(kept_ids) == 1
    assert set(report.replacements.values()) <= kept_ids


def question_for(passage_ids: list[str]) -> Question:
    return Question(
        question_id="q1",
        text="Who?",
        answer="someone",
        supporting_passage_ids=tuple(passage_ids),
        supporting_sentences=tuple((pid, 0) for pid in passage_ids),
        level="hard",
        qtype="bridge",
    )


def test_question_is_remapped_to_the_surviving_duplicate():
    question = question_for(["dead", "alive"])
    kept, report = remap_questions([question], {"dead": "kept_other"}, {"alive", "kept_other"})
    assert report.questions_remapped == 1
    assert report.questions_dropped == 0
    assert kept[0].supporting_passage_ids == ("kept_other", "alive")


def test_question_is_dropped_when_no_replacement_exists():
    question = question_for(["gone", "alive"])
    kept, report = remap_questions([question], {}, {"alive"})
    assert kept == []
    assert report.questions_dropped_missing == 1


def test_question_is_dropped_when_both_gold_passages_collapse_into_one():
    # A 2-hop question whose two gold paragraphs turn out to be duplicates is no
    # longer a 2-hop question, so it must not survive into the multi-hop category.
    question = question_for(["dead", "alive"])
    kept, report = remap_questions([question], {"dead": "alive"}, {"alive"})
    assert kept == []
    assert report.questions_dropped_collapsed == 1
    assert report.questions_dropped_missing == 0


def test_dangling_supporting_ids_raise():
    with pytest.raises(ValueError, match="missing passage"):
        assert_no_dangling([question_for(["ghost"])], {"alive"})


def test_removals_are_recorded_by_title_not_just_counted():
    first = make_passage("Keeper", ["Shared body text.", body(40)])
    second = make_passage("Dropped", ["Shared body text.", body(40)])
    _, report = dedupe([first, second])
    assert len(report.removals) == 1
    removal = report.removals[0]
    assert {removal["removed_title"], removal["kept_title"]} == {"Keeper", "Dropped"}
    assert removal["kind"] == "exact"


def test_near_removals_record_the_similarity_that_triggered_them():
    long_body = [f"Sentence {i} carries some distinctive filler words here." for i in range(40)]
    tail = "Sentence 39 carries some distinctive filler words there."
    _, report = dedupe([make_passage("A", long_body), make_passage("B", [*long_body[:39], tail])])
    removal = report.removals[0]
    assert removal["kind"] == "near"
    assert JACCARD_THRESHOLD <= removal["jaccard"] < 1.0
