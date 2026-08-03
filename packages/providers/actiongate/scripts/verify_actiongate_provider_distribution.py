#!/usr/bin/env python3
"""Reproducible proof that ugence-actiongate-provider installs and operates in isolation.

Builds the canonical wheel and its dependency wheels, installs ONLY them into a fresh
virtualenv with no system site packages and no monorepo source path, then proves —
offline, without a network — that:

  * the canonical package imports outside the repository;
  * the in-process ActionGate provider maps requests/results correctly;
  * unknown outcomes and infrastructure failure never AUTHORIZE (fail closed);
  * DENIED / AUTHORIZED_WITH_CONSTRAINTS stay distinct; constraints/obligations survive;
  * health degrades (and never raises) when the engine is unavailable;
  * the ActionGate provider registers and resolves through the framework registry;
  * the provider exposes ``authorize`` and NO dispatch/execute/reconcile surface;
  * ``python -m ugence_actiongate_provider verify`` and ``demo`` pass;
  * the wheel is pure-Python, carries the canonical namespace, ships no tests, and
    bundles NO TAP and NO AI Hiring content;
  * neither ``tap_provider`` nor ``ugence_tap_provider`` is present;
  * the legacy ``dgm-actiongate-provider`` compatibility wheel makes
    ``import actiongate_provider`` resolve to the identical canonical objects.

Run:  python packages/providers/actiongate/scripts/verify_actiongate_provider_distribution.py
Exit code 0 on success; non-zero on the first failed step.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

# The isolation proof must not leak the monorepo source path into the clean venv:
# a repo-relative ``PYTHONPATH`` (e.g. set job-wide in CI) would make pip report the
# package "already satisfied" and make imports resolve against the source tree instead
# of the installed wheel. Scrub it for every subprocess so isolation is real.
_CLEAN_ENV = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]  # packages/providers/actiongate -> packages/providers -> packages -> repo

# Source trees to build into wheels (canonical core dependency closure + legacy shim).
BUILDS = {
    "ugence-governance-contracts": REPO / "packages" / "governance-contracts",
    "ugence-governance-provider-framework": REPO / "packages" / "governance-provider-framework",
    "ugence-actiongate-provider": PKG,
    "dgm-actiongate-provider": REPO / "packaging" / "dgm-actiongate-provider",
}

# Offline in-venv proof (public API only; no monorepo path).
_CHECK = r'''
import sys

# 1) canonical import outside the repo
import ugence_actiongate_provider as a
assert a.__version__ == "0.1.0", a.__version__
info = a.version_info()
assert info.distribution == "ugence-actiongate-provider"
assert info.production_certified is False

from ugence_governance_provider_framework.api import (
    ActionGovernanceOutcome, ActionGovernanceRequest, ProviderKind, ProviderRegistry,
    ProviderTimeoutError, ResolutionRequest, resolve)
from ugence_actiongate_provider.configuration import build_actiongate_provider
from ugence_actiongate_provider.core import (
    ActionGateConstraint, ActionGateEngine, ActionGateObligation, ConstrainedRule)

# 2) in-process provider + descriptor (authorization only)
p = build_actiongate_provider(ActionGateEngine()); p.initialize()
d = p.descriptor()
assert d.kind is ProviderKind.ACTION_GOVERNANCE
assert d.provider_id == "actiongate"
assert hasattr(p, "authorize")
assert not any(hasattr(p, m) for m in ("dispatch", "execute", "observe", "reconcile", "compensate"))

# 3) all four outcomes
assert p.authorize(ActionGovernanceRequest("OK")).outcome is ActionGovernanceOutcome.AUTHORIZED
dn = build_actiongate_provider(ActionGateEngine(denied=frozenset({"D"}))); dn.initialize()
assert dn.authorize(ActionGovernanceRequest("D")).outcome is ActionGovernanceOutcome.DENIED
uk = build_actiongate_provider(ActionGateEngine(unknown=frozenset({"U"}))); uk.initialize()
assert uk.authorize(ActionGovernanceRequest("U")).outcome is ActionGovernanceOutcome.INDETERMINATE
rule = ConstrainedRule(constraints=(ActionGateConstraint("maximum_amount", "10"),),
                       obligations=(ActionGateObligation("human_review"),))
cp = build_actiongate_provider(ActionGateEngine(constrained={"C": rule})); cp.initialize()
cr = cp.authorize(ActionGovernanceRequest("C"))
assert cr.outcome is ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS
assert "maximum_amount=10" in cr.constraints and "human_review" in cr.obligations

# 4) infrastructure failure never authorizes
fp = build_actiongate_provider(ActionGateEngine(fail="timeout")); fp.initialize()
try:
    fp.authorize(ActionGovernanceRequest("X")); raise SystemExit("timeout authorized!")
except ProviderTimeoutError:
    pass

# 5) health degrades and never raises
hp = build_actiongate_provider(ActionGateEngine(fail="unavailable")); hp.initialize()
assert hp.health().healthy is False

# 6) registry resolution
reg = ProviderRegistry(); reg.register(p.descriptor())
sel, rec = resolve(reg, ResolutionRequest(ProviderKind.ACTION_GOVERNANCE))
assert rec.selected_id == "actiongate"

# 7) TAP absent
assert not any(m.split(".")[0] in ("tap_provider", "ugence_tap_provider")
               for m in list(sys.modules))
print("in-venv checks: OK")
'''

_LEGACY_CHECK = r'''
import actiongate_provider, ugence_actiongate_provider
import actiongate_provider.api, ugence_actiongate_provider.api
import actiongate_provider.core, ugence_actiongate_provider.core
assert actiongate_provider.__version__ == ugence_actiongate_provider.__version__ == "0.1.0"
assert actiongate_provider.api is ugence_actiongate_provider.api
assert actiongate_provider.api.ActionGateProvider is ugence_actiongate_provider.api.ActionGateProvider
from actiongate_provider.mapping.result import map_result as a
from ugence_actiongate_provider.mapping.result import map_result as b
assert a is b
print("legacy facade checks: OK")
'''


def _run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd))
    kw.setdefault("env", _CLEAN_ENV)
    return subprocess.run(cmd, check=True, **kw)


def _build_all(dist_dir: Path) -> dict:
    wheels = {}
    for name, src in BUILDS.items():
        _run([sys.executable, "-m", "build", "--wheel", str(src), "--outdir", str(dist_dir)])
    for whl in dist_dir.glob("*.whl"):
        wheels[whl.name.split("-")[0]] = whl
    return wheels


def _audit_wheel(wheel: Path) -> None:
    names = zipfile.ZipFile(wheel).namelist()
    assert not any("/tests/" in n or n.endswith("/tests") for n in names), "tests in wheel"
    assert not any("tap_provider" in n.lower() for n in names), "TAP in wheel"
    assert not any("ai_hiring" in n.lower() for n in names), "AI Hiring in wheel"
    assert any(n.startswith("ugence_actiongate_provider/") for n in names), "namespace missing"
    print(f"  wheel-content audit OK: {wheel.name} ({len(names)} members)")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="actiongate-verify-"))
    try:
        dist = tmp / "dist"; dist.mkdir()
        print("[1/5] building wheels")
        _build_all(dist)
        canonical = next(dist.glob("ugence_actiongate_provider-*.whl"))
        _audit_wheel(canonical)

        print("[2/5] creating clean venv (no system site packages)")
        vdir = tmp / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(vdir)
        py = vdir / "bin" / "python"

        print("[3/5] installing canonical core only (offline, --no-index)")
        _run([str(py), "-m", "pip", "install", "--no-index", "--find-links", str(dist),
              "ugence-actiongate-provider"])

        print("[4/5] running in-venv provider + CLI checks (outside the repo)")
        _run([str(py), "-c", _CHECK], cwd=str(tmp))
        _run([str(py), "-m", "ugence_actiongate_provider", "verify"], cwd=str(tmp))
        _run([str(py), "-m", "ugence_actiongate_provider", "demo"], cwd=str(tmp))

        print("[5/5] installing legacy compat wheel + facade identity check")
        legacy = next(dist.glob("dgm_actiongate_provider-*.whl"))
        # --no-deps: the canonical wheel is already installed; the compat wheel only
        # adds the logic-free actiongate_provider shim (and would otherwise pull the
        # decision-authority extra's kernel closure, which the core path does not need).
        _run([str(py), "-m", "pip", "install", "--no-index", "--no-deps", str(legacy)])
        _run([str(py), "-c", _LEGACY_CHECK], cwd=str(tmp))

        print("\nActionGate distribution verification: PASS")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
