"""PostgreSQL-backed persistence (skeleton + DDL reference).

Deliberately not wired for RA-1..RA-4: the vertical slice and the conformance
suite run entirely on the in-memory reference store, keeping the package a
stdlib-only leaf. The canonical table set (spec §26, user brief §22) is
recorded here so the production adapter has an authoritative schema to build
against, and the class raises clearly rather than silently degrading.

Tables (all tenant-scoped, strong consistency for authority-changing writes):

    risk_cases(tenant_id, case_id PK, state, subject_id, model_id, purpose,
               domain, workflow_ir_id, workflow_ir_version, workflow_ir_digest,
               inherent_risk, residual_risk, created_at, correlation_id)
    risk_decisions(tenant_id, decision_id PK, case_id, outcome, principal_id,
               risk_class, domain, scope_json, conditions_json,
               workflow_ir_digest, evidence_snapshot_digest, model_digest,
               issued_at, expires_at)
    control_results(tenant_id, case_id, control_id, status, evidence_ids,
               evaluated_at, valid_until, PRIMARY KEY(tenant_id, case_id, control_id))
    evidence_metadata(tenant_id, evidence_id PK, type, subject_id, issuer,
               created_at, valid_until, digest, admission_status, provenance_json)
    authority_grants(tenant_id, principal_id PK, authority_type, domains,
               allowed_risk_classes, max_autonomy, grantable_scope_json,
               delegated_by, expires_at)
    envelopes(tenant_id, envelope_id PK, decision_id, subject, model_id,
               session_id, nonce, issued_at, not_before, expires_at,
               scope_json, conditions_json, bindings_json, key_id, signature)
    revocations(tenant_id, kind, target_id, epoch, created_at)
    governance_events(event_id PK, tenant_id, event_type, aggregate_id, actor,
               timestamp, correlation_id, payload_digest, prev_digest)  -- append-only
"""

from __future__ import annotations

__all__ = ["PostgresNotConfiguredError", "PostgresRepositoryFactory"]


class PostgresNotConfiguredError(NotImplementedError):
    """Raised when the Postgres store is used before RA production wiring."""


class PostgresRepositoryFactory:
    """Placeholder factory for the production Postgres-backed repositories."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _unavailable(self) -> "PostgresNotConfiguredError":
        return PostgresNotConfiguredError(
            "Postgres persistence is not wired in RA-1..RA-4; use the in-memory "
            "reference store. See this module's docstring for the target DDL."
        )

    def risk_cases(self):  # noqa: ANN201 - factory stub
        raise self._unavailable()

    def decisions(self):  # noqa: ANN201
        raise self._unavailable()

    def envelopes(self):  # noqa: ANN201
        raise self._unavailable()

    def authority_registry(self):  # noqa: ANN201
        raise self._unavailable()

    def events(self):  # noqa: ANN201
        raise self._unavailable()
