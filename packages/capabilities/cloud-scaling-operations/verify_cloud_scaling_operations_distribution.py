#!/usr/bin/env python3
"""Controlled-execution distribution verifier for ugence-cloud-scaling-operations.

Builds the operations wheel + sdist (and the advisory wheel, its dependency), installs
ONLY the built wheels into an isolated venv outside the repo, and asserts the package is
honestly execution-capable AND authority-gated: every mutation entrypoint fails closed
without authorization, import has no side effects, live mode is not default, and
auto-approval cannot reach execution. Generates SBOM + build provenance.

Emits CI-generated build evidence (gitignored):
  artifacts/distribution_verification.json, package_inventory.json,
  dependency_audit.json, sbom.json, build_provenance.json, evidence_sha256.json

Exits nonzero on any failed assertion.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parent
ADVISORY_PKG = PKG.parent / "cloud-scaling-controller"
ARTIFACTS = PKG / "artifacts"
DIST = "ugence-cloud-scaling-operations"
IMPORT_NAME = "ugence_cloud_scaling_operations"
EXPECTED_VERSION = "0.1.0"
BASELINE = "379a6366894fd2eead9460c29f4865fb1c3990de"

FORBIDDEN_CORE = ["kubernetes", "boto3", "botocore", "azure", "google.cloud",
                  "prometheus_client", "opentelemetry", "yaml"]


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


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _latest(d: Path, pat: str) -> Path:
    fs = sorted(d.glob(pat))
    if not fs:
        raise FileNotFoundError(pat)
    return fs[-1]


def main() -> int:
    ARTIFACTS.mkdir(exist_ok=True)
    c = Checks()
    ev = {"distribution": DIST, "import_namespace": IMPORT_NAME,
          "expected_version": EXPECTED_VERSION, "evidence_class": "CI_GENERATED_BUILD_EVIDENCE"}

    build_root = Path(tempfile.mkdtemp(prefix="cso-dist-"))
    dist = build_root / "dist"
    dist.mkdir()
    print("[build] operations wheel + sdist (and advisory wheel dependency)")
    b1 = _run([sys.executable, "-m", "build", str(PKG), "-o", str(dist)])
    c.check("build_operations_wheel_and_sdist", b1.returncode == 0,
            (b1.stderr.strip().splitlines() or [""])[-1] if b1.returncode else "")
    b2 = _run([sys.executable, "-m", "build", str(ADVISORY_PKG), "-o", str(dist)])
    c.check("build_advisory_dependency_wheel", b2.returncode == 0)
    if b1.returncode or b2.returncode:
        _finalize(c, ev, {}, {}, None, build_root)
        return 1

    wheel = _latest(dist, f"{IMPORT_NAME}-*.whl")
    sdist = _latest(dist, f"{IMPORT_NAME}-*.tar.gz")
    ev["wheel"] = {"name": wheel.name, "sha256": _sha(wheel)}
    ev["sdist"] = {"name": sdist.name, "sha256": _sha(sdist)}

    with zipfile.ZipFile(wheel) as z:
        names = z.namelist()
    tops = {n.split("/", 1)[0] for n in names if "/" in n}
    foreign = {t for t in tops if not (t == IMPORT_NAME or t.endswith(".dist-info"))}
    c.check("wheel_only_operations_namespace", not foreign, f"foreign={sorted(foreign)}")
    c.check("advisory_not_vendored",
            not any(n.startswith("ugence_cloud_scaling_controller/") for n in names))
    c.check("wheel_ships_py_typed", f"{IMPORT_NAME}/py.typed" in names)
    junk = [n for n in names if any(x in n.lower() for x in
            ("test", "__pycache__", ".pyc", "secret", ".git", "conftest"))]
    c.check("wheel_excludes_tests_caches_secrets", not junk, f"{junk[:4]}")

    # Every mutation entrypoint appears in the authority inventory.
    inv_path = ARTIFACTS / "execution_capability_inventory.json"
    inv = json.loads(inv_path.read_text()) if inv_path.exists() else {}
    mut = inv.get("mutation_entrypoints", [])
    c.check("mutation_entrypoints_inventoried",
            any("k8s_actuator" in m for m in mut) and any("gate_actuator" in m for m in mut),
            f"{mut}")

    package_inventory = {"wheel": wheel.name, "sha256": ev["wheel"]["sha256"],
                         "entry_count": len(names), "top_level": sorted(tops),
                         "packaged_modules": sorted(n for n in names if n.endswith(".py"))}

    requires = []
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        script = env / "bin" / "ugence-cloud-scaling-operations"
        clean = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        clean["PYTHONPATH"] = ""
        work = Path(td) / "work"
        work.mkdir()

        inst = _run([str(py), "-m", "pip", "install", "--quiet", "--find-links", str(dist), DIST],
                    env=clean)
        c.check("install_wheel_only", inst.returncode == 0,
                inst.stderr.strip()[-200:] if inst.returncode else "")
        pc = _run([str(py), "-m", "pip", "check"], env=clean)
        c.check("pip_check", pc.returncode == 0, (pc.stdout + pc.stderr).strip())
        ver = _run([str(py), "-I", "-c",
                    "import importlib.metadata as m;print(m.version('%s'))" % DIST],
                   cwd=str(work), env=clean)
        c.check("metadata_version", ver.stdout.strip() == EXPECTED_VERSION, ver.stdout.strip())

        probe = r"""
