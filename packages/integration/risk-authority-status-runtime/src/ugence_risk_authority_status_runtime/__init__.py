"""Ugence Risk Authority Status Runtime — RA-6 authority-lifecycle operationalization.

RA-6 makes the Risk Authority leaf's **already-present but operationally inert**
authority-lifecycle mechanism *operate*. The leaf already carries a signed
``authority_epoch``, a pure ``RevocationState`` predicate, an offline verifier
that rejects expiry / revocation / stale epoch, the terminal
``REVOKED/EXPIRED/SUPERSEDED`` states, and the ``ENVELOPE_REVOKED`` /
``AUTHORITY_EPOCH_ADVANCED`` events. What was missing was the **write side,
persistence, distribution, signal intake, and last-mile recheck** — this package
supplies exactly those, behind the three neutral leaf ports, and **introduces no
second authority artifact**. The Ed25519-signed ``RiskAuthorizationEnvelope``
remains the sole machine-execution authority.

Ratified model (RA-6 §4): SHORT TTL + MONOTONIC AUTHORITY EPOCH + TARGETED
REVOCATION, with a persisted authoritative store, event/pull propagation, a
bounded-stale local read cache, and an offline hot path.

    material change
        → AuthorityReassessmentSignal            (neutral; carries no authority)
        → AuthorityReassessor                     (validate + dedupe + reassess)
        → AuthorityLifecycleService (authenticated writer; sole mutator)
        → advance epoch / targeted revoke / no-op (monotonic, idempotent)
        → ReferenceAuthorityStore  →  AuthorityStatusCache (bounded-stale)
        → StatusAwareActionGate / pre-effect recheck observe invalid authority
        → DENY / stop execution

Dependency direction is one-way (``ugence-risk-authority`` stays a stdlib-only
leaf):

    risk_authority (leaf: ports + domain + pure predicate)
        ▲
    ugence_risk_authority_status_runtime (this package: persistence + writer +
        cache + reassessor + enforcement composition)

**Maturity (no overclaim, RA-6 §22):** this package implements *code-level
authority-lifecycle enforcement* with a **reference in-memory** persistence
adapter, in-process propagation, and a **delegated** authentication/authorization
seam (the deployment injects the real authenticated writer authorizer;
``ReferenceWriterAuthorizer`` is refused in production, RA-5 F-1 pattern).
Production Postgres persistence and real signal transport are delegated
(:mod:`.postgres`) — this is NOT globally-consistent, cryptographically-attested,
multi-region, or zero-window revocation.

See ``docs/architecture/RISK_AUTHORITY_RA6_SPEC.md`` (ratified, SHA e4b548a1).
"""

from __future__ import annotations

from .cache import AuthorityStatusCache
from .case_lifecycle import (
    expire_case_if_elapsed,
    reconcile_case_state,
    revoke_case,
    supersede_case,
)
from .enforcement import (
    PreEffectContext,
    StatusAwareActionGate,
    StatusAwareGateResult,
    make_pre_effect_recheck,
)
from .postgres import PostgresAuthorityStoreFactory, PostgresNotConfiguredError
from .reassessor import (
    AuthorityReassessor,
    ReassessmentAction,
    ReassessmentActionKind,
    ReassessmentDecider,
    ReferenceReassessmentDecider,
)
from .store import AuthorityStateExport, BASE_EPOCH, ReferenceAuthorityStore
from .version import __version__
from .writer import (
    EMERGENCY_STOP_CAPABILITY,
    LIFECYCLE_WRITE_CAPABILITY,
    AuthorityLifecycleService,
    ReferenceWriterAuthorizer,
    ReferenceWriterRejectedError,
    WriterAuthorizer,
)

__all__ = [
    "__version__",
    # store
    "ReferenceAuthorityStore",
    "AuthorityStateExport",
    "BASE_EPOCH",
    # cache
    "AuthorityStatusCache",
    # writer
    "AuthorityLifecycleService",
    "WriterAuthorizer",
    "ReferenceWriterAuthorizer",
    "ReferenceWriterRejectedError",
    "LIFECYCLE_WRITE_CAPABILITY",
    "EMERGENCY_STOP_CAPABILITY",
    # reassessor
    "AuthorityReassessor",
    "ReassessmentAction",
    "ReassessmentActionKind",
    "ReassessmentDecider",
    "ReferenceReassessmentDecider",
    # case lifecycle
    "reconcile_case_state",
    "expire_case_if_elapsed",
    "revoke_case",
    "supersede_case",
    # enforcement
    "StatusAwareActionGate",
    "StatusAwareGateResult",
    "PreEffectContext",
    "make_pre_effect_recheck",
    # production skeleton
    "PostgresAuthorityStoreFactory",
    "PostgresNotConfiguredError",
]
