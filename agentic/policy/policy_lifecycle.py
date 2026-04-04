"""
Policy Lifecycle Manager — Policy Phase P3

Provides a deployment lifecycle for policy profiles: draft, validation,
activation, supersession, archival, and rollback.

STATUS: ACTIVE (Policy Phase P3)

WHAT THIS MODULE DOES:
    - Defines lifecycle statuses for policy profiles
    - Tracks deployment history with audit-grade metadata
    - Supports explicit activation with actor/rationale/approval
    - Supports deterministic rollback to previous version
    - Produces approval-ready payloads for governance integration
    - Links simulation/comparison results to deployment decisions

WHAT THIS MODULE DOES NOT DO:
    - Persist deployment records to durable storage (in-memory only)
    - Provide HTTP endpoints or UI
    - Manage multi-tenant scoping
    - Execute approval workflows (produces payloads only)

Design Principles:
    - Zero-LLM: Pure deterministic logic
    - Fail-closed: Invalid transitions raise errors
    - Audit-by-default: Every lifecycle event is recorded
    - Backward compatible: Existing profile usage unchanged

Usage:
    from agentic.policy.policy_lifecycle import (
        PolicyLifecycleManager,
        ProfileStatus,
        DeploymentRecord,
    )

    mgr = PolicyLifecycleManager(registry)

    # Stage a candidate
    mgr.stage_candidate("trading", new_profile, actor="admin@corp.com")

    # Validate (optionally with simulation)
    mgr.validate_candidate("trading", actor="admin@corp.com", simulation_summary={...})

    # Activate (promotes to registry, supersedes previous)
    record = mgr.activate("trading", actor="admin@corp.com", rationale="tuning thresholds")

    # Rollback to previous
    record = mgr.rollback("trading", actor="admin@corp.com", rationale="regression detected")

    # History
    history = mgr.get_deployment_history("trading")
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .profile_schema import DomainProfile, ProfileRegistry


# =============================================================================
# Lifecycle Status
# =============================================================================


class ProfileStatus(Enum):
    """Lifecycle status of a policy profile revision."""
    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


# Valid transitions
_VALID_TRANSITIONS = {
    ProfileStatus.DRAFT: frozenset({ProfileStatus.VALIDATED, ProfileStatus.ACTIVE, ProfileStatus.ARCHIVED}),
    ProfileStatus.VALIDATED: frozenset({ProfileStatus.ACTIVE, ProfileStatus.ARCHIVED}),
    ProfileStatus.ACTIVE: frozenset({ProfileStatus.SUPERSEDED, ProfileStatus.ARCHIVED}),
    ProfileStatus.SUPERSEDED: frozenset({ProfileStatus.ARCHIVED}),
    ProfileStatus.ARCHIVED: frozenset(),
}


class PolicyLifecycleError(Exception):
    """Raised on invalid lifecycle operations."""


# =============================================================================
# Deployment Record
# =============================================================================


@dataclass(frozen=True)
class DeploymentRecord:
    """
    Immutable record of a policy deployment lifecycle event.

    Carries enough metadata to answer:
    - Which profile/version was active?
    - When was it activated?
    - What did it replace?
    - Who activated it?
    - Was it approved?
    - What simulation/comparison was done before activation?
    - When was it rolled back?
    """
    domain: str
    profile_id: str
    profile_version: str
    status: ProfileStatus
    created_at: str  # ISO-8601
    actor: str
    rationale: str = ""
    previous_version: Optional[str] = None
    previous_profile_id: Optional[str] = None
    approval_id: Optional[str] = None
    simulation_summary: Optional[Dict[str, Any]] = None
    record_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "domain": self.domain,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "status": self.status.value,
            "created_at": self.created_at,
            "actor": self.actor,
            "rationale": self.rationale,
            "previous_version": self.previous_version,
            "previous_profile_id": self.previous_profile_id,
            "approval_id": self.approval_id,
            "simulation_summary": self.simulation_summary,
        }


# =============================================================================
# Lifecycle Manager
# =============================================================================


class PolicyLifecycleManager:
    """
    Manages the deployment lifecycle for policy profiles.

    Tracks candidates, activations, supersessions, and rollbacks
    with audit-grade metadata.

    Works alongside ProfileRegistry: the registry holds the active
    profile; the lifecycle manager tracks the history and transitions.

    Thread Safety:
        Append-only history. For concurrent mutation, callers should
        use external synchronization.
    """

    def __init__(self, registry: "ProfileRegistry") -> None:
        self._registry = registry
        # domain -> list of DeploymentRecords (most recent last)
        self._history: Dict[str, List[DeploymentRecord]] = {}
        # domain -> candidate profile (staged but not yet active)
        self._candidates: Dict[str, _CandidateEntry] = {}

    # -----------------------------------------------------------------
    # Stage / Validate / Activate
    # -----------------------------------------------------------------

    def stage_candidate(
        self,
        domain: str,
        profile: "DomainProfile",
        actor: str,
        rationale: str = "",
    ) -> DeploymentRecord:
        """
        Stage a candidate profile for a domain.

        The candidate is in DRAFT status until validated and activated.
        Staging replaces any previously staged candidate for the domain.

        Args:
            domain: Domain identifier
            profile: DomainProfile to stage
            actor: Who is staging this candidate
            rationale: Why this candidate is being staged

        Returns:
            DeploymentRecord in DRAFT status
        """
        record = self._make_record(
            domain=domain,
            profile=profile,
            status=ProfileStatus.DRAFT,
            actor=actor,
            rationale=rationale,
        )
        self._candidates[domain] = _CandidateEntry(
            profile=profile, record=record,
        )
        self._append_history(domain, record)
        return record

    def validate_candidate(
        self,
        domain: str,
        actor: str,
        rationale: str = "",
        simulation_summary: Optional[Dict[str, Any]] = None,
    ) -> DeploymentRecord:
        """
        Mark a staged candidate as validated.

        Optionally attach a simulation/comparison summary.

        Args:
            domain: Domain identifier
            actor: Who is validating
            rationale: Validation notes
            simulation_summary: Optional simulation/comparison result

        Returns:
            DeploymentRecord in VALIDATED status

        Raises:
            PolicyLifecycleError: If no candidate is staged
        """
        entry = self._candidates.get(domain)
        if entry is None:
            raise PolicyLifecycleError(
                f"No candidate staged for domain '{domain}'"
            )
        self._check_transition(entry.record.status, ProfileStatus.VALIDATED)

        record = self._make_record(
            domain=domain,
            profile=entry.profile,
            status=ProfileStatus.VALIDATED,
            actor=actor,
            rationale=rationale,
            simulation_summary=simulation_summary,
        )
        self._candidates[domain] = _CandidateEntry(
            profile=entry.profile, record=record,
        )
        self._append_history(domain, record)
        return record

    def activate(
        self,
        domain: str,
        actor: str,
        rationale: str = "",
        approval_id: Optional[str] = None,
        simulation_summary: Optional[Dict[str, Any]] = None,
        require_validation: bool = False,
    ) -> DeploymentRecord:
        """
        Activate the staged candidate, promoting it into the registry.

        The previously active profile (if any) is marked SUPERSEDED.

        Args:
            domain: Domain identifier
            actor: Who is activating
            rationale: Why this activation is happening
            approval_id: Optional approval ID from approval workflow
            simulation_summary: Optional simulation/comparison to attach
            require_validation: If True, candidate must be in VALIDATED status

        Returns:
            DeploymentRecord in ACTIVE status

        Raises:
            PolicyLifecycleError: If no candidate staged, or validation required
                but candidate is still DRAFT
        """
        entry = self._candidates.get(domain)
        if entry is None:
            raise PolicyLifecycleError(
                f"No candidate staged for domain '{domain}'"
            )

        if require_validation and entry.record.status != ProfileStatus.VALIDATED:
            raise PolicyLifecycleError(
                f"Candidate for '{domain}' is {entry.record.status.value}, "
                f"not validated. Validate before activating."
            )

        self._check_transition(entry.record.status, ProfileStatus.ACTIVE)

        # Capture previous active profile info
        previous = self._registry.get(domain)
        prev_id = previous.profile_id if previous else None
        prev_version = previous.profile_version if previous else None

        # Supersede the previous active profile in history.
        # If there's no explicit ACTIVE record yet (i.e., the previous
        # profile was a builtin), create a SUPERSEDED record for it so
        # rollback can find it later.
        had_active = self._supersede_current(domain, actor)
        if not had_active and previous is not None:
            builtin_record = self._make_record(
                domain=domain,
                profile=previous,
                status=ProfileStatus.SUPERSEDED,
                actor=actor,
                rationale="superseded by lifecycle activation",
            )
            self._append_history(domain, builtin_record)

        # Register the candidate in the registry
        self._registry.register(entry.profile, domain_id=domain)

        # Use simulation_summary from validation if not provided at activation
        effective_sim = simulation_summary
        if effective_sim is None and entry.record.simulation_summary is not None:
            effective_sim = entry.record.simulation_summary

        record = self._make_record(
            domain=domain,
            profile=entry.profile,
            status=ProfileStatus.ACTIVE,
            actor=actor,
            rationale=rationale,
            previous_profile_id=prev_id,
            previous_version=prev_version,
            approval_id=approval_id,
            simulation_summary=effective_sim,
        )
        self._append_history(domain, record)

        # Clear candidate
        del self._candidates[domain]

        return record

    # -----------------------------------------------------------------
    # Rollback
    # -----------------------------------------------------------------

    def rollback(
        self,
        domain: str,
        actor: str,
        rationale: str = "",
    ) -> DeploymentRecord:
        """
        Rollback to the previously active profile for a domain.

        Finds the most recent SUPERSEDED record and re-activates that
        profile version. The current active is superseded.

        Args:
            domain: Domain identifier
            actor: Who is rolling back
            rationale: Why the rollback

        Returns:
            DeploymentRecord in ACTIVE status (the restored profile)

        Raises:
            PolicyLifecycleError: If no previous version to rollback to
        """
        history = self._history.get(domain, [])

        # Find the most recent SUPERSEDED record
        superseded_record = None
        for rec in reversed(history):
            if rec.status == ProfileStatus.SUPERSEDED:
                superseded_record = rec
                break

        if superseded_record is None:
            raise PolicyLifecycleError(
                f"No previous version to rollback to for domain '{domain}'"
            )

        # Find the profile that was superseded
        # We need to look it up — it might be a builtin or was previously registered
        target_profile = self._find_profile_by_id_and_version(
            superseded_record.profile_id,
            superseded_record.profile_version,
        )
        if target_profile is None:
            raise PolicyLifecycleError(
                f"Cannot find profile '{superseded_record.profile_id}' "
                f"v{superseded_record.profile_version} for rollback"
            )

        # Supersede current
        current = self._registry.get(domain)
        self._supersede_current(domain, actor)

        # Register the rollback target
        self._registry.register(target_profile, domain_id=domain)

        record = self._make_record(
            domain=domain,
            profile=target_profile,
            status=ProfileStatus.ACTIVE,
            actor=actor,
            rationale=f"ROLLBACK: {rationale}",
            previous_profile_id=current.profile_id if current else None,
            previous_version=current.profile_version if current else None,
        )
        self._append_history(domain, record)
        return record

    # -----------------------------------------------------------------
    # Approval hooks
    # -----------------------------------------------------------------

    def request_activation_approval(
        self,
        domain: str,
        actor: str,
        rationale: str = "",
        simulation_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Produce an approval-ready payload for policy activation.

        This does NOT create an actual approval request in ApprovalStore.
        It produces a structured dict that can be used by callers to
        integrate with the approval workflow.

        Args:
            domain: Domain identifier
            actor: Who is requesting approval
            rationale: Why the change is needed
            simulation_summary: Optional simulation/comparison result

        Returns:
            Dict with approval payload suitable for ApprovalContext

        Raises:
            PolicyLifecycleError: If no candidate staged
        """
        entry = self._candidates.get(domain)
        if entry is None:
            raise PolicyLifecycleError(
                f"No candidate staged for domain '{domain}'"
            )

        current = self._registry.get(domain)
        changed_flags = []
        if simulation_summary and isinstance(simulation_summary, dict):
            changed_flags = simulation_summary.get("changed_flags", [])

        return {
            "approval_type": "policy_activation",
            "domain": domain,
            "candidate_profile_id": entry.profile.profile_id,
            "candidate_profile_version": entry.profile.profile_version,
            "candidate_status": entry.record.status.value,
            "current_profile_id": current.profile_id if current else None,
            "current_profile_version": current.profile_version if current else None,
            "actor": actor,
            "rationale": rationale,
            "changed_flags": changed_flags,
            "simulation_summary": simulation_summary,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }

    # -----------------------------------------------------------------
    # Query
    # -----------------------------------------------------------------

    def get_deployment_history(
        self, domain: str, limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get deployment history for a domain (most recent first).

        Returns:
            List of DeploymentRecord dicts
        """
        history = self._history.get(domain, [])
        return [r.to_dict() for r in reversed(history[-limit:])]

    def get_active_record(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Get the current ACTIVE deployment record for a domain.

        Returns None if no explicit activation has been recorded
        (i.e., the profile is a builtin default).
        """
        for rec in reversed(self._history.get(domain, [])):
            if rec.status == ProfileStatus.ACTIVE:
                return rec.to_dict()
        return None

    def get_candidate(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get the currently staged candidate for a domain, if any."""
        entry = self._candidates.get(domain)
        if entry is None:
            return None
        return {
            "profile": entry.profile.to_dict(),
            "record": entry.record.to_dict(),
        }

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _make_record(
        self,
        domain: str,
        profile: "DomainProfile",
        status: ProfileStatus,
        actor: str,
        rationale: str = "",
        previous_profile_id: Optional[str] = None,
        previous_version: Optional[str] = None,
        approval_id: Optional[str] = None,
        simulation_summary: Optional[Dict[str, Any]] = None,
    ) -> DeploymentRecord:
        ts = datetime.now(timezone.utc).isoformat()
        content = f"{domain}:{profile.profile_id}:{profile.profile_version}:{status.value}:{ts}"
        record_id = f"plr-{hashlib.sha256(content.encode()).hexdigest()[:12]}"
        return DeploymentRecord(
            record_id=record_id,
            domain=domain,
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            status=status,
            created_at=ts,
            actor=actor,
            rationale=rationale,
            previous_profile_id=previous_profile_id,
            previous_version=previous_version,
            approval_id=approval_id,
            simulation_summary=simulation_summary,
        )

    def _append_history(self, domain: str, record: DeploymentRecord) -> None:
        if domain not in self._history:
            self._history[domain] = []
        self._history[domain].append(record)

    def _supersede_current(self, domain: str, actor: str) -> bool:
        """Mark the most recent ACTIVE record as SUPERSEDED. Returns True if found."""
        history = self._history.get(domain, [])
        for i in range(len(history) - 1, -1, -1):
            if history[i].status == ProfileStatus.ACTIVE:
                old = history[i]
                history[i] = DeploymentRecord(
                    record_id=old.record_id,
                    domain=old.domain,
                    profile_id=old.profile_id,
                    profile_version=old.profile_version,
                    status=ProfileStatus.SUPERSEDED,
                    created_at=old.created_at,
                    actor=old.actor,
                    rationale=old.rationale,
                    previous_profile_id=old.previous_profile_id,
                    previous_version=old.previous_version,
                    approval_id=old.approval_id,
                    simulation_summary=old.simulation_summary,
                )
                return True
        return False

    def _find_profile_by_id_and_version(
        self,
        profile_id: str,
        profile_version: str,
    ) -> Optional["DomainProfile"]:
        """
        Find a profile by ID and version.

        Checks:
        1. Current registry (may still have the right version)
        2. Builtin defaults (via a fresh registry)
        """
        # Check current registry
        for domain, profile in self._registry.all_profiles().items():
            if (
                profile.profile_id == profile_id
                and profile.profile_version == profile_version
            ):
                return profile

        # Check builtins by creating a temp registry
        from .profile_schema import ProfileRegistry
        temp = ProfileRegistry()
        for domain, profile in temp.all_profiles().items():
            if (
                profile.profile_id == profile_id
                and profile.profile_version == profile_version
            ):
                return profile

        return None

    @staticmethod
    def _check_transition(current: ProfileStatus, target: ProfileStatus) -> None:
        valid = _VALID_TRANSITIONS.get(current, frozenset())
        if target not in valid:
            raise PolicyLifecycleError(
                f"Invalid transition: {current.value} -> {target.value}. "
                f"Valid targets: {[s.value for s in valid]}"
            )


# =============================================================================
# Internal types
# =============================================================================


@dataclass
class _CandidateEntry:
    """Internal: tracks a staged candidate profile and its record."""
    profile: "DomainProfile"
    record: DeploymentRecord


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "ProfileStatus",
    "DeploymentRecord",
    "PolicyLifecycleManager",
    "PolicyLifecycleError",
]
