#!/usr/bin/env python3
"""Reproducible proof that the canonical Decision Authority package installs and
operates as a single, self-contained capability wheel with NO other Ugence
package on the path.

Builds ``ugence-decision-authority`` only, installs it into a fresh virtualenv
with no monorepo path (pydantic — its one declared runtime dependency — resolves
from the index), then proves inside that env:

  * ``ugence_decision_authority`` imports from site-packages (v1.0.0);
  * the curated public API resolves;
  * a representative kernel record (``DecisionRecord``) loads and produces a
    stable JSON schema; the frozen reason-code vocabulary is intact;
  * ``canonical_hash`` is importable and deterministic;
  * NO sibling Ugence package (the ``decision_governance`` shim, providers,
    consumers, platform) is importable — the capability pulls nothing else in.

Run:  python packages/capabilities/decision-authority/verify_decision_authority_distribution.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parent

_CHECK = r'''
import importlib.util, json, sys

import ugence_decision_authority as uda
assert uda.__version__ == "1.0.0", uda.__version__
assert "site-packages" in uda.__file__, uda.__file__
assert not any("/symbolu" in p or "decision_governance" in p for p in sys.path), sys.path

# curated public API resolves
from ugence_decision_authority.api import services, contracts, ports, repositories, \
    vocabulary, audit, identity, policy, errors, common
from ugence_decision_authority.api.contracts import DecisionRecord, DecisionOutcome
from ugence_decision_authority.api.services import DecisionCaseService

# a representative kernel record loads and yields a stable serialization shape
schema = DecisionRecord.model_json_schema()
assert isinstance(schema, dict) and schema.get("title") == "DecisionRecord", schema.get("title")

# frozen vocabulary intact
from ugence_decision_authority.vocabulary import ReasonCode, REASON_CODE_CATALOG
assert len(list(ReasonCode)) >= 1 and REASON_CODE_CATALOG, "reason-code vocabulary missing"

# deterministic hashing helper present
from ugence_decision_authority.common import canonical_hash
assert canonical_hash({"a": 1}) == canonical_hash({"a": 1})

# NO sibling Ugence package importable in this clean env (self-contained capability)
for mod in ("decision_governance", "governance_providers", "ugence_governance_contracts",
            "actiongate_provider", "tap_provider", "ai_hiring", "domains", "applications",
            "ugence_console_api", "platform_freeze", "ugence_storygraph"):
    assert importlib.util.find_spec(mod) is None, ("sibling package present: " + mod)

print("ISOLATED SINGLE-WHEEL DECISION-AUTHORITY VERIFICATION OK")
'''


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def _foreign_members(wheel: Path) -> set[str]:
    with zipfile.ZipFile(wheel) as z:
        tops = {n.split("/", 1)[0] for n in z.namelist() if "/" in n}
    return {t for t in tops if not (t == "ugence_decision_authority" or t.endswith(".dist-info"))}


def _bundles_tests(wheel: Path) -> bool:
    with zipfile.ZipFile(wheel) as z:
        return any("/tests/" in n or n.endswith("/tests") for n in z.namelist())


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print("[1/4] build the single decision-authority wheel")
    _run([sys.executable, "-m", "build", "--wheel", str(PKG), "-o", str(findlinks)])
    wheel = _latest(findlinks, "ugence_decision_authority-*.whl")
    print(f"      built {wheel.name}")

    print("[2/4] assert the wheel bundles no foreign package and no tests")
    foreign = _foreign_members(wheel)
    assert not foreign, f"wheel bundles foreign packages: {sorted(foreign)}"
    assert not _bundles_tests(wheel), "wheel bundles tests (should be excluded)"
    print("      wheel contains only ugence_decision_authority/ + dist-info")

    print("[3/4] create an isolated venv and install ONLY this wheel (+ pydantic from index)")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet",
              "--find-links", str(findlinks), "ugence-decision-authority"])

        print("[4/4] run the isolated proof (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK], cwd=str(td))

    shutil.rmtree(findlinks, ignore_errors=True)
    print("\nISOLATED SINGLE-WHEEL DECISION-AUTHORITY DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
