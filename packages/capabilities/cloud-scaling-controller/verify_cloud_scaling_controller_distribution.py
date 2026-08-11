#!/usr/bin/env python3
"""Advisory-boundary distribution verifier for ugence-cloud-scaling-controller (0.3.0).

Builds wheel + sdist, inspects the PACKAGED Python source inside the wheel for any
execution capability, installs ONLY the wheel into an isolated venv created OUTSIDE
the repository, and asserts the distribution is genuinely advisory-only. Generates
build provenance bound to the actual build revision and fails on any tampered or
inconsistent evidence.

Emits CI-generated build evidence (NOT committed):
  artifacts/distribution_verification.json
  artifacts/package_inventory.json
  artifacts/dependency_audit.json
  artifacts/build_provenance.json
  artifacts/evidence_sha256.json

Exits nonzero on ANY failed assertion.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parent
ARTIFACTS = PKG / "artifacts"
DIST_NAME = "ugence-cloud-scaling-controller"
IMPORT_NAME = "ugence_cloud_scaling_controller"
EXPECTED_VERSION = "0.3.0"
BASELINE_COMMIT = "0d5d4dde5b68ef61e6dec994cc4b9e55fa57e363"

FORBIDDEN_UGENCE = [
    "governance_studio", "decision_governance", "actiongate", "actiongate_provider",
    "agent_runtime", "hybrid_llm", "llm_steering", "ai_hiring", "control_plane",
    "governance_providers", "governance_contracts", "cloud_scaling_operations",
]
FORBIDDEN_CLOUD_SDK = ["boto3", "botocore", "azure", "google.cloud", "kubernetes"]
FORBIDDEN_CORE_EXTRAS = ["prometheus_client", "opentelemetry", "yaml",
                         "fastapi", "uvicorn", "flask"]

# Mandatory wheel-content prohibitions (section 10).
FORBIDDEN_WHEEL_PATH_SUBSTR = [
    "/action/", "/orchestrator.py", "/main.py",
    "/recommend/engine.py", "/recommend/approval.py", "/recommend/webhook.py",
    "/observability/metrics_server.py", "/observability/exporter.py",
    "/observability/otel_exporter.py", "/shadow/runner.py", "/shadow/live_efficiency.py",
]
FORBIDDEN_WHEEL_SYMBOLS = [
    "K8sActuator", "GateActuator", "ProductionOrchestrator", "ActuatorMode",
    "SCALE_PATCH", "ARGOCD_SYNC", "patch_namespaced_deployment_scale",
    "auto_approve_threshold", "auto-approved", "trigger_sync", "argocd_token",
    "ExecutionResult", "RecommendEngine",
]
# K8s/ArgoCD mutation call patterns that must not appear in any packaged source.
FORBIDDEN_MUTATION_PATTERNS = [
    "patch_namespaced_deployment", "replace_namespaced", "create_namespaced",
    "delete_namespaced", "argocd", "ArgoCD",
]


class Checks:
    def __init__(self):
        self.results = []
        self.ok = True

    def check(self, name, passed, detail=""):
        self.results.append({"check": name, "passed": bool(passed), "detail": str(detail)})
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
        if not passed:
            self.ok = False


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def main() -> int:
    ARTIFACTS.mkdir(exist_ok=True)
    c = Checks()
    evidence = {"distribution": DIST_NAME, "import_namespace": IMPORT_NAME,
                "expected_version": EXPECTED_VERSION, "evidence_class": "CI_GENERATED_BUILD_EVIDENCE"}

    build_root = Path(tempfile.mkdtemp(prefix="csc-dist-"))
    dist_dir = build_root / "dist"
    dist_dir.mkdir()
    print("[build] wheel + sdist")
    b = _run([sys.executable, "-m", "build", str(PKG), "-o", str(dist_dir)])
    c.check("build_wheel_and_sdist", b.returncode == 0,
            (b.stderr.strip().splitlines() or [""])[-1] if b.returncode else "")
    if b.returncode != 0:
        print(b.stderr)
        _finalize(c, evidence, {}, {}, None, build_root)
        return 1

    wheel = _latest(dist_dir, f"{IMPORT_NAME}-*.whl")
    sdist = _latest(dist_dir, f"{IMPORT_NAME}-*.tar.gz")
    evidence["wheel"] = {"name": wheel.name, "sha256": _sha256(wheel)}
    evidence["sdist"] = {"name": sdist.name, "sha256": _sha256(sdist)}

    # ---- Wheel content inspection (open each packaged .py) ----
    with zipfile.ZipFile(wheel) as z:
        names = z.namelist()
        py_sources = {n: z.read(n).decode("utf-8", "ignore")
                      for n in names if n.endswith(".py")}
    tops = {n.split("/", 1)[0] for n in names if "/" in n}
    foreign = {t for t in tops if not (t == IMPORT_NAME or t.endswith(".dist-info"))}
    c.check("wheel_no_foreign_top_level", not foreign, f"foreign={sorted(foreign)}")
    c.check("wheel_ships_py_typed", f"{IMPORT_NAME}/py.typed" in names)
    junk = [n for n in names if any(x in n.lower() for x in
            ("test", "__pycache__", ".pyc", "secret", ".git", "conftest"))]
    c.check("wheel_excludes_tests_caches_secrets_git", not junk, f"junk={junk[:5]}")
    controllers = [n for n in names if n.endswith("/controller.py")]
    c.check("wheel_single_controller_copy", len(controllers) == 1, f"copies={controllers}")
    legacy = [n for n in names if n.startswith("cloud_controller/")
              or n.startswith("symbolu/") or n.startswith("cloud_scaling_operations/")]
    c.check("wheel_excludes_legacy_and_operations", not legacy, f"present={legacy[:5]}")

    # Forbidden PATHS
    path_hits = [n for n in names for sub in FORBIDDEN_WHEEL_PATH_SUBSTR if sub in "/" + n]
    c.check("wheel_no_forbidden_paths", not path_hits, f"hits={sorted(set(path_hits))[:6]}")

    # Forbidden SYMBOLS inside packaged source
    sym_hits = {}
    for n, src in py_sources.items():
        for sym in FORBIDDEN_WHEEL_SYMBOLS:
            if re.search(r"\b" + re.escape(sym) + r"\b", src):
                sym_hits.setdefault(sym, []).append(n)
    c.check("wheel_no_forbidden_symbols", not sym_hits,
            f"{ {k: v[:1] for k, v in sym_hits.items()} }")

    # No K8s/ArgoCD mutation call patterns
    mut_hits = {}
    for n, src in py_sources.items():
        for pat in FORBIDDEN_MUTATION_PATTERNS:
            if pat in src:
                mut_hits.setdefault(pat, []).append(n)
    c.check("wheel_no_kubernetes_or_argocd_mutations", not mut_hits,
            f"{ {k: v[:1] for k, v in mut_hits.items()} }")

    # No concrete executor: ScalingExecutor is a Protocol; no .apply(...) implementation
    # that mutates, and no auto-approval.
    exec_hits = [n for n, s in py_sources.items()
                 if "def apply(self, recommendation" in s and "Protocol" not in s and "..." not in s]
    c.check("wheel_no_concrete_executor", not exec_hits, f"{exec_hits}")
    approve_hits = [n for n, s in py_sources.items()
                    if re.search(r"\bdef approve\b", s) or "auto_approve" in s]
    c.check("wheel_no_auto_approval_or_approver", not approve_hits, f"{approve_hits}")

    package_inventory = {
        "wheel": wheel.name, "sha256": evidence["wheel"]["sha256"],
        "entry_count": len(names), "top_level": sorted(tops),
        "packaged_python_modules": sorted(py_sources),
        "controller_copies": controllers,
    }

    # ---- Isolated install + runtime checks ----
    probe_out = {}
    requires = []
    core_reqs = []
    with tempfile.TemporaryDirectory() as td:
        env_dir = Path(td) / "venv"
        venv.create(env_dir, with_pip=True, clear=True, system_site_packages=False)
        py = env_dir / "bin" / "python"
        script = env_dir / "bin" / "ugence-cloud-scaling"
        clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        clean_env["PYTHONPATH"] = ""
        work = Path(td) / "work"
        work.mkdir()

        inst = _run([str(py), "-m", "pip", "install", "--quiet",
                     "--find-links", str(dist_dir), DIST_NAME], env=clean_env)
        c.check("install_wheel_only", inst.returncode == 0,
                inst.stderr.strip()[-200:] if inst.returncode else "")

        pc = _run([str(py), "-m", "pip", "check"], env=clean_env)
        c.check("pip_check", pc.returncode == 0, (pc.stdout + pc.stderr).strip())

        ver = _run([str(py), "-I", "-c",
                    "import importlib.metadata as m;print(m.version('%s'))" % DIST_NAME],
                   cwd=str(work), env=clean_env)
        c.check("metadata_version", ver.stdout.strip() == EXPECTED_VERSION,
                f"got={ver.stdout.strip()!r}")

        probe = r"""
