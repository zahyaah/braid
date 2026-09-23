"""Shared fixtures.

Ingest tests run against a hand-built stand-in for the HotpotQA dataset, so the
whole suite stays offline and fast. The one test that touches the real dataset
is marked `slow`.
"""

from __future__ import annotations

import pytest


class FakeDataset:
    """Minimal stand-in for a `datasets.Dataset`: len() and integer indexing."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, index: int) -> dict:
        return self._rows[index]


def make_row(
    question_id: str,
    question: str,
    answer: str,
    paragraphs: list[tuple[str, list[str]]],
    supporting: list[tuple[str, int]],
    level: str = "hard",
    qtype: str = "bridge",
) -> dict:
    return {
        "id": question_id,
        "question": question,
        "answer": answer,
        "level": level,
        "type": qtype,
        "context": {
            "title": [title for title, _ in paragraphs],
            "sentences": [sentences for _, sentences in paragraphs],
        },
        "supporting_facts": {
            "title": [title for title, _ in supporting],
            "sent_id": [sent_id for _, sent_id in supporting],
        },
    }


def paragraph(index: int, words: int = 12) -> tuple[str, list[str]]:
    """A deterministic, distinct paragraph."""
    body = " ".join(f"token{index}x{n}" for n in range(words))
    return (
        f"Title {index}",
        [f"Paragraph {index} opens here.", f"{body}.", f"Paragraph {index} closes here."],
    )


@pytest.fixture
def fake_dataset() -> FakeDataset:
    rows = []
    for q in range(12):
        paragraphs = [paragraph(q * 10 + p) for p in range(10)]
        rows.append(
            make_row(
                question_id=f"q{q:03d}",
                question=f"Question {q}?",
                answer=f"answer {q}",
                paragraphs=paragraphs,
                supporting=[(paragraphs[0][0], 0), (paragraphs[1][0], 1)],
            )
        )
    return FakeDataset(rows)


@pytest.fixture(scope="session")
def nlp():
    """en_core_web_sm: same dependency label scheme as en_core_web_trf
    (confirmed empirically), much faster to load for the test suite.
    """
    import spacy

    return spacy.load("en_core_web_sm")
