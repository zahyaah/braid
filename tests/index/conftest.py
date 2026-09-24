"""Shared fixtures for the /index test suite.

Integration tests against real OpenSearch/Neo4j containers skip cleanly with
a stated reason when the containers are down (SPEC-index.md, Task 22
acceptance) -- they must never fail the suite just because `docker compose
up` hasn't been run.

**Test isolation.** Every test in this directory must use `TEST_INDEX_NAME`
(OpenSearch) and `TEST_ENTITY_LABEL`/`TEST_RELATION_TYPE` (Neo4j), never the
real defaults -- the real defaults are the actual deliverable build. Running
the suite against the real names previously overwrote the real corpus-scale
BM25 index and dropped the real Neo4j graph from 6,862 nodes to 130,
discovered by running `python -m braid.index health` right after a test run.
"""

from __future__ import annotations

import pytest

from braid.index.health import check_neo4j, check_opensearch

TEST_INDEX_NAME = "braid-passages-test"
TEST_ENTITY_LABEL = "TestEntity"
TEST_RELATION_TYPE = "TEST_RELATION"


@pytest.fixture(scope="session")
def opensearch_available() -> bool:
    return check_opensearch().state != "down"


@pytest.fixture(scope="session")
def neo4j_available() -> bool:
    return check_neo4j().state != "down"


@pytest.fixture
def require_opensearch(opensearch_available):
    if not opensearch_available:
        pytest.skip("OpenSearch container is not reachable (docker compose up -d)")


@pytest.fixture
def require_neo4j(neo4j_available):
    if not neo4j_available:
        pytest.skip("Neo4j container is not reachable (docker compose up -d)")


@pytest.fixture(scope="session", autouse=True)
def _close_cached_neo4j_drivers():
    """graph.py caches a driver per (uri, auth) at module level; close it at
    session end rather than leaving the process to rely on the driver's
    deprecated close-on-destruction behavior.
    """
    yield
    from braid.index.graph import close_all

    close_all()


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_artifacts(opensearch_available, neo4j_available):
    """Leave no trace in the real services: delete the test OpenSearch index
    and clear test-labeled Neo4j nodes at session end. Scoped to the test
    names specifically (see module docstring), so this can never touch real
    deliverable data.
    """
    yield
    if opensearch_available:
        from braid.index.bm25 import _client

        client = _client()
        if client.indices.exists(index=TEST_INDEX_NAME):
            client.indices.delete(index=TEST_INDEX_NAME)
    if neo4j_available:
        from braid.index.graph import clear

        clear(entity_label=TEST_ENTITY_LABEL)
