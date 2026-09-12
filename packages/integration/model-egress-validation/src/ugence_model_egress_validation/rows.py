"""The eighteen validation rows (LP-4), as the harness knows them.

``offline`` says whether the row can be exercised with injected fake components and no
infrastructure. A row that is not offline-executable is reported with the reason and is
never marked conformant here: ruling 11 forbids marking an infrastructure-dependent row
as passed, and rows that need the exchange or an external verifier are named as such.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

__all__ = ["Row", "ROWS", "OFFLINE_ROWS", "STATUS_VOCABULARY"]

#: Per-row statuses this distribution can write. There is no PASS: a pass is the live
#: verifier's word, written into ``MEU_LIVE_VALIDATION.json`` by the owner's run.
STATUS_VOCABULARY = (
    "OFFLINE_CONFORMANT",          # fake components behaved exactly as the row requires
    "OFFLINE_NONCONFORMANT",       # they did not; the report says what was observed
    "NOT_EXECUTABLE_OFFLINE",      # infrastructure-, exchange- or verifier-dependent
)


@dataclass(frozen=True)
class Row:
    row: int
    scenario: str
    required: str
    offline: bool
    reason_if_not_offline: Optional[str] = None
    infrastructure_dependent: bool = False
    #: For a row that is not offline-executable: the specific external evidence the
    #: owner-run live verifier must produce before the row can carry a result.
    external_evidence_required: Optional[str] = None


ROWS: Tuple[Row, ...] = (
    Row(1, "custody absent", "REFUSED_CREDENTIAL_NOT_COMMISSIONED", True),
    Row(2, "credential never in any log, ledger row, exchange row, evidence report or answer", "NO_OCCURRENCE", True),
    Row(3, "egress to any URL but https://api.openai.com/v1/responses", "REFUSED_DESTINATION_NOT_PERMITTED", True),
    Row(4, "request digest binds the minimized context; a substituted prompt", "REFUSED_CONTENT_DIGEST_MISMATCH", True),
    Row(5, "model identifier is the floating alias, not the pinned snapshot", "REFUSED_MODEL_NOT_PINNED", True),
    Row(6, "input over 8,192 tokens", "REFUSED_REQUEST_LIMIT_EXCEEDED", True),
    Row(7, "max_output_tokens over 1,024", "REFUSED_REQUEST_LIMIT_EXCEEDED", True),
    Row(8, "streaming, store, tools, background or a previous response requested", "REFUSED_REQUEST_LIMIT_EXCEEDED", True),
    Row(9, "eleventh genuine call, or a reservation over USD 25, or a second concurrent request", "REFUSED_COMMISSIONING_BUDGET_EXHAUSTED", True),
    Row(10, "secret version named as latest, or a service-account-key identity", "REFUSED_AT_CONSTRUCTION", True),
    Row(11, "custody lease expired at use", "REFUSED_CUSTODY_UNAVAILABLE", True),
    Row(12, "the live answer's provenance", "GENUINE_CALL_TRUE_LEASE_PRODUCTION_AUTHORITATIVE_TRUST_UNTRUSTED_EVIDENCE", False,
        "a genuine answer needs the live transport, the commissioned credential and both predecessor gates of ADR §0.5; fake evidence cannot satisfy this row", True,
        "prerequisites (ADR §0.5; never MET, which is the outcome this row's evidence feeds): all seventeen step-8 designations "
        "independently verified (meu_live_status PENDING_VALIDATION); a production-authoritative custody lease within the "
        "non-production commissioning scope (the lease's authority under the real custody contract, not a production deployment); "
        "the owner's separate explicit authorization for the synthetic validation call (live_synthetic_validation_authorization); "
        "evidence: an EgressResult written by the live verifier with provenance.genuine_call true, custody_lease_id and "
        "custody_authority_id naming that lease, trust UNTRUSTED_EVIDENCE and the response digest, correlated with the row-18 "
        "secret-access evidence by non-secret identifiers and bounded timestamps"),
    Row(13, "TAP verification of the answer; INDETERMINATE", "TYPED_REFUSAL_NOT_DEGRADED_RESULT", False,
        "TAP verification is composed in the deployment unit, which does not exist yet (LP-1); not this distribution's to fake",
        False,
        "the deployment unit's composition record showing the TAP verifier wired behind the answer, and a verifier run on a live "
        "answer whose INDETERMINATE result is recorded as a typed refusal, not a degraded result"),
    Row(14, "purge replaces content with a tombstone on schedule", "TOMBSTONE_WITH_DIGESTS_ONLY", False,
        "needs the exchange on PostgreSQL; proven by the unit's own suite (tests/test_purge.py) and executed by the live verifier",
        False,
        "the exchange row of the live request after its retention deadline, read through the worker role: content columns null, "
        "the tombstone carrying only identifiers, digests, outcome and timestamps, captured by the live verifier"),
    Row(15, "lease expiry after dispatch", "OUTCOME_UNKNOWN_NEVER_A_SECOND_BILLED_CALL", False,
        "needs the exchange on PostgreSQL; proven by the unit's own suite (tests/test_reconcile.py) and executed by the live verifier",
        False,
        "a live request whose unit lease expired after dispatched_at was set: the reconciliation pass recording OUTCOME_UNKNOWN with "
        "a DispatchAttempt, the commissioning_reservation row unchanged, and vendor-side usage showing no second billed call"),
    Row(16, "retry after a transient failure before dispatch", "AT_MOST_ONE_RETRY_THEN_FAILED", True),
    Row(17, "vendor error, timeout and malformed answer", "TYPED_OUTCOMES_FAILED_OR_OUTCOME_UNKNOWN", True),
    Row(18, "Secret Manager Data Access audit log shows the read of the pinned version", "AUDIT_LOG_EVIDENCE_PRESENT", False,
        "audit-log evidence exists only in the designated GCP project after step 8; fake evidence cannot satisfy this row", True,
        "the Secret Manager Data Access audit-log query for the designated secret over the defined commissioning window: the IAM "
        "policy on the exact secret, one AccessSecretVersion event by the designated MEU workload identity naming the numeric "
        "version, no event by an identity outside the approved set within the window, correlated to the MEU request by "
        "non-secret identifiers and bounded timestamps (LP-7 ruling 5); the retention location recorded"),
)

OFFLINE_ROWS: Tuple[int, ...] = tuple(r.row for r in ROWS if r.offline)
