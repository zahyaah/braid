"""Build the multi-hop-relational category from HotpotQA's own labeled questions.

These queries are not drafted and not reviewed: they come from the dataset, and
their relevance judgments are HotpotQA's supporting-fact annotations resolved
to frozen passage IDs. That is the whole reason the multi-hop category is not
hand invented.

Relevance is binary (amendment 7, item 4): every supporting paragraph carries
gain 1.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from braid.eval.queryset.schema import (
    MANIFEST_FILE,
    QUERIES_FILE,
    QUERYSET_DIR,
    RELEVANT_GAIN,
    LabeledQuery,
    QuerySetManifest,
    read_queries,
    write_queries,
)
from braid.ingest.freeze import FrozenCorpusError
from braid.ingest.manifest import Manifest, utc_now
from braid.ingest.models import Question, load_questions

DEFAULT_QUESTIONS = Path("data/questions.jsonl")
DEFAULT_CORPUS_MANIFEST = Path("data/manifest.json")
QUERY_ID_PREFIX = "mh"


def to_labeled(question: Question) -> LabeledQuery:
    return LabeledQuery(
        query_id=f"{QUERY_ID_PREFIX}-{question.question_id}",
        text=question.text,
        category="multi-hop-relational",
        relevant={pid: RELEVANT_GAIN for pid in question.supporting_passage_ids},
        origin="hotpotqa",
        source_question_id=question.question_id,
    )


def build(questions: list[Question], limit: int | None = None) -> list[LabeledQuery]:
    """Convert questions to labeled queries, in a stable order.

    Questions with fewer than two supporting passages are skipped: they are not
    multi-hop, and the corpus build already drops the ones that collapsed.
    """
    ordered = sorted(questions, key=lambda q: q.question_id)
    queries = [
        to_labeled(question)
        for question in ordered
        if len(set(question.supporting_passage_ids)) >= 2
    ]
    return queries[:limit] if limit is not None else queries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="braid.eval.queryset.build_multihop")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--corpus-manifest", type=Path, default=DEFAULT_CORPUS_MANIFEST)
    parser.add_argument("--dir", type=Path, default=QUERYSET_DIR)
    parser.add_argument("--limit", type=int, default=None, help="cap at the locked category size")
    args = parser.parse_args(argv)

    corpus_manifest = Manifest.read(args.corpus_manifest)
    if not corpus_manifest.frozen:
        raise FrozenCorpusError(
            "corpus is not frozen; judgments may not be authored yet (decision D6). "
            "Run: python -m braid.ingest freeze"
        )

    questions = load_questions(args.questions)
    built = build(questions, limit=args.limit)

    queries_path = args.dir / QUERIES_FILE
    existing = read_queries(queries_path) if queries_path.exists() else []
    kept = [query for query in existing if query.category != "multi-hop-relational"]
    write_queries(queries_path, kept + built)

    manifest_path = args.dir / MANIFEST_FILE
    if manifest_path.exists():
        manifest = QuerySetManifest.read(manifest_path)
        manifest.corpus_hash = corpus_manifest.corpus_hash
    else:
        manifest = QuerySetManifest(
            corpus_hash=corpus_manifest.corpus_hash,
            created_at=utc_now(),
        )
    manifest.counts = {"multi-hop-relational": len(built)}
    manifest.write(manifest_path)

    skipped = len(questions) - len(build(questions))
    print(
        f"multi-hop queries: {len(built)} written "
        f"(from {len(questions)} questions, {skipped} skipped as not multi-hop); "
        f"corpus_hash {manifest.corpus_hash}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
