"""The genuine chain, held open: a Risk Authority application that still holds the decision.

Phase 5A's own fixtures produce a decision through the real ``RiskEvaluationSeam`` and then
let the application go. Issuance needs it back — the seam finds the decision by tenant and
id in the application that evaluated it (ADR D-5) — so this module rebuilds the same
reference seam over an observable clock and keeps the application. Everything downstream
of the decision is built by the neighbours' own fixture modules: the 5A candidate by Phase
5A's conftest, the bounds policy by 5B-0B's authority fixtures, the v2 attestation by
5B-0A's minting route.
"""

from __future__ import annotations

import importlib.util
import pathlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from risk_authority.api import RiskAuthorityApplication
from risk_authority.api.evaluation_seam import RiskEvaluationSeam
from risk_authority.crypto import SigningKey, SigningKeyRecord

from _policy_fixtures import T_CANDIDATE, issued_bounds
from _policy_fixtures import verifier_for as policy_verifier_for
from _producer_fixtures import (
    UNTRUSTED_PRODUCER_SEED,
    build_anchor,
    build_directory,
    build_verifier as producer_verifier_for,
)
from _producer_fixtures import build_attestation as mint_attestation

from ugence_cloud_scaling_envelope_issuance import (
    CloudScalingEnvelopeIssuance,
    CloudScalingEnvelopeIssuanceRequest,
)

__all__ = [
    "Clock",
    "World",
    "ISSUANCE_INSTANT",
    "EVALUATION_INSTANT",
    "KEY_RECORD",
    "P5A",
    "build_world",
    "issue_request",
    "mint_attestation",
    "producer_verifier_for",
    "policy_verifier_for",
    "build_anchor",
    "build_directory",
    "UNTRUSTED_PRODUCER_SEED",
]


def _load_phase5a():
    here = pathlib.Path(__file__).resolve()
    for candidate in here.parents:
        path = (candidate / "packages" / "integration" / "cloud-scaling-authorization-contracts"
                / "tests" / "conftest.py")
        if path.is_file():
            spec = importlib.util.spec_from_file_location("_phase5a_conftest_for_5b4", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise RuntimeError("the Phase 5A test tree is required to build the genuine chain")


P5A = _load_phase5a()

#: The decision is evaluated at Phase 5A's in-window instant (00:05:00 on 2026-01-01) and the
#: envelope is issued one minute later — inside the candidate's admissible window
#: [00:05:00, 00:08:10] that 5B-0B's gate 13 enforces, inside the bounds policy's effective
#: window and inside the producer anchor's window.
EVALUATION_INSTANT: datetime = P5A.INSIDE_WINDOW
ISSUANCE_INSTANT: datetime = T_CANDIDATE
assert ISSUANCE_INSTANT == EVALUATION_INSTANT + timedelta(minutes=1)

KEY_RECORD = SigningKeyRecord("cs-issuance-key", SigningKey.from_seed(bytes(range(32))))


class Clock:
    """An observable clock: every read is counted, and the instant can be moved."""

    def __init__(self, at: datetime = EVALUATION_INSTANT) -> None:
        self.at = at
        self.reads = 0

    def __call__(self) -> datetime:
        self.reads += 1
        return self.at


def held_reference_seam(clock: Clock) -> RiskEvaluationSeam:
    """Phase 5A's ``reference_seam``, verbatim in shape, over an observable clock."""

    from risk_authority.domain import (
        Predicate,
        PredicateOp,
        RuleEffect,
        WorkflowIR,
        WorkflowRule,
        WorkflowStatus,
    )
    from risk_authority.integrations import (
        InMemoryWorkflowIRSource,
        ReferenceSubjectAwarePolicyResolver,
    )
    from ugence_cloud_scaling_authorization_contracts import (
        DOMAIN_CLOUD_SCALING,
        PURPOSE_CAPACITY_ACTION,
    )

    workflow = WorkflowIR(
        workflow_ir_id="cloud-scaling-risk",
        version="1.0.0",
        status=WorkflowStatus.ACTIVE,
        rules=(
            WorkflowRule(
                rule_id="CS-1",
                conditions=(Predicate("domain", PredicateOp.EQ, DOMAIN_CLOUD_SCALING),),
                required_controls=(),
                effect=RuleEffect.ALLOW_IF_ALL,
            ),
        ),
        source_refs=("ADR-CLOUD-SCALING-P5",),
        effective_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    ).with_digest()
    source = InMemoryWorkflowIRSource()
    source.register(workflow)
    return RiskEvaluationSeam.reference(
        workflow_source=source,
        key_record=KEY_RECORD,
        clock=clock,
        policy_resolver=ReferenceSubjectAwarePolicyResolver(
            by_purpose_domain={(PURPOSE_CAPACITY_ACTION, DOMAIN_CLOUD_SCALING): workflow}
        ),
    )


@dataclass
class World:
    clock: Clock
    app: RiskAuthorityApplication
    decision: Any
    candidate: Any
    attestation: Any
    authority: Any
    record: Any
    producer_verifier: Any
    policy_verifier: Any

    def issuance(self, **overrides) -> CloudScalingEnvelopeIssuance:
        kwargs = dict(
            app=self.app, key_record=KEY_RECORD, producer_verifier=self.producer_verifier,
            policy_verifier=self.policy_verifier, clock=self.clock,
        )
        kwargs.update(overrides)
        return CloudScalingEnvelopeIssuance.reference(**kwargs)


def build_world(clock: Optional[Clock] = None, **policy_kwargs) -> World:
    """recommendation → projection → decision (held) → bounds policy → candidate → attestation."""

    clock = clock or Clock()
    seam = held_reference_seam(clock)
    app = seam._app
    projection = P5A.build_projection()
    decision = seam.evaluate(projection.request)
    authority, record = issued_bounds(**policy_kwargs)
    coordinate = record.coordinate
    scope = P5A.build_target_scope(projection)
    binding = P5A.build_policy_binding(
        scope, policy_id=coordinate.policy_id, policy_version=coordinate.version
    )
    coordinate_binding = P5A.build_policy_coordinate_binding(
        scope,
        policy_family=coordinate.policy_family,
        policy_id=coordinate.policy_id,
        policy_version=coordinate.version,
        policy_scope=coordinate.scope,
        policy_tenant_id=coordinate.tenant_id,
        policy_body_digest=record.policy_body_digest,
        issuing_authority_id=record.issuing_authority_id,
        key_id=record.key_id,
        signature_alg=record.signature_alg,
    )
    candidate = P5A.build_candidate(
        projection=projection, decision=decision, target_scope=scope,
        policy_binding=binding, policy_coordinate_binding=coordinate_binding,
    )
    attestation = mint_attestation(candidate)
    clock.at = ISSUANCE_INSTANT
    clock.reads = 0
    return World(
        clock=clock, app=app, decision=decision, candidate=candidate, attestation=attestation,
        authority=authority, record=record, producer_verifier=producer_verifier_for(),
        policy_verifier=policy_verifier_for(authority),
    )


def issue_request(world: World, **overrides) -> CloudScalingEnvelopeIssuanceRequest:
    base = dict(
        candidate=world.candidate, producer_attestation=world.attestation,
        audience="ugence.cloud-scaling.action-gate", session_id="sess-5b4-1", nonce="nonce-5b4-1",
    )
    base.update(overrides)
    return CloudScalingEnvelopeIssuanceRequest(**base)
