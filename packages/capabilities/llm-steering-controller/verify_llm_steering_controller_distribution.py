#!/usr/bin/env python3
"""Advisory-boundary distribution verifier for ugence-llm-steering-controller (0.1.0).

Builds wheel + sdist, inspects the PACKAGED Python source inside the wheel for any
execution / network / credential capability, installs ONLY the wheel into an isolated
venv created OUTSIDE the repository, and asserts the distribution is genuinely
advisory-only (routing recommendations, no provider execution). Generates build
provenance + SBOM bound to the actual build revision and fails on any tampered or
inconsistent evidence.

Emits CI-generated build evidence (NOT committed):
  artifacts/distribution_verification.json
  artifacts/package_inventory.json
  artifacts/dependency_audit.json
  artifacts/build_provenance.json
  artifacts/sbom.json
  artifacts/evidence_sha256.json

Exits nonzero on ANY failed assertion. On success prints:
  LLM STEERING CONTROLLER DISTRIBUTION VERIFIED
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
DIST_NAME = "ugence-llm-steering-controller"
IMPORT_NAME = "ugence_llm_steering_controller"
EXPECTED_VERSION = "0.1.0"
BASELINE_COMMIT = "cbf899043f46db171e9a9ca0f3bcdc9f42442bc1"

# Sibling Ugence packages / research trees that must never be importable from the wheel.
FORBIDDEN_UGENCE = [
    "governance_studio", "decision_governance", "actiongate", "agent_runtime",
    "hybrid_llm", "ai_hiring", "control_plane", "model_selection_pilot",
    "model_selection_experiment", "model_selection_reconciliation", "execution_gate",
]
# Provider SDKs / network libraries that must not be importable in the clean env or
# imported by packaged source.
FORBIDDEN_PROVIDER_SDK = [
    "openai", "anthropic", "boto3", "botocore", "google", "vertexai", "cohere",
    "mistralai", "requests", "httpx", "aiohttp",
]
# Source-level patterns that would indicate provider execution / credential / network use.
FORBIDDEN_SOURCE_PATTERNS = [
    r"os\.environ", r"os\.getenv", r"getenv\(", r"socket\.socket", r"\.connect\(",
    r"subprocess\.", r"\bPopen\b", r"requests\.(get|post|put|request|Session)",
    r"httpx\.", r"http\.client", r"urllib\.request", r"boto3", r"openai\.", r"anthropic\.",
    r"API_KEY", r"x-api-key", r"Bearer ", r"AWS_SECRET",
]
# Forbidden wheel path substrings (provider execution / runtime).
FORBIDDEN_WHEEL_PATH_SUBSTR = [
    "/provider.py", "/execute.py", "/executor.py", "/dispatch.py", "/invoke.py",
    "/client.py", "/adapters/", "/runtime/",
]
FORBIDDEN_WHEEL_SYMBOLS = [
    "ProviderClient", "invoke_provider", "call_provider", "execute_request",
    "run_inference", "dispatch_request", "load_credentials",
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
                "expected_version": EXPECTED_VERSION,
                "evidence_class": "CI_GENERATED_BUILD_EVIDENCE"}

    build_root = Path(tempfile.mkdtemp(prefix="lsc-dist-"))
    dist_dir = build_root / "dist"
    dist_dir.mkdir()
    print("[build] wheel + sdist")
    b = _run([sys.executable, "-m", "build", str(PKG), "-o", str(dist_dir)])
    c.check("build_wheel_and_sdist", b.returncode == 0,
            (b.stderr.strip().splitlines() or [""])[-1] if b.returncode else "")
    if b.returncode != 0:
        print(b.stderr)
        _finalize(c, evidence, {}, {}, None, None, build_root)
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
            ("test", "__pycache__", ".pyc", "secret", ".git", "conftest", "fixture"))]
    c.check("wheel_excludes_tests_caches_secrets_git_fixtures", not junk, f"junk={junk[:5]}")
    controllers = [n for n in names if n.endswith("/controller.py")]
    c.check("wheel_single_controller_copy", len(controllers) == 1, f"copies={controllers}")

    # Forbidden PATHS (provider execution / runtime)
    path_hits = [n for n in names for sub in FORBIDDEN_WHEEL_PATH_SUBSTR if sub in "/" + n]
    c.check("wheel_no_provider_execution_paths", not path_hits,
            f"hits={sorted(set(path_hits))[:6]}")

    # Forbidden SYMBOLS inside packaged source
    sym_hits = {}
    for n, src in py_sources.items():
        for sym in FORBIDDEN_WHEEL_SYMBOLS:
            if re.search(r"\b" + re.escape(sym) + r"\b", src):
                sym_hits.setdefault(sym, []).append(n)
    c.check("wheel_no_provider_execution_symbols", not sym_hits,
            f"{ {k: v[:1] for k, v in sym_hits.items()} }")

    # Forbidden provider-SDK imports inside packaged source
    import ast
    sdk_import_hits = {}
    src_pattern_hits = {}
    for n, src in py_sources.items():
        # AST import scan
        try:
            tree = ast.parse(src)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    mods = [node.module.split(".")[0]]
                for m in mods:
                    if m in FORBIDDEN_PROVIDER_SDK or m in FORBIDDEN_UGENCE or \
                       m in ("socket", "subprocess", "urllib", "http", "ssl", "asyncio",
                             "threading", "multiprocessing"):
                        sdk_import_hits.setdefault(m, []).append(n)
        # Text pattern scan (registry.py's secret-detection literals are matched by the
        # dedicated credential test, not here — these patterns target *usage*).
        for pat in FORBIDDEN_SOURCE_PATTERNS:
            if re.search(pat, src):
                src_pattern_hits.setdefault(pat, []).append(n)
    c.check("wheel_source_no_forbidden_imports", not sdk_import_hits,
            f"{ {k: v[:1] for k, v in sdk_import_hits.items()} }")
    c.check("wheel_source_no_network_or_credential_usage", not src_pattern_hits,
            f"{ {k: v[:1] for k, v in src_pattern_hits.items()} }")

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
        script = env_dir / "bin" / "ugence-llm-steering"
        clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        clean_env["PYTHONPATH"] = ""
        # Poison credential-shaped env vars: the package must ignore them entirely.
        clean_env["OPENAI_API_KEY"] = "verifier-should-not-read"
        clean_env["ANTHROPIC_API_KEY"] = "verifier-should-not-read"
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

        # Runtime probe with an audit hook that hard-fails on ANY socket/subprocess/exec,
        # proving import + recommendation open no socket and execute no provider call.
        probe = r'''
import json, sys
import importlib.util as _iu
def _hook(event, args):
    if event in ("socket.connect","socket.bind","socket.getaddrinfo",
                 "subprocess.Popen","os.system","os.exec","ssl.wrap_socket"):
        raise RuntimeError("FORBIDDEN:"+event)
sys.addaudithook(_hook)
import ugence_llm_steering_controller as U
from ugence_llm_steering_controller import recommend
out = {"version": U.__version__, "module_file": U.__file__}
reg = {"providers":[{"provider_id":"p1"},{"provider_id":"p2"}],
       "models":[{"model_id":"m1","provider_id":"p1","modalities_in":["text"],
                  "context_limit":128000,"cost_class":"low","quality_tier":"standard"},
                 {"model_id":"m2","provider_id":"p2","modalities_in":["text"],
                  "context_limit":32000,"cost_class":"high","quality_tier":"frontier"}]}
res = recommend(reg, {"task_category":"chat","quality_preference":"quality_first",
                      "requirements":{"estimated_input_tokens":2000}})
d = res.to_dict()
out["status"] = d["status"]
out["recommendation_only"] = d["recommendation_only"]
out["execution_status"] = d["execution_status"]
out["recommended_model"] = d["recommendation"]["recommended_model"]
out["deterministic"] = (res.decision_id == recommend(reg, {"task_category":"chat",
    "quality_preference":"quality_first","requirements":{"estimated_input_tokens":2000}}).decision_id)
blob = json.dumps(d)
out["leaks_env_secret"] = ("verifier-should-not-read" in blob)
forbidden = %r + %r
out["forbidden_importable"] = [m for m in forbidden if _iu.find_spec(m.split(".")[0]) is not None]
# Simulation fixture labels
from ugence_llm_steering_controller.simulation import run_suite, FIXTURE_LABELS
rep = run_suite([{"name":"x","registry":reg,"request":{"task_category":"chat"}}])
out["fixture_labels_ok"] = (rep["labels"] == FIXTURE_LABELS ==
    {"evidence_class":"FAKE_LOCAL_FIXTURE","provider_status":"NO_PROVIDER_CALLED",
     "execution_status":"NO_MODEL_EXECUTED"})
print(json.dumps(out))
''' % (FORBIDDEN_PROVIDER_SDK, FORBIDDEN_UGENCE)
        pr = _run([str(py), "-I", "-c", probe], cwd=str(work), env=clean_env)
        c.check("isolated_probe_ran_no_forbidden_events", pr.returncode == 0,
                pr.stderr.strip()[-300:] if pr.returncode else "")
        if pr.returncode == 0:
            probe_out = json.loads(pr.stdout.strip().splitlines()[-1])
            c.check("import_canonical_package", probe_out.get("version") == EXPECTED_VERSION)
            mf = probe_out.get("module_file", "")
            c.check("no_monorepo_path_in_module", str(PKG) not in mf and "site-packages" in mf, mf)
            c.check("recommendation_produced", probe_out.get("status") == "RECOMMENDED")
            c.check("recommendation_only_invariant",
                    probe_out.get("recommendation_only") is True and
                    probe_out.get("execution_status") == "NOT_EXECUTED")
            c.check("recommendation_is_deterministic", probe_out.get("deterministic") is True)
            c.check("no_env_credential_leak", probe_out.get("leaks_env_secret") is False)
            c.check("no_forbidden_packages_installed", not probe_out.get("forbidden_importable"),
                    f"present={probe_out.get('forbidden_importable')}")
            c.check("fixture_evidence_labeled", probe_out.get("fixture_labels_ok") is True)

        # CLI checks
        cli_ver = _run([str(script), "version"], cwd=str(work), env=clean_env)
        c.check("cli_version", cli_ver.returncode == 0 and EXPECTED_VERSION in cli_ver.stdout)
        cli_inspect = _run([str(script), "inspect"], cwd=str(work), env=clean_env)
        c.check("cli_inspect_advisory",
                cli_inspect.returncode == 0 and '"authority_class": "ADVISORY"' in cli_inspect.stdout and
                "NO PROVIDER REQUEST WAS EXECUTED" in cli_inspect.stderr)
        cli_verify = _run([str(script), "verify-package"], cwd=str(work), env=clean_env)
        c.check("cli_verify_package", cli_verify.returncode == 0 and
                '"verified": true' in cli_verify.stdout)

        sp = _run([str(py), "-I", "-c",
                   "import ugence_llm_steering_controller as U, pathlib, json;"
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
        c.check("core_has_no_runtime_dependencies", not core_reqs, f"core_reqs={core_reqs}")
        c.check("no_provider_sdk_in_declared_deps",
                not any(any(sdk in r.lower() for sdk in FORBIDDEN_PROVIDER_SDK) for r in requires),
                f"requires={requires}")

        # pip-audit over the (empty) runtime closure; the local package is excluded.
        freeze = _run([str(py), "-m", "pip", "freeze"], env=clean_env)
        runtime_reqs = [ln for ln in freeze.stdout.splitlines()
                        if ln and not re.match(r"^(pip|setuptools|wheel|%s)==" %
                                               re.escape(DIST_NAME), ln, re.I)]
        reqs_file = work / "runtime-reqs.txt"
        reqs_file.write_text("\n".join(runtime_reqs) + ("\n" if runtime_reqs else ""))
        audit_available = _run([str(py), "-m", "pip", "install", "--quiet", "pip-audit"],
                               env=clean_env).returncode == 0
        if audit_available and runtime_reqs:
            pa = _run([str(py), "-m", "pip_audit", "-r", str(reqs_file)], env=clean_env)
            c.check("pip_audit_clean", pa.returncode == 0, (pa.stdout + pa.stderr).strip()[-200:])
        else:
            c.check("pip_audit_empty_runtime_closure", not runtime_reqs,
                    "no third-party runtime deps to audit (stdlib only)")

    # ---- Build provenance + SBOM + fail conditions ----
    prov_path = ARTIFACTS / "build_provenance.json"
    gp = _run([sys.executable, str(PKG / "scripts" / "generate_build_provenance.py"),
               "--wheel", str(wheel), "--sdist", str(sdist), "--out", str(prov_path)])
    c.check("build_provenance_generated", gp.returncode == 0,
            gp.stderr.strip()[-200:] if gp.returncode else "")
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

    sbom_path = ARTIFACTS / "sbom.json"
    gs = _run([sys.executable, str(PKG / "scripts" / "generate_sbom.py"),
               "--wheel", str(wheel), "--out", str(sbom_path)])
    c.check("sbom_generated", gs.returncode == 0, gs.stderr.strip()[-200:] if gs.returncode else "")
    sbom = json.loads(sbom_path.read_text()) if sbom_path.exists() else {}
    c.check("sbom_zero_runtime_dependencies", sbom.get("runtime_dependency_count") == 0,
            f"count={sbom.get('runtime_dependency_count')}")

    dependency_audit = {
        "distribution": DIST_NAME,
        "declared_requirements": requires,
        "core_requirements": core_reqs,
        "forbidden_ugence_checked": FORBIDDEN_UGENCE,
        "forbidden_provider_sdk_checked": FORBIDDEN_PROVIDER_SDK,
        "forbidden_importable_in_clean_env": probe_out.get("forbidden_importable"),
    }

    _finalize(c, evidence, package_inventory, dependency_audit, provenance, sbom, build_root)
    return 0 if c.ok else 1


def _finalize(c, evidence, package_inventory, dependency_audit, provenance, sbom, build_root):
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
    hashes = {p.name: _sha256(p) for p in sorted(ARTIFACTS.glob("*.json"))
              if p.name != "evidence_sha256.json"}
    (ARTIFACTS / "evidence_sha256.json").write_text(json.dumps(hashes, indent=2, sort_keys=True))
    if build_root:
        shutil.rmtree(build_root, ignore_errors=True)
    print("\n" + ("LLM STEERING CONTROLLER DISTRIBUTION VERIFIED"
                  if c.ok else "LLM STEERING CONTROLLER DISTRIBUTION VERIFICATION FAILED"))
    print(f"evidence: {ARTIFACTS}/distribution_verification.json")


if __name__ == "__main__":
    sys.exit(main())