import json, sys, socket, threading, importlib.util as iu
_os = socket.socket
flags = {"socket": False, "threads0": threading.active_count()}
class _Tracked(_os):   # subclass so stdlib (ssl) can still subclass socket
    def __init__(self, *a, **k):
        flags["socket"] = True
        super().__init__(*a, **k)
socket.socket = _Tracked
import ugence_cloud_scaling_operations as O
from ugence_cloud_scaling_operations import (
    ControlledScalingExecutor, OperationsConfig, ExecutionMode, ExecutionRequest,
    TargetPolicy, FakeScalingBackend, ReferenceAuthorityVerifier)
out = {"version": O.__version__, "module_file": O.__file__}
flags["threads1"] = threading.active_count()
out["socket_opened"] = flags["socket"]
out["thread_started"] = flags["threads1"] != flags["threads0"]
out["default_mode_is_dry_run"] = OperationsConfig().mode == ExecutionMode.DRY_RUN
req = ExecutionRequest(action="scale", target_cluster="c", target_namespace="n",
    target_resource="r", current_replicas=3, target_replicas=5, recommendation_id="x",
    idempotency_key="k")
# LIVE without authorization -> denied (fail closed)
tp = TargetPolicy(allowed_clusters=("c",), allowed_namespaces=("n",), allowed_resources=("r",))
lx = ControlledScalingExecutor(OperationsConfig(mode=ExecutionMode.LIVE, target_policy=tp),
     backend=FakeScalingBackend({"c/n/r":3}), verifier=ReferenceAuthorityVerifier(), clock=lambda:1.0)
out["live_no_auth_denied"] = lx.execute(req, None, tenant_id="t").outcome == "denied"
# DRY_RUN proposes
dx = ControlledScalingExecutor(OperationsConfig(mode=ExecutionMode.DRY_RUN))
out["dry_run_proposes"] = dx.execute(req, tenant_id="t").outcome == "proposed"
forbidden = %r
out["forbidden_importable"] = [m for m in forbidden if iu.find_spec(m.split(".")[0]) is not None]
# auto-approval guard
try:
    from ugence_cloud_scaling_operations.orchestrator import ProductionOrchestrator, OrchestratorConfig
    from ugence_cloud_scaling_operations.recommend.engine import RecommendConfig
    from ugence_cloud_scaling_operations.action.k8s_actuator import ActuatorConfig, ActuatorMode
    try:
        ProductionOrchestrator(OrchestratorConfig(auto_approve_threshold="high",
            recommend=RecommendConfig(actuator=ActuatorConfig(mode=ActuatorMode.SCALE_PATCH))))
        out["auto_approval_guarded"] = False
    except RuntimeError:
        out["auto_approval_guarded"] = True
except Exception as exc:
    out["auto_approval_guarded"] = "error:" + type(exc).__name__
