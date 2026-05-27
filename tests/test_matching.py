"""Tests for deterministic and probabilistic matching."""

from identity_resolver.deterministic import DeterministicMatcher
from identity_resolver.models import Record
from identity_resolver.probabilistic import (
    ProbabilisticMatcher,
    jaro_winkler,
    soundex,
)


def _make_record(rid, **kwargs):
    return Record(record_id=rid, source="test", **kwargs)


class TestDeterministicMatcher:
    def test_email_match(self):
        records = [
            _make_record("r1", email="alice@example.com"),
            _make_record("r2", email="ALICE@EXAMPLE.COM"),
        ]
        matcher = DeterministicMatcher()
        matches = matcher.match(records)
        assert len(matches) == 1
        assert matches[0].score == 1.0
        assert "email" in matches[0].matched_fields

    def test_phone_match(self):
        records = [
            _make_record("r1", phone="(555) 123-4567"),
            _make_record("r2", phone="+1-555-123-4567"),
        ]
        matcher = DeterministicMatcher()
        matches = matcher.match(records)
        assert len(matches) == 1
        assert "phone" in matches[0].matched_fields

    def test_name_zip_match(self):
        records = [
            _make_record("r1", first_name="John", last_name="Doe", zip_code="90210"),
            _make_record("r2", first_name="JOHN", last_name="DOE", zip_code="90210-1234"),
        ]
        matcher = DeterministicMatcher()
        matches = matcher.match(records)
        assert len(matches) == 1
        assert matches[0].score == 0.9

    def test_no_match(self):
        records = [
            _make_record("r1", email="alice@example.com"),
            _make_record("r2", email="bob@example.com"),
        ]
        matcher = DeterministicMatcher()
        matches = matcher.match(records)
        assert len(matches) == 0

    def test_no_duplicate_pairs(self):
        records = [
            _make_record("r1", email="same@example.com", phone="5551234567"),
            _make_record("r2", email="same@example.com", phone="5551234567"),
        ]
        matcher = DeterministicMatcher()
        matches = matcher.match(records)
        # Email matches first, phone skips because pair already seen
        assert len(matches) == 1
        assert matches[0].matched_fields == ["email"]

    def test_disabled_match_types(self):
        records = [
            _make_record("r1", email="same@example.com"),
            _make_record("r2", email="same@example.com"),
        ]
        matcher = DeterministicMatcher(match_on_email=False)
        matches = matcher.match(records)
        assert len(matches) == 0


class TestJaroWinkler:
    def test_identical(self):
        assert jaro_winkler("shubham", "shubham") == 1.0

    def test_similar(self):
        score = jaro_winkler("shubham", "shubam")
        assert score > 0.9

    def test_different(self):
        score = jaro_winkler("alice", "bob")
        assert score < 0.5

    def test_empty_string(self):
        assert jaro_winkler("", "test") == 0.0

    def test_prefix_boost(self):
        # Jaro-Winkler should score higher than Jaro for matching prefixes
        score_jw = jaro_winkler("martha", "marhta")
        assert score_jw > 0.9


class TestSoundex:
    def test_robert_rupert(self):
        assert soundex("Robert") == soundex("Rupert")

    def test_ashcraft_ashcroft(self):
        assert soundex("Ashcraft") == soundex("Ashcroft")

    def test_different_names(self):
        assert soundex("John") != soundex("Mary")


class TestProbabilisticMatcher:
    def test_fuzzy_name_match(self):
        records = [
            _make_record("r1", first_name="Shubham", last_name="Safaya", zip_code="72712"),
            _make_record("r2", first_name="Shubam", last_name="Safaia", zip_code="72712"),
        ]
        matcher = ProbabilisticMatcher(threshold=0.5)
        matches = matcher.match(records)
        assert len(matches) == 1
        assert matches[0].score > 0.5

    def test_below_threshold(self):
        records = [
            _make_record("r1", first_name="Alice", last_name="Smith", zip_code="10001"),
            _make_record("r2", first_name="Bob", last_name="Jones", zip_code="10001"),
        ]
        matcher = ProbabilisticMatcher(threshold=0.8)
        matches = matcher.match(records)
        assert len(matches) == 0

    def test_excludes_existing_pairs(self):
        records = [
            _make_record("r1", first_name="John", last_name="Doe", zip_code="90210"),
            _make_record("r2", first_name="Jon", last_name="Doe", zip_code="90210"),
        ]
        exclude = {("r1", "r2")}
        matcher = ProbabilisticMatcher(threshold=0.5)
        matches = matcher.match(records, exclude_pairs=exclude)
        assert len(matches) == 0
