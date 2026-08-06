"""Fail-closed execution authorization gate for the unseen-identifier diagnostic.

Reserved diagnostic seeds (smoke 9070 / development 9071-9073 / final 90760-90764) cannot be used
to generate a cohort or train unless a caller supplies a valid execution-authorization token. No
such token exists: the registry is intentionally EMPTY, because execution is not authorized. Every
reserved seed therefore fails closed. Non-reserved seeds (including the fixture namespace) are
ungated so unit tests can build fixtures.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final

from .config import RESERVED_SEEDS, SMOKE_SEEDS, DEVELOPMENT_SEEDS, FINAL_SEEDS


class ExecutionNotAuthorized(PermissionError):
    """Raised before any dataset generation, model initialization, or training side effect."""


def _role(seed: int) -> str | None:
    s = int(seed)
    if s in SMOKE_SEEDS:
        return "smoke"
    if s in DEVELOPMENT_SEEDS:
        return "development"
    if s in FINAL_SEEDS:
        return "final"
    return None


# Intentionally EMPTY: execution is not authorized, so no reserved seed has a valid token.
_AUTHORIZATION_TOKENS: Final = MappingProxyType({})  # type: ignore[var-annotated]


def require_execution_authorization(seed: int, token: str | None = None) -> None:
    """Fail closed for reserved seeds. Non-reserved seeds are permitted (fixtures/tests)."""
    if int(seed) not in RESERVED_SEEDS:
        return
    role = _role(seed)
    expected = _AUTHORIZATION_TOKENS.get(role)
    if expected is None or token is None or token != expected:
        raise ExecutionNotAuthorized(
            f"seed {seed} is a reserved {role} diagnostic seed; execution is not authorized "
            f"(no valid execution-authorization token exists)"
        )


# ---------------------------------------------------------------------------
# Fail-closed execution authorization-record schema + validation (Decision 3).
#
# The interface REQUIRES an explicit authorization record at every command boundary and validates
# it BEFORE any pool/cohort generation. No SCIENTIFIC authorization record is created here: the only
# recognized state is the fixture state used by unit tests, and every permitted seed is additionally
# gated by `require_execution_authorization` — so a record naming any reserved seed (9070 / 9071-9073
# / 90760-90764) fails closed regardless of its other fields. A later, separately-audited execution
# authorization would add a scientific state bound to a real token; this implementation adds none.
# ---------------------------------------------------------------------------

FROZEN_PARAMETER_COUNT: Final[int] = 209_728

# The single recognized authorization state in THIS implementation. Scientific states
# (smoke/development/final) are intentionally absent — an unknown state fails closed.
FIXTURE_AUTHORIZATION_STATE: Final[str] = "FIXTURE_TEST_AUTHORIZATION"
RECOGNIZED_STATES: Final[frozenset[str]] = frozenset({FIXTURE_AUTHORIZATION_STATE})

_REQUIRED_RECORD_KEYS: Final[tuple[str, ...]] = (
    "authorization_state",
    "cohort",
    "permitted_seeds",
    "protocol_lock_commit",
    "implementation_authorization_commit",
    "implementation_commit",
    "model_recipe_hashes",
    "parameter_count",
    "scope",
    "record_digest",
)


class AuthorizationRecordError(ExecutionNotAuthorized):
    """Raised (fail-closed) when an authorization record is missing, malformed, or mismatched."""


def _record_payload(record: dict) -> dict:
    """The canonical payload whose digest is bound in `record_digest` (everything but the digest)."""
    return {k: record[k] for k in _REQUIRED_RECORD_KEYS if k != "record_digest"}


def compute_record_digest(record: dict) -> str:
    from .manifest import digest_json  # local import: keep execution.py import-light

    return digest_json(_record_payload(record))


def build_fixture_authorization_record(seed: int, cohort: str, *, scope: str = "one-run") -> dict:
    """Construct a VALID FIXTURE authorization record bound to a single fixture seed.

    Used only by fixture-level unit tests. It is NOT a scientific authorization record: the state is
    the fixture state and the seed must be a fixture seed (a reserved seed still fails closed)."""
    from .config import FIXTURE_SEEDS
    from .manifest import frozen_recipe_source_hashes

    if int(seed) not in FIXTURE_SEEDS:
        raise AuthorizationRecordError(
            f"a fixture authorization record may bind only fixture seeds {FIXTURE_SEEDS}; got {seed}"
        )
    if cohort not in ("seen", "unseen"):
        raise AuthorizationRecordError(f"unknown cohort: {cohort}")
    record = {
        "authorization_state": FIXTURE_AUTHORIZATION_STATE,
        "cohort": cohort,
        "permitted_seeds": [int(seed)],
        "protocol_lock_commit": "FIXTURE",
        "implementation_authorization_commit": "FIXTURE",
        "implementation_commit": "FIXTURE",
        "model_recipe_hashes": frozen_recipe_source_hashes(),
        "parameter_count": FROZEN_PARAMETER_COUNT,
        "scope": scope,
    }
    record["record_digest"] = compute_record_digest(record)
    return record


def validate_authorization_record(record: dict, *, seed: int, cohort: str) -> None:
    """Fail-closed validation performed BEFORE any pool/cohort generation.

    Rejects: missing/malformed records, unknown states, bad digest, wrong seed, wrong cohort,
    mismatched commits (empty), mismatched recipe hashes, mismatched parameter count, and any
    reserved seed (which additionally has no valid execution token → fails closed)."""
    from .config import RESERVED_SEEDS as _RESERVED
    from .manifest import frozen_recipe_source_hashes

    if not isinstance(record, dict):
        raise AuthorizationRecordError("authorization record must be a mapping")
    missing = [k for k in _REQUIRED_RECORD_KEYS if k not in record]
    if missing:
        raise AuthorizationRecordError(f"authorization record is missing keys: {missing}")

    state = record["authorization_state"]
    if state not in RECOGNIZED_STATES:
        raise AuthorizationRecordError(
            f"unknown/unauthorized authorization state {state!r} "
            f"(recognized: {sorted(RECOGNIZED_STATES)})"
        )

    if compute_record_digest(record) != record["record_digest"]:
        raise AuthorizationRecordError("authorization record digest mismatch (tampered or malformed)")

    if record["cohort"] not in ("seen", "unseen"):
        raise AuthorizationRecordError(f"unknown cohort in record: {record['cohort']!r}")
    if record["cohort"] != cohort:
        raise AuthorizationRecordError(
            f"requested cohort {cohort!r} not permitted by record (record binds {record['cohort']!r})"
        )

    permitted = record["permitted_seeds"]
    if not isinstance(permitted, list) or not permitted or not all(isinstance(s, int) for s in permitted):
        raise AuthorizationRecordError("permitted_seeds must be a non-empty list of integers")
    if int(seed) not in permitted:
        raise AuthorizationRecordError(f"seed {seed} is not in the record's permitted seeds {permitted}")

    for field_name in ("protocol_lock_commit", "implementation_authorization_commit", "implementation_commit"):
        value = record[field_name]
        if not isinstance(value, str) or not value.strip():
            raise AuthorizationRecordError(f"{field_name} must be a non-empty provenance string")

    if record["parameter_count"] != FROZEN_PARAMETER_COUNT:
        raise AuthorizationRecordError(
            f"parameter_count mismatch: record {record['parameter_count']} != frozen {FROZEN_PARAMETER_COUNT}"
        )
    if record["model_recipe_hashes"] != frozen_recipe_source_hashes():
        raise AuthorizationRecordError("model_recipe_hashes do not match the frozen recipe sources")

    # Every permitted seed must clear the reserved-seed gate (no scientific token exists → reserved
    # seeds fail closed here); this is the load-bearing prohibition on 9070 / 9071-9073 / 90760-90764.
    for permitted_seed in permitted:
        if int(permitted_seed) in _RESERVED:
            raise AuthorizationRecordError(
                f"seed {permitted_seed} is a reserved diagnostic seed; no execution authorization exists"
            )
        require_execution_authorization(int(permitted_seed), None)


def load_authorization_record(path: str) -> dict:
    """Load an authorization record from a JSON file (no validation performed here).

    A missing, unreadable, or non-JSON file is a fail-closed authorization error."""
    import json

    try:
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorizationRecordError(f"authorization record could not be read: {exc}") from exc
    if not isinstance(record, dict):
        raise AuthorizationRecordError("authorization record file must contain a JSON object")
    return record
