"""HotpotQA loader and seeded sampler.

Sampling starts from questions, not paragraphs: for each sampled question we
pull its gold *and* distractor paragraphs, so no multi-hop question ever lands
in the corpus with missing evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from braid.ingest.models import HOTPOTQA_SOURCE, Passage, Question
from braid.ingest.normalize import join_sentences, normalize_text, passage_id

DATASET = "hotpotqa/hotpot_qa"
CONFIG = "distractor"
SPLIT = "validation"
DEFAULT_SEED = 20260923
DEFAULT_TARGET_PASSAGES = 1000


@dataclass
class SampleReport:
    questions_sampled: int = 0
    questions_skipped: int = 0
    passages_seen: int = 0
    skipped_reasons: dict[str, int] = field(default_factory=dict)

    def skip(self, reason: str) -> None:
        self.questions_skipped += 1
        self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + 1


def _build_passages(row: dict[str, Any]) -> dict[str, tuple[Passage, dict[int, int]]]:
    """One passage per context paragraph, keyed by normalized title.

    The second element maps HotpotQA's original sentence index to the index of
    that sentence's span in the passage. They differ whenever a source sentence
    normalizes to the empty string and is dropped.
    """
    built: dict[str, tuple[Passage, dict[int, int]]] = {}
    for title, sentences in zip(row["context"]["title"], row["context"]["sentences"], strict=True):
        text, spans = join_sentences(list(sentences))
        if not text:
            continue
        index_map: dict[int, int] = {}
        kept = 0
        for original_index, sentence in enumerate(sentences):
            if normalize_text(sentence):
                index_map[original_index] = kept
                kept += 1
        passage = Passage(
            passage_id=passage_id(title, text),
            title=normalize_text(title),
            text=text,
            sentence_spans=spans,
            source=HOTPOTQA_SOURCE,
        )
        built[normalize_text(title)] = (passage, index_map)
    return built


def _build_question(row: dict[str, Any], built: dict[str, tuple[Passage, dict[int, int]]]):
    """Resolve a question's supporting facts to passage ids. Returns None if unresolvable."""
    supporting_ids: list[str] = []
    supporting_sentences: list[tuple[str, int]] = []
    facts = row["supporting_facts"]
    for title, sent_id in zip(facts["title"], facts["sent_id"], strict=True):
        key = normalize_text(title)
        entry = built.get(key)
        if entry is None:
            return None, "supporting title missing from context"
        passage, index_map = entry
        if passage.passage_id not in supporting_ids:
            supporting_ids.append(passage.passage_id)
        mapped = index_map.get(int(sent_id))
        if mapped is None:
            # HotpotQA carries a few supporting facts pointing past the end of
            # their paragraph. Keep the passage, drop the sentence pointer.
            continue
        supporting_sentences.append((passage.passage_id, mapped))
    if not supporting_ids:
        return None, "no resolvable supporting passages"
    question = Question(
        question_id=row["id"],
        text=normalize_text(row["question"]),
        answer=normalize_text(row["answer"]),
        supporting_passage_ids=tuple(supporting_ids),
        supporting_sentences=tuple(supporting_sentences),
        level=row["level"],
        qtype=row["type"],
    )
    return question, None


def sample(
    dataset,
    seed: int = DEFAULT_SEED,
    target_passages: int = DEFAULT_TARGET_PASSAGES,
) -> tuple[list[Passage], list[Question], SampleReport]:
    """Sample questions in a seeded order until the corpus reaches `target_passages`."""
    report = SampleReport()
    order = np.random.default_rng(seed).permutation(len(dataset))
    passages: dict[str, Passage] = {}
    questions: list[Question] = []

    for index in order:
        if len(passages) >= target_passages:
            break
        row = dataset[int(index)]
        built = _build_passages(row)
        question, reason = _build_question(row, built)
        if question is None:
            report.skip(reason)
            continue
        for passage, _ in built.values():
            passages.setdefault(passage.passage_id, passage)
        questions.append(question)
        report.questions_sampled += 1

    report.passages_seen = len(passages)
    ordered_passages = sorted(passages.values(), key=lambda p: p.passage_id)
    return ordered_passages, questions, report


def load_hotpotqa(split: str = SPLIT):
    from datasets import load_dataset

    return load_dataset(DATASET, CONFIG, split=split)
