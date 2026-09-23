"""Retrieval metrics: recall@k, nDCG@10, MRR.

Relevance is binary in every category (amendment 7, item 4). A multi-hop
query simply has several relevant passages, each with gain 1 -- there are no
graded gains anywhere in this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RankedHit:
    """The minimal shape a metric needs: a passage id and its rank (1-indexed)."""

    passage_id: str
    rank: int
    score: float = 0.0


def _ties_broken(hits: list[RankedHit]) -> list[RankedHit]:
    """Stable sort by (score desc, passage_id asc) so ties resolve deterministically."""
    ordered = sorted(hits, key=lambda h: (-h.score, h.passage_id))
    return [RankedHit(h.passage_id, i + 1, h.score) for i, h in enumerate(ordered)]


def recall_at_k(hits: list[RankedHit], relevant: dict[str, int], k: int) -> float:
    """Fraction of relevant passages present in the top k. 1.0 if there are none to find."""
    if not relevant:
        return 1.0
    top_k_ids = {h.passage_id for h in hits if h.rank <= k}
    found = sum(1 for pid in relevant if pid in top_k_ids)
    return found / len(relevant)


def mrr(hits: list[RankedHit], relevant: dict[str, int]) -> float:
    """Reciprocal rank of the first relevant hit; 0.0 if none appear."""
    for hit in sorted(hits, key=lambda h: h.rank):
        if hit.passage_id in relevant:
            return 1.0 / hit.rank
    return 0.0


def _dcg(gains: list[int]) -> float:
    return sum(gain / math.log2(i + 2) for i, gain in enumerate(gains))


def ndcg_at_k(hits: list[RankedHit], relevant: dict[str, int], k: int) -> float:
    """nDCG@k. IDCG is built from the query's own ideal ranking: its n relevant
    passages (all gain 1, since relevance is binary everywhere) placed in the
    first n positions, capped at k.
    """
    if not relevant:
        return 1.0
    ordered = sorted(hits, key=lambda h: h.rank)[:k]
    gains = [relevant.get(h.passage_id, 0) for h in ordered]
    dcg = _dcg(gains)
    ideal_gains = [1] * min(len(relevant), k)
    idcg = _dcg(ideal_gains)
    return dcg / idcg if idcg > 0 else 0.0
