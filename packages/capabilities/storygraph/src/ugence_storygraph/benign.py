"""Deterministic benign-context layer (§7).

Many legitimate workflows *look* like the fragments of a prohibited capability:
an approved data migration reads credentials, touches protected data, and moves
it outbound — the same three fragments as exfiltration. A benign explanation must
**not** automatically suppress risk. It may qualify (downgrade) an escalation
only when backed by explicit, scope-matched evidence: an approved change ticket,
an authorized workflow id, a named approver, a time-bounded and unexpired
approval, a matching target scope, and (where the recipe requires it) a valid
policy version.

The analyzer records *both* the threat evidence and the benign evidence, and the
finding states plainly whether the threat interpretation dominates, is
neutralized, or remains ambiguous. Nothing here is probabilistic or learned.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# benign verdicts
THREAT_DOMINATES = "THREAT_DOMINATES"   # no applicable benign context; escalation stands
NEUTRALIZED = "NEUTRALIZED"             # valid scope-matched approval; downgrade
AMBIGUOUS = "AMBIGUOUS"                 # benign context present but insufficient


@dataclass(frozen=True)
class BenignContext:
    """An approval/authorization asserted on an event (structured evidence)."""

    tag: str
    workflow: str = ""
    approver: str = ""
    ticket: str = ""
    target_family: str = ""
    scope: str = ""
    policy_version: str = ""
    expires_at: float | None = None    # same unit as evaluation time
    source_event_id: str = ""


def extract_benign_context(event: dict, *, at_epoch_of) -> list[BenignContext]:
    """Pull structured approval evidence from an event, if present.

    ``at_epoch_of`` converts a supplied timestamp/expiry to the active time unit
    (injected by the analyzer so this stays clock-free).
    """
    raw = event.get("approval") or event.get("benign_context")
    if not raw or not isinstance(raw, dict):
        return []
    exp = raw.get("exp") or raw.get("expires_at")
    return [BenignContext(
        tag=str(raw.get("tag", "")).strip().lower(),
        workflow=str(raw.get("workflow_id") or raw.get("workflow") or "").strip().lower(),
        approver=str(raw.get("approver", "")).strip(),
        ticket=str(raw.get("ticket", "")).strip(),
        target_family=str(raw.get("target_family", "")).strip().lower(),
        scope=str(raw.get("scope", "")).strip().lower(),
        policy_version=str(raw.get("policy_version", "")).strip(),
        expires_at=at_epoch_of(exp) if exp is not None else None,
        source_event_id=str(event.get("event_id", "")),
    )]


@dataclass
class BenignVerdict:
    status: str
    applied: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    explanation: str = ""


def _context_valid(ctx: BenignContext, recipe, link_dims, now, active_policy_version):
    """Return (ok, reason). A benign context must be fully supported to apply."""
    if ctx.tag not in recipe.benign_exclusions:
        return False, f"tag {ctx.tag!r} is not an accepted benign exclusion for recipe"
    if not ctx.approver:
        return False, "no named approver"
    if not ctx.ticket and not ctx.workflow:
        return False, "no change ticket or authorized workflow id"
    if ctx.expires_at is not None and now is not None and now > ctx.expires_at:
        return False, "approval expired"
    # scope: the approval's target family must match the assembly's, when given
    asm_family = link_dims.get("target_family", "")
    if ctx.target_family and asm_family and ctx.target_family != asm_family:
        return False, (f"approval scope target_family {ctx.target_family!r} "
                       f"does not match assembly {asm_family!r}")
    if active_policy_version and ctx.policy_version and \
            ctx.policy_version != active_policy_version:
        return False, "approval bound to a different policy version"
    return True, "valid, scope-matched, unexpired approval"


def evaluate(recipe, contexts, link_dims, now, active_policy_version) -> BenignVerdict:
    """Decide whether benign context neutralizes, leaves ambiguous, or is absent."""
    if not contexts:
        return BenignVerdict(THREAT_DOMINATES,
                             explanation="no benign-context evidence present")
    applied, rejected = [], []
    for ctx in contexts:
        ok, reason = _context_valid(ctx, recipe, link_dims, now, active_policy_version)
        record = {"tag": ctx.tag, "approver": ctx.approver, "ticket": ctx.ticket,
                  "workflow": ctx.workflow, "reason": reason,
                  "source_event_id": ctx.source_event_id}
        (applied if ok else rejected).append(record)
    if applied:
        return BenignVerdict(
            NEUTRALIZED, applied=applied, rejected=rejected,
            explanation="valid scope-matched approval qualifies the escalation")
    return BenignVerdict(
        AMBIGUOUS, applied=applied, rejected=rejected,
        explanation="benign context asserted but not fully supported; "
                    "threat interpretation not neutralized")
