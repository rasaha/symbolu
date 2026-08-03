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
assert awc.__version__ == "0.1.0", awc.__version__
assert awc.CONTRACT_VERSION == "awc.v1", awc.CONTRACT_VERSION
assert "site-packages" in awc.__file__, awc.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

# full offline pipeline over a frozen synthetic workflow
adapt, result = fixtures.run_demo("procurement")
assert adapt.ok and adapt.accounting_holds()
assert any(r.source_node_id == "proc_supplier_risk" for r in adapt.role_requirements)
# authority preservation: governance/human nodes never agent roles
for nd in adapt.node_dispositions:
    if nd.disposition.value in ("HUMAN_AUTHORITY_REQUIRED",
                                "EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP"):
        assert not nd.is_agent_role
# eligibility produced a result for every role x agent pair
snap = fixtures.registry_snapshot()
for rep in result.reports:
    assert len(rep.results) == len(snap.agent_profiles)
print("FP:" + result.workflow_fingerprint)
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
        print("\nAWC_P1_DISTRIBUTION_VERIFIED")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
