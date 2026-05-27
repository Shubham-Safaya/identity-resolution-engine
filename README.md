# Identity Resolution Engine

Open-source Python library for deterministic and probabilistic identity resolution. Takes messy customer records from multiple data sources and resolves them into unified identity profiles.

[![CI](https://github.com/Shubham-Safaya/identity-resolution-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Shubham-Safaya/identity-resolution-engine/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Why This Exists

Companies like LiveRamp, Experian, and TransUnion charge millions for identity resolution. Meanwhile, every company with customer data across multiple systems (CRM, website, point-of-sale, advertising) faces the same fundamental problem: **the same person looks different in every database.**

This library provides the core building blocks:

- **Normalization** -- Standardize emails, phones, names, and addresses so trivial differences don't block matches
- **Deterministic matching** -- High-confidence exact matches on normalized keys (email, phone, name+ZIP)
- **Probabilistic matching** -- Fuzzy matching with Jaro-Winkler similarity, Soundex phonetic encoding, and configurable field weights
- **Graph-based clustering** -- Build an identity graph and extract connected components as resolved identities
- **Privacy layer** -- CCPA/GDPR consent enforcement, PII hashing, k-anonymity, and differential privacy for aggregate queries

## Quick Start

```bash
pip install -e .
```

```python
from identity_resolver import IdentityResolver, Record

records = [
    Record(record_id="crm_1", source="crm",
           email="john.doe@gmail.com", phone="(555) 123-4567",
           first_name="John", last_name="Doe", zip_code="90210"),

    Record(record_id="web_1", source="website",
           email="JOHNDOE@GMAIL.COM",  # Gmail normalizes dots
           first_name="John", last_name="Doe", zip_code="90210-1234"),

    Record(record_id="pos_1", source="point_of_sale",
           phone="+1-555-123-4567",  # Same phone, different format
           first_name="J.", last_name="Doe", zip_code="90210"),
]

resolver = IdentityResolver()
result = resolver.resolve(records)

print(f"Resolved {result.total_records} records into {result.total_clusters} identities")
print(f"Resolution rate: {result.resolution_rate:.0%}")

for cluster in result.clusters:
    golden = cluster.golden_record()
    print(f"\nIdentity {golden['cluster_id']}:")
    print(f"  Name: {golden['first_name']} {golden['last_name']}")
    print(f"  Sources: {golden['sources']}")
```

Output:
```
Resolved 3 records into 1 identities
Resolution rate: 100%

Identity a1b2c3d4:
  Name: john doe
  Sources: ['crm', 'website', 'point_of_sale']
```

## Architecture

```
Input Records
     |
     v
[Normalization] -- Email, phone, name, address standardization
     |
     v
[Deterministic Matching] -- Exact match on normalized keys (O(n) per key)
     |
     v
[Probabilistic Matching] -- Jaro-Winkler + Soundex on unmatched pairs
     |                       with ZIP-based blocking to reduce comparisons
     v
[Identity Graph] -- Records = nodes, matches = edges (NetworkX)
     |
     v
[Clustering] -- Connected components = resolved identities
     |
     v
[Privacy Layer] -- Consent filtering, k-anonymity, differential privacy
     |
     v
Golden Records + Aggregate Statistics
```

## Configuration

```python
from identity_resolver import IdentityResolver
from identity_resolver.resolver import ResolverConfig
from identity_resolver.privacy import PrivacyMode

config = ResolverConfig(
    # Deterministic matching controls
    match_on_email=True,
    match_on_phone=True,
    match_on_name_zip=True,

    # Probabilistic matching
    probabilistic_threshold=0.65,  # Minimum score to consider a match
    blocking_fields=["zip_code"],  # Reduce comparison space

    # Privacy
    privacy_mode=PrivacyMode.CCPA,
    k_anonymity_threshold=5,
    dp_epsilon=1.0,
)

resolver = IdentityResolver(config)
```

## Privacy Modes

| Mode | Behavior |
|------|----------|
| `NONE` | No restrictions. Internal analytics only. |
| `CCPA` | Honor opt-out signals. Default mode. |
| `GDPR` | Require explicit opt-in consent. |
| `CLEAN_ROOM` | Full privacy: PII hashing + k-anonymity + differential privacy noise. |

## Normalization Examples

| Input | Normalized | Rule |
|-------|-----------|------|
| `John.Doe+spam@Gmail.COM` | `johndoe@gmail.com` | Gmail: strip dots and plus-addressing |
| `(555) 123-4567` | `5551234567` | Strip formatting, validate 10-digit US |
| `Mr. John Smith III` | `john smith` | Remove prefixes/suffixes |
| `123 Main Street, Apt. 4` | `123 main st apt 4` | Abbreviate, strip punctuation |
| `California` | `CA` | Full state name to abbreviation |
| `90210-1234` | `90210` | Strip ZIP+4 extension |

## Testing

```bash
pip install -e ".[dev]"
pytest -v
```

## Roadmap

- [ ] BigQuery connector (read from / write to BQ tables)
- [ ] Benchmarking on synthetic data at scale (1M+ records)
- [ ] Household-level clustering (group by address)
- [ ] REST API wrapper (FastAPI)
- [ ] Jupyter notebook with visualization of match quality and identity graph

## License

MIT
