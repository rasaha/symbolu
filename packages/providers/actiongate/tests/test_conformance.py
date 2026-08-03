"""Shared framework conformance + ActionGate-specific conformance (canonical)."""
from __future__ import annotations

from ugence_governance_provider_framework.conformance import run_action_provider_conformance
from ugence_governance_provider_framework.api import ActionGovernanceProvider

from ugence_actiongate_provider.configuration import build_actiongate_provider
from ugence_actiongate_provider.conformance import run_actiongate_conformance


def test_actiongate_passes_shared_action_conformance():
    rep = run_action_provider_conformance(lambda: build_actiongate_provider())
    assert rep.passed, rep.failures


def test_actiongate_specific_conformance():
    rep = run_actiongate_conformance()
    assert rep.passed, rep.failures
    names = {r.name for r in rep.results}
    for required in ("request_mapping", "result_allow", "result_denied",
                     "result_unknown_indeterminate", "constraints_preserved",
                     "obligations_preserved", "expiry_preserved",
                     "authority_basis_preserved", "timeout_translation",
                     "unavailable_translation", "malformed_translation",
                     "deterministic_fingerprint", "repeated_request_idempotency"):
        assert required in names


def test_actiongate_is_action_governance_provider():
    assert isinstance(build_actiongate_provider(), ActionGovernanceProvider)
