"""Profile ``database.mutation.v1`` — a materially non-Kubernetes actuation.

Governs a bounded, transactional data mutation (INSERT / UPDATE / DDL) against a
relational store. Identity is over the *statement against stored data*, expressed
without any raw SQL or credentials:

  * connection identity (non-secret logical ref), schema, table;
  * semantic SQL operation vocabulary {INSERT, UPDATE, DDL};
  * normalized statement digest (+ optional parameter/predicate digest);
  * affected-row scope bound (estimated rows + unbounded flag);
  * transaction mode + isolation requirement;
  * expected row-version (optimistic concurrency / state binding);
  * optional compensation reference (identity-bearing when present).

Maps directly onto the frozen ActionGate operation ``DB_MUTATION`` (rule R7):
FORBID ``unbounded``; REQUIRE_SIMULATION MEDIUM; MAX_SCOPE ``affected_count`` <=
10000; ALLOW_WITH_CONSTRAINTS ``in_transaction``. No ActionGate change is needed.

Domain-separated from the Kubernetes profiles by ``tool.server_id="database"`` and
``tool.tool_name="mutation"`` (both inside the hashed payload) and a disjoint
argument set — no digest collision with scale/rollout is possible.
"""
from __future__ import annotations

from typing import Any, Dict

from . import _envelope
from .base import CERValidationError, assert_no_secret_material, check_fields

PROFILE_ID = "database.mutation.v1"
ACTIONGATE_TOOL = "mutation"
ACTIONGATE_SERVER = "database"
ACTIONGATE_OPERATION = "DB_MUTATION"
FRESHNESS_SOURCE = "database"

# Semantic vocabulary for THIS profile. DELETE is deliberately excluded (it maps to
# the stricter DB_DELETE / R3 class and is reserved for a future database.delete.v1).
SQL_OPERATIONS = ("INSERT", "UPDATE", "DDL")
ISOLATION_LEVELS = ("READ_COMMITTED", "REPEATABLE_READ", "SERIALIZABLE")
TXN_MODES = ("in_transaction",)

REQUIRED_ACTUATION = ("operation", "target", "sql_operation", "statement_digest",
                      "affected_scope", "transaction", "expected_row_version",
                      "reversibility")
OPTIONAL_ACTUATION = ("parameters_digest", "predicate_digest", "compensation_ref")
# Kubernetes-only fields are prohibited here (guards against profile downgrade).
PROHIBITED_ACTUATION = ("replicas", "image_digest", "current_manifest_digest",
                        "rollout_strategy", "requested_state_transition",
                        "max_surge", "max_unavailable", "timeout_s", "rollback_ref")

_DIGEST_LEN = 71  # "sha256:" + 64 hex


def _is_digest(v: Any) -> bool:
    return isinstance(v, str) and v.startswith("sha256:") and len(v) == _DIGEST_LEN


def validate_actuation(actuation: Dict[str, Any]) -> None:
    # secret guard FIRST: a secret-bearing key must be reported as secret material,
    # not merely as an unknown field.
    assert_no_secret_material(actuation, PROFILE_ID)
    check_fields(actuation, REQUIRED_ACTUATION, OPTIONAL_ACTUATION,
                 PROHIBITED_ACTUATION, PROFILE_ID)

    tgt = actuation["target"]
    for f in ("connection_ref", "schema", "table"):
        if f not in tgt or not isinstance(tgt[f], str) or not tgt[f]:
            raise CERValidationError(f"database.mutation.v1 target missing/invalid {f}")

    if actuation["sql_operation"] not in SQL_OPERATIONS:
        raise CERValidationError(
            f"database.mutation.v1 unsupported sql_operation "
            f"{actuation['sql_operation']!r} (allowed: {SQL_OPERATIONS})")

    if not _is_digest(actuation["statement_digest"]):
        raise CERValidationError("database.mutation.v1 statement_digest must be sha256:<64hex>")
    for opt in ("parameters_digest", "predicate_digest"):
        if opt in actuation and not _is_digest(actuation[opt]):
            raise CERValidationError(f"database.mutation.v1 {opt} must be sha256:<64hex>")

    scope = actuation["affected_scope"]
    if not isinstance(scope, dict) or "estimated_rows" not in scope or "unbounded" not in scope:
        raise CERValidationError(
            "database.mutation.v1 affected_scope{estimated_rows,unbounded} required")
    if not str(scope["estimated_rows"]).isdigit():
        raise CERValidationError("database.mutation.v1 affected_scope.estimated_rows "
                                 "must be a non-negative integer string")
    if not isinstance(scope["unbounded"], bool):
        raise CERValidationError("database.mutation.v1 affected_scope.unbounded must be boolean")

    txn = actuation["transaction"]
    if not isinstance(txn, dict) or txn.get("mode") not in TXN_MODES:
        raise CERValidationError(
            f"database.mutation.v1 transaction.mode must be one of {TXN_MODES}")
    if txn.get("isolation") not in ISOLATION_LEVELS:
        raise CERValidationError(
            f"database.mutation.v1 transaction.isolation must be one of {ISOLATION_LEVELS}")

    if not isinstance(actuation["expected_row_version"], str) or not actuation["expected_row_version"]:
        raise CERValidationError("database.mutation.v1 expected_row_version required (string)")


def _target_id(actuation: Dict[str, Any]) -> str:
    t = actuation["target"]
    return f"{t['connection_ref']}/{t['schema']}/{t['table']}"


def _arguments(actuation: Dict[str, Any]) -> Dict[str, Any]:
    """Identity-bearing, normalized arguments. Includes the two ActionGate R7 facts
    (``unbounded`` bool, ``affected_count`` string) so the frozen gate governs it."""
    scope = actuation["affected_scope"]
    txn = actuation["transaction"]
    args: Dict[str, Any] = {
        "sql_operation": actuation["sql_operation"],
        "statement_digest": actuation["statement_digest"],
        "affected_count": str(scope["estimated_rows"]),   # R7 MAX_SCOPE fact
        "unbounded": bool(scope["unbounded"]),            # R7 FORBID fact
        "transaction_mode": txn["mode"],
        "isolation": txn["isolation"],
        "expected_row_version": actuation["expected_row_version"],
    }
    if "parameters_digest" in actuation:
        args["parameters_digest"] = actuation["parameters_digest"]
    if "predicate_digest" in actuation:
        args["predicate_digest"] = actuation["predicate_digest"]
    return args


def to_envelope(cer: Dict[str, Any]) -> Dict[str, Any]:
    act = cer["actuation"]
    rollback_plan = ({"ref": act["compensation_ref"]}
                     if act.get("compensation_ref") else None)
    return _envelope.build_envelope(
        cer, server_id=ACTIONGATE_SERVER, tool_name=ACTIONGATE_TOOL,
        operation=act["operation"], target_id=_target_id(act),
        arguments=_arguments(act), reversibility=act["reversibility"],
        freshness_source=FRESHNESS_SOURCE, rollback_plan=rollback_plan)
