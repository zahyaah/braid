"""The bootstrap is the module most likely to produce a plausible wrong number
(SPEC-eval.md Risks). Every test here checks against a known analytical
answer, not against the code's own output.
"""

import numpy as np
import pytest

from braid.eval.bootstrap import _unpaired_bootstrap_for_testing_only, paired_bootstrap


def scores(values: list[float], prefix: str = "q") -> dict[str, float]:
    return {f"{prefix}{i}": v for i, v in enumerate(values)}


# ---- known-answer tests ----

def test_identical_inputs_give_an_interval_containing_zero():
    a = scores([0.1, 0.5, 0.9, 0.3, 0.7, 0.2, 0.6, 0.4, 0.8, 0.0])
    result = paired_bootstrap(a, dict(a), seed=1)
    assert result.diff == 0.0
    assert result.ci_low <= 0.0 <= result.ci_high
    assert not result.excludes_zero


def test_constant_offset_gives_an_interval_excluding_zero():
    base = [0.1, 0.5, 0.9, 0.3, 0.7, 0.2, 0.6, 0.4, 0.8, 0.0]
    a = scores(base)
    b = scores([v - 0.2 for v in base])  # a is uniformly 0.2 better on every query
    result = paired_bootstrap(a, b, seed=1)
    assert abs(result.diff - 0.2) < 1e-9
    # Every query's diff is exactly 0.2, so every resample's mean is exactly
    # 0.2 too -- the interval collapses to a point at 0.2.
    assert abs(result.ci_low - 0.2) < 1e-9
    assert abs(result.ci_high - 0.2) < 1e-9
    assert result.excludes_zero


def test_interval_narrows_as_n_grows():
    rng = np.random.default_rng(42)

    def make(n: int) -> tuple[dict, dict]:
        a_vals = rng.normal(0.6, 0.15, size=n)
        b_vals = a_vals - rng.normal(0.05, 0.1, size=n)  # noisy per-query diff, mean 0.05
        return scores(a_vals.tolist(), "s"), scores(b_vals.tolist(), "s")

    a_small, b_small = make(20)
    a_large, b_large = make(2000)
    small = paired_bootstrap(a_small, b_small, seed=2)
    large = paired_bootstrap(a_large, b_large, seed=2)
    assert (large.ci_high - large.ci_low) < (small.ci_high - small.ci_low)


def test_fixed_seed_reproduces_the_interval_exactly():
    a = scores([0.1, 0.5, 0.9, 0.3, 0.7])
    b = scores([0.2, 0.4, 0.8, 0.3, 0.6])
    first = paired_bootstrap(a, b, seed=7)
    second = paired_bootstrap(a, b, seed=7)
    assert first.ci_low == second.ci_low
    assert first.ci_high == second.ci_high


def test_disjoint_keys_raise():
    with pytest.raises(ValueError, match="same query ids"):
        paired_bootstrap({"a": 1.0}, {"b": 2.0})


# ---- adversarial-review findings, 2026-09-23 ----
# A fresh-context reviewer found these against the real caller (table.py) and
# the project's own contract (SPEC-eval.md): silent partial-overlap
# truncation that could make a published table's Diff column disagree with
# its own Baseline/Target columns, a missing floor on n that let a single
# query render as a confident-looking zero-width interval, NaN silently
# reading as excludes_zero=False, and no coverage proving any of it.

def test_partial_overlap_raises_instead_of_silently_scoring_the_intersection():
    # Every real caller evaluates every config over the same query list
    # (SPEC-query.md); a mismatch means upstream data loss, not a legitimate
    # subset comparison, and must be refused rather than silently narrowed.
    a = scores([0.1, 0.5, 0.9])  # q0, q1, q2
    b = {"q0": 0.2, "q1": 0.4, "q3": 0.6}  # q2 missing, q3 extra
    with pytest.raises(ValueError, match="same query ids"):
        paired_bootstrap(a, b)


def test_single_query_raises_rather_than_producing_a_degenerate_interval():
    # n=1: every resample draws the same single point, collapsing to a
    # zero-width interval that would render identically to a well-powered
    # n=180 result with no signal that it rests on one query.
    with pytest.raises(ValueError, match="at least 2 queries"):
        paired_bootstrap({"q0": 0.9}, {"q0": 0.5})


def test_non_finite_scores_raise_rather_than_silently_reading_as_not_excluding_zero():
    # excludes_zero = bool(lo > 0 or hi < 0): both comparisons are False for
    # NaN, so an unvalidated NaN input would silently render as "excludes
    # zero: no" instead of surfacing the corruption.
    a = scores([0.1, 0.5, float("nan")])
    b = scores([0.2, 0.4, 0.3])
    with pytest.raises(ValueError, match="non-finite"):
        paired_bootstrap(a, b)


