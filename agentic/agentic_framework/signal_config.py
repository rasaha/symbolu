"""
signal_config.py — configuration for model-uncertainty signals in the MCP gateway.

Pivot (2026-06, falsification result): raw next-token predictive entropy is promoted to the
DEFAULT model-internal uncertainty signal; the CG 32-D sovereign-state projection
(entropy/vritti/JEPA-from-state) is DEMOTED to experimental/research-only. Rationale: on the
fastest-falsification fabrication probe (confident-but-unsafe hallucinated tools), raw
next-token entropy separated the fooled-unsafe cases (subset AUROC 0.857) while the 32-D
CG-state entropy was anti-predictive (0.457). See
AGENTIC_FRAMEWORK_INTERNAL_SIGNAL_THESIS.md. No proprietary claim is made about raw entropy —
it is a standard, provider-exposed quantity; the differentiation is the execution-path
*combination* of risk taxonomy + approvals + audit + budget + uncertainty signals.

All thresholds are CONSERVATIVE by default (escalate rarely, only on clearly-high entropy +
clearly-confident claims + non-trivial tool risk) and documented inline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SignalMode(str, Enum):
    """Operational posture of a signal in the gateway."""
    STABLE = "stable"              # production default; influences decisions
    EXPERIMENTAL = "experimental"  # research-only; ignored unless explicitly enabled


# Tool-risk ordering used by the gap's minimum-risk gate (mirrors ToolRiskLevel).
RISK_ORDER = ("read_only", "write", "execute", "destructive", "privileged")
RISK_RANK = {name: i for i, name in enumerate(RISK_ORDER)}


@dataclass(frozen=True)
class SignalConfig:
    """Gateway model-uncertainty signal configuration (conservative defaults).

    Raw entropy is the first-class signal; CG-state signals are off by default.
    """

    # --- raw next-token entropy (FIRST-CLASS, default ON) --------------------
    enable_raw_entropy_signal: bool = True
    raw_entropy_mode: SignalMode = SignalMode.STABLE

    # --- CG 32-D sovereign-state signals (DEMOTED: experimental, default OFF) -
    # When False, any caller-supplied CG-state entropy_result / vritti_result is
    # ignored for the decision (still recorded in audit as experimental). CG stays
    # research-only until it beats cheap uncertainty signals on held-out benchmarks.
    enable_cg_state_signals: bool = False
    cg_state_signals_mode: SignalMode = SignalMode.EXPERIMENTAL

    # --- confidence-risk gap escalation (the falsification finding, default ON) -
    # Fires when the model SAYS the action is safe (verbalized confidence high) but
    # its raw next-token entropy is HIGH (internally uncertain) on a non-trivial tool.
    enable_confidence_risk_gap: bool = True
    # The model's self-reported safety confidence must be at least this high to count
    # as a "confident" claim (so the gap captures confident-but-uncertain, not unsure).
    verbalized_safety_high: float = 0.70
    # Raw entropy must be at least this high to count as "internally uncertain".
    raw_entropy_high: float = 0.70
    # Only escalate the gap for tools at/above this risk level (skip read_only noise).
    min_risk_level_for_gap: str = "write"
    # Escalation level raised when the gap fires ("notify" | "confirm" | "halt").
    gap_escalation_level: str = "confirm"

    # --- verbalized safety self-assessment SEAM (default OFF) -----------------
    # The confidence-risk gap needs a verbalized safety score. We never invent one:
    # an adapter/agent may set `last_safety_confidence` from an existing signal, OR a
    # future self-assessment step may elicit it. That elicitation is a SECOND model
    # call (expensive), so it is gated here and OFF by default. When False, if no
    # safety score is supplied the gap simply does not fire (governance degrades to
    # verbalized confidence + risk taxonomy). Turning this on is the explicit opt-in
    # to pay for safety self-assessment; the elicitation itself is left to the caller.
    enable_safety_self_assessment: bool = False

    def risk_meets_gap_minimum(self, tool_risk_level: str) -> bool:
        """True if `tool_risk_level` is at/above the gap's minimum-risk gate."""
        return (RISK_RANK.get(str(tool_risk_level).lower(), 0)
                >= RISK_RANK.get(self.min_risk_level_for_gap, 0))


# The default the gateway uses if none is supplied: raw entropy on, CG off, gap on.
DEFAULT_SIGNAL_CONFIG = SignalConfig()
