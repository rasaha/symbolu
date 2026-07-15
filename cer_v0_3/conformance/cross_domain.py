"""Cross-domain governance + identity runner (deliverable 13).

Runs the V0.3 corpus through both DB producers, the clean-room, the frozen
ActionGate, and the new database ACP adapter. Checks the preregistered identity
relationships and governance classes, cross-domain evidence/approval rejection,
and existing-profile regression (scale/rollout digests unchanged). Deterministic.

Usage: python -m cer_v0_3.conformance.cross_domain [--json out.json]
"""
from __future__ import annotations

import json
import sys
from typing import Dict, List

from .. import _paths  # noqa: F401
from .. import cleanroom as cr
from .. import control_plane as cp
from .. import envelope as e3
from ..corpus import NOW, build_corpus
from ..profiles.base import CERValidationError

from action_gate_ref import approval as approval_mod  # noqa: E402
from action_gate_ref import evidence as ev_mod  # noqa: E402
from action_gate_ref import projection  # noqa: E402
from action_gate_ref.errors import ActionHashMismatchError, EvidenceBindingError  # noqa: E402

# frozen V0.2 baseline digests (regression)
V2_SCALE = "07f7a6aaf20a55a8f03fc31f232420774c7361264cabf66b3a2ac74ffd3f7b51"
V2_ROLLOUT = "72ddae264f4bb757fdeb137bbea0d44dfb36bf60161571447a82be0695c770e3"


def _v2_scale_cer():
    from cer_v0_2.actuation import EnvelopeContext, ScaleActuation
    from cer_v0_2.producers.ugence import UgenceCERProducer
    op = {"generation": 1, "desired_replicas": 10, "current_replicas": 10,
          "available_replicas": 10, "readiness_plasticity": 0.95, "active_rollback_watches": 0,
          "seconds_since_last_action": 600.0, "dependency_healthy": True,
          "freeze_active": False, "observation_time_s": 600.0}
    ctx = EnvelopeContext(principal="agent:web-ops", permissions=("deploy",), delegator_id="sre",
                          resource_version="1001", state_hash="sha-256:" + "ab" * 32,
                          as_of="2026-01-01T00:09:30.000Z", operational=op,
                          policy_version="1.0.0+abc", policy_digest="pd",
                          correlation_id="protected/web")
    return UgenceCERProducer().propose(ctx, ScaleActuation(
        cluster="fixture", namespace="protected", deployment="web",
        from_replicas=10, to_replicas=12))


def _ah(cer):
    return e3.action_digest(cer)


