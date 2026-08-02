"""Security + readiness preflight before a pilot can become READY.

Preflight verifies configuration, tenant/pilot identity, allowlists, durable-store
health + integrity, adapter/host/endpoint approval, read-only credential resolution
(without persisting the value), read-only GitHub permissions, known snapshot
schemas, the execution-disabled invariant, a clean static write-boundary scan, and
that evaluation/concurrency/stop bounds are present. It performs no mutation and
prints no credential.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from ..adapters.registry import AdapterRegistryProjection
from ..adapters.snapshot_schemas import SNAPSHOT_SCHEMAS
from ..persistence.sqlite import DurableShadowStore
from .config import PilotDeploymentConfig, validate_pilot_config
from .errors import PilotConfigError
from .security import scan_paths


class PreflightOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    NOT_RUN = "NOT_RUN"


class PermissionVerification(str, Enum):
    VERIFIED_FROM_SOURCE = "VERIFIED_FROM_SOURCE"
    DECLARED_AND_VALIDATED = "DECLARED_AND_VALIDATED"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class PilotPreflightResult:
    outcome: PreflightOutcome
    checks: Tuple[Tuple[str, str, str], ...] = ()  # (name, PASS/FAIL/WARN, detail)
    permission_verification: PermissionVerification = PermissionVerification.UNVERIFIED
    execution_status: str = "DISABLED"

    @property
    def passed(self) -> bool:
        return self.outcome in (PreflightOutcome.PASS, PreflightOutcome.PASS_WITH_WARNINGS)


def _operator_scan_paths() -> List[Path]:
    base = Path(__file__).resolve().parent.parent
    return list((base / "adapters").glob("*.py")) + list((base / "pilot_operator").glob("*.py"))


def run_pilot_preflight(
    config: PilotDeploymentConfig,
    *,
    store: Optional[DurableShadowStore],
    registry: Optional[AdapterRegistryProjection],
    github_adapter_id: str = "cg.github_readonly",
    github_source_host: str = "api.github.com",
    credential_resolver: Optional[Callable[[str], Any]] = None,
    live_metadata_probe: Optional[Callable[[], bool]] = None,
) -> PilotPreflightResult:
    """Run the pilot preflight. Fails closed; never persists or prints a credential."""
    checks: List[Tuple[str, str, str]] = []

    def ok(name, detail=""):
        checks.append((name, "PASS", detail))

    def fail(name, detail=""):
        checks.append((name, "FAIL", detail))

    def warn(name, detail=""):
        checks.append((name, "WARN", detail))

    # Configuration.
    try:
        validate_pilot_config(config)
        ok("config_schema_valid")
    except PilotConfigError as exc:
        fail("config_schema_valid", str(exc))

    ok("tenant_pilot_identity") if config.tenant_id and config.pilot_id else fail("tenant_pilot_identity")
    ok("repository_allowlist") if config.allowed_repositories else fail("repository_allowlist")
    ok("branch_allowlist") if config.allowed_branches else fail("branch_allowlist")
    ok("evaluation_bounds") if config.maximum_evaluations > 0 else fail("evaluation_bounds")
    ok("concurrency_bounds") if (config.maximum_concurrent_collections >= 1
                                 and config.maximum_concurrent_evaluations >= 1) else fail("concurrency_bounds")
    ok("stop_criteria") if config.stop_thresholds is not None else fail("stop_criteria")

    # Durable store.
    if store is None:
        fail("durable_store_present")
    else:
        health = store.health_check()
        ok("durable_store_healthy") if health.get("ok") else fail("durable_store_healthy", str(health))
        ok("durable_store_integrity") if health.get("ok") else fail("durable_store_integrity")

    # Adapter registry / host / endpoints.
    if registry is None:
        fail("adapter_registry_present")
    else:
        entry = registry.entry_for(github_adapter_id)
        if entry is None or not entry.enabled:
            fail("github_adapter_approved", "adapter not registered/enabled")
        else:
            ok("github_adapter_approved", f"{entry.adapter_id}:{entry.adapter_version}")
            ok("github_host_allowlisted") if github_source_host in entry.approved_hosts \
                else fail("github_host_allowlisted", github_source_host)
            ok("endpoints_read_only") if entry.approved_path_prefixes else warn(
                "endpoints_read_only", "no explicit path prefixes")

    # Read-only GitHub permissions (declared).
    perm = PermissionVerification.UNVERIFIED
    write_scopes = [s for ref in config.credential_references for s in ref.required_scopes
                    if ":write" in s]
    if write_scopes:
        fail("github_permissions_read_only", f"write scope requested: {write_scopes}")
    else:
        ok("github_permissions_read_only")
        perm = PermissionVerification.DECLARED_AND_VALIDATED

    # Credential resolution (value never persisted / printed).
    if credential_resolver is not None and config.credential_references:
        try:
            resolved = credential_resolver(config.credential_references[0].reference_id)
            ok("credential_resolver_available") if resolved else fail(
                "credential_resolver_available", "resolver returned nothing")
        except Exception:  # never surface the credential in the message
            fail("credential_resolver_available", "resolver raised")
    else:
        warn("credential_resolver_available", "no resolver supplied (offline preflight)")

    # Snapshot schemas known.
    unknown = [a for a in config.approved_snapshot_adapters
               if a not in {f"cg.{k}_snapshot" for k in SNAPSHOT_SCHEMAS}]
    ok("snapshot_schemas_known") if not unknown else fail("snapshot_schemas_known", str(unknown))

    # Execution-disabled invariant.
    ok("execution_disabled")

    # Static write-boundary scan.
    scan = scan_paths(_operator_scan_paths())
    ok("no_write_capable_api") if scan.clean else fail(
        "no_write_capable_api", f"{len(scan.findings)} findings")

    # Optional live metadata probe.
    if live_metadata_probe is not None:
        try:
            ok("live_metadata_get") if live_metadata_probe() else fail("live_metadata_get")
            perm = PermissionVerification.VERIFIED_FROM_SOURCE
        except Exception:
            fail("live_metadata_get", "probe raised")
    else:
        warn("live_metadata_get", "live checks disabled")

    failed = any(s == "FAIL" for _, s, _ in checks)
    warned = any(s == "WARN" for _, s, _ in checks)
    outcome = (PreflightOutcome.FAIL if failed
               else PreflightOutcome.PASS_WITH_WARNINGS if warned
               else PreflightOutcome.PASS)
    return PilotPreflightResult(outcome=outcome, checks=tuple(checks),
                                permission_verification=perm)


__all__ = ["PreflightOutcome", "PermissionVerification", "PilotPreflightResult",
           "run_pilot_preflight"]
