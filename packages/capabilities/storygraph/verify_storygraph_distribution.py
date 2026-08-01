#!/usr/bin/env python3
"""Reproducible proof that the StoryGraph capability installs and operates as a
single, self-contained wheel with NO other Ugence package on the path.

Builds ``ugence-storygraph`` only, installs it into a fresh virtualenv with no
system site packages and no monorepo source path, then proves inside that env:

  * ``ugence_storygraph`` imports from site-packages (not the monorepo tree);
  * version and curated public API resolve;
  * a reference StoryGraph evaluation runs (account-takeover proposed action);
  * a Policy Pack compiles and reproduces the frozen graph digest;
  * a deterministic replay reproduces the recorded report digest;
  * StoryGraph stays advisory (OBSERVE/ESCALATE/UNAVAILABLE only);
  * NO unrelated Ugence capability/product/console/research package is importable;
  * NO third-party runtime dependency was required (stdlib-only install).

Run:  python packages/capabilities/storygraph/verify_storygraph_distribution.py
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

# The in-venv proof. Public API + package data only; no monorepo path present.
# Digest anchors are the values recorded in docs/migrations/storygraph/BASELINE.md.
_CHECK = r'''
import importlib.util, json, pathlib, sys

# 1) imports from the installed wheel, not the monorepo source tree
import ugence_storygraph as usg
assert usg.__version__ == "2.0.0", usg.__version__
assert "site-packages" in usg.__file__, usg.__file__

# 2) no monorepo path leaked into sys.path
assert not any("composite_threat_detector" in p or "/symbolu" in p for p in sys.path), sys.path

# 3) NO unrelated Ugence package is importable in this clean env
for mod in ("decision_governance", "governance_providers", "actiongate_provider",
            "tap_provider", "agentic", "agent_runtime_migration", "ugence_console_api",
            "cer_v0_3", "symbolu_robotics", "composite_threat_detector",
            "experiments", "cyber_security"):
    assert importlib.util.find_spec(mod) is None, ("unrelated package present: " + mod)

# 4) no third-party runtime dep was pulled in
for tp in ("pydantic", "numpy", "torch", "pandas", "fastapi"):
    assert importlib.util.find_spec(tp) is None, ("third-party dep present: " + tp)

# 5) curated public API smoke test
from ugence_storygraph.api import (
    SequenceRiskAnalyzer, StoryGraph, evaluate_proposed_action, to_advisory_evidence,
    ACCOUNT_TAKEOVER_TRANSFER, DIGITAL_ONTOLOGY, OBSERVE, ESCALATE, UNAVAILABLE)

# 6) reference StoryGraph evaluation (account-takeover proposed action)
from ugence_storygraph import financial as F
from ugence_storygraph.storygraph import ObservedEvent
def oe(fid, eid, pos, **e): return ObservedEvent(fid, eid, pos, pos, "actor://u", dict(e))
asm = [oe(F.CRED_RESET, "r", 1, account="a1"),
       oe(F.DEVICE_NEW, "d", 2, account="a1", device="d1"),
       oe(F.BENEFICIARY_ADD, "bn", 3, account="a1", beneficiary="bob")]
prop = oe(F.TRANSFER, "x", 9, account="a1", beneficiary="bob", device="d1", amount="9000")
res = evaluate_proposed_action(asm, prop, ACCOUNT_TAKEOVER_TRANSFER)
assert res.category == "WOULD_COMPLETE_PROHIBITED_CAPABILITY", res.category
assert res.signal == "ESCALATE", res.signal                       # advisory, never binding

# 7) Policy Pack compilation smoke test — reproduces the frozen graph digest
from ugence_storygraph.policypack import compiler, reference, replay, replay_gates
b = compiler.compile_pack(reference.ACCOUNT_TAKEOVER_PACK)
assert compiler.graph_freeze_digest(b) == \
    "sha-256:6a77b8997263c40f2b6d791c9391ae562dfb51ba6e7ae04ce5da5f775cc081a8"
assert b.bundle_digest == \
    "sha-256:f6323c9275e125be0766fbc3986683aae3ece8009cad80df08278f8114896a1e"

# 8) replay smoke test — bundled fixture reproduces the recorded report digest
pp_dir = pathlib.Path(reference.__file__).resolve().parent
fx = json.loads((pp_dir / "fixtures" / "account_takeover_replay.json").read_text())
rr = replay.run_replay(reference.account_takeover_pack(), fx["records"])
assert rr["report_digest"] == \
    "sha-256:0dcf2bc4730bf12a89e5e5e6b54b8a9442b59b105dc068659d8035033977923b", rr["report_digest"]
assert replay_gates.preregistration_digest() == \
    "sha-256:1f026c7a95ee64bb9d2d8398941f84d75ff38f6414b7429b42eba76a736422d4"

# 9) shipped schema package-data is present
schema = pp_dir / "schemas" / "storypolicypack.schema.json"
assert schema.exists(), "policypack schema not shipped in the wheel"
intake = pathlib.Path(usg.__file__).resolve().parent / "replay_intake" / "replay_record.schema.json"
assert intake.exists(), "replay intake schema not shipped in the wheel"

print("ISOLATED SINGLE-WHEEL STORYGRAPH VERIFICATION OK")
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
    """Any packaged top-level dir other than ugence_storygraph / dist-info."""
    with zipfile.ZipFile(wheel) as z:
        tops = {n.split("/", 1)[0] for n in z.namelist() if "/" in n}
    return {t for t in tops if not (t == "ugence_storygraph" or t.endswith(".dist-info"))}


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print("[1/4] build the single StoryGraph wheel")
    _run([sys.executable, "-m", "build", "--wheel", str(PKG), "-o", str(findlinks)])
    wheel = _latest(findlinks, "ugence_storygraph-*.whl")
    print(f"      built {wheel.name}")

    print("[2/4] assert the wheel bundles no foreign top-level package")
    foreign = _foreign_members(wheel)
    assert not foreign, f"wheel bundles foreign packages: {sorted(foreign)}"
    print("      wheel contains only ugence_storygraph/ + dist-info")

    print("[3/4] create an isolated venv and install ONLY this wheel")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        # No index needed: StoryGraph declares zero third-party dependencies.
        _run([str(py), "-m", "pip", "install", "--quiet", "--no-index",
              "--find-links", str(findlinks), "ugence-storygraph"])

        print("[4/4] run the isolated proof (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK], cwd=str(td))

    shutil.rmtree(findlinks, ignore_errors=True)
    print("\nISOLATED SINGLE-WHEEL STORYGRAPH DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
