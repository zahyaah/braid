"""Mechanical uniqueness check for exact-term queries.

An exact-term query targets a term that appears verbatim in exactly one
passage. A term occurring in zero or several passages is not labeled around —
the author picks a term that satisfies the check (SPEC-queryset.md, Task 9).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from braid.ingest.models import Passage

# A capitalized phrase: 1-5 title-case words, allowing lowercase connectors
# ("of", "the", "van", ...) inside but not at the start.
# Name-internal particles only ("Duke of York", "Vincent van Gogh"). "and",
# "in", "for" deliberately excluded: those conjoin separate phrases rather
# than extending one entity name, and including them merged unrelated
# entities into a single bogus candidate.
_CONNECTORS = {"of", "the", "van", "von", "de", "da", "der"}
# A word token allows an internal period only when immediately followed by
# another uppercase letter with no space ("U.S", an abbreviation). A period
# before whitespace is a sentence boundary, not part of the word, so it is
# never consumed here -- consuming it let two words from *different*
# sentences join into one bogus phrase across "Delaware. Following".
# Accented Latin letters (Cándido, Creación, Léopold) so a corpus with
# European names does not get truncated mid-word. Latin-1 Supplement plus
# Latin Extended-A covers most Western European diacritics.
_ACCENTED = "\u00C0-\u017F"
_UPPER = "A-Z" + _ACCENTED
# "*" not "+": a single-letter initial ("U" in "U.S.") still needs to match.
_WORD = rf"[A-Za-z0-9{_ACCENTED}'-]*(?:\.(?=[A-Z]))?"
_PHRASE = re.compile(
    r"\b[{upper}]{word}(?:\s+(?:[{upper}]{word}|(?:{connectors})))*".format(
        upper=_UPPER, word=_WORD, connectors="|".join(sorted(_CONNECTORS))
    ),
    re.UNICODE,
)
_YEAR = re.compile(r"\b(1[5-9]\d{2}|20[0-4]\d)\b")
_NUMBER = re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b")


@dataclass(frozen=True)
class Candidate:
    term: str
    kind: str  # "phrase" | "year" | "number"


def extract_candidates(passage: Passage) -> list[Candidate]:
    """Candidate exact terms from one passage: proper-noun phrases, years, numbers.

    Not exhaustive by design — good enough to surface plausible drafting
    material. Every candidate still goes through `count_occurrences` before it
    is used.
    """
    seen: set[tuple[str, str]] = set()
    candidates: list[Candidate] = []

    for match in _PHRASE.finditer(passage.text):
        words = match.group().strip().split()
        # A sentence-initial "The"/"A" is capitalized but not part of the
        # entity name, so strip leading connector words rather than reject
        # the whole match because of them.
        while words and words[0].lower() in _CONNECTORS:
            words = words[1:]
        while words and words[-1].lower() in _CONNECTORS:
            words = words[:-1]
        if len(words) < 2:
            continue
        # A trailing possessive ("Germany's") is not part of the entity name.
        if words[-1].lower().endswith("'s"):
            words[-1] = words[-1][:-2]
        phrase = " ".join(words)
        if phrase == passage.title:
            continue
        key = ("phrase", phrase)
        if key not in seen:
            seen.add(key)
            candidates.append(Candidate(phrase, "phrase"))

    for match in _YEAR.finditer(passage.text):
        key = ("year", match.group())
        if key not in seen:
            seen.add(key)
            candidates.append(Candidate(match.group(), "year"))

    for match in _NUMBER.finditer(passage.text):
        value = match.group()
        if _YEAR.fullmatch(value):
            continue  # already captured as a year
        if len(value.replace(",", "").replace(".", "")) < 3:
            continue  # short numbers ("5", "12") are rarely unique or useful
        key = ("number", value)
        if key not in seen:
            seen.add(key)
            candidates.append(Candidate(value, "number"))

    return candidates


def count_occurrences(term: str, passages: list[Passage]) -> int:
    """How many passages contain `term` verbatim (case-sensitive substring)."""
    return sum(1 for passage in passages if term in passage.text)


def is_unique(term: str, passages: list[Passage]) -> bool:
    return count_occurrences(term, passages) == 1
