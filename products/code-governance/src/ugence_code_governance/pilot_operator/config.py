"""Immutable, versioned pilot deployment configuration.

A deployment config is tightly bounded and fails closed: it must name explicit
repositories and branches, an explicit tenant, an evaluation bound and/or a pilot
end time, bounded concurrency, and a durable store — and it must never inline a
credential value. Config fingerprints exclude credential values (only reference
names/scopes are fingerprinted).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple

from ..fingerprints import domain_hash
from ..pilot.config import RetentionCategory
from .errors import PilotConfigError
from .security import CredentialReference, ResolverKind

CONFIG_SCHEMA_VERSION = "code_governance.pilot_deployment_config.v1"
DOMAIN_PILOT_DEPLOYMENT_CONFIG = "cg.pilot_operator.config.v1"
#: Hard upper safety bound on concurrency for MVP 1E (no unbounded worker pools).
MAX_CONCURRENCY = 4


@dataclass(frozen=True)
class PilotStopThresholds:
    """Configured thresholds that trip a pause/stop/abort (advisory; never execution)."""

    max_integrity_failures: int = 0
    max_artifact_mismatch_rate: float = 1.0
    max_source_failure_rate: float = 1.0
    max_unexplained_escalation_rate: float = 1.0
    abort_on_write_boundary_violation: bool = True
    abort_on_credential_leak: bool = True


@dataclass(frozen=True)
class PilotDeploymentConfig:
    """An immutable, tightly-bounded pilot deployment configuration."""

    config_id: str
    config_version: str
    pilot_id: str
    tenant_id: str
    allowed_repositories: Tuple[str, ...]
    allowed_branches: Tuple[str, ...]
    durable_store_path: str
    github_adapter_registry_ref: str
    credential_references: Tuple[CredentialReference, ...] = ()
    approved_snapshot_adapters: Tuple[str, ...] = ()
    allowed_pull_request_numbers: Tuple[int, ...] = ()
    evaluation_profile_ref: str = ""
    intervention_routing_ref: str = ""
    reviewer_role_allowlist: Tuple[str, ...] = ()
    maximum_evaluations: int = 100
    maximum_evaluations_per_hour: int = 60
    maximum_concurrent_collections: int = 1
    maximum_concurrent_evaluations: int = 1
    collection_timeout_s: float = 10.0
    retry_max_attempts: int = 2
    pilot_start_at: Optional[str] = None
    pilot_end_at: Optional[str] = None
    manual_pause: bool = False
    stop_thresholds: PilotStopThresholds = field(default_factory=PilotStopThresholds)
    retention_category: RetentionCategory = RetentionCategory.SHORT_PILOT
    logging_policy: str = "redacted"
    metrics_policy: str = "operator"
    reporting_policy: str = "offline"
    schema_version: str = CONFIG_SCHEMA_VERSION
    policy_refs: Tuple[str, ...] = ()

    @property
    def fingerprint(self) -> str:
        return fingerprint_pilot_config(self)


def validate_pilot_config(config: PilotDeploymentConfig) -> PilotDeploymentConfig:
    """Validate a deployment config; raise PilotConfigError (fail closed) on any issue."""
    if config.schema_version != CONFIG_SCHEMA_VERSION:
        raise PilotConfigError(f"unsupported config schema version {config.schema_version!r}")
    if not config.tenant_id or config.tenant_id in ("*", "all", "any"):
        raise PilotConfigError("tenant scope must be explicit (no wildcard)")
    if not config.allowed_repositories:
        raise PilotConfigError("repository allowlist must be non-empty")
    if any(r in ("*", "") or r.endswith("/*") for r in config.allowed_repositories):
        raise PilotConfigError("repositories must be explicit (no wildcard)")
    if not config.allowed_branches:
        raise PilotConfigError("branch allowlist must be non-empty")
    if any(b in ("*", "") for b in config.allowed_branches):
        raise PilotConfigError("branches must be explicit (no wildcard)")
    if not config.durable_store_path:
        raise PilotConfigError("durable store path is required")
    # An evaluation bound and/or a pilot end time is mandatory.
    if config.maximum_evaluations <= 0 and not config.pilot_end_at:
        raise PilotConfigError("a positive maximum_evaluations or a pilot_end_at is required")
    if config.maximum_evaluations <= 0:
        raise PilotConfigError("maximum_evaluations must be positive")
    # Bounded concurrency.
    for name, val in (("maximum_concurrent_collections", config.maximum_concurrent_collections),
                      ("maximum_concurrent_evaluations", config.maximum_concurrent_evaluations)):
        if val < 1 or val > MAX_CONCURRENCY:
            raise PilotConfigError(f"{name} must be within 1..{MAX_CONCURRENCY}")
    if config.maximum_evaluations_per_hour <= 0:
        raise PilotConfigError("maximum_evaluations_per_hour must be positive")
    # Credential references must be read-only (no write scope) and value-free.
    for ref in config.credential_references:
        if any(":write" in s for s in ref.required_scopes):
            raise PilotConfigError(f"credential reference {ref.reference_id!r} requests a write scope")
    return config


def fingerprint_pilot_config(config: PilotDeploymentConfig) -> str:
    """Content fingerprint over the config, excluding any credential value.

    Credential references contribute only their names/refs/scopes (never a value).
    """
    return domain_hash(DOMAIN_PILOT_DEPLOYMENT_CONFIG, {
        "config_id": config.config_id, "config_version": config.config_version,
        "pilot_id": config.pilot_id, "tenant_id": config.tenant_id,
        "allowed_repositories": sorted(config.allowed_repositories),
        "allowed_branches": sorted(config.allowed_branches),
        "allowed_pull_request_numbers": sorted(config.allowed_pull_request_numbers),
        "durable_store_path": config.durable_store_path,
        "github_adapter_registry_ref": config.github_adapter_registry_ref,
        "approved_snapshot_adapters": sorted(config.approved_snapshot_adapters),
        "credential_references": sorted(
            [ref.fingerprint_fields() for ref in config.credential_references],
            key=lambda d: d["reference_id"]),
        "evaluation_profile_ref": config.evaluation_profile_ref,
        "intervention_routing_ref": config.intervention_routing_ref,
        "reviewer_role_allowlist": sorted(config.reviewer_role_allowlist),
        "maximum_evaluations": config.maximum_evaluations,
        "maximum_evaluations_per_hour": config.maximum_evaluations_per_hour,
        "maximum_concurrent_collections": config.maximum_concurrent_collections,
        "maximum_concurrent_evaluations": config.maximum_concurrent_evaluations,
        "collection_timeout_s": config.collection_timeout_s,
        "retry_max_attempts": config.retry_max_attempts,
        "pilot_start_at": config.pilot_start_at, "pilot_end_at": config.pilot_end_at,
        "retention_category": config.retention_category.value,
        "schema_version": config.schema_version, "policy_refs": sorted(config.policy_refs),
    })


def load_pilot_config(data: Mapping[str, Any]) -> PilotDeploymentConfig:
    """Load a deployment config from canonical JSON-compatible data (never executable).

    Inline credential *values* are refused; only credential *references* are read.
    """
    if not isinstance(data, Mapping):
        raise PilotConfigError("config must be a mapping")
    for banned in ("credential", "token", "secret", "password", "private_key", "api_key"):
        if banned in data:
            raise PilotConfigError(f"inline credential field {banned!r} is not permitted")
    refs = tuple(
        CredentialReference(
            reference_id=r["reference_id"],
            resolver_kind=ResolverKind(r.get("resolver_kind", "ENVIRONMENT")),
            source_host=r.get("source_host", ""),
            environment_variable_name=r.get("environment_variable_name", ""),
            external_resolver_ref=r.get("external_resolver_ref", ""),
            required_scopes=tuple(r.get("required_scopes", ())))
        for r in data.get("credential_references", []))
    st = data.get("stop_thresholds", {})
    config = PilotDeploymentConfig(
        config_id=data["config_id"], config_version=data["config_version"],
        pilot_id=data["pilot_id"], tenant_id=data["tenant_id"],
        allowed_repositories=tuple(data.get("allowed_repositories", ())),
        allowed_branches=tuple(data.get("allowed_branches", ())),
        durable_store_path=data.get("durable_store_path", ""),
        github_adapter_registry_ref=data.get("github_adapter_registry_ref", ""),
        credential_references=refs,
        approved_snapshot_adapters=tuple(data.get("approved_snapshot_adapters", ())),
        allowed_pull_request_numbers=tuple(data.get("allowed_pull_request_numbers", ())),
        evaluation_profile_ref=data.get("evaluation_profile_ref", ""),
        intervention_routing_ref=data.get("intervention_routing_ref", ""),
        reviewer_role_allowlist=tuple(data.get("reviewer_role_allowlist", ())),
        maximum_evaluations=int(data.get("maximum_evaluations", 100)),
        maximum_evaluations_per_hour=int(data.get("maximum_evaluations_per_hour", 60)),
        maximum_concurrent_collections=int(data.get("maximum_concurrent_collections", 1)),
        maximum_concurrent_evaluations=int(data.get("maximum_concurrent_evaluations", 1)),
        collection_timeout_s=float(data.get("collection_timeout_s", 10.0)),
        retry_max_attempts=int(data.get("retry_max_attempts", 2)),
        pilot_start_at=data.get("pilot_start_at"), pilot_end_at=data.get("pilot_end_at"),
        manual_pause=bool(data.get("manual_pause", False)),
        stop_thresholds=PilotStopThresholds(
            max_integrity_failures=int(st.get("max_integrity_failures", 0)),
            max_artifact_mismatch_rate=float(st.get("max_artifact_mismatch_rate", 1.0)),
            max_source_failure_rate=float(st.get("max_source_failure_rate", 1.0)),
            max_unexplained_escalation_rate=float(st.get("max_unexplained_escalation_rate", 1.0))),
        retention_category=RetentionCategory(data.get("retention_category", "SHORT_PILOT")),
        schema_version=data.get("schema_version", CONFIG_SCHEMA_VERSION),
        policy_refs=tuple(data.get("policy_refs", ())))
    return validate_pilot_config(config)


def load_pilot_config_json(text: str) -> PilotDeploymentConfig:
    return load_pilot_config(json.loads(text))


__all__ = [
    "CONFIG_SCHEMA_VERSION", "MAX_CONCURRENCY", "PilotStopThresholds",
    "PilotDeploymentConfig", "validate_pilot_config", "fingerprint_pilot_config",
    "load_pilot_config", "load_pilot_config_json",
]
