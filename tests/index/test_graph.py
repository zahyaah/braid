from functools import partial

import pytest

from braid.extract.models import Triple
from braid.index.graph import _driver
from braid.index.graph import clear as _clear
from braid.index.graph import counts as _counts
from braid.index.graph import load_triples as _load_triples
from tests.index.conftest import TEST_ENTITY_LABEL, TEST_RELATION_TYPE

clear = partial(_clear, entity_label=TEST_ENTITY_LABEL)
counts = partial(_counts, entity_label=TEST_ENTITY_LABEL, relation_type=TEST_RELATION_TYPE)
load_triples = partial(
    _load_triples, entity_label=TEST_ENTITY_LABEL, relation_type=TEST_RELATION_TYPE
)


def make_triple(subj, rel, obj, pid="p1", idx=0, subj_type=None, obj_type=None) -> Triple:
    return Triple(subj, rel, obj, pid, idx, subj_type, obj_type, pattern="active_svo")


@pytest.fixture(autouse=True)
def clean_graph(require_neo4j):
    clear()
    yield
    clear()


def test_load_creates_nodes_and_edges(require_neo4j):
    triples = [
        make_triple("Scott Derrickson", "direct", "Sinister", subj_type="PERSON"),
        make_triple("Scott Derrickson", "write", "Doctor Strange", subj_type="PERSON"),
    ]
    report = load_triples(triples)
    # 3 distinct entities (Scott Derrickson, Sinister, Doctor Strange), 2 edges.
    assert report.nodes == 3
    assert report.edges == 2


def test_repeated_load_is_idempotent_for_identical_triples(require_neo4j):
    triples = [make_triple("A", "know", "B")]
    load_triples(triples)
    report = load_triples(triples)
    assert report.nodes == 2
    assert report.edges == 1


def test_entity_uniqueness_merges_same_name_across_triples(require_neo4j):
    triples = [
        make_triple("Scott Derrickson", "direct", "Sinister"),
        make_triple("Scott Derrickson", "write", "Sinister"),
    ]
    report = load_triples(triples)
    assert report.nodes == 2  # not 4 -- "Scott Derrickson" and "Sinister" each merge to one node
    assert report.edges == 2  # two distinct relations between the same pair


def test_entity_type_is_set_when_known_and_absent_when_not(require_neo4j):
    triples = [
        make_triple("Scott Derrickson", "direct", "Sinister", subj_type="PERSON", obj_type=None)
    ]
    load_triples(triples)
    driver = _driver()
    records, _, _ = driver.execute_query(
        f"MATCH (e:{TEST_ENTITY_LABEL} {{name: 'Scott Derrickson'}}) RETURN e.type AS t",
        database_="neo4j",
    )
    assert records[0]["t"] == "PERSON"
    records, _, _ = driver.execute_query(
        f"MATCH (e:{TEST_ENTITY_LABEL} {{name: 'Sinister'}}) RETURN e.type AS t",
        database_="neo4j",
    )
    assert records[0]["t"] is None


def test_counts_matches_the_triple_file(require_neo4j):
    triples = [
        make_triple("A", "know", "B"),
        make_triple("B", "know", "C"),
        make_triple("C", "know", "A"),
    ]
    load_triples(triples)
    report = counts()
    assert report.nodes == 3
    assert report.edges == 3
