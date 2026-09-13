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


class AccessedSecretVersion:
    """One ``AccessSecretVersion`` answer: which version answered, and its bytes.

    A plain class with ``__slots__``, for the same reason
    :class:`ugence_model_egress_unit.CredentialLease` is one: a payload kept as a
    dataclass field is returned by ``dataclasses.asdict`` whatever ``repr=False`` says,
    and moving it out of ``fields()`` still leaves ``vars()`` and ``__dict__`` open.
    Here there is no ``__dict__`` to open and no ``fields()`` to walk, so ``vars()``
    raises ``TypeError``, ``asdict`` and ``astuple`` raise ``TypeError``, ``repr`` gives
    a size and not a value, ``==`` compares versions, and pickling and copying are
    refused.

    Bytes on purpose, and stored as given rather than coerced: decoding is the adapter's
    job and a decode failure is a refusal with the adapter's own message, so a payload
    that is not UTF-8 text never becomes a lease and a payload that is not bytes at all
    is the adapter's refusal rather than a constructor's ``TypeError``.
    """

    __slots__ = ("name", "_held")

    def __init__(self, *, name: str, payload: bytes) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "_held", payload)

    def __setattr__(self, attribute: str, value: object) -> None:
        raise AttributeError(f"an AccessedSecretVersion is immutable; {attribute!r} may not be reassigned")

    def __delattr__(self, attribute: str) -> None:
        raise AttributeError(f"an AccessedSecretVersion is immutable; {attribute!r} may not be deleted")

    @property
    def payload(self) -> bytes:
        """The bytes, for the adapter that validates them. The only way to them."""

        return self._held

    def __repr__(self) -> str:
        held = self._held
        size = len(held) if isinstance(held, (bytes, bytearray, str)) else "?"
        return f"AccessedSecretVersion(name={self.name!r}, payload=<{size} bytes, withheld>)"

    __str__ = __repr__

    def __format__(self, spec: str) -> str:
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        # Versions only: two answers never compare by payload.
        return isinstance(other, AccessedSecretVersion) and other.name == self.name

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    __hash__ = None  # type: ignore[assignment]

    def __getstate__(self):
        raise TypeError("an AccessedSecretVersion is never pickled, copied or serialized")

    __reduce__ = __getstate__
    __reduce_ex__ = lambda self, protocol: AccessedSecretVersion.__getstate__(self)  # noqa: E731
    __copy__ = __getstate__
    __deepcopy__ = lambda self, memo: AccessedSecretVersion.__getstate__(self)  # noqa: E731


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
