"""End-to-end CLI tests, offline, against the fake dataset."""

import pytest

from braid.ingest import __main__ as cli
from braid.ingest.freeze import corpus_hash
from braid.ingest.manifest import Manifest
from braid.ingest.models import load_corpus, load_questions


@pytest.fixture
def paths(tmp_path):
    return {
        "corpus": tmp_path / "corpus.jsonl",
        "questions": tmp_path / "questions.jsonl",
        "manifest": tmp_path / "manifest.json",
    }


def run(argv, paths):
    return cli.main(
        [
            "--out", str(paths["corpus"]),
            "--questions", str(paths["questions"]),
            "--manifest", str(paths["manifest"]),
            *argv,
        ]
    )


@pytest.fixture(autouse=True)
def offline_dataset(monkeypatch, fake_dataset):
    monkeypatch.setattr(cli, "load_hotpotqa", lambda split=None: fake_dataset)


def test_build_writes_corpus_questions_and_manifest(paths):
    assert run(["build", "--seed", "5", "--target", "10"], paths) == 0
    corpus = load_corpus(paths["corpus"])
    questions = load_questions(paths["questions"])
    manifest = Manifest.read(paths["manifest"])
    assert len(corpus) == 10
    assert len(questions) == 1
    assert manifest.passages_after_dedupe == 10
    assert manifest.corpus_hash == corpus_hash(corpus)
    assert manifest.frozen is False


def test_two_builds_with_the_same_seed_are_byte_identical(paths):
    run(["build", "--seed", "5", "--target", "30"], paths)
    first = paths["corpus"].read_bytes()
    run(["build", "--seed", "5", "--target", "30"], paths)
    assert paths["corpus"].read_bytes() == first


def test_no_question_has_a_dangling_supporting_passage(paths):
    run(["build", "--seed", "5", "--target", "50"], paths)
    ids = {passage.passage_id for passage in load_corpus(paths["corpus"])}
    for question in load_questions(paths["questions"]):
        assert set(question.supporting_passage_ids) <= ids


def test_incremental_add_adds_new_passages_and_changes_no_existing_id(paths):
    run(["build", "--seed", "5", "--target", "10"], paths)
    before = {p.passage_id: p for p in load_corpus(paths["corpus"])}
    assert len(before) == 10

    assert run(["add", "--seed", "11", "--target", "20"], paths) == 0
    after = {p.passage_id: p for p in load_corpus(paths["corpus"])}

    assert len(after) > len(before)
    for pid, passage in before.items():
        assert after[pid] == passage, "an existing passage changed during add"


def test_add_records_both_hashes_in_the_manifest(paths):
    run(["build", "--seed", "5", "--target", "10"], paths)
    before_hash = Manifest.read(paths["manifest"]).corpus_hash
    run(["add", "--seed", "11", "--target", "20"], paths)
    manifest = Manifest.read(paths["manifest"])
    assert len(manifest.hash_history) == 1
    entry = manifest.hash_history[0]
    assert entry["before"] == before_hash
    assert entry["after"] == manifest.corpus_hash
    assert entry["added"] > 0


def test_freeze_then_verify_round_trips(paths):
    run(["build", "--seed", "5", "--target", "10"], paths)
    assert run(["freeze"], paths) == 0
    manifest = Manifest.read(paths["manifest"])
    assert manifest.frozen is True
    assert run(["verify"], paths) == 0


def test_add_after_freeze_keeps_every_existing_passage_id(paths):
    run(["build", "--seed", "5", "--target", "10"], paths)
    run(["freeze"], paths)
    before = {p.passage_id: p for p in load_corpus(paths["corpus"])}
    run(["add", "--seed", "11", "--target", "20"], paths)
    after = {p.passage_id: p for p in load_corpus(paths["corpus"])}
    assert set(before) <= set(after)
    for pid, passage in before.items():
        assert after[pid] == passage


def test_both_drop_counters_are_reported_even_when_zero(paths, capsys):
    run(["build", "--seed", "5", "--target", "10"], paths)
    out = capsys.readouterr().out
    assert "dropped_missing 0" in out
    assert "dropped_collapsed 0" in out
    manifest = Manifest.read(paths["manifest"])
    assert manifest.remap["questions_dropped_collapsed"] == 0
    assert manifest.remap["questions_dropped_missing"] == 0
