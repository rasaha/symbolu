"""Phase 6-7 - Read-only orchestrator wrapper + audit extension for natural artifacts.

Runs each natural artifact through the FROZEN governed-inference orchestrator (read-only) and produces
an EXTENDED audit record that adds, without modifying the frozen trace:

  - the native ActionGate decision (all six outcomes preserved, zero loss) for any derived action,
  - the derivation provenance (which governance inputs were derived and how),
  - the blinded ground-truth label for scoring,
  - the frozen trace's own final disposition, reason codes, and replay signature.

Non-enforcing (`enforced=False` by construction). Deterministic. Re-implements no decision logic:
the frozen orchestrator decides the pipeline; the native contract decides the action; this wrapper
only composes and records.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from governed_inference_pilot import orchestrator as gip_orch

from bounded_shadow_pilot import actiongate_contract as ac
from bounded_shadow_pilot import case_builder

WRAPPER_VERSION = "natural_orchestrator_wrapper_v1"


@dataclass
class ExtendedAudit:
    artifact_id: str
    use_case: str
    source_kind: str
    source_path: str
    # frozen pipeline result (read-only, unmodified)
    final_shadow_disposition: str
    stage_dispositions: List[Dict[str, str]]
    reason_codes: List[str]
    replay_signature: str
    human_review_state: str
    # native ActionGate extension (zero loss)
    native_action_outcome: Optional[str] = None
    native_action_is_native: Optional[bool] = None
    native_action_blocks: Optional[bool] = None
    native_action_permits: Optional[bool] = None
    native_action_dispositive_rules: List[str] = field(default_factory=list)
    native_action_hash: str = ""
    native_policy_hash: str = ""
    # derivation provenance + ground truth
    derivation_version: str = ""
    derived_risk_tier: str = ""
    derived_evidence_state: str = ""
    action_derived: bool = False
    gt_expected_class: str = ""
    # invariants
    enforced: bool = False
    wrapper_version: str = WRAPPER_VERSION


def _stage_rows(trace) -> List[Dict[str, str]]:
    return [{"stage": e.stage, "disposition": e.disposition, "shadow_outcome": e.shadow_outcome}
            for e in trace.events]


def _all_reason_codes(trace) -> List[str]:
    codes: List[str] = []
    for e in trace.events:
        codes.extend(e.reason_codes)
    return codes


def run_natural(artifact: Dict[str, Any], gt: Dict[str, Any],
                config: str = gip_orch.DEFAULT_CONFIG) -> ExtendedAudit:
    """Run one natural artifact end-to-end and return the extended audit record."""
    case = case_builder.build_case(artifact, gt)

    # 1. frozen orchestrator, read-only
    trace = gip_orch.run_case(case, config=config)

    # 2. native ActionGate on any derived action (zero-loss outcome preserved)
    action = case.get("action_proposal")
    nad = ac.evaluate(action)

    return ExtendedAudit(
        artifact_id=artifact["artifact_id"],
        use_case=artifact["use_case"],
        source_kind=artifact["source_kind"],
        source_path=artifact["source_path"],
        final_shadow_disposition=trace.final_shadow_disposition,
        stage_dispositions=_stage_rows(trace),
        reason_codes=_all_reason_codes(trace),
        replay_signature=trace.replay_signature,
        human_review_state=trace.human_review_state,
        native_action_outcome=(nad.native_outcome if nad else None),
        native_action_is_native=(nad.is_native if nad else None),
        native_action_blocks=(nad.blocks if nad else None),
        native_action_permits=(nad.permits if nad else None),
        native_action_dispositive_rules=(nad.dispositive_rules if nad else []),
        native_action_hash=(nad.action_hash if nad else ""),
        native_policy_hash=(nad.policy_hash if nad else ""),
        derivation_version=case["derivation_version"],
        derived_risk_tier=case["risk_tier"],
        derived_evidence_state=case["evidence_steer"]["evidence_state"],
        action_derived=action is not None,
        gt_expected_class=gt.get("gt_expected_class", ""),
        enforced=False,
    )


def replay_signature(rec: ExtendedAudit) -> str:
    """Deterministic signature over the decision-bearing content of the extended record (excludes the
    frozen replay_signature to make double-recording detectable)."""
    payload = {
        "artifact_id": rec.artifact_id,
        "final": rec.final_shadow_disposition,
        "stages": rec.stage_dispositions,
        "reason_codes": rec.reason_codes,
        "native_action_outcome": rec.native_action_outcome,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def run_batch(artifacts: List[Dict[str, Any]], gts: Dict[str, Dict[str, Any]],
              config: str = gip_orch.DEFAULT_CONFIG) -> List[ExtendedAudit]:
    """Run a batch. `gts` maps artifact_id -> ground-truth label. Deterministic order (by id)."""
    out: List[ExtendedAudit] = []
    for a in sorted(artifacts, key=lambda x: x["artifact_id"]):
        gt = gts.get(a["artifact_id"], {})
        out.append(run_natural(a, gt, config=config))
    return out
