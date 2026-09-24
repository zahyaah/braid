"""Neo4j graph loader: (entity, relation, entity) triples -> a property graph.

Grounded (workflow step 5):
- `driver.execute_query(cypher, **params, database_=...)` --
  https://neo4j.com/docs/python-manual/current/query-simple/
- `UNWIND $rows AS row ... MERGE ...` batch pattern -- same page.
- `CREATE CONSTRAINT name FOR (n:Label) REQUIRE n.property IS UNIQUE` --
  https://neo4j.com/docs/cypher-manual/current/constraints/managing-constraints/
  (`IF NOT EXISTS` is standard Cypher DDL idempotency syntax.)

Schema: `(:Entity {name, type})` nodes, `[:RELATION {relation, passage_id,
sentence_index}]` edges (SPEC-index.md, Task 25). A uniqueness constraint on
`Entity.name` makes every `MERGE (:Entity {name: ...})` an upsert rather than
a duplicate-risking create.

`type` is frequently absent (extraction's own quality report: 40-55% of
triples have no resolved entity type) and Neo4j has no null property value --
setting one removes it. Types are therefore applied in a second pass, over
only the rows that have one, rather than attempted inline in the same MERGE
that creates the node.

**Test isolation via label, not database.** Neo4j Community Edition (this
project's stated target, SPEC.md) supports exactly one database -- multi-
database isolation is an Enterprise-only feature. An earlier version of this
module hardcoded the `Entity`/`RELATION` label and relationship type, which
meant every test run wrote into the *same* graph as the real deliverable
build: running the test suite after a real corpus-scale load dropped the real
graph from 6,862 nodes to 130, discovered by running `python -m braid.index
health` right after a test run. `entity_label`/`relation_type` are now
parameters (defaulting to the real names), and tests use distinct ones (see
tests/index/conftest.py's `test_labels` fixture) so test writes land on
different labels entirely and can never touch real data. Labels/relationship
types cannot be parameterized in Cypher (`$param` binds values, not schema
names), so they are interpolated directly; `_validate_label` restricts them
to a safe identifier pattern since they are still going into a query string.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from braid.extract.models import Triple

BATCH_SIZE = 500
DEFAULT_URI = "neo4j://localhost:7687"
DEFAULT_AUTH = ("neo4j", "braid-local-only")
DEFAULT_ENTITY_LABEL = "Entity"
DEFAULT_RELATION_TYPE = "RELATION"

_LABEL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _validate_label(label: str) -> str:
    if not _LABEL_PATTERN.match(label):
        raise ValueError(f"{label!r} is not a safe Cypher label/relationship-type identifier")
    return label


@dataclass(frozen=True)
class BuildReport:
    nodes: int
    edges: int


_driver_cache: dict[str, object] = {}


def _driver(uri: str = DEFAULT_URI, auth: tuple[str, str] = DEFAULT_AUTH):
    # Cached at module level, same reasoning as dense.py's model cache: every
    # function below calls this when no driver is passed in, and an earlier
    # version created a fresh, never-closed driver on every single call --
    # caught via the same deprecation warning found in health.py's Neo4j
    # path, here multiplied across every test in the suite.
    key = f"{uri}:{auth[0]}"
    if key not in _driver_cache:
        from neo4j import GraphDatabase

        _driver_cache[key] = GraphDatabase.driver(uri, auth=auth)
    return _driver_cache[key]


def close_all() -> None:
    """Close every cached driver. Call at process/test-session teardown."""
    for driver in _driver_cache.values():
        driver.close()
    _driver_cache.clear()


def _batches(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _triple_row(t: Triple) -> dict:
    return {
        "subject": t.subject,
        "object": t.object,
        "relation": t.relation,
        "passage_id": t.passage_id,
        "sentence_index": t.sentence_index,
    }


def ensure_constraint(
    driver=None, entity_label: str = DEFAULT_ENTITY_LABEL
) -> None:
    entity_label = _validate_label(entity_label)
    driver = driver or _driver()
    constraint_name = f"{entity_label.lower()}_name_unique"
    cypher = (
        f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
        f"FOR (e:{entity_label}) REQUIRE e.name IS UNIQUE"
    )
    driver.execute_query(cypher, database_="neo4j")


def load_triples(
    triples: list[Triple],
    driver=None,
    entity_label: str = DEFAULT_ENTITY_LABEL,
    relation_type: str = DEFAULT_RELATION_TYPE,
) -> BuildReport:
    """Batched UNWIND + MERGE load. Safe to call repeatedly (MERGE upserts
    nodes; edges MERGE on their full property set, so identical triples don't
    duplicate but a new relation between the same pair of entities does).
    """
    entity_label = _validate_label(entity_label)
    relation_type = _validate_label(relation_type)
    driver = driver or _driver()
    ensure_constraint(driver, entity_label)

    merge_cypher = f"""
    UNWIND $rows AS row
    MERGE (s:{entity_label} {{name: row.subject}})
    MERGE (o:{entity_label} {{name: row.object}})
    MERGE (s)-[r:{relation_type} {{
        relation: row.relation, passage_id: row.passage_id, sentence_index: row.sentence_index
    }}]->(o)
    """
    type_cypher = f"""
    UNWIND $rows AS row
    MATCH (e:{entity_label} {{name: row.name}})
    SET e.type = row.type
    """

    for batch in _batches(triples, BATCH_SIZE):
        rows = [_triple_row(t) for t in batch]
        driver.execute_query(merge_cypher, rows=rows, database_="neo4j")

        type_rows = [
            {"name": t.subject, "type": t.subject_type} for t in batch if t.subject_type
        ] + [{"name": t.object, "type": t.object_type} for t in batch if t.object_type]
        if type_rows:
            driver.execute_query(type_cypher, rows=type_rows, database_="neo4j")

    return counts(driver, entity_label, relation_type)


def counts(
    driver=None,
    entity_label: str = DEFAULT_ENTITY_LABEL,
    relation_type: str = DEFAULT_RELATION_TYPE,
) -> BuildReport:
    entity_label = _validate_label(entity_label)
    relation_type = _validate_label(relation_type)
    driver = driver or _driver()
    node_records, _, _ = driver.execute_query(
        f"MATCH (e:{entity_label}) RETURN count(e) AS c", database_="neo4j"
    )
    edge_records, _, _ = driver.execute_query(
        f"MATCH ()-[r:{relation_type}]->() RETURN count(r) AS c", database_="neo4j"
    )
    return BuildReport(nodes=node_records[0]["c"], edges=edge_records[0]["c"])


def clear(
    driver=None,
    entity_label: str = DEFAULT_ENTITY_LABEL,
) -> None:
    """Delete every node carrying `entity_label` (and its relationships).
    Scoped to the label, not the whole graph, so clearing test data can never
    touch the real deliverable's `:Entity` nodes when a different test label
    is used. Used to make a test/build run idempotent from empty, not called
    as part of normal incremental add.
    """
    entity_label = _validate_label(entity_label)
    driver = driver or _driver()
    driver.execute_query(f"MATCH (n:{entity_label}) DETACH DELETE n", database_="neo4j")
