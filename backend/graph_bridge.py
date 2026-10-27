"""Optional Neo4j persistence for the contradiction provenance graph."""

from __future__ import annotations

import os


def publish_graph(case_id: str, nodes: list[dict[str, str]], edges: list[dict[str, str]]) -> dict[str, str]:
    uri = os.getenv("REGULATRACE_NEO4J_URI", "").strip()
    if not uri:
        return {"backend": "in-memory", "detail": "Graph facts are shown in memory. Set REGULATRACE_NEO4J_URI to persist them in Neo4j."}
    try:
        from neo4j import GraphDatabase

        username = os.getenv("REGULATRACE_NEO4J_USER", "neo4j")
        password = os.getenv("REGULATRACE_NEO4J_PASSWORD", "")
        database = os.getenv("REGULATRACE_NEO4J_DATABASE", "neo4j")
        if not password:
            return {"backend": "in-memory", "detail": "Neo4j URI is set but no password is configured; graph remains in memory."}
        with GraphDatabase.driver(uri, auth=(username, password), connection_timeout=2) as driver:
            driver.verify_connectivity()
            driver.execute_query(
                "UNWIND $nodes AS item MERGE (n:RegulaTraceNode {caseId: $case_id, id: item.id}) "
                "SET n.label = item.label, n.type = item.type",
                nodes=nodes,
                case_id=case_id,
                database_=database,
            )
            driver.execute_query(
                "UNWIND $edges AS item "
                "MATCH (a:RegulaTraceNode {caseId: $case_id, id: item.source}) "
                "MATCH (b:RegulaTraceNode {caseId: $case_id, id: item.target}) "
                "MERGE (a)-[r:RELATES_TO {caseId: $case_id, label: item.label}]->(b)",
                edges=edges,
                case_id=case_id,
                database_=database,
            )
        return {"backend": "neo4j", "detail": f"{len(nodes)} nodes and {len(edges)} edges persisted to Neo4j case {case_id}."}
    except Exception as exc:
        return {"backend": "in-memory", "detail": f"Neo4j unavailable ({type(exc).__name__}); the graph is still visible in memory."}
