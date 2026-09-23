"""Paired bootstrap confidence intervals for cross-configuration comparisons.

This is the module the spec singles out for adversarial review (workflow step
7, SPEC-eval.md Risks): a bug here produces a plausible wrong number, not a
crash.

The correct procedure resamples *queries*, reading both configurations'
scores for each resampled query, then takes the mean of those paired
differences. The trap is resampling each configuration's scores
*independently* -- that destroys the pairing between a query and its two
scores, and inflates the interval whenever the two configurations are
correlated (which two real retrievers almost always are, since a query hard
for one tends to be hard for a related one too). `paired_bootstrap` is the
correct implementation; `_unpaired_bootstrap_for_testing_only` exists solely
so the regression test in tests/eval/test_bootstrap.py can demonstrate the
difference -- it is never called by application code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from braid.eval.result import EvalResult

DEFAULT_RESAMPLES = 1000
DEFAULT_SEED = 0
DEFAULT_CI = 0.95


@dataclass(frozen=True)
class Comparison:
    metric: str
    diff: float  # mean(a) - mean(b) on the observed (non-resampled) data
    ci_low: float
    ci_high: float
    excludes_zero: bool
    n: int
    resamples: int
    seed: int


MIN_N = 2


def paired_bootstrap(
    scores_a: dict[str, float],
    scores_b: dict[str, float],
    *,
    metric: str = "",
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    ci: float = DEFAULT_CI,
) -> Comparison:
    """95%-by-default percentile CI on mean(a) - mean(b), paired by query id.

    Resamples query *indices* with replacement and reads both configurations'
    scores for each resampled query -- the pairing between a query and its
    two scores is preserved in every resample. This is what "paired" means
    here, and it is the property the regression test in test_bootstrap.py
    checks directly.

    Every real caller in this codebase evaluates every configuration over the
    identical query list (SPEC-query.md: "all five configurations ... pass one
    shared contract test suite"), so `scores_a` and `scores_b` are expected to
    carry exactly the same query ids. A mismatch is not a legitimate "some
    queries only apply to one side" case here -- it is evidence of upstream
    data loss (a retriever erroring on a subset of queries), and silently
    scoring over the intersection would let `Comparison.diff` disagree with
    `EvalResult.aggregate()`'s own per-config means in the published table
    (found by adversarial review, 2026-09-23). It is refused, not repaired.
    """
    if set(scores_a) != set(scores_b):
        only_a = set(scores_a) - set(scores_b)
        only_b = set(scores_b) - set(scores_a)
        raise ValueError(
            "scores_a and scores_b must cover exactly the same query ids; "
            f"{len(only_a)} id(s) only in scores_a, {len(only_b)} only in scores_b "
            "-- this indicates upstream data loss, not a legitimate partial overlap"
        )
    common_ids = sorted(scores_a)
    if len(common_ids) < MIN_N:
        raise ValueError(
            f"need at least {MIN_N} queries to bootstrap, got {len(common_ids)} "
            "-- a single-query interval is degenerate (zero width) and would render "
            "indistinguishably from a well-powered result"
        )
    diffs = np.array([scores_a[qid] - scores_b[qid] for qid in common_ids])
    if not np.all(np.isfinite(diffs)):
        raise ValueError("scores_a/scores_b contain non-finite values (NaN or inf)")
    n = len(diffs)

    rng = np.random.default_rng(seed)
    resampled_means = np.empty(resamples)
    for i in range(resamples):
        idx = rng.integers(0, n, size=n)
        resampled_means[i] = diffs[idx].mean()

    alpha = (1 - ci) / 2
    lo, hi = np.percentile(resampled_means, [alpha * 100, (1 - alpha) * 100])
    point = float(diffs.mean())
    excludes_zero = bool(lo > 0 or hi < 0)
    return Comparison(
        metric=metric,
        diff=point,
        ci_low=float(lo),
        ci_high=float(hi),
        excludes_zero=excludes_zero,
        n=n,
        resamples=resamples,
        seed=seed,
    )


def compare(
    a: EvalResult,
    b: EvalResult,
    *,
    metric: str,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> Comparison:
    """The interface SPEC-eval.md documents: `compare(a: EvalResult, b: EvalResult, ...)`.

    A thin wrapper over `paired_bootstrap` so the module's public surface
    matches what the spec promises, without duplicating the resampling logic.
    Extracts per-query values for `metric` pooled across all categories and
    defers to `paired_bootstrap`. Callers that need a specific category (as
    table.py does) should call `paired_bootstrap` directly with
    `EvalResult.per_query_values(category, metric)`.
    """
    from braid.eval.result import POOLED

    return paired_bootstrap(
        a.per_query_values(POOLED, metric),
        b.per_query_values(POOLED, metric),
        metric=metric,
        resamples=resamples,
        seed=seed,
    )


def _unpaired_bootstrap_for_testing_only(
    scores_a: dict[str, float],
    scores_b: dict[str, float],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    ci: float = DEFAULT_CI,
) -> Comparison:
    """The wrong way: resamples each configuration's scores independently,
    destroying the query-level pairing. Exists only to demonstrate, in a test,
    how much narrower the correct paired interval is on correlated data. Not
    used by any application code -- do not call this from eval or the CLI.
    """
    a = np.array([scores_a[qid] for qid in sorted(scores_a)])
    b = np.array([scores_b[qid] for qid in sorted(scores_b)])
    n_a, n_b = len(a), len(b)

    rng = np.random.default_rng(seed)
    resampled_diffs = np.empty(resamples)
    for i in range(resamples):
        resampled_diffs[i] = (
            a[rng.integers(0, n_a, size=n_a)].mean() - b[rng.integers(0, n_b, size=n_b)].mean()
        )

    alpha = (1 - ci) / 2
    lo, hi = np.percentile(resampled_diffs, [alpha * 100, (1 - alpha) * 100])
    point = float(a.mean() - b.mean())
    return Comparison(
        metric="", diff=point, ci_low=float(lo), ci_high=float(hi),
        excludes_zero=bool(lo > 0 or hi < 0), n=n_a, resamples=resamples, seed=seed,
    )
