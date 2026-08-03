#!/usr/bin/env python3
"""Independent-distribution verifier for ``ugence-ai-hiring``.

Proves the wheel is genuinely independent rather than a copy that still leans on
the monorepo:

1. Build the audited Ugence dependency wheels + this package's wheel & sdist into
   a temporary wheelhouse (reproducible: SOURCE_DATE_EPOCH pinned).
2. Install the wheel into a clean venv from the wheelhouse (``--find-links``);
   ``pydantic`` is the only third-party runtime dependency resolved from the index.
3. From a directory OUTSIDE the repository, import ``ugence_ai_hiring`` and the
   ``ai_hiring`` compatibility facade, and run ``version`` / ``verify`` / ``demo``.
4. Run the packaged test suite against the INSTALLED package (no repo source path).
5. Audit wheel contents (facade + canonical present; no tests, secrets, build
   artifacts, Hybrid LLM, or Cloud Scaling files).
6. Rebuild the wheel and assert bit-for-bit reproducibility.

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
DEP_PACKAGES = [
    REPO / "packages" / "governance-contracts",
    REPO / "packages" / "governance-provider-framework",
    REPO / "packages" / "capabilities" / "decision-authority",
]


def run(cmd, **kw):
    kw.setdefault("check", True)
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
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


def main() -> int:
    report: dict = {"distribution": "ugence-ai-hiring", "checks": {}}
    env = dict(os.environ)
    env["SOURCE_DATE_EPOCH"] = source_date_epoch()

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        wheelhouse = tmp / "wheelhouse"
        wheelhouse.mkdir()
        build2 = tmp / "build2"
        build2.mkdir()

        # 1. Build dependency wheels + this package.
        for dep in DEP_PACKAGES:
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

        # 2. Reproducibility (wheel bit-for-bit).
        wheel2 = next(build2.glob("ugence_ai_hiring-*.whl"))
        report["checks"]["wheel_reproducible_bit_for_bit"] = sha256(wheel) == sha256(wheel2)

        # 3. Wheel-content audit.
        names = zipfile.ZipFile(wheel).namelist()
        tops = sorted({n.split("/")[0] for n in names})
        forbidden = [n for n in names if re.search(
            r"(^|/)tests?/|hybrid|cloud_controller|cloud_scaling|\.env|secret|\.pyc$|"
            r"__pycache__", n, re.I)]
        report["checks"]["wheel_has_canonical_and_facade"] = (
            "ugence_ai_hiring" in tops and "ai_hiring" in tops)
        report["checks"]["wheel_has_no_forbidden_members"] = not forbidden
        report["wheel_top_level"] = tops
        if forbidden:
            report["wheel_forbidden_members"] = forbidden[:20]

        # 4. Clean-venv install from wheelhouse.
        venv_dir = tmp / "venv"
        venv.EnvBuilder(with_pip=True).create(venv_dir)
        vpy = venv_dir / "bin" / "python"
        run([str(vpy), "-m", "pip", "install", "--upgrade", "pip"], env=env)
        run([str(vpy), "-m", "pip", "install", "--find-links", str(wheelhouse),
             "ugence-ai-hiring"], env=env)
        run([str(vpy), "-m", "pip", "install", "pytest"], env=env)

        # 5. Out-of-root imports + CLI (cwd = tmp, outside the repo).
        code = ("import ugence_ai_hiring, ai_hiring;"
                "assert ugence_ai_hiring.__version__;"
                "assert ai_hiring.build_in_memory_platform is ugence_ai_hiring.build_in_memory_platform;"
                "assert ugence_ai_hiring.version_info().production_certified is False;"
                "print('IMPORTS_OK')")
        r = run([str(vpy), "-c", code], cwd=str(tmp), env=env)
        report["checks"]["out_of_root_imports"] = "IMPORTS_OK" in r.stdout
        for sub in ("version", "verify", "demo"):
            r = run([str(vpy), "-m", "ugence_ai_hiring", sub], cwd=str(tmp), env=env)
            report["checks"][f"cli_{sub}"] = (r.returncode == 0)

        # 6. Installed-package test suite from OUTSIDE the repo.
        iso = tmp / "iso_tests"
        run(["cp", "-r", str(PKG / "tests"), str(iso)])
        r = run([str(vpy), "-m", "pytest", str(iso), "-q", "-p", "no:cacheprovider"],
                cwd=str(tmp), env=env, check=False)
        report["checks"]["installed_tests_pass"] = (r.returncode == 0)
        m = re.search(r"(\d+) passed", r.stdout)
        report["installed_tests_passed"] = int(m.group(1)) if m else None
        if r.returncode != 0:
            report["installed_tests_tail"] = r.stdout[-1500:]

    ok = all(report["checks"].values())
    report["result"] = "INDEPENDENT_PACKAGE_VERIFIED" if ok else "FAILED"
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
