"""Make the integration package and its three dependencies importable in a bare
source checkout (no editable install), mirroring the ActionGate package's own
conftest convention.

* ``ugence_risk_authority_runtime`` — from this package's ``src`` layout.
* ``risk_authority``               — the machine-authority owner (leaf).
* ``ugence_decision_authority``    — the organizational governance kernel.
* ``ugence_actiongate_provider``   — the action-policy provider (core only).
* ``ugence_governance_provider_framework`` / ``ugence_governance_contracts`` —
  transitive dependencies of the ActionGate provider's public API surface.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# packages/integration/risk-authority-runtime -> packages/integration -> packages -> repo
REPO = HERE.parents[2]

_SRC_PATHS = (
    HERE / "src",
    REPO / "packages" / "risk_authority" / "src",
    REPO / "packages" / "capabilities" / "decision-authority" / "src",
    REPO / "packages" / "providers" / "actiongate" / "src",
    REPO / "packages" / "governance-provider-framework" / "src",
    REPO / "packages" / "governance-contracts" / "src",
)

for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
