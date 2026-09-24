"""Train/dev split guarantees (review findings on checkpoint selection)."""

from braid.finetune.pairs import Pair
from braid.finetune.train import split_pairs


def _pairs():
    out = []
    for i in range(20):
        qid = f"q{i:02d}"
        out.append(Pair(f"{qid}:pos:0", f"query {i}?", f"T{i}: gold {i}", 1))
        out.append(Pair(f"{qid}:neg:0", f"query {i}?", f"D{i}: distractor {i}", 0))
    return out


def test_split_is_by_question_no_query_spans_both_halves():
    train, dev = split_pairs(_pairs(), validation_fraction=0.2, seed=1)
    assert {p.guid.split(":")[0] for p in train}.isdisjoint({p.guid.split(":")[0] for p in dev})


def test_dev_pairs_whose_passage_appears_in_train_are_dropped():
    # A passage reused across questions (HotpotQA does this) would otherwise sit
    # in both halves and inflate the dev score that selects the checkpoint.
    pairs = _pairs() + [
        Pair("q00:neg:1", "query 0?", "SHARED: reused paragraph", 0),
        Pair("q19:neg:1", "query 19?", "SHARED: reused paragraph", 0),
    ]
    train, dev = split_pairs(pairs, validation_fraction=0.5, seed=3)
    train_passages = {p.passage for p in train}
    assert not any(p.passage in train_passages for p in dev)
