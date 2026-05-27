"""
Top-level identity resolver — orchestrates the full pipeline.

normalize -> deterministic match -> probabilistic match -> graph cluster -> privacy filter
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from identity_resolver.deterministic import DeterministicMatcher
from identity_resolver.graph import IdentityGraph
from identity_resolver.models import IdentityCluster, MatchResult, Record
from identity_resolver.normalizer import normalize_record
from identity_resolver.privacy import PrivacyConfig, PrivacyEngine, PrivacyMode
from identity_resolver.probabilistic import ProbabilisticMatcher

logger = logging.getLogger(__name__)


@dataclass
class ResolverConfig:
    """Configuration for the identity resolution pipeline."""

    # Deterministic matching
    match_on_email: bool = True
    match_on_phone: bool = True
    match_on_name_zip: bool = True

    # Probabilistic matching
    probabilistic_threshold: float = 0.65
    probabilistic_weights: dict[str, float] | None = None
    blocking_fields: list[str] = field(default_factory=lambda: ["zip_code"])

    # Graph
    min_edge_score: float = 0.5

    # Privacy
    privacy_mode: PrivacyMode = PrivacyMode.CCPA
    hash_salt: str = ""
    k_anonymity_threshold: int = 5
    dp_epsilon: float = 1.0


@dataclass
class ResolutionResult:
    """Full output of the resolution pipeline."""

    clusters: list[IdentityCluster]
    deterministic_matches: list[MatchResult]
    probabilistic_matches: list[MatchResult]
    graph_stats: dict
    privacy_stats: dict | None = None

    @property
    def total_records(self) -> int:
        return sum(c.record_count for c in self.clusters)

    @property
    def total_clusters(self) -> int:
        return len(self.clusters)

    @property
    def multi_record_clusters(self) -> int:
        return sum(1 for c in self.clusters if c.record_count > 1)

    @property
    def resolution_rate(self) -> float:
        """Fraction of records that matched to at least one other record."""
        matched = sum(c.record_count for c in self.clusters if c.record_count > 1)
        return matched / self.total_records if self.total_records else 0.0

    def summary(self) -> dict:
        return {
            "total_records": self.total_records,
            "total_clusters": self.total_clusters,
            "multi_record_clusters": self.multi_record_clusters,
            "singletons": self.total_clusters - self.multi_record_clusters,
            "resolution_rate": round(self.resolution_rate, 3),
            "deterministic_matches": len(self.deterministic_matches),
            "probabilistic_matches": len(self.probabilistic_matches),
            "graph_stats": self.graph_stats,
        }


class IdentityResolver:
    """End-to-end identity resolution pipeline.

    Usage:
        resolver = IdentityResolver()
        result = resolver.resolve(records)
        for cluster in result.clusters:
            print(cluster.golden_record())
    """

    def __init__(self, config: ResolverConfig | None = None):
        self.config = config or ResolverConfig()

        self.deterministic = DeterministicMatcher(
            match_on_email=self.config.match_on_email,
            match_on_phone=self.config.match_on_phone,
            match_on_name_zip=self.config.match_on_name_zip,
        )

        self.probabilistic = ProbabilisticMatcher(
            threshold=self.config.probabilistic_threshold,
            weights=self.config.probabilistic_weights,
            blocking_fields=self.config.blocking_fields,
        )

        self.privacy = PrivacyEngine(
            PrivacyConfig(
                mode=self.config.privacy_mode,
                hash_salt=self.config.hash_salt,
                k_anonymity_threshold=self.config.k_anonymity_threshold,
                dp_epsilon=self.config.dp_epsilon,
            )
        )

    def resolve(self, records: list[Record]) -> ResolutionResult:
        """Run the full identity resolution pipeline.

        Steps:
        1. Filter opted-out records (privacy)
        2. Normalize all PII fields
        3. Deterministic matching (exact keys)
        4. Probabilistic matching (fuzzy, on unmatched pairs)
        5. Build identity graph
        6. Extract clusters
        """
        logger.info(f"Starting identity resolution: {len(records)} input records")

        # Step 1: Privacy filter
        records = self.privacy.filter_opted_out(records)
        logger.info(f"After privacy filter: {len(records)} records")

        # Step 2: Normalize
        for r in records:
            normalize_record(r)

        # Step 3: Deterministic matching
        det_matches = self.deterministic.match(records)

        # Step 4: Probabilistic matching (exclude already-matched pairs)
        matched_pairs = {
            tuple(sorted([m.record_a_id, m.record_b_id])) for m in det_matches
        }
        prob_matches = self.probabilistic.match(
            records, exclude_pairs=matched_pairs
        )

        # Step 5: Build graph
        graph = IdentityGraph()
        graph.add_records(records)
        graph.add_matches(det_matches, min_score=0.0)  # All deterministic pass
        graph.add_matches(prob_matches, min_score=self.config.min_edge_score)

        # Step 6: Cluster
        clusters = graph.cluster()

        result = ResolutionResult(
            clusters=clusters,
            deterministic_matches=det_matches,
            probabilistic_matches=prob_matches,
            graph_stats=graph.stats(),
        )

        logger.info(
            f"Resolution complete: {result.total_clusters} identities, "
            f"{result.resolution_rate:.1%} resolution rate"
        )

        return result