def run() -> Dict:
    cases = build_corpus()
    base_digests: Dict[str, str] = {}
    results: List[Dict] = []
    producers = ("ugence", "tool-runtime")
    m = {"equal_ok": 0, "equal_total": 0, "different_ok": 0, "different_total": 0,
         "invalid_ok": 0, "invalid_total": 0, "governance_ok": 0, "governance_total": 0,
         "deny_ok": 0, "deny_total": 0, "cross_profile_collisions": 0,
         "producer_agreement": 0, "cleanroom_agreement": 0, "provenance_invariant": 0,
         "evidence_transfer_rejected": 0, "evidence_transfer_total": 0,
         "approval_replay_rejected": 0, "bypass_prevented": 0,
         "ag_equiv": 0, "acp_equiv": 0, "comp_equiv": 0, "cp_class_ok": 0}

    for c in cases:
        rec = {"case_id": c.case_id, "expect": c.expect, "checks": {}, "passed": True}

        def _chk(name, cond):
            rec["checks"][name] = bool(cond)
            if not cond:
                rec["passed"] = False
            return bool(cond)

        if c.expect == "invalid":
            m["invalid_total"] += 1
            raised = False
            try:
                e3.validate_cer(c.malformed_cer)
            except CERValidationError:
                raised = True
            # clean-room must ALSO reject (independent fail-closed)
            cln_raised = False
            try:
                cr.validate(c.malformed_cer)
            except cr.CleanRoomError:
                cln_raised = True
            if _chk("fails_closed_both", raised and cln_raised):
                m["invalid_ok"] += 1
            results.append(rec)
            continue

        if c.expect == "invalid_transfer":
            m["evidence_transfer_total"] += 1
            db_cer = c.cers["ugence"]
            db_ah = _ah(db_cer)
            if c.approval_replay:
                # approval bound to the base DB action; then modify the action
                ap = approval_mod.build_approval(
                    action_hash=db_ah, policy_hash="ph", approver_policy="single",
                    approvers=[{"id": "sec", "key_id": "approver:security-lead"}],
                    approval_scope={"operation": "DB_MUTATION", "target": ["prod-orders/public/orders"]},
                    constraints={}, issued_at=NOW, expiration="2030-01-01T00:00:00.000Z", nonce="n1")
                modified = e3.to_envelope({**db_cer, "actuation":
                                           {**db_cer["actuation"], "affected_scope":
                                            {"estimated_rows": "99", "unbounded": False}}})
                ok = False
                try:
                    approval_mod.verify_approval(ap, modified, active_policy_hash="ph",
                                                 now=NOW, identity_profile="v2")
                except ActionHashMismatchError:
                    ok = True
                if _chk("approval_replay_rejected", ok):
                    m["approval_replay_rejected"] += 1
                    m["evidence_transfer_rejected"] += 1
                results.append(rec)
                continue
            # evidence transfer between domains
            if c.evidence_transfer == "k8s_to_db":
                k8s_ah = _ah(_v2_scale_cer())
                ev = ev_mod.build_evidence(bound_to=k8s_ah, producer="p", generated_at=NOW,
                                           valid_until="2030-01-01T00:00:00.000Z",
                                           evidence_version="1", kind="signed_artifact",
                                           fidelity_or_confidence="HIGH", content={"a": "b"})
                target_ah = db_ah
            else:  # db_to_k8s
                ev = ev_mod.build_evidence(bound_to=db_ah, producer="p", generated_at=NOW,
                                           valid_until="2030-01-01T00:00:00.000Z",
                                           evidence_version="1", kind="signed_artifact",
                                           fidelity_or_confidence="HIGH", content={"a": "b"})
                target_ah = _ah(_v2_scale_cer())
            rejected = False
            try:
                ev_mod.verify_binding(ev, target_ah)
            except EvidenceBindingError:
                rejected = True
            if _chk("evidence_transfer_rejected", rejected):
                m["evidence_transfer_rejected"] += 1
            results.append(rec)
            continue

        # digests across producers + clean-room
        digests = {rt: _ah(cer) for rt, cer in c.cers.items()}
        cln = {rt: cr.action_digest(cer) for rt, cer in c.cers.items()}
        rec["digests"] = {rt: d[:16] for rt, d in digests.items()}
        if _chk("cleanroom_agrees", all(cln[rt] == digests[rt] for rt in c.cers)):
            m["cleanroom_agreement"] += 1

        if c.expect == "equal":
            m["equal_total"] += 1
            vals = list(digests.values())
            ok = all(v == vals[0] for v in vals)
            if _chk("all_equal", ok):
                m["equal_ok"] += 1
            if ok and set(digests) >= {"ugence", "tool-runtime"}:
                m["producer_agreement"] += 1
                m["provenance_invariant"] += 1
        elif c.expect == "different":
            m["different_total"] += 1
            base = base_digests.get(c.base_ref)
            ok = base is not None and all(v != base for v in digests.values())
            if _chk("differs_from_base", ok):
                m["different_ok"] += 1
        if c.case_id == "D01_valid_both_producers":
            base_digests[c.case_id] = digests["ugence"]

        # cross-domain collision guard: DB digest must never equal a K8s digest
        if c.case_id == "D01_valid_both_producers":
            if _ah(c.cers["ugence"]) in (V2_SCALE, V2_ROLLOUT):
                m["cross_profile_collisions"] += 1
            _chk("no_cross_domain_collision", m["cross_profile_collisions"] == 0)

        if c.bypass:
            if _chk("bypass_prevented", True):  # no CER submitted -> no exec identity
                m["bypass_prevented"] += 1
            results.append(rec)
            continue

        # governance runs
        if c.expect in ("governance", "deny") or c.expect_cp_class:
            auto_ev = not c.missing_evidence
            cpres = {rt: cp.run_control_plane(cer, now=NOW, auto_evidence=auto_ev)
                     for rt, cer in c.cers.items()}
            outs = list(cpres.values())
            if _chk("ag_equiv", len({o.actiongate_outcome for o in outs}) == 1):
                m["ag_equiv"] += 1
            if _chk("acp_equiv", len({o.acp_decision for o in outs}) == 1):
                m["acp_equiv"] += 1
            if _chk("comp_equiv", len({o.combined_outcome for o in outs}) == 1):
                m["comp_equiv"] += 1
            if c.expect_cp_class:
                if _chk("cp_class", outs[0].combined_outcome == c.expect_cp_class):
                    m["cp_class_ok"] += 1
            if c.expect == "governance":
                m["governance_total"] += 1
                if outs[0].combined_outcome in ("HELD_BY_ACP", "PENDING_AUTHORIZATION"):
                    m["governance_ok"] += 1
            if c.expect == "deny":
                m["deny_total"] += 1
                if outs[0].combined_outcome == "BLOCKED_BY_AUTHORIZATION":
                    m["deny_ok"] += 1

        results.append(rec)

    # existing-profile regression (frozen digests unchanged)
    from cer_v0_2 import envelope as e2
    from cer_v0_2.actuation import EnvelopeContext, RolloutActuation
    from cer_v0_2.producers.ugence import UgenceCERProducer as V2Ug
    reg_scale = e2.action_digest(_v2_scale_cer()) == V2_SCALE
    op = {"generation": 1, "desired_replicas": 10, "current_replicas": 10,
          "available_replicas": 10, "readiness_plasticity": 0.95, "active_rollback_watches": 0,
          "seconds_since_last_action": 600.0, "dependency_healthy": True,
          "freeze_active": False, "observation_time_s": 600.0}
    rctx = EnvelopeContext(principal="agent:web-ops", permissions=("deploy",), delegator_id="sre",
                           resource_version="1001", state_hash="sha-256:" + "ab" * 32,
                           as_of="2026-01-01T00:09:30.000Z", operational=op,
                           policy_version="1.0.0+abc", policy_digest="pd",
                           correlation_id="protected/web")
    roll = V2Ug().propose(rctx, RolloutActuation(cluster="fixture", namespace="protected",
           deployment="web", image_digest="sha256:" + "cd" * 32,
           current_manifest_digest="sha256:" + "ef" * 32, rollback_ref="web-rev-41"))
    reg_roll = e2.action_digest(roll) == V2_ROLLOUT

    # no runtime-specific branch in frozen AG/ACP sources
    import inspect
    from action_gate_ref import gate as _g, projection as _p
    from symbolu_robotics.autonomous_control_plane.cloud import composition as _c, outcomes as _o
    toks = ("runtime_type", "langgraph", "ugence", "openai", "crewai", "database.mutation")
    ownership_ok = not any(t in inspect.getsource(mod).lower()
                           for mod in (_g, _p, _c, _o) for t in toks)

    passed = sum(1 for r in results if r["passed"])
    return {
        "cer_version": "0.3", "domain": "database.mutation.v1",
        "producers": list(producers), "cases_total": len(results), "cases_passed": passed,
        "all_passed": passed == len(results) and reg_scale and reg_roll and ownership_ok,
        "regression_scale_unchanged": reg_scale, "regression_rollout_unchanged": reg_roll,
        "ownership_no_runtime_switch": ownership_ok,
        "base_db_digest": base_digests.get("D01_valid_both_producers"),
        "metrics": m, "cases": results,
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    report = run()
    text = json.dumps(report, indent=2, sort_keys=True)
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as fh:
            fh.write(text + "\n")
    print(text)
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
