"""Entity normalization: alias resolution against the passage title, case
folding, and within-passage pronoun substitution (SPEC-extract.md).

Cross-passage coreference is explicitly not attempted: normalization only
ever draws on the *current* passage's own title. Nothing here looks at, or
could look at, another passage's entities -- there is no shared state and no
function that accepts more than one passage's context at a time.
"""

from __future__ import annotations

import re
import unicodedata

from braid.extract.models import RawTriple, Triple
from braid.extract.ner import Entity
from braid.ingest.models import Passage

# Third-person pronouns only -- first/second person ("I", "you", "we") never
# refer to the passage's own subject in encyclopedic prose, so substituting
# them would be wrong, not just unhelpful.
PRONOUNS = frozenset(
    {"he", "him", "his", "she", "her", "hers", "it", "its", "they", "them", "their", "theirs"}
)

_PARENTHETICAL = re.compile(r"\s*\([^)]*\)\s*$")


def fold_case(text: str) -> str:
    """The comparison key for alias/entity matching: NFKC-normalized,
    case-folded, whitespace-collapsed. Used only for *matching* -- display
    text keeps its original casing.
    """
    normalized = unicodedata.normalize("NFKC", text)
    return " ".join(normalized.casefold().split())


def is_pronoun(text: str) -> bool:
    return fold_case(text) in PRONOUNS


def substitute_pronoun(text: str, passage_title: str) -> str:
    """First-mention title substitution: a bare pronoun is replaced with the
    passage's own title. This is a deliberate simplification, not general
    antecedent tracking -- HotpotQA passages are single-subject encyclopedic
    prose, so a third-person pronoun overwhelmingly refers to the article's
    own subject. It is documented here, not silently assumed.
    """
    return passage_title if is_pronoun(text) else text


def _strip_disambiguator(text: str) -> str:
    """Drop a trailing parenthetical ("... (film)") for alias comparison only."""
    return _PARENTHETICAL.sub("", text).strip()


def resolve_alias(text: str, passage_title: str) -> str:
    """If `text` refers to the passage's own subject -- matching the title
    exactly, or matching it with a disambiguating parenthetical stripped --
    canonicalize to the title's own casing. Otherwise the text is returned
    unchanged: this is alias resolution against the *passage title*
    specifically, not general entity linking.
    """
    if fold_case(text) == fold_case(passage_title):
        return passage_title
    if fold_case(_strip_disambiguator(passage_title)) == fold_case(text):
        return passage_title
    return text


def normalize_surface(text: str, passage_title: str) -> str:
    """Pronoun substitution, then alias resolution -- the two within-passage
    normalization rules, applied in that order (a substituted pronoun becomes
    the title, which alias resolution then leaves alone since it already
    matches).
    """
    substituted = substitute_pronoun(text, passage_title)
    return resolve_alias(substituted, passage_title)


def _find_type(text: str, sentence_entities: list[Entity]) -> str | None:
    """The NER label of an entity whose text is contained in (or equal to)
    `text`, if any.

    A pattern's subject/object span often carries words around the named
    entity itself ("director Mike Nichols", "a 1970 film adapted from..."),
    so an *exact* match against the NER span found almost nothing on the real
    corpus -- 78% of subjects and 90% of objects came back untyped on the
    first full run, discovered by inspecting real output before writing the
    quality report. Containment catches "Mike Nichols" inside "director Mike
    Nichols". When more than one entity is contained, the longest wins, since
    a longer contained span is more specific (e.g. an object containing both
    "Sony" and "Sony Corp" should prefer "Sony Corp").
    """
    target = fold_case(text)
    candidates = [
        entity for entity in sentence_entities if fold_case(entity.text) in target
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda e: len(e.text)).label


def normalize_triple(
    raw: RawTriple, passage: Passage, sentence_entities: list[Entity]
) -> Triple:
    """A RawTriple (surface text) into a Triple (normalized subject/object,
    with types attached from NER where a match exists).
    """
    subject = normalize_surface(raw.subject_text, passage.title)
    obj = normalize_surface(raw.object_text, passage.title)
    return Triple(
        subject=subject,
        relation=raw.relation,
        object=obj,
        passage_id=passage.passage_id,
        sentence_index=raw.sentence_index,
        subject_type=_find_type(raw.subject_text, sentence_entities),
        object_type=_find_type(raw.object_text, sentence_entities),
        pattern=raw.pattern,
    )
