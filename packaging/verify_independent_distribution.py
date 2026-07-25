#!/usr/bin/env python3
"""Reproducible proof that decision-governance builds/installs/consumes independently.

This harness deliberately does NOT trust the monorepo source tree — it builds the
distribution, installs it into a fresh virtual environment (no system site
packages), and runs a third-party consumer from a working directory that does not
contain the kernel source. That is the only way to catch packaging defects that a
`pip install -e .` checkout would otherwise mask.

Steps (each must pass):

  1. build the independent decision-governance wheel + sdist;
  2. build the root symbolu wheel;
  3. byte-compare the packaged ``decision_governance/`` kernel files across both
     wheels — they must be identical (no drift);
  4. create an isolated venv and install ONLY the independent wheel;
  5. assert version 1.0.0 and that ai_hiring / domains / applications are absent;
  6. run the external consumer (public API only) to a RECONCILED lifecycle.

Run:  python packaging/verify_independent_distribution.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DGM_BUILD = REPO / "packaging" / "decision-governance"
CONSUMER = REPO / "packaging" / "external_consumer"


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def _kernel_hashes(wheel: Path) -> dict[str, str]:
    with zipfile.ZipFile(wheel) as z:
        return {
            n: hashlib.sha256(z.read(n)).hexdigest()
            for n in z.namelist()
            if n.startswith("decision_governance/") and n.endswith(".py")
            and "/tests/" not in n
        }


def main() -> int:
    print("[1/6] build independent decision-governance wheel + sdist")
    _run([sys.executable, "-m", "build", str(DGM_BUILD)])
    dgm_wheel = _latest(DGM_BUILD / "dist", "decision_governance-*.whl")
    _latest(DGM_BUILD / "dist", "decision_governance-*.tar.gz")  # sdist exists

    print("[2/6] build root symbolu wheel")
    _run([sys.executable, "-m", "build", "--wheel", str(REPO)])
    root_wheel = _latest(REPO / "dist", "symbolu-*.whl")

    print("[3/6] byte-compare kernel files across the two wheels")
    r, i = _kernel_hashes(root_wheel), _kernel_hashes(dgm_wheel)
    assert set(r) == set(i), f"kernel file set differs: {set(r) ^ set(i)}"
    diffs = [n for n in r if r[n] != i[n]]
    assert not diffs, f"kernel content drift: {diffs}"
    print(f"      {len(i)} kernel files byte-identical")

    print("[4/6] create isolated venv and install ONLY the independent wheel")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet", str(dgm_wheel)])

        print("[5/6] assert version + absence of consuming layers")
        check = (
            "import importlib.util, decision_governance as d; "
            "assert d.__version__=='1.0.0', d.__version__; "
            "import decision_governance.api, decision_governance.conformance; "
            "missing=[p for p in ('ai_hiring','domains','applications') "
            "if importlib.util.find_spec(p) is not None]; "
            "assert not missing, missing; print('version+isolation OK')"
        )
        # cwd is the consumer dir (contains no kernel source) so '' cannot leak it.
        _run([str(py), "-c", check], cwd=str(CONSUMER))

        print("[6/6] run external consumer (public API only)")
        _run([str(py), "-c",
              "import consumer; print('consumer lifecycle:', consumer.run())"],
             cwd=str(CONSUMER))

    print("\nINDEPENDENT DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
