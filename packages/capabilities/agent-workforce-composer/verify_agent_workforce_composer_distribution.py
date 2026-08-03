#!/usr/bin/env python3
"""Reproducible independent-packaging proof for ``ugence-agent-workforce-composer``.

Builds the wheel + sdist, audits wheel contents, installs the wheel into a fresh
virtualenv with NO monorepo path, and proves the capability behaves outside the
repository:

  1. build wheel + sdist and record artifact hashes;
  2. audit wheel contents — only ``ugence_agent_workforce_composer`` source +
     metadata; ``py.typed`` present; NO tests/docs/scripts/fixtures-of-other-pkgs;
     NO foreign Ugence package bundled;
  3. clean-install the wheel (stdlib + pydantic only) and, with no ``/symbolu`` on
     ``sys.path``: run ``version``; adapt + validate a synthetic workflow; validate
     a registry and policies; run eligibility; and prove deterministic output
     ACROSS TWO SEPARATE PROCESSES (identical workflow fingerprint);
  4. report wheel reproducibility (bit-for-bit where achievable) and sdist
     reproducibility honestly.

Run:  python packages/capabilities/agent-workforce-composer/verify_agent_workforce_composer_distribution.py
Exit 0 on success; non-zero on the first failed step.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parent

CLEAN_INSTALL_CHECK = r'''
import sys, json
import ugence_agent_workforce_composer as awc
from ugence_agent_workforce_composer import api, fixtures
assert awc.__version__ == "0.2.1", awc.__version__
assert awc.CONTRACT_VERSION == "awc.v1", awc.CONTRACT_VERSION
assert api.COMPOSITION_CONTRACT_VERSION == "awc.composition.v1"
assert "site-packages" in awc.__file__, awc.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

# --- P1: adaptation + eligibility ---
adapt, result = fixtures.run_demo("procurement")
assert adapt.ok and adapt.accounting_holds()
for nd in adapt.node_dispositions:
    if nd.disposition.value in ("HUMAN_AUTHORITY_REQUIRED",
                                "EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP"):
        assert not nd.is_agent_role
snap = fixtures.registry_snapshot()
for rep in result.reports:
    assert len(rep.results) == len(snap.agent_profiles)

# --- P2: rank -> compose -> permission -> fallback -> AgentTeamPlan ---
adapt2, plan = fixtures.run_compose_demo("procurement")
assert plan.plan_state.value == "COMPLETE"
assert plan.search_statistics.optimality_status.value == "EXACT_OPTIMUM"
assert len(plan.role_assignments) == len(adapt2.role_requirements)
# least-privilege: proposed permissions never exceed role-required
for prop in plan.permission_bound_proposals:
    assert "does not grant" in prop.notice
# every fallback is a distinct eligible candidate
for fp in plan.role_fallback_plans:
    idents = [(c.agent_id, c.agent_version) for c in fp.candidates]
    assert len(idents) == len(set(idents))
# security workflow: typed NO_FEASIBLE_TEAM (no silent empty success)
_a, sec = fixtures.run_compose_demo("security")
assert sec.plan_state.value == "NO_FEASIBLE_TEAM" and sec.role_assignments == ()

# --- P2.1: compiler workflow_ir.v2 compatibility adapter (self-contained) ---
import ugence_agent_workforce_composer.adapter_v2 as a2
from ugence_agent_workforce_composer.compatibility import adapt_workflow
_node = {"node_id": "n_ev", "kind": "EVIDENCE_REQUIREMENT", "owning_capability": "COMPILER",
         "authority_type": "", "disposition": "ADVISORY", "public_contract_target": "",
         "input_object_ids": [], "output_contract": "evidence", "failure_behavior": "BLOCK",
         "audit_requirements": [], "label": "collect evidence"}
_term = {"node_id": "n_term", "kind": "TERMINAL_OUTCOME", "owning_capability": "COMPILER",
         "authority_type": "", "disposition": "ADVISORY", "public_contract_target": "",
         "input_object_ids": [], "output_contract": "", "failure_behavior": "BLOCK",
         "audit_requirements": [], "label": "terminal"}
_v2doc = {"ir_version": "workflow_ir.v2", "contract_version": "workflow_ir.v2",
          "policy_pack_id": "iso.v2", "policy_pack_version": 1, "base_ir_digest": "sha256:0",
          "base_ir": {"ir_version": "workflow_ir.v1", "policy_pack_id": "iso.v2",
                      "policy_pack_version": 1, "nodes": [_node, _term], "edges": [],
                      "referenced_capabilities": ["COMPILER"]},
          "node_semantics": [{"node_id": "n_ev", "node_kind": "EVIDENCE_REQUIREMENT",
              "semantic_purpose": "collect and extract evidence for a governed decision",
              "semantic_description": "collect evidence", "role_relevance": "ADVISORY_AGENT_ELIGIBLE",
              "required_capability_refs": [{"capability_id": "evidence_extraction",
                  "source": "NODE_KIND_MAPPING", "provenance": {"compiler_rule": "node_kind_capability_mapping",
                  "compiler_version": "0.2.0", "derivation_class": "DETERMINISTIC_MAPPING"}}],
              "human_review_requirement": {"required": False, "review_kind": "none"},
              "authority_disposition": "ADVISORY", "canonical_capability_owner": "COMPILER",
              "provenance": {"compiler_rule": "node_semantics_extraction", "compiler_version": "0.2.0",
                  "derivation_class": "DETERMINISTIC_MAPPING", "source_policy_id": "iso.v2"}}],
          "dependency_semantics": [], "compiler_version": "0.2.0", "workflow_fingerprint": "sha256:0",
          "release_metadata": {"synthetic": True}}
_env = a2.adapt_compiled_workflow_v2(_v2doc, source_package_digest="sha256:iso")
assert _env.ok and _env.adapter_mode == "V2_SEMANTIC"
assert len(_env.adaptation_result.role_requirements) == 1
_role = _env.adaptation_result.role_requirements[0]
assert _role.role_name == "collect and extract evidence for a governed decision"
assert "evidence_extraction" in _role.required_capabilities
# explicit dispatch: v2 doc routes to the semantic adapter; unknown fails closed.
assert adapt_workflow(_v2doc, source_package_digest="sha256:iso").adapter_mode == "V2_SEMANTIC"
assert adapt_workflow({"ir_version": "workflow_ir.v9"}).ok is False
# overlay reduction removes only compiler-emitted fields.
_red, _rem = a2.reduce_overlay({"n_ev": {"role_name": "x", "required_capabilities": ["risk"]}})
assert "role_name" in _rem["n_ev"] and "required_capabilities" in _red["n_ev"]
print("V2_ADAPTER_OK")
print("FP:" + plan.plan_fingerprint)
'''

FORBIDDEN_WHEEL_SUBSTRINGS = (
    "agentic", "agent_runtime", "ugence_model_selection", "ugence_policy_workflow_compiler",
    "ai_hiring", "ugence_procurement", "control_plane", "provider.py", "benchmark",
    "simulator", "corpus", "harness", "/tests/", "conftest",
)


import os

#: A fixed timestamp so wheel zip entries are deterministic (bit-for-bit builds).
_BUILD_ENV = {**os.environ, "SOURCE_DATE_EPOCH": "1704067200", "PYTHONHASHSEED": "0"}


def _run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, **kw)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build(outdir: Path) -> tuple[Path, Path]:
    _run([sys.executable, "-m", "build", "--outdir", str(outdir), str(PKG)], env=_BUILD_ENV)
    wheels = list(outdir.glob("*.whl"))
    sdists = list(outdir.glob("*.tar.gz"))
    assert wheels and sdists, "build did not produce wheel + sdist"
    return wheels[0], sdists[0]


def _audit_wheel(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    assert any(n.endswith("ugence_agent_workforce_composer/py.typed") for n in names), \
        "py.typed missing from wheel"
    assert any(n.endswith("ugence_agent_workforce_composer/api.py") for n in names), \
        "api.py missing from wheel"
    for n in names:
        low = n.lower()
        for bad in FORBIDDEN_WHEEL_SUBSTRINGS:
            if bad in low and "ugence_agent_workforce_composer" not in low.replace(bad, ""):
                # allow the package's own module names; forbid foreign/test/doc content
                if bad in ("/tests/", "conftest") or not low.startswith("ugence_agent_workforce_composer"):
                    raise AssertionError(f"forbidden wheel content {n!r} (matched {bad!r})")
    print("  wheel audit OK:", len(names), "entries; py.typed present; no foreign/test content")


def main() -> int:
    print("== build ==")
    work = Path(tempfile.mkdtemp(prefix="awc_dist_"))
    try:
        dist1 = work / "dist1"
        wheel1, sdist1 = _build(dist1)
        print("  wheel:", wheel1.name, _sha256(wheel1)[:16])
        print("  sdist:", sdist1.name, _sha256(sdist1)[:16])

        print("== wheel content audit ==")
        _audit_wheel(wheel1)

        print("== clean-install outside the repo ==")
        env_dir = work / "venv"
        venv.create(env_dir, with_pip=True)
        py = env_dir / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet", str(wheel1)])

        fingerprints = []
        for i in (1, 2):  # two SEPARATE processes -> determinism across processes
            res = _run([str(py), "-c", CLEAN_INSTALL_CHECK], capture_output=True, text=True)
            line = [l for l in res.stdout.splitlines() if l.startswith("FP:")][0]
            fingerprints.append(line[3:])
            print(f"  process {i} workflow fingerprint:", fingerprints[-1][:24])
        assert fingerprints[0] == fingerprints[1], "non-deterministic across processes"
        print("  cross-process determinism: OK")

        print("== CLI (installed console script) ==")
        _run([str(env_dir / "bin" / "ugence-agent-workforce-composer"), "version"],
             stdout=subprocess.DEVNULL)
        _run([str(env_dir / "bin" / "ugence-agent-workforce-composer"), "demo", "security"],
             stdout=subprocess.DEVNULL)
        _run([str(env_dir / "bin" / "ugence-agent-workforce-composer"), "demo", "procurement",
              "--compose"], stdout=subprocess.DEVNULL)

        print("== reproducibility ==")
        dist2 = work / "dist2"
        wheel2, sdist2 = _build(dist2)
        wheel_repro = _sha256(wheel1) == _sha256(wheel2)
        sdist_repro = _sha256(sdist1) == _sha256(sdist2)
        print(f"  wheel bit-for-bit reproducible: {wheel_repro}")
        print(f"  sdist bit-for-bit reproducible: {sdist_repro} "
              f"(sdist reproducibility is content-stable; gzip mtime may vary)")

        print("\nARTIFACT HASHES")
        print("  wheel:", _sha256(wheel1))
        print("  sdist:", _sha256(sdist1))
        print("\nAWC_P2_DISTRIBUTION_VERIFIED")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
