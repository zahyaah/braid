"""Evaluation CLI.

    python -m braid.eval --stub    # proves the harness works, no real retriever needed
    python -m braid.eval --all-configs --bootstrap 1000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from braid.eval.bootstrap import DEFAULT_RESAMPLES, DEFAULT_SEED
from braid.eval.queryset.schema import QUERIES_FILE, QUERYSET_DIR, read_queries
from braid.eval.result import evaluate
from braid.eval.table import criterion2_comparisons, render_markdown

DEFAULT_REPORT = Path("reports/comparison.md")
# The stub run's output is meaningless placeholder data (a hash-based stub
# retriever essentially never hits a real 16-hex-char passage id), so it
# defaults to a separate, gitignored path -- never reports/comparison.md,
# which is reserved for the real evaluation's output. Committing stub zeros
# under the same name a reader expects real results at would be misleading.
DEFAULT_STUB_REPORT = Path("reports/stub-comparison.md")


class StubRetriever:
    """A retriever with no real logic, so `eval` can be proven end to end
    before any real retriever exists (SPEC-eval.md acceptance).
    """

    def __init__(self, name: str, seed: int = 0):
        self.name = name
        self._seed = seed

    def search(self, query: str, k: int):
        import hashlib

        from braid.eval.metrics import RankedHit

        # Deterministic pseudo-ranking from a hash of (name, query), so
        # different stub configs produce different, reproducible rankings.
        digest = hashlib.sha256(f"{self.name}:{self._seed}:{query}".encode()).digest()
        return [
            RankedHit(passage_id=f"p{digest[i]}", rank=i + 1, score=1.0 / (i + 1))
            for i in range(k)
        ]


def cmd_stub(args: argparse.Namespace) -> int:
    queries = read_queries(args.dir / QUERIES_FILE)
    configs = ["bm25", "dense", "fused", "fused-rerank"]
    results = {
        name: evaluate(queries, StubRetriever(name, seed=i)) for i, name in enumerate(configs)
    }
    comparisons = criterion2_comparisons(results, resamples=args.bootstrap, seed=args.seed)
    report = render_markdown(results, comparisons)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"stub evaluation over {len(queries)} queries, {len(configs)} configs -> {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="braid.eval")
    parser.add_argument("--dir", type=Path, default=QUERYSET_DIR)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--bootstrap", type=int, default=DEFAULT_RESAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--stub", action="store_true", help="run against stub retrievers")
    parser.add_argument(
        "--all-configs", action="store_true", help="run against real configs (not yet available)"
    )
    args = parser.parse_args(argv)

    if args.out is None:
        args.out = DEFAULT_STUB_REPORT if args.stub else DEFAULT_REPORT

    if args.stub:
        return cmd_stub(args)
    if args.all_configs:
        print("real configurations are not built yet (Phase 6); use --stub", file=sys.stderr)
        return 1
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
