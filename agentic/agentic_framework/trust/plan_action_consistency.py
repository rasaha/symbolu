"""
plan_action_consistency.py — Phase 2 heuristic observable (PROVISIONAL, advisory-only).

Detects OBVIOUS mismatches between a stated plan and the proposed action. Deterministic
keyword/structured heuristics — no ML, no GPU, no hidden state. Conservative by design: it
fires only on clear contradictions, and (being heuristic) is confirm-only.

Mismatch kinds:
  read_plan_mutating_action        plan says read/summarize/view but the action mutates/sends
  confirm_plan_executes            plan says ask/confirm/clarify but the action executes
  no_external_plan_external_action plan says no external access but the action uses an external tool
  resource_mismatch                plan targets one resource but the action targets another
                                   (only when both target sets are given and disjoint)

Produces a VALIDATOR / PROVISIONAL Observation (confirm-only). Inert when no context (or an
empty context) is supplied, so it never changes a production decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Mapping, Optional, Tuple

from agentic.agentic_framework.trust.observables import (
    EvidenceStatus,
    Observation,
    ObservableType,
    Verdict,
)

_READ_WORDS = ("read", "summarize", "summarise", "view", "list", "describe", "analyze",
               "analyse", "inspect", "show", "report on", "look at", "review")
_MUTATE_WORDS = ("write", "delete", "remove", "drop", "send", "email", "post", "transfer",
                 "update", "create", "modify", "overwrite", "purge", "deploy", "publish")
_EXECUTE_WORDS = _MUTATE_WORDS + ("execute", "run", "invoke", "perform", "trigger", "call")
_CONFIRM_WORDS = ("ask", "confirm", "clarify", "verify with", "check with", "get approval",
                  "request approval", "double-check")
_NO_EXTERNAL_PHRASES = ("no external", "without external", "local only", "offline",
                        "no network", "do not access the internet", "no internet",
                        "stay local", "without network")
_EXTERNAL_WORDS = ("http", "https", "url", "www", "email", "send", "api", "web", "browser",
                   "network", "upload", "download", "fetch_url", "remote")


def _has(text: str, words) -> bool:
    return any(w in text for w in words)


@dataclass(frozen=True)
class PlanActionContext:
    """A stated plan paired with the action actually proposed."""
    stated_plan: str = ""
    proposed_action: str = ""               # tool / action name
    action_args: Mapping[str, object] = field(default_factory=dict)
    user_goal: Optional[str] = None
    # optional structured hints (used only when present — conservative)
    plan_targets: Tuple[str, ...] = ()
    action_targets: Tuple[str, ...] = ()
    action_mutates: Optional[bool] = None    # override for action mutation detection
    action_external: Optional[bool] = None   # override for external-access detection

    def is_empty(self) -> bool:
        return not self.stated_plan and not self.proposed_action


@dataclass(frozen=True)
class PlanActionViolation:
    kind: str
    detail: str


def _action_text(ctx: PlanActionContext) -> str:
    return (ctx.proposed_action + " " + " ".join(
        f"{k} {v}" for k, v in (ctx.action_args or {}).items())).lower()


def _action_mutates(ctx: PlanActionContext, action_text: str) -> bool:
    if ctx.action_mutates is not None:
        return ctx.action_mutates
    return _has(action_text, _MUTATE_WORDS)


def _action_executes(ctx: PlanActionContext, action_text: str) -> bool:
    if ctx.action_mutates:
        return True
    return _has(action_text, _EXECUTE_WORDS)


def _action_external(ctx: PlanActionContext, action_text: str) -> bool:
    if ctx.action_external is not None:
        return ctx.action_external
    return _has(action_text, _EXTERNAL_WORDS)


def detect_plan_action_mismatch(ctx: PlanActionContext) -> List[PlanActionViolation]:
    """Return the deterministic list of obvious plan↔action mismatches (possibly empty)."""
    out: List[PlanActionViolation] = []
    plan = (ctx.stated_plan + " " + (ctx.user_goal or "")).lower()
    action_text = _action_text(ctx)

    plan_is_read = _has(plan, _READ_WORDS) and not _has(plan, _MUTATE_WORDS)
    if plan_is_read and _action_mutates(ctx, action_text):
        out.append(PlanActionViolation(
            "read_plan_mutating_action",
            f"plan is read-only but action '{ctx.proposed_action}' mutates/sends"))

    if _has(plan, _CONFIRM_WORDS) and _action_executes(ctx, action_text):
        out.append(PlanActionViolation(
            "confirm_plan_executes",
            f"plan says ask/confirm but action '{ctx.proposed_action}' executes"))

    if _has(plan, _NO_EXTERNAL_PHRASES) and _action_external(ctx, action_text):
        out.append(PlanActionViolation(
            "no_external_plan_external_action",
            f"plan forbids external access but action '{ctx.proposed_action}' is external"))

    if ctx.plan_targets and ctx.action_targets:
        pt = {t.lower() for t in ctx.plan_targets}
        at = {t.lower() for t in ctx.action_targets}
        if pt.isdisjoint(at):
            out.append(PlanActionViolation(
                "resource_mismatch",
                f"plan targets {sorted(pt)} but action targets {sorted(at)}"))

    return out


def build_plan_action_observation(
    ctx: Optional[PlanActionContext],
    *,
    evidence: EvidenceStatus = EvidenceStatus.PROVISIONAL,
) -> Optional[Observation]:
    """Build the plan-action-consistency Observation, or None when inert.

    Heuristic → verdict UNSURE on any mismatch (confirm-only), SAFE otherwise; it never emits
    UNSAFE (it does not block even when promoted — blocking a heuristic would need a separate,
    higher-bar decision). None when no/empty context, so production calls are unaffected.
    """
    if ctx is None or ctx.is_empty():
        return None

    violations = detect_plan_action_mismatch(ctx)
    verdict = Verdict.UNSURE if violations else Verdict.SAFE
    severity = min(1.0, 0.4 + 0.2 * len(violations)) if violations else 0.0
    if violations:
        reason = "plan-action mismatch: " + "; ".join(
            f"{v.kind} ({v.detail})" for v in violations)
    else:
        reason = "proposed action is consistent with the stated plan"

    return Observation(
        name="plan_action_consistency",
        otype=ObservableType.VALIDATOR,
        evidence=evidence,
        verdict=verdict,
        severity=severity,
        reason=reason,
        detail={"violations": [{"kind": v.kind, "detail": v.detail} for v in violations]},
    )