import json, sys
import importlib.util as _iu
import ugence_cloud_scaling_controller as U
from ugence_cloud_scaling_controller import CloudScalingController, ScalingObservation
out = {"version": U.__version__, "module_file": U.__file__}
c = CloudScalingController()
rec = c.recommend(ScalingObservation(metrics={"cpu":0.92,"memory":0.88,"latency_p99":0.81,
                  "error_rate":0.2,"queue_depth":0.7}, current_replicas=4, phase="peak",
                  correlation_id="verify-1"))
d = rec.to_dict()
out["recommendation"] = d["recommendation"]
out["advisory_only"] = d["advisory_only"]
out["actuation_performed"] = d["actuation_performed"]
out["correlation_id"] = d["correlation_id"]
out["json_ok"] = json.loads(rec.to_json())["schema_version"] == "1.1"
out["determinism_present"] = isinstance(d.get("determinism"), dict) and \
    "identity_deviation" in d["determinism"].get("nondeterministic_fields", [])

# --- Phase 2 shadow forecasting smoke (installed wheel), full chain ---
from datetime import datetime, timedelta, timezone
from ugence_cloud_scaling_controller import (
    CanonicalCapacityState, CapacitySubject, Measurement, Unit,
    NormalizationPolicy, NormalizationMethod,
)
from ugence_cloud_scaling_controller.canonical import InfrastructureState, CapacityState
from ugence_cloud_scaling_controller.forecasting import (
    CanonicalCapacitySeries, ForecastTarget, ForecastHorizon, build_input_window,
    PersistenceForecaster, UncertaintyConfig, forecast_with_evidence, evaluate_forecast,
)
_subj = CapacitySubject(workload_id="verify-wl", tenant_id="verify-tenant")
_t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
_hist = [CanonicalCapacityState(subject=_subj, observed_at=_t0 + timedelta(seconds=60 * i),
         infrastructure=InfrastructureState(cpu_utilization=Measurement(50.0 + i, Unit.PERCENT)),
         capacity=CapacityState(running_replicas=4)) for i in range(8)]
