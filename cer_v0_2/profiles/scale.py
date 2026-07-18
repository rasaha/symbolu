"""Profile ``kubernetes.scale.v1`` — identity-equivalent to CER V0.1's scale.

Its envelope projection matches V0.1 so the SAME actuation yields the SAME action
digest across CER V0.1 and V0.2 (verified by the compatibility tests).
"""
from __future__ import annotations

from typing import Any, Dict

from . import _common
from .base import CERValidationError, check_fields

PROFILE_ID = "kubernetes.scale.v1"
ACTIONGATE_TOOL = "scale"
ACTIONGATE_OPERATION = "DEPLOY"

REQUIRED_ACTUATION = ("operation", "target", "arguments",
                      "requested_state_transition", "reversibility")
OPTIONAL_ACTUATION = ()
# rollout-only fields are PROHIBITED here (guards against profile downgrade)
PROHIBITED_ACTUATION = ("image_digest", "current_manifest_digest", "rollout_strategy",
                        "max_surge", "max_unavailable", "timeout_s", "rollback_ref")


def validate_actuation(actuation: Dict[str, Any]) -> None:
    check_fields(actuation, REQUIRED_ACTUATION, OPTIONAL_ACTUATION,
                 PROHIBITED_ACTUATION, PROFILE_ID)
    tgt = actuation["target"]
    for f in ("cluster", "namespace", "deployment"):
        if f not in tgt:
            raise CERValidationError(f"scale.v1 target missing {f}")
    st = actuation["requested_state_transition"]
    if "replicas" not in st or "from" not in st["replicas"] or "to" not in st["replicas"]:
        raise CERValidationError("scale.v1 requested_state_transition.replicas{from,to} required")
    if "replicas" not in actuation["arguments"]:
        raise CERValidationError("scale.v1 arguments.replicas required")


def to_envelope(cer: Dict[str, Any]) -> Dict[str, Any]:
    act = cer["actuation"]
    tgt = act["target"]
    target_id = f"{tgt['namespace']}/{tgt['deployment']}"
    return _common.build_envelope(
        cer, tool_name=ACTIONGATE_TOOL, operation=act["operation"],
        target_id=target_id, arguments=act["arguments"], reversibility=act["reversibility"])


def to_cloud_world(cer: Dict[str, Any]):
    return _common.live_cloud_world(cer)


def to_cloud_candidate(cer: Dict[str, Any]):
    from symbolu_robotics.autonomous_control_plane.cloud.envelopes import (
        CloudActionCandidate, CloudOperation,
    )
    act = cer["actuation"]
    tgt = act["target"]
    st = act["requested_state_transition"]["replicas"]
    return CloudActionCandidate(
        candidate_id="cand:scale", operation=CloudOperation.SCALE,
        namespace=tgt["namespace"], deployment=tgt["deployment"],
        current_replicas=int(st["from"]), desired_replicas=int(st["to"]),
        manifest_digest="", rollback_ref=cer["state_binding"].get("rollback_ref", ""),
        rollout_strategy="RollingUpdate", max_unavailable=0, max_surge=1, timeout_s=60.0,
        origin_state_version=_common.observed_world_version(cer),
    )
