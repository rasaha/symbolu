"""Key retrieval (IA-3): one configured JWKS URL, keys cached by ``kid``, one refresh
on an unknown ``kid``, then fail closed. No discovery document is ever fetched, and
TLS verification is the standard library's default and is never relaxed."""

from __future__ import annotations

import json
import urllib.request
from typing import Callable, Dict, Optional

import jwt

from .config import AdapterConfig
from .errors import KeyRetrievalFailed

__all__ = ["JwksKeyCache", "MAX_JWKS_BYTES"]

#: A JWKS larger than this is refused as malformed rather than read.
MAX_JWKS_BYTES = 256 * 1024


def _default_fetch(url: str, timeout_s: float) -> bytes:
    """GET the JWKS with the standard library. Default TLS context: verification on."""

    request = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return response.read(MAX_JWKS_BYTES + 1)


class JwksKeyCache:
    """Public keys by ``kid``. Holds public material only.

    ``fetch`` is injectable for tests and is the only place bytes come in from
    outside. Every failure to fetch or parse is ``KeyRetrievalFailed``, a typed
    ``IdentityUnavailable``: the caller cannot tell a token apart from a key outage
    and must not try.
    """

    def __init__(self, config: AdapterConfig, *,
                 fetch: Callable[[str, float], bytes] = _default_fetch) -> None:
        self._config = config
        self._fetch = fetch
        self._keys: Dict[str, jwt.PyJWK] = {}
        self.fetch_count = 0

    @property
    def known_kids(self) -> frozenset:
        return frozenset(self._keys)

    def key_for(self, kid: str) -> Optional[jwt.PyJWK]:
        """The key for ``kid``: from the cache, else after exactly one refresh, else
        ``None``. Raises ``KeyRetrievalFailed`` when the refresh itself fails."""

        key = self._keys.get(kid)
        if key is not None:
            return key
        self.refresh()
        return self._keys.get(kid)

    def refresh(self) -> None:
        self.fetch_count += 1
        try:
            raw = self._fetch(self._config.jwks_url, self._config.fetch_timeout_s)
        except Exception as exc:  # noqa: BLE001 - URLError, timeout, TLS, HTTP status, ...
            raise KeyRetrievalFailed(
                f"JWKS could not be fetched: {type(exc).__name__}") from None
        if not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_JWKS_BYTES:
            raise KeyRetrievalFailed("JWKS response is not bytes or exceeds the size ceiling")
        try:
            document = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            raise KeyRetrievalFailed("JWKS response is not JSON") from None
        if not isinstance(document, dict) or not isinstance(document.get("keys"), list):
            raise KeyRetrievalFailed("JWKS document has no 'keys' list")
        parsed: Dict[str, jwt.PyJWK] = {}
        for entry in document["keys"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("kid"), str) \
                    or not entry["kid"]:
                raise KeyRetrievalFailed("JWKS entry without a string 'kid'")
            if entry.get("kty") == "oct" or "k" in entry:
                # A symmetric key can never verify a permitted algorithm and must never
                # be held here (IA-2).
                raise KeyRetrievalFailed("JWKS entry is a symmetric key")
            try:
                parsed[entry["kid"]] = jwt.PyJWK(entry)
            except Exception as exc:  # noqa: BLE001 - PyJWKError and friends
                raise KeyRetrievalFailed(
                    f"JWKS entry could not be parsed: {type(exc).__name__}") from None
        # Replace, never merge: a rotated-out key is gone after the refresh.
        self._keys = parsed
