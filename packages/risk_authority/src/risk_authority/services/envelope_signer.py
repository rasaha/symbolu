"""The envelope signer port (Phase 5, decision D-5).

Mirrors Trusted Evidence Authority's ``ReceiptSignerPort``: the issuer hands a
signer the exact canonical bytes it must sign and receives a signature; it never
touches key material. An HSM- or KMS-backed signer implements the same port and
drops in without touching a caller. What a signer cannot be handed is bytes of
the caller's choosing — the issuer computes the payload.

:class:`ReferenceEnvelopeSigner` wraps an in-memory :class:`SigningKeyRecord`. It
is the conformance signer and declares ``is_production_authoritative = False``,
so the production issuance seam refuses it at construction rather than minting a
production envelope under an in-process key.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..crypto.keys import SigningKeyRecord
from ..crypto.signing import SIGNATURE_ALG
from ..domain.errors import RiskAuthorityError

__all__ = ["EnvelopeSignerPort", "ReferenceEnvelopeSigner"]


@runtime_checkable
class EnvelopeSignerPort(Protocol):
    """Sign a package-computed envelope payload under one identified key."""

    @property
    def key_id(self) -> str: ...

    @property
    def signature_alg(self) -> str: ...

    @property
    def is_production_authoritative(self) -> bool: ...

    def sign(self, payload: bytes) -> bytes: ...


class ReferenceEnvelopeSigner:
    """In-memory Ed25519 signer over a :class:`SigningKeyRecord`. Never production."""

    is_production_authoritative = False

    def __init__(self, key_record: SigningKeyRecord) -> None:
        if not isinstance(key_record, SigningKeyRecord):
            raise RiskAuthorityError("ReferenceEnvelopeSigner requires a SigningKeyRecord")
        self._record = key_record

    @property
    def key_id(self) -> str:
        return self._record.key_id

    @property
    def signature_alg(self) -> str:
        return SIGNATURE_ALG

    def sign(self, payload: bytes) -> bytes:
        if not isinstance(payload, (bytes, bytearray)) or not payload:
            raise RiskAuthorityError("signer refuses an empty or non-bytes payload")
        return self._record.signing_key.sign(bytes(payload))