print(json.dumps(out))
""" % (FORBIDDEN_CORE,)
        pr = _run([str(py), "-I", "-c", probe], cwd=str(work), env=clean)
        c.check("isolated_probe_ran", pr.returncode == 0, pr.stderr.strip()[-300:] if pr.returncode else "")
        po = {}
        if pr.returncode == 0:
            po = json.loads(pr.stdout.strip().splitlines()[-1])
            c.check("import_canonical_package", po.get("version") == EXPECTED_VERSION)
            mf = po.get("module_file", "")
            c.check("no_monorepo_path_in_module", str(PKG) not in mf and "site-packages" in mf, mf)
            c.check("import_no_socket", po.get("socket_opened") is False)
            c.check("import_no_thread", po.get("thread_started") is False)
            c.check("default_mode_is_dry_run", po.get("default_mode_is_dry_run") is True)
            c.check("live_without_authorization_denied", po.get("live_no_auth_denied") is True)
            c.check("dry_run_proposes_only", po.get("dry_run_proposes") is True)
            c.check("no_forbidden_cloud_sdk_installed", not po.get("forbidden_importable"),
                    f"{po.get('forbidden_importable')}")
            c.check("auto_approval_cannot_reach_execution", po.get("auto_approval_guarded") is True,
                    f"{po.get('auto_approval_guarded')}")

        v = _run([str(script), "version"], cwd=str(work), env=clean)
        c.check("cli_version", v.returncode == 0 and EXPECTED_VERSION in v.stdout)
        insp = _run([str(script), "inspect-capabilities"], cwd=str(work), env=clean)
        c.check("cli_declares_execution_capability",
                insp.returncode == 0 and "INFRASTRUCTURE_MUTATION" in insp.stdout)
        ex_default = _run([str(script), "execute"], cwd=str(work), env=clean)
        c.check("cli_execute_default_non_mutating", ex_default.returncode != 0)

        dep = _run([str(py), "-I", "-c",
                    "import importlib.metadata as m, json;"
                    "print(json.dumps({'r': m.distribution('%s').requires or []}))" % DIST],
                   cwd=str(work), env=clean)
        requires = json.loads(dep.stdout.strip())["r"] if dep.returncode == 0 else []
        core = [r for r in requires if "extra ==" not in r]
        c.check("advisory_is_a_dependency",
                any("ugence-cloud-scaling-controller" in r for r in core), f"{core}")
        c.check("no_cloud_sdk_in_core_deps",
                not any(s in r.lower() for r in core for s in ("kubernetes", "boto3", "azure")), f"{core}")

    # SBOM + provenance.
    sbom_path = ARTIFACTS / "sbom.json"
    _run([sys.executable, str(PKG / "scripts" / "generate_sbom.py"), "--out", str(sbom_path)])
    c.check("sbom_generated", sbom_path.exists())
    prov_path = ARTIFACTS / "build_provenance.json"
    gp = _run([sys.executable, str(PKG / "scripts" / "generate_build_provenance.py"),
               "--wheel", str(wheel), "--sdist", str(sdist), "--sbom", str(sbom_path),
               "--authority-inventory", str(inv_path), "--out", str(prov_path)])
    c.check("build_provenance_generated", gp.returncode == 0)
    prov = json.loads(prov_path.read_text()) if prov_path.exists() else {}
    c.check("provenance_tree_clean", prov.get("dirty_tree") is False)
    c.check("provenance_wheel_hash_matches", prov.get("wheel", {}).get("sha256") == ev["wheel"]["sha256"])
    c.check("provenance_version_matches_manifest", prov.get("package_version") == EXPECTED_VERSION)
    c.check("provenance_build_not_baseline",
            prov.get("source_commit") and prov.get("source_commit") != BASELINE)

    dependency_audit = {"distribution": DIST, "declared_requirements": requires,
                        "forbidden_importable_in_clean_env": po.get("forbidden_importable")}
    _finalize(c, ev, package_inventory, dependency_audit, prov, build_root)
    return 0 if c.ok else 1


def _finalize(c, ev, pkg_inv, dep_audit, prov, build_root):
    ev["checks"] = c.results
    ev["verdict"] = "VERIFIED" if c.ok else "FAILED"
    ARTIFACTS.mkdir(exist_ok=True)
    (ARTIFACTS / "distribution_verification.json").write_text(json.dumps(ev, indent=2, sort_keys=True))
    if pkg_inv:
        (ARTIFACTS / "package_inventory.json").write_text(json.dumps(pkg_inv, indent=2, sort_keys=True))
    if dep_audit:
        (ARTIFACTS / "dependency_audit.json").write_text(json.dumps(dep_audit, indent=2, sort_keys=True))
    hashes = {p.name: _sha(p) for p in sorted(ARTIFACTS.glob("*.json"))
              if p.name not in ("evidence_sha256.json", "execution_capability_inventory.json")}
    (ARTIFACTS / "evidence_sha256.json").write_text(json.dumps(hashes, indent=2, sort_keys=True))
    if build_root:
        shutil.rmtree(build_root, ignore_errors=True)
    print("\n" + ("OPERATIONS DISTRIBUTION VERIFIED" if c.ok
                  else "OPERATIONS DISTRIBUTION VERIFICATION FAILED"))


if __name__ == "__main__":
    sys.exit(main())
