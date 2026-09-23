"""Ingest CLI: build, add, freeze, verify.

    python -m braid.ingest build  --out data/corpus.jsonl
    python -m braid.ingest add    --seed 7
    python -m braid.ingest freeze
    python -m braid.ingest verify
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from braid.ingest import freeze as freeze_mod
from braid.ingest.dedupe import assert_no_dangling, dedupe, remap_questions
from braid.ingest.loader import (
    CONFIG,
    DATASET,
    DEFAULT_SEED,
    DEFAULT_TARGET_PASSAGES,
    SPLIT,
    load_hotpotqa,
    sample,
)
from braid.ingest.manifest import Manifest, utc_now
from braid.ingest.models import (
    Passage,
    load_corpus,
    load_questions,
    write_jsonl,
)

DEFAULT_CORPUS = Path("data/corpus.jsonl")
DEFAULT_QUESTIONS = Path("data/questions.jsonl")
DEFAULT_MANIFEST = Path("data/manifest.json")


def _datasets_version() -> str:
    import datasets

    return datasets.__version__


def cmd_build(args: argparse.Namespace) -> int:
    dataset = load_hotpotqa(args.split)
    passages, questions, sample_report = sample(
        dataset, seed=args.seed, target_passages=args.target
    )
    before = len(passages)
    kept, dedupe_report = dedupe(passages)
    kept_ids = {passage.passage_id for passage in kept}
    questions, remap_report = remap_questions(questions, dedupe_report.replacements, kept_ids)
    assert_no_dangling(questions, kept_ids)

    write_jsonl(args.out, kept)
    write_jsonl(args.questions, questions)
    manifest = Manifest(
        dataset=DATASET,
        config=CONFIG,
        split=args.split,
        datasets_version=_datasets_version(),
        seed=args.seed,
        target_passages=args.target,
        questions_sampled=sample_report.questions_sampled,
        questions_out=remap_report.questions_out,
        passages_before_dedupe=before,
        passages_after_dedupe=len(kept),
        dedupe=dedupe_report.to_json(),
        remap=remap_report.to_json(),
        corpus_hash=freeze_mod.corpus_hash(kept),
    )
    manifest.write(args.manifest)

    print(
        f"passages {before} -> {len(kept)} "
        f"(exact -{dedupe_report.exact_removed}, near -{dedupe_report.near_removed})"
    )
    print(
        f"questions {remap_report.questions_in} -> {remap_report.questions_out} "
        f"(remapped {remap_report.questions_remapped}, "
        f"dropped_missing {remap_report.questions_dropped_missing}, "
        f"dropped_collapsed {remap_report.questions_dropped_collapsed})"
    )
    for removal in dedupe_report.removals:
        print(
            f"  removed [{removal['kind']} j={removal['jaccard']}] "
            f"{removal['removed_title']!r} -> kept {removal['kept_title']!r}"
        )
    print(f"corpus_hash {manifest.corpus_hash}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    """Incremental add. Adds only new passages and changes no existing id."""
    manifest = Manifest.read(args.manifest)
    existing = load_corpus(args.out)
    existing_questions = load_questions(args.questions)
    existing_ids = {passage.passage_id for passage in existing}
    existing_question_ids = {question.question_id for question in existing_questions}
    before_hash = freeze_mod.corpus_hash(existing)

    dataset = load_hotpotqa(manifest.split)
    sampled, questions, _ = sample(dataset, seed=args.seed, target_passages=args.target)
    new_passages: list[Passage] = [p for p in sampled if p.passage_id not in existing_ids]
    new_questions = [q for q in questions if q.question_id not in existing_question_ids]

    combined = sorted(existing + new_passages, key=lambda p: p.passage_id)
    kept_ids = {passage.passage_id for passage in combined}
    # A frozen corpus still accepts new passages; it refuses changes to existing
    # ones, which is why nothing here rewrites an existing passage.
    new_questions, _ = remap_questions(new_questions, {}, kept_ids)
    all_questions = existing_questions + new_questions
    assert_no_dangling(all_questions, kept_ids)

    write_jsonl(args.out, combined)
    write_jsonl(args.questions, all_questions)

    after_hash = freeze_mod.corpus_hash(combined)
    manifest.passages_after_dedupe = len(combined)
    manifest.questions_out = len(all_questions)
    manifest.hash_history.append(
        {
            "at": utc_now(),
            "before": before_hash,
            "after": after_hash,
            "added": len(new_passages),
            "seed": args.seed,
        }
    )
    manifest.corpus_hash = after_hash
    manifest.write(args.manifest)
    print(f"added {len(new_passages)} passages, {len(new_questions)} questions; "
          f"corpus_hash {before_hash} -> {after_hash}")
    return 0


def cmd_freeze(args: argparse.Namespace) -> int:
    passages = load_corpus(args.out)
    manifest = freeze_mod.freeze(args.manifest, passages)
    print(f"frozen at {manifest.frozen_at}; corpus_hash {manifest.corpus_hash}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    freeze_mod.verify(args.manifest, load_corpus(args.out))
    print("corpus matches the frozen hash")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="braid.ingest")
    parser.add_argument("--out", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="sample, dedupe, and write the corpus")
    build.add_argument("--seed", type=int, default=DEFAULT_SEED)
    build.add_argument("--target", type=int, default=DEFAULT_TARGET_PASSAGES)
    build.add_argument("--split", default=SPLIT)
    build.set_defaults(func=cmd_build)

    add = sub.add_parser("add", help="incrementally add new passages")
    add.add_argument("--seed", type=int, required=True)
    add.add_argument("--target", type=int, default=DEFAULT_TARGET_PASSAGES)
    add.set_defaults(func=cmd_add)

    sub.add_parser("freeze", help="record the content hash and freeze").set_defaults(
        func=cmd_freeze
    )
    sub.add_parser("verify", help="check the corpus against the frozen hash").set_defaults(
        func=cmd_verify
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
