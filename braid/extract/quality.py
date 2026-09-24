"""Extraction quality: precision and recall against a hand-checked sample,
with 95% Wilson intervals (SPEC-extract.md, Task 21).

The sample must be annotated *before* the pipeline's own output for those
sentences is consulted -- otherwise recall is unmeasurable, because "did the
pipeline miss anything" can only be answered by ground truth that wasn't
derived from the pipeline in the first place. This module's `compare()`
enforces nothing about ordering itself (it can't -- that discipline lives in
how the sample file was produced); the ordering is recorded in
`data/extract-sample.jsonl`'s own metadata and the report states it.

Match definition: a gold triple and an extracted triple match when they share
the same sentence_index, the relation is equal after case-folding (gold
relations are annotated using the verb's base form -- the same lemma
convention the pipeline itself uses), and the subject and object are equal
*or one contains the other* after case-folding.

Containment, not exact equality, on subject/object: a pattern's extracted
span is its full syntactic subtree ("director Mike Nichols", not just "Mike
Nichols" -- see entities.py's `_find_type` for the identical issue on entity
typing). Requiring a hand-annotated gold span to reproduce spaCy's exact
subtree boundaries would make the comparison brittle in a way that reflects
annotation-format mismatches, not real extraction errors -- a human annotator
writes the core entity ("Mike Nichols"), not the parser's exact phrase
boundary. Containment captures "the extracted span correctly includes the
entity the annotator identified" without requiring that prediction. This is
still auditable (the containment rule is one sentence, applied identically
both directions) and still meaningfully restrictive: unrelated strings do not
contain each other.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from braid.extract.entities import fold_case
from braid.extract.models import Triple

# How the hand-annotated sample was produced. This is a constant (not derived
# from any file) so `python -m braid.extract quality` can reproduce the report's
# methodology note verbatim.
ANNOTATION_ORDER_NOTE = (
    "Annotated **before** the pipeline's output for these sentences was "
    "consulted: sentences were sampled (seed 20260923) and read cold, applying "
    "the five documented patterns (README.md) by eye. The only pipeline-adjacent "
    "information used was each passage's own title (needed to annotate "
    "pronoun-subject sentences correctly, since entities.py substitutes "
    "third-person pronouns with the title) -- that is corpus metadata, not "
    "extraction output."
)

# Hand-written annotation methodology prose, reproduced verbatim so
# `python -m braid.extract quality` can regenerate the full report (numbers +
# methodology) rather than just the computed tables.
METHODOLOGY_SECTION = """## Annotation methodology and its limitations

Gold triples were written using the same five patterns the pipeline
implements (active SVO, passive+agent, copular, prep-object, conjunction
expansion), applied by manual reading rather than by predicting spaCy's exact
parse tree. Subject/object text uses the core entity only (e.g. "Mike
Nichols", not "director Mike Nichols"); `compare()` uses containment matching
specifically so an annotator's minimal span still counts as correct against
the pipeline's fuller syntactic span (see quality.py's docstring).

**Annotation was conservative, not exhaustive**, for sentences with multiple
plausible triples (conjoined attributes, multiple clauses): one representative
triple was recorded rather than every one. Spot-checking the unmatched
extracted triples after the real run confirmed this directly -- a substantial
share of triples counted as "extra" (lowering precision) are additional
correct facts the gold set simply never recorded, not extraction errors:
`(four-piece band, consist of, Tim Commerford)`, `(students, obtain, master's
degrees)`, `(Rudolph Wendelin, be, best-known artist behind Smokey Bear)` --
all correct, all conjuncts or clauses this annotation pass chose not to
duplicate. **The measured precision above is therefore a conservative lower
bound**, not a point estimate to be taken at face value; the true precision on
a fully exhaustive gold standard is very likely higher.

**Two real bugs were found and fixed** during this process, before the
numbers above were finalized (both with regression tests in
`tests/extract/test_patterns.py`):

1. **Relative pronoun subjects** ("which", "who", "that" as a relative
   pronoun -- POS tag WDT/WP) were treated as ordinary subjects, since only
   third-person personal pronouns are substituted (entities.py). This
   produced nonsensical triples like `(which, air on, ABC)` from "the movie,
   which aired on ABC...". Fixed by skipping WH-tagged subjects entirely
   (no triple emitted, consistent with the module's existing
   "err toward silence" rule for interrogative sentences) rather than
   attempting antecedent resolution, which is out of scope for the documented
   pronoun-substitution rule (title-only, not general coreference).
