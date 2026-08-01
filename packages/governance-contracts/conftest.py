"""Make both the canonical package and the legacy ``governance_providers`` shim
importable for the package's own tests.

``ugence_governance_contracts`` resolves from the src layout; ``governance_providers``
resolves from the repository root (its contract modules are now re-export shims).
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "src"
REPO = HERE.parents[1]  # packages/governance-contracts -> packages -> repo root
for p in (str(SRC), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)
