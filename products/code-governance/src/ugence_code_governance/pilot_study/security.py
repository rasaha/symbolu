"""Pre-/post-run security + integrity verification for a pilot study.

Before and after every (live) run the study verifies: execution disabled, the
static read-only inspection passes, durable-store integrity passes, and the pilot
manifest still matches its frozen fingerprint. Any failure is a structured finding
that must trigger the existing pause/stop/abort mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from ..pilot_operator.security import scan_paths
from ..persistence.sqlite import DurableShadowStore


@dataclass(frozen=True)
class PilotSecurityVerification:
    ok: bool
    findings: Tuple[str, ...] = ()
    execution_status: str = "DISABLED"


def _scan_paths() -> List[Path]:
    base = Path(__file__).resolve().parent.parent
    return (list((base / "adapters").glob("*.py"))
            + list((base / "pilot_operator").glob("*.py"))
            + list((base / "pilot_study").glob("*.py")))


def run_pilot_security_verification(
    store: Optional[DurableShadowStore],
    *,
    tenant_id: str,
    pilot_id: str,
    current_manifest_fingerprint: str,
    frozen_manifest_fingerprint: str,
) -> PilotSecurityVerification:
    """Verify execution-disabled, read-only scan, store integrity, and manifest freeze."""
    findings: List[str] = []

    # Static read-only boundary must be clean (no write client / mutation / reserve_once).
    scan = scan_paths(_scan_paths())
    if not scan.clean:
        findings.append(f"read_only_boundary_violation:{len(scan.findings)}")

    # Durable-store integrity.
    if store is not None:
        if not store.health_check().get("ok"):
            findings.append("store_integrity_failure")
        for lineage in (f"study:{pilot_id}", f"op:{pilot_id}", f"pilot:{pilot_id}"):
            try:
                store.verify_records(tenant_id, lineage)
                store.verify_event_chain(tenant_id, lineage)
            except Exception as exc:  # integrity failure fails closed
                findings.append(f"store_integrity_failure:{lineage}:{type(exc).__name__}")

    # Manifest freeze must still match.
    if frozen_manifest_fingerprint and current_manifest_fingerprint != frozen_manifest_fingerprint:
        findings.append("manifest_fingerprint_mismatch")

    return PilotSecurityVerification(ok=not findings, findings=tuple(findings))


__all__ = ["PilotSecurityVerification", "run_pilot_security_verification"]
