"""The Secret Manager client seam: a protocol the adapter uses, and the one function
that builds the real Google client.

The protocol carries exactly one method. There is no ``list_secrets``, no
``list_secret_versions`` and no ``get_secret``, because a protocol that cannot express
an operation is a stronger statement than a rule asking nobody to call it: the adapter
has no way to enumerate anything, and a test can assert the protocol's whole surface.

:func:`build_google_secret_manager_client` is the ONLY place this repository imports a
Google SDK, the import happens inside the function rather than at module scope, and it
is called from the deployment composition root and nowhere else. Importing this module
therefore reaches no network, needs no SDK installed, and constructs no client.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass
from typing import Any, Optional, Protocol, runtime_checkable

__all__ = [
    "AccessedSecretVersion",
    "SecretManagerClient",
    "GoogleClientUnavailable",
    "build_google_secret_manager_client",
]


class GoogleClientUnavailable(RuntimeError):
    """The Google SDK is not installed, or the client could not be constructed. Carries
    no provider message: see :mod:`.errors`."""


@dataclass(frozen=True)
class AccessedSecretVersion:
    """One ``AccessSecretVersion`` answer: which version answered, and its bytes.

    The bytes are **not a field of this dataclass**. They arrive as an ``InitVar`` and
    are read back through :attr:`payload`, so ``dataclasses.asdict`` and ``astuple``
    return the version name and nothing else. ``repr=False`` on a field would not have
    done that: ``asdict`` walks ``fields()`` and ignores ``repr``, which the adversarial
    pass of 2026-09-13 found on this class and on ``CredentialLease``.

    Bytes on purpose: decoding is the adapter's job and a decode failure is a refusal, so
    a payload that is not UTF-8 text never becomes a lease.
    """

    name: str
    _payload: InitVar[bytes] = b""

    def __post_init__(self, _payload: bytes) -> None:
        object.__setattr__(self, "_held", _payload)

    def __init__(self, *, name: str, payload: bytes) -> None:  # type: ignore[no-redef]
        # Written out rather than generated so the keyword stays ``payload`` for callers
        # while the value never becomes a field. Frozen, so both names are set directly.
        # The value is stored AS GIVEN and not coerced: a client that answers with
        # something that is not bytes is the adapter's refusal to make, with its own
        # message, rather than a TypeError from a constructor.
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "_held", payload)

    @property
    def payload(self) -> bytes:
        return self._held

    def __repr__(self) -> str:
        held = self._held
        size = len(held) if isinstance(held, (bytes, bytearray, str)) else "?"
        return f"AccessedSecretVersion(name={self.name!r}, payload=<{size} bytes, withheld>)"

    __str__ = __repr__

    def __eq__(self, other: object) -> bool:
        # Names only: two answers never compare by payload.
        return isinstance(other, AccessedSecretVersion) and other.name == self.name

    __hash__ = None  # type: ignore[assignment]

    def __getstate__(self):
        raise TypeError("an AccessedSecretVersion is never pickled, copied or serialized")

    def __reduce__(self):
        raise TypeError("an AccessedSecretVersion is never pickled, copied or serialized")


@runtime_checkable
class SecretManagerClient(Protocol):
    """One method. Access exactly one pinned version by its full resource name."""

    def access_secret_version(self, *, name: str) -> AccessedSecretVersion:
        ...


def build_google_secret_manager_client(*, transport: Optional[str] = None) -> SecretManagerClient:
    """The real Google client, wrapped so the adapter only ever sees the protocol.

    Call this from a deployment composition root, never at import time and never from a
    test. The credential comes from the runtime's attached service account through the
    Google auth library's discovery; this package asserts nothing about that discovery
    and relies on :class:`ugence_model_egress_unit.CustodyIdentity` to decide whether
    the identity the operator *declares* may be production-authoritative.
    """

    try:  # imported here, never at module scope: see the module docstring
        from google.cloud import secretmanager  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001 - the import error's text is not ours to repeat
        from .errors import sanitize_exception_type
        raise GoogleClientUnavailable(
            f"the Google Secret Manager client is not installed ({sanitize_exception_type(exc)}); "
            f"install this distribution's 'google' extra in the deployment image") from None
    try:
        client = (secretmanager.SecretManagerServiceClient(transport=transport)
                  if transport else secretmanager.SecretManagerServiceClient())
    except Exception as exc:  # noqa: BLE001
        from .errors import sanitize_exception_type
        raise GoogleClientUnavailable(
            f"the Google Secret Manager client could not be constructed ({sanitize_exception_type(exc)})") from None
    return _GoogleSecretManagerClient(client)


class _GoogleSecretManagerClient:
    """Narrows the SDK client to the one permitted call.

    The SDK object is private and is never returned, so a caller holding this wrapper
    cannot reach ``list_secrets`` through it.
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    def __repr__(self) -> str:  # no SDK object, no project, no endpoint
        return "_GoogleSecretManagerClient(<google-cloud-secret-manager>)"

    __str__ = __repr__

    def access_secret_version(self, *, name: str) -> AccessedSecretVersion:
        response = self._client.access_secret_version(request={"name": name})
        return AccessedSecretVersion(name=str(getattr(response, "name", "")),
                                     payload=bytes(response.payload.data))
