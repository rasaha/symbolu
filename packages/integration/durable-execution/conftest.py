"""Make this package and Agent Runtime importable in a bare source checkout
(no editable install), mirroring the sibling integration packages' convention."""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# packages/integration/durable-execution -> packages/integration -> packages -> repo
REPO = HERE.parents[2]

for path in (
    HERE / "src",
    REPO / "packages" / "runtime" / "agent-runtime" / "src",
):
    p = str(path)
    if path.is_dir() and p not in sys.path:
        sys.path.insert(0, p)
