#!/usr/bin/env python3
"""Clean-environment distribution verifier for ugence-cloud-scaling-controller.

Builds the wheel + sdist, installs ONLY the wheel into an isolated virtual environment
created OUTSIDE the repository (sanitized PYTHONPATH, cwd outside the repo), and asserts
the independent capability behaves correctly with none of the forbidden dependencies.

Produces machine-readable evidence:
  artifacts/distribution_verification.json
  artifacts/package_inventory.json
  artifacts/dependency_audit.json

Exits nonzero on ANY failed assertion.
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
ARTIFACTS = PKG / "artifacts"
DIST_NAME = "ugence-cloud-scaling-controller"
IMPORT_NAME = "ugence_cloud_scaling_controller"
EXPECTED_VERSION = "0.1.0"

FORBIDDEN_UGENCE = [
    "governance_studio", "decision_governance", "actiongate", "actiongate_provider",
    "agent_runtime", "hybrid_llm", "llm_steering", "ai_hiring", "control_plane",
    "governance_providers", "governance_contracts",
]
FORBIDDEN_CLOUD_SDK = [
    "boto3", "botocore", "azure", "google.cloud", "kubernetes",
]
# Extras are optional; a bare-core install must NOT pull these either.
FORBIDDEN_CORE_EXTRAS = ["requests", "prometheus_client", "opentelemetry", "yaml",
                         "fastapi", "uvicorn", "flask"]


class Checks:
    def __init__(self):
        self.results = []
        self.ok = True

    def check(self, name, passed, detail=""):
        self.results.append({"check": name, "passed": bool(passed), "detail": str(detail)})
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
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
                "expected_version": EXPECTED_VERSION}

    # Build into a temp dir OUTSIDE the repo.
    build_root = Path(tempfile.mkdtemp(prefix="csc-dist-"))
    dist_dir = build_root / "dist"
    dist_dir.mkdir()
    print("[build] wheel + sdist")
    b = _run([sys.executable, "-m", "build", str(PKG), "-o", str(dist_dir)])
    c.check("build_wheel_and_sdist", b.returncode == 0, b.stderr.strip().splitlines()[-1] if b.returncode else "")
    if b.returncode != 0:
        print(b.stderr)
        _finalize(c, evidence, {}, {}, build_root)
        return 1

    wheel = _latest(dist_dir, f"{IMPORT_NAME}-*.whl")
    sdist = _latest(dist_dir, f"{IMPORT_NAME}-*.tar.gz")
    evidence["wheel"] = {"name": wheel.name, "sha256": _sha256(wheel)}
    evidence["sdist"] = {"name": sdist.name, "sha256": _sha256(sdist)}

    # ---- Wheel content inspection (steps 16-18) ----
    with zipfile.ZipFile(wheel) as z:
        names = z.namelist()
    tops = {n.split("/", 1)[0] for n in names if "/" in n}
    foreign = {t for t in tops if not (t == IMPORT_NAME or t.endswith(".dist-info"))}
    c.check("wheel_no_foreign_top_level", not foreign, f"foreign={sorted(foreign)}")
    c.check("wheel_ships_py_typed", f"{IMPORT_NAME}/py.typed" in names)
    bad = [n for n in names if any(x in n.lower() for x in
           ("test", "__pycache__", ".pyc", "secret", ".git", "conftest"))]
    c.check("wheel_excludes_tests_caches_secrets_git", not bad, f"bad={bad[:5]}")
    controller_copies = [n for n in names if n.endswith("/controller.py")]
    c.check("wheel_single_controller_copy", len(controller_copies) == 1, f"copies={controller_copies}")
    # legacy namespaces must NOT be in the wheel
    legacy_in_wheel = [n for n in names if n.startswith("cloud_controller/") or n.startswith("symbolu/")]
    c.check("wheel_excludes_legacy_namespaces", not legacy_in_wheel, f"legacy={legacy_in_wheel[:5]}")

    package_inventory = {
        "wheel": wheel.name, "sha256": evidence["wheel"]["sha256"],
        "entry_count": len(names), "top_level": sorted(tops),
        "members": sorted(names),
        "controller_copies": controller_copies,
    }

    # ---- Isolated install + runtime checks (steps 2-15) ----
    with tempfile.TemporaryDirectory() as td:
        env_dir = Path(td) / "venv"
        venv.create(env_dir, with_pip=True, clear=True, system_site_packages=False)
        py = env_dir / "bin" / "python"
        script = env_dir / "bin" / "ugence-cloud-scaling"
        # Sanitized environment: no PYTHONPATH, no monorepo on path.
        clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        clean_env["PYTHONPATH"] = ""
        work = Path(td) / "work"  # cwd OUTSIDE the repository
        work.mkdir()

        # Install OUR package from the locally-built wheel (--find-links prefers it);
        # the index is left available only so the declared PyPI core dep (numpy) can
        # resolve. No other Ugence/monorepo package is installed.
        inst = _run([str(py), "-m", "pip", "install", "--quiet",
                     "--find-links", str(dist_dir), DIST_NAME], env=clean_env)
        c.check("install_wheel_only", inst.returncode == 0, inst.stderr.strip()[-200:] if inst.returncode else "")

        pc = _run([str(py), "-m", "pip", "check"], env=clean_env)
        c.check("pip_check", pc.returncode == 0, pc.stdout.strip() + pc.stderr.strip())

        # Version via importlib.metadata.
        ver = _run([str(py), "-I", "-c",
                    "import importlib.metadata as m;print(m.version('%s'))" % DIST_NAME],
                   cwd=str(work), env=clean_env)
        got_ver = ver.stdout.strip()
        c.check("metadata_version", got_ver == EXPECTED_VERSION, f"got={got_ver!r}")

        # Import + no-monorepo-path + demo + JSON + version, all in one isolated run.
        probe = r"""
