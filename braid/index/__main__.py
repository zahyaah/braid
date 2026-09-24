"""Index CLI.

    python -m braid.index health
    python -m braid.index build --all      # OpenSearch BM25 + FAISS dense + Neo4j graph
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from braid.index.base import BM25Builder, DenseBuilder, GraphBuilder
from braid.index.health import health
from braid.ingest.models import load_corpus

DEFAULT_CORPUS = Path("data/corpus.jsonl")


def cmd_health(args: argparse.Namespace) -> int:
    # health() covers the two live services (OpenSearch, Neo4j); dense is
    # file-based, not a container, and is checked separately via the same
    # DenseBuilder.health() the shared IndexBuilder contract uses -- so
    # "all three" here means all three, not two plus a gap.
    #
    # `--services-only` checks just the two services. reproduce.sh needs it:
    # on a clean checkout the dense index file legitimately does not exist yet
    # ("down"), so gating the *start* of a reproduction on all three stores
    # aborted every clean run before anything was built.
    results = list(health())
    if not args.services_only:
        results.append(DenseBuilder().health())
    for r in results:
        print(f"{r.name:12} {r.state:10} count={r.count!s:6} {r.detail}")
    return 0 if all(r.state != "down" for r in results) else 1


def cmd_build(args: argparse.Namespace) -> int:
    passages = load_corpus(args.corpus)
    builders = (BM25Builder(), DenseBuilder(), GraphBuilder())
    for builder in builders:
        report = builder.build(passages)
        print(f"{builder.name:12} count={report.count!s:6} {report.detail}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="braid.index")
    sub = parser.add_subparsers(dest="command", required=True)
    health_parser = sub.add_parser("health", help="check OpenSearch, Neo4j, and the dense index")
    health_parser.add_argument(
        "--services-only",
        action="store_true",
        help="check only the OpenSearch/Neo4j services (skip the file-based dense index)",
    )
    health_parser.set_defaults(func=cmd_health)
    build_parser = sub.add_parser(
        "build", help="build the OpenSearch BM25, FAISS dense, and Neo4j graph indexes"
    )
    build_parser.add_argument(
        "--all",
        action="store_true",
        help="build all three indexes (the default; flag retained for SPEC conformance)",
    )
    build_parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    build_parser.set_defaults(func=cmd_build)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
