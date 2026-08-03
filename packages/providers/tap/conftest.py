"""Make the canonical package, its dependencies, and the legacy shim importable
for the package's own tests in a bare source checkout (no editable install).

* ``ugence_tap_provider`` — from this package's ``src`` layout.
* ``ugence_governance_provider_framework`` — the neutral provider framework (hard
  dependency) whose ``.api`` surface TAP consumes.
* ``ugence_governance_contracts`` — the neutral contract leaf (transitive).
* ``ugence_decision_authority`` — backs ``decision_governance.api`` for the
  assessment-lifecycle tests (optional ``decision-authority`` dependency).
* ``tap_provider`` / ``governance_providers`` / ``decision_governance`` — the legacy
  shims at the repository root (compatibility tests import through them).
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]  # packages/providers/tap -> packages/providers -> packages -> repo
for p in (
    HERE / "src",
    HERE / "tests",  # shared helpers importable across subdirs
    REPO / "packages" / "governance-provider-framework" / "src",
    REPO / "packages" / "governance-contracts" / "src",
    REPO / "packages" / "capabilities" / "decision-authority" / "src",
    REPO,
):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
