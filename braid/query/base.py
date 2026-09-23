"""The Retriever interface: designed once, called identically by the CLI and by
`eval` (SPEC-query.md). Every configuration under test implements this and
nothing more.

This file is interface-only by design: the `Retriever` Protocol and `Hit`
dataclass below, no concrete retrieval logic. It is the whitelisted exception
to Checkpoint B's "no retrieval code before the query set is reviewed" rule
(amendment 7, item 1) -- a mechanical check, since neither body goes past `...`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Hit:
    passage_id: str
    score: float
    rank: int
    # Per-source contribution, e.g. {"bm25": .., "dense": .., "graph": ..}
    provenance: dict[str, float]


class Retriever(Protocol):
    name: str

    def search(self, query: str, k: int) -> list[Hit]: ...