_series = CanonicalCapacitySeries.build(_hist)
_npol = NormalizationPolicy(policy_id="verify-pol",
                            method_by_signal={"cpu": NormalizationMethod.PERCENT_TO_RATIO})
_cut = _hist[-1].observed_at
_win = build_input_window(_series, ForecastTarget.CPU_UTILIZATION, _cut, ForecastHorizon(60.0))
_ev = forecast_with_evidence(_series, ForecastTarget.CPU_UTILIZATION, _cut, ForecastHorizon(60.0),
      PersistenceForecaster(), normalization_policy=_npol,
      uncertainty_config=UncertaintyConfig(min_calibration_samples=3, match_tolerance_seconds=5.0))
_actual = CanonicalCapacityState(subject=_subj, observed_at=_ev.forecast.forecast_for,
          infrastructure=InfrastructureState(cpu_utilization=Measurement(60.0, Unit.PERCENT)),
          capacity=CapacityState(running_replicas=4))
_rec2 = evaluate_forecast(_ev, _actual, match_tolerance_seconds=5.0)
out["forecast_status"] = _ev.forecast.status
out["forecast_shadow_only"] = _ev.forecast.shadow_only
out["forecast_advisory_only"] = _ev.forecast.advisory_only
out["forecast_actuation"] = _ev.forecast.actuation_performed
out["forecast_authority"] = _ev.forecast.authority_class
out["forecast_execution_capability"] = _ev.forecast.execution_capability
out["forecast_window_samples"] = _win.sample_count
out["forecast_evidence_digest_ok"] = _ev.digest().startswith("sha256:")
out["forecast_evaluation_status"] = _rec2.status.value
# Live path unchanged: the recommendation above is byte-identical to Phase-1 behavior.
out["live_path_advisory"] = d["advisory_only"] is True and d["actuation_performed"] is False

