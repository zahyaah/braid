import pytest

from braid.index.dense import DIMENSION, add, build, load, search
from braid.ingest.models import Passage


def make_passage(pid: str, title: str, text: str) -> Passage:
    return Passage(pid, title, text, ((0, len(text)),), "test")


@pytest.fixture
def paths(tmp_path):
    return tmp_path / "dense.faiss", tmp_path / "dense-ids.json"


@pytest.mark.slow
def test_build_writes_index_and_ids_with_matching_lengths(paths):
    index_path, ids_path = paths
    passages = [
        make_passage("p1", "Scott Derrickson", "Scott Derrickson directed a horror film."),
        make_passage("p2", "Ed Wood", "Ed Wood is a 1994 biographical film."),
        make_passage("p3", "Gardening", "A completely unrelated passage about gardening."),
    ]
    n = build(passages, index_path, ids_path)
    assert n == 3
    index, ids = load(index_path, ids_path)
    assert index.ntotal == 3
    assert len(ids) == 3
    assert index.d == DIMENSION


@pytest.mark.slow
def test_search_finds_semantically_similar_passage_without_lexical_overlap(paths):
    index_path, ids_path = paths
    passages = [
        make_passage(
            "p1", "Doctor Strange",
            "A 2016 superhero film about a neurosurgeon who becomes a sorcerer.",
        ),
        make_passage("p2", "Gardening", "A completely unrelated passage about gardening."),
    ]
    build(passages, index_path, ids_path)
    # Query shares no vocabulary with p1's text at all -- purely semantic match.
    query = "Which movie is about a surgeon turned sorcerer?"
    hits = search(query, k=2, index_path=index_path, ids_path=ids_path)
    assert hits
    assert hits[0].passage_id == "p1"


@pytest.mark.slow
def test_incremental_add_appends_without_disturbing_existing_ordinals(paths):
    index_path, ids_path = paths
    build([make_passage("p1", "A", "first passage text here")], index_path, ids_path)
    add([make_passage("p2", "B", "second passage text here")], index_path, ids_path)
    index, ids = load(index_path, ids_path)
    assert index.ntotal == 2
    assert ids == ["p1", "p2"]


@pytest.mark.slow
def test_load_raises_on_ordinal_id_length_mismatch(paths, tmp_path):
    import json

    index_path, ids_path = paths
    two_passages = [make_passage("p1", "A", "text one"), make_passage("p2", "B", "text two")]
    build(two_passages, index_path, ids_path)
    # Corrupt ids.json to simulate a bad partial write.
    ids_path.write_text(json.dumps(["p1"]))
    with pytest.raises(ValueError, match="ordinal-to-passage-id"):
        load(index_path, ids_path)
