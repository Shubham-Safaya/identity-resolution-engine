"""Tests for identity graph construction and clustering."""

from identity_resolver.graph import IdentityGraph
from identity_resolver.models import MatchResult, MatchType, Record


def _make_record(rid, source="test", **kwargs):
    return Record(record_id=rid, source=source, **kwargs)


def _make_match(a_id, b_id, score=0.9, match_type=MatchType.DETERMINISTIC, fields=None):
    return MatchResult(
        record_a_id=a_id,
        record_b_id=b_id,
        match_type=match_type,
        score=score,
        matched_fields=fields or ["email"],
    )


class TestIdentityGraphEmpty:
    def test_empty_graph_properties(self):
        g = IdentityGraph()
        assert g.node_count == 0
        assert g.edge_count == 0
        assert g.cluster_count == 0

    def test_empty_graph_clusters(self):
        g = IdentityGraph()
        clusters = g.cluster()
        assert clusters == []

    def test_empty_graph_stats(self):
        g = IdentityGraph()
        stats = g.stats()
        assert stats["total_nodes"] == 0
        assert stats["largest_cluster"] == 0


class TestAddRecords:
    def test_add_records_as_nodes(self):
        g = IdentityGraph()
        records = [_make_record("r1"), _make_record("r2"), _make_record("r3")]
        g.add_records(records)
        assert g.node_count == 3
        assert g.edge_count == 0

    def test_single_record_clusters(self):
        """Records with no matches become singleton clusters."""
        g = IdentityGraph()
        g.add_records([_make_record("r1"), _make_record("r2")])
        clusters = g.cluster()
        assert len(clusters) == 2
        assert all(c.record_count == 1 for c in clusters)


class TestAddMatches:
    def test_add_match_edge(self):
        g = IdentityGraph()
        g.add_records([_make_record("r1"), _make_record("r2")])
        added = g.add_matches([_make_match("r1", "r2")])
        assert added == 1
        assert g.edge_count == 1

    def test_min_score_filtering(self):
        g = IdentityGraph()
        g.add_records([_make_record("r1"), _make_record("r2")])
        added = g.add_matches([_make_match("r1", "r2", score=0.4)], min_score=0.5)
        assert added == 0
        assert g.edge_count == 0

    def test_match_requires_existing_nodes(self):
        """Edges for unknown record IDs are silently skipped."""
        g = IdentityGraph()
        g.add_records([_make_record("r1")])
        added = g.add_matches([_make_match("r1", "r_unknown")])
        assert added == 0


class TestClustering:
    def test_connected_components_clustering(self):
        g = IdentityGraph()
        g.add_records([_make_record("r1"), _make_record("r2"), _make_record("r3")])
        g.add_matches([_make_match("r1", "r2")])
        clusters = g.cluster()
        # r1-r2 in one cluster, r3 alone
        assert len(clusters) == 2
        sizes = sorted([c.record_count for c in clusters], reverse=True)
        assert sizes == [2, 1]

    def test_merge_clusters_with_bridge(self):
        """Adding a bridging match merges two separate clusters."""
        g = IdentityGraph()
        g.add_records([
            _make_record("r1"), _make_record("r2"),
            _make_record("r3"), _make_record("r4"),
        ])
        g.add_matches([_make_match("r1", "r2"), _make_match("r3", "r4")])
        assert g.cluster_count == 2

        # Bridge the two clusters
        g.add_matches([_make_match("r2", "r3")])
        assert g.cluster_count == 1
        clusters = g.cluster()
        assert clusters[0].record_count == 4

    def test_clusters_sorted_largest_first(self):
        g = IdentityGraph()
        g.add_records([_make_record(f"r{i}") for i in range(5)])
        # Cluster of 3: r0-r1-r2, cluster of 2: r3-r4
        g.add_matches([
            _make_match("r0", "r1"),
            _make_match("r1", "r2"),
            _make_match("r3", "r4"),
        ])
        clusters = g.cluster()
        assert clusters[0].record_count == 3
        assert clusters[1].record_count == 2


class TestFindCluster:
    def test_find_existing_record(self):
        g = IdentityGraph()
        g.add_records([_make_record("r1"), _make_record("r2")])
        g.add_matches([_make_match("r1", "r2")])
        cluster = g.find_cluster("r1")
        assert cluster == {"r1", "r2"}

    def test_find_nonexistent_record(self):
        g = IdentityGraph()
        assert g.find_cluster("nope") is None
