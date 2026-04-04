"""
Policy Control Plane — Policy Phase P4

Operator-ready query surfaces, policy health visibility, and
clean backend/API-facing control-plane surface for the policy layer.

STATUS: ACTIVE (Policy Phase P4)

WHAT THIS MODULE DOES:
    - Provides unified snapshot of all-domains policy state
    - Exposes per-domain status including active profile, candidate, history
    - Computes policy health signals (stale candidates, fallback detection)
    - Prepares structured outputs suitable for backend/API consumers
    - Supports future tenant-scoping via optional tenant_id parameters

WHAT THIS MODULE DOES NOT DO:
    - Serve HTTP endpoints or render UI
    - Manage tenants or licensing
    - Call LLMs or perform non-deterministic operations
    - Persist data (delegates to in-memory stores)

Design Principles:
    - Zero-LLM: Pure deterministic logic
    - Read-only: All methods are queries, no mutations
    - Fail-open for reads: Missing data returns empty/None, not errors
    - Structured output: Every method returns dicts suitable for JSON serialization
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .policy_lifecycle import PolicyLifecycleManager
    from .profile_schema import ProfileRegistry

# =============================================================================
# Constants
# =============================================================================

P4_VERSION = "1.0.0"

# A candidate older than this many seconds is considered stale
_STALE_CANDIDATE_THRESHOLD_SECONDS = 86400  # 24 hours


# =============================================================================
# Domain Status
# =============================================================================


@dataclass(frozen=True)
class PolicyDomainStatus:
    """
    Snapshot of a single domain's policy state.

    Captures the active profile, whether a candidate is staged,
    deployment history depth, and health signals.
    """
    domain: str
    profile_id: str
    profile_version: str
    is_builtin: bool
    has_candidate: bool
    candidate_status: Optional[str] = None
    candidate_profile_id: Optional[str] = None
    active_record_id: Optional[str] = None
    deployment_count: int = 0
    last_activated_at: Optional[str] = None
    last_activated_by: Optional[str] = None
    is_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "is_builtin": self.is_builtin,
            "has_candidate": self.has_candidate,
            "candidate_status": self.candidate_status,
            "candidate_profile_id": self.candidate_profile_id,
            "active_record_id": self.active_record_id,
            "deployment_count": self.deployment_count,
            "last_activated_at": self.last_activated_at,
            "last_activated_by": self.last_activated_by,
            "is_fallback": self.is_fallback,
        }


# =============================================================================
# Health Report
# =============================================================================


@dataclass(frozen=True)
class PolicyHealthReport:
    """
    Aggregated health report for the policy subsystem.

    Captures:
    - Total registered domains
    - Domains using builtin vs custom profiles
    - Stale candidates (staged but not activated within threshold)
    - Domains using fallback (generic) profiles
    - Subsystem readiness flags
    """
    total_domains: int
    builtin_count: int
    custom_count: int
    fallback_domains: List[str]
    stale_candidates: List[Dict[str, Any]]
    domains_with_candidates: List[str]
    total_deployments: int
    healthy: bool
    warnings: List[str]
    checked_at: str
    version: str = P4_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_domains": self.total_domains,
            "builtin_count": self.builtin_count,
            "custom_count": self.custom_count,
            "fallback_domains": self.fallback_domains,
            "stale_candidates": self.stale_candidates,
            "domains_with_candidates": self.domains_with_candidates,
            "total_deployments": self.total_deployments,
            "healthy": self.healthy,
            "warnings": self.warnings,
            "checked_at": self.checked_at,
            "version": self.version,
        }


# =============================================================================
# Control Plane
# =============================================================================


class PolicyControlPlane:
    """
    Operator-ready, read-only control-plane surface for the policy layer.

    Provides structured queries over registry, lifecycle, and audit state.
    All methods return JSON-serializable dicts.

    Usage:
        from agentic.policy.policy_control_plane import PolicyControlPlane

        cp = PolicyControlPlane(registry, lifecycle_manager, audit_log)
        snapshot = cp.get_system_snapshot()
        health = cp.get_health_report()
        status = cp.get_domain_status("trading")
    """

    def __init__(
        self,
        registry: "ProfileRegistry",
        lifecycle_manager: "PolicyLifecycleManager",
        audit_log: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self._registry = registry
        self._lifecycle = lifecycle_manager
        self._audit_log = audit_log if audit_log is not None else []

    # -----------------------------------------------------------------
    # System snapshot
    # -----------------------------------------------------------------

    def get_system_snapshot(
        self, tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get a unified snapshot of all-domains policy state.

        Returns a structured dict with per-domain status, aggregate
        counts, and metadata. Suitable for operator dashboards or
        backend health checks.

        Args:
            tenant_id: Reserved for future tenant-scoping (currently ignored)

        Returns:
            Dict with:
                domains: dict of domain -> PolicyDomainStatus.to_dict()
                summary: aggregate counts
                version: P4 version
                generated_at: ISO-8601 timestamp
                tenant_id: tenant_id (passthrough for future use)
        """
        ts = datetime.now(timezone.utc).isoformat()
        all_profiles = self._registry.all_profiles()

        domains = {}
        builtin_count = 0
        custom_count = 0
        fallback_domains = []

        for domain_key, profile in all_profiles.items():
            status = self._build_domain_status(domain_key, profile)
            domains[domain_key] = status.to_dict()
            if status.is_builtin:
                builtin_count += 1
            else:
                custom_count += 1
            if status.is_fallback:
                fallback_domains.append(domain_key)

        return {
            "domains": domains,
            "summary": {
                "total_domains": len(all_profiles),
                "builtin_count": builtin_count,
                "custom_count": custom_count,
                "fallback_domains": fallback_domains,
            },
            "version": P4_VERSION,
            "generated_at": ts,
            "tenant_id": tenant_id,
        }

    # -----------------------------------------------------------------
    # Per-domain status
    # -----------------------------------------------------------------

    def get_domain_status(
        self,
        domain: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the full policy status for a single domain.

        Returns None if the domain is not registered (including
        domains that would fall back to generic).

        Args:
            domain: Domain identifier
            tenant_id: Reserved for future tenant-scoping

        Returns:
            PolicyDomainStatus.to_dict() or None
        """
        all_profiles = self._registry.all_profiles()
        profile = all_profiles.get(domain)
        if profile is None:
            return None
        status = self._build_domain_status(domain, profile)
        result = status.to_dict()
        result["tenant_id"] = tenant_id
        return result

    # -----------------------------------------------------------------
    # Deployment history query
    # -----------------------------------------------------------------

    def get_deployment_history(
        self,
        domain: str,
        limit: int = 50,
        status_filter: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get filtered deployment history for a domain.

        Args:
            domain: Domain identifier
            limit: Max records to return
            status_filter: Optional status to filter by (e.g., "active", "superseded")
            tenant_id: Reserved for future tenant-scoping

        Returns:
            Dict with records list and metadata
        """
        history = self._lifecycle.get_deployment_history(domain, limit=limit)

        if status_filter:
            history = [r for r in history if r.get("status") == status_filter]

        return {
            "domain": domain,
            "records": history,
            "count": len(history),
            "version": P4_VERSION,
            "tenant_id": tenant_id,
        }

    # -----------------------------------------------------------------
    # Approval history query
    # -----------------------------------------------------------------

    def get_approval_history(
        self,
        domain: Optional[str] = None,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get audit entries related to approvals and activations.

        Filters the audit log for activation/approval events.

        Args:
            domain: Optional domain filter
            limit: Max entries to return
            tenant_id: Reserved for future tenant-scoping

        Returns:
            Dict with entries list and metadata
        """
        approval_types = {
            "activate_profile",
            "rollback_profile",
            "request_activation_approval",
            "stage_candidate",
            "validate_candidate",
        }

        entries = [
            e for e in reversed(self._audit_log)
            if e.get("event_type") in approval_types
        ]

        if domain:
            entries = [e for e in entries if e.get("domain") == domain]

        entries = entries[:limit]

        return {
            "entries": entries,
            "count": len(entries),
            "domain": domain,
            "version": P4_VERSION,
            "tenant_id": tenant_id,
        }

    # -----------------------------------------------------------------
    # Simulation results query
    # -----------------------------------------------------------------

    def get_simulation_history(
        self,
        domain: Optional[str] = None,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get deployment records that include simulation summaries.

        Scans deployment history for records with non-null simulation_summary.

        Args:
            domain: Optional domain filter (None = all domains)
            limit: Max records to return
            tenant_id: Reserved for future tenant-scoping

        Returns:
            Dict with records list and metadata
        """
        results = []
        domains_to_check = (
            [domain] if domain
            else list(self._registry.all_profiles().keys())
        )

        for d in domains_to_check:
            history = self._lifecycle.get_deployment_history(d, limit=200)
            for record in history:
                if record.get("simulation_summary") is not None:
                    results.append(record)

        # Sort by created_at descending
        results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        results = results[:limit]

        return {
            "records": results,
            "count": len(results),
            "domain": domain,
            "version": P4_VERSION,
            "tenant_id": tenant_id,
        }

    # -----------------------------------------------------------------
    # Health report
    # -----------------------------------------------------------------

    def get_health_report(
        self,
        stale_threshold_seconds: int = _STALE_CANDIDATE_THRESHOLD_SECONDS,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compute a policy health report.

        Checks:
        - Stale candidates (staged but not activated within threshold)
        - Fallback domains (using generic profile unexpectedly)
        - Subsystem readiness

        Args:
            stale_threshold_seconds: Seconds after which a candidate is stale
            tenant_id: Reserved for future tenant-scoping

        Returns:
            PolicyHealthReport.to_dict() with tenant_id added
        """
        ts = datetime.now(timezone.utc)
        all_profiles = self._registry.all_profiles()

        builtin_ids = {"trading", "therapy", "identity", "generic"}
        builtin_count = 0
        custom_count = 0
        fallback_domains: List[str] = []
        stale_candidates: List[Dict[str, Any]] = []
        domains_with_candidates: List[str] = []
        total_deployments = 0
        warnings: List[str] = []

        for domain_key, profile in all_profiles.items():
            # Classify builtin vs custom
            is_builtin = self._is_builtin_profile(domain_key, profile, builtin_ids)
            if is_builtin:
                builtin_count += 1
            else:
                custom_count += 1

            # Fallback detection
            if domain_key != "generic" and profile.profile_id == "generic":
                fallback_domains.append(domain_key)

            # Count deployments
            history = self._lifecycle.get_deployment_history(domain_key)
            total_deployments += len(history)

            # Check for candidates
            candidate = self._lifecycle.get_candidate(domain_key)
            if candidate is not None:
                domains_with_candidates.append(domain_key)
                # Check staleness
                record = candidate.get("record", {})
                created_at = record.get("created_at")
                if created_at and self._is_stale(created_at, ts, stale_threshold_seconds):
                    stale_candidates.append({
                        "domain": domain_key,
                        "profile_id": record.get("profile_id"),
                        "status": record.get("status"),
                        "created_at": created_at,
                        "age_seconds": self._age_seconds(created_at, ts),
                    })

        # Build warnings
        if stale_candidates:
            warnings.append(
                f"{len(stale_candidates)} stale candidate(s) detected"
            )
        if fallback_domains:
            warnings.append(
                f"{len(fallback_domains)} domain(s) using fallback profile: "
                + ", ".join(fallback_domains)
            )

        healthy = len(warnings) == 0

        report = PolicyHealthReport(
            total_domains=len(all_profiles),
            builtin_count=builtin_count,
            custom_count=custom_count,
            fallback_domains=fallback_domains,
            stale_candidates=stale_candidates,
            domains_with_candidates=domains_with_candidates,
            total_deployments=total_deployments,
            healthy=healthy,
            warnings=warnings,
            checked_at=ts.isoformat(),
        )

        result = report.to_dict()
        result["tenant_id"] = tenant_id
        return result

    # -----------------------------------------------------------------
    # Active state summary (all domains at once)
    # -----------------------------------------------------------------

    def get_active_profiles_summary(
        self, tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get a summary of the currently active profile for every domain.

        Returns a lightweight view suitable for quick operator checks.

        Args:
            tenant_id: Reserved for future tenant-scoping

        Returns:
            Dict with per-domain active profile info
        """
        all_profiles = self._registry.all_profiles()
        builtin_ids = {"trading", "therapy", "identity", "generic"}
        profiles = {}

        for domain_key, profile in all_profiles.items():
            active_record = self._lifecycle.get_active_record(domain_key)
            is_builtin = self._is_builtin_profile(domain_key, profile, builtin_ids)

            profiles[domain_key] = {
                "profile_id": profile.profile_id,
                "profile_version": profile.profile_version,
                "is_builtin": is_builtin,
                "activated_at": active_record.get("created_at") if active_record else None,
                "activated_by": active_record.get("actor") if active_record else None,
            }

        return {
            "profiles": profiles,
            "count": len(profiles),
            "version": P4_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tenant_id": tenant_id,
        }

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _build_domain_status(
        self, domain: str, profile: Any,
    ) -> PolicyDomainStatus:
        """Build a PolicyDomainStatus for a domain."""
        builtin_ids = {"trading", "therapy", "identity", "generic"}
        is_builtin = self._is_builtin_profile(domain, profile, builtin_ids)

        # Check for candidate
        candidate = self._lifecycle.get_candidate(domain)
        has_candidate = candidate is not None
        candidate_status = None
        candidate_profile_id = None
        if candidate:
            record = candidate.get("record", {})
            candidate_status = record.get("status")
            candidate_profile_id = record.get("profile_id")

        # Active deployment record
        active_record = self._lifecycle.get_active_record(domain)
        active_record_id = active_record.get("record_id") if active_record else None
        last_activated_at = active_record.get("created_at") if active_record else None
        last_activated_by = active_record.get("actor") if active_record else None

        # Deployment count
        history = self._lifecycle.get_deployment_history(domain)
        deployment_count = len(history)

        # Fallback detection
        is_fallback = (domain != "generic" and profile.profile_id == "generic")

        return PolicyDomainStatus(
            domain=domain,
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            is_builtin=is_builtin,
            has_candidate=has_candidate,
            candidate_status=candidate_status,
            candidate_profile_id=candidate_profile_id,
            active_record_id=active_record_id,
            deployment_count=deployment_count,
            last_activated_at=last_activated_at,
            last_activated_by=last_activated_by,
            is_fallback=is_fallback,
        )

    @staticmethod
    def _is_builtin_profile(
        domain: str, profile: Any, builtin_ids: set,
    ) -> bool:
        """Check if a profile is a builtin default."""
        return (
            domain in builtin_ids
            and profile.profile_id == domain
            and profile.profile_version == "1.0.0"
        )

    @staticmethod
    def _is_stale(
        created_at: str, now: datetime, threshold_seconds: int,
    ) -> bool:
        """Check if a timestamp is older than the threshold."""
        try:
            created = datetime.fromisoformat(created_at)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age = (now - created).total_seconds()
            return age > threshold_seconds
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _age_seconds(created_at: str, now: datetime) -> float:
        """Compute age in seconds from a timestamp."""
        try:
            created = datetime.fromisoformat(created_at)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return (now - created).total_seconds()
        except (ValueError, TypeError):
            return 0.0


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "PolicyControlPlane",
    "PolicyDomainStatus",
    "PolicyHealthReport",
    "P4_VERSION",
]
