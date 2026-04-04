"""
Policy Service — Clean service-facing wrapper for the policy layer.

STATUS: ACTIVE (Policy Phase P1)

    This module is the canonical service-facing entry point for all
    policy computations. It wraps the existing policy engine, session
    policy, trading guardrails, and interaction mode resolution into
    a single, structured API suitable for backend/governance consumers.

WHAT THIS MODULE DOES:
    - Provides typed, structured results for all policy operations
    - Delegates to existing deterministic engines (zero new logic)
    - Collects lightweight audit entries for all policy decisions
    - Exposes interaction mode read/override through a governance-facing API

WHAT THIS MODULE DOES NOT DO:
    - Add new policy rules or modify existing ones
    - Call LLMs or perform non-deterministic operations
    - Persist audit data (consumers pull from the audit log)
    - Replace direct imports (backward compatibility preserved)

Design Principles:
    - Zero-LLM: All operations are deterministic and rule-based
    - Delegation-only: Wraps existing engines, adds no new logic
    - Fail-open for reads, fail-closed for writes
    - Audit-by-default: Every call produces an audit entry

Usage:
    from agentic.policy.policy_service import PolicyService

    svc = PolicyService()

    # Compute policy flags
    result = svc.compute_policy(unified_output, domain="trading")
    flags = result["flags"]

    # Resolve interaction mode
    result = svc.resolve_interaction_mode(domain="therapy", user_override="smart_insight")
    mode = result["mode"]

    # Compute session policy
    result = svc.compute_session_policy(session_summary)
    session_flags = result["flags"]

    # Compute trading guardrails
    result = svc.compute_trading_guardrails(summary, policy, motivation, intent_arc, identity_sig)
    guardrails = result["flags"]

    # Read audit log
    log = svc.get_policy_audit_log(limit=50)
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .domain_profiles import get_domain_profile
from .interaction_modes import (
    InteractionMode,
    resolve_interaction_mode,
    get_mode_name,
    is_mode_valid,
)
from .policy_engine import compute_policy_flags, explain_policy_flags
from .session_policy import SessionPolicyFlags, compute_session_policy_flags
from .trading_guardrail_engine import TradingGuardrailFlags, compute_trading_guardrails


# =============================================================================
# Constants
# =============================================================================

P1_VERSION = "1.0.0"

# Maximum in-memory audit entries before oldest are evicted
_MAX_AUDIT_ENTRIES = 1000


# =============================================================================
# PolicyService
# =============================================================================


class PolicyService:
    """
    Service-facing wrapper for the agentic policy layer.

    Provides structured, auditable access to:
    - Policy flag computation (compute_policy_flags)
    - Interaction mode resolution (resolve_interaction_mode)
    - Session policy computation (compute_session_policy_flags)
    - Trading guardrail computation (compute_trading_guardrails)
    - Policy lifecycle management (P3: stage/validate/activate/rollback)
    - Policy control-plane queries (P4: snapshots, health, history)

    Every call returns a structured dict with:
    - The computed result (flags, mode, etc.)
    - Metadata (version, timestamp, domain)
    - Audit trail entry (automatically collected)

    Known Limitations:
        - The audit log is in-memory only (max 1000 entries, no persistence).
        - compute_policy() wraps compute_policy_flags() with audit/metadata;
          some pipeline consumers may call compute_policy_flags() directly.
          Both paths use the same ProfileRegistry and produce identical flags.
        - Lifecycle state (P3) and control-plane queries (P4) are backed by
          in-memory stores. See PolicyLifecycleManager for details.

    Thread Safety:
        The audit log is append-only. For concurrent access, callers
        should use external synchronization if strict ordering is needed.
    """

    def __init__(self) -> None:
        self._policy_audit_log: List[Dict[str, Any]] = []

    # -----------------------------------------------------------------
    # P1-A: Policy flag computation
    # -----------------------------------------------------------------

    def compute_policy(
        self,
        unified: Dict[str, Any],
        domain: str,
        user_mode_override: Optional[str] = None,
        admin_mode_override: Optional[str] = None,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compute policy flags for a unified output and domain.

        Delegates to compute_policy_flags() and wraps the result
        with metadata and audit.

        Args:
            unified: Unified output dictionary from USU-API v1.0
            domain: Domain identifier (e.g., "trading", "therapy")
            user_mode_override: Optional user interaction mode override
            admin_mode_override: Optional admin interaction mode override
            user_id: Optional user identifier for preference lookup
            org_id: Optional organization identifier for preference lookup

        Returns:
            Dict with:
                flags: policy flags dictionary
                domain: domain used
                version: P1 version
                timestamp: ISO-8601 timestamp
        """
        ts = datetime.now(timezone.utc)

        flags = compute_policy_flags(
            unified=unified,
            domain=domain,
            user_mode_override=user_mode_override,
            admin_mode_override=admin_mode_override,
            user_id=user_id,
            org_id=org_id,
        )

        # P2: include profile identity for traceability
        effective_profile = get_domain_profile(domain)

        result = {
            "flags": flags,
            "domain": domain,
            "profile_id": effective_profile.profile_id,
            "profile_version": effective_profile.profile_version,
            "version": P1_VERSION,
            "timestamp": ts.isoformat(),
        }

        self._append_audit_entry(
            event_type="compute_policy",
            domain=domain,
            timestamp=ts,
            summary={
                "interaction_mode": flags.get("interaction_mode"),
                "needs_grounding": flags.get("needs_grounding"),
                "stability_status": flags.get("stability_status"),
                "coherence_warning": flags.get("coherence_warning"),
            },
        )

        return result

    # -----------------------------------------------------------------
    # P1-B: Interaction mode resolution
    # -----------------------------------------------------------------

    def resolve_interaction_mode(
        self,
        domain: str,
        user_override: Optional[str] = None,
        admin_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolve the active interaction mode for a domain.

        Delegates to resolve_interaction_mode() with the domain profile.

        Args:
            domain: Domain identifier
            user_override: Optional user-specified mode override
            admin_override: Optional admin-specified mode override

        Returns:
            Dict with:
                mode: InteractionMode enum value
                mode_value: string value of the mode
                mode_name: human-readable mode name
                domain: domain used
                version: P1 version
                timestamp: ISO-8601 timestamp
        """
        ts = datetime.now(timezone.utc)

        profile = get_domain_profile(domain)
        mode = resolve_interaction_mode(
            domain_profile=profile,
            user_override=user_override,
            admin_override=admin_override,
        )

        result = {
            "mode": mode,
            "mode_value": mode.value,
            "mode_name": get_mode_name(mode),
            "domain": domain,
            "version": P1_VERSION,
            "timestamp": ts.isoformat(),
        }

        self._append_audit_entry(
            event_type="resolve_interaction_mode",
            domain=domain,
            timestamp=ts,
            summary={
                "resolved_mode": mode.value,
                "user_override": user_override,
                "admin_override": admin_override,
            },
        )

        return result

    # -----------------------------------------------------------------
    # P1-C: Session policy
    # -----------------------------------------------------------------

    def compute_session_policy(
        self,
        session_summary: Any,
    ) -> Dict[str, Any]:
        """
        Compute session-level policy flags from a SessionSummary.

        Delegates to compute_session_policy_flags().

        Args:
            session_summary: SessionSummary with multi-turn metrics
                (None returns a result with flags=None)

        Returns:
            Dict with:
                flags: SessionPolicyFlags.to_dict() or None
                flags_obj: SessionPolicyFlags instance or None
                version: P1 version
                timestamp: ISO-8601 timestamp
        """
        ts = datetime.now(timezone.utc)

        flags_obj = compute_session_policy_flags(session_summary)

        result = {
            "flags": flags_obj.to_dict() if flags_obj is not None else None,
            "flags_obj": flags_obj,
            "version": P1_VERSION,
            "timestamp": ts.isoformat(),
        }

        summary = {}
        if flags_obj is not None:
            summary = {
                "session_is_stable": flags_obj.session_is_stable,
                "session_needs_grounding": flags_obj.session_needs_grounding,
                "session_recommended_style": flags_obj.session_recommended_style,
            }
        else:
            summary = {"session_summary_provided": False}

        self._append_audit_entry(
            event_type="compute_session_policy",
            domain=None,
            timestamp=ts,
            summary=summary,
        )

        return result

    # -----------------------------------------------------------------
    # P1-C: Trading guardrails
    # -----------------------------------------------------------------

    def compute_trading_guardrails(
        self,
        summary: Any,
        policy: Any,
        motivation: Any,
        intent_arc: Any,
        identity_signature: Any,
    ) -> Dict[str, Any]:
        """
        Compute trading guardrail flags.

        Delegates to compute_trading_guardrails().

        Args:
            summary: SessionSummary with coherence metrics and formula values
            policy: PolicyFlags (reserved)
            motivation: MotivationProfile (reserved)
            intent_arc: IntentArc (reserved)
            identity_signature: IdentitySignature (reserved)

        Returns:
            Dict with:
                flags: TradingGuardrailFlags.to_dict()
                flags_obj: TradingGuardrailFlags instance
                version: P1 version
                timestamp: ISO-8601 timestamp
        """
        ts = datetime.now(timezone.utc)

        flags_obj = compute_trading_guardrails(
            summary=summary,
            policy=policy,
            motivation=motivation,
            intent_arc=intent_arc,
            identity_signature=identity_signature,
        )

        result = {
            "flags": flags_obj.to_dict(),
            "flags_obj": flags_obj,
            "version": P1_VERSION,
            "timestamp": ts.isoformat(),
        }

        self._append_audit_entry(
            event_type="compute_trading_guardrails",
            domain=None,
            timestamp=ts,
            summary={
                "recommend_no_action": flags_obj.recommend_no_action,
                "high_tension_risk": flags_obj.high_tension_risk,
                "negative_momentum_risk": flags_obj.negative_momentum_risk,
                "volatility_risk": flags_obj.volatility_risk,
            },
        )

        return result

    # -----------------------------------------------------------------
    # P1-B: Resolve domain profile (convenience)
    # -----------------------------------------------------------------

    def get_domain_profile(self, domain: str) -> Dict[str, Any]:
        """
        Resolve a domain profile by name.

        Args:
            domain: Domain identifier

        Returns:
            Dict with:
                profile: DomainProfile instance
                domain: domain used
                version: P1 version
                timestamp: ISO-8601 timestamp
        """
        ts = datetime.now(timezone.utc)
        profile = get_domain_profile(domain)

        return {
            "profile": profile,
            "domain": domain,
            "version": P1_VERSION,
            "timestamp": ts.isoformat(),
        }

    # -----------------------------------------------------------------
    # P2: Simulation support
    # -----------------------------------------------------------------

    def simulate_policy(
        self,
        unified: Dict[str, Any],
        domain: str = "generic",
        profile: Optional[Any] = None,
        user_mode_override: Optional[str] = None,
        admin_mode_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Simulate policy flag computation under an alternate profile.

        Delegates to policy_simulation.simulate_policy().

        Args:
            unified: Unified output dict
            domain: Domain identifier
            profile: Optional DomainProfile override
            user_mode_override: Optional mode override
            admin_mode_override: Optional admin mode override

        Returns:
            Simulation result dict with flags, profile_id, etc.
        """
        from .policy_simulation import simulate_policy
        return simulate_policy(
            unified=unified,
            domain=domain,
            profile=profile,
            user_mode_override=user_mode_override,
            admin_mode_override=admin_mode_override,
        )

    def compare_policy(
        self,
        unified: Dict[str, Any],
        domain: str,
        candidate_profile: Any,
        user_mode_override: Optional[str] = None,
        admin_mode_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compare policy outputs between default and candidate profiles.

        Delegates to policy_simulation.compare_policy().

        Returns:
            Comparison result with baseline, candidate, changed_flags
        """
        from .policy_simulation import compare_policy
        return compare_policy(
            unified=unified,
            domain=domain,
            candidate_profile=candidate_profile,
            user_mode_override=user_mode_override,
            admin_mode_override=admin_mode_override,
        )

    def simulate_session_policy(
        self,
        session_summary: Any,
        profile: Optional[Any] = None,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Simulate session policy under alternate thresholds.

        Delegates to policy_simulation.simulate_session_policy().
        """
        from .policy_simulation import simulate_session_policy
        return simulate_session_policy(
            session_summary=session_summary,
            profile=profile,
            thresholds=thresholds,
        )

    def simulate_trading_guardrails(
        self,
        summary: Any,
        profile: Optional[Any] = None,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Simulate trading guardrails under alternate thresholds.

        Delegates to policy_simulation.simulate_trading_guardrails().
        """
        from .policy_simulation import simulate_trading_guardrails
        return simulate_trading_guardrails(
            summary=summary,
            profile=profile,
            thresholds=thresholds,
        )

    # -----------------------------------------------------------------
    # P3: Policy lifecycle management
    # -----------------------------------------------------------------

    def _get_registry(self) -> Any:
        """Get the ProfileRegistry used by this service."""
        from .profile_schema import get_profile_registry
        return get_profile_registry()

    def get_lifecycle_manager(self) -> Any:
        """
        Get the PolicyLifecycleManager attached to this service.

        Lazily created on first access. Uses the global ProfileRegistry.
        """
        if not hasattr(self, "_lifecycle_manager"):
            from .policy_lifecycle import PolicyLifecycleManager
            self._lifecycle_manager = PolicyLifecycleManager(self._get_registry())
        return self._lifecycle_manager

    def stage_candidate(
        self,
        domain: str,
        profile: Any,
        actor: str,
        rationale: str = "",
    ) -> Dict[str, Any]:
        """
        Stage a candidate profile for activation.

        Args:
            domain: Domain identifier
            profile: DomainProfile to stage
            actor: Who is staging
            rationale: Why

        Returns:
            DeploymentRecord dict
        """
        ts = datetime.now(timezone.utc)
        mgr = self.get_lifecycle_manager()
        record = mgr.stage_candidate(domain, profile, actor, rationale)
        self._append_audit_entry(
            event_type="stage_candidate",
            domain=domain,
            timestamp=ts,
            summary={
                "profile_id": record.profile_id,
                "profile_version": record.profile_version,
                "status": record.status.value,
                "actor": actor,
            },
        )
        return record.to_dict()

    def validate_candidate(
        self,
        domain: str,
        actor: str,
        rationale: str = "",
        simulation_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Validate a staged candidate, optionally with simulation results.

        Returns:
            DeploymentRecord dict
        """
        ts = datetime.now(timezone.utc)
        mgr = self.get_lifecycle_manager()
        record = mgr.validate_candidate(
            domain, actor, rationale, simulation_summary,
        )
        self._append_audit_entry(
            event_type="validate_candidate",
            domain=domain,
            timestamp=ts,
            summary={
                "profile_id": record.profile_id,
                "profile_version": record.profile_version,
                "status": record.status.value,
                "has_simulation": simulation_summary is not None,
            },
        )
        return record.to_dict()

    def activate_profile(
        self,
        domain: str,
        actor: str,
        rationale: str = "",
        approval_id: Optional[str] = None,
        simulation_summary: Optional[Dict[str, Any]] = None,
        require_validation: bool = False,
    ) -> Dict[str, Any]:
        """
        Activate a staged candidate, promoting it into the registry.

        Args:
            domain: Domain identifier
            actor: Who is activating
            rationale: Why
            approval_id: Optional approval ID from governance workflow
            simulation_summary: Optional simulation results to attach
            require_validation: If True, candidate must be validated first

        Returns:
            DeploymentRecord dict
        """
        ts = datetime.now(timezone.utc)
        mgr = self.get_lifecycle_manager()
        record = mgr.activate(
            domain, actor, rationale, approval_id,
            simulation_summary, require_validation,
        )
        self._append_audit_entry(
            event_type="activate_profile",
            domain=domain,
            timestamp=ts,
            summary={
                "profile_id": record.profile_id,
                "profile_version": record.profile_version,
                "previous_profile_id": record.previous_profile_id,
                "previous_version": record.previous_version,
                "approval_id": approval_id,
                "actor": actor,
            },
        )
        return record.to_dict()

    def rollback_profile(
        self,
        domain: str,
        actor: str,
        rationale: str = "",
    ) -> Dict[str, Any]:
        """
        Rollback to the previous active profile for a domain.

        Returns:
            DeploymentRecord dict (the restored profile)
        """
        ts = datetime.now(timezone.utc)
        mgr = self.get_lifecycle_manager()
        record = mgr.rollback(domain, actor, rationale)
        self._append_audit_entry(
            event_type="rollback_profile",
            domain=domain,
            timestamp=ts,
            summary={
                "restored_profile_id": record.profile_id,
                "restored_version": record.profile_version,
                "previous_profile_id": record.previous_profile_id,
                "previous_version": record.previous_version,
                "actor": actor,
            },
        )
        return record.to_dict()

    def request_activation_approval(
        self,
        domain: str,
        actor: str,
        rationale: str = "",
        simulation_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Produce an approval-ready payload for policy activation.

        Does NOT create an approval in ApprovalStore. Returns a
        structured dict suitable for integration with approval workflow.
        """
        ts = datetime.now(timezone.utc)
        mgr = self.get_lifecycle_manager()
        payload = mgr.request_activation_approval(
            domain, actor, rationale, simulation_summary,
        )
        self._append_audit_entry(
            event_type="request_activation_approval",
            domain=domain,
            timestamp=ts,
            summary={
                "candidate_profile_id": payload.get("candidate_profile_id"),
                "candidate_profile_version": payload.get("candidate_profile_version"),
                "actor": actor,
            },
        )
        return payload

    def get_deployment_history(
        self, domain: str, limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get deployment history for a domain (most recent first)."""
        mgr = self.get_lifecycle_manager()
        return mgr.get_deployment_history(domain, limit)

    def get_active_deployment(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get the current active deployment record for a domain."""
        mgr = self.get_lifecycle_manager()
        return mgr.get_active_record(domain)

    # -----------------------------------------------------------------
    # P4: Control-plane surfaces
    # -----------------------------------------------------------------

    def get_control_plane(self) -> Any:
        """
        Get the PolicyControlPlane attached to this service.

        Lazily created on first access. Uses the same registry and
        lifecycle manager as this service.
        """
        if not hasattr(self, "_control_plane"):
            from .policy_control_plane import PolicyControlPlane
            self._control_plane = PolicyControlPlane(
                registry=self._get_registry(),
                lifecycle_manager=self.get_lifecycle_manager(),
                audit_log=self._policy_audit_log,
            )
        return self._control_plane

    def get_system_snapshot(
        self, tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get a unified snapshot of all-domains policy state.

        Delegates to PolicyControlPlane.get_system_snapshot().
        """
        return self.get_control_plane().get_system_snapshot(tenant_id=tenant_id)

    def get_domain_status(
        self, domain: str, tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get full policy status for a single domain.

        Delegates to PolicyControlPlane.get_domain_status().
        """
        return self.get_control_plane().get_domain_status(
            domain=domain, tenant_id=tenant_id,
        )

    def get_health_report(
        self, tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compute a policy health report.

        Delegates to PolicyControlPlane.get_health_report().
        """
        return self.get_control_plane().get_health_report(tenant_id=tenant_id)

    def get_active_profiles_summary(
        self, tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get a summary of active profiles for all domains.

        Delegates to PolicyControlPlane.get_active_profiles_summary().
        """
        return self.get_control_plane().get_active_profiles_summary(
            tenant_id=tenant_id,
        )

    def get_filtered_deployment_history(
        self,
        domain: str,
        limit: int = 50,
        status_filter: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get filtered deployment history with metadata envelope.

        Delegates to PolicyControlPlane.get_deployment_history().
        """
        return self.get_control_plane().get_deployment_history(
            domain=domain, limit=limit,
            status_filter=status_filter, tenant_id=tenant_id,
        )

    def get_approval_history(
        self,
        domain: Optional[str] = None,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get audit entries related to approvals and activations.

        Delegates to PolicyControlPlane.get_approval_history().
        """
        return self.get_control_plane().get_approval_history(
            domain=domain, limit=limit, tenant_id=tenant_id,
        )

    def get_simulation_history(
        self,
        domain: Optional[str] = None,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get deployment records with attached simulation summaries.

        Delegates to PolicyControlPlane.get_simulation_history().
        """
        return self.get_control_plane().get_simulation_history(
            domain=domain, limit=limit, tenant_id=tenant_id,
        )

    # -----------------------------------------------------------------
    # P1-D: Audit log
    # -----------------------------------------------------------------

    def get_policy_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent policy audit entries.

        Args:
            limit: Maximum entries to return (most recent first)

        Returns:
            List of audit entry dicts, most recent first
        """
        return list(reversed(self._policy_audit_log[-limit:]))

    def get_policy_audit_count(self) -> int:
        """Get total number of policy audit entries."""
        return len(self._policy_audit_log)

    def clear_policy_audit_log(self) -> None:
        """Clear the in-memory audit log."""
        self._policy_audit_log.clear()

    # -----------------------------------------------------------------
    # Internal audit helpers
    # -----------------------------------------------------------------

    def _append_audit_entry(
        self,
        event_type: str,
        domain: Optional[str],
        timestamp: datetime,
        summary: Dict[str, Any],
    ) -> None:
        """Append a lightweight audit entry to the in-memory log."""
        entry = {
            "event_type": event_type,
            "timestamp": timestamp.isoformat(),
            "decision_id": self._generate_decision_id(event_type, timestamp),
            "domain": domain,
            "summary": summary,
            "service_version": P1_VERSION,
        }
        self._policy_audit_log.append(entry)

        # Evict oldest entries if over limit
        if len(self._policy_audit_log) > _MAX_AUDIT_ENTRIES:
            self._policy_audit_log = self._policy_audit_log[-_MAX_AUDIT_ENTRIES:]

    @staticmethod
    def _generate_decision_id(event_type: str, timestamp: datetime) -> str:
        """Generate a short deterministic decision ID."""
        content = f"{event_type}:{timestamp.isoformat()}"
        return f"ps-{hashlib.sha256(content.encode()).hexdigest()[:12]}"


# =============================================================================
# Module-level convenience
# =============================================================================


def get_policy_service() -> PolicyService:
    """
    Get a new PolicyService instance.

    Each call returns a fresh instance with its own audit log.
    For shared audit across a request lifecycle, callers should
    create one instance and pass it through.
    """
    return PolicyService()


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "PolicyService",
    "get_policy_service",
    "P1_VERSION",
]
