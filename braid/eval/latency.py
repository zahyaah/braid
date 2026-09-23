"""Query latency and throughput harness (decision D1 thresholds, decision D7
fallbacks; amendment 5).

- 10 warm-up queries are discarded before timing.
- Concurrency 1 for p50/p95: queries run sequentially, so the percentiles
  describe single-query latency, not queueing.
- Throughput is a derived figure at concurrency 1, not a concurrent-capacity
  claim.
- Swap and memory pressure are captured alongside every latency figure, so a
  passing number produced while the machine is swapping is visible rather
  than inferable.
- Every figure records the rerank depth it was measured at (D7).
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass

WARMUP_QUERIES = 10
D1_P50_SECONDS = 1.2
D1_P95_SECONDS = 2.5


@dataclass(frozen=True)
class MemorySample:
    swapins: int | None
    swapouts: int | None
    compressor_pages: int | None
    peak_rss_mb: float | None


@dataclass(frozen=True)
class LatencyReport:
    config_name: str
    rerank_depth: int
    warmup_count: int
    n_timed: int
    concurrency: int
    p50_seconds: float
    p95_seconds: float
    throughput_qps: float
    memory_before: MemorySample
    memory_after: MemorySample

    @property
    def passes_d1(self) -> bool:
        return self.p50_seconds < D1_P50_SECONDS and self.p95_seconds < D1_P95_SECONDS


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    # Nearest-rank method: simple, deterministic, matches how p50/p95 are
    # conventionally reported for latency without needing interpolation.
    index = max(0, min(len(ordered) - 1, int(round(pct / 100 * len(ordered))) - 1))
    return ordered[index]


def sample_vm_stat() -> MemorySample:
    """Best-effort macOS `vm_stat` sample. Returns all-None off macOS or on failure."""
    try:
        result = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5, check=True)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return MemorySample(None, None, None, None)

    swapins = swapouts = compressor = None
    for line in result.stdout.splitlines():
        if "Swapins" in line:
            swapins = _parse_vm_stat_count(line)
        elif "Swapouts" in line:
            swapouts = _parse_vm_stat_count(line)
        elif "Pages occupied by compressor" in line:
            compressor = _parse_vm_stat_count(line)
    return MemorySample(swapins, swapouts, compressor, peak_rss_mb=None)


def _parse_vm_stat_count(line: str) -> int | None:
    try:
        return int(line.split(":")[1].strip().rstrip("."))
    except (IndexError, ValueError):
        return None


def measure_latency(
    retriever,
    queries: list[str],
    *,
    rerank_depth: int,
    k: int = 10,
    warmup: int = WARMUP_QUERIES,
) -> LatencyReport:
    """Sequential (concurrency-1) timing of `retriever.search` over `queries`.
    The first `warmup` queries are run and discarded before timing starts.
    """
    if len(queries) <= warmup:
        raise ValueError(f"need more than {warmup} queries to leave any timed after warm-up")

    for query in queries[:warmup]:
        retriever.search(query, k)

    memory_before = sample_vm_stat()
    timed_queries = queries[warmup:]
    durations: list[float] = []
    start_all = time.perf_counter()
    for query in timed_queries:
        start = time.perf_counter()
        retriever.search(query, k)
        durations.append(time.perf_counter() - start)
    total_elapsed = time.perf_counter() - start_all
    memory_after = sample_vm_stat()

    throughput = len(timed_queries) / total_elapsed if total_elapsed > 0 else float("inf")

    return LatencyReport(
        config_name=getattr(retriever, "name", "unknown"),
        rerank_depth=rerank_depth,
        warmup_count=warmup,
        n_timed=len(timed_queries),
        concurrency=1,
        p50_seconds=_percentile(durations, 50),
        p95_seconds=_percentile(durations, 95),
        throughput_qps=throughput,
        memory_before=memory_before,
        memory_after=memory_after,
    )


def render_markdown(reports: list[LatencyReport]) -> str:
    lines = [
        "## Latency and throughput\n",
        "| Config | Rerank depth | Warm-up | N timed | Concurrency | p50 (s) | "
        "p95 (s) | Throughput (q/s) | D1 pass |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in reports:
        d1 = "yes" if r.passes_d1 else "no"
        lines.append(
            f"| {r.config_name} | {r.rerank_depth} | {r.warmup_count} | {r.n_timed} | "
            f"{r.concurrency} | {r.p50_seconds:.4f} | {r.p95_seconds:.4f} | "
            f"{r.throughput_qps:.2f} | {d1} |"
        )
    lines.append("\n### Memory pressure (before / after each pass)\n")
    lines.append(
        "| Config | Swapins before->after | Swapouts before->after | "
        "Compressor pages before->after |"
    )
    lines.append("|---|---|---|---|")
    for r in reports:
        b, a = r.memory_before, r.memory_after
        lines.append(
            f"| {r.config_name} | {b.swapins}->{a.swapins} | {b.swapouts}->{a.swapouts} | "
            f"{b.compressor_pages}->{a.compressor_pages} |"
        )
    return "\n".join(lines) + "\n"
