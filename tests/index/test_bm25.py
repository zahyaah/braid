from functools import partial

from braid.index.bm25 import add as _add
from braid.index.bm25 import build as _build
from braid.index.bm25 import doc_count as _doc_count
from braid.index.bm25 import search as _search
from braid.ingest.models import Passage
from tests.index.conftest import TEST_INDEX_NAME

build = partial(_build, index_name=TEST_INDEX_NAME)
add = partial(_add, index_name=TEST_INDEX_NAME)
doc_count = partial(_doc_count, index_name=TEST_INDEX_NAME)
search = partial(_search, index_name=TEST_INDEX_NAME)


def make_passage(pid: str, title: str, text: str) -> Passage:
    return Passage(pid, title, text, ((0, len(text)),), "test")


def test_build_indexes_all_passages_and_count_matches(require_opensearch):
    passages = [
        make_passage("p1", "Scott Derrickson", "Scott Derrickson directed the film Sinister."),
        make_passage("p2", "Ed Wood", "Ed Wood is a 1994 biographical film about a director."),
        make_passage("p3", "Unrelated", "A completely unrelated passage about gardening."),
    ]
    report = build(passages)
    assert report.errors == []
    assert report.indexed == 3
    assert doc_count() == 3


def test_search_finds_lexical_match(require_opensearch):
    passages = [
        make_passage("p1", "Scott Derrickson", "Scott Derrickson directed the film Sinister."),
        make_passage("p2", "Ed Wood", "Ed Wood is a 1994 biographical film about a director."),
    ]
    build(passages)
    hits = search("Sinister", k=5)
    assert hits
    assert hits[0].passage_id == "p1"


def test_rebuild_is_idempotent_not_accumulating(require_opensearch):
    passages = [make_passage("p1", "A", "first version of the text")]
    build(passages)
    assert doc_count() == 1
    build(passages)
    assert doc_count() == 1


def test_incremental_add_does_not_drop_existing_docs(require_opensearch):
    build([make_passage("p1", "A", "first passage text here")])
    assert doc_count() == 1
    add([make_passage("p2", "B", "second passage text here")])
    assert doc_count() == 2
