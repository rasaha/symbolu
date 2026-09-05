"""Make this package and its dependencies importable in a bare source checkout
(no editable install), mirroring the sibling integration packages' convention."""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# packages/integration/agent-runtime-governance -> packages/integration -> packages -> repo
REPO = HERE.parents[2]

for path in (
    HERE / "src",
    REPO / "packages" / "runtime" / "agent-runtime" / "src",
    REPO / "packages" / "integration" / "risk-authority-runtime" / "src",
    REPO / "packages" / "integration" / "risk-authority-status-runtime" / "src",
    REPO / "packages" / "risk_authority" / "src",
    REPO / "packages" / "capabilities" / "decision-authority" / "src",
    REPO / "packages" / "providers" / "actiongate" / "src",
):
    p = str(path)
    if path.is_dir() and p not in sys.path:
        sys.path.insert(0, p)
