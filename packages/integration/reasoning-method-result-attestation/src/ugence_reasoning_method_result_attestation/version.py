"""Single source of truth for the distribution version.

``0.1.0`` is the contracts-only slice ratified by
``docs/architecture/ADR_UGENCE_SIGNED_COMPARISON_RESULT_SCOPING.md`` (SCR-1): the
signed-comparison-result wrapper, the one comparison-engine role, the signer
port and its typed verification result, one verifier over the Trusted Evidence
Authority's anchors, and a reference signer for tests. Maturity is
REFERENCE-GRADE / NOT PRODUCTION-READY. No key for any comparison engine exists.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
