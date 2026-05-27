"""
Probabilistic matching for identity resolution.

When records don't share exact keys, probabilistic matching uses
string similarity (Jaro-Winkler), phonetic encoding (Soundex),
and field-weighted scoring to estimate match probability.

This catches typos, maiden names, nicknames, and data entry errors
that deterministic matching misses.
"""

from __future__ import annotations

import logging
import math
from itertools import combinations

from identity_resolver.models import MatchResult, MatchType, Record
from identity_resolver.normalizer import normalize_record

logger = logging.getLogger(__name__)


# ── String Similarity Functions ───────────────────────────────────────

def jaro_similarity(s1: str, s2: str) -> float:
    """Jaro similarity between two strings. Returns 0.0 to 1.0."""
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)

        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    return (
        matches / len1 + matches / len2 + (matches - transpositions / 2) / matches
    ) / 3


def jaro_winkler(s1: str, s2: str, prefix_weight: float = 0.1) -> float:
    """Jaro-Winkler similarity — boosts score for matching prefixes.

    Particularly effective for names where first few characters
    are most discriminative (e.g., "Shubham" vs "Shubam").
    """
    jaro = jaro_similarity(s1, s2)

    # Count common prefix (up to 4 chars)
    prefix_len = 0
    for i in range(min(len(s1), len(s2), 4)):
        if s1[i] == s2[i]:
            prefix_len += 1
        else:
            break

    return jaro + prefix_len * prefix_weight * (1 - jaro)


def soundex(name: str) -> str:
    """American Soundex phonetic encoding.

    Maps names to a letter + 3 digits code so that
    similar-sounding names produce the same code.
    E.g., "Robert" and "Rupert" both encode to R163.
    """
    if not name:
        return ""

    name = name.upper()

    # Keep first letter
    code = name[0]
    mapping = {
        "B": "1", "F": "1", "P": "1", "V": "1",
        "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
        "D": "3", "T": "3",
        "L": "4",
        "M": "5", "N": "5",
        "R": "6",
    }

    prev = mapping.get(name[0], "0")
    for ch in name[1:]:
        digit = mapping.get(ch, "0")
        if digit != "0" and digit != prev:
            code += digit
        prev = digit if digit != "0" else prev

    # Pad or truncate to 4 characters
    code = (code + "000")[:4]
    return code


# ── Field Weights ─────────────────────────────────────────────────────

DEFAULT_WEIGHTS = {
    "email": 0.30,
    "phone": 0.25,
    "first_name": 0.10,
    "last_name": 0.15,
    "address_line1": 0.10,
    "zip_code": 0.10,
}


# ── Probabilistic Matcher ────────────────────────────────────────────

class ProbabilisticMatcher:
    """Fuzzy matching using Jaro-Winkler similarity and field weighting.

    For large record sets, use `blocking_fields` to reduce the
    comparison space. Blocking groups records by a shared attribute
    (e.g., zip_code) and only compares within each block.
    """

    def __init__(
        self,
        threshold: float = 0.65,
        weights: dict[str, float] | None = None,
        blocking_fields: list[str] | None = None,
    ):
        self.threshold = threshold
        self.weights = weights or DEFAULT_WEIGHTS
        self.blocking_fields = blocking_fields or ["zip_code"]

    def match(
        self,
        records: list[Record],
        exclude_pairs: set[tuple[str, str]] | None = None,
    ) -> list[MatchResult]:
        """Find probabilistic matches across the record set.

        Args:
            records: Records to compare (should be pre-normalized).
            exclude_pairs: Record ID pairs already matched deterministically.
        """
        for r in records:
            if not r._normalized:
                normalize_record(r)

        exclude = exclude_pairs or set()
        blocks = self._build_blocks(records)

        results = []
        comparisons = 0

        for block_key, block_records in blocks.items():
            if len(block_records) < 2:
                continue

            for a, b in combinations(block_records, 2):
                pair = tuple(sorted([a.record_id, b.record_id]))
                if pair in exclude:
                    continue

                comparisons += 1
                result = self._compare(a, b)
                if result and result.score >= self.threshold:
                    results.append(result)

        logger.info(
            f"Probabilistic matching: {comparisons} comparisons -> "
            f"{len(results)} matches (threshold={self.threshold})"
        )
        return results

    def _build_blocks(self, records: list[Record]) -> dict[str, list[Record]]:
        """Group records by blocking fields to reduce comparison space.

        Without blocking, N records require N*(N-1)/2 comparisons.
        With ZIP blocking, ~50-100 records per block is typical.
        """
        blocks: dict[str, list[Record]] = {"__all__": []}

        if not self.blocking_fields:
            blocks["__all__"] = records
            return blocks

        for r in records:
            block_key_parts = []
            for f in self.blocking_fields:
                val = getattr(r, f, None)
                block_key_parts.append(str(val or "__null__"))

            block_key = "|".join(block_key_parts)
            blocks.setdefault(block_key, []).append(r)

        # Also add a null block for records missing blocking fields
        return blocks

    def _compare(self, a: Record, b: Record) -> MatchResult | None:
        """Compare two records using weighted field similarity."""
        scores = {}
        matched_fields = []
        total_weight = 0.0
        weighted_score = 0.0

        for field_name, weight in self.weights.items():
            val_a = getattr(a, field_name, None)
            val_b = getattr(b, field_name, None)

            if not val_a or not val_b:
                continue

            total_weight += weight
            similarity = self._field_similarity(field_name, val_a, val_b)
            weighted_score += weight * similarity
            scores[field_name] = round(similarity, 3)

            if similarity >= 0.8:
                matched_fields.append(field_name)

        if total_weight == 0:
            return None

        # Normalize by total weight of compared fields
        final_score = weighted_score / total_weight

        return MatchResult(
            record_a_id=a.record_id,
            record_b_id=b.record_id,
            match_type=MatchType.PROBABILISTIC,
            score=round(final_score, 4),
            matched_fields=matched_fields,
            details={"field_scores": scores},
        )

    def _field_similarity(self, field: str, a: str, b: str) -> float:
        """Compute similarity for a specific field type."""
        if a == b:
            return 1.0

        if field in ("email", "phone", "zip_code"):
            # These are either exact or not — no fuzzy middle ground
            return 1.0 if a == b else 0.0

        if field in ("first_name", "last_name"):
            jw = jaro_winkler(a, b)
            # Boost if soundex matches (catches phonetic equivalents)
            if soundex(a) == soundex(b):
                jw = min(1.0, jw + 0.1)
            return jw

        if field == "address_line1":
            return jaro_winkler(a, b)

        return jaro_winkler(a, b)
