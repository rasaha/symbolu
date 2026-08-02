"""Make the canonical package, its dependencies, and the legacy shim importable
for the package's own tests in a bare source checkout (no editable install).

* ``ugence_governance_provider_framework`` — from this package's ``src`` layout.
* ``ugence_governance_contracts`` — the neutral contract leaf (hard dependency).
* ``ugence_decision_authority`` — backs ``decision_governance.api`` for the
  kernel-bound adapter tests (optional ``adapters`` dependency).
* ``governance_providers`` / ``decision_governance`` — the legacy shims at the
  repository root (compatibility tests import through them).
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]  # packages/governance-provider-framework -> packages -> repo root
for p in (
    HERE / "src",
    HERE / "tests",  # shared test helpers (e.g. kernel_lifecycle) importable across subdirs
    REPO / "packages" / "governance-contracts" / "src",
    REPO / "packages" / "capabilities" / "decision-authority" / "src",
    REPO,
):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
