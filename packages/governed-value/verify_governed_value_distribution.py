#!/usr/bin/env python3
"""Reproducible proof that Governed Value installs and operates as a single,
self-contained leaf wheel with NO other Ugence package (and no third-party
dependency) on the path.

Builds ``ugence-governed-value`` only, installs it into a fresh virtualenv with
no system site packages and no monorepo path (``--no-index`` — the package
declares zero third-party runtime dependencies), then proves inside that env:

  * ``governed_value`` imports from site-packages and ships ``py.typed``;
  * the spine scores a case end-to-end and the headline NGVA is exact Decimal;
  * a fail-closed guard (no baseline) suppresses the headline;
  * a portfolio normalizes two agents to net-governed-value-per-authorized-action;
  * NO capability / framework / product / authority package is importable.

Run:  python packages/governed-value/verify_governed_value_distribution.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PKG = Path(__file__).resolve().parent

_CHECK = r'''
import importlib.util, sys
from decimal import Decimal

import governed_value as gv
assert gv.__version__ == "0.1.0", gv.__version__
assert "site-packages" in gv.__file__, gv.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

import pathlib as _pl
assert (_pl.Path(gv.__file__).resolve().parent / "py.typed").is_file(), "py.typed missing"

# No third-party / unrelated Ugence package in this clean env.
for mod in ("pydantic", "fastapi", "numpy", "governance_providers",
            "risk_authority", "ugence_actiongate_provider", "platform_freeze"):
    assert importlib.util.find_spec(mod) is None, ("unexpected package present: " + mod)

from governed_value.api import (GovernedValueApplication, AgentValueCase, AttributionContext,
    AuthorizedActionRef, CostToServe, DomainKind, DomainProfile, ErrorProfile,
    GeographyProfile, Money, OutcomeClass, RealizedValue, Scorability, ValueSource)


def _case(agent_id, authorized, baseline=True):
    return AgentValueCase(
        agent_id=agent_id,
        domain=DomainProfile(kind=DomainKind.SUPPORT, natural_unit="contact_deflected",
                             dominant_source=ValueSource.LABOR_DISPLACED),
        geography=GeographyProfile(label="PH", currency="USD"),
        outcome=OutcomeClass.DETERMINISTIC_AUTOMATION,
        realized=RealizedValue(labor_displaced=Money(1_000_00, "USD"),
                               throughput_gained=Money(0, "USD"), loss_avoided=Money(0, "USD")),
        error_profile=ErrorProfile(p_error=Decimal("0.05"), severity=Decimal("0.20")),
        cost=CostToServe(currency="USD", inference=Money(200_00, "USD"), retries=Money(20_00, "USD"),
                         evals=Money(15_00, "USD"), monitoring=Money(10_00, "USD"),
                         human_in_loop_review=Money(50_00, "USD"),
                         incident_remediation=Money(5_00, "USD"), model_migration=Money(0, "USD")),
        attribution=AttributionContext(baseline_captured=baseline, realization_rate=Decimal("0.90"),
                                       headcount_or_scope_changed=True),
        action=AuthorizedActionRef(tenant_id="t", envelope_id="e", action_digest="d",
                                   authorized_count=authorized),
    )


app = GovernedValueApplication()

# 1) Spine scores end to end; headline is exact Decimal.
r = app.score(_case("a", 500))
assert r.scorability is Scorability.SCORABLE, r.reasons
assert r.net_governed_value.minor_units == 59_100, r.net_governed_value
assert r.ngva_per_action == Decimal("118.2"), r.ngva_per_action
assert isinstance(r.ngva_per_action, Decimal)

# 2) Fail-closed guard suppresses the headline.
bad = app.score(_case("b", 500, baseline=False))
assert bad.scorability is Scorability.NOT_SCORABLE
assert bad.ngva_per_action is None and bad.roi_ratio is None

# 3) Portfolio normalizes to net-governed-value-per-authorized-action.
summary = app.compare([_case("high", 500), _case("low", 5000)], base_currency="USD")
assert [e.agent_id for e in summary.ranked] == ["high", "low"], summary.ranked
assert summary.portfolio_ngva is not None

print("governed_value distribution OK:", gv.__version__)
'''


def main() -> int:
    build_dir = PKG / "build"
    dist_dir = PKG / "dist"
    for d in (build_dir, dist_dir):
        if d.exists():
            shutil.rmtree(d)

    print(f"[1/3] building wheel for {PKG.name} ...")
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir), str(PKG)],
        check=True,
    )
    wheels = list(dist_dir.glob("ugence_governed_value-*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
    wheel = wheels[0]

    with tempfile.TemporaryDirectory() as tmp:
        env_dir = Path(tmp) / "venv"
        print(f"[2/3] creating clean venv at {env_dir} ...")
        venv.create(env_dir, with_pip=True, clear=True)
        py = env_dir / "bin" / "python"
        if not py.exists():  # Windows layout
            py = env_dir / "Scripts" / "python.exe"

        print("[3/3] installing wheel (--no-index) and running checks ...")
        subprocess.run(
            [str(py), "-m", "pip", "install", "--no-index", "--quiet", str(wheel)],
            check=True,
        )
        # Run the proof from a neutral cwd so the monorepo root (which holds
        # sibling packages like ``governance_providers``) is never on sys.path.
        subprocess.run([str(py), "-c", _CHECK], check=True, cwd=tmp)

    print("PASS: ugence-governed-value is a self-contained stdlib-only leaf.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
