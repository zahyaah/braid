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


def test_possessive_clitic_does_not_produce_a_bare_s_token():
    # Regression: "Disturbed's" tokenized as {"disturb", "s"} before the fix,
    # and that lone "s" spuriously overlapped any *other* possessive anywhere
    # in the target passage -- a false positive, not real vocabulary reuse.
    assert "s" not in content_words("Disturbed's second album")


def test_possessive_no_longer_creates_a_spurious_overlap():
    query = "Which band's second album debuted at number one?"
    passage = "The company's headquarters relocated in 1994."
    assert passes(query, passage)


def test_decimal_numbers_do_not_fragment_into_spurious_shared_digits():
    # Regression: "2.2" tokenized as a bare "2" before the fix, so two
    # different figures like "2.2" and "12.2" spuriously "shared" the digit
    # "2" even though the actual numbers are unrelated.
    assert content_words("It earned 2.2 million") == {"2.2", "earn", "million"}
    # Different sentences, sharing no words except the numeral fragments a
    # naive regex would have split "12.6" and "12.2" into -- both would have
    # produced a bare "12" before the fix, flagging as overlap despite being
    # unrelated figures.
    assert passes("Revenue climbed to 12.6 last quarter", "Attendance fell to 12.2 that season")


def test_matching_decimals_still_flag_as_shared():
    assert not passes("It earned 2.2 million", "Revenue reached 2.2 million that year")


def test_silent_e_plural_folds_to_its_singular_not_a_mangled_stem():
    # Regression: "notes" stripped its "es" suffix down to "not" -- a real,
    # extremely common word -- so any query using the stopword-adjacent "not"
    # nowhere near the passage's actual meaning would spuriously "overlap"
    # any passage that happened to say "notes". True sibilant "es" plurals
    # (boxes, watches) still fold correctly.
    assert fold("notes") == "note"
    assert fold("votes") == "vote"
    assert fold("boxes") == "box"
    assert fold("watches") == "watch"


def test_notes_no_longer_spuriously_matches_a_query_using_not():
    query = "Is this not the correct answer to the question?"
    passage = "The fragrance's notes include lime and leather."
    assert passes(query, passage)
