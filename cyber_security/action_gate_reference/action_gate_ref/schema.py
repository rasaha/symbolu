"""Canonical action-envelope validation for the 24 frozen fields.

Enforces required/optional/null/empty exactly per ACTION_GATE_SPECIFICATION.md §2
and ACTION_CANONICALIZATION_AND_HASHING_SPEC.md §3, plus the Action-Profile rules
(no bare numbers, duplicate keys, NaN/Inf, bad timestamps, invalid enums, unknown
schema versions). A machine-readable JSON Schema mirror lives in
fixtures/envelope.schema.json; this module is the *enforced* validator (it checks
what JSON Schema cannot, e.g. duplicate keys and bare-number rejection).
"""

from __future__ import annotations

import re
from typing import Any

from . import jcs
from .errors import (
    BadTimestampError,
    InvalidEnumError,
    RequiredMissingError,
    UnknownSchemaError,
    GateError,
)

SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0.0"})

# schema-declared set-like paths (order-independent, dedup) — spec §7
ENVELOPE_SET_PATHS = frozenset({"credential_scope.permissions"})
# schema-declared NFC-required paths (validated, never rewritten) — spec §2.2
ENVELOPE_NFC_PATHS = frozenset()

REVERSIBILITY = frozenset({"REVERSIBLE", "REVERSIBLE_WITH_COST", "IRREVERSIBLE"})
DELEGATOR_TYPES = frozenset({"HUMAN", "SERVICE"})
OPERATIONS = frozenset({
    "IAM_GRANT_ADMIN", "DEPLOY", "DB_DELETE", "NET_EXPOSE", "SECRET_READ",
    "MONITORING_DISABLE", "DB_MUTATION", "KEY_ROTATE", "CLOUD_SPEND_INCREASE",
    "EXTERNAL_COMMS",
})

REQUIRED_FIELDS = (
    "action_id", "timestamp", "agent_identity", "runtime", "model_provider",
    "delegator", "delegation_chain", "objective", "tool", "operation",
    "target_resource", "arguments", "credential_scope", "current_state_hash",
    "state_freshness", "policy_version", "reversibility", "correlation_id",
    "sequence_id",
)
OPTIONAL_FIELDS = ("linked_ticket", "approvals", "attestation", "rollback_plan",
                   "expected_effects")
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

# RFC-3339 UTC, 'Z', exactly 3 fractional digits, no leap second (spec §5)
_TS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T([01]\d|2[0-3]):[0-5]\d:([0-5]\d)\.\d{3}Z$"
)
_HASH_RE = re.compile(r"^(?:sha-?256:)?[0-9a-f]{64}$")
_POLICY_VER_RE = re.compile(r"^\d+\.\d+\.\d+\+.+$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def validate_timestamp(value: str, field: str) -> None:
    if not isinstance(value, str) or not _TS_RE.match(value):
        raise BadTimestampError(f"not RFC-3339 UTC ms-precision: {value!r}", field=field)


def _require(env: dict, field: str) -> Any:
    if field not in env:
        raise RequiredMissingError(f"required field absent: {field}", field=field)
    if env[field] is None:
        raise RequiredMissingError(f"required field is null: {field}", field=field)
    return env[field]


def validate_envelope(envelope: Any, *, schema_version: str = "1.0.0") -> None:
    """Validate structure + enums + timestamps, then enforce the Action Profile.

    Raises a GateError (with a machine-readable ``.code``) on any violation.
    """
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise UnknownSchemaError(f"unsupported envelope_schema_version {schema_version!r}")
    if not isinstance(envelope, dict):
        raise GateError("envelope must be a JSON object")

    unknown = set(envelope) - set(ALL_FIELDS)
    if unknown:
        # unknown REQUIRED field in a newer schema => fail closed (spec §13 gate)
        raise UnknownSchemaError(f"unknown envelope fields: {sorted(unknown)}")

    for f in REQUIRED_FIELDS:
        _require(envelope, f)

    # enums
    op = envelope["operation"]
    if op not in OPERATIONS:
        raise InvalidEnumError(f"operation not in taxonomy: {op!r}", field="operation")
    rev = envelope["reversibility"]
    if rev not in REVERSIBILITY:
        raise InvalidEnumError(f"reversibility invalid: {rev!r}", field="reversibility")
    dtype = envelope["delegator"].get("type") if isinstance(envelope["delegator"], dict) else None
    if dtype not in DELEGATOR_TYPES:
        raise InvalidEnumError(f"delegator.type invalid: {dtype!r}", field="delegator.type")

    # timestamps
    validate_timestamp(envelope["timestamp"], "timestamp")
    sf = envelope["state_freshness"]
    if not isinstance(sf, dict) or "as_of" not in sf:
        raise BadTimestampError("state_freshness.as_of missing", field="state_freshness")
    validate_timestamp(sf["as_of"], "state_freshness.as_of")

    # id / hash / policy formats
    if not _UUID_RE.match(str(envelope["action_id"])):
        raise GateError("action_id not a UUIDv4", field="action_id")
    if not _HASH_RE.match(str(envelope["current_state_hash"])):
        raise GateError("current_state_hash malformed", field="current_state_hash")
    if not _POLICY_VER_RE.match(str(envelope["policy_version"])):
        raise GateError("policy_version malformed (want semver+hash)", field="policy_version")

    # non-empty required collections
    if not envelope["target_resource"]:
        raise RequiredMissingError("target_resource must be non-empty", field="target_resource")
    if not envelope["delegation_chain"]:
        raise RequiredMissingError("delegation_chain must be non-empty",
                                   field="delegation_chain")

    # Action Profile enforcement: successful canonicalization rejects bare numbers,
    # duplicate keys (already at load), NaN/Inf, non-NFC, unsupported types.
    jcs.canonicalize(envelope, ENVELOPE_SET_PATHS, ENVELOPE_NFC_PATHS)
