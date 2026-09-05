"""One ledger entry: what a caller hands over, and what it digests to.

An entry carries a **kind**, a tenant, the instant the caller observed, and an
uninterpreted payload. It carries no decision, no outcome and no authority: the
ledger records that somebody wrote something down, never that it was true or that
anyone was entitled to write it — the same limit
:class:`~ugence_governance_contracts.contracts.audit.AuditReference` states about
itself.

The ``kind`` is a free string the caller chooses. This package ships **no event-type
vocabulary**: Decision Authority's ``AuditEventType`` is frozen at 1.0.0 and owns its
names, and a neutral second catalog here would fork them — which is exactly what G4
refused to do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from ._canon import canonical_bytes, domain_digest, iso, require_nonempty, require_tzaware
from .errors import ContractViolation

__all__ = ["LedgerEntry", "GENESIS_DIGEST"]

#: The digest a tenant's first entry links to. Domain-separated like every other
#: digest here, so it cannot be confused with an entry that happens to be all zeros.
GENESIS_DIGEST = "0" * 64


def _require_jsonable(payload: object, name: str) -> dict:
    """A payload must survive canonicalization, or the digest means nothing."""

    if not isinstance(payload, Mapping):
        raise ContractViolation(f"{name} must be a mapping")
    plain = dict(payload)
    for key in plain:
        if not isinstance(key, str):
            raise ContractViolation(f"{name} keys must be strings")
    try:
        canonical_bytes(plain)
    except (TypeError, ValueError) as exc:
        raise ContractViolation(
            f"{name} must be JSON-serializable; the digest is over its canonical "
            f"bytes, so a value that cannot be canonicalized cannot be recorded ({exc})"
        ) from None
    return plain


@dataclass(frozen=True)
class LedgerEntry:
    """One append, as the caller supplies it. Frozen, digest-bound, clock-free."""

    tenant_id: str
    kind: str
    #: The instant the caller observed — never the instant this object was built.
    recorded_at: datetime
    recorded_by: str
    payload: dict = field(default_factory=dict)
    correlation_id: str = ""

    def __init_subclass__(cls, **kwargs):
        """Refuse subclassing: the invariants live in ``__post_init__``, and a
        subclass could replace them with nothing."""

        raise TypeError(
            "LedgerEntry may not be subclassed: its invariants live in "
            "__post_init__, and a subclass could replace them")

    def __setstate__(self, state: dict) -> None:
        """Re-validate on unpickling; ``pickle`` never calls ``__init__``."""

        for key, value in state.items():
            object.__setattr__(self, key, value)
        self.__post_init__()

    def __post_init__(self) -> None:
        for name in ("tenant_id", "kind", "recorded_by"):
            object.__setattr__(self, name,
                               require_nonempty(getattr(self, name), f"LedgerEntry.{name}"))
        if not isinstance(self.correlation_id, str):
            raise ContractViolation("LedgerEntry.correlation_id must be a string")
        object.__setattr__(self, "correlation_id", self.correlation_id.strip())
        object.__setattr__(self, "payload",
                           _require_jsonable(self.payload, "LedgerEntry.payload"))
        require_tzaware(self.recorded_at, "LedgerEntry.recorded_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id, "kind": self.kind,
            "recorded_at": iso(self.recorded_at, "recorded_at"),
            "recorded_by": self.recorded_by, "payload": self.payload,
            "correlation_id": self.correlation_id,
        }

    def content_digest(self) -> str:
        """The entry's own content, independent of where it lands in a chain."""

        return domain_digest("control_plane_root.entry", self.to_dict())
