"""The paraphrase drafting constraint: no content word shared with the target passage.

Scope is the target passage only, never the whole corpus (amendment 6). A
corpus-wide ban would make most natural English unwritable.

**Deliberately not spaCy.** This is a drafting constraint, not a linguistic
analysis: over-flagging costs a rewrite, under-flagging leaks vocabulary into a
query that is supposed to test paraphrase retrieval. A short explicit stopword
list plus conservative suffix folding is deterministic, needs no model
download, runs offline in tests, and errs toward flagging. Its limitation is
irregular morphology — "ran" does not fold to "run" — which is why a reviewer
can override in the other direction but never silently waive a flag.
"""

from __future__ import annotations

import re

# A decimal ("2.2", "12.6") must tokenize as one number, not fragments split
# at the period -- "[a-z0-9]+" alone splits "2.2" into two bare "2" tokens,
# so two genuinely different figures like "2.2" and "12.2" would spuriously
# "share" the digit "2". Numbers with an optional decimal part are matched
# before the general run, so the decimal point binds to its own number.
_WORD = re.compile(r"\d+\.\d+|[a-z0-9]+")
# A possessive clitic ("Disturbed's", "band's") is not itself a content word.
# Left unstripped, "'s" tokenizes as a bare one-letter "s" that spuriously
# "overlaps" any *other* possessive anywhere in the passage -- a false
# positive found by running this at scale on real paraphrase drafts, not a
# hypothetical.
_POSSESSIVE = re.compile(r"'s\b")

# Function words carry no topical content, so sharing them is not vocabulary reuse.
STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are as at be because been before being
    below between both but by can cannot could did do does doing down during each few for from
    further had has have having he her here hers herself him himself his how i if in into is it
    its itself me more most my myself no nor not of off on once only or other ought our ours
    ourselves out over own same she should so some such than that the their theirs them
    themselves then there these they this those through to too under until up very was we were
    what when where which while who whom why with would you your yours yourself yourselves
    """.split()  # noqa: SIM905 - one word per column reads better than a 130-item literal
)

# True "es" pluralization only follows a sibilant or affricate ending
# (boxes, watches, wishes, buzzes, glasses) -- stripping "es" unconditionally
# also matches silent-e plurals like "notes" or "votes", corrupting them to
# "not" and "vot". Checked *before* the generic suffix loop, which then only
# strips the trailing "s" from those, correctly yielding "note" and "vote".
_ES_PLURAL = re.compile(r"(?:[sxz]es|(?:ch|sh)es)$")
_SUFFIXES = ("ies", "ing", "ed", "s", "ly")


def fold(word: str) -> str:
    """Conservative suffix folding, so 'directors' and 'director' count as one word."""
    lowered = word.lower()
    if lowered in STOPWORDS or len(lowered) <= 3:
        return lowered
    if _ES_PLURAL.search(lowered) and len(lowered) - 2 >= 3:
        return lowered[:-2]
    for suffix in _SUFFIXES:
        if lowered.endswith(suffix) and len(lowered) - len(suffix) >= 3:
            stem = lowered[: -len(suffix)]
            if suffix == "ies":
                return stem + "y"
            return stem
    return lowered


def content_words(text: str) -> set[str]:
    """Folded, non-stopword tokens. Numbers count as content."""
    stripped = _POSSESSIVE.sub("", text.lower())
    return {fold(token) for token in _WORD.findall(stripped) if token not in STOPWORDS}


def shared_terms(query: str, passage_text: str) -> tuple[str, ...]:
    """Content words the query shares with its target passage, sorted for stability."""
    return tuple(sorted(content_words(query) & content_words(passage_text)))


def passes(query: str, passage_text: str) -> bool:
    return not shared_terms(query, passage_text)
