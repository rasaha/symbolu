"""Neutral idempotency contract — *is this the same logical action again?* (G7).

Closes contract gap **G7** of the governance-contracts evolution plan:
``idempotency_key`` existed as a free string on
:class:`~.action.ActionGovernanceRequest` and
:class:`~.execution.ExecutionDispatchRequest` with no contract defining what
the key identifies, what it is unique within, or how a duplicate is reported.

This module defines **contracts and structural invariants only**. It is not a
deduplication store, a reservation ledger, a replay-protection service or an
executor. It grants no permission and mints no authority. Atomic one-time
reservation, retention windows and replay protection belong to the execution
ledger that Action Clearance's phase G names; this contract gives that ledger
and every producer one vocabulary.

Semantics
---------
An :class:`IdempotencyKey` names **one logical action**. Its identity is the
``key`` together with the coordinates its :class:`IdempotencyScope` declares:

| scope                 | identity                            |
|-----------------------|-------------------------------------|
| ``GLOBAL``            | ``key``                             |
| ``ACTOR``             | ``actor`` + ``key``                 |
| ``TARGET_RESOURCE``   | ``target_resource`` + ``key``       |
| ``ACTOR_AND_TARGET``  | ``actor`` + ``target_resource`` + ``key`` |

Every identity also carries an opaque ``partition`` token so that, once the
tenant and environment gaps (G1, G2) land, the same key in two tenants stays
two identities. A coordinate the scope does **not** name must be empty: if it
were allowed to vary it would fork the digest of one identity into many, and
the digest is the identity.

Two requests whose keys have the same :meth:`IdempotencyKey.canonical_digest`
are the **same logical action**. A receiver that has already observed that
identity reports the second as a duplicate, naming the original in
``duplicate_of``, and must not perform the action again. That is what
:class:`IdempotencyResolution` carries:

* ``FIRST`` — the identity had not been observed; the action may proceed
  through whatever authorization and clearance the consumer requires.
* ``DUPLICATE`` — the identity was already observed; ``duplicate_of`` names the
  original request (its ``external_request_id`` or ``correlation_id``) and is
  required.
* ``UNKNOWN`` — the receiver could not determine either. **Unknown is never
  first.** A consumer that cannot tell whether it has already acted must fail
  closed; the contract makes that distinction unmistakable by forbidding
  ``duplicate_of`` on it and by never reporting it as determinate.

Relation to the frozen provider contracts
-----------------------------------------
The provider dataclasses are **unchanged**: their fields, defaults, constructor
signatures and serialized forms are pinned by the serialization-equivalence
tests, and adding a field to them would move every fingerprint a consumer
computes over an existing request. The binding is by value instead: a producer
that adopts this contract places ``IdempotencyKey.canonical_digest()`` in the
existing free-string ``idempotency_key`` field, which makes that field
scope-bound and fixed-width without changing its type or default, and an
:class:`ExecutionObservation` whose ``business_outcome`` is ``DUPLICATE``
corresponds to a resolution whose disposition is ``DUPLICATE``. Nothing here
enforces that binding — a free string stays a free string for every caller that
has not adopted the contract.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "IdempotencyContractError",
    "IdempotencyScope",
    "IdempotencyKey",
    "IdempotencyDisposition",
    "IdempotencyResolution",
]


class IdempotencyContractError(ValueError):
    """A structural idempotency invariant was violated.

    Subclasses :class:`ValueError`, mirroring
    :class:`~.evidence.EvidenceContractError`, so existing ``ValueError``
    handling still catches it. It signals a *structural* rejection — never a
    claim that any store was consulted.
    """


class IdempotencyScope(str, Enum):
    """What a key is unique within. Declared explicitly, never inferred."""

    GLOBAL = "GLOBAL"
    ACTOR = "ACTOR"
    TARGET_RESOURCE = "TARGET_RESOURCE"
    ACTOR_AND_TARGET = "ACTOR_AND_TARGET"


class IdempotencyDisposition(str, Enum):
    """How a receiver classified one identity. ``UNKNOWN`` is never ``FIRST``."""

    FIRST = "FIRST"
    DUPLICATE = "DUPLICATE"
    UNKNOWN = "UNKNOWN"


#: Which coordinates each scope names. A coordinate absent from a scope's tuple
#: must be empty on a key carrying that scope.
_SCOPE_COORDINATES: dict[IdempotencyScope, tuple[str, ...]] = {
    IdempotencyScope.GLOBAL: (),
    IdempotencyScope.ACTOR: ("actor",),
    IdempotencyScope.TARGET_RESOURCE: ("target_resource",),
    IdempotencyScope.ACTOR_AND_TARGET: ("actor", "target_resource"),
}

_ALL_COORDINATES = ("actor", "target_resource")


# --------------------------------------------------------------------------- #
# Small validation helpers (stdlib-only; module-local, mirroring system_identity.py)
# --------------------------------------------------------------------------- #
def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise IdempotencyContractError(
            f"{name} must be a string (got {type(value).__name__})"
        )
    return value


def _require_nonempty(value: object, name: str) -> str:
    text = _require_str(value, name)
    if not text.strip():
        raise IdempotencyContractError(f"{name} must be a non-empty string")
    return text.strip()


def _canonical_bytes(obj) -> bytes:
    payload = dataclasses.asdict(obj)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return encoded.encode("utf-8")


@dataclass(frozen=True)
class IdempotencyKey:
    """The identity of one logical action.

    ``key`` is the caller's token for the action and must be non-blank; it is
    stored stripped, so ``" k "`` and ``"k"`` are one key. ``scope`` says which
    of ``actor`` and ``target_resource`` participate; those the scope names are
    required and those it does not must be empty. ``partition`` is an opaque
    token reserved for the tenant/environment coordinate (G1, G2) and always
    participates in the identity. Every field participates in
    :meth:`canonical_digest`.
    """

    key: str
    scope: IdempotencyScope
    actor: str = ""
    target_resource: str = ""
    partition: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _require_nonempty(self.key, "IdempotencyKey.key"))
        if not isinstance(self.scope, IdempotencyScope):
            raise IdempotencyContractError(
                "IdempotencyKey.scope must be an IdempotencyScope member"
            )
        for name in _ALL_COORDINATES + ("partition",):
            value = _require_str(getattr(self, name), f"IdempotencyKey.{name}")
            object.__setattr__(self, name, value.strip())

        named = _SCOPE_COORDINATES[self.scope]
        for name in _ALL_COORDINATES:
            value = getattr(self, name)
            if name in named and not value:
                raise IdempotencyContractError(
                    f"IdempotencyKey.{name} is required under scope {self.scope.value}"
                )
            if name not in named and value:
                raise IdempotencyContractError(
                    f"IdempotencyKey.{name} must be empty under scope {self.scope.value}: "
                    "a coordinate the scope does not name would fork one identity's digest"
                )

    @property
    def identity(self) -> tuple[str, str, str, str, str]:
        """The complete tuple that defines *same logical action*."""

        return (self.partition, self.scope.value, self.actor, self.target_resource, self.key)

    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`canonical_digest` hashes."""

        return _canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over the complete identity.

        This is the value a producer places in the frozen free-string
        ``idempotency_key`` field when it adopts the contract. Equal keys share
        one digest; keys differing in any coordinate, including scope, do not.
        """

        return hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class IdempotencyResolution:
    """How a receiver classified one :class:`IdempotencyKey`.

    ``duplicate_of`` is required exactly when the disposition is ``DUPLICATE``
    and forbidden otherwise, so a resolution can never claim a duplicate without
    naming the original, nor name an original while claiming to be first.
    """

    key: IdempotencyKey
    disposition: IdempotencyDisposition
    duplicate_of: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.key, IdempotencyKey):
            raise IdempotencyContractError(
                "IdempotencyResolution.key must be an IdempotencyKey"
            )
        if not isinstance(self.disposition, IdempotencyDisposition):
            raise IdempotencyContractError(
                "IdempotencyResolution.disposition must be an IdempotencyDisposition member"
            )
        original = _require_str(self.duplicate_of, "IdempotencyResolution.duplicate_of").strip()
        object.__setattr__(self, "duplicate_of", original)
        if self.disposition is IdempotencyDisposition.DUPLICATE and not original:
            raise IdempotencyContractError(
                "IdempotencyResolution.duplicate_of is required when disposition is "
                "DUPLICATE: a duplicate must name the original request"
            )
        if self.disposition is not IdempotencyDisposition.DUPLICATE and original:
            raise IdempotencyContractError(
                "IdempotencyResolution.duplicate_of must be empty unless disposition is "
                f"DUPLICATE (got {self.disposition.value})"
            )

    @property
    def is_first(self) -> bool:
        """``True`` only for ``FIRST``. ``UNKNOWN`` is never first."""

        return self.disposition is IdempotencyDisposition.FIRST

    @property
    def is_duplicate(self) -> bool:
        return self.disposition is IdempotencyDisposition.DUPLICATE

    @property
    def is_determinate(self) -> bool:
        """``False`` for ``UNKNOWN``: the receiver could not decide, so the consumer must fail closed."""

        return self.disposition is not IdempotencyDisposition.UNKNOWN

    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`canonical_digest` hashes."""

        return _canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over key identity, disposition and original."""

        return hashlib.sha256(self.canonical_bytes()).hexdigest()
