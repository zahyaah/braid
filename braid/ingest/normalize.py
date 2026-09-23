"""Text normalization and content-addressed passage IDs.

Passage IDs are content-addressed so that a rerun on the same source yields
identical IDs, and an unchanged passage keeps its ID when the corpus is
extended (SPEC-ingest.md, Task 3).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
ID_LENGTH = 16
NUL = "\x00"


def normalize_text(value: str) -> str:
    """NFKC-normalize, collapse whitespace runs to one space, strip."""
    normalized = unicodedata.normalize("NFKC", value)
    # NFKC leaves some separators alone; map them to plain spaces first.
    normalized = normalized.replace(" ", " ").replace("​", "")
    return _WHITESPACE.sub(" ", normalized).strip()


def normalize_title(value: str) -> str:
    return normalize_text(value)


def join_sentences(sentences: list[str]) -> tuple[str, tuple[tuple[int, int], ...]]:
    """Flatten HotpotQA's per-sentence lists into one string plus char spans.

    Empty sentences are dropped rather than producing zero-width spans. Slicing
    the returned text by any span reproduces that normalized sentence exactly.
    """
    parts: list[str] = []
    spans: list[tuple[int, int]] = []
    cursor = 0
    for raw in sentences:
        sentence = normalize_text(raw)
        if not sentence:
            continue
        if parts:
            cursor += 1  # the single space joining this sentence to the previous one
        spans.append((cursor, cursor + len(sentence)))
        parts.append(sentence)
        cursor += len(sentence)
    return " ".join(parts), tuple(spans)


def passage_id(title: str, text: str) -> str:
    """sha256(normalized_title + NUL + normalized_text), truncated to 16 hex chars."""
    payload = f"{normalize_title(title)}{NUL}{normalize_text(text)}".encode()
    return hashlib.sha256(payload).hexdigest()[:ID_LENGTH]


def text_hash(text: str) -> str:
    """sha256 over normalized text alone, for the exact-duplicate pass."""
    return hashlib.sha256(normalize_text(text).encode()).hexdigest()