import json, sys
import importlib.util as _iu
import ugence_cloud_scaling_controller as U
from ugence_cloud_scaling_controller import CloudScalingController, ScalingObservation
out = {}
out["version"] = U.__version__
out["module_file"] = U.__file__
# deterministic demo via CLI fixture path (single evaluate)
c = CloudScalingController()
rec = c.recommend(ScalingObservation(metrics={"cpu":0.92,"memory":0.88,"latency_p99":0.81,
                  "error_rate":0.2,"queue_depth":0.7}, current_replicas=4, phase="peak",
                  correlation_id="verify-1"))
d = rec.to_dict()
out["recommendation"] = d["recommendation"]
out["advisory_only"] = d["advisory_only"]
out["actuation_performed"] = d["actuation_performed"]
out["correlation_id"] = d["correlation_id"]
out["json_ok"] = json.loads(rec.to_json())["schema_version"] == "1.0"
# forbidden imports present after a full cycle?
forbidden = %r + %r + %r
out["forbidden_importable"] = [m for m in forbidden if _iu.find_spec(m.split(".")[0]) is not None]
# legacy namespaces must NOT be importable from the wheel-only install
out["legacy_cloud_controller_importable"] = _iu.find_spec("cloud_controller") is not None
print(json.dumps(out))
""" % (FORBIDDEN_UGENCE, FORBIDDEN_CLOUD_SDK, FORBIDDEN_CORE_EXTRAS)
        pr = _run([str(py), "-I", "-c", probe], cwd=str(work), env=clean_env)
        c.check("isolated_probe_ran", pr.returncode == 0, pr.stderr.strip()[-300:] if pr.returncode else "")
        probe_out = {}
        if pr.returncode == 0:
            probe_out = json.loads(pr.stdout.strip().splitlines()[-1])
            c.check("import_canonical_package", probe_out.get("version") == EXPECTED_VERSION)
            mod_file = probe_out.get("module_file", "")
            c.check("no_monorepo_path_in_module", str(PKG) not in mod_file and "site-packages" in mod_file,
                    mod_file)
            c.check("demo_executes", bool(probe_out.get("recommendation")))
            c.check("advisory_only_invariant", probe_out.get("advisory_only") is True
                    and probe_out.get("actuation_performed") is False)
            c.check("json_serialization", probe_out.get("json_ok") is True)
            c.check("correlation_id_preserved", probe_out.get("correlation_id") == "verify-1")
            c.check("no_forbidden_packages_installed", not probe_out.get("forbidden_importable"),
                    f"present={probe_out.get('forbidden_importable')}")
            c.check("legacy_imports_not_shipped_in_wheel",
                    probe_out.get("legacy_cloud_controller_importable") is False)

        # CLI console-script smoke (version + demo + evaluate via stdin).
        cli_ver = _run([str(script), "version"], cwd=str(work), env=clean_env)
        c.check("cli_version", cli_ver.returncode == 0 and EXPECTED_VERSION in cli_ver.stdout)
        cli_demo = _run([str(script), "demo"], cwd=str(work), env=clean_env)
        demo_ok = cli_demo.returncode == 0 and '"advisory_only": true' in cli_demo.stdout
        c.check("cli_demo", demo_ok, cli_demo.stderr.strip()[-160:] if not demo_ok else "")
        cli_eval = _run([str(script), "evaluate", "--input", "-"], cwd=str(work),
                        env=clean_env, input='{"metrics":{"cpu":0.9},"current_replicas":3}')
        c.check("cli_evaluate", cli_eval.returncode == 0 and '"schema_version": "1.0"' in cli_eval.stdout)
        cli_bad = _run([str(script), "evaluate", "--input", "-"], cwd=str(work),
                       env=clean_env, input="{not json")
        c.check("cli_nonzero_on_invalid", cli_bad.returncode != 0)

        # Single implementation copy inside the installed site-packages.
        sp = _run([str(py), "-I", "-c",
                   "import ugence_cloud_scaling_controller as U, pathlib, json;"
                   "p=pathlib.Path(U.__file__).parent;"
                   "print(json.dumps([str(x.relative_to(p)) for x in p.rglob('controller.py')]))"],
                  cwd=str(work), env=clean_env)
        installed_controllers = json.loads(sp.stdout.strip()) if sp.returncode == 0 else ["<error>"]
        c.check("installed_single_implementation", installed_controllers == ["controller.py"],
                f"found={installed_controllers}")

        # Dependency audit from the installed distribution metadata.
        dep = _run([str(py), "-I", "-c",
                    "import importlib.metadata as m, json;"
                    "d=m.distribution('%s');"
                    "print(json.dumps({'requires': d.requires or []}))" % DIST_NAME],
                   cwd=str(work), env=clean_env)
        requires = json.loads(dep.stdout.strip())["requires"] if dep.returncode == 0 else []
        # Core (non-extra) requirements only.
        core_reqs = [r for r in requires if "extra ==" not in r]
        c.check("core_dependency_is_numpy_only",
                all("numpy" in r.lower() for r in core_reqs) and len(core_reqs) >= 1,
                f"core_reqs={core_reqs}")

    dependency_audit = {
        "distribution": DIST_NAME,
        "declared_requirements": requires,
        "core_requirements": core_reqs,
        "forbidden_ugence_checked": FORBIDDEN_UGENCE,
        "forbidden_cloud_sdk_checked": FORBIDDEN_CLOUD_SDK,
        "forbidden_core_extras_checked": FORBIDDEN_CORE_EXTRAS,
        "forbidden_importable_in_clean_env": probe_out.get("forbidden_importable", None),
    }

    _finalize(c, evidence, package_inventory, dependency_audit, build_root)
    return 0 if c.ok else 1


def _finalize(c: "Checks", evidence, package_inventory, dependency_audit, build_root):
    evidence["checks"] = c.results
    evidence["verdict"] = "VERIFIED" if c.ok else "FAILED"
    ARTIFACTS.mkdir(exist_ok=True)
    (ARTIFACTS / "distribution_verification.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True))
    if package_inventory:
        (ARTIFACTS / "package_inventory.json").write_text(
            json.dumps(package_inventory, indent=2, sort_keys=True))
    if dependency_audit:
        (ARTIFACTS / "dependency_audit.json").write_text(
            json.dumps(dependency_audit, indent=2, sort_keys=True))
    # Add self-hashes for the evidence artifacts.
    hashes = {p.name: _sha256(p) for p in sorted(ARTIFACTS.glob("*.json"))}
    (ARTIFACTS / "evidence_sha256.json").write_text(json.dumps(hashes, indent=2, sort_keys=True))
    shutil.rmtree(build_root, ignore_errors=True)
    print("\n" + ("DISTRIBUTION VERIFIED" if c.ok else "DISTRIBUTION VERIFICATION FAILED"))
    print(f"evidence: {ARTIFACTS}/distribution_verification.json")


if __name__ == "__main__":
    sys.exit(main())
