"""Ugence Model Egress Unit — the reference exchange between the worker and a model call.

**This distribution cannot call a model vendor.** It carries no HTTP client, no
vendor SDK, no credential reader and no destination configuration, and the only
providers it ships compute their answers from a hash or refuse outright. What is
real here is the boundary: a dedicated PostgreSQL schema, three roles of which the
owner cannot log in, forced row-level security keyed on a required tenant
identity, request and result records with complete canonical digests, terminal
refusals, ``OUTCOME_UNKNOWN``, consumption acknowledgement, and content purge
leaving digest-only tombstones.

The unit exists as a separate deployment unit so the governance worker's egress
claim stays intact. **D-1 through D-5 were ratified on 2026-09-10**, together with
the exchange grants and tenancy and the retention horizons; this package is written
against those rulings. What remains unauthorized is a *live* provider: D-3 keeps
provider custody out of this deployment, and CR-1 still admits only one companion
deployment unit, so the MEU's boundary is specified while its commissioning as a
running unit is not `[G]`.

Since 0.2.0 (2026-09-11) the package carries the three pieces of mechanism the
commissioning ballot (``ADR_UGENCE_LIVE_MODEL_PROVIDER_COMMISSIONING.md``) can carry
before the owner rules: the provider-credential custody **port** with an inert
reference adapter (``custody``), the ledger-kind schema that refuses content-bearing
keys (``ledger_kinds``), and transport protection for the exchange's own DSNs
(``postgres.transport``). None of them holds, reads or reaches a credential; the
owner's designations (OpenAI; Google Secret Manager) live in
``MEU_LIVE_PROVIDER_DESIGNATION.json`` beside the package, and
``MEU_LIVE_VALIDATION.json`` stays ``BLOCKED_PENDING_OWNER_RULINGS``.
"""

from __future__ import annotations

from .canonical import (
    EGRESS_REQUEST_DIGEST_DOMAIN,
    EGRESS_RESULT_DIGEST_DOMAIN,
    EXCHANGE_CONTENT_DIGEST_DOMAIN,
    MEU_CANONICALIZATION_VERSION,
    CanonicalizationError,
    canonical_bytes,
    canonical_digest,
    content_digest,
    minimized_context_digest,
    payload_digest,
)
from .custody import (
    CUSTODY_AUDIT_DOMAIN,
    CUSTODY_REQUEST_DOMAIN,
    REFERENCE_CUSTODY_MARKER,
    CredentialLease,
    CredentialRequest,
    CustodyAuditEvent,
    CustodyRefusal,
    CustodyRefused,
    CustodyRefusedInProduction,
    ModelCredentialCustodyPort,
    ReferenceCustodyAdapter,
    materialize_with_audit,
)
from .errors import (
    ExchangeError,
    RequestNotClaimable,
    ResultNotAcknowledgeable,
    TenantMismatch,
    UnscopableConnection,
)
from .ledger_kinds import (
    CONTENT_BEARING_KEYS,
    MAX_LEDGER_STRING,
    MEU_LEDGER_KINDS,
    LedgerKindViolation,
    ledger_payload,
    result_ledger_payload,
)
from .provider import (
    REFERENCE_CLEARANCE_DOMAIN,
    REFERENCE_RESPONSE_MARKER,
    DeterministicFakeProvider,
    EgressProvider,
    LiveEgressUnavailableProvider,
    ProviderRefusedInProduction,
    reference_clearance,
)
from .reconcile import ReconciliationPass, ReconciliationScheduler
from .records import (
    ACKNOWLEDGEMENT_GRACE,
    EXCHANGE_SCHEMA_VERSION,
    HARD_RETENTION_DEADLINE,
    TERMINAL_STATES,
    TRUST_LEVEL,
    AuthorizationBinding,
    DispatchAttempt,
    EgressRequest,
    EgressResult,
    MinimizedUnit,
    ProvenanceKind,
    RefusalReason,
    RequestState,
    ResultOutcome,
    purge_deadline,
)
from .unit import EgressUnit, UnitPass
from .version import (
    CONTRACT_VERSION,
    ENFORCEMENT_ENABLED,
    LIVE_VENDOR_EGRESS,
    MATURITY,
    __version__,
)

__all__ = [
    "__version__",
    "CONTRACT_VERSION",
    "MATURITY",
    "ENFORCEMENT_ENABLED",
    "LIVE_VENDOR_EGRESS",
    "MEU_CANONICALIZATION_VERSION",
    "EGRESS_REQUEST_DIGEST_DOMAIN",
    "EGRESS_RESULT_DIGEST_DOMAIN",
    "EXCHANGE_CONTENT_DIGEST_DOMAIN",
    "CanonicalizationError",
    "canonical_bytes",
    "canonical_digest",
    "content_digest",
    "minimized_context_digest",
    "payload_digest",
    "EXCHANGE_SCHEMA_VERSION",
    "TRUST_LEVEL",
    "ACKNOWLEDGEMENT_GRACE",
    "HARD_RETENTION_DEADLINE",
    "purge_deadline",
    "AuthorizationBinding",
    "MinimizedUnit",
    "DispatchAttempt",
    "ProvenanceKind",
    "RequestState",
    "ResultOutcome",
    "RefusalReason",
    "TERMINAL_STATES",
    "EgressRequest",
    "EgressResult",
    "ExchangeError",
    "UnscopableConnection",
    "TenantMismatch",
    "RequestNotClaimable",
    "ResultNotAcknowledgeable",
    "CUSTODY_AUDIT_DOMAIN",
    "CUSTODY_REQUEST_DOMAIN",
    "REFERENCE_CUSTODY_MARKER",
    "CredentialRequest",
    "CredentialLease",
    "CustodyAuditEvent",
    "CustodyRefusal",
    "CustodyRefused",
    "CustodyRefusedInProduction",
    "ModelCredentialCustodyPort",
    "ReferenceCustodyAdapter",
    "materialize_with_audit",
    "MEU_LEDGER_KINDS",
    "CONTENT_BEARING_KEYS",
    "MAX_LEDGER_STRING",
    "LedgerKindViolation",
    "ledger_payload",
    "result_ledger_payload",
    "EgressProvider",
    "DeterministicFakeProvider",
    "LiveEgressUnavailableProvider",
    "ProviderRefusedInProduction",
    "REFERENCE_RESPONSE_MARKER",
    "REFERENCE_CLEARANCE_DOMAIN",
    "reference_clearance",
    "EgressUnit",
    "UnitPass",
    "ReconciliationScheduler",
    "ReconciliationPass",
]
