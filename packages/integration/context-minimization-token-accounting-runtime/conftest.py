"""Make the integration package and BOTH core dependencies importable in a bare
source checkout (no editable install required).

* ``ugence_cm_token_accounting_runtime`` — this package's ``src`` layout.
* ``ugence_context_minimization``        — the Context Minimization leaf.
* ``ugence_agent_runtime``               — the Agent Runtime core.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# packages/integration/context-minimization-token-accounting-runtime -> ... -> repo
REPO = HERE.parents[2]

_SRC_PATHS = (
    HERE / "src",
    REPO / "packages" / "capabilities" / "context-minimization" / "src",
    REPO / "packages" / "runtime" / "agent-runtime" / "src",
)

for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
