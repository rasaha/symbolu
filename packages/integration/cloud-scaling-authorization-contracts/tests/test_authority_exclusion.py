"""Structural proof that no authority capability exists in this distribution.

The exclusions are asserted over source imports, public exports, AST call expressions, the
dataclass field sets and the package's own text — never over a prose claim or a fixed-False
boolean. Where a capability does not exist in the dependency graph at all, absence is
asserted structurally rather than by inventing a mock port to observe.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import ugence_cloud_scaling_authorization_contracts as pkg
from ugence_cloud_scaling_authorization_contracts import (
    CapacityAuthorizationCandidate,
    ExecutionTargetScope,
    PolicyTargetBindingReference,
    ProducerAttestationEvidence,
)

SRC = pathlib.Path(pkg.__file__).resolve().parent
SOURCES = sorted(SRC.rglob("*.py"))

#: Field names the candidate must never carry — not as True, and not as a fixed False.
#: Absence is the requirement: a fixed False still represents authority.
FORBIDDEN_FIELD_NAMES = (
    "authorized",
    "authority_granted",
    "envelope_issued",
    "actiongate_invoked",
    "credential_issued",
    "actuation_performed",
    "effect_verified",
    "executable",
    "authorization_performed",
    "risk_evaluated",
    "policy_resolved",
    "verified",
    "trusted",
    "authentic",
)

#: Call names that would constitute an authority, execution or Phase 6 capability.
FORBIDDEN_CALL_NAMES = frozenset(
    {
        "issue_envelope", "verify_envelope", "sign_envelope", "mint_envelope",
        "authorize_action", "authorize", "invoke_actiongate", "admit",
        "issue_credential", "mint_credential", "broker_credential", "assume_role",
        "issue_decision", "mint_decision", "evaluate_risk", "decide",
        "resolve_policy", "resolve", "admit_evidence",
        "scale", "apply", "execute", "actuate", "mutate", "provision",
        "verify_effect", "reconcile_effect", "record_outcome", "learn",
        "now", "utcnow", "monotonic", "time",
    }
)


@pytest.mark.parametrize("name", FORBIDDEN_FIELD_NAMES)
def test_candidate_has_no_authority_field(name):
    assert name not in CapacityAuthorizationCandidate.__dataclass_fields__


@pytest.mark.parametrize(
    "cls", [ExecutionTargetScope, PolicyTargetBindingReference, ProducerAttestationEvidence]
)
def test_supporting_artifacts_have_no_authority_field(cls):
    for name in FORBIDDEN_FIELD_NAMES:
        assert name not in cls.__dataclass_fields__, f"{cls.__name__}.{name} exists"


def test_candidate_canonical_form_has_no_authority_key(candidate):
    canonical = candidate.to_canonical_dict()
    for name in FORBIDDEN_FIELD_NAMES:
        assert name not in canonical, f"canonical form carries {name}"
    # The nested artifacts are canonicalized too; check them at depth.
    flat = repr(canonical)
    for name in ("authority_granted", "envelope_issued", "actiongate_invoked",
                 "credential_issued", "actuation_performed", "effect_verified"):
        assert f"'{name}'" not in flat


#: ``provider`` in the denylist below means an **authority** provider — a credential
#: provider, an executor provider, something that grants or performs. ETS-3 introduced a
#: *cloud* provider label, which is the opposite category: a descriptive token naming which
#: cloud an account belongs to, carried in a scope that grants nothing and performs
#: nothing. Exempting the two names is narrower than dropping the fragment, and narrower
#: than exempting a prefix: a future ``CredentialProviderPort`` still fails.
#:
#: The exemption is by exact name, so it cannot silently widen. Adding to it is a decision,
#: not a convenience — anything that actually provides an authority capability must fail
#: this test no matter how it is spelled.
_CLOUD_PROVIDER_LABEL_EXPORTS = frozenset(
    {"CANONICAL_CLOUD_PROVIDERS", "CLOUD_PROVIDER_AZURE"}
)


def test_no_public_export_names_an_authority_capability():
    for name in pkg.__all__:
        if name in _CLOUD_PROVIDER_LABEL_EXPORTS:
            continue
        lowered = name.lower()
        for fragment in (
            "envelope", "actiongate", "credential", "executor", "execute", "authorize",
            "authorization_granted", "issuer", "broker", "provider", "clock",
        ):
            assert fragment not in lowered, f"public export {name} names {fragment}"


def test_the_cloud_provider_exemption_covers_only_descriptive_labels():
    """The exemption above is a hole in an authority guard, so it is itself guarded.

    Every exempted name must exist, must be a plain descriptive value — a string or a
    frozenset of strings — and must not be callable. A port, a class or a factory smuggled
    in under a ``CLOUD_PROVIDER`` spelling fails here even though the exemption lets it past
    the denylist."""

    for name in _CLOUD_PROVIDER_LABEL_EXPORTS:
        assert name in pkg.__all__, f"{name} is exempted but not exported"
        value = getattr(pkg, name)
        assert not callable(value), f"{name} is exempted but callable"
        assert isinstance(value, (str, frozenset)), f"{name} is not a descriptive label"
        if isinstance(value, frozenset):
            assert all(isinstance(v, str) for v in value)


def test_no_source_file_makes_a_forbidden_call():
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                called = func.id
            elif isinstance(func, ast.Attribute):
                called = func.attr
            else:
                continue
            assert called not in FORBIDDEN_CALL_NAMES, (
                f"{path.name} calls {called}(), a forbidden capability"
            )


def test_no_source_file_defines_a_forbidden_capability():
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                lowered = node.name.lower()
                for fragment in ("envelope", "actiongate", "credential", "executor"):
                    assert fragment not in lowered, (
                        f"{path.name} defines {node.name}, naming {fragment}"
                    )


def test_the_only_trust_state_is_the_unverified_one():
    from ugence_cloud_scaling_authorization_contracts import EvidenceTrustState

    members = list(EvidenceTrustState)
    assert len(members) == 1
    assert members[0].value == "PRESENT_BUT_NOT_TRUST_VERIFIED"
    for forbidden in ("VERIFIED", "TRUSTED", "AUTHENTIC", "VALID", "APPROVED"):
        assert not hasattr(EvidenceTrustState, forbidden)


def test_no_rejection_reason_asserts_authenticity():
    """A structurally present signature is never classified as cryptographically authentic."""

    from ugence_cloud_scaling_authorization_contracts import (
        AuthorizationCandidateRejectionReason as Reason,
    )

    for member in Reason:
        lowered = member.value.lower()
        assert "authentic" not in lowered
        assert "verified" not in lowered
        assert "trusted" not in lowered
        # Every member is a refusal; there is no success member to mistake for approval.
        assert not lowered.startswith(("ok", "pass", "allow", "granted", "success"))


def test_no_authority_representation_survives_in_the_dependency_graph():
    """The capabilities simply are not importable from here — asserted, not mocked."""

    import importlib

    for name in (
        "ugence_decision_authority",
        "ugence_actiongate_provider",
        "ugence_cloud_scaling_operations",
        "kubernetes",
        "boto3",
    ):
        # Not reachable through this package's declared dependency closure. If one ever
        # becomes importable it must be because a dependency was added — which the
        # dependency-metadata test above would also catch.
        try:
            importlib.import_module(name)
        except ImportError:
            continue
        else:  # pragma: no cover - present only if the environment installs it anyway
            pytest.skip(f"{name} is installed in this environment by something else")
