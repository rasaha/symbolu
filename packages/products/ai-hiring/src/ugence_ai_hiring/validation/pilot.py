"""Bounded shadow-pilot cohort (H5) — synthetic, non-production.

Defines a small, manually-inspectable cohort with variation across requisition type,
seniority, evidence volume/completeness, recommendation confidence, human-review
outcome, ActionGate outcome, execution outcome, and reconciliation outcome. All data
is synthetic and all external effects go through deterministic in-memory adapters —
there are NO production HRIS writes, emails, calendar invites, payroll changes, or
identity provisioning.
"""

from __future__ import annotations

from ugence_governance_provider_framework.contracts import AssertionCoverage

from ..actions.action_types import HiringActionType
from ..governance.outcomes import HiringDecisionIntent
from .composition import build_validation_env
from .lifecycle import CaseRun, CaseSpec, run_lifecycle


def build_cohort() -> list[CaseSpec]:
    """A bounded, branch-covering synthetic cohort (analysis-only group labels)."""
    G = ("group_a", "group_b")
    specs: list[CaseSpec] = []
    # normal advance
    specs.append(CaseSpec(case_id="p01", group_label=G[0]))
    specs.append(CaseSpec(case_id="p02", group_label=G[1]))
    # hold
    specs.append(CaseSpec(case_id="p03", decision_intent=HiringDecisionIntent.HOLD,
                          action_type=HiringActionType.PLACE_ON_HOLD, group_label=G[0]))
    # reject → close
    specs.append(CaseSpec(case_id="p04", decision_intent=HiringDecisionIntent.REJECT,
                          action_type=HiringActionType.CLOSE_WITHOUT_SELECTION, group_label=G[1]))
    # offer preparation (authorized, not issued)
    specs.append(CaseSpec(case_id="p05", action_type=HiringActionType.PREPARE_OFFER, group_label=G[0]))
    # rejection preparation
    specs.append(CaseSpec(case_id="p06", decision_intent=HiringDecisionIntent.REJECT,
                          action_type=HiringActionType.PREPARE_REJECTION, group_label=G[1]))
    # constrained authorization (obligations satisfied)
    specs.append(CaseSpec(case_id="p07", action_constrained=frozenset({"ADVANCE_STAGE"}), group_label=G[0]))
    # denied authorization
    specs.append(CaseSpec(case_id="p08", action_denied=frozenset({"ADVANCE_STAGE"}), group_label=G[1]))
    # unsupported claim → review required (no decision/action)
    specs.append(CaseSpec(case_id="p09", assertion_coverage=AssertionCoverage.UNSUPPORTED,
                          decision_intent=None, action_type=None, group_label=G[0]))
    # incomplete evidence
    specs.append(CaseSpec(case_id="p10", provided_evidence=("resume",), decision_intent=None,
                          action_type=None, group_label=G[1]))
    # override (decision diverges from ADVANCE proposal)
    specs.append(CaseSpec(case_id="p11", decision_intent=HiringDecisionIntent.REJECT,
                          action_type=HiringActionType.CLOSE_WITHOUT_SELECTION, group_label=G[0]))
    # execution mismatch → compensation required
    specs.append(CaseSpec(case_id="p12", exec_flags={"observed_params_override": (("stage", "different"),)},
                          group_label=G[1]))
    return specs


def run_pilot(specs: list[CaseSpec] | None = None) -> list[CaseRun]:
    """Replay the cohort through the full lifecycle in one non-production env."""
    specs = specs or build_cohort()
    env = build_validation_env()
    return [run_lifecycle(env, s) for s in specs]
