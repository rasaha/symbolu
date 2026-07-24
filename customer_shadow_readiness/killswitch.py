"""Kill switches (M6 minimal; operational detail in M7). Pilot-wide and tenant-level. Fail closed: a
tripped switch makes the pilot API refuse new work. In-memory, deterministic, shadow-only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set

_PILOT_ENABLED = {"on": True}
_TENANT_DISABLED: Set[str] = set()


@dataclass
class KillState:
    active: bool
    reason: str = ""


def check(tenant: str) -> KillState:
    if not _PILOT_ENABLED["on"]:
        return KillState(False, "PILOT_KILLED")
    if tenant in _TENANT_DISABLED:
        return KillState(False, f"TENANT_KILLED:{tenant}")
    return KillState(True)


def trip_pilot() -> None:
    _PILOT_ENABLED["on"] = False


def restore_pilot() -> None:
    _PILOT_ENABLED["on"] = True


def trip_tenant(tenant: str) -> None:
    _TENANT_DISABLED.add(tenant)


def restore_tenant(tenant: str) -> None:
    _TENANT_DISABLED.discard(tenant)
