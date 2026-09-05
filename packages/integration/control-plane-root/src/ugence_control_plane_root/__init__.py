"""Ugence control-plane root — the audit-ledger service, and nothing else.

Scoped and ratified by ``docs/architecture/ADR_UGENCE_CONTROL_PLANE_ROOT_SCOPING.md``.

    THIS PACKAGE APPENDS AND RETURNS A REFERENCE. IT DECIDES NOTHING, OWNS NO
    POLICY, ISSUES NO ENVELOPE, BROKERS NO CREDENTIAL, AND UNIFIES NO EXISTING
    AUDIT STORE.

It is a **composition root**, not a capability (D-2): it wires packages that
already exist and adds nothing to the platform's capability count. It is
deliberately **not** the AI Control Plane — that noun names a product with its own
documentation tree and a shipped console (``ugence_console_api/``). This is a root
*under* it.

Why the ledger and not another roadmap §3 service: it is the only one both unowned
and composable from ``packages/``. Seven audit stores exist and none of them is the
service; the policy service and the contract layer are each already a single
package; identity belongs to the IdP; the console is already built.

Nothing here reads the system clock. Every instant is a caller input.
"""

from __future__ import annotations

from ._canon import canonical_bytes, domain_digest
from .entry import GENESIS_DIGEST, LedgerEntry
from .errors import (
    ContractViolation,
    ControlPlaneRootError,
    LedgerIntegrityError,
    SchemaVersionMismatch,
)
from .ledger import STORE_REF, AuditLedger, AuditReferenceFactory, StoredEntry
from .version import CONTRACT_VERSION, MATURITY, SCHEMA_VERSION, __version__

__all__ = [
    # the act
    "AuditLedger", "LedgerEntry", "StoredEntry", "AuditReferenceFactory",
    # identity of the store
    "STORE_REF", "GENESIS_DIGEST",
    # refusals
    "ControlPlaneRootError", "ContractViolation", "LedgerIntegrityError",
    "SchemaVersionMismatch",
    # canonicalization, exported so a composition root can verify a digest itself
    "canonical_bytes", "domain_digest",
    # declared, never inferred
    "__version__", "CONTRACT_VERSION", "SCHEMA_VERSION", "MATURITY",
]
