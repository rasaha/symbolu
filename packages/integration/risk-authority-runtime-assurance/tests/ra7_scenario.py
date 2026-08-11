"""Shared RA-7 scenario builder.

Wires a **real** RA-6 status runtime (reference authority store + authenticated
lifecycle writer + reassessor) behind the leaf's neutral intake port, so RA-7's
signal handoff can be exercised through the genuine reassess→revoke path — never a
mock. Also provides deterministic observation factories and a reference RA-7
service.

Uniquely named (``ra7_scenario``) so running this package's tests alongside other
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

from ugence_risk_authority_runtime_assurance import (
    AuthorityReassessmentSignalEmitter,
    ReferenceTrajectoryPolicyReader,
    RuntimeAssuranceService,
    TrajectoryObservation,
    TrajectoryPolicy,
    TrajectoryPolicyRef,
)

FIXED_NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
TENANT = "tenant_123"
ENVELOPE = "env_abc"
POLICY_ID = "traj-policy-1"
POLICY_VERSION = "1"
WORKFLOW = "wf_finance_1"


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


def default_policy() -> TrajectoryPolicy:
    return TrajectoryPolicy(
        policy_id=POLICY_ID,
        version=POLICY_VERSION,
        cumulative_exposure_limits={"model_cost": 50000.0},
        near_boundary_fraction=0.9,
        near_boundary_repeat=3,
        retry_loop_threshold=4,
        data_class_order=("public", "internal", "confidential", "restricted"),
        max_data_class_rank=2,  # up to "confidential" permitted; "restricted" is a jump
        context_expansion_limit=100000.0,
    )


def default_ref() -> TrajectoryPolicyRef:
    return TrajectoryPolicyRef(POLICY_ID, POLICY_VERSION)


def build_reference_service(
    *,
    harness: Optional[RA6Harness] = None,
    policy: Optional[TrajectoryPolicy] = None,
) -> RuntimeAssuranceService:
    reader = ReferenceTrajectoryPolicyReader()
    reader.register(policy or default_policy())
    emitter = (
        AuthorityReassessmentSignalEmitter(harness.reassessor) if harness else None
    )
    return RuntimeAssuranceService.reference(policy_reader=reader, emitter=emitter)


def make_observation(
    seq: int,
    *,
    tenant_id: str = TENANT,
    workflow_instance_id: str = WORKFLOW,
    envelope_id: str = ENVELOPE,
    event_id: Optional[str] = None,
    action_id: Optional[str] = None,
    runtime_event_type: str = "PROVIDER_COMPLETED",
    observed_at: datetime = FIXED_NOW,
    source: str = "agent-runtime-telemetry",
    source_version: str = "0.6.0",
    policy_ref: Optional[TrajectoryPolicyRef] = None,
    detail: Optional[Mapping[str, Any]] = None,
) -> TrajectoryObservation:
    return TrajectoryObservation(
        schema_version="1",
        event_id=event_id if event_id is not None else f"{workflow_instance_id}:{seq}",
        tenant_id=tenant_id,
        workflow_instance_id=workflow_instance_id,
        envelope_id=envelope_id,
        runtime_event_type=runtime_event_type,
        observed_at=observed_at,
        source=source,
        source_version=source_version,
        action_id=action_id if action_id is not None else f"act-{seq}",
        sequence_number=seq,
        policy_ref=policy_ref if policy_ref is not None else default_ref(),
        detail=dict(detail or {}),
    )
