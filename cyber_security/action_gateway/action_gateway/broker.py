"""Credential broker abstraction.

Tool adapters NEVER hold standing credentials and never execute directly. They
receive a short-lived, scoped capability from a broker, and only after the
gateway has verified an execution token. The broker:

  * issues a capability bound to a specific verified token hash;
  * refuses to widen scope beyond what the token permits (scope-expansion
    defence, independent of the token's own action-hash binding);
  * expires the capability at min(token expiry, requested TTL);
  * can be revoked, and validates capabilities by identity at use time so a
    forged capability object (not minted by this broker) is rejected.

``MockCredentialBroker`` mints no real secrets — the capability is an opaque
handle. Production key custody / real short-lived credentials are OUT OF SCOPE
(see README).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from .clock import parse_ts
from .errors import CredentialError


@dataclass(frozen=True)
class ScopedCredential:
    credential_id: str
    principal: str
    permissions: frozenset
    token_hash: str
    expires_at: str  # RFC-3339 UTC ms
    # NOTE: no secret material — this is a capability handle, not a credential value.


class CredentialBroker:
    """Interface. Implementations mint scoped, token-bound capabilities."""

    def issue(self, *, token: dict, requested_permissions, principal: str,
              now: str) -> ScopedCredential:  # pragma: no cover - interface
        raise NotImplementedError

    def validate(self, credential: ScopedCredential, *, needed_permission: str,
                 now: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def revoke(self, credential: ScopedCredential) -> None:  # pragma: no cover
        raise NotImplementedError


def _covers(perm_set, needed: str) -> bool:
    if needed in perm_set:
        return True
    for p in perm_set:
        if p == "*" or (p.endswith(":*") and needed.startswith(p[:-1])):
            return True
    return False


class MockCredentialBroker(CredentialBroker):
    def __init__(self):
        self._issued: dict[str, ScopedCredential] = {}
        self._revoked: set[str] = set()
        self._counter = itertools.count(1)

    def issue(self, *, token: dict, requested_permissions, principal: str,
              now: str) -> ScopedCredential:
        token_scope = set(token["payload"]["credential_scope"].get("permissions", []))
        requested = set(requested_permissions)
        # scope-expansion defence: every requested permission must be within the
        # token's approved credential scope.
        for perm in requested:
            if not _covers(token_scope, perm):
                raise CredentialError(
                    f"requested permission {perm!r} exceeds approved credential scope")
        # capability expires no later than the token it is bound to.
        token_exp = token["payload"]["expiration"]
        cred = ScopedCredential(
            credential_id=f"cred-{next(self._counter)}",
            principal=principal,
            permissions=frozenset(requested),
            token_hash=token["token_hash"],
            expires_at=token_exp,
        )
        self._issued[cred.credential_id] = cred
        return cred

    def validate(self, credential: ScopedCredential, *, needed_permission: str,
                 now: str) -> bool:
        # identity check: reject any capability this broker did not mint (forgery).
        known = self._issued.get(credential.credential_id)
        if known is None or known != credential:
            raise CredentialError("unknown or forged credential")
        if credential.credential_id in self._revoked:
            raise CredentialError("credential revoked")
        if parse_ts(now) >= parse_ts(credential.expires_at):
            raise CredentialError("credential expired")
        if not _covers(credential.permissions, needed_permission):
            raise CredentialError(
                f"credential lacks permission {needed_permission!r}")
        return True

    def revoke(self, credential: ScopedCredential) -> None:
        self._revoked.add(credential.credential_id)
