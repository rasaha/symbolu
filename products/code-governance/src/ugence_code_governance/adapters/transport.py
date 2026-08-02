"""Strict read-only transport boundary for enterprise adapters.

Only explicitly approved **read** operations are permitted. Mutating HTTP methods
(POST/PUT/PATCH/DELETE/…) and GraphQL mutations are rejected structurally. Host and
path allowlists, bounded timeouts, bounded response sizes, content-type validation,
and redirect-host validation are enforced here — no adapter may bypass this
boundary with a private client.

Credentials may be supplied through a ``CredentialResolver`` and are used only to
authenticate the outbound read. They are NEVER returned in a response, embedded in
a fingerprint, written to the durable store, or included in an error message.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlparse

from .errors import (
    AdapterResponseError,
    CredentialLeakError,
    ReadOnlyBoundaryViolation,
)

#: The only permitted (read) HTTP methods.
_READ_METHODS = {"GET", "HEAD"}
#: Explicitly refused mutating methods (rejected even if a caller passes them).
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE", "CONNECT", "OPTIONS", "TRACE"}
#: Header names that carry credentials and must never be returned/persisted/logged.
_CREDENTIAL_HEADER_NAMES = frozenset({
    "authorization", "proxy-authorization", "cookie", "set-cookie",
    "x-api-key", "x-auth-token", "private-token",
})


CredentialResolver = Callable[[str], Mapping[str, str]]


@dataclass(frozen=True)
class TransportPolicy:
    """The read-only boundary policy for one adapter/source."""

    allowed_hosts: Tuple[str, ...]
    allowed_path_prefixes: Tuple[str, ...] = ()
    allow_head: bool = False
    max_response_bytes: int = 1_000_000
    timeout_s: float = 10.0
    allowed_content_types: Tuple[str, ...] = ("application/json",)
    max_redirects: int = 0


@dataclass(frozen=True)
class ReadOnlyResponse:
    """A bounded, credential-free read response."""

    status: int
    content_type: str
    body: bytes
    #: response headers with all credential-bearing names removed
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RawResponse:
    """What a concrete transport backend returns before boundary validation."""

    status: int
    content_type: str
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)
    #: for redirect handling only (never followed automatically past the policy)
    redirect_location: Optional[str] = None


def _strip_credentials(headers: Mapping[str, str]) -> Dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _CREDENTIAL_HEADER_NAMES}


class ReadOnlyTransport:
    """Boundary-enforcing base transport. Backends implement ``_perform`` only."""

    def __init__(self, policy: TransportPolicy,
                 credential_resolver: Optional[CredentialResolver] = None) -> None:
        self._policy = policy
        self._resolver = credential_resolver

    @property
    def policy(self) -> TransportPolicy:
        return self._policy

    # --- public read API -------------------------------------------------
    def get(self, url: str, *, source_id: str) -> ReadOnlyResponse:
        return self.request("GET", url, source_id=source_id)

    def head(self, url: str, *, source_id: str) -> ReadOnlyResponse:
        return self.request("HEAD", url, source_id=source_id)

    def request(self, method: str, url: str, *, source_id: str,
                _redirects: int = 0) -> ReadOnlyResponse:
        m = (method or "").upper()
        if m in _MUTATING_METHODS or m not in _READ_METHODS:
            raise ReadOnlyBoundaryViolation(f"method {method!r} is not read-only")
        if m == "HEAD" and not self._policy.allow_head:
            raise ReadOnlyBoundaryViolation("HEAD is not permitted by this transport policy")
        self._check_url(url)
        headers = self._auth_headers(source_id)
        raw = self._perform(m, url, headers)
        # Redirects are validated, never blindly followed.
        if raw.redirect_location is not None:
            if _redirects >= self._policy.max_redirects:
                raise ReadOnlyBoundaryViolation("redirect not permitted by policy")
            self._check_url(raw.redirect_location)  # must stay within the allowlist
            return self.request(m, raw.redirect_location, source_id=source_id,
                                _redirects=_redirects + 1)
        self._validate_response(raw)
        return ReadOnlyResponse(status=raw.status, content_type=raw.content_type,
                                body=raw.body, headers=_strip_credentials(raw.headers))

    # --- boundary checks -------------------------------------------------
    def _check_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http"):
            raise ReadOnlyBoundaryViolation(f"unsupported scheme in {parsed.scheme!r}")
        host = parsed.hostname or ""
        if host not in self._policy.allowed_hosts:
            raise ReadOnlyBoundaryViolation(f"host {host!r} not in allowlist")
        if self._policy.allowed_path_prefixes:
            if not any(parsed.path.startswith(p) for p in self._policy.allowed_path_prefixes):
                raise ReadOnlyBoundaryViolation(f"path {parsed.path!r} not in allowlist")

    def _validate_response(self, raw: RawResponse) -> None:
        if len(raw.body) > self._policy.max_response_bytes:
            raise AdapterResponseError(
                f"response exceeds {self._policy.max_response_bytes} bytes")
        ctype = (raw.content_type or "").split(";")[0].strip().lower()
        allowed = tuple(c.lower() for c in self._policy.allowed_content_types)
        if ctype and allowed and ctype not in allowed:
            raise AdapterResponseError(f"unexpected content type {ctype!r}")

    def _auth_headers(self, source_id: str) -> Dict[str, str]:
        if self._resolver is None:
            return {}
        creds = dict(self._resolver(source_id))
        # Defensive: a resolver must only hand back header material, never leak it back.
        return creds

    def _perform(self, method: str, url: str, headers: Mapping[str, str]) -> RawResponse:
        raise NotImplementedError


class FakeReadOnlyTransport(ReadOnlyTransport):
    """Deterministic, offline transport for tests and the offline demo.

    Responses are keyed by ``(method, url)``. It records every attempt (without
    credential values) so tests can assert read-only behavior without a network.
    """

    def __init__(self, policy: TransportPolicy,
                 responses: Optional[Mapping[Tuple[str, str], RawResponse]] = None,
                 credential_resolver: Optional[CredentialResolver] = None) -> None:
        super().__init__(policy, credential_resolver)
        self._responses: Dict[Tuple[str, str], RawResponse] = dict(responses or {})
        self.attempts: List[Tuple[str, str]] = []
        #: credential header names seen by the backend (values are never stored)
        self.credential_header_names_seen: List[str] = []

    def set_response(self, method: str, url: str, response: RawResponse) -> None:
        self._responses[(method.upper(), url)] = response

    def _perform(self, method: str, url: str, headers: Mapping[str, str]) -> RawResponse:
        self.attempts.append((method, url))
        for name in headers:
            if name.lower() in _CREDENTIAL_HEADER_NAMES:
                self.credential_header_names_seen.append(name)
        key = (method, url)
        if key not in self._responses:
            raise AdapterResponseError(f"no fake response configured for {method} {url}")
        return self._responses[key]


__all__ = [
    "TransportPolicy",
    "ReadOnlyResponse",
    "RawResponse",
    "ReadOnlyTransport",
    "FakeReadOnlyTransport",
    "CredentialResolver",
]
