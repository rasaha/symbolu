"""Version, contract version and maturity — declared, never inferred."""

from __future__ import annotations

from typing import Final

__all__ = ["__version__", "CONTRACT_VERSION", "MATURITY", "SCHEMA_VERSION"]

__version__: Final[str] = "0.1.0"

#: The wire shape of one ledger entry. Bumped when a stored entry's canonical
#: form changes, never for an additive read helper.
CONTRACT_VERSION: Final[str] = "control_plane_root.audit_ledger.v1"

#: The SQLite schema this package writes, in the shape storygraph's durable audit
#: uses. A store opened at a different schema version is refused, not migrated.
SCHEMA_VERSION: Final[str] = "cpr.audit/1.0.0"

#: This root composes reference-grade packages and inherits that maturity
#: (ADR D-1). It is not production-ready and does not claim to be.
MATURITY: Final[str] = "REFERENCE_GRADE"
