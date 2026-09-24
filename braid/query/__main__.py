"""Query CLI (Task 34, SPEC-query.md).

Usage:
    python -m braid.query "<text>" --config fused-rerank --k 10

Prints ranked IDs, scores, provenance, and timing in a human-readable table.
The factory is the same as the one used by ``braid.eval``, guaranteeing identical
retrieval code paths.
"""

from __future__ import annotations

import argparse
import sys
import time


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="braid.query",
        description="Retrieve passages for a query using a named configuration.",
    )
    parser.add_argument("text", help="Query text to retrieve passages for.")
    parser.add_argument(
        "--config",
        type=str,
        default="fused-rerank",
        help="Retriever configuration name (default: fused-rerank).",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=10,
        help="Number of results to return (default: 10).",
    )
    args = parser.parse_args(argv)

    from braid.query.factory import create_retriever

    retriever = create_retriever(args.config)

    t_start = time.perf_counter()
    hits = retriever.search(args.text, k=args.k)
    elapsed_ms = (time.perf_counter() - t_start) * 1000

    print(f"\nQuery   : {args.text}")
    print(f"Config  : {args.config}  k={args.k}  time={elapsed_ms:.1f} ms\n")

    if not hits:
        print("No results returned.")
        return 0

    # Column widths
    id_w = max(len(h.passage_id) for h in hits)
    id_w = max(id_w, 11)  # "passage_id" header width

    header = (
        f"{'rank':>4}  {'passage_id':<{id_w}}  {'score':>12}  provenance"
    )
    print(header)
    print("-" * (len(header) + 20))

    for hit in hits:
        prov_str = "  ".join(
            f"{k}={v:.4f}" for k, v in sorted(hit.provenance.items()) if v > 0
        )
        print(
            f"{hit.rank:>4}  {hit.passage_id:<{id_w}}  {hit.score:>12.6f}  {prov_str}"
        )

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
