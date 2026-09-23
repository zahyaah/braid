"""Extraction data model.

`Triple` is the pipeline's final output; `RawTriple` is what the pattern
matchers in patterns.py produce before entity normalization (entities.py)
resolves surface text to canonical entity names and attaches types from NER.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RawTriple:
    """A pattern match before entity normalization. Subject/object are surface
    text spans, not yet resolved to canonical entity names.
    """

    subject_text: str
    relation: str
    object_text: str
    sentence_index: int
    pattern: str  # which documented pattern produced this (README.md, Task 19)


@dataclass(frozen=True)
class Triple:
    """The pipeline's final output, written to data/triples.jsonl."""

    subject: str
    relation: str
    object: str
    passage_id: str
    sentence_index: int
    subject_type: str | None
    object_type: str | None
    pattern: str

    def to_json(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "relation": self.relation,
            "object": self.object,
            "passage_id": self.passage_id,
            "sentence_index": self.sentence_index,
            "subject_type": self.subject_type,
            "object_type": self.object_type,
            "pattern": self.pattern,
        }

    @classmethod
    def from_json(cls, row: dict[str, Any]) -> Triple:
        return cls(
            subject=row["subject"],
            relation=row["relation"],
            object=row["object"],
            passage_id=row["passage_id"],
            sentence_index=row["sentence_index"],
            subject_type=row.get("subject_type"),
            object_type=row.get("object_type"),
            pattern=row.get("pattern", ""),
        )
