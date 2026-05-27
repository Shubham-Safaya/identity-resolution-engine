"""
Core data models for identity resolution.

Record: A single customer/user record from any data source.
MatchResult: The outcome of comparing two records.
IdentityCluster: A group of records resolved to the same real-world person.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MatchType(Enum):
    DETERMINISTIC = "deterministic"
    PROBABILISTIC = "probabilistic"


class ConsentStatus(Enum):
    OPTED_IN = "opted_in"
    OPTED_OUT = "opted_out"
    UNKNOWN = "unknown"


@dataclass
class Record:
    """A single identity record from any data source.

    Each record represents one row from a CRM, transaction log,
    ad exposure file, or any other customer data source.
    """

    record_id: str
    source: str  # e.g., "crm", "website", "point_of_sale"

    # PII fields — all optional since sources vary
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None

    # Metadata
    consent: ConsentStatus = ConsentStatus.UNKNOWN
    timestamp: Optional[str] = None  # ISO format

    # Internal — populated after normalization
    _normalized: bool = False

    def pii_hash(self, salt: str = "") -> str:
        """Generate a SHA-256 hash of all PII fields for privacy-safe storage."""
        raw = "|".join(
            str(v or "")
            for v in [
                self.email,
                self.phone,
                self.first_name,
                self.last_name,
                self.address_line1,
                self.city,
                self.state,
                self.zip_code,
            ]
        )
        return hashlib.sha256((salt + raw).encode()).hexdigest()


@dataclass
class MatchResult:
    """The outcome of comparing two records."""

    record_a_id: str
    record_b_id: str
    match_type: MatchType
    score: float  # 0.0 to 1.0
    matched_fields: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    @property
    def is_match(self) -> bool:
        return self.score >= 0.5

    @property
    def is_strong_match(self) -> bool:
        return self.score >= 0.85


@dataclass
class IdentityCluster:
    """A group of records resolved to the same real-world person.

    After matching and graph clustering, each cluster represents
    one unified identity with a golden record synthesized from
    the best-available data across all constituent records.
    """

    cluster_id: str
    records: list[Record] = field(default_factory=list)
    match_edges: list[MatchResult] = field(default_factory=list)

    @property
    def sources(self) -> set[str]:
        return {r.source for r in self.records}

    @property
    def record_count(self) -> int:
        return len(self.records)

    def golden_record(self) -> dict:
        """Synthesize a golden record from the best-available data.

        Priority: most recent non-null value for each field.
        For deterministic fields (email, phone), prefer the most
        common value across records.
        """
        fields = [
            "email", "phone", "first_name", "last_name",
            "address_line1", "city", "state", "zip_code",
        ]
        golden = {"cluster_id": self.cluster_id, "record_count": self.record_count}

        for f in fields:
            values = [getattr(r, f) for r in self.records if getattr(r, f)]
            if values:
                # Use most common non-null value
                golden[f] = max(set(values), key=values.count)
            else:
                golden[f] = None

        golden["sources"] = list(self.sources)
        return golden
