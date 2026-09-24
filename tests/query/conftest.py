"""Shared fixtures for tests/query."""

from __future__ import annotations

import pytest

from braid.index.health import check_neo4j, check_opensearch


@pytest.fixture(scope="session")
def opensearch_available() -> bool:
    return check_opensearch().state != "down"


@pytest.fixture(scope="session")
def neo4j_available() -> bool:
    return check_neo4j().state != "down"


@pytest.fixture
def require_opensearch(opensearch_available: bool) -> None:
    if not opensearch_available:
        pytest.skip("OpenSearch container is not reachable (docker compose up -d)")


@pytest.fixture
def require_neo4j(neo4j_available: bool) -> None:
    if not neo4j_available:
        pytest.skip("Neo4j container is not reachable (docker compose up -d)")
