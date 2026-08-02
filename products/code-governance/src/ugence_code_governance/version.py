"""Product version — single source of truth for ``ugence_code_governance``."""
from __future__ import annotations

__version__ = "0.3.0"

#: The bounded implementation phase this build corresponds to.
MVP_PHASE = "1D"

#: This build is read-only and non-enforcing. Execution is disabled by design.
EXECUTION_ENABLED = False

#: Durable persistence classification. This is a DURABLE_SHADOW_REFERENCE audit
#: store — NOT a production enforcement store or an execution-consumption ledger.
DURABILITY_CLASS = "DURABLE_SHADOW_REFERENCE"
