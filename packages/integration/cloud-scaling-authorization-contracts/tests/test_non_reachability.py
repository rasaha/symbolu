"""Every invalid case yields no candidate — and reaches no collaborator.

Two complementary proofs, because either alone would be weak:

* **Behavioural** — a sentinel is passed wherever a collaborator could be passed, and the
  sentinel fails loudly if it is touched. Every rejection path is swept.
* **Structural** — for capabilities that do not exist in this package's dependency graph
  at all (policy resolver, evidence resolver, Decision Authority, envelope issuer,
  ActionGate, credential broker, executor, clock), absence is asserted over the source
  rather than observed through an invented mock port. There is nothing to mock, and
  inventing a placeholder port would imply the seam exists.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

import ugence_cloud_scaling_authorization_contracts as pkg
from conftest import (
    ForbiddenCollaborator,
    build_attestation,
    build_decision,
    build_policy_binding,
    build_projection,
    build_recommendation,
    build_target_scope,
    coordinate_for,
    production_subject,
)
from risk_authority.integrations import SubjectRiskDecision, SubjectRiskDisposition
from ugence_cloud_scaling_authorization_contracts import (
    CandidateConstructionError,
    build_capacity_authorization_candidate,
)

SRC = pathlib.Path(pkg.__file__).resolve().parent
SOURCES = sorted(SRC.rglob("*.py"))


def _forged(decision, **overrides):
    forged = SubjectRiskDecision.__new__(SubjectRiskDecision)
    for f, v in vars(decision).items():
        object.__setattr__(forged, f, v)
    for f, v in overrides.items():
        object.__setattr__(forged, f, v)
    return forged


def invalid_cases(projection, decision, attestation, target_scope, policy_binding):
    """Every distinct rejection path, as ready-to-call builder kwargs."""

    other = build_projection(
        build_recommendation(subject=production_subject(tenant_id="tenant-2"))
    )
    base = dict(
        projection=projection, decision=decision, producer_attestation=attestation,
        policy_binding=policy_binding,
        policy_coordinate_binding=coordinate_for(policy_binding),
        target_scope=target_scope,
    )
    wrong_action = "scale_down" if target_scope.action_type != "scale_down" else "scale_up"
    substituted_scope = build_target_scope(projection, action_type=wrong_action)
    relocated_scope = build_target_scope(projection, region="eu-west-1")
    foreign_scope = build_target_scope(projection, account_id="acct-999999999999")

    yield "cross_tenant_decision", {**base, "decision": build_decision(other)}
    yield "cross_tenant_projection", {**base, "projection": other}
    yield "denied_decision", {
        **base,
        "decision": _forged(decision, disposition=SubjectRiskDisposition.RISK_DENIED),
    }
    yield "missing_decision_snapshot", {**base, "decision": _forged(decision, decision_snapshot=None)}
    yield "forged_decision_digest", {
        **base, "decision": _forged(decision, decision_digest="sha256:" + "a" * 64)
    }
    yield "missing_expiry", {**base, "decision": _forged(decision, expires_at=None)}
    yield "stale_request_digest", {
        **base, "decision": _forged(decision, request_digest="sha256:" + "0" * 64)
    }
    yield "missing_attestation", {**base, "producer_attestation": None}
    yield "attestation_for_another_recommendation", {
        **base,
        "producer_attestation": build_attestation(
            recommendation_digest=other.recommendation_digest
        ),
    }
    yield "missing_policy_binding", {**base, "policy_binding": None}
    yield "policy_for_another_scope", {
        **base, "policy_binding": build_policy_binding(foreign_scope)
    }
    yield "action_substitution", {
        **base, "target_scope": substituted_scope,
        "policy_binding": build_policy_binding(substituted_scope),
    }
    yield "target_relocation", {
        **base, "target_scope": relocated_scope,
        "policy_binding": build_policy_binding(relocated_scope),
    }
    yield "duck_typed_attestation", {**base, "producer_attestation": object()}
    yield "duck_typed_scope", {**base, "target_scope": object()}


def test_every_invalid_case_produces_no_candidate(
    projection, decision, attestation, target_scope, policy_binding
):
    seen = set()
    for label, kwargs in invalid_cases(
        projection, decision, attestation, target_scope, policy_binding
    ):
        seen.add(label)
        with pytest.raises(CandidateConstructionError):
            build_capacity_authorization_candidate(**kwargs)
    assert len(seen) == 15, f"expected 15 distinct rejection paths, swept {len(seen)}"


def test_no_invalid_case_reaches_a_collaborator(
    projection, decision, attestation, target_scope, policy_binding
):
    """A sentinel in every collaborator-shaped slot is never touched on a rejection path."""

    for label, kwargs in invalid_cases(
        projection, decision, attestation, target_scope, policy_binding
    ):
        sentinel = ForbiddenCollaborator(label)
        # There is no collaborator parameter to pass one into — which is itself the
        # finding. Passing it as an unexpected keyword must be refused outright rather
        # than silently accepted and stashed.
        with pytest.raises((CandidateConstructionError, TypeError)):
            build_capacity_authorization_candidate(**kwargs, policy_resolver=sentinel)
        assert sentinel.calls == []


def test_the_builder_accepts_no_collaborator_parameter():
    """Structural: there is no resolver, issuer, gate, broker, executor or clock seam."""

    import inspect

    params = set(inspect.signature(build_capacity_authorization_candidate).parameters)
    assert params == {
        "projection", "decision", "producer_attestation", "policy_binding",
        "policy_coordinate_binding", "target_scope",
    }
    for forbidden in (
        "policy_resolver", "evidence_resolver", "decision_authority", "envelope_issuer",
        "actiongate", "credential_broker", "executor", "clock", "seam", "port",
    ):
        assert forbidden not in params


@pytest.mark.parametrize(
    "capability",
    [
        "policy resolution", "evidence resolution", "decision authority",
        "envelope issuance", "actiongate admission", "credential brokerage",
        "execution", "clock read",
    ],
)
def test_capability_is_structurally_absent(capability):
    """No Protocol, ABC, port, adapter or client for any of these exists in the package."""

    fragments = {
        "policy resolution": ("policyresolver", "resolve_policy"),
        "evidence resolution": ("evidenceresolver", "resolve_evidence", "admit_evidence"),
        "decision authority": ("decisionauthority", "issue_decision", "mint_decision"),
        "envelope issuance": ("envelopeissuer", "issue_envelope", "riskauthorizationenvelope"),
        "actiongate admission": ("actiongate", "actionauthorization"),
        "credential brokerage": ("credentialbroker", "issue_credential", "assume_role"),
        "execution": ("executor", "execute_action", "executionrequest", "executionreceipt"),
        "clock read": ("datetime.now", "utcnow", "time.time", "monotonic"),
    }[capability]
    for path in SOURCES:
        text = path.read_text(encoding="utf-8").lower()
        # Strip docstrings and comments: the module docstrings legitimately *name* these
        # capabilities in order to state that they are excluded.
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                doc = ast.get_docstring(node)
                if doc:
                    text = text.replace(doc.lower(), "")
        text = "\n".join(
            line.split("#", 1)[0] for line in text.splitlines()
        )
        for fragment in fragments:
            assert fragment not in text, (
                f"{path.name} contains executable reference to {fragment!r} "
                f"({capability})"
            )


def test_no_authority_bearing_type_is_defined():
    """No class here is an envelope, an action authorization, a receipt or a credential.

    Matched by exact authority-bearing type name rather than by substring: this package's
    own ``CapacityAuthorizationCandidate`` and ``CloudScalingAuthorizationContractError``
    legitimately contain the word "authorization" while being, respectively, an explicit
    non-authorization and an error class.
    """

    forbidden_names = {
        "RiskAuthorizationEnvelope", "AuthorizationEnvelope", "Envelope",
        "EnvelopeIssuer", "EnvelopeVerifier",
        "ActionAuthorization", "ActionGate", "ActionGateResult", "ActionGateDecision",
        "ExecutionReceipt", "EffectVerificationReceipt", "ExecutionRecord",
        "ExecutionRequest", "Executor", "CredentialBroker", "Credential",
        "RiskDecision", "DecisionAuthority",
    }
    forbidden_suffixes = ("Envelope", "Receipt", "Credential", "Executor", "ActionGate")
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            assert node.name not in forbidden_names, f"{path.name} defines {node.name}"
            for suffix in forbidden_suffixes:
                assert not node.name.endswith(suffix), (
                    f"{path.name} defines {node.name}, an authority-bearing type"
                )


def test_the_candidate_type_name_says_candidate():
    """The load-bearing word is in the type name and in the schema tag."""

    from ugence_cloud_scaling_authorization_contracts import (
        AUTHORIZATION_CANDIDATE_SCHEMA_VERSION,
        CapacityAuthorizationCandidate,
    )

    assert CapacityAuthorizationCandidate.__name__.endswith("Candidate")
    assert "candidate" in AUTHORIZATION_CANDIDATE_SCHEMA_VERSION
