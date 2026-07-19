"""
Issuer + enforcement adapter + session state + metrics + harness.

The enforcement adapter is the trust boundary: it honors the signed authorization
artifact, re-checks all material facts at execution time (TOCTOU), and projects
only the permitted subset from the synthetic EMR. It never trusts the caller to
respect constraints, and it never lets field CONTENT influence the decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from agentic.healthcare.request import HealthcareAccessRequest
from agentic.healthcare.taxonomy import (
    DataCategory,
    PROHIBITED_CATEGORIES,
    RESTRICTED_CATEGORIES,
)
from agentic.healthcare.service import (
    HealthcareAccessDecision,
    HealthcareGovernanceService,
    HealthcareOutcome,
)
from agentic.healthcare.enforcement.artifact import (
    AuthorizationArtifact,
    DEFAULT_SIGNING_KEY,
    ExecutionReceipt,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    MismatchCode,
)
from agentic.healthcare.enforcement.emr import (
    SYNTHETIC_CREDENTIAL_SENTINEL,
    SyntheticEMR,
)

_RESTRICTED_VALUES = frozenset(c.value for c in RESTRICTED_CATEGORIES)
_PROHIBITED_VALUES = frozenset(c.value for c in PROHIBITED_CATEGORIES)
_MASK_VALUES = frozenset({DataCategory.IDENTITY_DOCUMENT.value})
_MASK_TOKEN = "***MASKED***"

GOVERNANCE_VERSION = "actiongate-healthcare/1.0"


class FixedClock:
    """Deterministic injectable clock (epoch seconds)."""

    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = float(now)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += float(seconds)


@dataclass
class EnforcementConfig:
    session_record_cap: int = 25
    default_ttl_seconds: float = 300.0


@dataclass
class EnforcementState:
    """Mutable enforcement state: consumed nonces + per-session record tallies."""

    used_nonces: set = field(default_factory=set)
    session_records: Dict[str, int] = field(default_factory=dict)

    def nonce_used(self, nonce: str) -> bool:
        return nonce in self.used_nonces

    def consume_nonce(self, nonce: str) -> None:
        self.used_nonces.add(nonce)

    def session_total(self, session_id: str) -> int:
        return self.session_records.get(session_id, 0)

    def add_session_records(self, session_id: str, count: int) -> None:
        self.session_records[session_id] = self.session_total(session_id) + count


@dataclass
class HarnessMetrics:
    authorizations_issued: int = 0
    authorizations_denied: int = 0  # decision not executable → no artifact
    executions_attempted: int = 0
    executions_executed: int = 0
    executions_rejected: int = 0
    constrained_executions: int = 0
    scope_mismatch_blocks: int = 0
    replay_blocks: int = 0
    tenant_isolation_blocks: int = 0
    stale_authorization_rejections: int = 0
    restricted_field_leakage: int = 0
    unauthorized_field_leakage: int = 0
    receipts_total: int = 0
    receipts_with_correlation: int = 0

    def to_dict(self) -> Dict[str, Any]:
        def rate(n: int, d: int) -> float:
            return round(n / d, 4) if d else 0.0
        return {
            "authorizations_issued": self.authorizations_issued,
            "authorizations_denied": self.authorizations_denied,
            "authorization_success_rate": rate(
                self.authorizations_issued,
                self.authorizations_issued + self.authorizations_denied),
            "executions_attempted": self.executions_attempted,
            "executions_executed": self.executions_executed,
            "denied_execution_attempts": self.executions_rejected,
            "constrained_execution_rate": rate(
                self.constrained_executions, self.executions_executed),
            "scope_mismatch_blocks": self.scope_mismatch_blocks,
            "replay_attempts_blocked": self.replay_blocks,
            "tenant_isolation_violations_blocked": self.tenant_isolation_blocks,
            "restricted_field_leakage_count": self.restricted_field_leakage,
            "unauthorized_field_leakage_count": self.unauthorized_field_leakage,
            "stale_authorization_rejections": self.stale_authorization_rejections,
            "audit_correlation_completeness": rate(
                self.receipts_with_correlation, self.receipts_total),
        }


# =============================================================================
# Issuer
# =============================================================================


class AuthorizationIssuer:
    """Turns an executable decision into a signed artifact. Allow-only."""

    _EXECUTABLE = (HealthcareOutcome.ALLOW, HealthcareOutcome.ALLOW_WITH_CONSTRAINTS)

    def __init__(
        self,
        *,
        signing_key: bytes = DEFAULT_SIGNING_KEY,
        clock: Callable[[], float] = None,
        config: Optional[EnforcementConfig] = None,
        metrics: Optional[HarnessMetrics] = None,
    ) -> None:
        self._key = signing_key
        self._clock = clock or FixedClock()
        self._config = config or EnforcementConfig()
        self._metrics = metrics
        self._counter = 0

    def issue(
        self,
        decision: HealthcareAccessDecision,
        request: HealthcareAccessRequest,
        *,
        ttl_seconds: Optional[float] = None,
        one_time: bool = False,
        require_policy_freshness: bool = False,
        approval_required: bool = False,
        approval_completed: bool = True,
    ) -> Optional[AuthorizationArtifact]:
        """Issue a signed artifact, or None for a non-executable decision.

        DEFER / REQUIRE_APPROVAL / DENY never produce an executable authorization.
        """
        if decision.outcome not in self._EXECUTABLE:
            if self._metrics:
                self._metrics.authorizations_denied += 1
            return None

        self._counter += 1
        now = self._clock()
        ttl = ttl_seconds if ttl_seconds is not None else self._config.default_ttl_seconds
        c = decision.constraints or {}
        dest_class = request.destination_class.value
        allow_external = dest_class in ("approved_external", "unapproved_external")

        artifact = AuthorizationArtifact(
            authorization_id=f"auth-{self._counter:06d}",
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            actor_role=request.actor_role.value,
            agent_id=request.agent_id,
            agent_version=request.agent_version,
            patient_ref=request.patient_ref,
            encounter_ref=request.encounter_ref,
            purpose=request.purpose.value,
            operation=request.operation.value,
            permitted_categories=tuple(decision.allowed_categories),
            excluded_categories=tuple(decision.excluded_categories),
            required_redactions=tuple(c.get("required_redactions", ()) or ()),
            max_record_count=int(c.get("max_record_count", request.record_count) or 1),
            approved_destination=(
                request.destination_ref if request.destination_approved else None),
            destination_class=dest_class,
            allow_external=allow_external,
            no_onward_disclosure=bool(c.get("no_onward_disclosure", allow_external)),
            approval_required=approval_required,
            approval_completed=approval_completed,
            policy_version=decision.policy_version,
            policy_hash=decision.policy_hash,
            governance_version=GOVERNANCE_VERSION,
            model_version=request.model_version,
            issued_at=now,
            expires_at=now + ttl,
            nonce=f"nonce-{self._counter:06d}",
            one_time=one_time,
            require_policy_freshness=require_policy_freshness,
            final_authority_used=decision.final_authority_used,
            consent_state=request.consent_state.value,
        ).signed(self._key)

        if self._metrics:
            self._metrics.authorizations_issued += 1
        return artifact


# =============================================================================
# Enforcement adapter
# =============================================================================


class EnforcementAdapter:
    """Deterministic enforcement between authorization and simulated retrieval."""

    def __init__(
        self,
        emr: SyntheticEMR,
        *,
        signing_key: bytes = DEFAULT_SIGNING_KEY,
        clock: Callable[[], float] = None,
        config: Optional[EnforcementConfig] = None,
        state: Optional[EnforcementState] = None,
        metrics: Optional[HarnessMetrics] = None,
    ) -> None:
        self._emr = emr
        self._key = signing_key
        self._clock = clock or FixedClock()
        self._config = config or EnforcementConfig()
        self._state = state or EnforcementState()
        self._metrics = metrics

    @property
    def state(self) -> EnforcementState:
        return self._state

    def execute(
        self, artifact: Optional[AuthorizationArtifact], exec_req: ExecutionRequest,
    ) -> ExecutionResult:
        if self._metrics:
            self._metrics.executions_attempted += 1

        if artifact is None:
            return self._reject(None, exec_req, MismatchCode.NO_AUTHORIZATION)

        code = self._check(artifact, exec_req)
        if code is not MismatchCode.OK:
            return self._reject(artifact, exec_req, code)

        return self._project_and_execute(artifact, exec_req)

    # ---- checks (TOCTOU material-fact re-verification) --------------------

    def _check(self, a: AuthorizationArtifact, r: ExecutionRequest) -> MismatchCode:
        if not a.verify(self._key):
            return MismatchCode.SIGNATURE_INVALID
        if r.authorization_id != a.authorization_id:
            return MismatchCode.NO_AUTHORIZATION
        if self._clock() > a.expires_at:
            return MismatchCode.EXPIRED
        if a.one_time and self._state.nonce_used(a.nonce):
            return MismatchCode.REPLAY
        if a.approval_required and not r.approval_completed:
            return MismatchCode.APPROVAL_INCOMPLETE
        if r.tenant_id != a.tenant_id:
            return MismatchCode.TENANT_MISMATCH
        if r.actor_id != a.actor_id:
            return MismatchCode.ACTOR_MISMATCH
        if a.agent_id is not None and r.agent_id != a.agent_id:
            return MismatchCode.AGENT_MISMATCH
        if r.patient_ref != a.patient_ref:
            return MismatchCode.PATIENT_MISMATCH
        if a.encounter_ref is not None and r.encounter_ref != a.encounter_ref:
            return MismatchCode.ENCOUNTER_MISMATCH
        if r.operation != a.operation:
            return MismatchCode.OPERATION_MISMATCH
        if r.purpose != a.purpose:
            return MismatchCode.PURPOSE_MISMATCH
        if r.destination_class != a.destination_class:
            return MismatchCode.DESTINATION_MISMATCH
        if a.approved_destination is not None and r.destination_ref != a.approved_destination:
            return MismatchCode.DESTINATION_MISMATCH
        if r.consent_state != a.consent_state:
            return MismatchCode.CONSENT_CHANGED
        if a.require_policy_freshness and r.policy_version != a.policy_version:
            return MismatchCode.POLICY_STALE
        requested = set(r.requested_categories) or set(a.permitted_categories)
        if requested - set(a.permitted_categories):
            return MismatchCode.SCOPE_WIDENING
        if r.record_count > a.max_record_count:
            return MismatchCode.RECORD_LIMIT
        prospective = self._state.session_total(r.session_id) + max(r.record_count, 1)
        if prospective > self._config.session_record_cap:
            return MismatchCode.CUMULATIVE_LIMIT
        return MismatchCode.OK

    # ---- projection / redaction / execution -------------------------------

    def _project_and_execute(
        self, a: AuthorizationArtifact, r: ExecutionRequest,
    ) -> ExecutionResult:
        requested = tuple(r.requested_categories) or a.permitted_categories
        permitted = set(a.permitted_categories)

        released: list = []
        dropped_redactions: list = []
        for cat in requested:
            if cat not in permitted:
                continue  # (already rejected by SCOPE_WIDENING; defense in depth)
            # Never release restricted or prohibited even if somehow permitted.
            if cat in _RESTRICTED_VALUES or cat in _PROHIBITED_VALUES:
                dropped_redactions.append(cat)
                continue
            released.append(cat)

        raw = self._emr.fetch(a.tenant_id, a.patient_ref, a.encounter_ref, released)
        payload: Dict[str, str] = {}
        masked: list = []
        for cat, value in raw.items():
            if value == SYNTHETIC_CREDENTIAL_SENTINEL:
                # Belt-and-suspenders: the credential sentinel is never released.
                dropped_redactions.append(cat)
                continue
            if cat in _MASK_VALUES:
                payload[cat] = _MASK_TOKEN
                masked.append(cat)
            else:
                payload[cat] = value

        released_final = tuple(sorted(payload.keys()))
        redactions_applied = tuple(sorted(
            set(a.required_redactions) | set(dropped_redactions) | set(masked)))

        # Leakage invariants (must always be zero by construction).
        if self._metrics:
            leaked_restricted = sum(1 for c in released_final if c in _RESTRICTED_VALUES)
            leaked_unauth = sum(
                1 for c in released_final if c not in permitted)
            self._metrics.restricted_field_leakage += leaked_restricted
            self._metrics.unauthorized_field_leakage += leaked_unauth

        # Commit state: consume nonce + tally session records.
        if a.one_time:
            self._state.consume_nonce(a.nonce)
        self._state.add_session_records(r.session_id, max(r.record_count, 1))

        receipt = ExecutionReceipt(
            authorization_id=a.authorization_id,
            execution_status=ExecutionStatus.EXECUTED.value,
            tenant_ref=a.tenant_id,
            actor_ref=a.actor_id,
            agent_ref=a.agent_id,
            patient_ref=a.patient_ref,
            encounter_ref=a.encounter_ref,
            operation=a.operation,
            categories_released=released_final,
            categories_excluded=a.excluded_categories,
            redactions_applied=redactions_applied,
            record_count=max(r.record_count, 1),
            destination_class=a.destination_class,
            policy_version=a.policy_version,
            timestamp=self._clock(),
            denial_code=None,
            audit_correlation_id=f"corr:{a.authorization_id}:{a.nonce}",
        )
        if self._metrics:
            self._metrics.executions_executed += 1
            self._metrics.receipts_total += 1
            self._metrics.receipts_with_correlation += 1
            if a.excluded_categories or redactions_applied:
                self._metrics.constrained_executions += 1
        return ExecutionResult(receipt=receipt, payload=payload)

    # ---- rejection --------------------------------------------------------

    def _reject(
        self,
        a: Optional[AuthorizationArtifact],
        r: ExecutionRequest,
        code: MismatchCode,
    ) -> ExecutionResult:
        auth_id = a.authorization_id if a is not None else "(none)"
        receipt = ExecutionReceipt(
            authorization_id=auth_id,
            execution_status=ExecutionStatus.REJECTED.value,
            tenant_ref=r.tenant_id,
            actor_ref=r.actor_id,
            agent_ref=r.agent_id,
            patient_ref=r.patient_ref,
            encounter_ref=r.encounter_ref,
            operation=r.operation,
            categories_released=(),
            categories_excluded=(a.excluded_categories if a else ()),
            redactions_applied=(),
            record_count=0,
            destination_class=r.destination_class,
            policy_version=r.policy_version,
            timestamp=self._clock(),
            denial_code=code.value,
            audit_correlation_id=f"corr:{auth_id}:reject",
        )
        if self._metrics:
            self._metrics.executions_rejected += 1
            self._metrics.receipts_total += 1
            self._metrics.receipts_with_correlation += 1
            if code in (MismatchCode.SCOPE_WIDENING, MismatchCode.OPERATION_MISMATCH,
                        MismatchCode.DESTINATION_MISMATCH, MismatchCode.PATIENT_MISMATCH,
                        MismatchCode.ENCOUNTER_MISMATCH, MismatchCode.RECORD_LIMIT,
                        MismatchCode.CUMULATIVE_LIMIT, MismatchCode.PURPOSE_MISMATCH):
                self._metrics.scope_mismatch_blocks += 1
            if code == MismatchCode.REPLAY:
                self._metrics.replay_blocks += 1
            if code == MismatchCode.TENANT_MISMATCH:
                self._metrics.tenant_isolation_blocks += 1
            if code in (MismatchCode.POLICY_STALE, MismatchCode.EXPIRED):
                self._metrics.stale_authorization_rejections += 1
        return ExecutionResult(receipt=receipt, payload={})


# =============================================================================
# Harness (convenience wiring)
# =============================================================================


class EnforcementHarness:
    """Ties decision service + issuer + adapter + synthetic EMR + metrics."""

    def __init__(
        self,
        *,
        emr: Optional[SyntheticEMR] = None,
        service: Optional[HealthcareGovernanceService] = None,
        signing_key: bytes = DEFAULT_SIGNING_KEY,
        clock: Callable[[], float] = None,
        config: Optional[EnforcementConfig] = None,
    ) -> None:
        from agentic.healthcare.enforcement.emr import build_synthetic_emr
        self.metrics = HarnessMetrics()
        self.clock = clock or FixedClock()
        self.config = config or EnforcementConfig()
        self.state = EnforcementState()
        self.emr = emr if emr is not None else build_synthetic_emr()
        self.service = service or HealthcareGovernanceService()
        self.issuer = AuthorizationIssuer(
            signing_key=signing_key, clock=self.clock, config=self.config,
            metrics=self.metrics)
        self.adapter = EnforcementAdapter(
            self.emr, signing_key=signing_key, clock=self.clock, config=self.config,
            state=self.state, metrics=self.metrics)

    def authorize(self, request: HealthcareAccessRequest) -> HealthcareAccessDecision:
        return self.service.authorize(request)

    def issue(self, decision, request, **kw) -> Optional[AuthorizationArtifact]:
        return self.issuer.issue(decision, request, **kw)

    def execute(self, artifact, exec_req) -> ExecutionResult:
        return self.adapter.execute(artifact, exec_req)

    def run(
        self, request: HealthcareAccessRequest, *,
        exec_overrides: Optional[Dict[str, Any]] = None,
        session_id: str = "default-session",
        **issue_kw,
    ):
        """authorize → issue → (faithful or overridden) execute. Returns
        (decision, artifact, result). ``artifact``/``result`` are None when the
        decision is not executable."""
        decision = self.authorize(request)
        artifact = self.issue(decision, request, **issue_kw)
        if artifact is None:
            return decision, None, None
        exec_req = ExecutionRequest.faithful_from(
            artifact, session_id=session_id, **(exec_overrides or {}))
        result = self.execute(artifact, exec_req)
        return decision, artifact, result
