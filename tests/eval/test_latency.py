import time

from braid.eval.latency import WARMUP_QUERIES, measure_latency, render_markdown


class SleepyRetriever:
    """A stub retriever with an injected, controllable delay per query."""

    def __init__(self, name: str, delay_seconds: float):
        self.name = name
        self._delay = delay_seconds

    def search(self, query: str, k: int):
        time.sleep(self._delay)
        return []


def test_warmup_queries_are_excluded_from_timing():
    # First WARMUP_QUERIES are slow; timed queries are fast. If warm-up were
    # not excluded, p50/p95 would be dominated by the slow queries.
    calls = {"n": 0}

    class VariableDelay:
        name = "variable"

        def search(self, query: str, k: int):
            calls["n"] += 1
            delay = 0.05 if calls["n"] <= WARMUP_QUERIES else 0.0
            time.sleep(delay)
            return []

    queries = [f"q{i}" for i in range(WARMUP_QUERIES + 5)]
    report = measure_latency(VariableDelay(), queries, rerank_depth=50)
    assert report.warmup_count == WARMUP_QUERIES
    assert report.n_timed == 5
    assert report.p95_seconds < 0.03  # timed queries were fast; warm-up excluded


def test_concurrency_is_always_one():
    queries = [f"q{i}" for i in range(WARMUP_QUERIES + 3)]
    report = measure_latency(SleepyRetriever("stub", 0.0), queries, rerank_depth=50)
    assert report.concurrency == 1


def test_rerank_depth_is_recorded():
    queries = [f"q{i}" for i in range(WARMUP_QUERIES + 3)]
    report = measure_latency(SleepyRetriever("stub", 0.0), queries, rerank_depth=30)
    assert report.rerank_depth == 30


def test_p50_and_p95_reflect_injected_delay():
    queries = [f"q{i}" for i in range(WARMUP_QUERIES + 20)]
    report = measure_latency(SleepyRetriever("stub", 0.01), queries, rerank_depth=50)
    assert report.p50_seconds >= 0.008
    assert report.p95_seconds >= report.p50_seconds


def test_throughput_is_consistent_with_measured_latency():
    queries = [f"q{i}" for i in range(WARMUP_QUERIES + 10)]
    report = measure_latency(SleepyRetriever("stub", 0.01), queries, rerank_depth=50)
    # ~10 queries at ~0.01s each -> roughly 100 q/s, generously bounded.
    assert 20 < report.throughput_qps < 500


def test_d1_pass_reflects_thresholds():
    queries = [f"q{i}" for i in range(WARMUP_QUERIES + 5)]
    fast = measure_latency(SleepyRetriever("fast", 0.0), queries, rerank_depth=50)
    assert fast.passes_d1 is True


def test_too_few_queries_raises():
    import pytest

    with pytest.raises(ValueError, match="need more than"):
        measure_latency(SleepyRetriever("stub", 0.0), ["q1", "q2"], rerank_depth=50)


def test_memory_sample_present_or_gracefully_none():
    queries = [f"q{i}" for i in range(WARMUP_QUERIES + 3)]
    report = measure_latency(SleepyRetriever("stub", 0.0), queries, rerank_depth=50)
    # On macOS this should be populated; elsewhere it degrades to None fields
    # rather than raising.
    assert report.memory_before is not None
    assert report.memory_after is not None


def test_render_markdown_includes_depth_and_d1_columns():
    queries = [f"q{i}" for i in range(WARMUP_QUERIES + 3)]
    report = measure_latency(SleepyRetriever("stub", 0.0), queries, rerank_depth=50)
    markdown = render_markdown([report])
    assert "Rerank depth" in markdown
    assert "D1 pass" in markdown
    assert "50" in markdown
