"""
Identity graph construction and clustering.

Takes match results (edges) and records (nodes) and builds a graph
where connected components represent resolved identities. Uses
NetworkX for graph operations.

The identity graph is the core data structure in production identity
resolution systems — LiveRamp, Experian, and Walmart all use
graph-based approaches to connect records across data sources.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

import networkx as nx

from identity_resolver.models import IdentityCluster, MatchResult, Record

logger = logging.getLogger(__name__)


class IdentityGraph:
    """Graph-based identity clustering.

    Nodes = records, edges = match results.
    Connected components = identity clusters.
    """

    def __init__(self):
        self.graph = nx.Graph()
        self._records: dict[str, Record] = {}

    @property
    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.graph.number_of_edges()

    @property
    def cluster_count(self) -> int:
        return nx.number_connected_components(self.graph)

    def add_records(self, records: list[Record]) -> None:
        """Add records as nodes in the graph."""
        for r in records:
            self._records[r.record_id] = r
            self.graph.add_node(r.record_id, source=r.source)

    def add_matches(
        self,
        matches: list[MatchResult],
        min_score: float = 0.5,
    ) -> int:
        """Add match results as edges. Returns count of edges added."""
        added = 0
        for m in matches:
            if m.score < min_score:
                continue

            # Only add edge if both nodes exist
            if m.record_a_id in self._records and m.record_b_id in self._records:
                self.graph.add_edge(
                    m.record_a_id,
                    m.record_b_id,
                    score=m.score,
                    match_type=m.match_type.value,
                    matched_fields=m.matched_fields,
                )
                added += 1

        logger.info(f"Added {added} edges to identity graph (min_score={min_score})")
        return added

    def cluster(self) -> list[IdentityCluster]:
        """Extract identity clusters from connected components.

        Each connected component becomes one IdentityCluster.
        Isolated nodes (no matches) become single-record clusters.
        """
        clusters = []

        for component in nx.connected_components(self.graph):
            cluster_id = str(uuid.uuid4())[:8]
            records = [self._records[rid] for rid in component if rid in self._records]

            # Collect edges within this component
            subgraph = self.graph.subgraph(component)
            match_edges = []
            for u, v, data in subgraph.edges(data=True):
                match_edges.append(
                    MatchResult(
                        record_a_id=u,
                        record_b_id=v,
                        match_type=data.get("match_type", "unknown"),
                        score=data.get("score", 0.0),
                        matched_fields=data.get("matched_fields", []),
                    )
                )

            clusters.append(
                IdentityCluster(
                    cluster_id=cluster_id,
                    records=records,
                    match_edges=match_edges,
                )
            )

        # Sort by cluster size (largest first)
        clusters.sort(key=lambda c: c.record_count, reverse=True)

        multi = sum(1 for c in clusters if c.record_count > 1)
        logger.info(
            f"Clustered {self.node_count} records into {len(clusters)} identities "
            f"({multi} multi-record, {len(clusters) - multi} singletons)"
        )
        return clusters

    def stats(self) -> dict:
        """Return graph statistics for monitoring and debugging."""
        components = list(nx.connected_components(self.graph))
        sizes = [len(c) for c in components]

        return {
            "total_nodes": self.node_count,
            "total_edges": self.edge_count,
            "total_clusters": len(components),
            "multi_record_clusters": sum(1 for s in sizes if s > 1),
            "singletons": sum(1 for s in sizes if s == 1),
            "largest_cluster": max(sizes) if sizes else 0,
            "avg_cluster_size": round(sum(sizes) / len(sizes), 2) if sizes else 0,
            "sources": list({
                data.get("source", "unknown")
                for _, data in self.graph.nodes(data=True)
            }),
        }

    def find_cluster(self, record_id: str) -> Optional[set[str]]:
        """Find all records in the same cluster as the given record."""
        if record_id not in self.graph:
            return None
        return nx.node_connected_component(self.graph, record_id)
