"""Index CLI.

    python -m braid.index health
"""

from __future__ import annotations

import argparse
import sys

from braid.index.base import DenseBuilder
from braid.index.health import health


def cmd_health(_args: argparse.Namespace) -> int:
    # health() covers the two live services (OpenSearch, Neo4j); dense is
    # file-based, not a container, and is checked separately via the same
    # DenseBuilder.health() the shared IndexBuilder contract uses -- so
    # "all three" here means all three, not two plus a gap.
    results = [*health(), DenseBuilder().health()]
    for r in results:
        print(f"{r.name:12} {r.state:10} count={r.count!s:6} {r.detail}")
    return 0 if all(r.state != "down" for r in results) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="braid.index")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health", help="check OpenSearch and Neo4j reachability").set_defaults(
        func=cmd_health
    )
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
