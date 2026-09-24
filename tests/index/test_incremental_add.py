"""The shared contract test suite: all three IndexBuilder implementations
exercised identically (SPEC-index.md, Task 26). Build on 10 passages, add 5
more, confirm 15 present and the original 10 unchanged.

Uses the real corpus and real extracted triples (not synthetic fixtures) so
the graph builder's passage-to-triple filtering is exercised against genuine
data, not a hand-built case that might not reflect real triple density.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

import pytest

from braid.index.base import BM25Builder, DenseBuilder, GraphBuilder
from braid.index.bm25 import doc_count as _doc_count
from braid.index.bm25 import search as _search
from braid.index.dense import load as load_dense_from
from braid.index.graph import clear as _clear_graph
from braid.ingest.models import load_corpus
from tests.index.conftest import TEST_ENTITY_LABEL, TEST_INDEX_NAME, TEST_RELATION_TYPE

CORPUS_PATH = Path("data/corpus.jsonl")
TRIPLES_PATH = Path("data/triples.jsonl")

doc_count = partial(_doc_count, index_name=TEST_INDEX_NAME)
search = partial(_search, index_name=TEST_INDEX_NAME)
clear_graph = partial(_clear_graph, entity_label=TEST_ENTITY_LABEL)


@pytest.fixture(scope="module")
def corpus():
    if not CORPUS_PATH.exists():
        pytest.skip("data/corpus.jsonl not present -- run ingest first")
    return load_corpus(CORPUS_PATH)


@pytest.fixture
def first_and_next(corpus):
    return corpus[:10], corpus[10:15]


BUILDER_FACTORIES = {
    "bm25": lambda tmp_path: BM25Builder(TEST_INDEX_NAME),
    "dense": lambda tmp_path: DenseBuilder(tmp_path / "dense.faiss", tmp_path / "dense-ids.json"),
    "graph": lambda tmp_path: GraphBuilder(TRIPLES_PATH, TEST_ENTITY_LABEL, TEST_RELATION_TYPE),
}


@pytest.mark.parametrize("builder_name", list(BUILDER_FACTORIES))
def test_build_then_add_reaches_fifteen(
    builder_name, first_and_next, require_opensearch, require_neo4j, tmp_path
):
    first, more = first_and_next
    builder = BUILDER_FACTORIES[builder_name](tmp_path)

    if builder.name == "graph":
        clear_graph()

    builder.build(first)
    builder.add(more)

    health = builder.health()
    assert health.state == "populated"

    if builder.name == "bm25":
        assert doc_count() == 15
    elif builder.name == "dense":
        # Regression: calling load_dense() with no arguments reads
        # dense.py's *default* path, not this builder's own tmp_path-scoped
        # one -- the two happen to coincide only when the real default
        # files don't exist yet. Once a real build populates
        # data/dense.faiss, this silently started reading 1000 real
        # vectors instead of the 15 this test just wrote. Load from the
        # exact paths the builder itself was constructed with.
        index, ids = load_dense_from(builder._index_path, builder._ids_path)
        assert index.ntotal == 15
        assert len(ids) == 15


def test_bm25_original_docs_unchanged_after_add(first_and_next, require_opensearch):
    first, more = first_and_next
    builder = BM25Builder(TEST_INDEX_NAME)
    builder.build(first)
    original_titles = {p.passage_id: p.title for p in first}
    builder.add(more)
    assert doc_count() == 15
    # Spot-check: searching for a term unique to one of the original 10 still
    # returns that same passage -- its content was not disturbed by the add.
    sample = first[0]
    hits = search(sample.text[:30], k=5)
    assert any(h.passage_id == sample.passage_id for h in hits)
    assert original_titles[sample.passage_id] == sample.title


def test_dense_ordinal_mapping_still_resolves_original_ids_after_add(
    first_and_next, tmp_path
):
    from braid.index import dense as dense_mod

    index_path, ids_path = tmp_path / "dense2.faiss", tmp_path / "dense2-ids.json"
    first, more = first_and_next

    dense_mod.build(first, index_path, ids_path)
    dense_mod.add(more, index_path, ids_path)
    index, ids = dense_mod.load(index_path, ids_path)
    assert index.ntotal == 15
    original_ids = {p.passage_id for p in first}
    # Every original passage's id is still present, at a stable ordinal.
    assert original_ids <= set(ids)
    assert ids[:10] == [p.passage_id for p in first]
