"""Ugence Cloud Scaling Credential Broker — Phase 5X.

**A grant is a handle, not execution.** This package exchanges an admitted (5C) and reserved
(execution-reservation) capacity action for a short-lived, least-privilege credential
handle through a broker port, and holds no provider secret to do it:

* :class:`CredentialBrokerPort` — mirrors the Trusted Evidence Authority signer port:
  ``broker_authority_id``, ``credential_profile``, ``is_production_authoritative``,
  ``materialize(request) -> CredentialGrant``. :class:`ReferenceCredentialBroker` returns an
  inert handle and is refused in production (D-1);
* :class:`CredentialRequest` — package-minted behind a private token by
  :class:`CredentialRequestMinter`, binding the authorization ref, the execution key, the
  target-scope digest, the reservation id, the derived role and a request digest (D-2);
* :func:`derive_least_privilege_role` — a pure function of the target scope; ``no_change``
  derives nothing; a broker may narrow and never widen (D-3);
* :class:`CredentialBrokerSeam` — one clock read; ``expires_at`` is the minimum of the
  authorization, lease and envelope expiries and ``issued_at + ttl_cap`` with the cap at
  most fifteen minutes; grant ids derive from the request digest and replay (D-4);
* :class:`CredentialGrant` — an opaque handle reference, the request digest and the
  validity window; no field can carry secret material, and the store persists only that (D-5).

What it does **not** do: read a clock; hold, load, persist, canonicalise or digest a
secret; call a cloud provider or Kubernetes; dispatch or execute anything (5D). LIVE
execution stays structurally blocked until 5D exists.
"""

from __future__ import annotations

from .broker import REFERENCE_BROKER_AUTHORITY_ID, CredentialBrokerPort, ReferenceCredentialBroker
from .errors import (
    CloudScalingCredentialBrokerError,
    CredentialBrokerConfigurationError,
    CredentialBrokerContractError,
    CredentialBrokerExactTypeError,
    CredentialRequestRefused,
)
from .grant import (
    CredentialGrant,
    CredentialGrantStore,
    GrantDisposition,
    InMemoryCredentialGrantStore,
    derive_grant_id,
)
from .identifiers import (
    CREDENTIAL_PROFILE,
    DEFAULT_TTL_CAP,
    FORBIDDEN_FIELD_NAMES,
    GRANT_ID_PREFIX,
    HANDLE_REF_PATTERN,
    MAX_TTL_CAP,
    REQUEST_DIGEST_PREFIX,
)
from .request import CredentialRefusal, CredentialRequest, CredentialRequestMinter, derive_request_digest
from .role import NO_CREDENTIAL_ACTION_TYPES, RoleStatement, derive_least_privilege_role, role_widening
from .seam import CredentialBrokerSeam, CredentialMaterializationOutcome, CredentialMaterializationRequest
from .version import __version__

__all__ = [
    "__version__",
    # --- the seam and its request/outcome ---
    "CredentialBrokerSeam",
    "CredentialMaterializationRequest",
    "CredentialMaterializationOutcome",
    "CredentialRefusal",
    # --- the broker port ---
    "CredentialBrokerPort",
    "ReferenceCredentialBroker",
    "REFERENCE_BROKER_AUTHORITY_ID",
    # --- the request, minted only here ---
    "CredentialRequest",
    "CredentialRequestMinter",
    "derive_request_digest",
    # --- the role ---
    "RoleStatement",
    "derive_least_privilege_role",
    "role_widening",
    "NO_CREDENTIAL_ACTION_TYPES",
    # --- the grant and its store ---
    "CredentialGrant",
    "GrantDisposition",
    "CredentialGrantStore",
    "InMemoryCredentialGrantStore",
    "derive_grant_id",
    # --- identifiers and limits ---
    "CREDENTIAL_PROFILE",
    "GRANT_ID_PREFIX",
    "REQUEST_DIGEST_PREFIX",
    "MAX_TTL_CAP",
    "DEFAULT_TTL_CAP",
    "FORBIDDEN_FIELD_NAMES",
    "HANDLE_REF_PATTERN",
    # --- typed errors ---
    "CloudScalingCredentialBrokerError",
    "CredentialBrokerConfigurationError",
    "CredentialBrokerContractError",
    "CredentialBrokerExactTypeError",
    "CredentialRequestRefused",
]
