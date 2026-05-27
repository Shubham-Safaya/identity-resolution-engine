"""
Identity Resolution Engine

Open-source deterministic and probabilistic identity resolution library.
Resolves messy customer records into unified identity profiles using
configurable match rules, scoring thresholds, and graph-based clustering.
"""

__version__ = "0.1.0"

from identity_resolver.models import Record, MatchResult, IdentityCluster
from identity_resolver.normalizer import normalize_record
from identity_resolver.deterministic import DeterministicMatcher
from identity_resolver.probabilistic import ProbabilisticMatcher
from identity_resolver.graph import IdentityGraph
from identity_resolver.resolver import IdentityResolver

__all__ = [
    "Record",
    "MatchResult",
    "IdentityCluster",
    "normalize_record",
    "DeterministicMatcher",
    "ProbabilisticMatcher",
    "IdentityGraph",
    "IdentityResolver",
]
