"""Shared RA-8 scenario builder.

Wires a **real** RA-6 status runtime (reference authority store + authenticated
lifecycle writer + reassessor) behind the leaf's neutral intake port, so RA-8's
signal handoff can be exercised through the genuine reassess→revoke path — never a
mock. Also provides deterministic governed-context / effect-observation factories
and a reference RA-8 service.

Uniquely named (``ra8_scenario``) so running this package's tests alongside other
packages in one pytest process never collides on a shared ``conftest`` name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Mapping, Optional

from risk_authority.integrations.authority_lifecycle import WriterPrincipal

from ugence_risk_authority_status_runtime import (
    AuthorityLifecycleService,
    AuthorityReassessor,
    ReferenceAuthorityStore,
    ReferenceWriterAuthorizer,
)
from ugence_risk_authority_status_runtime.writer import LIFECYCLE_WRITE_CAPABILITY

from ugence_decision_authority.execution.status import BusinessOutcome, Finality

from ugence_risk_authority_execution_assurance import (
    EffectAssuranceService,
    EffectAssuranceSignalEmitter,
    EffectObservation,
    ExpectedEffect,
    GovernedAuthorityContext,
)

FIXED_NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
TENANT = "tenant_123"
ENVELOPE = "env_abc"
WORKFLOW = "wf_finance_1"
ACTION_DIGEST = "pf-abc-123"
CORRELATION_ID = "corr-1"
ATTEMPT_ID = "idem-1#attempt-1"
PROVIDER = "cloud"
EXTERNAL_REQUEST = "ext-req-1"


def fixed_clock() -> datetime:
    return FIXED_NOW


@dataclass
class RA6Harness:
    """A real RA-6 reassess→revoke stack behind the neutral intake port."""

    store: ReferenceAuthorityStore
    writer: AuthorityLifecycleService
    reassessor: AuthorityReassessor
    events: List[Any] = field(default_factory=list)

    def is_envelope_revoked(self, envelope_id: str, tenant_id: str = TENANT) -> bool:
        return envelope_id in self.store.export(tenant_id).revoked_envelopes

    def current_epoch(self, tenant_id: str = TENANT) -> int:
        return self.store.export(tenant_id).epoch


def build_ra6_harness() -> RA6Harness:
    store = ReferenceAuthorityStore()
    store.seed_tenant(TENANT)
    events: List[Any] = []
    writer = AuthorityLifecycleService(
        store,
        ReferenceWriterAuthorizer(),
        event_sink=events.append,
        clock=fixed_clock,
        production_mode=False,
    )
    system_principal = WriterPrincipal(
        principal_id="ra-automated-reassessor",
        tenant_id=TENANT,
        capabilities=frozenset({LIFECYCLE_WRITE_CAPABILITY}),
    )
    reassessor = AuthorityReassessor(writer, system_principal=system_principal)
    return RA6Harness(store=store, writer=writer, reassessor=reassessor, events=events)


def default_context(
    *,
    tenant_id: str = TENANT,
    workflow_instance_id: str = WORKFLOW,
    envelope_id: str = ENVELOPE,
    authorized_action_digest: str = ACTION_DIGEST,
    correlation_id: str = CORRELATION_ID,
    provider: str = PROVIDER,
    idempotency_key: str = "idem-1",
) -> GovernedAuthorityContext:
    return GovernedAuthorityContext(
        tenant_id=tenant_id,
        workflow_instance_id=workflow_instance_id,
        envelope_id=envelope_id,
        authorized_action_digest=authorized_action_digest,
        correlation_id=correlation_id,
        provider=provider,
        idempotency_key=idempotency_key,
    )


def default_expected(
    *,
    action_type: str = "terminate_instances",
    target_system: str = "cloud",
    authorized_parameters: Optional[Mapping[str, str]] = None,
) -> ExpectedEffect:
    return ExpectedEffect(
        action_type=action_type,
        target_system=target_system,
        authorized_parameters=dict(
            authorized_parameters if authorized_parameters is not None else {"target": "i-123"}
        ),
    )


def make_observation(
    observation_id: str,
    business_outcome: BusinessOutcome,
    *,
    finality: Finality = Finality.FINAL,
    external_effect_id: str = "",
    tenant_id: str = TENANT,
    workflow_instance_id: str = WORKFLOW,
    envelope_id: str = ENVELOPE,
    authorized_action_digest: str = ACTION_DIGEST,
    attempt_id: str = ATTEMPT_ID,
    external_request_id: str = EXTERNAL_REQUEST,
    provider: str = PROVIDER,
    observed_parameters: Optional[Mapping[str, str]] = None,
    source: str = "reference-effect-source",
    source_version: str = "1",
) -> EffectObservation:
    return EffectObservation(
        schema_version="1",
        observation_id=observation_id,
        tenant_id=tenant_id,
        workflow_instance_id=workflow_instance_id,
        envelope_id=envelope_id,
        authorized_action_digest=authorized_action_digest,
        attempt_id=attempt_id,
        external_request_id=external_request_id,
        business_outcome=business_outcome,
        provider=provider,
        external_effect_id=external_effect_id or f"eff-{observation_id}",
        observed_parameters=dict(
            observed_parameters if observed_parameters is not None else {"target": "i-123"}
        ),
        finality=finality,
        source=source,
        source_version=source_version,
    )


def build_reference_service(
    *, harness: Optional[RA6Harness] = None
) -> EffectAssuranceService:
    emitter = EffectAssuranceSignalEmitter(harness.reassessor) if harness else None
    return EffectAssuranceService.reference(emitter=emitter)


def assess(
    service: EffectAssuranceService,
    observations,
    *,
    context: Optional[GovernedAuthorityContext] = None,
    expected: Optional[ExpectedEffect] = None,
    attempt_id: str = ATTEMPT_ID,
    external_request_id: str = EXTERNAL_REQUEST,
    idempotency_key: str = "idem-1",
    provider: str = PROVIDER,
    effect_source_available: bool = True,
):
    return service.assess(
        context or default_context(),
        attempt_id=attempt_id,
        expected=expected or default_expected(),
        observations=observations,
        external_request_id=external_request_id,
        idempotency_key=idempotency_key,
        provider=provider,
        effect_source_available=effect_source_available,
        produced_at=FIXED_NOW,
    )
