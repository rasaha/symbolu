"""Restart-safe pilot-operator recovery.

On reopen the operator validates the store, verifies integrity, loads the latest
lifecycle record + kill-switch state, identifies the last committed evaluation, and
returns a structured result. It performs **no** GitHub call automatically and never
auto-resumes an ACTIVE pilot — continuation requires an explicit operator action.
A configuration fingerprint mismatch blocks resume without rewriting history.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

from ..persistence.schema import RecordType
from ..persistence.sqlite import DurableShadowStore
from .config import PilotDeploymentConfig
from .lifecycle import PilotLifecycleStatus
from .persistence import OperatorDurableWriter


class PilotRecoveryStatus(str, Enum):
    RECOVERED_READY = "RECOVERED_READY"
    RECOVERED_ACTIVE_REQUIRES_CONFIRMATION = "RECOVERED_ACTIVE_REQUIRES_CONFIRMATION"
    RECOVERED_PAUSED = "RECOVERED_PAUSED"
    RECOVERED_COMPLETED = "RECOVERED_COMPLETED"
    RECOVERED_ABORTED = "RECOVERED_ABORTED"
    RECOVERED_INTEGRITY_FAILURE = "RECOVERED_INTEGRITY_FAILURE"
    CONFIGURATION_MISMATCH = "CONFIGURATION_MISMATCH"
    STORE_INTEGRITY_FAILURE = "STORE_INTEGRITY_FAILURE"
    NO_PRIOR_RUN = "NO_PRIOR_RUN"


@dataclass(frozen=True)
class PilotRecoveryResult:
    status: PilotRecoveryStatus
    pilot_id: str
    tenant_id: str
    last_lifecycle_status: str = ""
    last_run_id: str = ""
    last_evaluation_ref: str = ""
    kill_switch_active: bool = False
    requires_explicit_action: bool = False
    issues: Tuple[str, ...] = ()
    execution_status: str = "DISABLED"


_STATUS_MAP = {
    PilotLifecycleStatus.READY.value: PilotRecoveryStatus.RECOVERED_READY,
    PilotLifecycleStatus.ACTIVE.value: PilotRecoveryStatus.RECOVERED_ACTIVE_REQUIRES_CONFIRMATION,
    PilotLifecycleStatus.PAUSED.value: PilotRecoveryStatus.RECOVERED_PAUSED,
    PilotLifecycleStatus.STOPPING.value: PilotRecoveryStatus.RECOVERED_ACTIVE_REQUIRES_CONFIRMATION,
    PilotLifecycleStatus.COMPLETED.value: PilotRecoveryStatus.RECOVERED_COMPLETED,
    PilotLifecycleStatus.ABORTED.value: PilotRecoveryStatus.RECOVERED_ABORTED,
    PilotLifecycleStatus.INTEGRITY_FAILURE.value: PilotRecoveryStatus.RECOVERED_INTEGRITY_FAILURE,
}


def recover_pilot(
    store: DurableShadowStore,
    config: PilotDeploymentConfig,
) -> PilotRecoveryResult:
    """Recover a pilot from the durable store (no external call, no auto-resume)."""
    writer = OperatorDurableWriter(store)
    tenant, pilot = config.tenant_id, config.pilot_id

    # Store integrity.
    health = store.health_check()
    if not health.get("ok"):
        return PilotRecoveryResult(PilotRecoveryStatus.STORE_INTEGRITY_FAILURE, pilot, tenant,
                                   issues=("durable store integrity failed",))
    try:
        store.verify_event_chain(tenant, f"op:{pilot}")
        store.verify_records(tenant, f"op:{pilot}")
    except Exception as exc:
        return PilotRecoveryResult(PilotRecoveryStatus.STORE_INTEGRITY_FAILURE, pilot, tenant,
                                   issues=(str(exc),))

    run = writer.latest_of_type(tenant, pilot, RecordType.PILOT_RUN_RECORD)
    if run is None:
        return PilotRecoveryResult(PilotRecoveryStatus.NO_PRIOR_RUN, pilot, tenant)

    payload = run.canonical_payload
    # Config drift: persisted config fingerprint must match the supplied config.
    persisted_fp = payload.get("config_fingerprint", "")
    if persisted_fp and persisted_fp != config.fingerprint:
        return PilotRecoveryResult(
            PilotRecoveryStatus.CONFIGURATION_MISMATCH, pilot, tenant,
            last_lifecycle_status=payload.get("status", ""),
            last_run_id=payload.get("run_id", ""),
            issues=("supplied config fingerprint does not match persisted run",))

    kill = writer.latest_of_type(tenant, pilot, RecordType.PILOT_KILL_SWITCH_STATE)
    kill_active = bool(kill and kill.canonical_payload.get("active"))

    # The authoritative current lifecycle status is the newest lifecycle *event*
    # (run-record snapshots are content-deduped and can collapse identical states).
    last_event = writer.latest_of_type(tenant, pilot, RecordType.PILOT_LIFECYCLE_EVENT)
    status = (last_event.canonical_payload.get("to_status", "") if last_event
              else payload.get("status", ""))
    rstatus = _STATUS_MAP.get(status, PilotRecoveryStatus.NO_PRIOR_RUN)
    requires_action = rstatus in (
        PilotRecoveryStatus.RECOVERED_ACTIVE_REQUIRES_CONFIRMATION,
        PilotRecoveryStatus.RECOVERED_PAUSED)
    return PilotRecoveryResult(
        status=rstatus, pilot_id=pilot, tenant_id=tenant, last_lifecycle_status=status,
        last_run_id=payload.get("run_id", ""),
        last_evaluation_ref=payload.get("last_evaluation_ref", ""),
        kill_switch_active=kill_active, requires_explicit_action=requires_action)


__all__ = ["PilotRecoveryStatus", "PilotRecoveryResult", "recover_pilot"]
