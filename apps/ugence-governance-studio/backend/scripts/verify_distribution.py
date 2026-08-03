"""Isolated distribution verifier (§29).

Builds the API wheel + sdist and the AWC dependency wheel, installs them into a
CLEAN virtual environment OUTSIDE the repository, and drives the installed package
(never the repo source) through the full pipeline via an in-process test client.
It audits wheel contents (py.typed present; AWC/compiler source NOT bundled; no
source-tree leakage), checks separate-process determinism and records wheel/sdist
hashes.

    python scripts/verify_distribution.py

Exit code 0 on success. This script lives outside the importable package, so its
use of subprocess/venv does not violate the API's own security boundary.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
_APP = os.path.dirname(_BACKEND)
_REPO = os.path.dirname(os.path.dirname(_APP))
_AWC = os.path.join(_REPO, "packages", "capabilities", "agent-workforce-composer")

# The verification program executed INSIDE the clean venv against the INSTALLED
# package (imported from site-packages, not the repo).
_INNER = r'''
import json, sys
from starlette.testclient import TestClient
import ugence_governance_studio_api as pkg
from ugence_governance_studio_api import create_app, ApiSettings, version_info

# Guard: the installed package must not resolve to a repo src tree.
assert "site-packages" in pkg.__file__, pkg.__file__

app = create_app(ApiSettings(environment="dist-verify"))
c = TestClient(app)
out = {}
out["health"] = c.get("/health").json()["status"]
out["ready"] = c.get("/ready").json()["ready"]
v = c.get("/version").json()
out["awc_version"] = v["awc_distribution_version"]
out["scenarios"] = [s["scenario_id"] for s in c.get("/api/v1/scenarios").json()["result"]["scenarios"]]
out["procurement_plan"] = c.get("/api/v1/scenarios/procurement/plan").json()["result"]["verification"]["match"]
out["infeasible"] = c.get("/api/v1/scenarios/cybersecurity_no_feasible_team/plan").json()["result"]["plan_state"]
out["v1_adapt"] = c.post("/api/v1/workflows/adapt", json={"workflow": __import__("ugence_governance_studio_api.scenarios.catalog", fromlist=["x"]).ScenarioCatalog().raw_workflow("procurement"), "overlay": {}}).json()["result"]["ok"]
cat = __import__("ugence_governance_studio_api.scenarios.catalog", fromlist=["x"]).ScenarioCatalog()
v2 = cat.v2_inputs("procurement")
out["v2_adapt"] = c.post("/api/v1/workflows/adapt", json={"workflow": v2["v2_workflow"], "contract_version": "workflow_ir.v2", "overlay": v2["v2_overlay"]}).json()["result"]["ok"]
out["eligibility"] = bool(c.post("/api/v1/eligibility/evaluate", json={"scenario_id": "procurement"}).json()["result"]["role_reports"])
out["ranking"] = len(c.post("/api/v1/ranking/evaluate", json={"scenario_id": "procurement"}).json()["result"]["rankings"])
out["composition"] = c.post("/api/v1/composition/compose", json={"scenario_id": "procurement"}).json()["result"]["plan_state"]
out["replay"] = c.post("/api/v1/plans/replay", json={"scenario_id": "procurement"}).json()["result"]["match"]
out["compare"] = c.post("/api/v1/plans/compare", json={"left": {"scenario_id": "procurement"}, "right": {"scenario_id": "customer_support"}}).json()["result"]["same_workflow"]
out["what_if"] = c.post("/api/v1/scenarios/procurement/what-if", json={"operation": "FORBID_PROVIDER", "params": {"provider": "anthropic"}}).json()["result"]["modified_state"]
from ugence_governance_studio_api.openapi import canonical_openapi_bytes
out["openapi_sha256"] = __import__("hashlib").sha256(canonical_openapi_bytes()).hexdigest()
out["plan_fingerprint"] = c.get("/api/v1/scenarios/procurement/plan").json()["result"]["agent_team_plan"]["plan_fingerprint"]
import os as _os
out["py_typed"] = _os.path.isfile(_os.path.join(_os.path.dirname(pkg.__file__), "py.typed"))
print("RESULT_JSON " + json.dumps(out))
'''


# A clean environment for every subprocess: strip PYTHONPATH so the venv is
# TRULY isolated and can never import the package from the repo source tree.
_CLEAN_ENV = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}


def _run(cmd, **kw):
    print("+", " ".join(cmd))
    kw.setdefault("env", _CLEAN_ENV)
    return subprocess.run(cmd, check=True, **kw)


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _build(project_dir: str, out_dir: str) -> None:
    _run([sys.executable, "-m", "build", "--outdir", out_dir, project_dir])


def _audit_wheel(wheel_path: str) -> dict:
    with zipfile.ZipFile(wheel_path) as zf:
        names = zf.namelist()
    bundled_awc = [n for n in names if n.startswith("ugence_agent_workforce_composer/")]
    bundled_compiler = [n for n in names if n.startswith("ugence_policy_workflow_compiler/")]
    py_typed = any(n.endswith("ugence_governance_studio_api/py.typed") for n in names)
    data_files = [n for n in names if "/data/demo_data/" in n]
    leakage = [n for n in names if n.startswith("src/") or n.startswith("tests/")]
    return {
        "awc_source_bundled": bool(bundled_awc),
        "compiler_source_bundled": bool(bundled_compiler),
        "py_typed_present": py_typed,
        "bundled_fixture_count": len(data_files),
        "source_tree_leakage": leakage,
    }


def main() -> int:
    work = tempfile.mkdtemp(prefix="ugs-dist-verify-")
    try:
        dist = os.path.join(work, "dist")
        os.makedirs(dist, exist_ok=True)
        print("== building API wheel + sdist ==")
        _build(_BACKEND, dist)
        print("== building AWC dependency wheel ==")
        _build(_AWC, dist)

        wheels = [f for f in os.listdir(dist) if f.endswith(".whl")]
        api_wheel = next(f for f in wheels if f.startswith("ugence_governance_studio_api"))
        sdists = [f for f in os.listdir(dist) if f.endswith(".tar.gz")
                  and f.startswith("ugence_governance_studio_api")]
        api_wheel_path = os.path.join(dist, api_wheel)
        api_sdist_path = os.path.join(dist, sdists[0])

        print("== auditing wheel contents ==")
        audit = _audit_wheel(api_wheel_path)
        print(json.dumps(audit, indent=2))
        assert not audit["awc_source_bundled"], "AWC source must NOT be bundled"
        assert not audit["compiler_source_bundled"], "compiler source must NOT be bundled"
        assert audit["py_typed_present"], "py.typed must be present"
        assert not audit["source_tree_leakage"], f"source leakage: {audit['source_tree_leakage']}"
        assert audit["bundled_fixture_count"] > 0, "scenario fixtures must be bundled as data"

        print("== creating clean venv OUTSIDE the repo ==")
        venv = os.path.join(work, "venv")
        _run([sys.executable, "-m", "venv", venv])
        vpy = os.path.join(venv, "bin", "python")
        _run([vpy, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
        # install both wheels; resolve fastapi/pydantic/etc from the index.
        _run([vpy, "-m", "pip", "install", "--quiet",
              "--find-links", dist, api_wheel_path])
        _run([vpy, "-m", "pip", "install", "--quiet", "httpx"])

        print("== running installed-package verification (process 1) ==")
        r1 = subprocess.run([vpy, "-c", _INNER], cwd=work, check=False,
                            capture_output=True, text=True, env=_CLEAN_ENV)
        if r1.returncode != 0:
            print("INNER STDOUT:\n" + r1.stdout, file=sys.stderr)
            print("INNER STDERR:\n" + r1.stderr, file=sys.stderr)
            raise SystemExit(1)
        line1 = next(l for l in r1.stdout.splitlines() if l.startswith("RESULT_JSON "))
        res1 = json.loads(line1[len("RESULT_JSON "):])
        print(json.dumps(res1, indent=2))

        print("== separate-process determinism (process 2) ==")
        r2 = subprocess.run([vpy, "-c", _INNER], cwd=work, check=True,
                            capture_output=True, text=True, env=_CLEAN_ENV)
        line2 = next(l for l in r2.stdout.splitlines() if l.startswith("RESULT_JSON "))
        res2 = json.loads(line2[len("RESULT_JSON "):])
        determinism = (res1["plan_fingerprint"] == res2["plan_fingerprint"]
                       and res1["openapi_sha256"] == res2["openapi_sha256"])

        # assertions on functional results
        assert res1["health"] == "healthy"
        assert res1["ready"] is True
        assert res1["awc_version"] == "0.2.1"
        assert res1["procurement_plan"] is True
        assert res1["infeasible"] == "NO_FEASIBLE_TEAM"
        assert res1["v1_adapt"] and res1["v2_adapt"]
        assert res1["composition"] == "COMPLETE"
        assert res1["replay"] is True
        assert res1["what_if"] == "NO_FEASIBLE_TEAM"
        assert determinism, "separate-process results diverged"

        summary = {
            "verdict": "GOVERNANCE_STUDIO_P3B_DISTRIBUTION_OK",
            "wheel": api_wheel,
            "wheel_sha256": _sha256(api_wheel_path),
            "sdist": sdists[0],
            "sdist_sha256": _sha256(api_sdist_path),
            "wheel_audit": audit,
            "installed_verification": res1,
            "separate_process_determinism": determinism,
        }
        print("== SUMMARY ==")
        print(json.dumps(summary, indent=2))
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
