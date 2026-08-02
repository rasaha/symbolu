"""Legacy-namespace compatibility: ``decision_governance`` re-exports the canonical
``ugence_decision_authority`` with object identity preserved (zero semantic change).

Consumers that still import from ``decision_governance`` must observe the SAME
classes, functions, enums, and versions as the canonical package — so serialization,
hashes, ``isinstance`` checks, and behavior are identical across the two names.
"""

from __future__ import annotations

import importlib

import pytest

# Deep import paths that consumers rely on (from the baseline import graph).
LEGACY_SUBMODULES = [
    "api", "api.services", "api.contracts", "api.ports", "api.audit", "api.identity",
    "api.policy", "api.errors", "api.repositories", "api.vocabulary", "api.common",
    "actions", "actions.cer", "actions.action_request", "actions.authorization",
    "actions.control_plane", "actions.lifecycle", "actions.status",
    "decisions", "decisions.decision", "decisions.authority", "decisions.override",
    "decisions.case", "decisions.lifecycle", "decisions.status",
    "identity", "audit", "audit.service", "audit.namespace",
    "execution", "execution.reconciliation", "execution.external_system",
    "policy", "policy.access", "ports", "ports.linked_record",
    "repositories", "repositories.decision_case_repository",
    "services", "services.case_decision_service", "conformance",
    "base", "common", "errors", "vocabulary", "version", "surface",
]


@pytest.mark.parametrize("sub", LEGACY_SUBMODULES)
def test_legacy_submodule_is_the_same_object_as_canonical(sub):
    legacy = importlib.import_module("decision_governance." + sub)
    canon = importlib.import_module("ugence_decision_authority." + sub)
    assert legacy is canon, sub


def test_top_level_public_symbols_are_identical_objects():
    import decision_governance as dg
    import ugence_decision_authority as uda
    assert dg.__version__ == uda.__version__ == "1.0.0"
    assert list(dg.__all__) == list(uda.__all__)
    for name in uda.__all__:
        if name == "__version__":
            continue
        assert getattr(dg, name) is getattr(uda, name), name


def test_canonical_hash_is_identical_across_namespaces():
    from decision_governance.common import canonical_hash as legacy_hash
    from ugence_decision_authority.common import canonical_hash as canon_hash
    assert legacy_hash is canon_hash


def test_records_are_isinstance_across_namespaces():
    """A record built via the canonical class is an instance of the legacy alias
    (same class object) — proving persisted/typed consumers keep working."""
    from ugence_decision_authority.vocabulary import ReasonCode as CanonReason
    from decision_governance.vocabulary import ReasonCode as LegacyReason
    assert CanonReason is LegacyReason
    assert list(CanonReason) == list(LegacyReason)
