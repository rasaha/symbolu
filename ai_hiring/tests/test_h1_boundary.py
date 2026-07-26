"""H1 — architectural boundary tests.

Guards the two invariants H1 must not violate:

1. Human-only binding decisions are preserved — H1 introduces no hiring-decision
   authority for any actor (no accept/reject/hire outcome, no DGM decision path).
2. The hiring domain audit trail is hiring-owned and additive — it never smuggles
   new events into the frozen kernel ``AuditEventType`` and its active code consumes
   only the frozen ``decision_governance.api`` surface.
"""

from __future__ import annotations

import ast
import pathlib

from decision_governance.api.audit import AuditEventType
from ai_hiring.domain_audit.events import HiringDomainEventType
from ai_hiring.hiring_applications.status import (
    APPLICATION_TERMINAL_STATUSES,
    ApplicationStatus,
)

REPO = pathlib.Path(__file__).resolve().parents[2]

# Every module introduced by H1 (active application code).
H1_MODULES = [
    "ai_hiring/domain_audit/events.py", "ai_hiring/domain_audit/event.py",
    "ai_hiring/domain_audit/repository.py", "ai_hiring/domain_audit/service.py",
    "ai_hiring/requisitions/requisition.py", "ai_hiring/requisitions/job_definition.py",
    "ai_hiring/requisitions/status.py",
    "ai_hiring/candidates/candidate.py",
    "ai_hiring/hiring_applications/application.py", "ai_hiring/hiring_applications/status.py",
    "ai_hiring/hiring_applications/eligibility.py", "ai_hiring/hiring_applications/readiness.py",
    "ai_hiring/intake/intake.py",
    "ai_hiring/repositories/product_repositories.py",
    "ai_hiring/services/_hiring_context.py", "ai_hiring/services/requisition_service.py",
    "ai_hiring/services/candidate_service.py", "ai_hiring/services/application_service.py",
    "ai_hiring/services/evidence_intake_service.py",
    "ai_hiring/services/hiring_reconstruction_service.py",
    "ai_hiring/api/product_contracts.py",
]


def test_application_lifecycle_has_no_hiring_decision_outcome():
    """The structural lifecycle must not encode a binding accept/reject/hire outcome."""
    forbidden = {"ACCEPTED", "REJECTED", "HIRED", "OFFERED", "APPROVED", "DENIED", "DECIDED"}
    assert not ({s.value for s in ApplicationStatus} & forbidden)
    # Terminal states are purely structural closure.
    assert APPLICATION_TERMINAL_STATUSES == frozenset(
        {ApplicationStatus.CLOSED, ApplicationStatus.WITHDRAWN})


def test_h1_never_creates_a_governance_decision():
    """No H1 module references the kernel decision/authority contracts — binding
    decisions remain a later, human-authored governance phase."""
    banned = ("DecisionRecord", "DecisionOutcome", "CaseDecisionService",
              "RecommendationRecord", "ActionAuthorizationService")
    offenders = []
    for rel in H1_MODULES:
        src = (REPO / rel).read_text()
        for name in banned:
            if name in src:
                offenders.append(f"{rel} -> {name}")
    assert not offenders, "H1 must not touch governance decision contracts:\n" + "\n".join(offenders)


def test_domain_events_are_hiring_owned_not_in_frozen_kernel_enum():
    """The hiring domain event taxonomy is net-new and never added to the frozen
    kernel AuditEventType."""
    kernel_values = {m.value for m in AuditEventType}
    hiring_values = {m.value for m in HiringDomainEventType}
    assert hiring_values.isdisjoint(kernel_values)
    # And it is genuinely a distinct enum, not the kernel one.
    assert HiringDomainEventType is not AuditEventType


def test_h1_active_code_consumes_only_public_api():
    """Every H1 module that imports the platform imports it via decision_governance.api."""
    violations = []
    for rel in H1_MODULES:
        tree = ast.parse((REPO / rel).read_text(), filename=rel)
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                targets.append(node.module)
            elif isinstance(node, ast.Import):
                targets.extend(a.name for a in node.names)
            for t in targets:
                if t.split(".")[0] == "decision_governance" and not t.startswith("decision_governance.api"):
                    violations.append(f"{rel}:{node.lineno} -> {t}")
    assert not violations, "H1 code must import only decision_governance.api:\n" + "\n".join(violations)
