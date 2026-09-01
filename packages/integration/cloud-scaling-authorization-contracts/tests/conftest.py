"""Shared fixtures for the Phase 5A authorization-contracts suite.

Nothing here is a stub of the artifacts under test. The chain is genuine end to end:

* the recommendation comes from the controller's **real** Phase-3 pipeline;
* the projection comes from the **real** Phase 4C ``project_recommendation``;
* the ``SubjectRiskDecision`` comes from the **real** ``RiskEvaluationSeam.reference(...)``
  — genuine v2 admission, genuine binding revalidation, a genuine binding decision;
* the producer attestation carries a **real Ed25519 signature** over the real canonical
  signing payload.

The signature is real for realism, not because Phase 5A checks it — Phase 5A verifies no
signature at all. Signing genuinely simply keeps the fixture the shape production will
have, so the frozen digests below are the digests production would produce.

The seams are sentinels, never substitutes: :class:`ForbiddenCollaborator` fails the test
if it is reached, which is how the suite proves that a rejected input reaches no
collaborator rather than merely producing no candidate.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pytest

import ph_helpers as H  # controller Phase-3 test builders
from risk_authority.crypto import SigningKey, canonical_bytes
from risk_authority.integrations import SubjectRiskDecision
from ugence_cloud_scaling_controller.canonical.identity import CapacitySubject
from ugence_cloud_scaling_controller.planning import recommend_capacity_action
from ugence_cloud_scaling_controller.planning.recommendation import (
    CapacityActionRecommendation,
)
from ugence_cloud_scaling_risk_integration import (
    CapacityRiskSubjectProjection,
    authenticate_controller_output,
    project_recommendation,
)

from ugence_cloud_scaling_authorization_contracts import (
    POLICY_TARGET_BINDING_V2_SCHEMA_VERSION,
    PRODUCER_SIGNING_PURPOSE,
    ExecutionTargetScope,
    PolicyTargetBindingReference,
    PolicyTargetBindingReferenceV2,
    ProducerAttestationEvidence,
    build_capacity_authorization_candidate,
    canonical_digest,
)

# The controller fixtures are anchored at 2026-01-01T00:00:00Z; the recommendation is
# stamped at +190s with a 300s validity window, so "inside the window" is [190s, 490s].
REC_TIME = H.at(190.0)
VALIDITY_SECONDS = 300.0
INSIDE_WINDOW = H.at(300.0)

#: A fixed, non-secret test seed. Determinism is the point: the frozen digests must be
#: reproducible from the repository alone, with no generated key material.
PRODUCER_SEED = bytes(range(32, 64))

#: The tenant every fixture in this suite is scoped to. Named here because the V2 policy
#: coordinate carries a tenant component and is not always built from a target scope.
FIXTURE_TENANT_ID = "tenant-1"
PRODUCER_ID = "ugence.cloud-scaling-controller"
PRODUCER_KEY_ID = "producer-attestation-key-1"

RECOMMENDATION_ID = "rec-phase5a-1"
#: Synthetic but format-realistic, ratified ETS-13. The former value,
#: ``"acct-000123456789"``, was valid under no cloud at all, so no fixture ever exercised
#: what a real account identifier looks like on any provider. These are shaped like the
#: real thing and are *not* real: the AWS value is in the reserved 0000-prefixed range, the
#: GCP value is project-number-shaped, and the Azure value is a nil-adjacent GUID. No
#: fixture in this repository may carry a real customer or cloud account identifier.
ACCOUNT_ID = "000000000042"                              # AWS: 12-digit account number
ACCOUNT_ID_GCP = "000000000000000000317"                 # GCP: project number
ACCOUNT_ID_AZURE = "00000000-0000-4000-8000-000000000317"  # Azure: subscription GUID
ACCOUNT_ID_SELF_HOSTED = "cluster.control.internal"      # self-hosted: local authority

#: The default provider for fixtures. AWS because it is the shortest realistic identifier
#: and carries no resource-group obligation; the other three are exercised explicitly by
#: the schema-2 rule tests rather than by being the silent default.
CLOUD_PROVIDER = "aws"

#: Azure only. A resource group name, not an ARN or a full ARM id: the scope carries the
#: subscription in ``account_id`` and the group here, and an adapter composes the two.
RESOURCE_GROUP_AZURE = "rg-capacity-nonprod"
MAX_MAGNITUDE = 20
MAX_DELTA = 5


def production_subject(
    *,
    workload_id: str = "checkout-api",
    tenant_id: str = "tenant-1",
    **overrides: Any,
) -> CapacitySubject:
    """A fully-populated, production-shaped capacity subject.

    Every optional placement field is present. The frozen fixture uses this deliberately:
    a subject with ``None`` region and ``None`` cluster would leave the target-scope
    placement equality checks untested against real values.
    """

    kwargs = dict(
        workload_id=workload_id,
        tenant_id=tenant_id,
        resource_id="deploy/checkout-api",
        environment="prod",
        cluster="prod-us-east-1-blue",
        region="us-east-1",
        zone="us-east-1a",
    )
    kwargs.update(overrides)
    return CapacitySubject(**kwargs)


def build_recommendation(
    *,
    predicted: int = 9,
    current: int = 6,
    subject=None,
    recommendation_id: str = RECOMMENDATION_ID,
) -> CapacityActionRecommendation:
    """A genuine recommendation through the real Phase-3 pipeline."""

    subject = subject if subject is not None else production_subject()
    outcome = recommend_capacity_action(
        H.build_forecast_evidence(predicted, subj=subject),
        H.replicas_state(H.at(180.0), current, subj=subject),
        H.cost_book(subj=subject),
        H.constraints(),
        H.policy(),
        recommendation_time=REC_TIME,
        validity_seconds=VALIDITY_SECONDS,
        recommendation_id=recommendation_id,
    )
    if not isinstance(outcome, CapacityActionRecommendation):
        raise AssertionError(f"fixture produced {type(outcome).__name__}, not a recommendation")
    return outcome


def build_projection(recommendation=None) -> CapacityRiskSubjectProjection:
    """The genuine Phase 4C projection of a genuine recommendation."""

    recommendation = recommendation if recommendation is not None else build_recommendation()
    serialized = recommendation.to_canonical_dict()
    authenticated = authenticate_controller_output(
        recommendation,
        expected_recommendation_digest=serialized["evidence_digest"],
    )
    return project_recommendation(authenticated)


def reference_seam(now: datetime = INSIDE_WINDOW):
    """The REAL ``RiskEvaluationSeam.reference(...)`` — genuine v2 admission and decision.

    Visibly labelled reference: the production factory can never yield it. It is used to
    *produce* a genuine ``SubjectRiskDecision`` for the suite to consume. The Phase 5A
    package itself imports nothing from it — see ``test_import_boundary.py``.
    """

    from risk_authority.api.evaluation_seam import RiskEvaluationSeam
    from risk_authority.crypto import SigningKeyRecord
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
        key_record=SigningKeyRecord("cs-key", SigningKey.from_seed(bytes(range(32)))),
        clock=lambda: now,
        policy_resolver=ReferenceSubjectAwarePolicyResolver(
            by_purpose_domain={(PURPOSE_CAPACITY_ACTION, DOMAIN_CLOUD_SCALING): workflow}
        ),
    )


def build_decision(projection: CapacityRiskSubjectProjection) -> SubjectRiskDecision:
    """A genuine ALLOW-family ``SubjectRiskDecision`` for this exact projection."""

    decision = reference_seam().evaluate(projection.request)
    if type(decision) is not SubjectRiskDecision:
        raise AssertionError(f"seam returned {type(decision).__name__}")
    return decision


def build_attestation(
    *,
    recommendation_digest: str,
    recommendation_id: str = RECOMMENDATION_ID,
    producer_id: str = PRODUCER_ID,
    producer_key_id: str = PRODUCER_KEY_ID,
    signing_purpose: str = PRODUCER_SIGNING_PURPOSE,
    issued_at: datetime = REC_TIME,
) -> ProducerAttestationEvidence:
    """A genuine Ed25519-signed producer attestation over the canonical signing payload."""

    payload = {
        "schema_version": "cloud-scaling-producer-attestation-evidence-1",
        "producer_id": producer_id,
        "producer_key_id": producer_key_id,
        "signature_algorithm": "ed25519",
        "signing_purpose": signing_purpose,
        "recommendation_id": recommendation_id,
        "recommendation_digest": recommendation_digest,
        "issued_at": issued_at,
    }
    signature = SigningKey.from_seed(PRODUCER_SEED).sign(canonical_bytes(payload))
    return ProducerAttestationEvidence(
        producer_id=producer_id,
        producer_key_id=producer_key_id,
        signature_algorithm="ed25519",
        signature=signature.hex(),
        recommendation_id=recommendation_id,
        recommendation_digest=recommendation_digest,
        signing_purpose=signing_purpose,
        signing_payload_digest=canonical_digest(payload),
        issued_at=issued_at,
    )


def build_target_scope(
    projection: CapacityRiskSubjectProjection,
    *,
    account_id: str = ACCOUNT_ID,
    cloud_provider: str = CLOUD_PROVIDER,
    max_magnitude: int = MAX_MAGNITUDE,
    max_delta: int = MAX_DELTA,
    **overrides: Any,
) -> ExecutionTargetScope:
    """An execution target scope matching the projected subject, plus the account binding."""

    context = projection.context
    kwargs = dict(
        tenant_id=projection.tenant_id,
        account_id=account_id,
        cloud_provider=cloud_provider,
        environment=context.environment,
        region=context.region,
        zone=context.zone,
        namespace=None,
        compute_group=context.compute_group,
        resource_class=context.resource_class,
        action_type=context.action_type,
        magnitude_before=context.magnitude_before,
        requested_magnitude=context.magnitude_after,
        max_permitted_magnitude=max_magnitude,
        max_permitted_delta=max_delta,
    )
    kwargs.update(overrides)
    return ExecutionTargetScope(**kwargs)


def build_policy_binding(
    target_scope: ExecutionTargetScope,
    *,
    policy_id: str = "cloud-scaling.capacity-bounds",
    policy_version: str = "3.1.0",
    policy_issuer: str = "ugence.policy-authority",
    policy_key_id: str = "policy-signing-key-7",
    max_magnitude: Optional[int] = None,
    max_delta: Optional[int] = None,
    **overrides: Any,
) -> PolicyTargetBindingReference:
    """A policy/target binding referencing this exact scope by digest."""

    body = dict(
        policy_id=policy_id,
        policy_version=policy_version,
        policy_artifact_digest=canonical_digest({"policy": policy_id, "v": policy_version}),
        policy_issuer=policy_issuer,
        policy_key_id=policy_key_id,
        target_scope_digest=target_scope.digest(),
        max_permitted_magnitude=(
            max_magnitude if max_magnitude is not None else target_scope.max_permitted_magnitude
        ),
        max_permitted_delta=(
            max_delta if max_delta is not None else target_scope.max_permitted_delta
        ),
        policy_signature_algorithm="ed25519",
    )
    body.update({k: v for k, v in overrides.items() if k != "policy_signature"})
    payload = {"schema_version": "cloud-scaling-policy-target-binding-1", **body}
    signature = overrides.get(
        "policy_signature",
        SigningKey.from_seed(bytes(range(64, 96))).sign(canonical_bytes(payload)).hex(),
    )
    return PolicyTargetBindingReference(
        policy_signature=signature, binding_digest=canonical_digest(payload), **body
    )


def build_policy_coordinate_binding(
    target_scope: Optional[ExecutionTargetScope] = None,
    *,
    target_scope_digest: Optional[str] = None,
    policy_family: str = "capacity-bounds",
    policy_id: str = "cloud-scaling.capacity-bounds",
    policy_version: str = "3.1.0",
    policy_scope: str = "TENANT",
    policy_tenant_id: Optional[str] = None,
    policy_body_digest: Optional[str] = None,
    issuing_authority_id: str = "ugence.policy-authority",
    key_id: str = "policy-signing-key-7",
    signature_alg: str = "ed25519",
    **overrides: Any,
) -> PolicyTargetBindingReferenceV2:
    """A complete Policy Authority coordinate, bound to this exact scope (5B-1).

    ``policy_body_digest`` here is **well-shaped, not genuine**: it is a bare 64-hex digest
    over the fixture's own identity, because Phase 5A depends on neither the Policy Authority
    nor the UVI contracts and so cannot issue a real policy to derive one from. That is a
    property of this fixture and not of the contract — exactly as the existing
    ``policy_artifact_digest`` placeholder is. The genuine article is built in the Phase 5B-0B
    suite, which has the authority available and reconciles this coordinate against a real
    issued record.
    """

    if (target_scope is None) == (target_scope_digest is None):
        raise TypeError("pass exactly one of target_scope or target_scope_digest")
    tenant = policy_tenant_id
    if tenant is None:
        tenant = target_scope.tenant_id if target_scope is not None else FIXTURE_TENANT_ID
    body = dict(
        policy_family=policy_family,
        policy_id=policy_id,
        policy_version=policy_version,
        policy_scope=policy_scope,
        policy_tenant_id=tenant,
        issuing_authority_id=issuing_authority_id,
        key_id=key_id,
        signature_alg=signature_alg,
        target_scope_digest=(
            target_scope.digest() if target_scope is not None else target_scope_digest
        ),
    )
    digest = policy_body_digest or hashlib.sha256(
        canonical_bytes({"policy": policy_id, "v": policy_version, "body": "fixture"})
    ).hexdigest()
    body.update(policy_content_digest=digest, policy_body_digest=digest)
    body.update(overrides)
    payload = {
        "schema_version": POLICY_TARGET_BINDING_V2_SCHEMA_VERSION,
        "policy_family": body["policy_family"],
        "policy_id": body["policy_id"],
        "policy_version": body["policy_version"],
        "policy_content_digest": body["policy_content_digest"],
        "policy_scope": body["policy_scope"],
        "policy_tenant_id": body["policy_tenant_id"],
        "policy_body_digest": body["policy_body_digest"],
        "issuing_authority_id": body["issuing_authority_id"],
        "key_id": body["key_id"],
        "signature_alg": body["signature_alg"],
        "target_scope_digest": body["target_scope_digest"],
    }
    return PolicyTargetBindingReferenceV2(
        binding_digest=canonical_digest(payload), **body
    )


def coordinate_for(policy_binding, **overrides) -> PolicyTargetBindingReferenceV2:
    """The V2 coordinate that agrees with a given V1 binding.

    Derived *from* the binding rather than built alongside it, so a test that varies the
    binding does not have to remember to vary the coordinate too — the two stay in agreement
    unless a test deliberately breaks it, which is what
    ``tests/test_policy_coordinate_binding.py`` does on purpose.
    """

    derived = dict(
        target_scope_digest=policy_binding.target_scope_digest,
        policy_id=policy_binding.policy_id,
        policy_version=policy_binding.policy_version,
    )
    derived.update(overrides)
    return build_policy_coordinate_binding(**derived)


def build_candidate(**overrides: Any):
    """The full genuine chain: recommendation → projection → decision → candidate."""

    projection = overrides.pop("projection", None) or build_projection()
    decision = overrides.pop("decision", None) or build_decision(projection)
    attestation = overrides.pop("producer_attestation", None) or build_attestation(
        recommendation_digest=projection.recommendation_digest
    )
    target_scope = overrides.pop("target_scope", None) or build_target_scope(projection)
    policy_binding = overrides.pop("policy_binding", None) or build_policy_binding(target_scope)
    coordinate_binding = overrides.pop(
        "policy_coordinate_binding", None
    ) or build_policy_coordinate_binding(
        target_scope,
        policy_id=policy_binding.policy_id,
        policy_version=policy_binding.policy_version,
    )
    return build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        producer_attestation=attestation,
        policy_binding=policy_binding,
        policy_coordinate_binding=coordinate_binding,
        target_scope=target_scope,
    )


class ForbiddenCollaborator:
    """Fails the test if it is reached at all. A sentinel, not a mock."""

    def __init__(self, name: str = "collaborator") -> None:
        self.name = name
        self.calls: list = []

    def __getattr__(self, item: str):
        def _fail(*args: Any, **kwargs: Any):  # pragma: no cover - reaching this IS failure
            raise AssertionError(
                f"the Phase 5A boundary reached {self.name}.{item} — no collaborator may "
                "be invoked while building a candidate"
            )

        return _fail


@pytest.fixture
def projection() -> CapacityRiskSubjectProjection:
    return build_projection()


@pytest.fixture
def decision(projection) -> SubjectRiskDecision:
    return build_decision(projection)


@pytest.fixture
def attestation(projection) -> ProducerAttestationEvidence:
    return build_attestation(recommendation_digest=projection.recommendation_digest)


@pytest.fixture
def target_scope(projection) -> ExecutionTargetScope:
    return build_target_scope(projection)


@pytest.fixture
def policy_binding(target_scope) -> PolicyTargetBindingReference:
    return build_policy_binding(target_scope)


@pytest.fixture
def policy_coordinate_binding(target_scope) -> PolicyTargetBindingReferenceV2:
    return build_policy_coordinate_binding(target_scope)


@pytest.fixture
def candidate(
    projection, decision, attestation, target_scope, policy_binding, policy_coordinate_binding
):
    return build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        producer_attestation=attestation,
        policy_binding=policy_binding,
        policy_coordinate_binding=policy_coordinate_binding,
        target_scope=target_scope,
    )
