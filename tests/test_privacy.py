"""Tests for the privacy engine."""

import random

from identity_resolver.models import ConsentStatus, IdentityCluster, Record
from identity_resolver.privacy import PrivacyConfig, PrivacyEngine, PrivacyMode


def _make_record(rid, consent=ConsentStatus.UNKNOWN, **kwargs):
    return Record(record_id=rid, source="test", consent=consent, **kwargs)


def _make_cluster(cluster_id, n_records):
    records = [_make_record(f"{cluster_id}_r{i}") for i in range(n_records)]
    return IdentityCluster(cluster_id=cluster_id, records=records)


class TestPrivacyModes:
    def test_none_mode_passes_all(self):
        engine = PrivacyEngine(PrivacyConfig(mode=PrivacyMode.NONE))
        records = [
            _make_record("r1", consent=ConsentStatus.OPTED_OUT),
            _make_record("r2", consent=ConsentStatus.UNKNOWN),
        ]
        assert len(engine.filter_opted_out(records)) == 2

    def test_ccpa_removes_opted_out(self):
        engine = PrivacyEngine(PrivacyConfig(mode=PrivacyMode.CCPA))
        records = [
            _make_record("r1", consent=ConsentStatus.OPTED_IN),
            _make_record("r2", consent=ConsentStatus.OPTED_OUT),
            _make_record("r3", consent=ConsentStatus.UNKNOWN),
        ]
        result = engine.filter_opted_out(records)
        assert len(result) == 2
        ids = {r.record_id for r in result}
        assert "r2" not in ids

    def test_ccpa_keeps_unknown(self):
        engine = PrivacyEngine(PrivacyConfig(mode=PrivacyMode.CCPA))
        records = [_make_record("r1", consent=ConsentStatus.UNKNOWN)]
        assert len(engine.filter_opted_out(records)) == 1

    def test_gdpr_requires_opt_in(self):
        engine = PrivacyEngine(PrivacyConfig(mode=PrivacyMode.GDPR))
        records = [
            _make_record("r1", consent=ConsentStatus.OPTED_IN),
            _make_record("r2", consent=ConsentStatus.UNKNOWN),
            _make_record("r3", consent=ConsentStatus.OPTED_OUT),
        ]
        result = engine.filter_opted_out(records)
        assert len(result) == 1
        assert result[0].record_id == "r1"


class TestPIIHashing:
    def test_hash_produces_consistent_results(self):
        engine = PrivacyEngine(PrivacyConfig(hash_salt="test_salt"))
        record = _make_record("r1", email="alice@example.com", phone="5551234567")
        h1 = engine.hash_pii(record)
        h2 = engine.hash_pii(record)
        assert h1["email_hash"] == h2["email_hash"]
        assert h1["phone_hash"] == h2["phone_hash"]

    def test_hash_different_with_different_salt(self):
        r = _make_record("r1", email="alice@example.com")
        e1 = PrivacyEngine(PrivacyConfig(hash_salt="salt_a"))
        e2 = PrivacyEngine(PrivacyConfig(hash_salt="salt_b"))
        assert e1.hash_pii(r)["email_hash"] != e2.hash_pii(r)["email_hash"]

    def test_hash_none_field_returns_none(self):
        engine = PrivacyEngine(PrivacyConfig(hash_salt="s"))
        record = _make_record("r1")  # no email or phone
        hashed = engine.hash_pii(record)
        assert hashed["email_hash"] is None
        assert hashed["phone_hash"] is None

    def test_hash_preserves_zip(self):
        engine = PrivacyEngine()
        record = _make_record("r1", zip_code="90210")
        hashed = engine.hash_pii(record)
        assert hashed["zip_code"] == "90210"


class TestKAnonymity:
    def test_suppresses_small_clusters(self):
        engine = PrivacyEngine(PrivacyConfig(
            mode=PrivacyMode.CCPA, k_anonymity_threshold=3,
        ))
        clusters = [_make_cluster("big", 5), _make_cluster("small", 2)]
        result = engine.enforce_k_anonymity(clusters)
        assert len(result) == 1
        assert result[0].cluster_id == "big"

    def test_none_mode_skips_k_anonymity(self):
        engine = PrivacyEngine(PrivacyConfig(
            mode=PrivacyMode.NONE, k_anonymity_threshold=10,
        ))
        clusters = [_make_cluster("tiny", 1)]
        assert len(engine.enforce_k_anonymity(clusters)) == 1


class TestDifferentialPrivacy:
    def test_none_mode_returns_exact(self):
        engine = PrivacyEngine(PrivacyConfig(mode=PrivacyMode.NONE))
        assert engine.add_dp_noise(100.0) == 100.0

    def test_noise_is_added(self):
        """With a privacy mode active, noise should be added.
        Run multiple times to confirm it doesn't always return the exact value."""
        engine = PrivacyEngine(PrivacyConfig(mode=PrivacyMode.CCPA, dp_epsilon=0.1))
        random.seed(42)
        values = [engine.add_dp_noise(100.0) for _ in range(20)]
        # At least some values should differ from the true value
        assert any(v != 100.0 for v in values)

    def test_noisy_value_non_negative(self):
        engine = PrivacyEngine(PrivacyConfig(mode=PrivacyMode.CCPA, dp_epsilon=0.01))
        random.seed(0)
        for _ in range(50):
            assert engine.add_dp_noise(1.0) >= 0
