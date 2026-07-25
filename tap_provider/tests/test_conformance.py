"""Shared framework conformance + TAP-specific conformance."""
from __future__ import annotations

from governance_providers.conformance import run_assertion_provider_conformance
from governance_providers.api import AssertionGovernanceProvider
from tap_provider.configuration import build_tap_provider
from tap_provider.conformance import run_tap_conformance


def test_tap_passes_shared_assertion_conformance():
    rep = run_assertion_provider_conformance(lambda: build_tap_provider())
    assert rep.passed, rep.failures


def test_tap_specific_conformance():
    rep = run_tap_conformance()
    assert rep.passed, rep.failures
    names = {r.name for r in rep.results}
    for required in (
            "native_request_mapping", "evidence_provenance", "supported_mapping",
            "unsupported_mapping", "constrained_mapping", "indeterminate_mapping",
            "partial_support", "unsupported_components", "omitted_qualifiers",
            "evidence_coverage", "constraints_preserved", "obligations_preserved",
            "explanation_refs", "malformed_translation", "unknown_result_indeterminate",
            "timeout_translation", "unavailable_translation", "deterministic_fingerprint",
            "input_immutability", "repeated_request_idempotency"):
        assert required in names, required


def test_tap_is_assertion_governance_provider():
    assert isinstance(build_tap_provider(), AssertionGovernanceProvider)
