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

_WORD = re.compile(r"[a-z0-9]+")

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

_SUFFIXES = ("ies", "ing", "ed", "es", "s", "ly")


def fold(word: str) -> str:
    """Conservative suffix folding, so 'directors' and 'director' count as one word."""
    lowered = word.lower()
    if lowered in STOPWORDS or len(lowered) <= 3:
        return lowered
    for suffix in _SUFFIXES:
        if lowered.endswith(suffix) and len(lowered) - len(suffix) >= 3:
            stem = lowered[: -len(suffix)]
            if suffix == "ies":
                return stem + "y"
            return stem
    return lowered


def content_words(text: str) -> set[str]:
    """Folded, non-stopword tokens. Numbers count as content."""
    return {fold(token) for token in _WORD.findall(text.lower()) if token not in STOPWORDS}


def shared_terms(query: str, passage_text: str) -> tuple[str, ...]:
    """Content words the query shares with its target passage, sorted for stability."""
    return tuple(sorted(content_words(query) & content_words(passage_text)))


def passes(query: str, passage_text: str) -> bool:
    return not shared_terms(query, passage_text)
