"""End-to-end tests for the identity resolver pipeline."""

from identity_resolver.models import ConsentStatus, Record
from identity_resolver.privacy import PrivacyMode
from identity_resolver.resolver import IdentityResolver, ResolverConfig


def _make_record(rid, source="crm", **kwargs):
    return Record(record_id=rid, source=source, **kwargs)


class TestIdentityResolver:
    def test_basic_resolution(self):
        """Same person, two data sources, different formatting."""
        records = [
            _make_record(
                "crm_1", source="crm",
                email="john.doe@gmail.com", phone="(555) 123-4567",
                first_name="John", last_name="Doe",
                zip_code="90210",
            ),
            _make_record(
                "web_1", source="website",
                email="JOHNDOE@GMAIL.COM",  # Gmail normalizes to same
                first_name="John", last_name="Doe",
                zip_code="90210-1234",
            ),
            _make_record(
                "pos_1", source="point_of_sale",
                phone="+1-555-123-4567",  # Same phone, different format
                first_name="J.", last_name="Doe",
                zip_code="90210",
            ),
        ]

        resolver = IdentityResolver()
        result = resolver.resolve(records)

        # All three should resolve to one identity
        assert result.total_clusters == 1
        assert result.total_records == 3
        assert result.resolution_rate == 1.0

        # Golden record should merge best data
        golden = result.clusters[0].golden_record()
        assert golden["record_count"] == 3
        assert set(golden["sources"]) == {"crm", "website", "point_of_sale"}

    def test_two_distinct_people(self):
        """Two different people should stay in separate clusters."""
        records = [
            _make_record("r1", email="alice@example.com", first_name="Alice", last_name="Smith"),
            _make_record("r2", email="alice@example.com", first_name="Alice", last_name="Smith"),
            _make_record("r3", email="bob@example.com", first_name="Bob", last_name="Jones"),
        ]

        resolver = IdentityResolver()
        result = resolver.resolve(records)

        assert result.total_clusters == 2
        sizes = sorted([c.record_count for c in result.clusters], reverse=True)
        assert sizes == [2, 1]

    def test_privacy_opt_out(self):
        """Opted-out records should be excluded."""
        records = [
            _make_record("r1", email="alice@example.com", consent=ConsentStatus.OPTED_IN),
            _make_record("r2", email="alice@example.com", consent=ConsentStatus.OPTED_OUT),
        ]

        config = ResolverConfig(privacy_mode=PrivacyMode.CCPA)
        resolver = IdentityResolver(config)
        result = resolver.resolve(records)

        assert result.total_records == 1  # r2 filtered out

    def test_gdpr_requires_consent(self):
        """GDPR mode: only opted-in records should be processed."""
        records = [
            _make_record("r1", email="a@example.com", consent=ConsentStatus.OPTED_IN),
            _make_record("r2", email="a@example.com", consent=ConsentStatus.UNKNOWN),
        ]

        config = ResolverConfig(privacy_mode=PrivacyMode.GDPR)
        resolver = IdentityResolver(config)
        result = resolver.resolve(records)

        assert result.total_records == 1

    def test_probabilistic_catches_typos(self):
        """Fuzzy matching should catch name typos within same ZIP."""
        records = [
            _make_record("r1", first_name="Shubham", last_name="Safaya",
                         zip_code="72712", email="shubham@example.com"),
            _make_record("r2", first_name="Shubam", last_name="Safaia",
                         zip_code="72712", email="different@example.com"),
        ]

        config = ResolverConfig(probabilistic_threshold=0.5)
        resolver = IdentityResolver(config)
        result = resolver.resolve(records)

        # Should match probabilistically despite different emails
        assert result.total_clusters == 1
        assert len(result.probabilistic_matches) >= 1

    def test_summary_output(self):
        """Summary should contain all expected fields."""
        records = [
            _make_record("r1", email="a@example.com"),
            _make_record("r2", email="a@example.com"),
            _make_record("r3", email="b@example.com"),
        ]

        resolver = IdentityResolver()
        result = resolver.resolve(records)
        summary = result.summary()

        assert "total_records" in summary
        assert "total_clusters" in summary
        assert "resolution_rate" in summary
        assert "deterministic_matches" in summary
        assert "probabilistic_matches" in summary
        assert summary["total_records"] == 3
        assert summary["total_clusters"] == 2
