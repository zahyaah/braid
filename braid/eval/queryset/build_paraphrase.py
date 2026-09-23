"""Build the paraphrase category: agent-drafted queries describing a passage
without reusing its vocabulary.

Sampling is disjoint from passages already used as exact-term targets or as
multi-hop supporting evidence, so the eval set's passage coverage is spread
across categories rather than concentrated on a handful of popular passages.
This is a design choice, not a spec requirement, and is recorded here.

Draft text is supplied by the caller (`drafts`), keyed by passage_id, because
writing an accurate paraphrase requires reading and understanding the passage
-- exactly the part of Task 11 that is not mechanical. The overlap check
(`overlap.passes`) is enforced here regardless of where the text came from.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from braid.eval.queryset.overlap import shared_terms
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
from braid.ingest.manifest import Manifest
from braid.ingest.models import Passage, load_corpus

DEFAULT_CORPUS = Path("data/corpus.jsonl")
DEFAULT_CORPUS_MANIFEST = Path("data/manifest.json")
QUERY_ID_PREFIX = "pp"
DEFAULT_SEED = 20260923


def used_passage_ids(existing: list[LabeledQuery]) -> set[str]:
    """Passages already targeted by exact-term drafts or multi-hop evidence."""
    used: set[str] = set()
    for query in existing:
        if query.category in {"exact-term", "multi-hop-relational"}:
            used.update(query.relevant)
    return used


def sample_passages(
    corpus: list[Passage], exclude: set[str], limit: int, seed: int = DEFAULT_SEED
) -> list[Passage]:
    """Deterministic sample of passages not already used elsewhere in the query set."""
    eligible = [p for p in corpus if p.passage_id not in exclude]
    eligible.sort(key=lambda p: p.passage_id)
    order = np.random.default_rng(seed).permutation(len(eligible))
    return [eligible[int(i)] for i in order[:limit]]


def check_overlap(text: str, passage: Passage) -> tuple[str, ...]:
    return shared_terms(text, passage.text)


def build(
    passages: list[Passage], drafts: dict[str, str]
) -> tuple[list[LabeledQuery], dict[str, tuple[str, ...]]]:
    """Assemble LabeledQuery records from a passage list and a drafts dict.

    Returns (queries, failures), where failures maps passage_id to the shared
    content words for any draft that still fails the overlap check -- those
    need a rewrite or a reviewer override (Task 12), not a silent pass.
    """
    queries: list[LabeledQuery] = []
    failures: dict[str, tuple[str, ...]] = {}
    for passage in passages:
        text = drafts.get(passage.passage_id)
        if text is None:
            continue
        shared = check_overlap(text, passage)
        if shared:
            failures[passage.passage_id] = shared
        queries.append(
            LabeledQuery(
                query_id=f"{QUERY_ID_PREFIX}-{passage.passage_id}",
                text=text,
                category="paraphrase",
                relevant={passage.passage_id: RELEVANT_GAIN},
                origin="agent-drafted",
            )
        )
    return queries, failures


def cmd_sample(args: argparse.Namespace) -> int:
    """Print the sampled passages as a worksheet for drafting."""
    corpus_manifest = Manifest.read(args.corpus_manifest)
    if not corpus_manifest.frozen:
        raise FrozenCorpusError("corpus is not frozen (decision D6)")
    corpus = load_corpus(args.corpus)
    queries_path = args.dir / QUERIES_FILE
    existing = read_queries(queries_path) if queries_path.exists() else []
    exclude = used_passage_ids(existing)
    sampled = sample_passages(corpus, exclude, args.limit, args.seed)
    worksheet = [{"passage_id": p.passage_id, "title": p.title, "text": p.text} for p in sampled]
    payload = json.dumps(worksheet, indent=2, ensure_ascii=False) + "\n"
    args.out.write_text(payload, encoding="utf-8")
    print(f"sampled {len(sampled)} passages -> {args.out}")
    return 0


def cmd_write(args: argparse.Namespace) -> int:
    """Merge a completed drafts file (passage_id -> text) into queries.jsonl."""
    corpus_manifest = Manifest.read(args.corpus_manifest)
    corpus = load_corpus(args.corpus)
    by_id = {p.passage_id: p for p in corpus}
    drafts: dict[str, str] = json.loads(args.drafts.read_text(encoding="utf-8"))

    passages = [by_id[pid] for pid in drafts if pid in by_id]
    built, failures = build(passages, drafts)
    if failures:
        for pid, shared in failures.items():
            print(f"FAIL {pid}: shares content words {list(shared)}")
        print(f"{len(failures)} draft(s) still fail the overlap check; not writing")
        return 1

    queries_path = args.dir / QUERIES_FILE
    existing = read_queries(queries_path) if queries_path.exists() else []
    kept = [q for q in existing if q.category != "paraphrase"]
    write_queries(queries_path, kept + built)

    manifest_path = args.dir / MANIFEST_FILE
    manifest = QuerySetManifest.read(manifest_path)
    manifest.corpus_hash = corpus_manifest.corpus_hash
    manifest.counts["paraphrase"] = len(built)
    manifest.write(manifest_path)

    print(f"paraphrase queries: {len(built)} written; corpus_hash {manifest.corpus_hash}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="braid.eval.queryset.build_paraphrase")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--corpus-manifest", type=Path, default=DEFAULT_CORPUS_MANIFEST)
    parser.add_argument("--dir", type=Path, default=QUERYSET_DIR)
    sub = parser.add_subparsers(dest="command", required=True)

    sample = sub.add_parser("sample", help="sample passages and write a drafting worksheet")
    sample.add_argument("--limit", type=int, default=60)
    sample.add_argument("--seed", type=int, default=DEFAULT_SEED)
    sample.add_argument("--out", type=Path, default=Path("data/paraphrase-worksheet.json"))
    sample.set_defaults(func=cmd_sample)

    write = sub.add_parser("write", help="check drafts and merge into queries.jsonl")
    write.add_argument("--drafts", type=Path, required=True)
    write.set_defaults(func=cmd_write)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
