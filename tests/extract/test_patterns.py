"""One fixture per documented pattern (SPEC-extract.md, Task 19), plus
negative fixtures that must yield no triple.
"""

from braid.extract.patterns import extract_document


def triples_for(nlp, text: str):
    doc = nlp(text)
    return extract_document(doc)


def as_tuples(triples):
    return {(t.subject_text, t.relation, t.object_text, t.pattern) for t in triples}


# ---- one fixture per documented pattern ----

def test_active_svo(nlp):
    triples = triples_for(nlp, "Scott Derrickson directed Sinister.")
    assert as_tuples(triples) == {("Scott Derrickson", "direct", "Sinister", "active_svo")}


def test_passive_with_agent(nlp):
    triples = triples_for(nlp, "The film was directed by Scott Derrickson.")
    assert as_tuples(triples) == {("Scott Derrickson", "direct", "film", "passive")}


def test_copular(nlp):
    triples = triples_for(nlp, "Scott Derrickson is a director.")
    assert as_tuples(triples) == {("Scott Derrickson", "be", "director", "copular")}


def test_verb_attached_prepositional_object(nlp):
    triples = triples_for(nlp, "Scott Derrickson worked in Denver.")
    assert as_tuples(triples) == {("Scott Derrickson", "work in", "Denver", "prep_object")}


def test_conjunction_expansion_on_subject(nlp):
    triples = triples_for(nlp, "Scott Derrickson and Ethan Cross wrote the film.")
    assert as_tuples(triples) == {
        ("Scott Derrickson", "write", "film", "active_svo"),
        ("Ethan Cross", "write", "film", "active_svo"),
    }


def test_conjunction_expansion_on_object(nlp):
    triples = triples_for(nlp, "Scott Derrickson directed Sinister and Doctor Strange.")
    assert as_tuples(triples) == {
        ("Scott Derrickson", "direct", "Sinister", "active_svo"),
        ("Scott Derrickson", "direct", "Doctor Strange", "active_svo"),
    }


# ---- negative fixtures: must yield no triple ----

def test_sentence_fragment_yields_nothing(nlp):
    assert triples_for(nlp, "A great film about a serial killer.") == []


def test_question_yields_nothing(nlp):
    assert triples_for(nlp, "Who directed Sinister?") == []


def test_list_header_yields_nothing(nlp):
    assert triples_for(nlp, "Filmography:") == []


def test_passive_without_agent_yields_nothing(nlp):
    # No recoverable subject -- must not fabricate one.
    assert triples_for(nlp, "The film was directed.") == []


# ---- pattern precedence ----

def test_prep_object_does_not_fire_when_a_dobj_already_exists(nlp):
    # "wrote the film about war" has both a dobj (film) and a prep (about);
    # pattern 4 must not also fire for the same verb once pattern 1 has. The
    # object span legitimately includes "about war" -- it is an NP-internal
    # PP attached to "film" itself, not to the verb, so it is part of the
    # object's own noun phrase, not a second relation.
    triples = triples_for(nlp, "Scott Derrickson wrote the film about war.")
    patterns_fired = {t.pattern for t in triples}
    assert "prep_object" not in patterns_fired
    assert ("Scott Derrickson", "write", "film about war", "active_svo") in as_tuples(triples)


# ---- regressions found via the extraction-quality report ----

def test_relative_pronoun_subject_yields_no_triple(nlp):
    # Regression: "which" as a relative-clause subject has no antecedent
    # resolvable here (it refers to "movie", not the passage's title), and
    # was previously emitted verbatim as a nonsensical subject.
    triples = triples_for(nlp, "The movie, which aired on ABC, was popular.")
    assert not any(t.subject_text.lower() == "which" for t in triples)


def test_relative_pronoun_who_and_that_yield_no_triple(nlp):
    for text in [
        "The man who left was tired.",
        "The team that discovered fossils was led by Asfaw.",
    ]:
        triples = triples_for(nlp, text)
        subjects = {t.subject_text.lower() for t in triples}
        assert "who" not in subjects
        assert "that" not in subjects


def test_demonstrative_that_is_not_filtered(nlp):
    # "That" as a genuine demonstrative subject (tag DT, not WDT) is a real
    # subject and must still fire normally -- only the relative-pronoun tag
    # is excluded, not the literal word "that". "correct" as an adjective
    # (acomp) is outside pattern 3's documented scope (attr only), so this
    # uses a noun predicate instead to isolate the WH-filter behavior.
    triples = triples_for(nlp, "That is a mistake.")
    assert as_tuples(triples) == {("That", "be", "mistake", "copular")}


def test_prep_relation_is_lowercased_even_with_a_fronted_preposition(nlp):
    # Regression: a sentence-initial PP ("With her approach, Kamen became...")
    # left the preposition's surface capitalization in the relation string
    # ("become With" instead of "become with").
    triples = triples_for(nlp, "With her approach, Kamen became a persona.")
    relations = {t.relation for t in triples}
    assert not any(r != r.lower() for r in relations)
