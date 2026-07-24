"""Incident response (M7). Severity taxonomy, detection -> classification -> response mapping, and a
runbook. Ties detection signals (observability alerts, fault conditions) to the kill switches. Shadow-
only. Deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from . import killswitch

# severity taxonomy
SEV = {"SEV1": "safety/isolation breach", "SEV2": "governance degradation",
       "SEV3": "integration/availability", "SEV4": "informational"}

# signal -> (severity, response)
SIGNAL_MAP = {
    "SEC.CROSS_TENANT_DENIED": ("SEV1", "trip_tenant"),
    "SEC.CROSS_TENANT_CASE": ("SEV1", "trip_tenant"),
    "unsafe_action_escape": ("SEV1", "trip_pilot"),
    "ALERT.HIGH_ALLOW_RATE": ("SEV2", "page_oncall"),
    "ALERT.HIGH_CONTRACT_ERROR": ("SEV3", "page_oncall"),
    "ALERT.PIPELINE_ERROR": ("SEV3", "page_oncall"),
    "replay_nondeterminism": ("SEV2", "freeze_and_investigate"),
}


@dataclass
class Incident:
    signal: str
    severity: str
    response: str
    tenant: str = ""
    action_taken: str = ""


def handle(signal: str, tenant: str = "") -> Incident:
    sev, resp = SIGNAL_MAP.get(signal, ("SEV4", "log"))
    taken = "logged"
    if resp == "trip_tenant" and tenant:
        killswitch.trip_tenant(tenant); taken = f"tenant {tenant} disabled"
    elif resp == "trip_pilot":
        killswitch.trip_pilot(); taken = "pilot-wide kill engaged"
    elif resp in ("page_oncall", "freeze_and_investigate"):
        taken = resp
    return Incident(signal=signal, severity=sev, response=resp, tenant=tenant, action_taken=taken)
