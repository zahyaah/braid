"""Before/after comparison for the fine-tuned cross-encoder (SPEC-finetune.md).

Task 37. Compares ``fused-rerank`` (pretrained cross-encoder) against
``fused-rerank-ft`` (the fine-tuned checkpoint) over the same held-out
queryset, per metric, per category and pooled, with the same paired-bootstrap
95% confidence-interval treatment used for criterion 2.

Both retrievers share the identical ``fused`` candidate list and rerank depth
(RERANK_TOP_K), so the only difference under test is the cross-encoder
weights. A null or negative result is rendered at the same prominence as a
positive one.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from braid.eval.bootstrap import DEFAULT_RESAMPLES, DEFAULT_SEED, Comparison, paired_bootstrap
from braid.eval.queryset.schema import CATEGORIES
from braid.eval.result import METRICS, POOLED, EvalResult

GROUPS = (*CATEGORIES, POOLED)
BEFORE_CONFIG = "fused-rerank"
AFTER_CONFIG = "fused-rerank-ft"


def _derive_seed(base_seed: int, group: str, metric: str) -> int:
    """Deterministically derive a per-(group, metric) bootstrap seed."""
    digest = hashlib.sha256(f"{base_seed}:{group}:{metric}".encode()).digest()
    return int.from_bytes(digest[:4], "big")


@dataclass(frozen=True)
class BeforeAfterComparison:
    """One metric's before/after result plus its paired-bootstrap interval."""

    category: str
    metric: str
    before_value: float
    after_value: float
    comparison: Comparison


def compare_before_after(
    before: EvalResult,
    after: EvalResult,
    *,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> list[BeforeAfterComparison]:
    """Compare ``after`` (fine-tuned) against ``before`` (pretrained).

    ``paired_bootstrap(after_scores, before_scores)`` computes
    ``diff = mean(after) - mean(before)``, so a positive diff means the
    fine-tuned reranker scores higher on that metric.
    """
    comparisons: list[BeforeAfterComparison] = []
    for group in GROUPS:
        for metric in METRICS:
            before_scores = before.per_query_values(group, metric)
            after_scores = after.per_query_values(group, metric)
            cmp = paired_bootstrap(
                after_scores,
                before_scores,
                metric=metric,
                resamples=resamples,
                seed=_derive_seed(seed, group, metric),
            )
            comparisons.append(
                BeforeAfterComparison(
                    category=group,
                    metric=metric,
                    before_value=before.aggregate(group, metric),
                    after_value=after.aggregate(group, metric),
                    comparison=cmp,
                )
            )
    return comparisons


def render_before_after(comparisons: list[BeforeAfterComparison]) -> str:
    """Render the before/after table with a 95% CI and an excludes-zero column."""
    lines = [
        "## Before/after: fine-tuned cross-encoder vs pretrained",
        "",
        "`after` = `fused-rerank-ft` (models/ce-braid), `before` = `fused-rerank`"
        " (cross-encoder/ms-marco-MiniLM-L-6-v2). Both rerank the identical"
        " `fused` top-50 candidate list. A positive diff means the fine-tuned"
        " model scores higher; a null or negative result is reported at the same"
        " prominence as a positive one.",
        "",
        "| Category | Metric | Before (pretrained) | After (fine-tuned) "
        "| Diff | 95% CI | Excludes zero |",
        "|----------|--------|--------------------:|-------------------:"
        "|-----:|--------|:-------------:|",
    ]
    for row in comparisons:
        cmp = row.comparison
        ci = f"[{cmp.ci_low:.4f}, {cmp.ci_high:.4f}]"
        lines.append(
            f"| {row.category} | {row.metric} | {row.before_value:.4f} "
            f"| {row.after_value:.4f} | {cmp.diff:+.4f} | {ci} "
            f"| {'yes' if cmp.excludes_zero else 'no'} |"
        )
    return "\n".join(lines) + "\n"
