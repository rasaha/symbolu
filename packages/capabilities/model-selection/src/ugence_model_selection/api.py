"""Ugence Model Authority — curated public API.

The stable surface for consumers of the canonical capability core. Every symbol is
re-exported (same object, identity preserved) from the capability's internal modules,
grouped by the pipeline stages:

* **Eligibility** (ExecutionGate) — deterministic, fail-closed "can this approved
  candidate execute this request?"; never ranks or picks.
* **Ranking** (ModelPolicy) — advisory, policy-bounded "which eligible candidate is
  preferred?"; only ever chooses from the eligible set; abstains when none qualifies.
* **Authority** (ModelAuthority) — the binding external contract: "which model, if any,
  is *authorized* to execute this request?"; wraps eligibility + ranking and issues a
  :class:`ModelAuthorizationDecision` (ALLOW / DENY / HOLD / ESCALATE).

Ranking remains an internal optimization mechanism; authorization is the external
contract. This module adds no logic. It does not invoke models, route, retry, fail over,
load balance, orchestrate, authorize actions, or register providers.
"""
from __future__ import annotations

# --- contracts: reason codes -------------------------------------------------------
from .reason_codes import ReasonCode, normalize_raw

# --- contracts: eligibility states, verdicts, criticality, evidence ----------------
from .states import (
    Criticality,
    ConditionResult,
    EligibilityDecision,
    EligibilityState,
    Evidence,
    EvidenceSource,
    SOURCE_PRECEDENCE,
    Verdict,
)

# --- contracts: request / candidate / signal / config ------------------------------
from .model import Candidate, GateConfig, Request, Signal

# --- eligibility stage (ExecutionGate) ---------------------------------------------
from .gate import ExecutionGate

# --- ranking stage (ModelPolicy) — internal optimization mechanism -----------------
from .policy import PolicyWeights, Selection, select

# --- authority stage (ModelAuthority) — binding external contract ------------------
from .authority import (
    AuthorityReasonCode,
    ModelAuthority,
    ModelAuthorityService,
    ModelAuthorizationDecision,
    ModelAuthorizationDisposition,
    ModelAuthorizationPolicy,
    ModelSelectionService,
    ModelSelector,
)

# --- executable registry (candidate-metadata port) ---------------------------------
from .registry import ExecStatus, ExecutableRegistry, ModelRecord

# --- versioning + deterministic fingerprint ----------------------------------------
from .fingerprint import fingerprint
from .version import POLICY_VERSION, VERSION, __version__

__all__ = [
    # reason codes
    "ReasonCode", "normalize_raw",
    # states / evidence
    "Criticality", "ConditionResult", "EligibilityDecision", "EligibilityState",
    "Evidence", "EvidenceSource", "SOURCE_PRECEDENCE", "Verdict",
    # request / candidate / signal / config
    "Candidate", "GateConfig", "Request", "Signal",
    # eligibility
    "ExecutionGate",
    # ranking (internal optimization mechanism)
    "PolicyWeights", "Selection", "select",
    # authority (binding external contract)
    "ModelAuthority", "ModelAuthorityService", "ModelAuthorizationDecision",
    "ModelAuthorizationDisposition", "AuthorityReasonCode",
    # deprecated Model Selection → Model Authority compatibility aliases
    "ModelSelector", "ModelSelectionService", "ModelAuthorizationPolicy",
    # registry
    "ExecStatus", "ExecutableRegistry", "ModelRecord",
    # versioning + fingerprint
    "fingerprint", "POLICY_VERSION", "VERSION", "__version__",
]
