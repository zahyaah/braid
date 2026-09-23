"""The labeled evaluation set: queries, relevance judgments, and review records.

Acceptance criteria 1 through 4 rest entirely on this data. If the labels are
unsound, every number in Braid is unsound, so the types here are deliberately
strict and the validator that checks them is tested against broken fixtures.

Relevance is binary in every category (amendment 7, item 4). A multi-hop query
has several relevant passages, each with gain 1; it does not have graded gains.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Category = Literal["exact-term", "paraphrase", "multi-hop-relational"]
Origin = Literal["hotpotqa", "agent-drafted"]
Disposition = Literal["accepted", "edited", "rejected"]

CATEGORIES: tuple[Category, ...] = ("exact-term", "paraphrase", "multi-hop-relational")
DRAFTED_CATEGORIES: tuple[Category, ...] = ("exact-term", "paraphrase")
RELEVANT_GAIN = 1

QUERIES_FILE = "queries.jsonl"
REVIEW_FILE = "review.jsonl"
MANIFEST_FILE = "queryset-manifest.json"
QUERYSET_DIR = Path("braid/eval/queryset")


@dataclass(frozen=True)
class LabeledQuery:
    query_id: str
    text: str
    category: Category
    relevant: dict[str, int]
    origin: Origin
    source_question_id: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "text": self.text,
            "category": self.category,
            "relevant": dict(sorted(self.relevant.items())),
            "origin": self.origin,
            "source_question_id": self.source_question_id,
        }

    @classmethod
    def from_json(cls, row: dict[str, Any]) -> LabeledQuery:
        return cls(
            query_id=row["query_id"],
            text=row["text"],
            category=row["category"],
            relevant={pid: int(gain) for pid, gain in row["relevant"].items()},
            origin=row["origin"],
            source_question_id=row.get("source_question_id"),
        )


@dataclass(frozen=True)
class OverlapOverride:
    """A reviewer's decision to ship a paraphrase draft that fails the overlap check.

    Data, not prose: the validator reads it, and the README reports the count.
    """

    reviewer: str
    overridden_at: str
    reason: str
    shared_terms: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "reviewer": self.reviewer,
            "overridden_at": self.overridden_at,
            "reason": self.reason,
            "shared_terms": list(self.shared_terms),
        }

    @classmethod
    def from_json(cls, row: dict[str, Any]) -> OverlapOverride:
        return cls(
            reviewer=row["reviewer"],
            overridden_at=row["overridden_at"],
            reason=row["reason"],
            shared_terms=tuple(row["shared_terms"]),
        )


@dataclass(frozen=True)
class ReviewRecord:
    """One human review of one agent-drafted query.

    `draft_text` is never overwritten by an edit: the difference between agent
    wording and shipped wording has to stay inspectable (decision D4).
    """

    query_id: str
    source_passage_id: str
    draft_text: str
    final_text: str
    reviewer: str
    reviewed_at: str
    disposition: Disposition
    reason: str = ""
    overlap_override: OverlapOverride | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "source_passage_id": self.source_passage_id,
            "draft_text": self.draft_text,
            "final_text": self.final_text,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at,
            "disposition": self.disposition,
            "reason": self.reason,
            "overlap_override": (
                self.overlap_override.to_json() if self.overlap_override else None
            ),
        }

    @classmethod
    def from_json(cls, row: dict[str, Any]) -> ReviewRecord:
        override = row.get("overlap_override")
        return cls(
            query_id=row["query_id"],
            source_passage_id=row["source_passage_id"],
            draft_text=row["draft_text"],
            final_text=row["final_text"],
            reviewer=row["reviewer"],
            reviewed_at=row["reviewed_at"],
            disposition=row["disposition"],
            reason=row.get("reason", ""),
            overlap_override=OverlapOverride.from_json(override) if override else None,
        )


@dataclass
class QuerySetManifest:
    """What the set was built against, and at what size it was locked.

    `corpus_hash` is the frozen corpus the judgments were authored against
    (decision D6). The validator fails if it no longer matches the corpus
    manifest, which is what stops labels drifting under a corpus change.
    """

    corpus_hash: str
    locked_size: int | None = None
    per_category_target: int | None = None
    counts: dict[str, int] = field(default_factory=dict)
    created_at: str | None = None
    size_locked_at: str | None = None
    notes: str = ""

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "corpus_hash": self.corpus_hash,
            "locked_size": self.locked_size,
            "per_category_target": self.per_category_target,
            "counts": dict(sorted(self.counts.items())),
            "created_at": self.created_at,
            "size_locked_at": self.size_locked_at,
            "notes": self.notes,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> QuerySetManifest:
        return cls(**json.loads(path.read_text(encoding="utf-8")))


def write_queries(path: Path, queries: list[LabeledQuery]) -> None:
    from braid.ingest.models import write_jsonl

    write_jsonl(path, sorted(queries, key=lambda q: q.query_id))


def read_queries(path: Path) -> list[LabeledQuery]:
    from braid.ingest.models import read_jsonl

    return [LabeledQuery.from_json(row) for row in read_jsonl(path)]


def write_reviews(path: Path, reviews: list[ReviewRecord]) -> None:
    from braid.ingest.models import write_jsonl

    write_jsonl(path, sorted(reviews, key=lambda r: r.query_id))


def read_reviews(path: Path) -> list[ReviewRecord]:
    from braid.ingest.models import read_jsonl

    return [ReviewRecord.from_json(row) for row in read_jsonl(path)]
