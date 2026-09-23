from braid.eval.queryset.build_exact import build, draft_query, pick_unique_term
from braid.eval.queryset.uniqueness import (
    count_occurrences,
    extract_candidates,
    is_unique,
)
from braid.ingest.models import Passage


def passage(pid: str, title: str, text: str) -> Passage:
    return Passage(pid, title, text, ((0, len(text)),), "test")


def test_extracts_multi_word_phrases_years_and_numbers():
    p = passage(
        "p1",
        "Test",
        "Scott Derrickson directed a film in 1994 that grossed 1,200,000 dollars.",
    )
    candidates = extract_candidates(p)
    kinds = {c.kind for c in candidates}
    terms = {c.term for c in candidates}
    assert "phrase" in kinds and "Scott Derrickson" in terms
    assert "year" in kinds and "1994" in terms
    assert "number" in kinds and "1,200,000" in terms


def test_short_numbers_are_not_candidates():
    p = passage("p1", "Test", "He scored 12 points and 5 assists.")
    numbers = {c.term for c in extract_candidates(p) if c.kind == "number"}
    assert numbers == set()


def test_passage_title_itself_is_excluded_from_phrase_candidates():
    p = passage("p1", "Scott Derrickson", "Scott Derrickson made films.")
    phrases = {c.term for c in extract_candidates(p) if c.kind == "phrase"}
    assert "Scott Derrickson" not in phrases


def test_count_occurrences_and_is_unique():
    corpus = [
        passage("p1", "A", "Scott Derrickson directed Sinister."),
        passage("p2", "B", "Ed Wood was a different filmmaker entirely."),
    ]
    assert count_occurrences("Scott Derrickson", corpus) == 1
    assert is_unique("Scott Derrickson", corpus)
    extra = passage("p3", "C", "Another filmmaker worked here.")
    assert not is_unique("filmmaker", corpus + [extra])


def test_a_term_repeated_across_passages_is_not_unique():
    corpus = [
        passage("p1", "A", "The Golden Gate Bridge is in San Francisco."),
        passage("p2", "B", "Tourists photograph the Golden Gate Bridge daily."),
    ]
    assert not is_unique("Golden Gate Bridge", corpus)


def test_pick_unique_term_skips_non_unique_candidates_and_returns_a_unique_one():
    corpus = [
        passage("p1", "A", "The Golden Gate Bridge and Scott Derrickson both appear here."),
        passage("p2", "B", "The Golden Gate Bridge is mentioned again, with nobody else."),
    ]
    candidate = pick_unique_term(corpus[0], corpus)
    assert candidate is not None
    assert candidate.term == "Scott Derrickson"
    assert is_unique(candidate.term, corpus)


def test_pick_unique_term_returns_none_when_every_candidate_is_shared():
    corpus = [
        passage("p1", "A", "The Golden Gate Bridge stands tall."),
        passage("p2", "B", "The Golden Gate Bridge is famous."),
    ]
    assert pick_unique_term(corpus[0], corpus) is None


def test_draft_query_embeds_the_term_verbatim():
    p = passage("p1", "Scott Derrickson", "text")
    from braid.eval.queryset.uniqueness import Candidate

    text = draft_query(p, Candidate("Doctor Strange", "phrase"), template_index=0)
    assert "Doctor Strange" in text


def test_build_never_drafts_a_query_whose_term_is_not_unique():
    corpus = [
        passage("p1", "A", "Scott Derrickson directed a film in 1994."),
        passage("p2", "B", "The Golden Gate Bridge appears in both here."),
        passage("p3", "C", "The Golden Gate Bridge appears in both here too."),
    ]
    queries, skipped = build(corpus, limit=10, seed=1)
    for query in queries:
        passage_id = next(iter(query.relevant))
        target_passage = next(p for p in corpus if p.passage_id == passage_id)
        assert term_is_still_unique(target_passage, corpus)


def term_is_still_unique(target_passage, corpus) -> bool:
    # Every drafted query's underlying term (re-extracted the same way the
    # builder picked it) must still be unique across the corpus it was built
    # against.
    candidate = pick_unique_term(target_passage, corpus)
    return candidate is not None and is_unique(candidate.term, corpus)


def test_build_has_exactly_one_relevant_passage_per_query():
    corpus = [
        passage(f"p{i}", f"Title {i}", f"Unique{i} content appears here only.") for i in range(5)
    ]
    queries, _ = build(corpus, limit=5, seed=2)
    for query in queries:
        assert len(query.relevant) == 1


def test_build_is_deterministic_for_a_seed():
    corpus = [
        passage(f"p{i}", f"Title {i}", f"Unique{i} content appears here only.") for i in range(10)
    ]
    first, _ = build(corpus, limit=5, seed=7)
    second, _ = build(corpus, limit=5, seed=7)
    assert [q.query_id for q in first] == [q.query_id for q in second]


def test_build_skips_passages_with_no_unique_candidate_and_counts_them():
    corpus = [
        passage("p1", "A", "The Golden Gate Bridge is old."),
        passage("p2", "B", "The Golden Gate Bridge is still old."),
        passage("p3", "C", "Scott Derrickson directed a real film."),
    ]
    queries, skipped = build(corpus, limit=10, seed=3)
    assert skipped == 2
    assert len(queries) == 1


def test_phrase_matching_stops_at_a_sentence_boundary():
    # Regression: "University of Delaware. Following" must not become one
    # candidate joining two different sentences' capitalized words.
    p = passage(
        "p1", "Test", "He studied at the University of Delaware. Following that, he moved."
    )
    phrases = {c.term for c in extract_candidates(p) if c.kind == "phrase"}
    assert "University of Delaware" in phrases
    assert not any("Following" in phrase for phrase in phrases)


def test_trailing_possessive_is_stripped_from_a_phrase():
    p = passage("p1", "Test", "It was Nazi Germany's largest submarine class.")
    phrases = {c.term for c in extract_candidates(p) if c.kind == "phrase"}
    assert "Nazi Germany" in phrases
    assert not any(phrase.endswith("'s") for phrase in phrases)


def test_multi_period_abbreviation_does_not_bleed_into_the_next_sentence():
    # Perfect abbreviation parsing ("U.S." as one token) is not required here;
    # what matters is that it never drags the next sentence's capitalized word
    # into the same candidate phrase.
    p = passage("p1", "Test", "He later moved to the U.S. Following that, he retired.")
    phrases = {c.term for c in extract_candidates(p) if c.kind == "phrase"}
    assert not any("Following" in phrase for phrase in phrases)


def test_accented_latin_characters_are_not_truncated():
    p = passage("p1", "Test", "Manoel Cândido Pinto de Oliveira directed many films.")
    phrases = {c.term for c in extract_candidates(p) if c.kind == "phrase"}
    assert "Manoel Cândido Pinto de Oliveira" in phrases
    assert not any(phrase.endswith(" C") or phrase == "Manoel C" for phrase in phrases)
