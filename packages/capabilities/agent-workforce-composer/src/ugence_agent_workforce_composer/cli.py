"""Offline, deterministic CLI for the Agent Workforce Composer.

    ugence-agent-workforce-composer version
    ugence-agent-workforce-composer validate-workflow <file.json>
    ugence-agent-workforce-composer adapt-workflow   <file.json>
    ugence-agent-workforce-composer validate-registry <file.json>
    ugence-agent-workforce-composer validate-policy   <enterprise.json> <eligibility.json>
    ugence-agent-workforce-composer eligibility <workflow.json> <registry.json> <enterprise.json> <eligibility.json>
    ugence-agent-workforce-composer explain <workflow.json> <registry.json> <enterprise.json> <eligibility.json>
    ugence-agent-workforce-composer replay  <workflow.json> <registry.json> <enterprise.json> <eligibility.json>
    ugence-agent-workforce-composer demo {procurement|support|security}

No network, no live registry, no provider calls, no execution. Every command
prints canonical JSON to stdout and exits 0 on success, non-zero on failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .adapter import adapt_compiled_workflow
from .agents import (
    AgentCapabilityEvidence,
    AgentProfile,
    build_registry_snapshot,
)
from .canonical import canonical_json, to_canonical_obj
from .eligibility import evaluate_workflow_eligibility
from .policy import (
    EligibilityPolicy,
    EnterpriseAgentPolicy,
    finalize_eligibility_policy,
    finalize_enterprise_policy,
)
from .workflow import Provenance
from . import fixtures
from .fixtures import LOGICAL_TIME
from .version import version_info


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _emit(obj) -> None:
    print(canonical_json(obj))


def _load_registry(doc) -> "object":
    prov = Provenance(source_kind="cli_input", synthetic=bool(doc.get("synthetic", True)))
    profiles = [AgentProfile.model_validate(p) for p in doc.get("agent_profiles", [])]
    evidence = [AgentCapabilityEvidence.model_validate(e) for e in doc.get("capability_evidence", [])]
    return build_registry_snapshot(
        snapshot_id=doc.get("snapshot_id", "cli_registry"),
        registry_version=doc.get("registry_version", "cli.v1"),
        logical_time=float(doc.get("logical_time", LOGICAL_TIME)),
        agent_profiles=profiles, capability_evidence=evidence, provenance=prov,
        source_refs=tuple(doc.get("source_refs", ())))


def _load_policies(ent_doc, elig_doc):
    enterprise = finalize_enterprise_policy(EnterpriseAgentPolicy.model_validate(ent_doc))
    eligibility = finalize_eligibility_policy(EligibilityPolicy.model_validate(elig_doc))
    return enterprise, eligibility


def cmd_version(_args) -> int:
    _emit(version_info().to_dict())
    return 0


def cmd_validate_workflow(args) -> int:
    result = adapt_compiled_workflow(_read_json(args.file), role_overlay=None)
    _emit({"ok": result.ok, "workflow_identity": result.workflow_identity,
           "node_count": len(result.node_dispositions),
           "role_count": len(result.role_requirements),
           "non_agent_count": len(result.non_agent_dispositions),
           "accounting_holds": result.accounting_holds(),
           "diagnostics": [to_canonical_obj(d) for d in result.diagnostics]})
    return 0 if result.ok and result.accounting_holds() else 1


def cmd_adapt_workflow(args) -> int:
    result = adapt_compiled_workflow(_read_json(args.file), role_overlay=None)
    _emit(to_canonical_obj(result))
    return 0 if result.ok else 1


def cmd_validate_registry(args) -> int:
    try:
        snap = _load_registry(_read_json(args.file))
    except Exception as exc:  # deterministic structured failure
        _emit({"ok": False, "error": type(exc).__name__, "detail": str(exc)})
        return 1
    _emit({"ok": True, "snapshot_id": snap.snapshot_id,
           "agent_count": len(snap.agent_profiles),
           "evidence_count": len(snap.capability_evidence),
           "snapshot_digest": snap.snapshot_digest,
           "digest_matches": snap.snapshot_digest == snap.logical_digest()})
    return 0


def cmd_validate_policy(args) -> int:
    try:
        enterprise, eligibility = _load_policies(_read_json(args.enterprise), _read_json(args.eligibility))
    except Exception as exc:
        _emit({"ok": False, "error": type(exc).__name__, "detail": str(exc)})
        return 1
    _emit({"ok": True, "enterprise_policy_digest": enterprise.policy_digest,
           "eligibility_policy_digest": eligibility.policy_digest,
           "evaluation_order": list(eligibility.evaluation_order)})
    return 0


def _run_eligibility(args):
    result = adapt_compiled_workflow(_read_json(args.workflow), role_overlay=None)
    snap = _load_registry(_read_json(args.registry))
    enterprise, eligibility = _load_policies(_read_json(args.enterprise), _read_json(args.eligibility))
    return result, evaluate_workflow_eligibility(result, snap, enterprise, eligibility,
                                                 float(getattr(args, "time", LOGICAL_TIME)))


def cmd_eligibility(args) -> int:
    _adapt, result = _run_eligibility(args)
    _emit(to_canonical_obj(result))
    return 0


def cmd_explain(args) -> int:
    _adapt, result = _run_eligibility(args)
    _emit({"workflow_identity": result.workflow_identity,
           "explanations": [to_canonical_obj(e) for e in result.explanations]})
    return 0


def cmd_replay(args) -> int:
    _adapt, result = _run_eligibility(args)
    _emit({"workflow_identity": result.workflow_identity,
           "workflow_fingerprint": result.workflow_fingerprint,
           "replay_records": [to_canonical_obj(r) for r in result.replay_records]})
    return 0


def _p2_inputs(args):
    adaptation = adapt_compiled_workflow(_read_json(args.workflow), role_overlay=fixtures.role_overlay())
    snap = _load_registry(_read_json(args.registry))
    enterprise, eligibility = _load_policies(_read_json(args.enterprise), _read_json(args.eligibility))
    return adaptation, snap, enterprise, eligibility


def cmd_rank(args) -> int:
    from .ranking import rank_workflow_candidates
    adaptation, snap, enterprise, eligibility = _p2_inputs(args)
    rankings = rank_workflow_candidates(adaptation, snap, enterprise, eligibility,
                                        fixtures.ranking_policy(), float(args.time))
    _emit([to_canonical_obj(r) for r in rankings])
    return 0


def _build_plan(args):
    from .plan import build_agent_team_plan
    adaptation, snap, enterprise, eligibility = _p2_inputs(args)
    plan = build_agent_team_plan(
        adaptation, snap, enterprise, eligibility, fixtures.ranking_policy(),
        fixtures.team_composition_policy(), fixtures.permission_policy(),
        fixtures.fallback_policy(), float(args.time))
    return adaptation, plan


def cmd_compose(args) -> int:
    _adapt, plan = _build_plan(args)
    _emit(to_canonical_obj(plan))
    return 0


def cmd_explain_plan(args) -> int:
    _adapt, plan = _build_plan(args)
    _emit(to_canonical_obj(plan.selection_explanation))
    return 0


def cmd_replay_plan(args) -> int:
    from .plan import build_replay_record, replay_agent_team_plan
    adaptation, plan = _build_plan(args)
    replay = replay_agent_team_plan(
        adaptation, _load_registry(_read_json(args.registry)),
        *_load_policies(_read_json(args.enterprise), _read_json(args.eligibility)),
        fixtures.ranking_policy(), fixtures.team_composition_policy(),
        fixtures.permission_policy(), fixtures.fallback_policy(), float(args.time),
        expected=plan)
    rec = build_replay_record(plan, adaptation, float(args.time),
                              ("awc.v1", "workflow_ir.v1", "awc.composition.v1"))
    _emit({"reproduced": replay.plan_fingerprint == plan.plan_fingerprint,
           "plan_fingerprint": plan.plan_fingerprint, "replay_record": to_canonical_obj(rec)})
    return 0 if replay.plan_fingerprint == plan.plan_fingerprint else 1


def cmd_compare_plans(args) -> int:
    from .plan import AgentTeamPlan, compare_agent_team_plans
    a = AgentTeamPlan.model_validate(_read_json(args.plan_a))
    b = AgentTeamPlan.model_validate(_read_json(args.plan_b))
    _emit(to_canonical_obj(compare_agent_team_plans(a, b)))
    return 0


def cmd_demo(args) -> int:
    if getattr(args, "compose", False):
        adaptation, plan = fixtures.run_compose_demo(args.workflow)
        _emit({
            "workflow": args.workflow, "plan_state": plan.plan_state.value,
            "total_team_score": plan.total_team_score,
            "optimality_status": plan.search_statistics.optimality_status.value,
            "plan_fingerprint": plan.plan_fingerprint,
            "assignments": [{"role_id": a.role_id,
                             "primary": f"{a.primary_agent_id}@{a.primary_agent_version}",
                             "score": a.total_score} for a in plan.role_assignments],
            "unfilled_roles": list(plan.unfilled_roles),
            "fallbacks": [{"role_id": f.role_id, "state": f.fallback_state.value,
                           "depth": len(f.candidates)} for f in plan.role_fallback_plans],
            "search": to_canonical_obj(plan.search_statistics),
        })
        return 0
    adaptation, result = fixtures.run_demo(args.workflow)
    summary = {
        "workflow": args.workflow,
        "workflow_identity": adaptation.workflow_identity,
        "accounting_holds": adaptation.accounting_holds(),
        "adaptation_fingerprint": adaptation.adaptation_fingerprint,
        "workflow_fingerprint": result.workflow_fingerprint,
        "node_dispositions": [
            {"node_id": nd.node_id, "kind": nd.source_node_kind.value,
             "disposition": nd.disposition.value} for nd in adaptation.node_dispositions],
        "roles": [
            {"role_id": r.role_id, "role_name": rep.role_id and r.role_name,
             "outcome": rep.outcome, "eligible": list(rep.eligible_agent_ids),
             "eliminated": len(rep.eliminated_agent_ids)}
            for r, rep in zip(sorted(adaptation.role_requirements, key=lambda x: x.role_id),
                              result.reports)],
    }
    _emit(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ugence-agent-workforce-composer",
        description="Offline, deterministic agent workflow-role adaptation and hard-constraint eligibility (P1).")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="print version + maturity metadata").set_defaults(func=cmd_version)

    vw = sub.add_parser("validate-workflow", help="adapt a serialized workflow and check accounting")
    vw.add_argument("file")
    vw.set_defaults(func=cmd_validate_workflow)

    aw = sub.add_parser("adapt-workflow", help="emit the full adaptation result")
    aw.add_argument("file")
    aw.set_defaults(func=cmd_adapt_workflow)

    vr = sub.add_parser("validate-registry", help="validate a serialized registry snapshot")
    vr.add_argument("file")
    vr.set_defaults(func=cmd_validate_registry)

    vp = sub.add_parser("validate-policy", help="validate enterprise + eligibility policies")
    vp.add_argument("enterprise")
    vp.add_argument("eligibility")
    vp.set_defaults(func=cmd_validate_policy)

    for name, fn, helptext in (
        ("eligibility", cmd_eligibility, "evaluate every role x agent pair"),
        ("explain", cmd_explain, "emit deterministic eligibility explanations"),
        ("replay", cmd_replay, "emit deterministic replay records"),
    ):
        c = sub.add_parser(name, help=helptext)
        c.add_argument("workflow")
        c.add_argument("registry")
        c.add_argument("enterprise")
        c.add_argument("eligibility")
        c.add_argument("--time", type=float, default=LOGICAL_TIME)
        c.set_defaults(func=fn)

    # -- P2 commands --
    for name, fn, helptext in (
        ("rank", cmd_rank, "rank P1-eligible candidates per role"),
        ("compose", cmd_compose, "compose an AgentTeamPlan (bounded exact search)"),
        ("explain-plan", cmd_explain_plan, "emit the deterministic selection explanation"),
        ("replay-plan", cmd_replay_plan, "rebuild the plan and verify the fingerprint reproduces"),
    ):
        c = sub.add_parser(name, help=helptext)
        c.add_argument("workflow")
        c.add_argument("registry")
        c.add_argument("enterprise")
        c.add_argument("eligibility")
        c.add_argument("--time", type=float, default=LOGICAL_TIME)
        c.set_defaults(func=fn)

    cp = sub.add_parser("compare-plans", help="diff two AgentTeamPlan JSON artifacts")
    cp.add_argument("plan_a")
    cp.add_argument("plan_b")
    cp.set_defaults(func=cmd_compare_plans)

    dm = sub.add_parser("demo", help="run a frozen synthetic demo")
    dm.add_argument("workflow", choices=sorted(fixtures.WORKFLOWS))
    dm.add_argument("--compose", action="store_true", help="run the full P1→P2 composition pipeline")
    dm.set_defaults(func=cmd_demo)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
