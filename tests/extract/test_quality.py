"""Wilson interval and precision/recall matching, checked against values
hand-derived from the closed-form Wilson formula (see quality.py's _erfinv
docstring for the derivation of the 8/20 reference).
"""

import math

from braid.extract.models import Triple
from braid.extract.quality import GoldTriple, compare, render_markdown, wilson_interval


def test_wilson_interval_matches_hand_derived_8_of_20():
    result = wilson_interval(8, 20)
    assert math.isclose(result.point, 0.4, rel_tol=1e-9)
    assert math.isclose(result.low, 0.2188, abs_tol=1e-3)
    assert math.isclose(result.high, 0.6134, abs_tol=1e-3)


def test_wilson_interval_matches_hand_derived_50_of_100():
    # center = (0.5 + z^2/200) / (1 + z^2/100); z^2 = 3.841459
    # center = (0.5 + 0.019207) / 1.038415 = 0.519207/1.038415 = 0.500000
    # half-width = z/1.038415 * sqrt(0.25/100 + z^2/40000)
    #            = 1.887530 * sqrt(0.0025 + 0.000096) = 1.887530 * 0.050952 = 0.096178
    result = wilson_interval(50, 100)
    assert math.isclose(result.point, 0.5, rel_tol=1e-9)
    assert math.isclose(result.low, 0.5 - 0.09613, abs_tol=1e-3)
    assert math.isclose(result.high, 0.5 + 0.09613, abs_tol=1e-3)


def test_wilson_interval_zero_successes_stays_within_bounds():
    result = wilson_interval(0, 10)
    assert result.low == 0.0
    assert 0.0 < result.high < 1.0


def test_wilson_interval_all_successes_stays_within_bounds():
    result = wilson_interval(10, 10)
    assert result.high <= 1.0
    assert 0.0 < result.low < 1.0


def test_wilson_interval_empty_sample_is_nan_not_a_crash():
    result = wilson_interval(0, 0)
    assert result.point != result.point  # NaN


def test_wilson_interval_narrows_with_larger_n_same_proportion():
    small = wilson_interval(4, 10)
    large = wilson_interval(40, 100)
    assert (large.high - large.low) < (small.high - small.low)


def gold(pid, idx, s, r, o) -> GoldTriple:
    return GoldTriple(passage_id=pid, sentence_index=idx, subject=s, relation=r, object=o)


def triple(pid, idx, s, r, o) -> Triple:
    return Triple(
        subject=s, relation=r, object=o, passage_id=pid, sentence_index=idx,
        subject_type=None, object_type=None, pattern="active_svo",
    )


def test_compare_perfect_match_gives_precision_and_recall_of_one():
    gold_set = [gold("p1", 0, "Scott Derrickson", "direct", "Sinister")]
    extracted = [triple("p1", 0, "Scott Derrickson", "direct", "Sinister")]
    report = compare(
        gold_set, extracted, full_run_triple_count=1, full_run_relation_histogram={"direct": 1}
    )
    assert report.precision.point == 1.0
    assert report.recall.point == 1.0
    assert report.n_correct == 1


def test_compare_is_case_insensitive_on_the_match_key():
    gold_set = [gold("p1", 0, "Scott Derrickson", "direct", "Sinister")]
    extracted = [triple("p1", 0, "scott derrickson", "direct", "sinister")]
    report = compare(gold_set, extracted, full_run_triple_count=1, full_run_relation_histogram={})
    assert report.n_correct == 1


def test_compare_matches_when_extracted_span_contains_the_gold_entity():
    # The realistic case: patterns.py's span is the full subtree ("director
    # Mike Nichols"), while a human annotator writes the core entity
    # ("Mike Nichols"). Containment must count this as correct.
    gold_set = [gold("p1", 0, "Mike Nichols", "work on", "film script")]
    extracted = [triple("p1", 0, "director Mike Nichols", "work on", "film script")]
    report = compare(gold_set, extracted, full_run_triple_count=1, full_run_relation_histogram={})
    assert report.n_correct == 1


def test_compare_does_not_match_across_different_relations():
    gold_set = [gold("p1", 0, "Mike Nichols", "direct", "the film")]
    extracted = [triple("p1", 0, "director Mike Nichols", "work on", "film script")]
    report = compare(gold_set, extracted, full_run_triple_count=1, full_run_relation_histogram={})
    assert report.n_correct == 0


def test_compare_greedy_matching_does_not_double_count():
    # One extracted triple can only satisfy one gold triple, even if it
    # would contain-match several.
    gold_set = [
        gold("p1", 0, "Mike", "direct", "X"),
        gold("p1", 0, "Nichols", "direct", "X"),
    ]
    extracted = [triple("p1", 0, "Mike Nichols", "direct", "X")]
    report = compare(gold_set, extracted, full_run_triple_count=1, full_run_relation_histogram={})
    assert report.n_correct == 1
    assert report.n_gold == 2
    assert report.n_extracted == 1


def test_compare_a_false_positive_lowers_precision_not_recall():
    gold_set = [gold("p1", 0, "A", "r", "B")]
    extracted = [
        triple("p1", 0, "A", "r", "B"),
        triple("p1", 0, "C", "r", "D"),  # extra, wrong
    ]
    report = compare(gold_set, extracted, full_run_triple_count=2, full_run_relation_histogram={})
    assert report.precision.point == 0.5
    assert report.recall.point == 1.0


def test_compare_a_missed_gold_triple_lowers_recall_not_precision():
    gold_set = [gold("p1", 0, "A", "r", "B"), gold("p1", 0, "C", "r", "D")]
    extracted = [triple("p1", 0, "A", "r", "B")]  # missed the second
    report = compare(gold_set, extracted, full_run_triple_count=1, full_run_relation_histogram={})
    assert report.precision.point == 1.0
    assert report.recall.point == 0.5


def test_compare_ignores_extracted_triples_outside_the_sampled_sentences():
    # A triple from a sentence not in the gold sample must not count against
    # precision -- the sample defines the denominator, not the whole corpus.
    gold_set = [gold("p1", 0, "A", "r", "B")]
    extracted = [
        triple("p1", 0, "A", "r", "B"),
        triple("p2", 5, "X", "r", "Y"),  # different sentence, not sampled
    ]
    report = compare(gold_set, extracted, full_run_triple_count=2, full_run_relation_histogram={})
    assert report.n_extracted == 1
    assert report.precision.point == 1.0


def test_render_markdown_includes_precision_recall_and_histogram():
    gold_set = [gold("p1", 0, "A", "r", "B")]
    extracted = [triple("p1", 0, "A", "r", "B")]
    histogram = {"direct": 30, "write": 12}
    report = compare(
        gold_set, extracted, full_run_triple_count=42, full_run_relation_histogram=histogram
    )
    markdown = render_markdown(
        report, sample_size=100, annotation_order_note="Annotated before extraction."
    )
    assert "Precision" in markdown
    assert "Recall" in markdown
    assert "42" in markdown
    assert "direct" in markdown and "30" in markdown
