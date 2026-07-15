"""Profile ``kubernetes.rollout.v1`` — a materially distinct actuation.

Identity-bearing fields absent from scale: image/manifest digest, rollout strategy,
maxSurge, maxUnavailable, rollback reference, timeout. Domain-separated from scale
by ``tool.tool_name="rollout"`` and a disjoint argument set, so no digest collision
with scale is possible even where field names overlap (e.g. ``target``).
"""
from __future__ import annotations

from typing import Any, Dict

from . import _common
from .base import CERValidationError, check_fields

PROFILE_ID = "kubernetes.rollout.v1"
ACTIONGATE_TOOL = "rollout"
ACTIONGATE_OPERATION = "DEPLOY"

REQUIRED_ACTUATION = ("operation", "target", "image_digest", "current_manifest_digest",
                      "rollout_strategy", "max_surge", "max_unavailable", "timeout_s",
                      "reversibility")
OPTIONAL_ACTUATION = ("rollback_ref",)
# scale-only fields are PROHIBITED here (guards against profile downgrade/confusion)
PROHIBITED_ACTUATION = ("requested_state_transition", "replicas")

_DIGEST_FIELDS = ("image_digest", "current_manifest_digest")


def validate_actuation(actuation: Dict[str, Any]) -> None:
    check_fields(actuation, REQUIRED_ACTUATION, OPTIONAL_ACTUATION,
                 PROHIBITED_ACTUATION, PROFILE_ID)
    tgt = actuation["target"]
    for f in ("cluster", "namespace", "deployment"):
        if f not in tgt:
            raise CERValidationError(f"rollout.v1 target missing {f}")
    for f in _DIGEST_FIELDS:
        v = actuation[f]
        if not (isinstance(v, str) and v.startswith("sha256:") and len(v) == 71):
            raise CERValidationError(f"rollout.v1 {f} must be a sha256:<64hex> digest")
    if actuation["rollout_strategy"] not in ("RollingUpdate", "Recreate"):
        raise CERValidationError("rollout.v1 rollout_strategy must be RollingUpdate|Recreate")
    # units: max_surge/max_unavailable/timeout_s are typed-string integers
    for f in ("max_surge", "max_unavailable", "timeout_s"):
        if not str(actuation[f]).lstrip("-").isdigit():
            raise CERValidationError(f"rollout.v1 {f} must be an integer string")


def _arguments(actuation: Dict[str, Any]) -> Dict[str, str]:
    """Normalized, identity-bearing rollout arguments (typed strings; sorted by key
    at canonicalization). Units: replicas/surge counts are integer strings; timeout
    in whole seconds."""
    return {
        "image_digest": actuation["image_digest"],
        "current_manifest_digest": actuation["current_manifest_digest"],
        "rollout_strategy": actuation["rollout_strategy"],
        "max_surge": str(actuation["max_surge"]),
        "max_unavailable": str(actuation["max_unavailable"]),
        "timeout_s": str(actuation["timeout_s"]),
    }


def to_envelope(cer: Dict[str, Any]) -> Dict[str, Any]:
    act = cer["actuation"]
    tgt = act["target"]
    target_id = f"{tgt['namespace']}/{tgt['deployment']}"
    # rollback reference is identity-bearing via ActionGate's rollback_plan projection
    rollback_plan = {"ref": act["rollback_ref"]} if act.get("rollback_ref") else None
    return _common.build_envelope(
        cer, tool_name=ACTIONGATE_TOOL, operation=act["operation"],
        target_id=target_id, arguments=_arguments(act), reversibility=act["reversibility"],
        rollback_plan=rollback_plan)


def to_cloud_world(cer: Dict[str, Any]):
    return _common.live_cloud_world(cer)


def to_cloud_candidate(cer: Dict[str, Any]):
    from symbolu_robotics.autonomous_control_plane.cloud.envelopes import (
        CloudActionCandidate, CloudOperation,
    )
    act = cer["actuation"]
    tgt = act["target"]
    op = cer["state_binding"]["operational"]
    replicas = int(op["current_replicas"])  # rollout does not change replica count
    return CloudActionCandidate(
        candidate_id="cand:rollout", operation=CloudOperation.ROLLOUT,
        namespace=tgt["namespace"], deployment=tgt["deployment"],
        current_replicas=replicas, desired_replicas=replicas,
        manifest_digest=act["image_digest"],
        rollback_ref=act.get("rollback_ref", ""),
        rollout_strategy=act["rollout_strategy"],
        max_unavailable=int(act["max_unavailable"]), max_surge=int(act["max_surge"]),
        timeout_s=float(act["timeout_s"]),
        origin_state_version=_common.observed_world_version(cer),
    )
