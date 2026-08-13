#!/usr/bin/env python3
"""Reproducible proof that Governed Value installs and operates as a single,
self-contained leaf wheel with NO other Ugence package (and no third-party
dependency) on the path.

Builds ``ugence-governed-value`` only, installs it into a fresh virtualenv with
no system site packages and no monorepo path (``--no-index`` — the package
declares zero third-party runtime dependencies), then proves inside that env:

  * ``governed_value`` imports from site-packages and ships ``py.typed``;
  * the realized kernel scores a case end-to-end, the headline ROI is exact
    Decimal, and the result is honestly classified POST_DEPLOYMENT_VALUE /
    REPORTED / UNVERIFIED;
  * a fail-closed guard (no baseline) suppresses the headline (ROI + payback);
  * GV-1: an additive catastrophic expected-loss item exceeds total benefit and
    drives risk-adjusted net governed value deeply negative;
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
assert gv.__version__ == "0.2.0", gv.__version__
assert "site-packages" in gv.__file__, gv.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

import pathlib as _pl
assert (_pl.Path(gv.__file__).resolve().parent / "py.typed").is_file(), "py.typed missing"

# No third-party / unrelated Ugence package in this clean env.
for mod in ("pydantic", "fastapi", "numpy", "governance_providers",
            "risk_authority", "ugence_actiongate_provider", "platform_freeze"):
    assert importlib.util.find_spec(mod) is None, ("unexpected package present: " + mod)

from governed_value.api import (GovernedValueApplication, AgentValueCase, AttributionEvidence,
    AssessmentStage, AuthorityStatus, CostToServe, DomainKind, DomainProfile, EvidenceStatus,
    ExpectedLoss, ExpectedLossItem, GeographyProfile, Money, OutcomeClass, ReportedValue,
    Scorability, TotalInvestment, ValueSource)

M = lambda u: Money(u, "USD")


def _cost():
    return CostToServe(currency="USD", inference=M(200_00), retries=M(20_00), evals=M(15_00),
        monitoring=M(10_00), human_in_loop_review=M(50_00), incident_remediation=M(5_00),
        model_migration=M(0))


def _inv():
    return TotalInvestment(currency="USD", capital_expenditure=M(100_00), one_time_build=M(300_00),
        integration=M(100_00), amortized_cost_to_serve=M(0))


def _case(agent_id, baseline=True, expected_loss=None):
    return AgentValueCase(
        tenant_id="t", agent_id=agent_id,
        domain=DomainProfile(kind=DomainKind.SUPPORT, natural_unit="contact_deflected",
                             dominant_source=ValueSource.LABOR_DISPLACED),
        geography=GeographyProfile(label="PH", currency="USD"),
        outcome=OutcomeClass.DETERMINISTIC_AUTOMATION,
        benefit=ReportedValue(labor_displaced=M(1_000_00), throughput_gained=M(0), loss_avoided=M(0)),
        actual_losses=M(0),
        residual_expected_loss=expected_loss if expected_loss is not None else ExpectedLoss(
            currency="USD", items=(ExpectedLossItem("wrong", Decimal("0.01"), M(200_00)),)),
        cost=_cost(), investment=_inv(),
        attribution=AttributionEvidence(baseline_captured=baseline),
    )


app = GovernedValueApplication()

# 1) Realized kernel scores end to end; headline is exact Decimal; honest class.
r = app.score(_case("a"))
assert r.scorability is Scorability.SCORABLE, r.reasons
assert r.reported_net_governed_value.minor_units == 70_000, r.reported_net_governed_value
assert r.risk_adjusted_net_governed_value.minor_units == 69_800
assert r.reported_roi == Decimal("70000") / Decimal("50000")
assert isinstance(r.reported_roi, Decimal)
assert r.stage is AssessmentStage.POST_DEPLOYMENT_VALUE
assert r.evidence_status is EvidenceStatus.REPORTED
assert r.authority_status is AuthorityStatus.UNVERIFIED

# 2) Fail-closed guard suppresses the headline (ROI + payback).
bad = app.score(_case("b", baseline=False))
assert bad.scorability is Scorability.NOT_SCORABLE
assert bad.reported_roi is None and bad.risk_adjusted_roi is None and bad.payback_periods is None

# 3) GV-1 core: additive expected loss may exceed benefit and invert NGV.
catastrophe = ExpectedLoss(currency="USD",
    items=(ExpectedLossItem("catastrophe", Decimal("0.10"), M(50_000_00)),))
c = app.score(_case("c", expected_loss=catastrophe))
assert c.residual_expected_loss.minor_units == 500_000 > c.total_benefit.minor_units
assert c.risk_adjusted_net_governed_value.minor_units == -430_000

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
