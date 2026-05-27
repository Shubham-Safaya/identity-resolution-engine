"""
PII normalization for identity resolution.

Standardizes emails, phone numbers, names, and addresses so that
trivially different representations of the same person match
deterministically. All normalization is locale-aware and idempotent.
"""

import re
from typing import Optional

from identity_resolver.models import Record


# ── Email Normalization ───────────────────────────────────────────────

# Gmail ignores dots and everything after +
_GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}


def normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None

    email = email.strip().lower()

    # Basic validation
    if "@" not in email:
        return None

    local, domain = email.rsplit("@", 1)

    # Gmail-specific: remove dots and plus-addressing
    if domain in _GMAIL_DOMAINS:
        local = local.split("+")[0]
        local = local.replace(".", "")

    return f"{local}@{domain}"


# ── Phone Normalization ───────────────────────────────────────────────

def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Normalize to E.164-ish format: digits only, 10 or 11 chars for US."""
    if not phone:
        return None

    digits = re.sub(r"\D", "", phone)

    # US numbers: strip leading 1 if 11 digits
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    # Must be exactly 10 digits for US
    if len(digits) != 10:
        return None

    return digits


# ── Name Normalization ────────────────────────────────────────────────

_NAME_PREFIXES = {"mr", "mrs", "ms", "dr", "prof", "sir"}
_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "esq", "phd", "md"}


def normalize_name(name: Optional[str]) -> Optional[str]:
    """Lowercase, strip prefixes/suffixes, collapse whitespace."""
    if not name:
        return None

    name = name.strip().lower()
    name = re.sub(r"[^\w\s\-']", "", name)  # Keep letters, spaces, hyphens, apostrophes

    parts = name.split()
    parts = [p for p in parts if p.rstrip(".") not in _NAME_PREFIXES | _NAME_SUFFIXES]

    result = " ".join(parts).strip()
    return result if result else None


# ── Address Normalization ─────────────────────────────────────────────

_ADDRESS_ABBREVIATIONS = {
    "street": "st",
    "avenue": "ave",
    "boulevard": "blvd",
    "drive": "dr",
    "lane": "ln",
    "road": "rd",
    "court": "ct",
    "place": "pl",
    "circle": "cir",
    "terrace": "ter",
    "highway": "hwy",
    "apartment": "apt",
    "suite": "ste",
    "building": "bldg",
    "floor": "fl",
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
    "northeast": "ne",
    "northwest": "nw",
    "southeast": "se",
    "southwest": "sw",
}


def normalize_address(address: Optional[str]) -> Optional[str]:
    """Standardize address: lowercase, abbreviate common words, strip punctuation."""
    if not address:
        return None

    address = address.strip().lower()
    address = re.sub(r"[.,#]", "", address)

    words = address.split()
    normalized_words = [_ADDRESS_ABBREVIATIONS.get(w, w) for w in words]

    result = " ".join(normalized_words).strip()
    return result if result else None


def normalize_zip(zip_code: Optional[str]) -> Optional[str]:
    """Normalize to 5-digit ZIP (strip ZIP+4 extension)."""
    if not zip_code:
        return None

    digits = re.sub(r"\D", "", zip_code)
    if len(digits) >= 5:
        return digits[:5]
    return None


def normalize_state(state: Optional[str]) -> Optional[str]:
    """Normalize state to uppercase 2-letter abbreviation."""
    if not state:
        return None

    state = state.strip().upper()

    STATE_MAP = {
        "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
        "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
        "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID",
        "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
        "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
        "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
        "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV",
        "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY",
        "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK",
        "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI",
        "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX",
        "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
        "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
        "DISTRICT OF COLUMBIA": "DC",
    }

    if len(state) == 2:
        return state
    return STATE_MAP.get(state, state[:2] if len(state) >= 2 else None)


# ── Top-Level Normalizer ─────────────────────────────────────────────

def normalize_record(record: Record) -> Record:
    """Normalize all PII fields on a record in-place and return it."""
    record.email = normalize_email(record.email)
    record.phone = normalize_phone(record.phone)
    record.first_name = normalize_name(record.first_name)
    record.last_name = normalize_name(record.last_name)
    record.address_line1 = normalize_address(record.address_line1)
    record.city = normalize_name(record.city)
    record.state = normalize_state(record.state)
    record.zip_code = normalize_zip(record.zip_code)
    record._normalized = True
    return record
