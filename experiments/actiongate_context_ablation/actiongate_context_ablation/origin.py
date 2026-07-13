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
SYNTHETIC = "SYNTHETIC_AUTHORED"          # authored fixtures (Tiers 1 & 3 here)
NATURALISTIC_REPO = "NATURALISTIC_REPO"   # real repo artifacts w/ documented provenance
FIELD_REAL = "FIELD_REAL"                 # real production context

_SYNTHETIC_ORIGINS = frozenset({MOCK, SYNTHETIC})

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