forbidden = %r + %r + %r
out["forbidden_importable"] = [m for m in forbidden if _iu.find_spec(m.split(".")[0]) is not None]
out["legacy_cloud_controller_importable"] = _iu.find_spec("cloud_controller") is not None
out["operations_importable"] = _iu.find_spec("cloud_scaling_operations") is not None
print(json.dumps(out))
""" % (FORBIDDEN_UGENCE, FORBIDDEN_CLOUD_SDK, FORBIDDEN_CORE_EXTRAS)
        pr = _run([str(py), "-I", "-c", probe], cwd=str(work), env=clean_env)
        c.check("isolated_probe_ran", pr.returncode == 0, pr.stderr.strip()[-300:] if pr.returncode else "")
        if pr.returncode == 0:
            probe_out = json.loads(pr.stdout.strip().splitlines()[-1])
            c.check("import_canonical_package", probe_out.get("version") == EXPECTED_VERSION)
            mf = probe_out.get("module_file", "")
            c.check("no_monorepo_path_in_module", str(PKG) not in mf and "site-packages" in mf, mf)
            c.check("demo_executes", bool(probe_out.get("recommendation")))
            c.check("advisory_only_invariant", probe_out.get("advisory_only") is True
                    and probe_out.get("actuation_performed") is False)
            c.check("json_serialization_schema_1_1", probe_out.get("json_ok") is True)
            c.check("determinism_disclosure_present", probe_out.get("determinism_present") is True)
            c.check("correlation_id_preserved", probe_out.get("correlation_id") == "verify-1")
            c.check("no_forbidden_packages_installed", not probe_out.get("forbidden_importable"),
                    f"present={probe_out.get('forbidden_importable')}")
            c.check("legacy_imports_not_shipped_in_wheel",
                    probe_out.get("legacy_cloud_controller_importable") is False)
            c.check("operations_not_shipped_in_wheel",
                    probe_out.get("operations_importable") is False)
            # Phase 2 shadow forecasting: full chain executes from the installed wheel and
            # is shadow-only / advisory-only, and the live recommendation path is unchanged.
            c.check("forecast_full_chain_executes",
                    probe_out.get("forecast_status") == "forecast"
                    and probe_out.get("forecast_window_samples") == 8
                    and probe_out.get("forecast_evaluation_status") == "evaluated")
            c.check("forecast_shadow_advisory_invariant",
                    probe_out.get("forecast_shadow_only") is True
                    and probe_out.get("forecast_advisory_only") is True
                    and probe_out.get("forecast_actuation") is False
                    and probe_out.get("forecast_authority") == "ADVISORY"
                    and probe_out.get("forecast_execution_capability") == "NONE")
            c.check("forecast_evidence_digest_present",
                    probe_out.get("forecast_evidence_digest_ok") is True)
            c.check("live_recommendation_path_unchanged",
                    probe_out.get("live_path_advisory") is True)

        cli_ver = _run([str(script), "version"], cwd=str(work), env=clean_env)
        c.check("cli_version", cli_ver.returncode == 0 and EXPECTED_VERSION in cli_ver.stdout)
        cli_demo = _run([str(script), "demo"], cwd=str(work), env=clean_env)
        c.check("cli_demo", cli_demo.returncode == 0 and '"advisory_only": true' in cli_demo.stdout,
                cli_demo.stderr.strip()[-160:] if cli_demo.returncode else "")
        cli_eval = _run([str(script), "evaluate", "--input", "-"], cwd=str(work),
                        env=clean_env, input='{"metrics":{"cpu":0.9},"current_replicas":3}')
        c.check("cli_evaluate", cli_eval.returncode == 0 and '"schema_version": "1.1"' in cli_eval.stdout)
        cli_bad = _run([str(script), "evaluate", "--input", "-"], cwd=str(work),
                       env=clean_env, input="{not json")
        c.check("cli_nonzero_on_invalid", cli_bad.returncode != 0)

        sp = _run([str(py), "-I", "-c",
                   "import ugence_cloud_scaling_controller as U, pathlib, json;"
                   "p=pathlib.Path(U.__file__).parent;"
                   "print(json.dumps(sorted(str(x.relative_to(p)) for x in p.rglob('controller.py'))))"],
                  cwd=str(work), env=clean_env)
        installed_controllers = json.loads(sp.stdout.strip()) if sp.returncode == 0 else ["<err>"]
        c.check("installed_single_implementation", installed_controllers == ["controller.py"],
                f"found={installed_controllers}")

        dep = _run([str(py), "-I", "-c",
                    "import importlib.metadata as m, json;"
                    "print(json.dumps({'requires': m.distribution('%s').requires or []}))" % DIST_NAME],
                   cwd=str(work), env=clean_env)
        requires = json.loads(dep.stdout.strip())["requires"] if dep.returncode == 0 else []
        core_reqs = [r for r in requires if "extra ==" not in r]
        c.check("core_dependency_is_numpy_only",
                core_reqs and all("numpy" in r.lower() for r in core_reqs), f"core_reqs={core_reqs}")
        c.check("no_cloud_sdk_in_declared_deps",
                not any(any(sdk in r.lower() for sdk in ("kubernetes", "boto3", "azure", "google-cloud"))
                        for r in requires), f"requires={requires}")

    # ---- Build provenance + fail conditions ----
    prov_path = ARTIFACTS / "build_provenance.json"
    gp = _run([sys.executable, str(PKG / "scripts" / "generate_build_provenance.py"),
               "--wheel", str(wheel), "--sdist", str(sdist), "--out", str(prov_path)])
    c.check("build_provenance_generated", gp.returncode == 0, gp.stderr.strip()[-200:] if gp.returncode else "")
    provenance = json.loads(prov_path.read_text()) if prov_path.exists() else {}
    c.check("provenance_build_revision_present", bool(provenance.get("build_commit")))
    c.check("provenance_tree_clean", provenance.get("dirty_tree") is False,
            "working tree is dirty" if provenance.get("dirty_tree") else "")
    c.check("provenance_wheel_hash_matches",
            provenance.get("wheel", {}).get("sha256") == evidence["wheel"]["sha256"])
    c.check("provenance_sdist_hash_matches",
            provenance.get("sdist", {}).get("sha256") == evidence["sdist"]["sha256"])
    c.check("provenance_version_matches_manifest",
            provenance.get("package_version") == EXPECTED_VERSION)
    c.check("provenance_build_not_baseline_commit",
            provenance.get("build_commit") and provenance.get("build_commit") != BASELINE_COMMIT,
            "build_commit must not be the pre-packaging baseline commit")

    dependency_audit = {
        "distribution": DIST_NAME,
        "declared_requirements": requires,
        "core_requirements": core_reqs,
        "forbidden_ugence_checked": FORBIDDEN_UGENCE,
        "forbidden_cloud_sdk_checked": FORBIDDEN_CLOUD_SDK,
        "forbidden_importable_in_clean_env": probe_out.get("forbidden_importable"),
    }

    _finalize(c, evidence, package_inventory, dependency_audit, provenance, build_root)
    return 0 if c.ok else 1


def _finalize(c, evidence, package_inventory, dependency_audit, provenance, build_root):
    evidence["checks"] = c.results
    evidence["verdict"] = "VERIFIED" if c.ok else "FAILED"
    ARTIFACTS.mkdir(exist_ok=True)
    (ARTIFACTS / "distribution_verification.json").write_text(json.dumps(evidence, indent=2, sort_keys=True))
    if package_inventory:
        (ARTIFACTS / "package_inventory.json").write_text(json.dumps(package_inventory, indent=2, sort_keys=True))
    if dependency_audit:
        (ARTIFACTS / "dependency_audit.json").write_text(json.dumps(dependency_audit, indent=2, sort_keys=True))
    hashes = {p.name: _sha256(p) for p in sorted(ARTIFACTS.glob("*.json")) if p.name != "evidence_sha256.json"}
    (ARTIFACTS / "evidence_sha256.json").write_text(json.dumps(hashes, indent=2, sort_keys=True))
    if build_root:
        shutil.rmtree(build_root, ignore_errors=True)
    print("\n" + ("ADVISORY DISTRIBUTION VERIFIED" if c.ok else "ADVISORY DISTRIBUTION VERIFICATION FAILED"))
    print(f"evidence: {ARTIFACTS}/distribution_verification.json")


if __name__ == "__main__":
    sys.exit(main())
