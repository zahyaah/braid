"""Deduplication, and the guard that protects multi-hop ground truth.

Two passes, in order:

1. Exact duplicates, by sha256 over normalized text.
2. Near duplicates, by Jaccard similarity over word 3-gram shingles at
   `JACCARD_THRESHOLD`.

The near-duplicate pass is exact rather than a MinHash estimate. At this corpus
size (500-1,000 passages) exact Jaccard is cheap, because
`jaccard(A, B) >= t` implies `min(|A|,|B|) / max(|A|,|B|) >= t`: sorting by
shingle-set size and comparing only within that size band prunes almost every
pair without discarding a single true duplicate. See SPEC-ingest.md for why
this replaced the MinHash/LSH formulation.

Removing a passage that some question depends on would silently corrupt
multi-hop ground truth, so `remap_questions` either remaps the question to the
surviving duplicate or drops the question, and counts which happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from braid.ingest.models import Passage, Question
from braid.ingest.normalize import text_hash

JACCARD_THRESHOLD = 0.9
SHINGLE_SIZE = 3


@dataclass
class DedupeReport:
    passages_in: int = 0
    exact_removed: int = 0
    near_removed: int = 0
    passages_out: int = 0
    # removed passage id -> surviving passage id
    replacements: dict[str, str] = field(default_factory=dict)
    # Every removal, by title. A reviewer needs to see *what* was dropped, not
    # just how many, so this is not truncated.
    removals: list[dict[str, object]] = field(default_factory=list)

    def to_json(self) -> dict[str, object]:
        return {
            "passages_in": self.passages_in,
            "exact_removed": self.exact_removed,
            "near_removed": self.near_removed,
            "passages_out": self.passages_out,
            "removals": self.removals,
        }


@dataclass
class RemapReport:
    questions_in: int = 0
    questions_remapped: int = 0
    questions_dropped_missing: int = 0
    questions_dropped_collapsed: int = 0
    questions_out: int = 0

    @property
    def questions_dropped(self) -> int:
        return self.questions_dropped_missing + self.questions_dropped_collapsed

    def to_json(self) -> dict[str, object]:
        return {
            "questions_in": self.questions_in,
            "questions_remapped": self.questions_remapped,
            "questions_dropped_missing": self.questions_dropped_missing,
            "questions_dropped_collapsed": self.questions_dropped_collapsed,
            "questions_out": self.questions_out,
        }


def shingles(text: str, size: int = SHINGLE_SIZE) -> frozenset[tuple[str, ...]]:
    """Word n-gram shingles. Short texts yield one shingle of the whole text."""
    words = text.lower().split()
    if not words:
        return frozenset()
    if len(words) <= size:
        return frozenset({tuple(words)})
    return frozenset(tuple(words[i : i + size]) for i in range(len(words) - size + 1))


def jaccard(left: frozenset, right: frozenset) -> float:
    if not left and not right:
        return 1.0
    union = len(left | right)
    return len(left & right) / union if union else 0.0


class _Union:
    def __init__(self, keys: list[str]) -> None:
        self._parent = {key: key for key in keys}

    def find(self, key: str) -> str:
        while self._parent[key] != key:
            self._parent[key] = self._parent[self._parent[key]]
            key = self._parent[key]
        return key

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            # Lexicographically smallest id wins, so clustering is deterministic.
            low, high = sorted((left_root, right_root))
            self._parent[high] = low


def dedupe(
    passages: list[Passage], threshold: float = JACCARD_THRESHOLD
) -> tuple[list[Passage], DedupeReport]:
    report = DedupeReport(passages_in=len(passages))
    by_id = {passage.passage_id: passage for passage in passages}
    ordered = sorted(by_id.values(), key=lambda p: p.passage_id)

    # Pass 1: exact duplicates on normalized text.
    survivors: dict[str, Passage] = {}
    seen_text: dict[str, str] = {}
    for passage in ordered:
        digest = text_hash(passage.text)
        kept_id = seen_text.get(digest)
        if kept_id is None:
            seen_text[digest] = passage.passage_id
            survivors[passage.passage_id] = passage
        else:
            report.exact_removed += 1
            report.replacements[passage.passage_id] = kept_id
            report.removals.append(
                {
                    "kind": "exact",
                    "removed_id": passage.passage_id,
                    "removed_title": passage.title,
                    "kept_id": kept_id,
                    "kept_title": survivors[kept_id].title,
                    "jaccard": 1.0,
                }
            )

    # Pass 2: near duplicates, exact Jaccard inside a size band.
    ids = sorted(survivors)
    fingerprints = {pid: shingles(survivors[pid].text) for pid in ids}
    by_size = sorted(ids, key=lambda pid: (len(fingerprints[pid]), pid))
    union = _Union(ids)
    for i, left_id in enumerate(by_size):
        left = fingerprints[left_id]
        if not left:
            continue
        ceiling = len(left) / threshold
        for right_id in by_size[i + 1 :]:
            right = fingerprints[right_id]
            if len(right) > ceiling:
                break  # sorted by size, so every later candidate is too large
            if jaccard(left, right) >= threshold:
                union.union(left_id, right_id)

    kept: list[Passage] = []
    for pid in ids:
        root = union.find(pid)
        if root == pid:
            kept.append(survivors[pid])
        else:
            report.near_removed += 1
            report.replacements[pid] = root
            report.removals.append(
                {
                    "kind": "near",
                    "removed_id": pid,
                    "removed_title": survivors[pid].title,
                    "kept_id": root,
                    "kept_title": survivors[root].title,
                    "jaccard": round(jaccard(fingerprints[pid], fingerprints[root]), 4),
                }
            )

    # A removed passage may point at a passage that was itself removed; collapse
    # the chains so every replacement lands on a surviving id.
    kept_ids = {passage.passage_id for passage in kept}
    for removed_id in list(report.replacements):
        target = report.replacements[removed_id]
        while target not in kept_ids and target in report.replacements:
            target = report.replacements[target]
        report.replacements[removed_id] = target

    report.passages_out = len(kept)
    return kept, report


def remap_questions(
    questions: list[Question],
    replacements: dict[str, str],
    kept_ids: set[str],
) -> tuple[list[Question], RemapReport]:
    """Point questions at surviving passages, or drop them. Never leave a dangling id.

    Runs strictly before the corpus freeze. After the freeze, the same situation
    is escalated to the author as a judgment change (decision D6).
    """
    report = RemapReport(questions_in=len(questions))
    survivors: list[Question] = []
    for question in questions:
        resolved: list[str] = []
        remapped = False
        missing = False
        for pid in question.supporting_passage_ids:
            if pid in kept_ids:
                target = pid
            else:
                replacement = replacements.get(pid)
                if replacement is None or replacement not in kept_ids:
                    missing = True
                    break
                target = replacement
                remapped = True
            if target not in resolved:
                resolved.append(target)
        if missing:
            report.questions_dropped_missing += 1
            continue
        if len(resolved) < len(set(question.supporting_passage_ids)):
            # Two gold paragraphs collapsed into one. A 2-hop question with one
            # piece of evidence is no longer multi-hop, so it is dropped rather
            # than quietly reclassified.
            report.questions_dropped_collapsed += 1
            continue
        if remapped:
            report.questions_remapped += 1
            seen: set[tuple[str, int]] = set()
            sentences: list[tuple[str, int]] = []
            for pid, index in question.supporting_sentences:
                target = pid if pid in kept_ids else replacements.get(pid, pid)
                if (target, index) not in seen:
                    seen.add((target, index))
                    sentences.append((target, index))
            question = Question(
                question_id=question.question_id,
                text=question.text,
                answer=question.answer,
                supporting_passage_ids=tuple(resolved),
                supporting_sentences=tuple(sentences),
                level=question.level,
                qtype=question.qtype,
            )
        survivors.append(question)
    report.questions_out = len(survivors)
    return survivors, report


def assert_no_dangling(questions: list[Question], kept_ids: set[str]) -> None:
    """Dangling supporting-passage ids raise. They are never warned about."""
    for question in questions:
        for pid in question.supporting_passage_ids:
            if pid not in kept_ids:
                raise ValueError(
                    f"question {question.question_id} references missing passage {pid}"
                )
        for pid, _ in question.supporting_sentences:
            if pid not in kept_ids:
                raise ValueError(
                    f"question {question.question_id} references missing passage {pid} "
                    "in supporting_sentences"
                )
