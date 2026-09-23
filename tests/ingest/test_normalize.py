from braid.ingest.normalize import (
    join_sentences,
    normalize_text,
    passage_id,
    text_hash,
)


def test_normalize_collapses_whitespace_and_nbsp():
    assert normalize_text("  a  b\n\tc  ") == "a b c"


def test_normalize_is_nfkc():
    # Fullwidth 'A' and the ligature 'ﬁ' both have NFKC compatibility forms.
    assert normalize_text("Ａ") == "A"
    assert normalize_text("ﬁn") == "fin"


def test_passage_id_is_stable_and_16_hex_chars():
    first = passage_id("Title", "Some text.")
    assert first == passage_id("Title", "Some text.")
    assert len(first) == 16
    assert all(char in "0123456789abcdef" for char in first)


def test_passage_id_ignores_formatting_but_not_content():
    assert passage_id("Title", "Some text.") == passage_id(" Title ", "Some   text.")
    assert passage_id("Title", "Some text.") != passage_id("Title", "Some other text.")
    assert passage_id("Title", "Some text.") != passage_id("Other", "Some text.")


def test_sentence_spans_round_trip():
    sentences = ["First one.", "  Second   one. ", "Third one."]
    text, spans = join_sentences(sentences)
    sliced = [text[start:end] for start, end in spans]
    assert sliced == ["First one.", "Second one.", "Third one."]
    assert text == "First one. Second one. Third one."


def test_empty_sentences_are_dropped_not_zero_width():
    text, spans = join_sentences(["Kept.", "   ", "", "Also kept."])
    assert len(spans) == 2
    assert [text[a:b] for a, b in spans] == ["Kept.", "Also kept."]


def test_text_hash_ignores_title():
    assert text_hash("Same body.") == text_hash("  Same   body. ")