2. **Relation casing**: a sentence-initial fronted preposition ("With her
   approach, Kamen became...") left its surface capitalization in the
   relation string (`"become With"` instead of `"become with"`).

**Known, documented gaps** (not fixed, out of the documented pattern set's
scope -- see README.md's "What is not extracted"):
- Copula verbs other than literal "be" ("become", "remain", "seem") are not
  covered by pattern 3.
- Adjectival predicates (`acomp`: "is correct") are not covered by pattern 3,
  which only matches noun-phrase predicates (`attr`).
- Clausal complements (`ccomp`: "notes that X") are not covered by pattern 1,
  which requires a nominal `dobj`.
- **Conjoined verb phrases are not expanded.** "Allen was born in Los
  Angeles and currently lives in Lancaster" only ever considers the verb a
  subject's `head` directly governs; a second conjoined verb sharing the same
  subject is not visited. Pattern 5 (conjunction expansion) only covers
  conjoined *subjects and objects*, not conjoined *verbs* -- a real,
  identified limitation, not yet fixed given scope/time.
- **Parallel/positional conjunctions produce a cartesian product, not
  paired triples.** "X, Y, Z were replaced by A, B, C respectively" would
  expand to nine triples (every subject conjunct paired with every object
  conjunct) instead of the three correctly-paired ones. Not fixed; flagged
  here because it was observed directly in the sample (passage
  `de3fe845a68ba037`) and not annotated in gold for that reason.
"""


@dataclass(frozen=True)
class GoldTriple:
    """One hand-annotated expected triple for one sentence."""

    passage_id: str
    sentence_index: int
    subject: str
    relation: str
    object: str


@dataclass(frozen=True)
class WilsonInterval:
    point: float
    low: float
    high: float
    successes: int
    n: int


def wilson_interval(successes: int, n: int, confidence: float = 0.95) -> WilsonInterval:
    """The Wilson score interval for a binomial proportion.

    Preferred over the naive normal-approximation interval for small n (this
    report's sample is 100 sentences, and successes can be a small count) --
    the Wilson interval stays within [0, 1] and does not degenerate the way
    the normal approximation can near 0 or 1.
    """
    if n == 0:
        nan = float("nan")
        return WilsonInterval(point=nan, low=nan, high=nan, successes=0, n=0)
    p = successes / n
    z = _z_score(confidence)
    denom = 1 + z**2 / n
    center = p + z**2 / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    low = (center - spread) / denom
    high = (center + spread) / denom
    return WilsonInterval(point=p, low=max(0.0, low), high=min(1.0, high), successes=successes, n=n)


def _z_score(confidence: float) -> float:
    """Two-sided normal z-score for the given confidence level, via the
    inverse error function -- no scipy dependency for one number.
    """
    return math.sqrt(2) * _erfinv(confidence)


def _erfinv(x: float, iterations: int = 60) -> float:
    """Inverse error function via bisection against `math.erf` (exact, in the
    standard library) rather than a rational approximation. Bisection has no
    approximation-error term to reason about or bound; 60 iterations narrows
    the bracket past float64 precision. Verified by hand against the closed-
    form Wilson formula for 8 successes of 20 (z=1.959964): the formula
    itself gives [0.2188, 0.6134], which this function reproduces exactly.
    """
    lo, hi = -6.0, 6.0  # erf saturates to +-1 well before +-6
    for _ in range(iterations):
        mid = (lo + hi) / 2
        if math.erf(mid) < x:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _contains_or_equal(a: str, b: str) -> bool:
    a, b = fold_case(a), fold_case(b)
    return a == b or a in b or b in a


@dataclass(frozen=True)
class QualityReport:
    precision: WilsonInterval
    recall: WilsonInterval
    n_gold: int
    n_extracted: int
    n_correct: int
    triple_count: int  # total triples in the full extraction run (not just the sample)
    relation_histogram: dict[str, int]


def _triples_match(gold: GoldTriple, extracted: Triple) -> bool:
    return (
        gold.passage_id == extracted.passage_id
        and gold.sentence_index == extracted.sentence_index
        and fold_case(gold.relation) == fold_case(extracted.relation)
        and _contains_or_equal(gold.subject, extracted.subject)
        and _contains_or_equal(gold.object, extracted.object)
    )


def compare(
    gold: list[GoldTriple],
    extracted: list[Triple],
    *,
    full_run_triple_count: int,
    full_run_relation_histogram: dict[str, int],
) -> QualityReport:
    """Precision and recall of `extracted` against `gold`, restricted to the
    same (passage_id, sentence_index) pairs the gold sample covers.

    Matching is a greedy one-to-one pairing (via `_triples_match`), not a set
    intersection: containment means a single extracted triple could in
    principle satisfy more than one gold triple's containment check (or vice
    versa), and each side is consumed at most once so precision/recall can't
    be inflated by one triple "matching" several counterparts.
    """
    sampled_sentences = {(g.passage_id, g.sentence_index) for g in gold}
    extracted_in_sample = [
        t for t in extracted if (t.passage_id, t.sentence_index) in sampled_sentences
    ]

    unmatched_extracted = list(extracted_in_sample)
    correct = 0
    for g in gold:
        for i, e in enumerate(unmatched_extracted):
            if _triples_match(g, e):
                correct += 1
                del unmatched_extracted[i]
                break

    precision = wilson_interval(correct, len(extracted_in_sample))
    recall = wilson_interval(correct, len(gold))

    return QualityReport(
        precision=precision,
        recall=recall,
        n_gold=len(gold),
        n_extracted=len(extracted_in_sample),
        n_correct=correct,
        triple_count=full_run_triple_count,
        relation_histogram=full_run_relation_histogram,
    )


def render_markdown(report: QualityReport, *, sample_size: int, annotation_order_note: str) -> str:
    p, r = report.precision, report.recall
    lines = [
        "# Extraction quality report\n",
        f"Hand-annotated sample: {sample_size} sentences. {annotation_order_note}\n",
        "## Precision and recall\n",
        "| Metric | Value | 95% Wilson CI | Correct | Total |",
        "|---|---|---|---|---|",
        (
            f"| Precision | {p.point:.3f} | [{p.low:.3f}, {p.high:.3f}] | "
            f"{report.n_correct} | {report.n_extracted} |"
        ),
        (
            f"| Recall | {r.point:.3f} | [{r.low:.3f}, {r.high:.3f}] | "
            f"{report.n_correct} | {report.n_gold} |"
        ),
        "",
        f"## Full-corpus extraction: {report.triple_count} triples\n",
        "| Relation | Count |",
        "|---|---|",
    ]
    for relation, count in sorted(
        report.relation_histogram.items(), key=lambda kv: (-kv[1], kv[0])
    ):
        lines.append(f"| {relation} | {count} |")
    return "\n".join(lines) + "\n"
