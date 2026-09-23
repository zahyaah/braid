"""Corpus data model and JSONL round-tripping.

Every other module addresses passages by `Passage.passage_id`, so these types
and their serialization are the contract the rest of Braid is written against.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HOTPOTQA_SOURCE = "hotpotqa/distractor/validation"


@dataclass(frozen=True)
class Passage:
    """One HotpotQA paragraph. One passage is one chunk; there is no sub-chunking."""

    passage_id: str
    title: str
    text: str
    sentence_spans: tuple[tuple[int, int], ...]
    source: str = HOTPOTQA_SOURCE

    def sentence(self, index: int) -> str:
        start, end = self.sentence_spans[index]
        return self.text[start:end]

    def to_json(self) -> dict[str, Any]:
        return {
            "passage_id": self.passage_id,
            "title": self.title,
            "text": self.text,
            "sentence_spans": [list(span) for span in self.sentence_spans],
            "source": self.source,
        }

    @classmethod
    def from_json(cls, row: dict[str, Any]) -> Passage:
        return cls(
            passage_id=row["passage_id"],
            title=row["title"],
            text=row["text"],
            sentence_spans=tuple((int(a), int(b)) for a, b in row["sentence_spans"]),
            source=row["source"],
        )


@dataclass(frozen=True)
class Question:
    """A HotpotQA question with its supporting evidence resolved to passage IDs."""

    question_id: str
    text: str
    answer: str
    supporting_passage_ids: tuple[str, ...]
    supporting_sentences: tuple[tuple[str, int], ...]
    level: str
    qtype: str

    def to_json(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "text": self.text,
            "answer": self.answer,
            "supporting_passage_ids": list(self.supporting_passage_ids),
            "supporting_sentences": [[pid, idx] for pid, idx in self.supporting_sentences],
            "level": self.level,
            "qtype": self.qtype,
        }

    @classmethod
    def from_json(cls, row: dict[str, Any]) -> Question:
        return cls(
            question_id=row["question_id"],
            text=row["text"],
            answer=row["answer"],
            supporting_passage_ids=tuple(row["supporting_passage_ids"]),
            supporting_sentences=tuple((pid, int(idx)) for pid, idx in row["supporting_sentences"]),
            level=row["level"],
            qtype=row["qtype"],
        )


def write_jsonl(path: Path, rows: Iterable[Any]) -> int:
    """Write records as JSONL. Returns the row count.

    Keys are sorted and separators fixed so that two runs producing the same
    records produce byte-identical files, which Task 5 asserts.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            payload = row.to_json() if hasattr(row, "to_json") else row
            handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False))
            handle.write("\n")
            count += 1
    return count


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def load_corpus(path: Path) -> list[Passage]:
    return [Passage.from_json(row) for row in read_jsonl(path)]


def load_questions(path: Path) -> list[Question]:
    return [Question.from_json(row) for row in read_jsonl(path)]
