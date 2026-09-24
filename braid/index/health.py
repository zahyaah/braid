"""Health checks for the three-service local stack (OpenSearch, FAISS index
files, Neo4j). `health()` distinguishes container-down, reachable-but-empty,
and populated-with-N (SPEC-index.md, Task 22) -- the boring failure modes of
a multi-service local stack need to be diagnosable from one command.

Client API calls, grounded in official docs (workflow step 5):
- OpenSearch instantiation (no-auth, local): "hosts=[{'host':..,'port':..}],
  use_ssl=False, verify_certs=False" --
  https://docs.opensearch.org/latest/clients/python-low-level/
- `client.ping()` -- "Returns whether the cluster is running" --
  https://opensearch-project.github.io/opensearch-py/api-ref/clients/opensearch_client.html
- `client.cluster.health()` -- ClusterClient.health() --
  https://opensearch-project.github.io/opensearch-py/api-ref/clients/cluster_client.html
- `client.indices.exists()` -- IndicesClient.exists() --
  https://opensearch-project.github.io/opensearch-py/api-ref/clients/opensearch_client.html
- Neo4j `GraphDatabase.driver(uri, auth=(...))` and `driver.verify_connectivity()` --
  https://neo4j.com/docs/python-manual/current/connect/
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

State = Literal["down", "empty", "populated"]

DEFAULT_OPENSEARCH_HOST = "localhost"
DEFAULT_OPENSEARCH_PORT = 9200
DEFAULT_OPENSEARCH_INDEX = "braid-passages"
DEFAULT_NEO4J_URI = "neo4j://localhost:7687"
DEFAULT_NEO4J_AUTH = ("neo4j", "braid-local-only")
DEFAULT_ENTITY_LABEL = "Entity"


@dataclass(frozen=True)
class StoreHealth:
    name: str
    state: State
    count: int | None  # None when down; 0+ otherwise
    detail: str


def check_opensearch(
    host: str = DEFAULT_OPENSEARCH_HOST,
    port: int = DEFAULT_OPENSEARCH_PORT,
    index: str = DEFAULT_OPENSEARCH_INDEX,
) -> StoreHealth:
    from opensearchpy import OpenSearch
    from opensearchpy.exceptions import ConnectionError as OSConnectionError
    from opensearchpy.exceptions import NotFoundError

    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        use_ssl=False,
        verify_certs=False,
        ssl_show_warn=False,
    )
    try:
        if not client.ping():
            return StoreHealth("opensearch", "down", None, f"ping failed at {host}:{port}")
    except OSConnectionError as exc:
        return StoreHealth("opensearch", "down", None, f"connection failed: {exc}")

    empty_detail = f"reachable, index {index!r} does not exist"
    try:
        if not client.indices.exists(index=index):
            return StoreHealth("opensearch", "empty", 0, empty_detail)
        count = client.count(index=index)["count"]
    except NotFoundError:
        return StoreHealth("opensearch", "empty", 0, empty_detail)

    if count == 0:
        return StoreHealth("opensearch", "empty", 0, f"index {index!r} exists but has 0 documents")
    return StoreHealth("opensearch", "populated", count, f"{count} documents in {index!r}")


def check_neo4j(
    uri: str = DEFAULT_NEO4J_URI,
    auth: tuple[str, str] = DEFAULT_NEO4J_AUTH,
    entity_label: str = DEFAULT_ENTITY_LABEL,
) -> StoreHealth:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable

    # `GraphDatabase.driver` only describes how to connect; it does not
    # itself open a connection, so the driver object exists (and must be
    # closed) even when verify_connectivity() then fails -- left unclosed on
    # that path in an earlier version, which the driver flagged as a
    # deprecation warning during testing.
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        driver.verify_connectivity()
    except ServiceUnavailable as exc:
        driver.close()
        return StoreHealth("neo4j", "down", None, f"connection failed: {exc}")

    # Scoped to `entity_label`, not every node in the database: Neo4j
    # Community has no multi-database isolation, so tests use a distinct
    # label (see graph.py's module docstring) and this check must respect
    # that scope to mean anything -- counting every node would report
    # "populated" from another label's leftover data.
    from braid.index.graph import _validate_label

    label = _validate_label(entity_label)
    try:
        records, _, _ = driver.execute_query(f"MATCH (n:{label}) RETURN count(n) AS c")
        count = records[0]["c"]
    finally:
        driver.close()

    if count == 0:
        return StoreHealth("neo4j", "empty", 0, f"reachable, 0 {label!r}-labeled nodes")
    return StoreHealth("neo4j", "populated", count, f"{count} {label!r}-labeled nodes")


def health() -> list[StoreHealth]:
    """All store health checks, in a fixed order (opensearch, neo4j)."""
    return [check_opensearch(), check_neo4j()]
