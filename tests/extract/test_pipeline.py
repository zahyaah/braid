from braid.extract.__main__ import extract_passage
from braid.ingest.models import Passage
from braid.ingest.normalize import join_sentences, passage_id


def make_passage(title: str, sentences: list[str]) -> Passage:
    text, spans = join_sentences(sentences)
    return Passage(passage_id(title, text), title, text, spans, "test")


def test_extract_passage_wires_ner_patterns_and_normalization(nlp):
    sentences = ["Scott Derrickson directed Sinister.", "He worked with Ethan Cross."]
    p = make_passage("Scott Derrickson", sentences)
    triples = extract_passage(nlp, p)
    subjects = {t.subject for t in triples}
    # The pronoun "He" in sentence 1 must resolve to the passage title.
    assert "Scott Derrickson" in subjects
    assert not any(s.lower() == "he" for s in subjects)


def test_extract_passage_attaches_entity_types_when_ner_finds_one(nlp):
    p = make_passage("Scott Derrickson", ["Scott Derrickson directed Sinister."])
    triples = extract_passage(nlp, p)
    assert triples
    matching = [t for t in triples if t.subject == "Scott Derrickson"]
    assert matching
    assert matching[0].subject_type is not None
