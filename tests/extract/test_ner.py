import pytest

from braid.extract.ner import extract_entities, peak_rss_mb


def test_entities_carry_char_spans_into_the_doc_text(nlp):
    text = "Scott Derrickson directed Sinister in 2012."
    doc = nlp(text)
    entities = extract_entities(doc)
    assert entities  # en_core_web_sm should find at least the person and date
    for ent in entities:
        assert text[ent.start_char : ent.end_char] == ent.text


def test_entity_labels_are_present(nlp):
    doc = nlp("Scott Derrickson directed Sinister in 2012.")
    labels = {e.label for e in extract_entities(doc)}
    assert labels  # non-empty; exact label set is model-dependent


def test_no_entities_on_a_sentence_with_none():
    import spacy

    nlp = spacy.blank("en")
    doc = nlp("the quick fast thing happened")
    assert extract_entities(doc) == []


def test_peak_rss_is_a_positive_number():
    # A real, sane measurement -- this process has allocated memory just by
    # running the test suite.
    assert peak_rss_mb() > 0


@pytest.mark.slow
def test_real_trf_model_loads_and_extracts():
    from braid.extract.ner import load_pipeline

    nlp = load_pipeline()
    doc = nlp("Scott Derrickson directed Sinister, a 2012 horror film.")
    entities = extract_entities(doc)
    assert any(e.label == "PERSON" for e in entities)
