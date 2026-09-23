from braid.eval.queryset.overlap import content_words, fold, passes, shared_terms

PASSAGE = (
    "Scott Derrickson is an American film director, screenwriter and producer. "
    "He directed the 2016 Marvel film Doctor Strange."
)


def test_stopwords_are_not_content():
    assert content_words("the and of a") == set()


def test_shared_content_word_is_flagged():
    assert shared_terms("Which American film director made Doctor Strange?", PASSAGE)
    assert not passes("Which American film director made Doctor Strange?", PASSAGE)


def test_a_true_paraphrase_passes():
    query = "Who helmed a 2016 superhero movie about a neurosurgeon turned sorcerer?"
    assert shared_terms(query, PASSAGE) == ("2016",)


def test_stopword_reuse_alone_does_not_fail_the_check():
    assert passes("Who made that one, and why?", "Scott Derrickson directed Sinister.")


def test_folding_catches_inflected_reuse():
    assert fold("directors") == "director"
    assert fold("directed") == "direct"
    assert fold("companies") == "company"
    assert shared_terms("Which directors were involved?", PASSAGE) == ("director",)


def test_folding_leaves_short_words_alone():
    assert fold("is") == "is"
    assert fold("gas") == "gas"


def test_numbers_count_as_content():
    assert shared_terms("What happened in 2016?", PASSAGE) == ("2016",)
