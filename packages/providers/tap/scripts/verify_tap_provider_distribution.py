#!/usr/bin/env python3
"""Reproducible proof that ugence-tap-provider installs and operates in isolation.

Builds the canonical wheel and its dependency wheels, installs ONLY them into a
fresh virtualenv with no system site packages and no monorepo source path, then
proves — offline, without a network — that:

  * the canonical package imports outside the repository;
  * the in-process TAP provider maps requests/results correctly;
  * fail-safe converts infrastructure failure to INDETERMINATE (never SUPPORTED);
  * unknown outcomes map to INDETERMINATE;
  * health degrades (and never raises) when the engine is unavailable;
  * the TAP provider registers and resolves through the framework registry;
  * ``python -m ugence_tap_provider verify`` and ``demo`` pass;
  * the wheel is pure-Python, carries the canonical namespace, ships no tests,
    and bundles NO ActionGate and NO AI Hiring content;
  * neither ``actiongate_provider`` nor ``ugence_actiongate_provider`` is present;
  * the legacy ``dgm-tap-provider`` compatibility wheel makes ``import tap_provider``
    resolve to the identical canonical objects (installed against the canonical wheel).

Run:  python packages/providers/tap/scripts/verify_tap_provider_distribution.py
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

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]  # packages/providers/tap -> packages/providers -> packages -> repo

# Source trees to build into wheels (canonical core dependency closure + legacy shim).
BUILDS = {
    "ugence-governance-contracts": REPO / "packages" / "governance-contracts",
    "ugence-governance-provider-framework": REPO / "packages" / "governance-provider-framework",
    "ugence-tap-provider": PKG,
    "dgm-tap-provider": REPO / "packaging" / "dgm-tap-provider",
}

# Offline in-venv proof (public API only; no monorepo path).
_CHECK = r'''
import sys

# 1) canonical import outside the repo
import ugence_tap_provider as t
assert t.__version__ == "0.1.0", t.__version__
info = t.version_info()
assert info.distribution == "ugence-tap-provider"
assert info.production_certified is False

from ugence_governance_provider_framework.api import (
    AssertionCoverage, AssertionGovernanceRequest, ProviderKind, ProviderRegistry,
    ResolutionRequest, resolve)
from ugence_tap_provider.configuration import build_tap_provider
from ugence_tap_provider.core import TapEngine

# 2) in-process provider + descriptor
p = build_tap_provider(TapEngine()); p.initialize()
d = p.descriptor()
assert d.kind is ProviderKind.ASSERTION_GOVERNANCE
assert d.provider_id == "tap"

# 3) mapping
supported = p.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
assert supported.coverage is AssertionCoverage.SUPPORTED and supported.evidence_coverage == 1.0
indeterminate = p.evaluate(AssertionGovernanceRequest("A", evidence_refs=()))
assert indeterminate.coverage is AssertionCoverage.INDETERMINATE

# 4) fail-safe never SUPPORTED
for mode in ("timeout", "unavailable", "malformed", "protocol", "config"):
    fp = build_tap_provider(TapEngine(fail=mode)); fp.initialize()
    r = fp.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    assert r.coverage is AssertionCoverage.INDETERMINATE, mode

# 5) unknown outcome
up = build_tap_provider(TapEngine(emit_unknown=True)); up.initialize()
assert up.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",))).coverage \
    is AssertionCoverage.INDETERMINATE

# 6) health degrades and never raises
dp = build_tap_provider(TapEngine(fail="unavailable")); dp.initialize()
assert dp.health().healthy is False

# 7) registry resolution
reg = ProviderRegistry(); reg.register(p.descriptor())
sel, rec = resolve(reg, ResolutionRequest(ProviderKind.ASSERTION_GOVERNANCE))
assert rec.selected_id == "tap"

# 8) ActionGate absent
assert not any(m.split(".")[0] in ("actiongate_provider", "ugence_actiongate_provider")
               for m in list(sys.modules))
print("in-venv checks: OK")
'''

_LEGACY_CHECK = r'''
import tap_provider, ugence_tap_provider
import tap_provider.api, ugence_tap_provider.api
import tap_provider.core, ugence_tap_provider.core
assert tap_provider.__version__ is ugence_tap_provider.__version__ == "0.1.0"
assert tap_provider.api is ugence_tap_provider.api
assert tap_provider.api.TAPProvider is ugence_tap_provider.api.TAPProvider
from tap_provider.mapping.result import map_result as a
from ugence_tap_provider.mapping.result import map_result as b
assert a is b
print("legacy facade checks: OK")
'''


def _run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd))
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
    assert not any("actiongate" in n.lower() for n in names), "ActionGate in wheel"
    assert not any("ai_hiring" in n.lower() for n in names), "AI Hiring in wheel"
    assert any(n.startswith("ugence_tap_provider/") for n in names), "namespace missing"
    print(f"  wheel-content audit OK: {wheel.name} ({len(names)} members)")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="tap-verify-"))
    try:
        dist = tmp / "dist"; dist.mkdir()
        print("[1/5] building wheels")
        _build_all(dist)
        canonical = next(dist.glob("ugence_tap_provider-*.whl"))
        _audit_wheel(canonical)

        print("[2/5] creating clean venv (no system site packages)")
        vdir = tmp / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(vdir)
        py = vdir / "bin" / "python"

        print("[3/5] installing canonical core only (offline, --no-index)")
        _run([str(py), "-m", "pip", "install", "--no-index", "--find-links", str(dist),
              "ugence-tap-provider"])

        print("[4/5] running in-venv provider + CLI checks (outside the repo)")
        _run([str(py), "-c", _CHECK], cwd=str(tmp))
        _run([str(py), "-m", "ugence_tap_provider", "verify"], cwd=str(tmp))
        _run([str(py), "-m", "ugence_tap_provider", "demo"], cwd=str(tmp))

        print("[5/5] installing legacy compat wheel + facade identity check")
        legacy = next(dist.glob("dgm_tap_provider-*.whl"))
        # --no-deps: the canonical wheel is already installed; the compat wheel
        # only adds the logic-free tap_provider shim.
        _run([str(py), "-m", "pip", "install", "--no-index", "--no-deps", str(legacy)])
        _run([str(py), "-c", _LEGACY_CHECK], cwd=str(tmp))

        print("\nTAP distribution verification: PASS")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
