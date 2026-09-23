from braid.extract.entities import (
    fold_case,
    is_pronoun,
    normalize_surface,
    normalize_triple,
    resolve_alias,
    substitute_pronoun,
)
from braid.extract.models import RawTriple
from braid.extract.ner import Entity
from braid.ingest.models import Passage


def passage(title: str, text: str = "text") -> Passage:
    return Passage("p1", title, text, ((0, len(text)),), "test")


# ---- case folding ----

def test_fold_case_ignores_case_and_whitespace():
    assert fold_case("Scott  Derrickson") == fold_case("scott derrickson")


def test_fold_case_normalizes_unicode():
    assert fold_case("Cortés") == fold_case("cortés")


# ---- pronoun substitution ----

def test_third_person_pronouns_are_detected():
    for word in ("he", "She", "ITS", "Their", "them"):
        assert is_pronoun(word)


def test_first_and_second_person_are_not_pronouns_for_this_purpose():
    for word in ("I", "you", "we", "I'd"):
        assert not is_pronoun(word)


def test_pronoun_is_substituted_with_the_passage_title():
    assert substitute_pronoun("He", "Scott Derrickson") == "Scott Derrickson"
    assert substitute_pronoun("their", "Arsenal F.C.") == "Arsenal F.C."


def test_non_pronoun_is_left_unchanged_by_substitution():
    assert substitute_pronoun("Sinister", "Scott Derrickson") == "Sinister"


# ---- alias resolution ----

def test_alias_matching_the_title_exactly_canonicalizes_casing():
    assert resolve_alias("scott derrickson", "Scott Derrickson") == "Scott Derrickson"


def test_alias_matching_title_with_disambiguator_stripped():
    assert resolve_alias("Ed Wood", "Ed Wood (film)") == "Ed Wood (film)"


def test_unrelated_text_is_left_unchanged():
    assert resolve_alias("Sinister", "Scott Derrickson") == "Sinister"


# ---- combined ----

def test_normalize_surface_applies_pronoun_then_alias():
    assert normalize_surface("she", "Ruby Lindsay") == "Ruby Lindsay"
    assert normalize_surface("Ruby lindsay", "Ruby Lindsay") == "Ruby Lindsay"
    assert normalize_surface("Sinister", "Ruby Lindsay") == "Sinister"


# ---- normalize_triple, including type attachment ----

def test_normalize_triple_substitutes_pronoun_subject_and_attaches_type():
    p = passage("Scott Derrickson")
    raw = RawTriple("He", "direct", "Sinister", sentence_index=1, pattern="active_svo")
    entities = [Entity("He", "PERSON", 0, 2)]
    triple = normalize_triple(raw, p, entities)
    assert triple.subject == "Scott Derrickson"
    assert triple.subject_type == "PERSON"
    assert triple.object == "Sinister"
    assert triple.sentence_index == 1
    assert triple.passage_id == "p1"


def test_find_type_matches_by_containment_not_just_exact_equality():
    # Regression: the object/subject span frequently carries words around the
    # named entity itself ("director Mike Nichols"), and requiring an exact
    # match against the NER span left 78%/90% of subjects/objects untyped on
    # the real corpus -- found by inspecting real extraction output.
    p = passage("Catch-22 (film)")
    raw = RawTriple(
        "director Mike Nichols", "work on", "film script", sentence_index=0, pattern="prep_object"
    )
    entities = [Entity("Mike Nichols", "PERSON", 9, 21)]
    triple = normalize_triple(raw, p, entities)
    assert triple.subject_type == "PERSON"


def test_find_type_prefers_the_longer_contained_entity():
    p = passage("Sony")
    raw = RawTriple("Sony Corp announcement", "make", "X", sentence_index=0, pattern="active_svo")
    entities = [Entity("Sony", "ORG", 0, 4), Entity("Sony Corp", "ORG", 0, 9)]
    triple = normalize_triple(raw, p, entities)
    assert triple.subject_type == "ORG"  # both match; containment itself is what's tested
    # More telling: a case where lengths would disambiguate differently.
    entities2 = [Entity("Sony", "PERSON", 0, 4), Entity("Sony Corp", "ORG", 0, 9)]
    triple2 = normalize_triple(raw, p, entities2)
    assert triple2.subject_type == "ORG"  # the longer, more specific match wins


def test_normalize_triple_leaves_object_type_none_when_no_entity_matches():
    p = passage("Scott Derrickson")
    raw = RawTriple(
        "Scott Derrickson", "direct", "a horror film", sentence_index=0, pattern="active_svo"
    )
    triple = normalize_triple(raw, p, sentence_entities=[])
    assert triple.object_type is None


# ---- cross-passage coreference is explicitly not attempted ----

def test_normalization_never_draws_on_another_passages_title():
    # The only context normalize_triple/normalize_surface ever receive is the
    # *current* passage and its own entities -- there is no parameter, global,
    # or lookup path by which a different passage's title could reach here.
    import inspect

    sig = inspect.signature(normalize_triple)
    assert list(sig.parameters) == ["raw", "passage", "sentence_entities"]
    # A pronoun resolves only to *this* passage's title, never to a title
    # supplied from elsewhere in the corpus.
    other_passage_title = "Some Other Article Entirely"
    p = passage("Scott Derrickson")
    raw = RawTriple("he", "direct", "Sinister", sentence_index=0, pattern="active_svo")
    triple = normalize_triple(raw, p, sentence_entities=[])
    assert triple.subject != other_passage_title
    assert triple.subject == "Scott Derrickson"
