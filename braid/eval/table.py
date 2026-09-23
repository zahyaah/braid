"""The comparison table: criterion 1 (per-config, per-category, pooled metrics)
and criterion 2 (fused+reranked vs best single-method baseline, with a paired
bootstrap CI per category, explicit "excludes zero" column).

"Best single-method baseline" is descriptive, not selected post-hoc (amendment
7, item 3): for each category and metric, it is whichever of bm25 or dense
scores higher on that category, read off the criterion-1 numbers. It is never
chosen because it makes the comparison look better, and the table names which
one won so the choice is visible rather than implied.
"""

from __future__ import annotations

from dataclasses import dataclass

from braid.eval.bootstrap import Comparison, paired_bootstrap
from braid.eval.queryset.schema import CATEGORIES
from braid.eval.result import METRICS, POOLED, EvalResult

GROUPS = (*CATEGORIES, POOLED)
BASELINE_CANDIDATES = ("bm25", "dense")
TARGET_CONFIG = "fused-rerank"


@dataclass(frozen=True)
class BaselineComparison:
    category: str
    metric: str
    baseline_name: str  # which of bm25/dense won this category+metric
    baseline_value: float
    target_value: float
    comparison: Comparison


def _derive_seed(base_seed: int, category: str, metric: str) -> int:
    """A stable, reproducible per-(category, metric) seed derived from one base
    seed, so each of the 16 calls in a run resamples independently while the
    whole run remains reproducible from a single number.
    """
    import hashlib

    digest = hashlib.sha256(f"{base_seed}:{category}:{metric}".encode()).digest()
    return int.from_bytes(digest[:4], "big")


def pick_baseline(results: dict[str, EvalResult], category: str, metric: str) -> str:
    """The stronger of bm25/dense on this category+metric, read descriptively
    off the criterion-1 table -- never chosen after seeing the comparison.
    """
    values = {name: results[name].aggregate(category, metric) for name in BASELINE_CANDIDATES}
    return max(values, key=lambda name: values[name])


def criterion1_table(results: dict[str, EvalResult]) -> dict[str, dict[str, dict[str, float]]]:
    """{config: {group: {metric: value}}} for every configuration, every
    category, and pooled. Never pooled-only.
    """
    return {name: result.table() for name, result in results.items()}


def criterion2_comparisons(
    results: dict[str, EvalResult],
    *,
    resamples: int = 1000,
    seed: int = 0,
    target: str = TARGET_CONFIG,
) -> list[BaselineComparison]:
    """For every category and metric: target vs the descriptively-best single
    baseline, with a paired-bootstrap 95% CI. Pooled is included alongside the
    three categories, not in place of them (criterion 1's "not pooled-only"
    applies here too).
    """
    out: list[BaselineComparison] = []
    for category in GROUPS:
        for metric in METRICS:
            baseline_name = pick_baseline(results, category, metric)
            baseline_scores = results[baseline_name].per_query_values(category, metric)
            target_scores = results[target].per_query_values(category, metric)
            # A distinct seed per (category, metric) call, derived deterministically
            # from the base seed. Reusing one seed across all 16 calls would give
            # every metric within a category the *same* sequence of resampled
            # query-index draws -- correlated, not independent, evidence (found by
            # adversarial review, 2026-09-23). Still fully reproducible: the same
            # base seed always derives the same per-call seeds.
            call_seed = _derive_seed(seed, category, metric)
            comparison = paired_bootstrap(
                target_scores, baseline_scores, metric=metric, resamples=resamples, seed=call_seed
            )
            out.append(
                BaselineComparison(
                    category=category,
                    metric=metric,
                    baseline_name=baseline_name,
                    baseline_value=results[baseline_name].aggregate(category, metric),
                    target_value=results[target].aggregate(category, metric),
                    comparison=comparison,
                )
            )
    return out


def render_markdown(
    results: dict[str, EvalResult], comparisons: list[BaselineComparison]
) -> str:
    """One markdown document: the criterion-1 table, then the criterion-2
    comparison table with the winning-baseline and excludes-zero columns.
    """
    lines = ["## Criterion 1: per-configuration metrics\n"]
    lines.append("| Config | Category | " + " | ".join(METRICS) + " |")
    lines.append("|---|---|" + "---|" * len(METRICS))
    for config_name, result in results.items():
        table = result.table()
        for group in GROUPS:
            row = " | ".join(f"{table[group][m]:.4f}" for m in METRICS)
            lines.append(f"| {config_name} | {group} | {row} |")

    lines.append("\n## Criterion 2: fused-rerank vs best single-method baseline\n")
    lines.append(
        "| Category | Metric | Baseline | Baseline value | Target value | Diff | "
        "95% CI | Excludes zero |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for c in comparisons:
        ci = f"[{c.comparison.ci_low:.4f}, {c.comparison.ci_high:.4f}]"
        excludes = "yes" if c.comparison.excludes_zero else "no"
        lines.append(
            f"| {c.category} | {c.metric} | {c.baseline_name} | {c.baseline_value:.4f} | "
            f"{c.target_value:.4f} | {c.comparison.diff:+.4f} | {ci} | {excludes} |"
        )
    return "\n".join(lines) + "\n"
