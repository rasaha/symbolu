"""Clean-room profile registry (declarative).

Written from the published CER V0.2 profile specifications (scale.v1, rollout.v1)
and, for V0.3, the database.mutation.v1 profile specification
(CER_DATABASE_MUTATION_PROFILE.md). Each entry is DATA describing how a profile's
actuation maps into the universal envelope's identity-bearing fields — a
deliberately different shape from the reference's one-module-per-profile design.

No import of the reference profiles, envelope, or ActionGate code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from .errors import ValueFormatError


@dataclass(frozen=True)
class CleanRoomProfile:
    profile_id: str
    operation: str                    # expected actuation.operation
    server_id: str                    # tool.server_id
    tool_name: str                    # tool.tool_name (the domain separator)
    freshness_source: str             # default state_freshness.source
    required: Tuple[str, ...]
    optional: Tuple[str, ...]
    prohibited: Tuple[str, ...]
    target_id: Callable[[Dict[str, Any]], str]
    arguments: Callable[[Dict[str, Any]], Dict[str, str]]
    rollback_plan: Callable[[Dict[str, Any]], Optional[Dict[str, str]]] = \
        field(default=lambda a: None)
    validate_extra: Callable[[Dict[str, Any]], None] = field(default=lambda a: None)
    # database-domain only: fields that must never carry secret material
    secret_guarded: Tuple[str, ...] = ()


_REGISTRY: Dict[str, CleanRoomProfile] = {}


def register(p: CleanRoomProfile) -> CleanRoomProfile:
    _REGISTRY[p.profile_id] = p
    return p


def get(profile_id: str) -> Optional[CleanRoomProfile]:
    return _REGISTRY.get(profile_id)


def known() -> Tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


# ----------------------------------------------------------------------------
# kubernetes.scale.v1
# ----------------------------------------------------------------------------
def _k8s_target(a: Dict[str, Any]) -> str:
    t = a["target"]
    return f"{t['namespace']}/{t['deployment']}"


def _scale_validate(a: Dict[str, Any]) -> None:
    t = a["target"]
    for f in ("cluster", "namespace", "deployment"):
        if f not in t:
            raise ValueFormatError(f"scale target missing {f}", path=f"actuation.target.{f}")
    st = a["requested_state_transition"]
    r = st.get("replicas", {}) if isinstance(st, dict) else {}
    if "from" not in r or "to" not in r:
        raise ValueFormatError("scale requested_state_transition.replicas{from,to} required",
                               path="actuation.requested_state_transition")
    if "replicas" not in a["arguments"]:
        raise ValueFormatError("scale arguments.replicas required", path="actuation.arguments")


register(CleanRoomProfile(
    profile_id="kubernetes.scale.v1", operation="DEPLOY", server_id="kubernetes",
    tool_name="scale", freshness_source="kubernetes",
    required=("operation", "target", "arguments", "requested_state_transition", "reversibility"),
    optional=(),
    prohibited=("image_digest", "current_manifest_digest", "rollout_strategy",
                "max_surge", "max_unavailable", "timeout_s", "rollback_ref"),
    target_id=_k8s_target,
    arguments=lambda a: dict(a["arguments"]),
    validate_extra=_scale_validate,
))


# ----------------------------------------------------------------------------
# kubernetes.rollout.v1
# ----------------------------------------------------------------------------
_DIGEST_LEN = 71  # "sha256:" + 64 hex


def _rollout_validate(a: Dict[str, Any]) -> None:
    t = a["target"]
    for f in ("cluster", "namespace", "deployment"):
        if f not in t:
            raise ValueFormatError(f"rollout target missing {f}", path=f"actuation.target.{f}")
    for f in ("image_digest", "current_manifest_digest"):
        v = a[f]
        if not (isinstance(v, str) and v.startswith("sha256:") and len(v) == _DIGEST_LEN):
            raise ValueFormatError(f"rollout {f} must be sha256:<64hex>", path=f"actuation.{f}")
    if a["rollout_strategy"] not in ("RollingUpdate", "Recreate"):
        raise ValueFormatError("rollout_strategy must be RollingUpdate|Recreate",
                               path="actuation.rollout_strategy")
    for f in ("max_surge", "max_unavailable", "timeout_s"):
        if not str(a[f]).lstrip("-").isdigit():
            raise ValueFormatError(f"rollout {f} must be an integer string",
                                   path=f"actuation.{f}")


def _rollout_arguments(a: Dict[str, Any]) -> Dict[str, str]:
    return {
        "image_digest": a["image_digest"],
        "current_manifest_digest": a["current_manifest_digest"],
        "rollout_strategy": a["rollout_strategy"],
        "max_surge": str(a["max_surge"]),
        "max_unavailable": str(a["max_unavailable"]),
        "timeout_s": str(a["timeout_s"]),
    }


register(CleanRoomProfile(
    profile_id="kubernetes.rollout.v1", operation="DEPLOY", server_id="kubernetes",
    tool_name="rollout", freshness_source="kubernetes",
    required=("operation", "target", "image_digest", "current_manifest_digest",
              "rollout_strategy", "max_surge", "max_unavailable", "timeout_s", "reversibility"),
    optional=("rollback_ref",),
    prohibited=("requested_state_transition", "replicas"),
    target_id=_k8s_target,
    arguments=_rollout_arguments,
    rollback_plan=lambda a: {"ref": a["rollback_ref"]} if a.get("rollback_ref") else None,
    validate_extra=_rollout_validate,
))
