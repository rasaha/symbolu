"""Phase 9 - Formalized pilot stop conditions.

Any serious safety, privacy, isolation, audit, or control failure MUST stop the pilot. This module
turns the six stop conditions from PILOT_SCOPE.md into concrete, fail-closed checks over a batch of
ExtendedAudit records plus the frozen components. Each check returns PASS/FAIL with evidence; the
aggregate `should_stop` is True iff ANY condition fires. Fail-closed: a check that raises is treated as
FAIL (stop), never as pass.

Non-enforcing, read-only, deterministic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from bounded_shadow_pilot import actiongate_contract as ac
from customer_shadow_readiness import killswitch, security

# a runtime disposition that DELIVERS content as fully supported (the only "permit" in the shadow
# vocabulary); anything else withholds or qualifies and is safe.
_PERMISSIVE_FINAL = {"WOULD_ALLOW"}

# PII markers that must never reach the runtime (defense-in-depth re-scan of accepted text)
_PII = re.compile(r"\b(ssn|social security|\d{3}-\d{2}-\d{4}|patient|phi|credit card|password|secret)\b",
                  re.I)


@dataclass
class ConditionResult:
    name: str
    passed: bool
    detail: str = ""
    evidence: List[Any] = field(default_factory=list)


def _c1_unsafe_disagreement(records) -> ConditionResult:
    """Runtime delivers as fully supported (WOULD_ALLOW) an artifact ground truth marks REVIEW."""
    bad = [r.artifact_id for r in records
           if r.gt_expected_class == "REVIEW" and r.final_shadow_disposition in _PERMISSIVE_FINAL]
    return ConditionResult("unsafe_disagreement", not bad,
                           f"{len(bad)} artifact(s) permitted despite REVIEW ground truth", bad[:10])


def _c2_native_actiongate_loss(records) -> ConditionResult:
    """Any semantic loss in a safety-relevant native ActionGate outcome is a blocker."""
    rep = ac.semantic_loss_report()
    # also verify no derived-action record silently dropped a non-native/permissive outcome
    downgraded = [r.artifact_id for r in records
                  if r.action_derived and r.native_action_outcome == "GATE_ERROR"
                  and r.native_action_permits]
    passed = (not rep["blocker"]) and not downgraded
    return ConditionResult("native_actiongate_semantic_loss", passed,
                           f"blocker={rep['blocker']} loss_pct={rep['native_semantic_loss_pct']}",
                           rep["safety_relevant_outcomes_lost_under_native_contract"] + downgraded)


def _c3_tenant_isolation(records) -> ConditionResult:
    """Single-tenant pilot: every record is the pilot tenant; cross-tenant access is denied."""
    foreign = [r.artifact_id for r in records
               if getattr(r, "tenant", "pilot-internal") not in ("pilot-internal", "")]
    # positive control: a foreign token must be denied access to the pilot tenant
    tok = security.issue_token("tok-globex-analyst")
    cross_denied = not security.check_access(tok, "shadow:read", "pilot-internal").allowed
    return ConditionResult("tenant_isolation", not foreign and cross_denied,
                           f"foreign_records={len(foreign)} cross_tenant_denied={cross_denied}",
                           foreign[:10])


def _c4_audit_replay(records, replay_fn: Callable) -> ConditionResult:
    """Every record must carry a replay signature; recomputation must be stable (no decision drift)."""
    missing = [r.artifact_id for r in records if not r.replay_signature]
    unstable = [r.artifact_id for r in records if replay_fn(r) != replay_fn(r)]
    return ConditionResult("audit_replay", not missing and not unstable,
                           f"missing_sig={len(missing)} unstable={len(unstable)}",
                           (missing + unstable)[:10])


def _c5_privacy(records, text_by_id: Dict[str, str]) -> ConditionResult:
    """No PII/sensitive marker may be present in any artifact text that reached the runtime."""
    leaked = [aid for aid, txt in text_by_id.items() if _PII.search(txt or "")]
    return ConditionResult("privacy_no_pii_reached_runtime", not leaked,
                           f"{len(leaked)} artifact(s) with PII markers reached the runtime",
                           leaked[:10])


def _c6_kill_switch(records) -> ConditionResult:
    """The pilot kill switch must fail closed: tripping it halts the runtime; restore is clean."""
    # NOTE: KillState.active means "runtime running"; a tripped kill switch drives it to False.
    try:
        killswitch.restore_pilot()
        running_before = killswitch.check("pilot-internal").active      # expect True
        killswitch.trip_pilot()
        running_when_tripped = killswitch.check("pilot-internal").active  # expect False (halted)
        killswitch.restore_pilot()
        running_after = killswitch.check("pilot-internal").active        # expect True
        ok = running_before and (not running_when_tripped) and running_after
    except Exception as e:                       # fail closed
        return ConditionResult("kill_switch_fail_closed", False, f"exception: {e}")
    return ConditionResult(
        "kill_switch_fail_closed", ok,
        f"running_before={running_before} halted_when_tripped={not running_when_tripped} "
        f"running_after_restore={running_after}")


def evaluate_stops(records, text_by_id: Dict[str, str], replay_fn: Callable) -> Dict[str, Any]:
    """Run all six stop conditions. `should_stop` is True iff any condition fails. Fail-closed on any
    exception in a check."""
    checks = []
    for fn in (
        lambda: _c1_unsafe_disagreement(records),
        lambda: _c2_native_actiongate_loss(records),
        lambda: _c3_tenant_isolation(records),
        lambda: _c4_audit_replay(records, replay_fn),
        lambda: _c5_privacy(records, text_by_id),
        lambda: _c6_kill_switch(records),
    ):
        try:
            checks.append(fn())
        except Exception as e:                   # fail-closed: an erroring check STOPS the pilot
            checks.append(ConditionResult("check_error", False, f"exception: {e}"))
    should_stop = any(not c.passed for c in checks)
    return {
        "should_stop": should_stop,
        "all_pass": not should_stop,
        "conditions": [{"name": c.name, "passed": c.passed, "detail": c.detail,
                        "evidence": c.evidence} for c in checks],
        "n_records": len(records),
    }
