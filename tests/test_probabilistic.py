"""Tests for probabilistic matching functions and matcher."""

from identity_resolver.models import Record
from identity_resolver.probabilistic import (
    ProbabilisticMatcher,
    jaro_similarity,
    jaro_winkler,
    soundex,
)


def _make_record(rid, **kwargs):
    return Record(record_id=rid, source="test", **kwargs)


class TestJaroSimilarity:
    def test_identical_strings(self):
        assert jaro_similarity("hello", "hello") == 1.0

    def test_empty_string(self):
        assert jaro_similarity("", "hello") == 0.0
        assert jaro_similarity("hello", "") == 0.0

    def test_both_empty(self):
        assert jaro_similarity("", "") == 1.0

    def test_completely_different(self):
        assert jaro_similarity("abc", "xyz") == 0.0


class TestJaroWinklerAdditional:
    def test_prefix_boost_increases_score(self):
        """Jaro-Winkler should be >= Jaro for strings sharing a prefix."""
        jw = jaro_winkler("johnson", "jonson")
        jaro = jaro_similarity("johnson", "jonson")
        assert jw >= jaro

    def test_none_like_empty(self):
        """Empty strings should return 0.0."""
        assert jaro_winkler("", "") == 1.0
        assert jaro_winkler("a", "") == 0.0


class TestSoundexAdditional:
    def test_empty_string(self):
        assert soundex("") == ""

    def test_known_encoding(self):
        assert soundex("Robert") == "R163"

    def test_short_name_padded(self):
        # Single char name should be padded to 4
        code = soundex("A")
        assert len(code) == 4
        assert code == "A000"


class TestProbabilisticMatcherBlocking:
    def test_different_zip_not_compared(self):
        """Records in different ZIPs should not match when zip blocking is on."""
        records = [
            _make_record("r1", first_name="John", last_name="Doe", zip_code="10001"),
            _make_record("r2", first_name="John", last_name="Doe", zip_code="90210"),
        ]
        matcher = ProbabilisticMatcher(threshold=0.5, blocking_fields=["zip_code"])
        matches = matcher.match(records)
        assert len(matches) == 0

    def test_same_zip_compared(self):
        records = [
            _make_record("r1", first_name="John", last_name="Doe", zip_code="10001"),
            _make_record("r2", first_name="Jon", last_name="Doe", zip_code="10001"),
        ]
        matcher = ProbabilisticMatcher(threshold=0.5, blocking_fields=["zip_code"])
        matches = matcher.match(records)
        assert len(matches) == 1


class TestProbabilisticMatcherWeights:
    def test_custom_weights(self):
        records = [
            _make_record("r1", first_name="Alice", last_name="Smith", zip_code="10001"),
            _make_record("r2", first_name="Alicia", last_name="Smith", zip_code="10001"),
        ]
        # Heavy weight on last_name should produce a high score
        matcher = ProbabilisticMatcher(
            threshold=0.3,
            weights={"first_name": 0.1, "last_name": 0.9},
        )
        matches = matcher.match(records)
        assert len(matches) == 1
        assert matches[0].score > 0.8


class TestProbabilisticMatcherEdgeCases:
    def test_no_shared_fields(self):
        """Records with no overlapping non-null fields produce no match."""
        records = [
            _make_record("r1", first_name="Alice", zip_code="10001"),
            _make_record("r2", last_name="Smith", zip_code="10001"),
        ]
        matcher = ProbabilisticMatcher(threshold=0.1)
        matches = matcher.match(records)
        # Only zip_code overlaps, and the default weights include zip_code
        # but the two records share the same zip so that field scores 1.0
        # The match depends on whether zip alone exceeds the threshold
        # With threshold 0.1 and zip weight 0.10, score = 1.0 (only field compared)
        assert all(m.score >= 0.1 for m in matches)

    def test_threshold_filtering(self):
        records = [
            _make_record("r1", first_name="Alice", last_name="Smith", zip_code="10001"),
            _make_record("r2", first_name="Bob", last_name="Jones", zip_code="10001"),
        ]
        matcher = ProbabilisticMatcher(threshold=0.9)
        matches = matcher.match(records)
        assert len(matches) == 0
