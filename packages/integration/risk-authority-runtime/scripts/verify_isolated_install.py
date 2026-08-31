#!/usr/bin/env python3
"""Reproducible proof that ``ugence-risk-authority-runtime`` installs and operates
from its DECLARED dependencies alone, in a fresh virtualenv with no monorepo path.

Unlike ``ugence-risk-authority`` (a zero-dependency leaf proven with
``--no-index``), the runtime package is an *integration* layer: it legitimately
depends on three first-party wheels (risk-authority, decision-authority,
actiongate-provider) plus their transitive first-party leaves
(governance-provider-framework, governance-contracts) and pydantic. This verifier
therefore builds a local wheelhouse of the FIRST-PARTY wheels and installs the
runtime from it, allowing only third-party wheels (pydantic) from the index.

It then proves, inside that clean env:

  * ``ugence_risk_authority_runtime`` imports from site-packages (not the repo);
  * a full GRANT composition runs (RA ALLOW + DA ADVANCE + AG ALLOW);
  * a DENY composition runs (RA DENY absorbs permissive governance);
  * governance can never express ALLOW (VetoDisposition has no ALLOW member);
  * NO out-of-scope monorepo package (symbolu/agentic/apps/…) is importable.

Run:  python packages/integration/risk-authority-runtime/scripts/verify_isolated_install.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]  # packages/integration/risk-authority-runtime -> repo

# First-party wheels the runtime needs, built locally into the wheelhouse.
FIRST_PARTY = [
    REPO / "packages" / "governance-contracts",
    REPO / "packages" / "governance-provider-framework",
    REPO / "packages" / "providers" / "actiongate",
    REPO / "packages" / "capabilities" / "decision-authority",
    REPO / "packages" / "risk_authority",
    PKG,
]

_PROBE = r"""
import importlib, sys, pathlib

# 1. Import from site-packages, not the repo checkout.
import ugence_risk_authority_runtime as rt
loc = pathlib.Path(rt.__file__).resolve()
assert "site-packages" in loc.parts, f"not installed from site-packages: {loc}"

from ugence_risk_authority_runtime import (
    RiskAuthorityCompositionEngine, DecisionAuthorityGovernanceAdapter,
    ActionGatePolicyAdapter, RiskAuthorityMachineResult, RiskAuthorityDisposition,
    FinalDisposition, VetoDisposition,
)
from ugence_decision_authority.decisions.status import DecisionOutcome
from ugence_actiongate_provider.core import ActionGateDecision, ActionGateOutcome
from risk_authority.domain import Scope

engine = RiskAuthorityCompositionEngine()
da = DecisionAuthorityGovernanceAdapter()
ag = ActionGatePolicyAdapter()
scope = Scope(tools_allow=("crm.read",), max_transaction_minor_units=500000)

# 2. GRANT path.
grant = engine.compose(
    risk_authority=RiskAuthorityMachineResult(disposition=RiskAuthorityDisposition.ALLOW, scope=scope),
    decision_authority=da.to_veto(DecisionOutcome.ADVANCE),
    actiongate=ag.to_veto(ActionGateDecision(outcome=ActionGateOutcome.ALLOW)),
)
assert grant.final_disposition is FinalDisposition.GRANT, grant.final_disposition

# 3. DENY path — RA DENY absorbs permissive governance.
deny = engine.compose(
    risk_authority=RiskAuthorityMachineResult(disposition=RiskAuthorityDisposition.DENY),
    decision_authority=da.to_veto(DecisionOutcome.ADVANCE),
    actiongate=ag.to_veto(ActionGateDecision(outcome=ActionGateOutcome.ALLOW)),
)
assert deny.final_disposition is FinalDisposition.DENY, deny.final_disposition

# 4. Governance can never express ALLOW.
assert "ALLOW" not in {d.value for d in VetoDisposition}

# 5. No out-of-scope monorepo package importable.
for forbidden in ("symbolu", "agentic", "ai_hiring", "applications", "domains",
                  "tap_provider", "cloud_controller"):
    try:
        importlib.import_module(forbidden)
    except ImportError:
        continue
    raise SystemExit(f"FAIL: out-of-scope package importable: {forbidden}")

print("OK: runtime installed from declared deps; GRANT+DENY verified; boundaries clean")
"""


def _run(cmd: list[str]) -> None:
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        wheelhouse = tmpdir / "wheelhouse"
        wheelhouse.mkdir()
        env_dir = tmpdir / "venv"

        # Build first-party wheels into the wheelhouse (deps resolved from index).
        for pkg in FIRST_PARTY:
            _run([sys.executable, "-m", "pip", "wheel", "--no-deps",
                  "-w", str(wheelhouse), str(pkg)])

        # Fresh venv with pip.
        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        vpy = env_dir / "bin" / "python"
        if not vpy.exists():  # windows
            vpy = env_dir / "Scripts" / "python.exe"

        # Install the runtime, preferring local wheels; index only for pydantic.
        _run([str(vpy), "-m", "pip", "install", "--quiet",
              "--find-links", str(wheelhouse), "ugence-risk-authority-runtime"])

        probe = tmpdir / "probe.py"
        probe.write_text(_PROBE)
        _run([str(vpy), str(probe)])
    print("verify_isolated_install: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print(f"verify_isolated_install: FAIL ({exc})", file=sys.stderr)
        sys.exit(1)
