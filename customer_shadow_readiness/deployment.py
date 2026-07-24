"""Deployment packaging + rollback/recovery (M8). Produces a reproducible, pinned, NON-ENFORCING pilot
package manifest and a rollback/recovery procedure to the frozen baseline. Deterministic, shadow-only.
No real deployment infrastructure is built (out of scope).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

from . import verify_prior_artifacts as guard

MANIFEST_VERSION = "csr_pilot_manifest_v1"
FROZEN_BASELINE_COMMIT = "ab237af"          # governed_inference_pilot frozen baseline

# component versions this pilot pins (read-only)
PINNED_COMPONENTS = {
    "execution_gate": "exec_gate_v1", "model_policy": "reconciliation_v1",
    "claim_integrity": "ci_claim_v1", "scope_integrity": "scope_hybrid_v1",
    "evidence_assurance": "ea_evidence_v1", "assertion_gate": "assertion_gate_v1",
    "action_gate_real": "action_gate_ref_v1",          # M2/M3: the REAL gate, not the shadow mapping
    "orchestrator": "gip_orch_v1", "audit": "gip_audit_v1", "contracts": "gip_contracts_v1",
    "pilot_api": "csr_pilot_api_v1", "security": "csr_security_v1", "data_controls": "csr_data_v1",
}

# pilot configuration - enforcement MUST be off
PILOT_CONFIG = {
    "enforcement": "OFF",                  # non-negotiable: shadow only
    "external_actions": "DISABLED",
    "live_provider_calls": "DISABLED",
    "execution_mode": "fixture",
    "action_gate": "real_read_only",       # real gate used for decisions, never enforcement
    "tenant_isolation": "ENABLED",
    "kill_switches": ["pilot", "tenant"],
    "data_egress": "minimized_redacted_only",
}


@dataclass
class Manifest:
    version: str
    frozen_baseline_commit: str
    components: Dict[str, str]
    config: Dict[str, Any]
    frozen_artifact_hashes: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {"version": self.version, "frozen_baseline_commit": self.frozen_baseline_commit,
                "components": self.components, "config": self.config,
                "frozen_artifact_hashes": self.frozen_artifact_hashes}


def build_manifest() -> Manifest:
    # pin the frozen artifact hashes (the exact bytes this pilot runs against)
    hashes = {rel: h[:16] for rel, h in guard.FROZEN.items()}
    return Manifest(MANIFEST_VERSION, FROZEN_BASELINE_COMMIT, dict(PINNED_COMPONENTS),
                    dict(PILOT_CONFIG), hashes)


def preflight() -> Dict[str, Any]:
    """Deployment preflight: enforcement off + all frozen artifacts intact. Fail-closed gate."""
    m = build_manifest()
    enforcement_off = m.config["enforcement"] == "OFF" and m.config["external_actions"] == "DISABLED"
    artifacts_intact = guard.verify()
    return {"enforcement_off": enforcement_off, "frozen_artifacts_intact": artifacts_intact,
            "deployable": enforcement_off and artifacts_intact}


def rollback_check() -> Dict[str, Any]:
    """Rollback to the frozen baseline is SAFE iff the baseline artifacts are byte-identical (the
    guard passes). Recovery = redeploy the frozen manifest; no data migration (shadow, minimized)."""
    intact = guard.verify()
    return {"baseline_commit": FROZEN_BASELINE_COMMIT, "baseline_intact": intact,
            "rollback_safe": intact,
            "recovery_procedure": ["engage pilot-wide kill", "verify frozen guard",
                                   "redeploy frozen manifest", "restore kill switch after validation"]}
