"""Tests for PII normalization."""

from identity_resolver.models import Record
from identity_resolver.normalizer import (
    normalize_address,
    normalize_email,
    normalize_name,
    normalize_phone,
    normalize_record,
    normalize_state,
    normalize_zip,
)


class TestEmailNormalization:
    def test_basic_lowercase(self):
        assert normalize_email("John.Doe@Gmail.COM") == "johndoe@gmail.com"

    def test_gmail_dots_stripped(self):
        assert normalize_email("j.o.h.n@gmail.com") == "john@gmail.com"

    def test_gmail_plus_addressing(self):
        assert normalize_email("john+shopping@gmail.com") == "john@gmail.com"

    def test_non_gmail_keeps_dots(self):
        assert normalize_email("john.doe@company.com") == "john.doe@company.com"

    def test_none_returns_none(self):
        assert normalize_email(None) is None

    def test_invalid_no_at(self):
        assert normalize_email("not-an-email") is None

    def test_whitespace_stripped(self):
        assert normalize_email("  alice@example.com  ") == "alice@example.com"


class TestPhoneNormalization:
    def test_strips_formatting(self):
        assert normalize_phone("(555) 123-4567") == "5551234567"

    def test_strips_country_code(self):
        assert normalize_phone("+1-555-123-4567") == "5551234567"

    def test_already_clean(self):
        assert normalize_phone("5551234567") == "5551234567"

    def test_too_short(self):
        assert normalize_phone("555123") is None

    def test_none_returns_none(self):
        assert normalize_phone(None) is None


class TestNameNormalization:
    def test_lowercase(self):
        assert normalize_name("John") == "john"

    def test_strips_prefix(self):
        assert normalize_name("Dr. John Smith") == "john smith"

    def test_strips_suffix(self):
        assert normalize_name("John Smith Jr.") == "john smith"

    def test_strips_both(self):
        assert normalize_name("Mr. John Smith III") == "john smith"

    def test_preserves_hyphen(self):
        assert normalize_name("Mary-Jane Watson") == "mary-jane watson"

    def test_none_returns_none(self):
        assert normalize_name(None) is None


class TestAddressNormalization:
    def test_abbreviates_street(self):
        assert normalize_address("123 Main Street") == "123 main st"

    def test_abbreviates_avenue(self):
        assert normalize_address("456 Park Avenue") == "456 park ave"

    def test_abbreviates_apartment(self):
        assert normalize_address("789 Oak Blvd Apartment 4") == "789 oak blvd apt 4"

    def test_strips_punctuation(self):
        assert normalize_address("123 Main St., #5") == "123 main st 5"

    def test_directions(self):
        assert normalize_address("100 North Main Street") == "100 n main st"


class TestStateNormalization:
    def test_full_name(self):
        assert normalize_state("California") == "CA"

    def test_already_abbreviated(self):
        assert normalize_state("TX") == "TX"

    def test_lowercase(self):
        assert normalize_state("new york") == "NY"


class TestZipNormalization:
    def test_five_digit(self):
        assert normalize_zip("90210") == "90210"

    def test_strips_plus_four(self):
        assert normalize_zip("90210-1234") == "90210"

    def test_too_short(self):
        assert normalize_zip("902") is None


class TestNormalizeRecord:
    def test_normalizes_all_fields(self):
        record = Record(
            record_id="r1",
            source="crm",
            email="John.Doe+spam@Gmail.COM",
            phone="(555) 123-4567",
            first_name="Mr. John",
            last_name="Doe Jr.",
            address_line1="123 Main Street",
            city="Los Angeles",
            state="California",
            zip_code="90210-1234",
        )

        result = normalize_record(record)

        assert result.email == "johndoe@gmail.com"
        assert result.phone == "5551234567"
        assert result.first_name == "john"
        assert result.last_name == "doe"
        assert result.address_line1 == "123 main st"
        assert result.city == "los angeles"
        assert result.state == "CA"
        assert result.zip_code == "90210"
        assert result._normalized is True
