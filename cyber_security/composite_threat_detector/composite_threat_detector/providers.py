"""Trusted benign-evidence providers (§3).

Self-declared benign intent — from an agent, user, event payload, or unverified
metadata — is **never** accepted as neutralizing. A benign authorization must be
independently verified by a trusted provider and must match the assembly's scope
and time window.

This module defines a **versioned provider interface** plus a replayable
``FixtureProvider`` (records supplied as data). There are **no network calls** in
the deterministic core; a real deployment supplies an adapter that implements the
same interface against its source system (see ``replay.py`` /
``HISTORICAL_REPLAY_CONTRACT``). A provider response is fully described by data,
so evaluation is deterministic and replayable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical import digest

# reference provider types (§3)
CHANGE_TICKET = "change_management_ticket"
MAINTENANCE_WINDOW = "approved_maintenance_window"
PENTEST_AUTH = "penetration_test_authorization"
BACKUP_MIGRATION = "backup_or_migration_approval"
INCIDENT_CASE = "incident_response_case"
HUMAN_APPROVAL = "human_approval_record"
WORKFLOW_CONFIG = "workflow_configuration"
IAM_RECORD = "iam_record"

PROVIDER_TYPES = frozenset({
    CHANGE_TICKET, MAINTENANCE_WINDOW, PENTEST_AUTH, BACKUP_MIGRATION,
    INCIDENT_CASE, HUMAN_APPROVAL, WORKFLOW_CONFIG, IAM_RECORD,
})

# verification statuses
VERIFIED = "VERIFIED"
NOT_FOUND = "NOT_FOUND"
UNVERIFIED = "UNVERIFIED"

# the scope dimensions an authorization can bind
SCOPE_DIMS = ("tenant", "actor", "workflow", "target_family", "operation",
              "destination", "environment", "tool")


@dataclass(frozen=True)
class AuthorizationQuery:
    tenant: str
    actor: str = ""
    workflow: str = ""
    target_family: str = ""
    operations: tuple[str, ...] = ()
    destinations: tuple[str, ...] = ()
    environment: str = ""
    tools: tuple[str, ...] = ()
    now: float | None = None
    policy_version: str = ""
    claim_tag: str = ""
    claim_record_id: str = ""


@dataclass(frozen=True)
class BenignAuthorization:
    """A verified (or explicitly unverified) authorization record."""

    source_system: str
    provider_type: str
    record_id: str
    record_version: str
    tag: str
    verification_status: str            # VERIFIED | NOT_FOUND | UNVERIFIED
    scope_match: dict                   # per-dim bool
    time_window_match: bool
    approver_identity: str
    approver_authority: str
    policy_version: str
    evidence_digest: str
    detail: dict = field(default_factory=dict)

    def fully_scope_matched(self) -> bool:
        return bool(self.scope_match) and all(self.scope_match.values())

    def to_dict(self) -> dict:
        return {
            "source_system": self.source_system,
            "provider_type": self.provider_type,
            "record_id": self.record_id,
            "record_version": self.record_version,
            "tag": self.tag,
            "verification_status": self.verification_status,
            "scope_match": self.scope_match,
            "time_window_match": self.time_window_match,
            "approver_identity": self.approver_identity,
            "approver_authority": self.approver_authority,
            "policy_version": self.policy_version,
            "evidence_digest": self.evidence_digest,
        }


class BenignEvidenceProvider:
    """Versioned provider interface. Implement ``verify`` deterministically."""

    provider_id = "abstract"
    version = "0.0.0"

    def verify(self, query: AuthorizationQuery) -> BenignAuthorization | None:
        raise NotImplementedError


def _dim_match(record_value, query_value, query_multi=None) -> bool:
    if record_value in ("*", None, ""):
        return True
    if query_multi is not None:
        return all(v == record_value or record_value == "*" for v in query_multi) \
            if query_multi else True
    return record_value == query_value


class FixtureProvider(BenignEvidenceProvider):
    """A trusted provider backed by replayable fixture records (no network).

    Each record is a dict with keys: ``record_id``, ``record_version``,
    ``provider_type``, ``tag``, scope values (``tenant``, ``actor``, ``workflow``,
    ``target_family``, ``operations``, ``destinations``, ``environment``,
    ``tools``), ``start``/``expiry`` (numeric, same unit as query.now),
    ``approver_identity``, ``approver_authority``, ``policy_version``.
    """

    def __init__(self, provider_id: str, version: str, records: list[dict],
                 source_system: str = "fixture"):
        self.provider_id = provider_id
        self.version = version
        self.source_system = source_system
        self._records = list(records)

    def verify(self, query: AuthorizationQuery) -> BenignAuthorization | None:
        best = None
        for rec in self._records:
            if rec.get("tenant", "*") not in ("*", query.tenant):
                continue  # tenant isolation is hard: never match across tenants
            if query.claim_record_id and rec.get("record_id") != query.claim_record_id:
                continue
            scope_match = {
                "tenant": rec.get("tenant", "*") in ("*", query.tenant),
                "actor": _dim_match(rec.get("actor", "*"), query.actor),
                "workflow": _dim_match(rec.get("workflow", "*"), query.workflow),
                "target_family": _dim_match(rec.get("target_family", "*"),
                                            query.target_family),
                "operation": _ops_match(rec.get("operations", "*"), query.operations),
                "destination": _multi_match(rec.get("destinations", "*"),
                                            query.destinations),
                "environment": _dim_match(rec.get("environment", "*"),
                                          query.environment),
                "tool": _multi_match(rec.get("tools", "*"), query.tools),
            }
            start = rec.get("start")
            expiry = rec.get("expiry")
            tw = True
            if query.now is not None:
                if start is not None and query.now < float(start):
                    tw = False
                if expiry is not None and query.now > float(expiry):
                    tw = False
            payload = {"record_id": rec.get("record_id"),
                       "record_version": rec.get("record_version", "1"),
                       "provider": self.provider_id, "version": self.version,
                       "scope": {k: rec.get(k) for k in
                                 ("tenant", "actor", "workflow", "target_family",
                                  "operations", "destinations", "environment", "tools")}}
            auth = BenignAuthorization(
                source_system=self.source_system,
                provider_type=rec.get("provider_type", CHANGE_TICKET),
                record_id=str(rec.get("record_id", "")),
                record_version=str(rec.get("record_version", "1")),
                tag=str(rec.get("tag", "")).strip().lower(),
                verification_status=VERIFIED,
                scope_match=scope_match,
                time_window_match=tw,
                approver_identity=str(rec.get("approver_identity", "")),
                approver_authority=str(rec.get("approver_authority", "")),
                policy_version=str(rec.get("policy_version", "")),
                evidence_digest=digest(payload, domain="CTD-BENIGN"),
                detail=payload,
            )
            # prefer a fully scope-matched, in-window, authored authorization
            score = (sum(scope_match.values()), int(tw),
                     int(bool(auth.approver_authority)))
            if best is None or score > best[0]:
                best = (score, auth)
        return best[1] if best else None


def _ops_match(record_ops, query_ops) -> bool:
    if record_ops in ("*", None, ""):
        return True
    allowed = set(record_ops)
    return all(op in allowed for op in query_ops) if query_ops else True


def _multi_match(record_vals, query_vals) -> bool:
    if record_vals in ("*", None, ""):
        return True
    allowed = set(record_vals)
    return all(v in allowed for v in query_vals) if query_vals else True


@dataclass
class ProviderRegistry:
    """Queries trusted providers in a fixed order; returns the best authorization."""

    providers: tuple[BenignEvidenceProvider, ...] = ()

    def verify(self, query: AuthorizationQuery) -> BenignAuthorization | None:
        best = None
        for prov in self.providers:
            auth = prov.verify(query)
            if auth is None:
                continue
            score = (sum(auth.scope_match.values()), int(auth.time_window_match),
                     int(bool(auth.approver_authority)))
            if best is None or score > best[0]:
                best = (score, auth)
        return best[1] if best else None

    def describe(self) -> list[dict]:
        return [{"provider_id": p.provider_id, "version": p.version}
                for p in self.providers]
