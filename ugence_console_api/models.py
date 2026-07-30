"""Canonical console API contracts (Pydantic v2 DTOs).

These are the *stable public contract* of the console API. Each maps 1:1 onto a
platform module's neutral request/result vocabulary, so the browser never sees a
module-internal type. Verdict vocabularies are preserved verbatim from the
modules (all fail-closed): ActionGate AUTHORIZED/DENIED/…; TAP SUPPORTED/
UNSUPPORTED/…; ACP CLEAR/HOLD.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Deployment mode — one product, three modes (First Look §2).
# --------------------------------------------------------------------------- #
class DeploymentMode(str, Enum):
    SHADOW = "shadow"                # observe + record, change nothing
    RECOMMENDATION = "recommendation"  # surface findings / required escalations
    ENFORCEMENT = "enforcement"      # actively allow / constrain / block before commit


# --------------------------------------------------------------------------- #
# Agent Gateway — Context Minimization ("what may enter").
# --------------------------------------------------------------------------- #
class ContextUnit(BaseModel):
    id: str
    text: str
    redundancy_set: Optional[str] = Field(
        default=None,
        description="Units sharing a redundancy_set carry the same fact; only one is kept.",
    )
    protected: bool = False


class MinimizeRequest(BaseModel):
    context_id: str = "ctx"
    units: List[ContextUnit]
    correlation_id: str = ""


class MinimizeResult(BaseModel):
    kept_ids: List[str]
    removed_ids: List[str]
    total_units: int
    removed_units: int
    protected_ids: List[str]
    lossless: bool = Field(description="True when structural compression preserved every fact.")


# --------------------------------------------------------------------------- #
# Truth & Evidence — Truth Assurance Platform (assertion governance).
# --------------------------------------------------------------------------- #
class AssertionRequest(BaseModel):
    assertion: str
    assertion_type: str = ""
    evidence_refs: List[str] = Field(default_factory=list)
    source_identity: str = ""
    policy_refs: List[str] = Field(default_factory=list)
    correlation_id: str = ""


class AssertionVerdict(BaseModel):
    coverage: str                      # SUPPORTED / UNSUPPORTED / CONSTRAINED / INDETERMINATE
    evidence_coverage: float
    covered_evidence_refs: List[str] = Field(default_factory=list)
    unsupported_elements: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    obligations: List[str] = Field(default_factory=list)
    provider_trace_id: str = ""


# --------------------------------------------------------------------------- #
# Action Control — ActionGate ("may THIS exact action execute?").
# --------------------------------------------------------------------------- #
class ActionRequest(BaseModel):
    action_type: str
    requested_parameters: Dict[str, str] = Field(default_factory=dict)
    actor: str = ""
    authority_context: str = ""
    target_resource: str = ""
    policy_refs: List[str] = Field(default_factory=list)
    risk_context: Dict[str, str] = Field(default_factory=dict)
    evidence_refs: List[str] = Field(default_factory=list)
    correlation_id: str = ""
    authorization_expired: bool = False


class ActionVerdict(BaseModel):
    outcome: str                       # AUTHORIZED / AUTHORIZED_WITH_CONSTRAINTS / DENIED / …
    constraints: List[str] = Field(default_factory=list)
    obligations: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)
    authority_basis: str = ""
    provider_trace_id: str = ""
    cer_id: str = Field(description="Canonical Execution Request identity (hash of the action envelope).")
    action_fingerprint: str = ""


# --------------------------------------------------------------------------- #
# Operational safety — Autonomous Control Plane ("safe right now?").
# --------------------------------------------------------------------------- #
class OperationalSignals(BaseModel):
    error_budget_remaining: Optional[float] = Field(
        default=None, description="Fraction 0..1 of the SLO error budget left.")
    cluster_health: Optional[str] = Field(
        default=None, description="green / yellow / red")
    change_freeze_active: Optional[bool] = Field(
        default=None, description="True during a change-freeze window.")


class ClearanceVerdict(BaseModel):
    disposition: str                   # CLEAR / HOLD
    reason_codes: List[str] = Field(default_factory=list)
    evaluated: Dict[str, str] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# The governed loop.
# --------------------------------------------------------------------------- #
class GovernedLoopRequest(BaseModel):
    mode: DeploymentMode = DeploymentMode.SHADOW
    correlation_id: Optional[str] = None
    context_units: List[ContextUnit] = Field(default_factory=list)
    assertion: AssertionRequest
    action: ActionRequest
    operational_signals: OperationalSignals


class StageResult(BaseModel):
    stage: str                         # Gateway / Verify / Authorize / Clear / Record
    capability: str
    module: str
    module_maturity: str
    question: str
    decision: str
    summary: str
    detail: Dict[str, object] = Field(default_factory=dict)


class GovernedLoopResult(BaseModel):
    correlation_id: str
    cer_id: str
    mode: DeploymentMode
    stages: List[StageResult]
    final_disposition: str             # human-readable, mode-aware
    would_execute: bool = Field(
        description="What enforcement mode WOULD do with this decision (computed even in shadow).")
    recorded: bool


# --------------------------------------------------------------------------- #
# Module registry + audit.
# --------------------------------------------------------------------------- #
class ModuleInfo(BaseModel):
    key: str
    name: str
    layer: str
    capability: str
    maturity: str
    wiring: str                        # loop | standalone | read-only
    question: str


class AuditEntry(BaseModel):
    stage: str
    module: str
    decision: str
    summary: str
    detail: Dict[str, object] = Field(default_factory=dict)


class AuditChain(BaseModel):
    correlation_id: str
    cer_id: str
    mode: str
    final_disposition: str
    entries: List[AuditEntry]
