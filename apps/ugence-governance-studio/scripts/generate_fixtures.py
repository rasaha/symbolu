"""Generate the committed Governance Studio demo fixtures and frozen expected
outputs from the REAL Agent Workforce Composer engine.

Run from anywhere:

    python apps/ugence-governance-studio/scripts/generate_fixtures.py

For every scenario in :mod:`scenario_authoring` this writes, under
``apps/ugence-governance-studio/``:

* ``demo_data/<scenario>/*.json`` — the ten input fixtures (workflow, overlay,
  registry, six policies, scenario manifest), all in the real AWC schemas.
* ``expected_outputs/<scenario>/*.json`` — the frozen canonical outputs of the
  real P1/P2 pipeline (adaptation, eligibility, ranking, composition, permission
  proposals, fallback plans, AgentTeamPlan, replay record, fingerprints).
* ``expected_outputs/MANIFEST.json`` — sha256 of every input and output file plus
  the AWC package/contract versions and each scenario's plan fingerprint.

The script re-derives every result from the AWC public API and mirrors the exact
internal call sequence of ``build_agent_team_plan`` so the separately serialized
composition/replay artifacts are byte-identical to what the pipeline computes.
It NEVER re-implements any AWC policy logic.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ugence_agent_workforce_composer.api as awc  # noqa: E402
import scenario_authoring as sa  # noqa: E402

DEMO_DATA = os.path.join(_APP, "demo_data")
EXPECTED = os.path.join(_APP, "expected_outputs")
LT = sa.LOGICAL_TIME
CONTRACTS = (awc.CONTRACT_VERSION, awc.COMPOSITION_CONTRACT_VERSION)


# --------------------------------------------------------------------------- #
# canonical, byte-stable JSON serialization
# --------------------------------------------------------------------------- #

def _to_jsonable(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    return obj


def _canonical_bytes(obj) -> bytes:
    text = json.dumps(_to_jsonable(obj), sort_keys=True, indent=2, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def _write(path: str, obj) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = _canonical_bytes(obj)
    with open(path, "wb") as fh:
        fh.write(data)
    return hashlib.sha256(data).hexdigest()


def _rel(path: str) -> str:
    return os.path.relpath(path, _APP)


# --------------------------------------------------------------------------- #
# pipeline (mirrors build_agent_team_plan internals for byte-exact sub-artifacts)
# --------------------------------------------------------------------------- #

def _run_pipeline(s: dict) -> dict:
    workflow, overlay = s["workflow"], s["overlay"]
    reg, ent, elig = s["registry"], s["enterprise_policy"], s["eligibility_policy"]
    rank_p, comp_p = s["ranking_policy"], s["composition_policy"]
    perm_p, fb_p = s["permission_policy"], s["fallback_policy"]

    adaptation = awc.adapt_compiled_workflow(workflow, role_overlay=overlay)
    eligibility = awc.evaluate_workflow_eligibility(adaptation, reg, ent, elig, LT)

    roles = tuple(sorted(adaptation.role_requirements, key=lambda r: r.role_id))
    reports = {r.role_id: awc.evaluate_registry_for_role(r, reg, ent, elig, LT) for r in roles}
    rankings = tuple(awc.rank_eligible_candidates(r, reports[r.role_id], reg, rank_p, LT)
                     for r in roles)
    dep_graph = awc.build_role_dependency_graph(roles)
    composition = awc.compose_agent_team(
        roles, rankings, reg, ent, comp_p, perm_p, dep_graph,
        eligibility_policy_digest=elig.policy_digest,
        ranking_policy_digest=rank_p.policy_digest,
        workflow_fingerprint=adaptation.adaptation_fingerprint)

    plan = awc.build_agent_team_plan(adaptation, reg, ent, elig, rank_p, comp_p, perm_p, fb_p, LT)
    replay = awc.build_replay_record(plan, adaptation, LT, CONTRACTS)
    # Prove the plan replays to an identical fingerprint before we freeze it.
    awc.replay_agent_team_plan(adaptation, reg, ent, elig, rank_p, comp_p, perm_p, fb_p, LT,
                               expected=plan)

    return {
        "adaptation": adaptation,
        "eligibility": eligibility,
        "rankings": rankings,
        "composition": composition,
        "plan": plan,
        "replay": replay,
    }


def _fingerprints(out: dict) -> dict:
    plan = out["plan"]
    return {
        "adaptation_fingerprint": out["adaptation"].adaptation_fingerprint,
        "workflow_eligibility_fingerprint": out["eligibility"].workflow_fingerprint,
        "composition_fingerprint": out["composition"].composition_fingerprint,
        "plan_fingerprint": plan.plan_fingerprint,
        "plan_id": plan.plan_id,
        "plan_state": plan.plan_state.value,
        "replay_fingerprint": out["replay"].replay_fingerprint,
        "expected_plan_fingerprint": out["replay"].expected_plan_fingerprint,
    }


# --------------------------------------------------------------------------- #
# scenario manifest (input side)
# --------------------------------------------------------------------------- #

_DEMONSTRATION = {
    "procurement": {
        "headline": "non-greedy team selection under provider concentration",
        "expected_plan_state": "COMPLETE",
        "shows_non_greedy_selection": True,
        "shows_no_feasible_team": False,
        "shows_no_fallback_available": True,
    },
    "customer_support": {
        "headline": "clean feasible support team; cyber specialist eliminated, not mis-assigned",
        "expected_plan_state": "COMPLETE",
        "shows_non_greedy_selection": False,
        "shows_no_feasible_team": False,
        "shows_no_fallback_available": False,
    },
    "cybersecurity_success": {
        "headline": "feasible incident-response team; single-holder roles have no fallback",
        "expected_plan_state": "COMPLETE",
        "shows_non_greedy_selection": False,
        "shows_no_feasible_team": False,
        "shows_no_fallback_available": True,
    },
    "cybersecurity_no_feasible_team": {
        "headline": "NO_FEASIBLE_TEAM: only one approved provider is cleared to level 4",
        "expected_plan_state": "NO_FEASIBLE_TEAM",
        "shows_non_greedy_selection": False,
        "shows_no_feasible_team": True,
        "shows_no_fallback_available": False,
    },
}

_INPUT_FILES = [
    ("compiled_workflow.json", "workflow"),
    ("enterprise_role_overlay.json", "overlay"),
    ("agent_registry_snapshot.json", "registry"),
    ("enterprise_agent_policy.json", "enterprise_policy"),
    ("eligibility_policy.json", "eligibility_policy"),
    ("ranking_policy.json", "ranking_policy"),
    ("composition_policy.json", "composition_policy"),
    ("permission_policy.json", "permission_policy"),
    ("fallback_policy.json", "fallback_policy"),
]

_OUTPUT_ARTIFACTS = [
    ("adaptation.json", "adaptation"),
    ("eligibility.json", "eligibility"),
    ("ranking.json", "rankings"),
    ("composition.json", "composition"),
    ("agent_team_plan.json", "plan"),
    ("replay_record.json", "replay"),
]


def generate() -> dict:
    manifest = {
        "schema": "governance_studio.fixture_manifest.v1",
        "synthetic": True,
        "logical_time": LT,
        "awc_package": "ugence-agent-workforce-composer",
        "awc_version": awc.__version__,
        "awc_contract_version": awc.CONTRACT_VERSION,
        "awc_composition_contract_version": awc.COMPOSITION_CONTRACT_VERSION,
        "scenario_order": list(sa.SCENARIO_ORDER),
        "scenarios": {},
        "inputs": {},
        "outputs": {},
    }

    for sid in sa.SCENARIO_ORDER:
        s = sa.build_scenario(sid)
        out = _run_pipeline(s)
        fps = _fingerprints(out)

        # -- inputs --
        input_hashes = {}
        for fname, key in _INPUT_FILES:
            path = os.path.join(DEMO_DATA, sid, fname)
            input_hashes[fname] = _write(path, s[key])
            manifest["inputs"][_rel(path)] = input_hashes[fname]

        # -- outputs --
        output_hashes = {}
        # ranking is a tuple -> serialize as a list of models
        serializable = dict(out)
        serializable["rankings"] = [r for r in out["rankings"]]
        for fname, key in _OUTPUT_ARTIFACTS:
            path = os.path.join(EXPECTED, sid, fname)
            output_hashes[fname] = _write(path, serializable[key])
            manifest["outputs"][_rel(path)] = output_hashes[fname]
        # fingerprints artifact
        fp_path = os.path.join(EXPECTED, sid, "fingerprints.json")
        output_hashes["fingerprints.json"] = _write(fp_path, fps)
        manifest["outputs"][_rel(fp_path)] = output_hashes["fingerprints.json"]

        # -- per-scenario input manifest (the required scenario_manifest.json) --
        scenario_manifest = {
            "schema": "governance_studio.scenario_manifest.v1",
            "scenario_id": sid,
            "synthetic": True,
            "logical_time": LT,
            "awc_version": awc.__version__,
            "awc_contract_version": awc.CONTRACT_VERSION,
            "awc_composition_contract_version": awc.COMPOSITION_CONTRACT_VERSION,
            "demonstration": _DEMONSTRATION[sid],
            "digests": {
                "workflow_adaptation_fingerprint": out["adaptation"].adaptation_fingerprint,
                "registry_snapshot_digest": s["registry"].snapshot_digest,
                "enterprise_policy_digest": s["enterprise_policy"].policy_digest,
                "eligibility_policy_digest": s["eligibility_policy"].policy_digest,
                "ranking_policy_digest": s["ranking_policy"].policy_digest,
                "composition_policy_digest": s["composition_policy"].policy_digest,
                "permission_policy_digest": s["permission_policy"].policy_digest,
                "fallback_policy_digest": s["fallback_policy"].policy_digest,
            },
            "expected_fingerprints": fps,
            "input_files": input_hashes,
            "expected_output_files": output_hashes,
        }
        sm_path = os.path.join(DEMO_DATA, sid, "scenario_manifest.json")
        sm_hash = _write(sm_path, scenario_manifest)
        manifest["inputs"][_rel(sm_path)] = sm_hash

        manifest["scenarios"][sid] = {
            "plan_state": fps["plan_state"],
            "plan_fingerprint": fps["plan_fingerprint"],
            "demonstration": _DEMONSTRATION[sid],
        }
        print(f"  {sid}: {fps['plan_state']}  plan={fps['plan_fingerprint']}")

    manifest_path = os.path.join(EXPECTED, "MANIFEST.json")
    _write(manifest_path, manifest)
    print(f"wrote manifest -> {_rel(manifest_path)} "
          f"({len(manifest['inputs'])} inputs, {len(manifest['outputs'])} outputs)")
    return manifest


if __name__ == "__main__":
    print(f"Generating Governance Studio fixtures with AWC {awc.__version__} "
          f"({awc.CONTRACT_VERSION} / {awc.COMPOSITION_CONTRACT_VERSION})")
    generate()
