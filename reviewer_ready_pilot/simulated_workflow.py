"""Phase 18 - Simulated workflow test (SIMULATED_WORKFLOW_ONLY).

Exercises the ENTIRE reviewer-ready apparatus end-to-end - assignment -> blinded Stage A -> reveal ->
Stage B -> audit -> metrics -> adjudication -> stop conditions - using MOCK reviewers, to prove the wiring
works before any real reviewer arrives.

THIS IS NOT HUMAN VALIDATION. Every synthesized reviewer is flagged `is_mock=True`; every record produced
here carries `is_mock=True`; the run is stamped `mode=SIMULATED_WORKFLOW_ONLY`. The metrics module excludes
mock records, so a simulated run can NEVER produce a human-agreement number. The mock "judgments" are
mechanical stand-ins (they echo the frozen system obligation) chosen only to drive the plumbing; they say
nothing about whether a human would agree with the policy.

Deterministic, stdlib-only aside from the frozen components consumed read-only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from reviewer_ready_pilot import assignment as asg
from reviewer_ready_pilot import audit as audit_mod
from reviewer_ready_pilot import metrics as metrics_mod
from reviewer_ready_pilot import adjudication as adj
from reviewer_ready_pilot import policy_runner as pr
from reviewer_ready_pilot import schema
from reviewer_ready_pilot import stop_conditions as sc
from reviewer_ready_pilot.qualification import short_level
from reviewer_ready_pilot.review_interface import BlindedReviewSession

MODE = "SIMULATED_WORKFLOW_ONLY"

_RISK_TO_FLOOR = {"low": "E1", "medium": "E2", "high": "E3", "critical": "E4", "unknown": "ER"}


def _mock_stage_a(artifact: Dict[str, Any], system: pr.SystemResult, perturb: int) -> schema.StageALabel:
    """A mechanical stand-in judgment. Echoes the frozen obligation, with a deterministic perturbation on
    some reviewers so the simulation exercises the disagreement/adjudication path. NOT a human judgment."""
    ob = short_level(system.final_obligation) or "ER"
    risk = artifact.get("risk_tier", "unknown")
    trap = artifact.get("trap_type", "none")
    action = system.action_present
    # perturb every 5th (reviewer,artifact) upward by one safe level to create some disagreement
    order = ["E0", "E1", "E2", "E3", "E4", "ER"]
    if perturb % 5 == 0 and ob in order and order.index(ob) < 5:
        ob = order[order.index(ob) + 1]
    if risk in ("high", "critical") and ob == "E0":
        ob = "E3"
    return schema.StageALabel(
        obligation=ob, risk_tier=risk if risk in _RISK_TO_FLOOR else "unknown",
        source_authority="unknown", obligation_satisfied=not system.review_required,
        action_present=action, action_requires_approval=action if action else None,
        trap_detected=trap if trap != "none" else "none", confidence=0.6, review_time_seconds=30.0,
        reason="simulated mechanical stand-in")


def _mock_stage_b(system: pr.SystemResult, stage_a: schema.StageALabel) -> schema.StageBLabel:
    sys_ob = short_level(system.final_obligation)
    agree = stage_a.obligation == sys_ob
    override = not agree and stage_a.obligation in ("E4", "ER")  # only override stricter, with reason
    return schema.StageBLabel(
        obligation=stage_a.obligation, agreement=agree, override=override,
        override_direction="stricter" if override else "none",
        override_reason="simulated stricter override" if override else "",
        acceptable_actiongate_outcome=(system.native_actiongate_outcome or "not_applicable"),
        explanation_useful=4, trace_comprehensible=True, missing_context=False, confidence=0.6,
        review_time_seconds=20.0, reason="simulated")


def run(final_items: List[Dict[str, Any]], *, n_reviewers: int = 4,
        reviewers_per_artifact: int = 2, limit: Optional[int] = None) -> Dict[str, Any]:
    """Drive the whole pipeline with mock reviewers. Returns a report stamped SIMULATED_WORKFLOW_ONLY."""
    items = sorted(final_items, key=lambda a: a["artifact_id"])
    if limit:
        items = items[:limit]

    roster = [asg.Reviewer(f"REV-{chr(65 + i)}", roles={"technical", "policy", "domain"}, is_mock=True)
              for i in range(n_reviewers)]
    plan = asg.assign(items, roster, reviewers_per_artifact=reviewers_per_artifact)

    log = audit_mod.AuditLog()
    records: List[Dict[str, Any]] = []
    system_results: Dict[str, Dict[str, Any]] = {}
    art_by_id = {a["artifact_id"]: a for a in items}
    ts = 0

    for a in plan.assignments:
        art = art_by_id[a.artifact_id]
        system = pr.run(art)
        sysd = system.as_dict()
        if art.get("trap_type"):
            sysd["expected_trap"] = art["trap_type"]
        system_results[a.artifact_id] = sysd
        for k, rid in enumerate(a.reviewer_ids):
            sess = BlindedReviewSession(rid, art, is_mock=True)
            log.assigned(ts, rid, "technical", a.artifact_id); ts += 1
            # deterministic perturbation index = running record count (no Date/random needed)
            sa = _mock_stage_a(art, system, perturb=len(records))
            sess.submit_stage_a(sa)
            log.stage_a(ts, rid, "technical", a.artifact_id, schema.stage_a_dict(sa)); ts += 1
            sess.reveal(pr.reveal_view(system))
            log.revealed(ts, rid, "technical", a.artifact_id, pr.reveal_view(system)); ts += 1
            sb = _mock_stage_b(system, sa)
            rec = sess.submit_stage_b(sb)
            log.stage_b(ts, rid, "technical", a.artifact_id, schema.stage_b_dict(sb)); ts += 1
            records.append(rec.as_dict())

    audit_report = audit_mod.verify(log)
    # metrics: because every record is_mock, this MUST come back NOT_ENOUGH_HUMAN_EVIDENCE
    real_metrics = metrics_mod.compute(records, system_results)
    disputes = adj.summarize(records)
    stop = sc.evaluate({}, real_metrics)

    return {
        "mode": MODE,
        "is_human_validation": False,
        "n_mock_reviewers": n_reviewers,
        "artifacts": len(items),
        "records_produced": len(records),
        "all_records_mock": all(r["is_mock"] for r in records),
        "audit": audit_report,
        "metrics_on_real_records": real_metrics,           # NOT_ENOUGH_HUMAN_EVIDENCE by construction
        "adjudication": disputes,
        "stop": stop.as_dict(),
        "note": "SIMULATED_WORKFLOW_ONLY. Mock reviewers exercise the plumbing. No human agreement or "
                "usability is measured or claimed. Metrics on real records are NOT_ENOUGH_HUMAN_EVIDENCE.",
    }


if __name__ == "__main__":
    from reviewer_ready_pilot import dataset
    rep = run(dataset.load_final(), limit=40)
    print(f"mode={rep['mode']} artifacts={rep['artifacts']} records={rep['records_produced']} "
          f"all_mock={rep['all_records_mock']}")
    print(f"audit workflow_ok={rep['audit']['workflow_ok']} chain_ok={rep['audit']['chain_ok']}")
    print(f"metrics status={rep['metrics_on_real_records']['status']}")
    print(f"stop should_stop={rep['stop']['should_stop']}")
