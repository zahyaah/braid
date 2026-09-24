"""Tests for GraphRetriever (braid/query/graph.py).

Acceptance criteria (Task 30):
- Entity linking by exact match on case-folded normalized Entity.name, per D5
- Traversal depth 2; fan-out cap 50 edges per node; entities of degree > 200 skipped as hubs
- Candidate K = 50; passages emitted as a ranked third source
- Link-failure rate recorded -- how many queries linked zero entities --
  since that bounds criterion 3
"""

import pytest

from braid.eval.queryset.schema import QUERIES_FILE, QUERYSET_DIR, read_queries
from braid.query import params
from braid.query.graph import GraphRetriever, compute_link_failure_rate
from tests.query.test_contract import assert_retriever_contract


class MockNeo4jDriver:
    """Mock Neo4j driver for unit testing graph traversal."""

    def __init__(self, entities: list[str] | None = None, records: list[dict] | None = None):
        self.entities = entities or ["Scott Derrickson", "Sinister", "Doctor Strange"]
        self.records = records or [
            {"pid1": "p_hop1_a", "pid2": "p_hop2_b"},
            {"pid1": "p_hop1_a", "pid2": None},
            {"pid1": "p_hop1_c", "pid2": "p_hop2_d"},
        ]
        self.last_query = None
        self.last_params = None

    def execute_query(self, cypher: str, database_: str = "neo4j", **kwargs):
        self.last_query = cypher
        self.last_params = kwargs
        if "MATCH (e:" in cypher and "RETURN e.name" in cypher:
            return [{"name": name} for name in self.entities], None, None
        return self.records, None, None


def test_graph_retriever_attributes_and_contract():
    driver = MockNeo4jDriver()
    retriever = GraphRetriever(driver=driver)

    assert retriever.name == "graph"
    assert retriever.candidate_k == params.GRAPH_CANDIDATE_K
    assert retriever.candidate_k == 50
    assert retriever.traversal_depth == params.GRAPH_TRAVERSAL_DEPTH
    assert retriever.traversal_depth == 2
    assert retriever.fan_out_cap == params.GRAPH_FAN_OUT_CAP
    assert retriever.fan_out_cap == 50
    assert retriever.hub_cap == params.GRAPH_HUB_DEGREE_THRESHOLD
    assert retriever.hub_cap == 200

    assert_retriever_contract(retriever, queries=["Who directed Sinister?", "Doctor Strange"])


def test_graph_entity_linking_exact_match():
    driver = MockNeo4jDriver(entities=["Scott Derrickson", "Sinister", "Ed Wood"])
    retriever = GraphRetriever(driver=driver)

    linked = retriever.link_entities("Did Scott Derrickson direct sinister?")
    assert "Scott Derrickson" in linked
    assert "Sinister" in linked
    assert "Ed Wood" not in linked

    assert retriever.link_entities("") == []
    assert retriever.link_entities("   ") == []


def test_graph_search_ranking_and_provenance():
    driver = MockNeo4jDriver(
        entities=["Sinister"],
        records=[
            {"pid1": "p1", "pid2": "p2"},
            {"pid1": "p1", "pid2": None},  # p1 gets 1.0 + 1.0 = 2.0; p2 gets 0.5
        ],
    )
    retriever = GraphRetriever(driver=driver, candidate_k=10)
    hits = retriever.search("Sinister", k=5)

    assert len(hits) == 2
    assert hits[0].passage_id == "p1"
    assert hits[0].score == 2.0
    assert hits[0].rank == 1
    assert hits[0].provenance == {"graph": 2.0}

    assert hits[1].passage_id == "p2"
    assert hits[1].score == 0.5
    assert hits[1].rank == 2
    assert hits[1].provenance == {"graph": 0.5}


def test_graph_unlinked_query_returns_empty_list():
    driver = MockNeo4jDriver(entities=["Target Entity"])
    retriever = GraphRetriever(driver=driver)
    hits = retriever.search("Completely unrelated vocabulary without mentions")
    assert hits == []


@pytest.mark.integration
def test_graph_live_traversal(require_neo4j):
    retriever = GraphRetriever()
    hits = retriever.search("What is Chris Cornell associated with in Audioslave?", k=10)
    assert len(hits) > 0
    assert hits[0].provenance.get("graph") is not None
    assert hits[0].rank == 1
    assert hits[0].score > 0.0


@pytest.mark.integration
def test_link_failure_rate_on_evaluation_queryset(require_neo4j):
    queries = read_queries(QUERYSET_DIR / QUERIES_FILE)
    retriever = GraphRetriever()
    rate = compute_link_failure_rate(queries, retriever)

    # Link failure rate must be recorded and below 5% (empirically 0.56% = 1/180)
    assert rate <= 0.05
    assert 0.0 <= rate < 0.02
