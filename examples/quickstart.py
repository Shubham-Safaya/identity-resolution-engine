"""
Quickstart: Identity Resolution in 30 seconds

This example shows how to resolve messy customer records into
unified identity profiles using deterministic matching,
probabilistic matching, and graph-based clustering.
"""

from identity_resolver import IdentityResolver, Record

# Three records that are the same person — but formatted differently
records = [
    Record(
        record_id="crm-001",
        source="crm",
        email="john.doe+work@gmail.com",
        phone="(555) 123-4567",
        first_name="Mr. John",
        last_name="Doe",
        address_line1="123 Main Street",
        city="Austin",
        state="Texas",
        zip_code="78701",
    ),
    Record(
        record_id="web-002",
        source="website",
        email="JOHNDOE@GMAIL.COM",
        first_name="John",
        last_name="Doe",
        city="Austin",
        state="TX",
        zip_code="78701",
    ),
    Record(
        record_id="pos-003",
        source="point_of_sale",
        phone="+1-555-123-4567",
        first_name="J.",
        last_name="Doe",
        address_line1="123 Main St",
        city="Austin",
        state="TX",
        zip_code="78701-1234",
    ),
    # A completely different person
    Record(
        record_id="crm-004",
        source="crm",
        email="jane.smith@outlook.com",
        phone="(555) 999-0000",
        first_name="Jane",
        last_name="Smith",
        city="Seattle",
        state="WA",
        zip_code="98101",
    ),
]

# Resolve identities
resolver = IdentityResolver()
result = resolver.resolve(records)

# Results
print(f"Input:    {len(records)} records")
print(f"Output:   {result.total_clusters} identity clusters")
print(f"Matches:  {len(result.deterministic_matches) + len(result.probabilistic_matches)} match pairs found")
print(f"Rate:     {result.resolution_rate:.0%} of records matched to another")
print()

for i, cluster in enumerate(result.clusters, 1):
    record_ids = [r.record_id for r in cluster.records]
    print(f"Cluster {i} ({cluster.record_count} records): {record_ids}")
    gr = cluster.golden_record()
    print(f"  Email: {gr.get('email', 'N/A')}")
    print(f"  Phone: {gr.get('phone', 'N/A')}")
    print(f"  Name:  {gr.get('first_name', '')} {gr.get('last_name', '')}")
    print()

print("Summary:", result.summary())

# Expected output:
# Cluster 1 (3 records): ['crm-001', 'web-002', 'pos-003'] — all John Doe
# Cluster 2 (1 records): ['crm-004'] — Jane Smith (separate person)
