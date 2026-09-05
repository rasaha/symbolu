"""The genuine chain, extended by one envelope: 5B-4's world, plus the envelope it issues.

Everything upstream of admission is built by the neighbours' own fixture modules; this
module only issues the envelope through the 5B-4 composition root and remembers the
session it was issued for, which the admission request must present again.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from risk_authority.api import RiskAuthorityApplication
from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.domain import WorkflowIR, WorkflowStatus
from risk_authority.integrations import InMemoryWorkflowIRSource
from risk_authority.persistence import SqliteRiskAuthorityStore
from risk_authority.services.decision_authority import ReferenceDecisionAuthority

from _issuance_fixtures import ISSUANCE_INSTANT, KEY_RECORD, Clock, build_world, issue_request

from ugence_cloud_scaling_action_admission import (
    CapacityAdmissionRequest,
    CloudScalingActionAdmission,
)

__all__ = [
    "ADMISSION_INSTANT",
    "ISSUANCE_INSTANT",
    "SESSION_ID",
    "World",
    "build_admission_world",
    "admission_request",
    "production_app",
    "Clock",
]

SESSION_ID = "sess-5c-1"
#: One second after issuance: inside the envelope window and the candidate's admissible window.
ADMISSION_INSTANT: datetime = ISSUANCE_INSTANT + timedelta(seconds=1)


@dataclass
class World:
    clock: Clock
    app: RiskAuthorityApplication
    candidate: Any
    envelope: Any
    issuance_world: Any

    @property
    def target_scope(self):
        return self.candidate.target_scope

    def admission(self) -> CloudScalingActionAdmission:
        return CloudScalingActionAdmission.reference(app=self.app, clock=self.clock)


def build_admission_world() -> World:
    issuance_world = build_world()
    out = issuance_world.issuance().issue(issue_request(issuance_world, session_id=SESSION_ID))
    assert out.issued, (out.refusal, out.detail)
    clock = issuance_world.clock
    clock.at = ADMISSION_INSTANT
    clock.reads = 0
    return World(clock=clock, app=issuance_world.app, candidate=issuance_world.candidate,
                 envelope=out.envelope, issuance_world=issuance_world)


def admission_request(world: World, **overrides) -> CapacityAdmissionRequest:
    base = dict(tenant_id=world.candidate.tenant_id, envelope_id=world.envelope.envelope_id,
                target_scope=world.target_scope, candidate_digest=world.candidate.candidate_digest,
                session_id=SESSION_ID)
    base.update(overrides)
    return CapacityAdmissionRequest(**base)


# --- a production Risk Authority application, as Risk Authority's own containment suite builds it
NOW = datetime(2026, 1, 1, 0, 6, tzinfo=timezone.utc)


class _Ingress:
    def is_trusted(self, evidence, *, now): return True


class _Admission:
    def is_admissible(self, record, *, now): return True


class _ControlAssurance:
    is_production_authoritative = True

    def evaluate(self, request):  # pragma: no cover
        raise AssertionError("not reached")


class _DecisionAuthority:
    is_production_authoritative = True

    def __init__(self): self._inner = ReferenceDecisionAuthority()

    def issue_decision(self, **kw): return self._inner.issue_decision(**kw)


def production_app() -> RiskAuthorityApplication:
    source = InMemoryWorkflowIRSource()
    source.register(WorkflowIR(workflow_ir_id="w", version="1", status=WorkflowStatus.ACTIVE,
                               rules=(), source_refs=(), effective_at=NOW).with_digest())
    return RiskAuthorityApplication(
        workflow_source=source, key_record=KEY_RECORD, clock=lambda: NOW,
        evidence_admission=_Admission(), control_assurance=_ControlAssurance(),
        evidence_ingress=_Ingress(), decision_authority=_DecisionAuthority(),
        persistence=SqliteRiskAuthorityStore(os.path.join(tempfile.mkdtemp(), "ra.sqlite")),
        production_mode=True,
    )
