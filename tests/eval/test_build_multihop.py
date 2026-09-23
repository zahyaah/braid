from braid.eval.queryset.build_multihop import build, to_labeled
from braid.ingest.models import Question


def question(qid: str, supporting: tuple[str, ...]) -> Question:
    return Question(
        question_id=qid,
        text=f"Question {qid}?",
        answer="answer",
        supporting_passage_ids=supporting,
        supporting_sentences=tuple((pid, 0) for pid in supporting),
        level="hard",
        qtype="bridge",
    )


def test_relevance_is_binary_with_one_entry_per_supporting_paragraph():
    labeled = to_labeled(question("q1", ("p1", "p2", "p3")))
    assert labeled.relevant == {"p1": 1, "p2": 1, "p3": 1}
    assert labeled.category == "multi-hop-relational"
    assert labeled.origin == "hotpotqa"
    assert labeled.source_question_id == "q1"


def test_query_ids_are_derived_from_the_hotpotqa_question_id():
    assert to_labeled(question("abc123", ("p1", "p2"))).query_id == "mh-abc123"


def test_single_support_questions_are_skipped_as_not_multi_hop():
    built = build([question("q1", ("p1",)), question("q2", ("p1", "p2"))])
    assert [q.query_id for q in built] == ["mh-q2"]


def test_build_order_is_stable_and_limit_takes_a_prefix():
    questions = [question(f"q{i}", ("p1", "p2")) for i in (3, 1, 2)]
    assert [q.query_id for q in build(questions)] == ["mh-q1", "mh-q2", "mh-q3"]
    assert [q.query_id for q in build(questions, limit=2)] == ["mh-q1", "mh-q2"]
