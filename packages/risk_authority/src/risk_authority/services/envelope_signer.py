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

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from ..crypto.keys import SigningKeyRecord, validate_key_window
from ..crypto.signing import SIGNATURE_ALG
from ..domain.errors import RiskAuthorityError

__all__ = [
    "EnvelopeSignerPort",
    "WindowedEnvelopeSignerPort",
    "ReferenceEnvelopeSigner",
    "signer_window",
]


@runtime_checkable
class EnvelopeSignerPort(Protocol):
    """Sign a package-computed envelope payload under one identified key.

    Unchanged by issue #1398: an existing signer that declares no window keeps working and
    its key is unbounded-valid (ruling 1). Declaring a bounded key is the additive
    :class:`WindowedEnvelopeSignerPort` capability below.
    """

    @property
    def key_id(self) -> str: ...

    @property
    def signature_alg(self) -> str: ...

    @property
    def is_production_authoritative(self) -> bool: ...

    def sign(self, payload: bytes) -> bytes: ...


@runtime_checkable
class WindowedEnvelopeSignerPort(EnvelopeSignerPort, Protocol):
    """An :class:`EnvelopeSignerPort` that declares its key's validity window.

    Additive rather than a change to the base Protocol, so no existing implementation
    breaks (issue #1398 ruling 4). A signer that declares bounds is held to them:
    :meth:`EnvelopeIssuer.issue` refuses to invoke ``sign`` outside the window, so an
    external signer cannot bypass issuance-time validation by living behind the port.

    This declares a **metadata and validation contract only**. It is not an HSM/KMS
    integration, performs no key generation, defines no custody mechanism, and makes no
    provider call — those remain out of scope and unbuilt.
    """

    @property
    def not_before(self) -> Optional[datetime]: ...

    @property
    def not_after(self) -> Optional[datetime]: ...


def signer_window(signer: object) -> "tuple[Optional[datetime], Optional[datetime]]":
    """Read a signer's declared window, or ``(None, None)`` when it declares none.

    Reads the attributes rather than requiring the Protocol, so a signer predating
    :class:`WindowedEnvelopeSignerPort` that happens to carry the fields is still held to
    them. Silence means unbounded — never a refusal (ruling 1) — but a *malformed*
    declaration is a refusal, because a signer that tried to express bounds and got them
    wrong must not be read as unbounded.
    """

    not_before = getattr(signer, "not_before", None)
    not_after = getattr(signer, "not_after", None)
    validate_key_window(not_before, not_after, owner=type(signer).__name__)
    return not_before, not_after


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

    @property
    def not_before(self):
        return self._record.not_before

    @property
    def not_after(self):
        return self._record.not_after

    def sign(self, payload: bytes) -> bytes:
        if not isinstance(payload, (bytes, bytearray)) or not payload:
            raise RiskAuthorityError("signer refuses an empty or non-bytes payload")
        return self._record.signing_key.sign(bytes(payload))
