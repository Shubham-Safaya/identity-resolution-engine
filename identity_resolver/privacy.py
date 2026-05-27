"""
Privacy layer for identity resolution.

Implements privacy-preserving operations required for CCPA, GDPR,
and clean room contexts:

- PII hashing (SHA-256 with configurable salt)
- Consent enforcement (opt-out filtering)
- k-anonymity checks (suppress clusters below threshold)
- Differential privacy noise injection for aggregate queries
"""

from __future__ import annotations

import hashlib
import logging
import math
import random
from dataclasses import dataclass
from enum import Enum

from identity_resolver.models import ConsentStatus, IdentityCluster, Record

logger = logging.getLogger(__name__)


class PrivacyMode(Enum):
    """Privacy compliance modes."""
    NONE = "none"            # No restrictions (internal analytics)
    CCPA = "ccpa"            # Honor opt-outs, provide deletion capability
    GDPR = "gdpr"            # Consent required, data minimization
    CLEAN_ROOM = "clean_room"  # Full privacy: hashing + k-anon + DP


@dataclass
class PrivacyConfig:
    mode: PrivacyMode = PrivacyMode.CCPA
    hash_salt: str = ""
    k_anonymity_threshold: int = 5
    dp_epsilon: float = 1.0  # Differential privacy budget


class PrivacyEngine:
    """Enforces privacy constraints on identity resolution outputs."""

    def __init__(self, config: PrivacyConfig | None = None):
        self.config = config or PrivacyConfig()

    def filter_opted_out(self, records: list[Record]) -> list[Record]:
        """Remove records where the user has opted out of data processing.

        CCPA: Must honor opt-out signals.
        GDPR: Must have explicit consent.
        """
        if self.config.mode == PrivacyMode.NONE:
            return records

        filtered = []
        removed = 0

        for r in records:
            if self.config.mode == PrivacyMode.GDPR:
                # GDPR requires explicit opt-in
                if r.consent != ConsentStatus.OPTED_IN:
                    removed += 1
                    continue
            else:
                # CCPA: only exclude explicit opt-outs
                if r.consent == ConsentStatus.OPTED_OUT:
                    removed += 1
                    continue
            filtered.append(r)

        if removed:
            logger.info(f"Privacy filter: removed {removed} records ({self.config.mode.value} mode)")

        return filtered

    def hash_pii(self, record: Record) -> dict:
        """Replace PII fields with salted SHA-256 hashes.

        Used when sharing identity data with external parties
        or storing in clean room environments.
        """
        salt = self.config.hash_salt

        def _hash(value: str | None) -> str | None:
            if not value:
                return None
            return hashlib.sha256((salt + value).encode()).hexdigest()

        return {
            "record_id": record.record_id,
            "source": record.source,
            "email_hash": _hash(record.email),
            "phone_hash": _hash(record.phone),
            "name_hash": _hash(
                f"{record.first_name or ''}|{record.last_name or ''}"
            ),
            "zip_code": record.zip_code,  # ZIP is generally not PII alone
            "consent": record.consent.value,
        }

    def enforce_k_anonymity(
        self, clusters: list[IdentityCluster]
    ) -> list[IdentityCluster]:
        """Suppress clusters with fewer records than k threshold.

        k-anonymity ensures that any individual in the output is
        indistinguishable from at least k-1 others. Clusters below
        the threshold are dropped from results.
        """
        if self.config.mode == PrivacyMode.NONE:
            return clusters

        k = self.config.k_anonymity_threshold
        passed = [c for c in clusters if c.record_count >= k]
        suppressed = len(clusters) - len(passed)

        if suppressed:
            logger.info(
                f"k-anonymity (k={k}): suppressed {suppressed} clusters, "
                f"{len(passed)} remain"
            )

        return passed

    def add_dp_noise(self, value: float, sensitivity: float = 1.0) -> float:
        """Add Laplace noise for differential privacy.

        Args:
            value: The true aggregate value.
            sensitivity: Maximum change in output from adding/removing one record.

        Uses the Laplace mechanism: noise ~ Laplace(0, sensitivity/epsilon).
        """
        if self.config.mode == PrivacyMode.NONE:
            return value

        epsilon = self.config.dp_epsilon
        scale = sensitivity / epsilon

        # Laplace noise via inverse CDF
        u = random.random() - 0.5
        noise = -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))

        noisy_value = value + noise
        return max(0, noisy_value)  # Ensure non-negative for counts

    def safe_aggregate(
        self, clusters: list[IdentityCluster]
    ) -> dict:
        """Generate privacy-safe aggregate statistics.

        Applies k-anonymity filtering and differential privacy noise
        to all aggregate metrics.
        """
        safe_clusters = self.enforce_k_anonymity(clusters)

        true_count = len(safe_clusters)
        true_records = sum(c.record_count for c in safe_clusters)
        sources = set()
        for c in safe_clusters:
            sources.update(c.sources)

        return {
            "cluster_count": round(self.add_dp_noise(true_count)),
            "total_records": round(self.add_dp_noise(true_records)),
            "avg_cluster_size": round(
                self.add_dp_noise(
                    true_records / true_count if true_count else 0,
                    sensitivity=1.0,
                ),
                1,
            ),
            "source_count": len(sources),
            "privacy_mode": self.config.mode.value,
            "k_anonymity_threshold": self.config.k_anonymity_threshold,
            "dp_epsilon": self.config.dp_epsilon,
        }
