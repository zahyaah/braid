"""Evaluation CLI.

    python -m braid.eval --stub           # proves the harness works, no real retriever needed
    python -m braid.eval --all-configs --bootstrap 1000
    python -m braid.eval --criterion3     # graph-win exhaustive count (Task 33)
    python -m braid.eval --latency --config fused-rerank   # D1 latency (Task 32)
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


def cmd_config(args: argparse.Namespace) -> int:
    from braid.eval.queryset.schema import CATEGORIES
    from braid.eval.result import METRICS, POOLED
    from braid.query.factory import create_retriever

    queries = read_queries(args.dir / QUERIES_FILE)
    retriever = create_retriever(args.config)
    result = evaluate(queries, retriever, k=args.k)
    table = result.table()

    print(f"\nConfiguration: {args.config} (k={args.k}, queries={len(queries)})")
    header = f"| {'Category':24} | " + " | ".join(f"{m:>9}" for m in METRICS) + " |"
    sep = "|" + "-" * 26 + "|" + "|".join(["-" * 11] * len(METRICS)) + "|"
    print(header)
    print(sep)
    groups = (*CATEGORIES, POOLED)
    for group in groups:
        row = " | ".join(f"{table[group][m]:9.4f}" for m in METRICS)
        print(f"| {group:24} | {row} |")
    print()

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# Evaluation Report: {args.config}\n", header, sep]
        for group in groups:
            row = " | ".join(f"{table[group][m]:9.4f}" for m in METRICS)
            lines.append(f"| {group:24} | {row} |")
        args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Report written to {args.out}")

    return 0


def cmd_all_configs(args: argparse.Namespace) -> int:
    from braid.query.factory import create_retriever

    # The four configurations scoreable before the fine-tuned reranker exists
    # (Task 37 adds `fused-rerank-ft`). All are evaluated over the identical
    # query list, so criterion-2's paired bootstrap is well-defined.
    configs = ("bm25", "dense", "fused", "fused-rerank")
    queries = read_queries(args.dir / QUERIES_FILE)
    results = {}
    for name in configs:
        print(f"evaluating {name} ...")
        results[name] = evaluate(queries, create_retriever(name), k=args.k)

    comparisons = criterion2_comparisons(results, resamples=args.bootstrap, seed=args.seed)
    report = render_markdown(results, comparisons)

    out = args.out if args.out else DEFAULT_REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"evaluated {len(configs)} configs over {len(queries)} queries -> {out}")
    return 0


def cmd_latency(args: argparse.Namespace) -> int:
    from braid.eval.latency import measure_latency
    from braid.eval.latency import render_markdown as render_latency
    from braid.query.factory import create_retriever
    from braid.query.params import RERANK_TOP_K

    config = args.config if args.config else "fused-rerank"
    queries = read_queries(args.dir / QUERIES_FILE)
    texts = [q.text for q in queries]
    retriever = create_retriever(config)
    # D7: every latency figure records the rerank depth it was measured at.
    rerank_depth = RERANK_TOP_K if "rerank" in retriever.name else 0
    print(
        f"measuring latency for {config} over {len(queries)} queries "
        f"(warm-up 10, concurrency 1) ..."
    )
    report = measure_latency(retriever, texts, rerank_depth=rerank_depth, k=args.k)

    out = args.out if args.out else Path("reports/latency.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_latency([report]), encoding="utf-8")

    status = "pass" if report.passes_d1 else "FAIL"
    print(
        f"  p50={report.p50_seconds:.4f}s  p95={report.p95_seconds:.4f}s  "
        f"throughput={report.throughput_qps:.2f} q/s  D1={status}"
    )
    print(f"  Report written to {out}")
    return 0


def cmd_criterion3(args: argparse.Namespace) -> int:
    """Run criterion-3 exhaustive graph-win count over every multi-hop query."""
    from braid.eval.criterion3 import TOP_K, render_markdown, run_criterion3
    from braid.query.factory import create_retriever

    queries = read_queries(args.dir / QUERIES_FILE)
    multi_hop = [q for q in queries if q.category == "multi-hop-relational"]
    print(f"Criterion-3: analysing {len(multi_hop)} multi-hop queries ...")

    dense_retriever = create_retriever("dense")
    fused_retriever = create_retriever("fused")

    from braid.eval.criterion3 import count_graph_wins

    verdicts = run_criterion3(queries, dense_retriever, fused_retriever, k=TOP_K)
    n_wins = count_graph_wins(verdicts)
    report_md = render_markdown(verdicts)

    out = args.out if args.out else Path("reports/graph-vs-vector.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report_md, encoding="utf-8")

    print(
        f"  Multi-hop queries : {len(verdicts)}"
        f"\n  Graph-win queries  : {n_wins}"
        f"\n  Graph-win rate     : {n_wins / len(verdicts):.1%}"
        f"\n  Report written to  : {out}"
    )
    if n_wins < 5:
        print(
            "\n[FINDING] Graph-win count is below 5. "
            "Graph traversal contributes fewer unique gold passages "
            "over dense retrieval than expected for this queryset.",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="braid.eval")
    parser.add_argument("--dir", type=Path, default=QUERYSET_DIR)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--bootstrap", type=int, default=DEFAULT_RESAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--k", type=int, default=10, help="top-k depth for evaluation (default: 10)"
    )
    parser.add_argument(
        "--config", type=str, default=None, help="evaluate a single configuration (e.g. bm25)"
    )
    parser.add_argument(
        "--all-configs",
        action="store_true",
        help="evaluate every built configuration and write the criterion-1/2 table",
    )
    parser.add_argument(
        "--stub", action="store_true", help="run stub evaluation (no real retriever needed)"
    )
    parser.add_argument(
        "--criterion3",
        action="store_true",
        help="run criterion-3 exhaustive graph-win count over every multi-hop query",
    )
    parser.add_argument(
        "--latency",
        action="store_true",
        help="measure warm p50/p95 latency against D1 for --config (default fused-rerank)",
    )
    args = parser.parse_args(argv)

    if args.latency:
        return cmd_latency(args)

    if args.config:
        return cmd_config(args)

    if args.criterion3:
        return cmd_criterion3(args)

    if args.out is None:
        args.out = DEFAULT_STUB_REPORT if args.stub else DEFAULT_REPORT

    if args.stub:
        return cmd_stub(args)
    if args.all_configs:
        return cmd_all_configs(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
