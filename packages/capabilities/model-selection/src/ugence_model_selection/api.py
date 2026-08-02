"""Ugence Model Selection — curated public API.

The stable surface for consumers of the canonical Model Selection product core. Every
symbol is re-exported (same object, identity preserved) from the capability's internal
modules, grouped by the two audited stages:

* **Eligibility** (ExecutionGate) — deterministic, fail-closed "can this approved
  candidate execute this request?"; never ranks or picks.
* **Selection** (ModelPolicy) — advisory, policy-bounded "which eligible candidate
  should?"; only ever chooses from the eligible set; abstains when none qualifies.

This module adds no logic. It does not invoke models, route, retry, fail over, load
balance, orchestrate, authorize actions, or register providers.
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

# --- selection stage (ModelPolicy) -------------------------------------------------
from .policy import PolicyWeights, Selection, select

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
    # selection
    "PolicyWeights", "Selection", "select",
    # registry
    "ExecStatus", "ExecutableRegistry", "ModelRecord",
    # versioning + fingerprint
    "fingerprint", "POLICY_VERSION", "VERSION", "__version__",
]
