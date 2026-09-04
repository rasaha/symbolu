"""The credential grant and its store (ADR 5X, D-4, D-5).

A :class:`CredentialGrant` is an opaque handle *reference* plus metadata: the request
digest it was minted for, the role it carries, its validity window, and the broker that
issued it. It has no slot for secret material, its handle reference is short printable
text, and the structural test in ``tests/test_no_secret_material.py`` asserts no field in
this package could ever carry one. The store records grants by derived id and refuses a
second grant under the same id for another request.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from risk_authority.crypto.hashing import sha256_hex
from ugence_governance_contracts.api import Validity

from .errors import CredentialBrokerContractError
from .identifiers import CREDENTIAL_PROFILE, FORBIDDEN_FIELD_NAMES, GRANT_ID_PREFIX, HANDLE_REF_PATTERN
from .role import RoleStatement

__all__ = [
    "GrantDisposition",
    "CredentialGrant",
    "CredentialGrantStore",
    "InMemoryCredentialGrantStore",
    "derive_grant_id",
]

_HANDLE = re.compile(HANDLE_REF_PATTERN)


class GrantDisposition(str, Enum):
    MATERIALIZED = "MATERIALIZED"
    REPLAYED = "REPLAYED"


def derive_grant_id(request_digest: str) -> str:
    """``cred.v1:sha256(request_digest)``: one request, one grant, forever (D-4)."""

    if type(request_digest) is not str or not request_digest:
        raise CredentialBrokerContractError("derive_grant_id requires a request digest")
    return GRANT_ID_PREFIX + sha256_hex(request_digest.encode("utf-8"))[len("sha256:"):]


@dataclass(frozen=True)
class CredentialGrant:
    """An opaque handle reference and the facts that bound it. Never the secret."""

    grant_id: str
    tenant_id: str
    request_digest: str
    handle_ref: str
    role: RoleStatement
    validity: Validity
    broker_authority_id: str
    credential_profile: str
    disposition: GrantDisposition = GrantDisposition.MATERIALIZED

    def __post_init__(self) -> None:
        if type(self.handle_ref) is not str or not _HANDLE.match(self.handle_ref):
            raise CredentialBrokerContractError(
                "handle_ref must be a short printable reference; it never carries material")
        if self.grant_id != derive_grant_id(self.request_digest):
            raise CredentialBrokerContractError("grant_id does not derive from request_digest")
        if type(self.role) is not RoleStatement or type(self.validity) is not Validity:
            raise CredentialBrokerContractError("CredentialGrant carries foreign types")
        if self.validity.expires_at is None:
            raise CredentialBrokerContractError("a credential grant must expire")
        if self.credential_profile != CREDENTIAL_PROFILE:
            raise CredentialBrokerContractError(f"credential_profile must be {CREDENTIAL_PROFILE!r}")
        if type(self.disposition) is not GrantDisposition:
            raise CredentialBrokerContractError("disposition must be a GrantDisposition")
        for name in ("tenant_id", "broker_authority_id"):
            value = getattr(self, name)
            if type(value) is not str or not value.strip():
                raise CredentialBrokerContractError(f"CredentialGrant.{name} must be a non-blank str")
        leaked = {f.name for f in fields(self)} & FORBIDDEN_FIELD_NAMES
        if leaked:  # pragma: no cover — the dataclass is fixed; this guards a future edit
            raise CredentialBrokerContractError(f"CredentialGrant carries forbidden fields {sorted(leaked)}")

    @property
    def executable(self) -> bool:
        """Always ``False``: a grant is a handle, and execution is 5D's."""

        return False


@runtime_checkable
class CredentialGrantStore(Protocol):
    @property
    def is_production_authoritative(self) -> bool: ...

    def save(self, grant: CredentialGrant) -> None: ...

    def get(self, tenant_id: str, grant_id: str) -> Optional[CredentialGrant]: ...


class InMemoryCredentialGrantStore:
    """Reference store: process-local, refused in production (D-5)."""

    is_production_authoritative = False

    def __init__(self) -> None:
        self._grants: dict[tuple[str, str], CredentialGrant] = {}

    def save(self, grant: CredentialGrant) -> None:
        if type(grant) is not CredentialGrant:
            raise CredentialBrokerContractError("save requires a CredentialGrant")
        key = (grant.tenant_id, grant.grant_id)
        stored = self._grants.get(key)
        if stored is not None:
            if stored.request_digest != grant.request_digest:
                raise CredentialBrokerContractError(
                    f"grant {grant.grant_id!r} exists for another request")
            return
        self._grants[key] = grant

    def get(self, tenant_id: str, grant_id: str) -> Optional[CredentialGrant]:
        return self._grants.get((tenant_id, grant_id))
