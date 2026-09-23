"""Structural validation of the labeled query set.

Run as `python -m braid.eval.queryset validate`. Exits non-zero on any problem
and prints every problem it found, not just the first: a half-valid query set
is not a thing worth iterating on one error at a time.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from braid.eval.queryset.overlap import shared_terms
from braid.eval.queryset.schema import (
    CATEGORIES,
    DRAFTED_CATEGORIES,
    MANIFEST_FILE,
    QUERIES_FILE,
    QUERYSET_DIR,
    RELEVANT_GAIN,
    REVIEW_FILE,
    LabeledQuery,
    QuerySetManifest,
    ReviewRecord,
    read_queries,
    read_reviews,
)
from braid.ingest.manifest import Manifest
from braid.ingest.models import Passage, load_corpus

DEFAULT_CORPUS = Path("data/corpus.jsonl")
DEFAULT_CORPUS_MANIFEST = Path("data/manifest.json")
VALID_DISPOSITIONS = {"accepted", "edited", "rejected"}


def _check_corpus_binding(
    manifest: QuerySetManifest, corpus_manifest: Manifest, problems: list[str]
) -> None:
    if not corpus_manifest.frozen:
        problems.append(
            "corpus is not frozen: judgments may not be authored against a corpus "
            "that can still move (decision D6)"
        )
    if manifest.corpus_hash != corpus_manifest.corpus_hash:
        problems.append(
            f"corpus_hash mismatch: query set was authored against "
            f"{manifest.corpus_hash}, corpus is now {corpus_manifest.corpus_hash}"
        )


def _check_query(query: LabeledQuery, passages: dict[str, Passage], problems: list[str]) -> None:
    where = f"query {query.query_id}"
    if query.category not in CATEGORIES:
        problems.append(f"{where}: unknown category {query.category!r}")
        return
    if not query.text.strip():
        problems.append(f"{where}: empty text")
    if not query.relevant:
        problems.append(f"{where}: no relevant passages")
    for passage_id, gain in query.relevant.items():
        if passage_id not in passages:
            problems.append(f"{where}: relevant passage {passage_id} is not in the corpus")
        if gain != RELEVANT_GAIN:
            problems.append(
                f"{where}: gain {gain} for {passage_id}; relevance is binary in every "
                "category (amendment 7, item 4)"
            )

    if query.category == "multi-hop-relational":
        if query.origin != "hotpotqa":
            problems.append(f"{where}: multi-hop queries come from HotpotQA, not {query.origin!r}")
        if not query.source_question_id:
            problems.append(f"{where}: multi-hop query has no source_question_id")
        if len(query.relevant) < 2:
            problems.append(
                f"{where}: multi-hop query has {len(query.relevant)} relevant passage(s); "
                "a question with one piece of evidence is not multi-hop"
            )
    else:
        if query.origin != "agent-drafted":
            problems.append(
                f"{where}: {query.category} queries are agent-drafted, not {query.origin!r}"
            )
        if len(query.relevant) != 1:
            problems.append(
                f"{where}: {query.category} query has {len(query.relevant)} relevant "
                "passages; expected exactly 1, or a label explaining why"
            )


def _check_review(
    query: LabeledQuery,
    review: ReviewRecord | None,
    passages: dict[str, Passage],
    problems: list[str],
) -> None:
    where = f"query {query.query_id}"
    if query.category not in DRAFTED_CATEGORIES:
        if review is not None:
                problems.append(
                f"{where}: multi-hop queries are not drafted and need no review record"
            )
        return
    if review is None:
        problems.append(f"{where}: no review record; every drafted query is human-reviewed (D4)")
        return
    if review.disposition not in VALID_DISPOSITIONS:
        problems.append(f"{where}: unknown disposition {review.disposition!r}")
    if review.disposition in {"edited", "rejected"} and not review.reason.strip():
        problems.append(f"{where}: disposition {review.disposition!r} requires a reason")
    if not review.reviewer.strip() or not review.reviewed_at.strip():
        problems.append(f"{where}: review record is missing a reviewer or a timestamp")
    if not review.draft_text.strip():
        problems.append(f"{where}: review record has no draft_text; the agent wording must survive")
    if review.final_text != query.text:
        problems.append(f"{where}: review final_text does not match the shipped query text")
    if review.source_passage_id not in passages:
        problems.append(
            f"{where}: review source_passage_id {review.source_passage_id} "
            "is not in the corpus"
        )


def _check_paraphrase_overlap(
    query: LabeledQuery,
    review: ReviewRecord | None,
    passages: dict[str, Passage],
    problems: list[str],
) -> None:
    if query.category != "paraphrase":
        return
    for passage_id in query.relevant:
        passage = passages.get(passage_id)
        if passage is None:
            continue
        shared = shared_terms(query.text, passage.text)
        if not shared:
            continue
        override = review.overlap_override if review else None
        if override is None:
            problems.append(
                f"query {query.query_id}: paraphrase shares content words with its target "
                f"passage {sorted(shared)} and carries no reviewer override"
            )
        elif set(override.shared_terms) != set(shared):
            problems.append(
                f"query {query.query_id}: override lists {sorted(override.shared_terms)} "
                f"but the check flags {sorted(shared)}"
            )


def _check_balance(
    manifest: QuerySetManifest, queries: list[LabeledQuery], problems: list[str]
) -> None:
    counts = {category: 0 for category in CATEGORIES}
    for query in queries:
        if query.category in counts:
            counts[query.category] += 1
    if manifest.per_category_target is None:
        return
    for category, count in counts.items():
        if count != manifest.per_category_target:
            problems.append(
                f"category {category} has {count} queries; the locked size requires "
                f"{manifest.per_category_target}"
            )
    if manifest.locked_size is not None and sum(counts.values()) != manifest.locked_size:
        problems.append(
            f"query set has {sum(counts.values())} queries; locked size is {manifest.locked_size}"
        )


def validate(
    queryset_dir: Path = QUERYSET_DIR,
    corpus_path: Path = DEFAULT_CORPUS,
    corpus_manifest_path: Path = DEFAULT_CORPUS_MANIFEST,
) -> list[str]:
    problems: list[str] = []
    manifest = QuerySetManifest.read(queryset_dir / MANIFEST_FILE)
    corpus_manifest = Manifest.read(corpus_manifest_path)
    passages = {passage.passage_id: passage for passage in load_corpus(corpus_path)}

    _check_corpus_binding(manifest, corpus_manifest, problems)

    queries = read_queries(queryset_dir / QUERIES_FILE)
    review_path = queryset_dir / REVIEW_FILE
    reviews = read_reviews(review_path) if review_path.exists() else []
    by_query: dict[str, ReviewRecord] = {}
    for review in reviews:
        if review.query_id in by_query:
            problems.append(f"query {review.query_id}: more than one review record")
        by_query[review.query_id] = review

    seen: set[str] = set()
    for query in queries:
        if query.query_id in seen:
            problems.append(f"query {query.query_id}: duplicate query_id")
        seen.add(query.query_id)
        _check_query(query, passages, problems)
        review = by_query.get(query.query_id)
        _check_review(query, review, passages, problems)
        _check_paraphrase_overlap(query, review, passages, problems)

    for query_id in by_query:
        if query_id not in seen:
            problems.append(f"review record {query_id}: no such query")

    _check_balance(manifest, queries, problems)
    return problems


def summarize(queryset_dir: Path = QUERYSET_DIR) -> dict[str, int]:
    queries = read_queries(queryset_dir / QUERIES_FILE)
    counts = {category: 0 for category in CATEGORIES}
    for query in queries:
        counts[query.category] = counts.get(query.category, 0) + 1
    review_path = queryset_dir / REVIEW_FILE
    reviews = read_reviews(review_path) if review_path.exists() else []
    counts["reviewed"] = len(reviews)
    counts["overlap_overrides"] = sum(1 for r in reviews if r.overlap_override is not None)
    counts["total"] = len(queries)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="braid.eval.queryset")
    parser.add_argument("command", choices=["validate", "summary"])
    parser.add_argument("--dir", type=Path, default=QUERYSET_DIR)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--corpus-manifest", type=Path, default=DEFAULT_CORPUS_MANIFEST)
    args = parser.parse_args(argv)

    if args.command == "summary":
        for key, value in sorted(summarize(args.dir).items()):
            print(f"{key}: {value}")
        return 0

    problems = validate(args.dir, args.corpus, args.corpus_manifest)
    for problem in problems:
        print(f"FAIL {problem}")
    if problems:
        print(f"{len(problems)} problem(s)")
        return 1
    counts = summarize(args.dir)
    print(f"query set valid: {counts['total']} queries, {counts['reviewed']} reviewed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
