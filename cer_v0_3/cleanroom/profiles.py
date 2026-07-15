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
    # runs BEFORE field-presence/unknown-field checks (e.g. the secret-material guard,
    # so a secret-bearing key is reported as secret material, not as an unknown field)
    pre_check: Callable[[Dict[str, Any]], None] = field(default=lambda a: None)


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


# ----------------------------------------------------------------------------
# database.mutation.v1  (V0.3 — written from CER_DATABASE_MUTATION_PROFILE.md)
# ----------------------------------------------------------------------------
import re as _re  # noqa: E402  (kept local to the DB profile)

from .errors import SecretMaterialError  # noqa: E402

_DB_SQL_OPS = ("INSERT", "UPDATE", "DDL")
_DB_ISOLATION = ("READ_COMMITTED", "REPEATABLE_READ", "SERIALIZABLE")
_DB_TXN_MODES = ("in_transaction",)
_DB_SECRET_KEYS = {"password", "passwd", "secret", "dsn", "connection_string",
                   "conn_string", "credentials", "credential", "token", "api_key",
                   "private_key", "statement", "sql", "sql_text", "query_text"}
_DB_SECRET_VALUE = _re.compile(
    r"(password\s*=)|(://[^/\s:]+:[^/\s@]+@)|(-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    _re.IGNORECASE)


def _db_is_digest(v: Any) -> bool:
    return isinstance(v, str) and v.startswith("sha256:") and len(v) == 71


def _db_walk(value: Any):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k, v
            yield from _db_walk(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _db_walk(v)


def _db_secret_scan(a: Dict[str, Any]) -> None:
    """Secret-material guard — runs BEFORE unknown-field checks (fail closed)."""
    for k, v in _db_walk(a):
        if isinstance(k, str) and k.lower() in _DB_SECRET_KEYS:
            raise SecretMaterialError(f"secret-bearing key {k!r} in database actuation",
                                      path=f"actuation.{k}")
        if isinstance(v, str) and _DB_SECRET_VALUE.search(v):
            raise SecretMaterialError(f"embedded credential material under {k!r}",
                                      path="actuation")


def _db_validate(a: Dict[str, Any]) -> None:
    _db_secret_scan(a)
    t = a["target"]
    for f in ("connection_ref", "schema", "table"):
        if not isinstance(t.get(f), str) or not t.get(f):
            raise ValueFormatError(f"database target missing/invalid {f}",
                                   path=f"actuation.target.{f}")
    if a["sql_operation"] not in _DB_SQL_OPS:
        raise ValueFormatError(f"unsupported sql_operation {a['sql_operation']!r}",
                               path="actuation.sql_operation")
    if not _db_is_digest(a["statement_digest"]):
        raise ValueFormatError("statement_digest must be sha256:<64hex>",
                               path="actuation.statement_digest")
    for opt in ("parameters_digest", "predicate_digest"):
        if opt in a and not _db_is_digest(a[opt]):
            raise ValueFormatError(f"{opt} must be sha256:<64hex>", path=f"actuation.{opt}")
    scope = a["affected_scope"]
    if not isinstance(scope, dict) or "estimated_rows" not in scope or "unbounded" not in scope:
        raise ValueFormatError("affected_scope{estimated_rows,unbounded} required",
                               path="actuation.affected_scope")
    if not str(scope["estimated_rows"]).isdigit():
        raise ValueFormatError("affected_scope.estimated_rows must be integer string",
                               path="actuation.affected_scope.estimated_rows")
    if not isinstance(scope["unbounded"], bool):
        raise ValueFormatError("affected_scope.unbounded must be boolean",
                               path="actuation.affected_scope.unbounded")
    txn = a["transaction"]
    if not isinstance(txn, dict) or txn.get("mode") not in _DB_TXN_MODES:
        raise ValueFormatError(f"transaction.mode must be one of {_DB_TXN_MODES}",
                               path="actuation.transaction.mode")
    if txn.get("isolation") not in _DB_ISOLATION:
        raise ValueFormatError(f"transaction.isolation must be one of {_DB_ISOLATION}",
                               path="actuation.transaction.isolation")
    if not isinstance(a["expected_row_version"], str) or not a["expected_row_version"]:
        raise ValueFormatError("expected_row_version required (string)",
                               path="actuation.expected_row_version")


def _db_target(a: Dict[str, Any]) -> str:
    t = a["target"]
    return f"{t['connection_ref']}/{t['schema']}/{t['table']}"


def _db_arguments(a: Dict[str, Any]) -> Dict[str, Any]:
    scope = a["affected_scope"]
    txn = a["transaction"]
    args: Dict[str, Any] = {
        "sql_operation": a["sql_operation"],
        "statement_digest": a["statement_digest"],
        "affected_count": str(scope["estimated_rows"]),
        "unbounded": bool(scope["unbounded"]),
        "transaction_mode": txn["mode"],
        "isolation": txn["isolation"],
        "expected_row_version": a["expected_row_version"],
    }
    if "parameters_digest" in a:
        args["parameters_digest"] = a["parameters_digest"]
    if "predicate_digest" in a:
        args["predicate_digest"] = a["predicate_digest"]
    return args


register(CleanRoomProfile(
    profile_id="database.mutation.v1", operation="DB_MUTATION", server_id="database",
    tool_name="mutation", freshness_source="database",
    required=("operation", "target", "sql_operation", "statement_digest",
              "affected_scope", "transaction", "expected_row_version", "reversibility"),
    optional=("parameters_digest", "predicate_digest", "compensation_ref"),
    prohibited=("replicas", "image_digest", "current_manifest_digest", "rollout_strategy",
                "requested_state_transition", "max_surge", "max_unavailable", "timeout_s",
                "rollback_ref"),
    target_id=_db_target,
    arguments=_db_arguments,
    rollback_plan=lambda a: {"ref": a["compensation_ref"]} if a.get("compensation_ref") else None,
    validate_extra=_db_validate,
    pre_check=_db_secret_scan,
))
