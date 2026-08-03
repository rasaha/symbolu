#!/usr/bin/env python3
"""Independent-distribution verifier for ``ugence-ai-hiring`` (canonical-provider matrix).

Proves the wheel is genuinely independent AND that its optional TAP / ActionGate
dependencies are normalized onto the canonical Ugence provider distributions, while
every compatibility guarantee is preserved. It builds a local wheelhouse of the
audited Ugence dependency closure plus this package's wheel & sdist, then runs a
matrix of CLEAN virtualenvs (no monorepo source path, no repo-wide PYTHONPATH),
each reported separately:

  core_only          ugence-ai-hiring                      (no providers)
  tap_only           ugence-ai-hiring[tap]                 (canonical TAP only)
  actiongate_only    ugence-ai-hiring[actiongate]          (canonical ActionGate only)
  combined           ugence-ai-hiring[tap,actiongate]      (both canonical peers)
  legacy_deployment  ugence-ai-hiring + dgm-* compat wheels (old deployment shape)

For each it proves the relevant subset of: clean import outside the repo; the
default in-memory platform; CLI version/verify/demo; canonical adapter import;
legacy adapter-module import; loaders fail closed when a provider is absent; the
canonical provider class is loaded (object identity ==
``ugence_*_provider.provider.*``); the legacy adapter path returns the identical
class/functions; peer independence (TAP-absent / ActionGate-absent as expected);
the dgm-* legacy wheels are never pulled by AI Hiring itself yet still resolve to
the canonical providers when a deployment installs them; and ``pip check`` passes.

It also audits the built wheel (canonical + ai_hiring facade present; no tests /
TAP / ActionGate / Hybrid LLM / Cloud Scaling / secrets bundled), audits the wheel
METADATA (canonical Requires-Dist under the extras; no dgm-* requirement), runs the
installed package test suite from outside the repo, and asserts bit-for-bit wheel
reproducibility.

Exit code 0 on success. Prints a JSON report to stdout.

    python packages/products/ai-hiring/scripts/verify_ai_hiring_distribution.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]

# Audited dependency closure to build into the wheelhouse (canonical providers
# included; the dgm-* compatibility wheels are built only for the legacy-deployment
# scenario — AI Hiring itself never declares them).
DEP_PACKAGES = {
    "ugence-governance-contracts": REPO / "packages" / "governance-contracts",
    "ugence-governance-provider-framework": REPO / "packages" / "governance-provider-framework",
    "ugence-decision-authority": REPO / "packages" / "capabilities" / "decision-authority",
    "ugence-tap-provider": REPO / "packages" / "providers" / "tap",
    "ugence-actiongate-provider": REPO / "packages" / "providers" / "actiongate",
}
LEGACY_COMPAT_PACKAGES = {
    "dgm-tap-provider": REPO / "packaging" / "dgm-tap-provider",
    "dgm-actiongate-provider": REPO / "packaging" / "dgm-actiongate-provider",
    # Transitive compat wheel: the dgm-* wheels pull the provider
    # ``[decision-authority]`` extra, which reaches the framework ``[adapters]``
    # extra, which requires the legacy ``decision-governance==1.0.0`` distribution
    # (a logic-free re-export of ugence-decision-authority). Built so the
    # legacy-deployment closure resolves offline; AI Hiring never declares it.
    "decision-governance": REPO / "packaging" / "decision-governance",
}

# Never leak a repo-relative PYTHONPATH into the clean venvs: it would make pip
# report packages "already satisfied" and make imports resolve against the source
# tree instead of the installed wheels.
_CLEAN_ENV = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}


def run(cmd, **kw):
    kw.setdefault("check", True)
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    kw.setdefault("env", _CLEAN_ENV)
    return subprocess.run(cmd, **kw)


def source_date_epoch() -> str:
    try:
        return run(["git", "-C", str(REPO), "show", "-s", "--format=%ct", "HEAD"]).stdout.strip()
    except Exception:
        return "1700000000"


def build(pkg_dir: Path, out: Path, env: dict) -> None:
    run([sys.executable, "-m", "build", str(pkg_dir), "-o", str(out)], env=env)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sdist_content_map(path: Path) -> dict:
    """Map each regular file in the sdist to a content hash (ignoring tar/gzip
    metadata like mtime/uid/gid that legitimately vary build-to-build)."""
    import tarfile

    out = {}
    with tarfile.open(path, "r:gz") as tf:
        for m in sorted(tf.getmembers(), key=lambda x: x.name):
            if m.isfile():
                fh = tf.extractfile(m)
                out[m.name] = hashlib.sha256(fh.read()).hexdigest() if fh else ""
    return out


def classify_reproducibility(a: Path, b: Path, *, is_sdist: bool) -> str:
    if sha256(a) == sha256(b):
        return "BIT_FOR_BIT_REPRODUCIBLE"
    if is_sdist and _sdist_content_map(a) == _sdist_content_map(b):
        return "CONTENT_REPRODUCIBLE"
    return "NOT_REPRODUCIBLE"


def make_venv(tmp: Path, name: str) -> Path:
    vdir = tmp / f"venv_{name}"
    venv.EnvBuilder(with_pip=True, clear=True).create(vdir)
    py = vdir / "bin" / "python"
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"], env=_CLEAN_ENV)
    return py


# --- In-venv probe programs (run outside the repo) ---------------------------

_CORE_IMPORT = (
    "import ugence_ai_hiring, ai_hiring;"
    "assert ugence_ai_hiring.__version__ == '0.1.1', ugence_ai_hiring.__version__;"
    "assert ai_hiring.build_in_memory_platform is ugence_ai_hiring.build_in_memory_platform;"
    "assert ugence_ai_hiring.version_info().production_certified is False;"
    "p = ugence_ai_hiring.build_in_memory_platform();"
    "assert type(p).__name__ == 'HiringPlatform';"
    "print('CORE_OK')"
)

# Import both adapter module names without touching the providers; assert no
# concrete provider module is loaded as a side effect.
_ADAPTER_IMPORT_NO_LOAD = (
    "import sys;"
    "import ugence_ai_hiring.integrations.tap_adapter, "
    "ugence_ai_hiring.integrations.actiongate_adapter, "
    "ugence_ai_hiring.integrations.tap_legacy_adapter, "
    "ugence_ai_hiring.integrations.actiongate_legacy_adapter;"
    "leak=[m for m in ('ugence_tap_provider','ugence_actiongate_provider',"
    "'tap_provider','actiongate_provider') if m in sys.modules];"
    "print('ADAPTER_IMPORT_OK' if not leak else 'LEAK='+','.join(leak))"
)

_LOADERS_FAIL_CLOSED = (
    "from ugence_ai_hiring.integrations import ProviderUnavailable, LegacyProviderUnavailable;"
    "assert LegacyProviderUnavailable is ProviderUnavailable;"
    "import ugence_ai_hiring.integrations.tap_adapter as t;"
    "import ugence_ai_hiring.integrations.actiongate_adapter as a;"
    "n=0\n"
    "try:\n t.load_tap_provider_cls()\nexcept ProviderUnavailable:\n n+=1\n"
    "try:\n a.load_actiongate_provider_cls()\nexcept ProviderUnavailable:\n n+=1\n"
    "print('FAIL_CLOSED_OK' if n==2 else 'FAIL_CLOSED=%d'%n)"
)

_TAP_CANONICAL_IDENTITY = (
    "import ugence_tap_provider.provider as canon;"
    "import ugence_ai_hiring.integrations.tap_adapter as t;"
    "import ugence_ai_hiring.integrations.tap_legacy_adapter as tl;"
    "assert t.load_tap_provider_cls() is canon.TAPProvider;"
    "assert tl.load_tap_provider_cls() is canon.TAPProvider;"
    "assert tl.load_tap_provider_cls is t.load_tap_provider_cls;"
    "assert tl.build_claim_assertion_evaluator is t.build_claim_assertion_evaluator;"
    "print('TAP_IDENTITY_OK')"
)

_ACTIONGATE_CANONICAL_IDENTITY = (
    "import ugence_actiongate_provider.provider as canon;"
    "import ugence_ai_hiring.integrations.actiongate_adapter as a;"
    "import ugence_ai_hiring.integrations.actiongate_legacy_adapter as al;"
    "assert a.load_actiongate_provider_cls() is canon.ActionGateProvider;"
    "assert al.load_actiongate_provider_cls() is canon.ActionGateProvider;"
    "assert al.load_actiongate_provider_cls is a.load_actiongate_provider_cls;"
    "assert al.build_action_authorization_integration is a.build_action_authorization_integration;"
    "print('ACTIONGATE_IDENTITY_OK')"
)


def _mod_present(py: Path, module: str) -> bool:
    r = run([str(py), "-c", f"import importlib.util,sys;"
                             f"sys.exit(0 if importlib.util.find_spec('{module}') else 1)"],
            check=False)
    return r.returncode == 0


def _pip_check(py: Path) -> bool:
    return run([str(py), "-m", "pip", "check"], check=False).returncode == 0


def _probe(py: Path, code: str, token: str, cwd: Path) -> bool:
    r = run([str(py), "-c", code], cwd=str(cwd), check=False)
    ok = token in r.stdout
    if not ok:
        print(f"    probe[{token}] FAILED: {r.stdout.strip()} {r.stderr.strip()[-400:]}", file=sys.stderr)
    return ok


def scenario_core_only(py: Path, tmp: Path, wheelhouse: Path) -> dict:
    run([str(py), "-m", "pip", "install", "--find-links", str(wheelhouse), "ugence-ai-hiring"])
    s = {}
    s["core_import_and_platform"] = _probe(py, _CORE_IMPORT, "CORE_OK", tmp)
    s["adapter_import_no_provider_load"] = _probe(py, _ADAPTER_IMPORT_NO_LOAD, "ADAPTER_IMPORT_OK", tmp)
    s["loaders_fail_closed"] = _probe(py, _LOADERS_FAIL_CLOSED, "FAIL_CLOSED_OK", tmp)
    s["tap_provider_absent"] = not _mod_present(py, "ugence_tap_provider")
    s["actiongate_provider_absent"] = not _mod_present(py, "ugence_actiongate_provider")
    for sub in ("version", "verify", "demo"):
        s[f"cli_{sub}"] = run([str(py), "-m", "ugence_ai_hiring", sub], cwd=str(tmp),
                              check=False).returncode == 0
    s["pip_check"] = _pip_check(py)
    return s


def scenario_tap_only(py: Path, tmp: Path, wheelhouse: Path) -> dict:
    run([str(py), "-m", "pip", "install", "--find-links", str(wheelhouse), "ugence-ai-hiring[tap]"])
    s = {}
    s["ugence_tap_provider_installed"] = _mod_present(py, "ugence_tap_provider")
    s["dgm_tap_provider_not_installed"] = (
        run([str(py), "-m", "pip", "show", "dgm-tap-provider"], check=False).returncode != 0
    )
    s["actiongate_provider_absent"] = not _mod_present(py, "ugence_actiongate_provider")
    s["tap_class_identity_and_legacy_path"] = _probe(py, _TAP_CANONICAL_IDENTITY, "TAP_IDENTITY_OK", tmp)
    s["core_import"] = _probe(py, _CORE_IMPORT, "CORE_OK", tmp)
    s["pip_check"] = _pip_check(py)
    return s


def scenario_actiongate_only(py: Path, tmp: Path, wheelhouse: Path) -> dict:
    run([str(py), "-m", "pip", "install", "--find-links", str(wheelhouse),
         "ugence-ai-hiring[actiongate]"])
    s = {}
    s["ugence_actiongate_provider_installed"] = _mod_present(py, "ugence_actiongate_provider")
    s["dgm_actiongate_provider_not_installed"] = (
        run([str(py), "-m", "pip", "show", "dgm-actiongate-provider"], check=False).returncode != 0
    )
    s["tap_provider_absent"] = not _mod_present(py, "ugence_tap_provider")
    s["actiongate_class_identity_and_legacy_path"] = _probe(
        py, _ACTIONGATE_CANONICAL_IDENTITY, "ACTIONGATE_IDENTITY_OK", tmp)
    s["core_import"] = _probe(py, _CORE_IMPORT, "CORE_OK", tmp)
    s["pip_check"] = _pip_check(py)
    return s


def scenario_combined(py: Path, tmp: Path, wheelhouse: Path) -> dict:
    run([str(py), "-m", "pip", "install", "--find-links", str(wheelhouse),
         "ugence-ai-hiring[tap,actiongate]"])
    s = {}
    s["both_canonical_installed"] = (
        _mod_present(py, "ugence_tap_provider") and _mod_present(py, "ugence_actiongate_provider"))
    s["neither_dgm_installed"] = (
        run([str(py), "-m", "pip", "show", "dgm-tap-provider"], check=False).returncode != 0
        and run([str(py), "-m", "pip", "show", "dgm-actiongate-provider"], check=False).returncode != 0)
    s["tap_identity"] = _probe(py, _TAP_CANONICAL_IDENTITY, "TAP_IDENTITY_OK", tmp)
    s["actiongate_identity"] = _probe(py, _ACTIONGATE_CANONICAL_IDENTITY, "ACTIONGATE_IDENTITY_OK", tmp)
    s["core_import_no_eager_provider_load"] = _probe(py, _ADAPTER_IMPORT_NO_LOAD, "ADAPTER_IMPORT_OK", tmp)
    s["pip_check"] = _pip_check(py)
    return s


def scenario_legacy_deployment(py: Path, tmp: Path, wheelhouse: Path) -> dict:
    # AI Hiring core WITHOUT its extras, plus the dgm-* compatibility wheels — the
    # shape of an old deployment. The dgm-* wheels pull in the canonical providers.
    run([str(py), "-m", "pip", "install", "--find-links", str(wheelhouse),
         "ugence-ai-hiring", "dgm-tap-provider", "dgm-actiongate-provider"])
    s = {}
    s["canonical_providers_pulled_by_dgm"] = (
        _mod_present(py, "ugence_tap_provider") and _mod_present(py, "ugence_actiongate_provider"))
    s["legacy_namespace_facades_available"] = (
        _mod_present(py, "tap_provider") and _mod_present(py, "actiongate_provider"))
    s["canonical_adapters_load_canonical_classes"] = (
        _probe(py, _TAP_CANONICAL_IDENTITY, "TAP_IDENTITY_OK", tmp)
        and _probe(py, _ACTIONGATE_CANONICAL_IDENTITY, "ACTIONGATE_IDENTITY_OK", tmp))
    s["provider_facade_identity"] = _probe(
        py,
        "import tap_provider.provider as f1, ugence_tap_provider.provider as c1;"
        "import actiongate_provider.provider as f2, ugence_actiongate_provider.provider as c2;"
        "assert f1.TAPProvider is c1.TAPProvider;"
        "assert f2.ActionGateProvider is c2.ActionGateProvider;"
        "print('FACADE_IDENTITY_OK')",
        "FACADE_IDENTITY_OK", tmp)
    s["pip_check"] = _pip_check(py)
    return s


def audit_wheel_contents(wheel: Path) -> dict:
    names = zipfile.ZipFile(wheel).namelist()
    tops = sorted({n.split("/")[0] for n in names})
    forbidden = [n for n in names if re.search(
        r"(^|/)tests?/|hybrid|cloud_controller|cloud_scaling|\.env|secret|\.pyc$|"
        r"__pycache__|tap_provider|actiongate_provider", n, re.I)]
    return {
        "wheel_top_level": tops,
        "has_canonical_and_facade": ("ugence_ai_hiring" in tops and "ai_hiring" in tops),
        "no_forbidden_members": not forbidden,
        "no_provider_impl_bundled": not any(
            "tap_provider" in n or "actiongate_provider" in n for n in names),
        "forbidden_members": forbidden[:20],
    }


def audit_wheel_metadata(wheel: Path) -> dict:
    z = zipfile.ZipFile(wheel)
    meta_name = [n for n in z.namelist() if n.endswith("METADATA")][0]
    text = z.read(meta_name).decode()
    reqs = [ln for ln in text.splitlines() if ln.startswith("Requires-Dist")]
    joined = "\n".join(reqs)
    return {
        "requires_dist": reqs,
        "tap_extra_canonical": bool(re.search(
            r'Requires-Dist:\s*ugence-tap-provider.*extra == "tap"', joined)),
        "actiongate_extra_canonical": bool(re.search(
            r'Requires-Dist:\s*ugence-actiongate-provider.*extra == "actiongate"', joined)),
        "no_dgm_tap_requirement": "dgm-tap-provider" not in joined,
        "no_dgm_actiongate_requirement": "dgm-actiongate-provider" not in joined,
        "tap_actiongate_not_core": not any(
            (("tap-provider" in r or "actiongate-provider" in r) and "extra ==" not in r)
            for r in reqs),
        "legacy_dgm_requirement_count": sum(
            r.count("dgm-tap-provider") + r.count("dgm-actiongate-provider") for r in reqs),
    }


def main() -> int:
    report: dict = {"distribution": "ugence-ai-hiring", "scenarios": {}, "audits": {}}
    env = dict(os.environ)
    env["SOURCE_DATE_EPOCH"] = source_date_epoch()

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        wheelhouse = tmp / "wheelhouse"
        wheelhouse.mkdir()
        build2 = tmp / "build2"
        build2.mkdir()

        print("[1] building dependency + product wheels", file=sys.stderr)
        for dep in DEP_PACKAGES.values():
            build(dep, wheelhouse, env)
        for dep in LEGACY_COMPAT_PACKAGES.values():
            build(dep, wheelhouse, env)
        build(PKG, wheelhouse, env)
        build(PKG, build2, env)  # second build for reproducibility

        wheels = sorted(wheelhouse.glob("ugence_ai_hiring-*.whl"))
        sdists = sorted(wheelhouse.glob("ugence_ai_hiring-*.tar.gz"))
        assert wheels and sdists, "wheel/sdist not built"
        wheel = wheels[0]
        report["wheel"] = wheel.name
        report["wheel_sha256"] = sha256(wheel)
        report["sdist"] = sdists[0].name
        report["sdist_sha256"] = sha256(sdists[0])

        wheel2 = next(build2.glob("ugence_ai_hiring-*.whl"))
        sdist2 = next(build2.glob("ugence_ai_hiring-*.tar.gz"))
        report["wheel_reproducibility"] = classify_reproducibility(wheel, wheel2, is_sdist=False)
        report["sdist_reproducibility"] = classify_reproducibility(sdists[0], sdist2, is_sdist=True)
        # Bit-for-bit for the wheel is required; the sdist must be at least
        # content-reproducible (tar/gzip metadata may legitimately vary).
        report["audits"]["wheel_reproducible"] = (
            report["wheel_reproducibility"] == "BIT_FOR_BIT_REPRODUCIBLE")
        report["audits"]["sdist_reproducible"] = (
            report["sdist_reproducibility"] in ("BIT_FOR_BIT_REPRODUCIBLE", "CONTENT_REPRODUCIBLE"))

        print("[2] auditing wheel contents + metadata", file=sys.stderr)
        report["audits"]["contents"] = audit_wheel_contents(wheel)
        report["audits"]["metadata"] = audit_wheel_metadata(wheel)

        print("[3] scenario: core_only", file=sys.stderr)
        report["scenarios"]["core_only"] = scenario_core_only(make_venv(tmp, "core"), tmp, wheelhouse)
        print("[4] scenario: tap_only", file=sys.stderr)
        report["scenarios"]["tap_only"] = scenario_tap_only(make_venv(tmp, "tap"), tmp, wheelhouse)
        print("[5] scenario: actiongate_only", file=sys.stderr)
        report["scenarios"]["actiongate_only"] = scenario_actiongate_only(
            make_venv(tmp, "ag"), tmp, wheelhouse)
        print("[6] scenario: combined", file=sys.stderr)
        report["scenarios"]["combined"] = scenario_combined(make_venv(tmp, "combined"), tmp, wheelhouse)
        print("[7] scenario: legacy_deployment", file=sys.stderr)
        report["scenarios"]["legacy_deployment"] = scenario_legacy_deployment(
            make_venv(tmp, "legacy"), tmp, wheelhouse)

        print("[8] installed-package test suite (core venv, outside the repo)", file=sys.stderr)
        core_py = tmp / "venv_core" / "bin" / "python"
        run([str(core_py), "-m", "pip", "install", "pytest"], env=_CLEAN_ENV)
        iso = tmp / "iso_tests"
        run(["cp", "-r", str(PKG / "tests"), str(iso)])
        r = run([str(core_py), "-m", "pytest", str(iso), "-q", "-p", "no:cacheprovider"],
                cwd=str(tmp), check=False)
        report["audits"]["installed_tests_pass"] = (r.returncode == 0)
        m = re.search(r"(\d+) passed", r.stdout)
        report["installed_tests_passed"] = int(m.group(1)) if m else None
        if r.returncode != 0:
            report["installed_tests_tail"] = r.stdout[-2000:]

    def _all_ok(d) -> bool:
        return all(
            _all_ok(v) if isinstance(v, dict) else (v if isinstance(v, bool) else True)
            for k, v in d.items() if k not in ("forbidden_members", "requires_dist",
                                               "wheel_top_level", "legacy_dgm_requirement_count")
        )

    ok = (_all_ok(report["scenarios"]) and _all_ok(report["audits"])
          and report["audits"]["metadata"]["legacy_dgm_requirement_count"] == 0)
    report["result"] = "CANONICAL_PROVIDER_DEPENDENCIES_VERIFIED" if ok else "FAILED"
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
