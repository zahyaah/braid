import json

import pytest

from braid.ingest.freeze import FrozenCorpusError, corpus_hash, ensure_mutable, freeze, verify
from braid.ingest.manifest import Manifest
from braid.ingest.models import Passage


def passages(texts: list[str]) -> list[Passage]:
    return [
        Passage(passage_id=f"id{i:02d}", title=f"T{i}", text=text, sentence_spans=((0, len(text)),))
        for i, text in enumerate(texts)
    ]


def write_manifest(tmp_path):
    manifest = Manifest(
        dataset="d",
        config="c",
        split="validation",
        datasets_version="0",
        seed=1,
        target_passages=10,
        questions_sampled=1,
        questions_out=1,
        passages_before_dedupe=2,
        passages_after_dedupe=2,
        dedupe={},
        remap={},
    )
    path = tmp_path / "manifest.json"
    manifest.write(path)
    return path


def test_corpus_hash_is_stable_across_runs():
    corpus = passages(["one", "two"])
    assert corpus_hash(corpus) == corpus_hash(corpus)


def test_corpus_hash_ignores_list_order():
    corpus = passages(["one", "two"])
    assert corpus_hash(corpus) == corpus_hash(list(reversed(corpus)))


def test_corpus_hash_changes_when_any_passage_text_changes():
    before = corpus_hash(passages(["one", "two"]))
    after = corpus_hash(passages(["one", "two!"]))
    assert before != after


def test_freeze_records_hash_and_sets_flags(tmp_path):
    path = write_manifest(tmp_path)
    corpus = passages(["one", "two"])
    manifest = freeze(path, corpus)
    assert manifest.frozen is True
    assert manifest.frozen_at is not None
    assert manifest.corpus_hash == corpus_hash(corpus)
    on_disk = json.loads(path.read_text())
    assert on_disk["frozen"] is True
    assert on_disk["corpus_hash"] == manifest.corpus_hash


def test_ensure_mutable_blocks_writes_to_a_frozen_corpus(tmp_path):
    path = write_manifest(tmp_path)
    freeze(path, passages(["one"]))
    manifest = Manifest.read(path)
    with pytest.raises(FrozenCorpusError, match="refusing to rewrite passage"):
        ensure_mutable(manifest, "rewrite passage id00")


def test_ensure_mutable_allows_writes_before_the_freeze(tmp_path):
    ensure_mutable(Manifest.read(write_manifest(tmp_path)), "rewrite passage id00")


def test_freeze_is_idempotent_when_nothing_changed(tmp_path):
    path = write_manifest(tmp_path)
    corpus = passages(["one"])
    first = freeze(path, corpus)
    second = freeze(path, corpus)
    assert first.corpus_hash == second.corpus_hash
    assert first.frozen_at == second.frozen_at


def test_refreezing_a_changed_corpus_raises(tmp_path):
    path = write_manifest(tmp_path)
    freeze(path, passages(["one"]))
    with pytest.raises(FrozenCorpusError, match="content hash has changed"):
        freeze(path, passages(["one", "two"]))


def test_verify_detects_a_corpus_that_drifted_from_its_frozen_hash(tmp_path):
    path = write_manifest(tmp_path)
    freeze(path, passages(["one"]))
    verify(path, passages(["one"]))
    with pytest.raises(FrozenCorpusError, match="corpus hash mismatch"):
        verify(path, passages(["one", "two"]))


def test_verify_refuses_an_unfrozen_corpus(tmp_path):
    with pytest.raises(FrozenCorpusError, match="not frozen"):
        verify(write_manifest(tmp_path), passages(["one"]))
