"""Generate committed v1/v2 equivalence conformance fixtures for the four merged
Governance Studio P3A scenarios.

This READS the frozen P3A demo_data (never mutates it), enriches each v1
``workflow_ir`` to ``workflow_ir.v2`` via the REAL Policy Workflow Compiler,
reduces the overlay, runs the full AWC pipeline on both the v1+full-overlay and
v2+reduced-overlay paths, and writes self-contained conformance fixtures plus an
equivalence manifest under this directory. The committed fixtures let the AWC test
suite verify v1/v2 equivalence without the compiler or the Governance Studio app
being present at test time.

Run:  python packages/capabilities/agent-workforce-composer/conformance/generate_compiler_v2_conformance.py
"""
from __future__ import annotations

import hashlib
import json
import os

import ugence_agent_workforce_composer.api as awc
import ugence_agent_workforce_composer.adapter_v2 as a2
import ugence_agent_workforce_composer.compatibility as compat
from ugence_policy_workflow_compiler.compiler.workflow_ir import WorkflowIR
from ugence_policy_workflow_compiler.semantics import enrich_workflow

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))))
_P3A = os.path.join(_REPO, "apps", "ugence-governance-studio", "demo_data")
OUT = os.path.join(_HERE, "governance_studio_v2")
LT = 1_000_000.0
SCENARIOS = ("procurement", "customer_support", "cybersecurity_success",
             "cybersecurity_no_feasible_team")

_INPUT_COPY = [
    ("agent_registry_snapshot.json", "registry.json"),
    ("enterprise_agent_policy.json", "enterprise_policy.json"),
    ("eligibility_policy.json", "eligibility_policy.json"),
    ("ranking_policy.json", "ranking_policy.json"),
    ("composition_policy.json", "composition_policy.json"),
    ("permission_policy.json", "permission_policy.json"),
    ("fallback_policy.json", "fallback_policy.json"),
]


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(data)
    return hashlib.sha256(data).hexdigest()


def _v2_doc(v1_doc):
    ir = WorkflowIR.model_validate(v1_doc["workflow_ir"])
    v2 = enrich_workflow(ir, compiler_version="0.2.0")
    d = v2.model_dump(mode="json")
    d["release_metadata"] = {"synthetic": True}
    return d


def _policies(base):
    return {
        "registry": awc.AgentRegistrySnapshot.model_validate(_read(os.path.join(base, "agent_registry_snapshot.json"))),
        "enterprise_policy": awc.EnterpriseAgentPolicy.model_validate(_read(os.path.join(base, "enterprise_agent_policy.json"))),
        "eligibility_policy": awc.EligibilityPolicy.model_validate(_read(os.path.join(base, "eligibility_policy.json"))),
        "ranking_policy": awc.AgentRankingPolicy.model_validate(_read(os.path.join(base, "ranking_policy.json"))),
        "composition_policy": awc.TeamCompositionPolicy.model_validate(_read(os.path.join(base, "composition_policy.json"))),
        "permission_policy": awc.PermissionBoundingPolicy.model_validate(_read(os.path.join(base, "permission_policy.json"))),
        "fallback_policy": awc.AgentFallbackPolicy.model_validate(_read(os.path.join(base, "fallback_policy.json"))),
    }


def _plan(ad, p):
    return awc.build_agent_team_plan(
        ad, p["registry"], p["enterprise_policy"], p["eligibility_policy"],
        p["ranking_policy"], p["composition_policy"], p["permission_policy"],
        p["fallback_policy"], LT)


def generate():
    manifest = {"schema": "awc.compiler_v2_conformance.v1", "logical_time": LT,
                "awc_version": awc.__version__, "scenarios": {}}
    for sid in SCENARIOS:
        base = os.path.join(_P3A, sid)
        v1_doc = _read(os.path.join(base, "compiled_workflow.json"))
        overlay = _read(os.path.join(base, "enterprise_role_overlay.json"))
        v2_doc = _v2_doc(v1_doc)
        reduced, removed = a2.reduce_overlay(overlay)
        p = _policies(base)

        v1_ad = awc.adapt_compiled_workflow(v1_doc, role_overlay=overlay)
        env = a2.adapt_compiled_workflow_v2(v2_doc, role_overlay=reduced)
        v1_plan = _plan(v1_ad, p)
        v2_plan = _plan(env.adaptation_result, p)
        ad_rep = compat.compare_adaptations(compat._wrap_v1(v1_ad), env)
        plan_rep = compat.compare_workforce_plans(v1_plan, v2_plan)

        out = os.path.join(OUT, sid)
        hashes = {}
        hashes["v1_workflow.json"] = _write(os.path.join(out, "v1_workflow.json"), v1_doc)
        hashes["v1_overlay.json"] = _write(os.path.join(out, "v1_overlay.json"), overlay)
        hashes["v2_workflow.json"] = _write(os.path.join(out, "v2_workflow.json"), v2_doc)
        hashes["v2_overlay.json"] = _write(os.path.join(out, "v2_overlay.json"), reduced)
        for src, dst in _INPUT_COPY:
            hashes[dst] = _write(os.path.join(out, dst), _read(os.path.join(base, src)))

        manifest["scenarios"][sid] = {
            "v1_input_digests": hashes,
            "removed_overlay_fields": {k: sorted(v) for k, v in removed.items()},
            "retained_overlay_fields": sorted({k for f in reduced.values() for k in f}),
            "adaptation_equivalence": ad_rep.state,
            "plan_equivalence": plan_rep.state,
            "v1_plan_state": v1_plan.plan_state.value,
            "v2_plan_state": v2_plan.plan_state.value,
            "v1_plan_fingerprint": v1_plan.plan_fingerprint,
            "v2_plan_fingerprint": v2_plan.plan_fingerprint,
            "v1_adaptation_fingerprint": v1_ad.adaptation_fingerprint,
            "v2_adaptation_fingerprint": env.adaptation_result.adaptation_fingerprint,
            "semantic_equivalence_fingerprint": plan_rep.semantic_equivalence_fingerprint,
        }
        print(f"  {sid}: adapt={ad_rep.state} plan={plan_rep.state} "
              f"v1={v1_plan.plan_state.value} v2={v2_plan.plan_state.value}")
    _write(os.path.join(OUT, "EQUIVALENCE_MANIFEST.json"), manifest)
    print(f"wrote conformance manifest with {len(manifest['scenarios'])} scenarios")
    return manifest


if __name__ == "__main__":
    print(f"Generating compiler-v2 conformance (AWC {awc.__version__})")
    generate()