def test_comparison_records_n_resamples_and_seed_correctly():
    # No prior test inspected these fields; a regression computing n as
    # len(scores_a) instead of len(common_ids) would have passed silently.
    a = scores([0.1, 0.5, 0.9, 0.3, 0.7])
    b = scores([0.2, 0.4, 0.8, 0.3, 0.6])
    result = paired_bootstrap(a, b, resamples=250, seed=11)
    assert result.n == 5
    assert result.resamples == 250
    assert result.seed == 11


def test_interval_has_real_spread_on_a_non_constant_diff():
    # The existing constant-offset test collapses every resample to the same
    # value and never exercises genuine percentile computation on a resampled
    # distribution with actual variance.
    rng = np.random.default_rng(99)
    n = 60
    a_vals = rng.uniform(0.4, 0.9, size=n)
    b_vals = a_vals - rng.normal(0.05, 0.08, size=n)  # noisy per-query diff
    result = paired_bootstrap(scores(a_vals.tolist()), scores(b_vals.tolist()), seed=5)
    assert result.ci_high > result.ci_low
    assert result.ci_high - result.ci_low > 0.01  # not degenerate


def test_realistic_minimum_category_size_n_equals_30():
    # SPEC.md's D3 minimum fallback is 30 queries/category; this is the real
    # operating floor, not just the mathematical minimum of 2.
    rng = np.random.default_rng(30)
    n = 30
    a_vals = rng.uniform(0.3, 0.9, size=n)
    b_vals = a_vals - rng.normal(0.05, 0.1, size=n)
    result = paired_bootstrap(scores(a_vals.tolist()), scores(b_vals.tolist()), seed=6)
    assert result.n == 30
    assert result.ci_low <= result.diff <= result.ci_high


def test_non_default_ci_changes_the_percentile_bounds():
    # Exercises the alpha = (1 - ci) / 2 formula independent of the
    # hardcoded 95% default -- a narrower ci should give a narrower interval.
    rng = np.random.default_rng(77)
    n = 100
    a_vals = rng.uniform(0.3, 0.9, size=n)
    b_vals = a_vals - rng.normal(0.05, 0.15, size=n)
    a, b = scores(a_vals.tolist()), scores(b_vals.tolist())
    wide = paired_bootstrap(a, b, seed=8, ci=0.99)
    narrow = paired_bootstrap(a, b, seed=8, ci=0.80)
    assert (narrow.ci_high - narrow.ci_low) < (wide.ci_high - wide.ci_low)


# ---- the paired-vs-unpaired regression test ----
# This is the test that would have caught the most likely silent bug: resampling
# each configuration's scores independently instead of resampling queries and
# reading both configurations' scores for the resampled query.

def test_paired_interval_is_far_narrower_than_unpaired_on_correlated_data():
    rng = np.random.default_rng(123)
    n = 200
    # High per-query variance (retrievers agree on which queries are hard),
    # but a *constant* per-query improvement -- so the true paired diff has
    # essentially zero variance, while each configuration's own scores are
    # spread widely.
    a_vals = rng.uniform(0.0, 1.0, size=n)
    b_vals = a_vals - 0.1  # exactly 0.1 worse on every single query, no noise in the delta
    a = scores(a_vals.tolist())
    b = scores(b_vals.tolist())

    paired = paired_bootstrap(a, b, seed=3)
    unpaired = _unpaired_bootstrap_for_testing_only(a, b, seed=3)

    paired_width = paired.ci_high - paired.ci_low
    unpaired_width = unpaired.ci_high - unpaired.ci_low

    # The paired interval collapses to essentially a point (true diff has zero
    # variance across queries); the unpaired interval reflects the full spread
    # of two independent uniform(0,1)-ish samples, which is far wider.
    assert paired_width < 0.02
    assert unpaired_width > 10 * paired_width
    # Both should still correctly detect the true 0.1 difference.
    assert paired.excludes_zero
    assert unpaired.excludes_zero


# ---- compare(): the interface SPEC-eval.md documents ----

def test_compare_matches_the_spec_documented_interface():
    from braid.eval.bootstrap import compare
    from braid.eval.metrics import RankedHit
    from braid.eval.queryset.schema import LabeledQuery
    from braid.eval.result import evaluate

    class Stub:
        def __init__(self, name, hit):
            self.name = name
            self._hit = hit

        def search(self, query, k):
            return [RankedHit(self._hit, rank=1, score=1.0)]

    queries = [
        LabeledQuery(f"q{i}", f"text {i}", "exact-term", {"gold": 1}, "agent-drafted")
        for i in range(5)
    ]
    a = evaluate(queries, Stub("a", "gold"))
    b = evaluate(queries, Stub("b", "distractor"))
    result = compare(a, b, metric="mrr", resamples=100, seed=1)
    assert result.diff == 1.0  # a always hits, b never does
    assert result.excludes_zero
