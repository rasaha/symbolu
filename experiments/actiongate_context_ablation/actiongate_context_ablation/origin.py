"""Data-origin guard: synthetic/mock corpora may NOT emit a scientific verdict.

Mirrors the discipline of the behavioral-biometrics ``origin.guarded`` pattern:
a pipeline can be *path-verified* on synthetic data, but a product-grade verdict
(ABLATION_OPPORTUNITY_SUPPORTED, CONTEXT_INTRINSICALLY_DENSE, ...) requires real,
provenance-documented context. If any context in a run is synthetic/mock, the
whole run is locked to a no-scientific-verdict result.
"""

from __future__ import annotations

# Origin tiers, most-synthetic first.
MOCK = "MOCK_TEST_ONLY"
SYNTHETIC = "SYNTHETIC_AUTHORED"          # authored fixtures (synthetic Tiers 1 & 3)
# naturalistic partitions: realistic but NOT confidential customer data
PUBLIC_NATURALISTIC = "PUBLIC_NATURALISTIC_CORPUS"     # repository-derived, provenance-documented
AUTHORED_REALISTIC = "AUTHORED_REALISTIC_CORPUS"       # independently authored realistic
NATURALISTIC_REPO = "NATURALISTIC_REPO"   # real repo artifacts w/ documented provenance
FIELD_REAL = "FIELD_REAL"                 # real production customer context

_SYNTHETIC_ORIGINS = frozenset({MOCK, SYNTHETIC})
_NATURALISTIC_ORIGINS = frozenset({PUBLIC_NATURALISTIC, AUTHORED_REALISTIC})


def is_naturalistic(origin: str) -> bool:
    return origin in _NATURALISTIC_ORIGINS


def run_is_naturalistic(origins) -> bool:
    """A naturalistic run may emit a corpus-level opportunity verdict (never customer)."""
    origins = list(origins)
    return bool(origins) and all(o in _NATURALISTIC_ORIGINS for o in origins)

# Locked verdicts an all-synthetic / mock run may emit.
PIPELINE_PATH_VERIFIED = "PIPELINE_PATH_VERIFIED"
MOCK_NO_SCIENTIFIC_VERDICT = "MOCK_NO_SCIENTIFIC_VERDICT"
SYNTHETIC_NO_SCIENTIFIC_VERDICT = "SYNTHETIC_NO_SCIENTIFIC_VERDICT"


def is_synthetic(origin: str) -> bool:
    return origin in _SYNTHETIC_ORIGINS


def run_is_scientific(origins) -> bool:
    """A run yields a scientific verdict only if EVERY context is real provenance."""
    origins = list(origins)
    if not origins:
        return False
    return all(o in (NATURALISTIC_REPO, FIELD_REAL) for o in origins)


def locked_verdict(origins) -> str:
    """The no-scientific-verdict result appropriate to the run's origins."""
    origins = list(origins)
    if any(o == MOCK for o in origins):
        return MOCK_NO_SCIENTIFIC_VERDICT
    return SYNTHETIC_NO_SCIENTIFIC_VERDICT
