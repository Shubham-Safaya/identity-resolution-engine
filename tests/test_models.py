"""Tests for core data models."""

from identity_resolver.models import (
    ConsentStatus,
    IdentityCluster,
    MatchResult,
    MatchType,
    Record,
)


def _make_record(rid, source="test", **kwargs):
    return Record(record_id=rid, source=source, **kwargs)


class TestRecord:
    def test_default_consent_is_unknown(self):
        r = _make_record("r1")
        assert r.consent == ConsentStatus.UNKNOWN

    def test_not_normalized_by_default(self):
        r = _make_record("r1")
        assert r._normalized is False

    def test_pii_hash_deterministic(self):
        r = _make_record("r1", email="test@example.com", phone="5551234567")
        assert r.pii_hash() == r.pii_hash()

    def test_pii_hash_changes_with_salt(self):
        r = _make_record("r1", email="test@example.com")
        assert r.pii_hash("salt_a") != r.pii_hash("salt_b")

    def test_pii_hash_differs_for_different_records(self):
        r1 = _make_record("r1", email="alice@example.com")
        r2 = _make_record("r2", email="bob@example.com")
        assert r1.pii_hash() != r2.pii_hash()


class TestMatchResult:
    def test_is_match_above_threshold(self):
        m = MatchResult("r1", "r2", MatchType.DETERMINISTIC, score=0.7, matched_fields=["email"])
        assert m.is_match is True

    def test_is_match_below_threshold(self):
        m = MatchResult("r1", "r2", MatchType.PROBABILISTIC, score=0.3, matched_fields=[])
        assert m.is_match is False

    def test_is_strong_match(self):
        m = MatchResult("r1", "r2", MatchType.DETERMINISTIC, score=0.95, matched_fields=["email"])
        assert m.is_strong_match is True

    def test_is_not_strong_match(self):
        m = MatchResult("r1", "r2", MatchType.PROBABILISTIC, score=0.7, matched_fields=["first_name"])
        assert m.is_strong_match is False

    def test_boundary_match_score(self):
        m = MatchResult("r1", "r2", MatchType.DETERMINISTIC, score=0.5, matched_fields=[])
        assert m.is_match is True

    def test_boundary_strong_match_score(self):
        m = MatchResult("r1", "r2", MatchType.DETERMINISTIC, score=0.85, matched_fields=[])
        assert m.is_strong_match is True


class TestIdentityCluster:
    def test_sources_property(self):
        cluster = IdentityCluster(
            cluster_id="c1",
            records=[
                _make_record("r1", source="crm"),
                _make_record("r2", source="website"),
                _make_record("r3", source="crm"),
            ],
        )
        assert cluster.sources == {"crm", "website"}

    def test_record_count(self):
        cluster = IdentityCluster(
            cluster_id="c1",
            records=[_make_record("r1"), _make_record("r2")],
        )
        assert cluster.record_count == 2

    def test_golden_record_picks_most_common_value(self):
        cluster = IdentityCluster(
            cluster_id="c1",
            records=[
                _make_record("r1", email="common@example.com", first_name="Alice"),
                _make_record("r2", email="common@example.com", first_name="Alice"),
                _make_record("r3", email="rare@example.com", first_name="Alicia"),
            ],
        )
        golden = cluster.golden_record()
        assert golden["email"] == "common@example.com"
        assert golden["first_name"] == "Alice"

    def test_golden_record_null_field(self):
        cluster = IdentityCluster(
            cluster_id="c1",
            records=[_make_record("r1"), _make_record("r2")],
        )
        golden = cluster.golden_record()
        assert golden["email"] is None
        assert golden["phone"] is None
