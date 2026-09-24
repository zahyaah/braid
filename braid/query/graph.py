"""Graph candidate retriever over Neo4j property graph (SPEC-query.md).

Implements candidate retrieval over the entity graph:
1. Entity linking: exact match on case-folded, normalized Entity.name (Decision D5).
2. Traversal: 2-hop expansion from linked entities.
3. Hub filtering: entities with degree > 200 skipped as hubs.
4. Fan-out cap: at most 50 edges per node at each hop.
5. Candidate K: 50 passages emitted as ranked third source (Decision D5).

Grounded in official Neo4j Cypher documentation:
https://neo4j.com/docs/cypher-manual/current/clauses/match/
"""

from __future__ import annotations

import re
from typing import Any

from braid.extract.entities import fold_case
from braid.index.graph import (
    DEFAULT_AUTH,
    DEFAULT_ENTITY_LABEL,
    DEFAULT_RELATION_TYPE,
    DEFAULT_URI,
    _driver,
    _validate_label,
)
from braid.query import params
from braid.query.base import Hit


class GraphRetriever:
    """Retriever implementation using 2-hop graph traversal in Neo4j."""

    name: str = "graph"

    def __init__(
        self,
        driver: Any = None,
        uri: str = DEFAULT_URI,
        auth: tuple[str, str] = DEFAULT_AUTH,
        entity_label: str = DEFAULT_ENTITY_LABEL,
        relation_type: str = DEFAULT_RELATION_TYPE,
        candidate_k: int = params.GRAPH_CANDIDATE_K,
        traversal_depth: int = params.GRAPH_TRAVERSAL_DEPTH,
        fan_out_cap: int = params.GRAPH_FAN_OUT_CAP,
        hub_cap: int = params.GRAPH_HUB_DEGREE_THRESHOLD,
        entity_names: dict[str, set[str]] | None = None,
    ) -> None:
        self.entity_label = _validate_label(entity_label)
        self.relation_type = _validate_label(relation_type)
        self.candidate_k = candidate_k
        self.traversal_depth = traversal_depth
        self.fan_out_cap = fan_out_cap
        self.hub_cap = hub_cap
        self._driver = driver
        self._uri = uri
        self._auth = auth
        self._entity_names_cache: dict[str, set[str]] | None = entity_names

    def _get_driver(self) -> Any:
        if self._driver is None:
            self._driver = _driver(self._uri, self._auth)
        return self._driver

    def _get_entity_names(self) -> dict[str, set[str]]:
        if self._entity_names_cache is None:
            driver = self._get_driver()
            cypher = f"MATCH (e:{self.entity_label}) RETURN e.name AS name"
            records, _, _ = driver.execute_query(cypher, database_="neo4j")
            mapping: dict[str, set[str]] = {}
            for r in records:
                name = r["name"]
                if name:
                    key = fold_case(name)
                    if key and len(key) >= 2:
                        mapping.setdefault(key, set()).add(name)
            self._entity_names_cache = mapping
        return self._entity_names_cache

    def link_entities(self, query: str) -> list[str]:
        """Link entities from query text using exact match on case-folded,
        normalized Entity.name (Decision D5).
        """
        if not query or not query.strip():
            return []

        q_norm = fold_case(query)
        entity_map = self._get_entity_names()

        matched: set[str] = set()
        for key, original_names in entity_map.items():
            pattern = r"\b" + re.escape(key) + r"\b"
            if re.search(pattern, q_norm):
                matched.update(original_names)

        return sorted(matched)

    def search(self, query: str, k: int | None = None) -> list[Hit]:
        """Traverse 2 hops from entities linked in query, returning candidate passages.

        Parameters
        ----------
        query : str
            Query text to search for.
        k : int, optional
            Number of top results to return. If None, defaults to candidate_k (50).

        Returns
        -------
        list[Hit]
            Ranked list of Hit objects with provenance={"graph": score}.
        """
        top_k = self.candidate_k if k is None else k
        if not query or not query.strip():
            return []

        linked_entities = self.link_entities(query)
        if not linked_entities:
            return []

        driver = self._get_driver()

        # Cypher traversal implementing 2-hop traversal with fan-out cap and hub filtering
        # Grounded in Neo4j 5.x Cypher pattern comprehension syntax.
        cypher = f"""
        UNWIND $start_names AS sname
        MATCH (s:{self.entity_label} {{name: sname}})
        WHERE size([(s)-[]-() | 1]) <= $hub_cap
        WITH s
        UNWIND [(s)-[r1:{self.relation_type}]-(n1:{self.entity_label})
                WHERE size([(n1)-[]-() | 1]) <= $hub_cap |
                {{edge: r1, target: n1}}][..$fan_out] AS hop1
        WITH s, hop1.edge AS r1, hop1.target AS n1
        OPTIONAL MATCH (n1)
        WITH s, r1, n1,
             [(n1)-[r2:{self.relation_type}]-(n2:{self.entity_label})
              WHERE n2 <> s AND size([(n2)-[]-() | 1]) <= $hub_cap |
              r2.passage_id][..$fan_out] AS hop2_pids
        UNWIND (CASE WHEN size(hop2_pids) > 0 THEN hop2_pids ELSE [null] END) AS pid2
        RETURN r1.passage_id AS pid1, pid2
        """

        records, _, _ = driver.execute_query(
            cypher,
            start_names=linked_entities,
            hub_cap=self.hub_cap,
            fan_out=self.fan_out_cap,
            database_="neo4j",
        )

        passage_scores: dict[str, float] = {}
        for r in records:
            p1 = r["pid1"]
            p2 = r["pid2"]
            if p1:
                passage_scores[p1] = passage_scores.get(p1, 0.0) + 1.0
            if p2:
                passage_scores[p2] = passage_scores.get(p2, 0.0) + 0.5

        if not passage_scores:
            return []

        # Sort descending by score, tie-break by passage_id asc
        ordered = sorted(passage_scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]

        return [
            Hit(
                passage_id=pid,
                score=score,
                rank=i + 1,
                provenance={"graph": score},
            )
            for i, (pid, score) in enumerate(ordered)
        ]


def compute_link_failure_rate(queries: list[Any], retriever: GraphRetriever) -> float:
    """Compute fraction of queries that link zero entities."""
    if not queries:
        return 0.0
    zero_count = sum(1 for q in queries if len(retriever.link_entities(q.text)) == 0)
    return zero_count / len(queries)
