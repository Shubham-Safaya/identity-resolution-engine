"""
Deterministic matching for identity resolution.

Exact-match on normalized keys: email, phone, or composite keys
(first_name + last_name + zip). Deterministic matches are high-confidence
(score=1.0) and form the backbone of the identity graph.
"""

from __future__ import annotations

import logging
from itertools import combinations

from identity_resolver.models import MatchResult, MatchType, Record
from identity_resolver.normalizer import normalize_record

logger = logging.getLogger(__name__)


class DeterministicMatcher:
    """Finds exact matches across a set of records using normalized keys.

    Match keys (in priority order):
    1. Email — strongest signal, globally unique
    2. Phone — strong signal, can be recycled but rare in short windows
    3. Name + ZIP — composite key, high precision when both match
    """

    def __init__(
        self,
        match_on_email: bool = True,
        match_on_phone: bool = True,
        match_on_name_zip: bool = True,
    ):
        self.match_on_email = match_on_email
        self.match_on_phone = match_on_phone
        self.match_on_name_zip = match_on_name_zip

    def match(self, records: list[Record]) -> list[MatchResult]:
        """Find all deterministic matches across the record set.

        Uses index-based matching (O(n) per key) rather than
        pairwise comparison (O(n^2)).
        """
        # Normalize all records first
        for r in records:
            if not r._normalized:
                normalize_record(r)

        results: list[MatchResult] = []
        seen_pairs: set[tuple[str, str]] = set()

        if self.match_on_email:
            results.extend(self._match_by_key(records, "email", seen_pairs))

        if self.match_on_phone:
            results.extend(self._match_by_key(records, "phone", seen_pairs))

        if self.match_on_name_zip:
            results.extend(self._match_by_composite(records, seen_pairs))

        logger.info(
            f"Deterministic matching: {len(records)} records -> {len(results)} matches"
        )
        return results

    def _match_by_key(
        self,
        records: list[Record],
        field: str,
        seen_pairs: set[tuple[str, str]],
    ) -> list[MatchResult]:
        """Index records by a single field and match on exact value."""
        index: dict[str, list[Record]] = {}

        for r in records:
            value = getattr(r, field)
            if value:
                index.setdefault(value, []).append(r)

        matches = []
        for key_value, group in index.items():
            if len(group) < 2:
                continue

            for a, b in combinations(group, 2):
                pair = tuple(sorted([a.record_id, b.record_id]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                matches.append(
                    MatchResult(
                        record_a_id=a.record_id,
                        record_b_id=b.record_id,
                        match_type=MatchType.DETERMINISTIC,
                        score=1.0,
                        matched_fields=[field],
                        details={"key": field, "value": key_value},
                    )
                )

        return matches

    def _match_by_composite(
        self,
        records: list[Record],
        seen_pairs: set[tuple[str, str]],
    ) -> list[MatchResult]:
        """Match on first_name + last_name + zip_code composite key."""
        index: dict[str, list[Record]] = {}

        for r in records:
            if r.first_name and r.last_name and r.zip_code:
                key = f"{r.first_name}|{r.last_name}|{r.zip_code}"
                index.setdefault(key, []).append(r)

        matches = []
        for key_value, group in index.items():
            if len(group) < 2:
                continue

            for a, b in combinations(group, 2):
                pair = tuple(sorted([a.record_id, b.record_id]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                matches.append(
                    MatchResult(
                        record_a_id=a.record_id,
                        record_b_id=b.record_id,
                        match_type=MatchType.DETERMINISTIC,
                        score=0.9,  # Slightly lower than single-key email/phone
                        matched_fields=["first_name", "last_name", "zip_code"],
                        details={"key": "name_zip", "value": key_value},
                    )
                )

        return matches
