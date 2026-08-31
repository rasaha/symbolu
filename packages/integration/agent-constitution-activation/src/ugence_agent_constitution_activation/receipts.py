"""The two receipt shapes (`ACC-IA-4`): identity fields, never key material.

A receipt is a **derived, frozen restatement of what an authority act bound** —
it grants nothing, proves nothing on its own, and is not a signed artifact. The
evidence remains the authority's own record and registry; a receipt exists so an
operator holds a compact, key-material-free statement of what was issued or
activated, suitable for logs and hand-off.

What a receipt never carries, by construction rather than by convention: the
signature bytes, the signing key, any verification key, the policy artifact
itself, or any approval artifact content. Signer identity reaches a receipt as
the three identity fields the ``PolicySigner`` protocol exposes —
``authority_id``, ``key_id``, ``signature_alg`` — and nothing else. Times are
caller-supplied and timezone-aware; no module in this package reads a clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Tuple

from ugence_policy_authority.api import PolicyCoordinate

from .errors import ActivationRequestError

__all__ = ["IssuanceReceipt", "ActivationReceipt"]

_HEX = frozenset("0123456789abcdef")


def _require_str(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ActivationRequestError(f"{name} must be a non-empty str")
    return value


def _require_digest(value: object, name: str) -> str:
    if type(value) is not str or len(value) != 64 or any(c not in _HEX for c in value):
        raise ActivationRequestError(
            f"{name} must be a lowercase 64-char sha-256 hex digest"
        )
    return value


def _require_tzaware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.tzinfo.utcoffset(value) is None
    ):
        raise ActivationRequestError(
            f"{name} must be a timezone-aware datetime; a naive datetime is never "
            "assumed to be UTC"
        )
    return value


def _require_coordinate(value: object, name: str) -> PolicyCoordinate:
    if type(value) is not PolicyCoordinate:
        raise ActivationRequestError(f"{name} must be exactly a PolicyCoordinate")
    return value


@dataclass(frozen=True)
class IssuanceReceipt:
    """What one issuance bound: coordinate, digests, signer identity, approval evidence.

    Derived from the authority's ``IssuedPolicyRecord`` by the composition root.
    Deliberately **not** the record: the record carries the signature bytes and
    the policy artifact itself, and a receipt carries neither.
    """

    record_id: str
    coordinate: PolicyCoordinate
    policy_body_digest: str
    issuing_authority_id: str
    key_id: str
    signature_alg: str
    approving_authority_id: str
    approval_ref: str
    approval_digest: str
    issued_at: datetime

    def __post_init__(self) -> None:
        _require_str(self.record_id, "IssuanceReceipt.record_id")
        _require_coordinate(self.coordinate, "IssuanceReceipt.coordinate")
        _require_digest(self.policy_body_digest, "IssuanceReceipt.policy_body_digest")
        _require_str(self.issuing_authority_id, "IssuanceReceipt.issuing_authority_id")
        _require_str(self.key_id, "IssuanceReceipt.key_id")
        _require_str(self.signature_alg, "IssuanceReceipt.signature_alg")
        _require_str(
            self.approving_authority_id, "IssuanceReceipt.approving_authority_id"
        )
        _require_str(self.approval_ref, "IssuanceReceipt.approval_ref")
        _require_digest(self.approval_digest, "IssuanceReceipt.approval_digest")
        _require_tzaware(self.issued_at, "IssuanceReceipt.issued_at")


@dataclass(frozen=True)
class ActivationReceipt:
    """What one activation derived: every reference-map entry, listed (`ACC-IA-3`).

    ``activated_entries`` is the complete list of ``(tenant_id,
    role_contract_ref)`` keys this activation derived from the issued record —
    each one mapping to ``coordinate`` — in ascending order. The receipt lists
    entries; it is not itself a reference map, and building a resolver still
    requires the mapping the activation call returned.
    """

    record_id: str
    coordinate: PolicyCoordinate
    activated_entries: Tuple[Tuple[str, str], ...]
    activated_at: datetime

    def __post_init__(self) -> None:
        _require_str(self.record_id, "ActivationReceipt.record_id")
        _require_coordinate(self.coordinate, "ActivationReceipt.coordinate")
        _require_tzaware(self.activated_at, "ActivationReceipt.activated_at")
        if type(self.activated_entries) is not tuple:
            raise ActivationRequestError(
                "ActivationReceipt.activated_entries must be a tuple"
            )
        for entry in self.activated_entries:
            if (
                type(entry) is not tuple
                or len(entry) != 2
                or type(entry[0]) is not str
                or type(entry[1]) is not str
            ):
                raise ActivationRequestError(
                    "every ActivationReceipt entry must be a (tenant_id, "
                    "role_contract_ref) pair of strings"
                )
            if entry[0] != self.coordinate.tenant_id:
                raise ActivationRequestError(
                    "every ActivationReceipt entry must carry the coordinate's own "
                    "tenant component"
                )
            _require_str(entry[1], "ActivationReceipt entry role_contract_ref")
        if list(self.activated_entries) != sorted(set(self.activated_entries)):
            raise ActivationRequestError(
                "ActivationReceipt.activated_entries must be strictly ascending "
                "and free of duplicates"
            )
