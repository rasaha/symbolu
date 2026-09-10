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
claim stays intact — the worker talks to one host, and that host is its identity
provider. Whether a *live* provider may ever run here is an open owner decision
(``docs/architecture/OWNER_RATIFICATION_LIVE_MODEL_PROVIDER.md``, D-1 to D-5) and
this package neither answers it nor presumes an answer.
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
)
from .errors import (
    ExchangeError,
    RequestNotClaimable,
    ResultNotAcknowledgeable,
    TenantMismatch,
    UnscopableConnection,
)
from .provider import (
    REFERENCE_RESPONSE_MARKER,
    DeterministicFakeProvider,
    EgressProvider,
    LiveEgressUnavailableProvider,
    ProviderRefusedInProduction,
)
from .reconcile import ReconciliationPass, ReconciliationScheduler
from .records import (
    TERMINAL_STATES,
    EgressRequest,
    EgressResult,
    RefusalReason,
    RequestState,
    ResultOutcome,
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
    "EgressProvider",
    "DeterministicFakeProvider",
    "LiveEgressUnavailableProvider",
    "ProviderRefusedInProduction",
    "REFERENCE_RESPONSE_MARKER",
    "EgressUnit",
    "UnitPass",
    "ReconciliationScheduler",
    "ReconciliationPass",
]
