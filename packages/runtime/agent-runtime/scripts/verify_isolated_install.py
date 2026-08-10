#!/usr/bin/env python3
"""Build the wheel + sdist, install into a throwaway virtualenv, and exercise the
package from the INSTALLED distribution — with no access to the monorepo source path.

Covers section-24 checks 1-4, 6, 52-54:
  * wheel builds; sdist builds;
  * installs into a clean virtualenv;
  * imports without the monorepo source path;
  * metadata correct; version accessible;
  * package tests run from the installed wheel;
  * no product package required; no hidden editable install.

Usage:  python scripts/verify_isolated_install.py
Exit 0 on success; non-zero otherwise.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]


def run(cmd, **kw):
    print(f"$ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        dist = tmp / "dist"

        # 1 & 2: build wheel + sdist
        run([sys.executable, "-m", "build", "--outdir", str(dist), str(PKG_ROOT)])
        wheels = list(dist.glob("*.whl"))
        sdists = list(dist.glob("*.tar.gz"))
        assert wheels, "no wheel built"
        assert sdists, "no sdist built"
        wheel = wheels[0]
        print(f"built wheel: {wheel.name}")
        print(f"built sdist: {sdists[0].name}")

        # 14: the wheel must contain ONLY the intended top-level package.
        import zipfile

        with zipfile.ZipFile(wheel) as zf:
            tops = {n.split("/", 1)[0] for n in zf.namelist()}
        pkg_tops = {t for t in tops if not t.endswith(".dist-info") and not t.endswith(".data")}
        assert pkg_tops == {"ugence_agent_runtime"}, f"unexpected top-level in wheel: {pkg_tops}"
        print(f"wheel top-level packages: {sorted(pkg_tops)}")

        # 3: clean virtualenv
        env_dir = tmp / "venv"
        venv.EnvBuilder(with_pip=True).create(env_dir)
        py = env_dir / "bin" / "python"

        # install ONLY the wheel (no editable, no monorepo path)
        run([str(py), "-m", "pip", "install", "--quiet", f"{wheel}[test]"])

        # 4 & 7: import + version, from a cwd with NO monorepo source on the path
        check = (
            "import ugence_agent_runtime as ar;"
            "import ugence_agent_runtime.api as api;"
            "assert ar.__version__ == '0.3.0', ar.__version__;"
            # confirm the import resolves inside site-packages, not the monorepo src
            "assert 'site-packages' in ar.__file__, ar.__file__;"
            "print('import OK', ar.__version__, ar.__file__)"
        )
        run([str(py), "-c", check], cwd=str(tmp))

        # 6: metadata correct
        meta = (
            "import importlib.metadata as m;"
            "d = m.metadata('ugence-agent-runtime');"
            "assert d['Name'] == 'ugence-agent-runtime', d['Name'];"
            "assert d['Version'] == '0.3.0', d['Version'];"
            "reqs = m.requires('ugence-agent-runtime') or [];"
            # no mandatory runtime dependency (only optional [test] extras allowed)
            "hard = [r for r in reqs if 'extra' not in r];"
            "assert not hard, hard;"
            "print('metadata OK; hard deps:', hard)"
        )
        run([str(py), "-c", meta], cwd=str(tmp))

        # 53/55: run the package test suite FROM the installed wheel, in a location
        # with NO monorepo above it. We copy ONLY the tests dir into the isolated tmp
        # tree so pytest's rootdir is tmp (not the monorepo) and no monorepo root
        # conftest is loaded — otherwise the legacy package would leak onto sys.path and
        # the isolation (and the "no monorepo fixture imported" guarantee) would be void.
        import shutil

        iso_tests = tmp / "isolated_tests"
        shutil.copytree(PKG_ROOT / "tests", iso_tests)
        run([str(py), "-m", "pip", "install", "--quiet", "pytest"])
        run([str(py), "-m", "pytest", str(iso_tests), "-q", "-p", "no:cacheprovider"],
            cwd=str(tmp))

        # run the standalone demo from the installed distribution
        run([str(py), str(PKG_ROOT / "examples" / "agent_runtime_demo.py")], cwd=str(tmp))

    print("\nISOLATED INSTALL VERIFICATION: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
