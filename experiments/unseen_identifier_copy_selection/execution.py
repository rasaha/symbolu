"""Fail-closed execution authorization for the unseen-identifier diagnostic.

Reserved diagnostic seeds (smoke 9070 / development 9071-9073 / final 90760-90764) cannot generate a
cohort or train unless the caller holds a VALIDATED authorization context for that exact seed and
role. A context is produced ONLY by `authorize(...)`, which validates a provenance-bound
authorization record (canonical digest, recognized state, state-to-seed-role matrix, cohort, commits,
frozen model hashes + parameter count, and — for scientific states — an approved repository
authorization artifact). The capability the context carries is honoured by the primitive-level guards
only while the context is active (`active_authorization(...)`), so a raw string, a manually-built
record, or an internally-consistent-but-unapproved record cannot bypass the guard.

The schema RECOGNIZES all four frozen states, but recognition does not activate a state: a scientific
state is usable only through a valid record that references an approved authorization artifact. No
such artifact exists in this session, so every scientific/reserved seed still fails closed and no
scientific token is minted here. Non-reserved (fixture) seeds are validated through a fixture context
and are otherwise ungated so unit tests can build fixtures.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Iterator

from .config import (
    DEVELOPMENT_SEEDS,
    FINAL_SEEDS,
    FIXTURE_SEEDS,
    RESERVED_SEEDS,
    SMOKE_SEEDS,
)


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


# ---------------------------------------------------------------------------
# Frozen authorization states + state-to-seed-role matrix.
# Recognizing a state does NOT activate it; activation additionally requires a valid, provenance-bound
# record (and, for scientific states, an approved authorization artifact — none of which exist here).
# ---------------------------------------------------------------------------

FIXTURE_AUTHORIZATION_STATE: Final[str] = "FIXTURE_TEST_AUTHORIZATION"
SMOKE_EXECUTION_STATE: Final[str] = "SMOKE_EXECUTION_AUTHORIZED"
DEVELOPMENT_EXECUTION_STATE: Final[str] = "DEVELOPMENT_EXECUTION_AUTHORIZED"
FINAL_EXECUTION_STATE: Final[str] = "FINAL_EXECUTION_AUTHORIZED"

SCIENTIFIC_STATES: Final[frozenset[str]] = frozenset(
    {SMOKE_EXECUTION_STATE, DEVELOPMENT_EXECUTION_STATE, FINAL_EXECUTION_STATE}
)
RECOGNIZED_STATES: Final[frozenset[str]] = frozenset(
    {FIXTURE_AUTHORIZATION_STATE} | SCIENTIFIC_STATES
)

# Each state may bind ONLY its own seed role; every cross-role combination is rejected.
STATE_SEED_ROLES: Final = MappingProxyType(
    {
        FIXTURE_AUTHORIZATION_STATE: frozenset(FIXTURE_SEEDS),
        SMOKE_EXECUTION_STATE: frozenset(SMOKE_SEEDS),
        DEVELOPMENT_EXECUTION_STATE: frozenset(DEVELOPMENT_SEEDS),
        FINAL_EXECUTION_STATE: frozenset(FINAL_SEEDS),
    }
)

FROZEN_PARAMETER_COUNT: Final[int] = 209_728

# Frozen authorization scopes. A record's scope must be recognized (an unknown scope fails closed).
RECOGNIZED_SCOPES: Final[frozenset[str]] = frozenset({"one-run"})

_CORE_RECORD_KEYS: Final[tuple[str, ...]] = (
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
# Present ONLY on scientific-state records: the canonical digest of the approved authorization
# artifact the record is bound to. Fixture-state records never carry it.
_ARTIFACT_DIGEST_KEY: Final[str] = "authorization_artifact_digest"


class AuthorizationRecordError(ExecutionNotAuthorized):
    """Raised (fail-closed) when an authorization record is missing, malformed, or mismatched."""


@dataclass(frozen=True)
class AuthorizationContext:
    """Immutable, validated authorization. Constructed ONLY by `authorize(...)`."""

    authorization_state: str
    seed: int
    cohort: str
    record_digest: str
    protocol_lock_commit: str
    implementation_authorization_commit: str
    implementation_commit: str
    model_recipe_hashes: tuple[tuple[str, str], ...]
    parameter_count: int
    scope: str

    @property
    def capability(self) -> str:
        """The one-run capability honoured by the primitive guards while this context is active."""
        return self.record_digest

    @property
    def role_seeds(self) -> frozenset[int]:
        return STATE_SEED_ROLES[self.authorization_state]


# Live, process-local registry of ACTIVE capabilities. Populated ONLY by `active_authorization`
# (never by importing a record or by a raw string), and emptied on context exit.
_ACTIVE_CAPABILITIES: dict[str, AuthorizationContext] = {}


def require_execution_authorization(seed: int, token: str | None = None) -> None:
    """Fail closed for reserved seeds. Non-reserved (fixture) seeds are ungated.

    For a reserved seed the `token` must be the capability of an ACTIVE, validated authorization
    context whose seed and state-role match. An unknown/None token, or a mismatched capability,
    fails closed — so no reserved seed runs without a live validated context."""
    if int(seed) not in RESERVED_SEEDS:
        return
    context = _ACTIVE_CAPABILITIES.get(token) if token is not None else None
    if context is None:
        raise ExecutionNotAuthorized(
            f"seed {seed} is a reserved {_role(seed)} diagnostic seed; no active validated "
            f"authorization context exists (execution is not authorized)"
        )
    if int(context.seed) != int(seed):
        raise ExecutionNotAuthorized(
            f"authorization capability is bound to seed {context.seed}, not {seed}"
        )
    if int(seed) not in context.role_seeds:
        raise ExecutionNotAuthorized(
            f"authorization state {context.authorization_state!r} does not permit seed {seed}"
        )


@contextlib.contextmanager
def active_authorization(context: AuthorizationContext) -> Iterator[AuthorizationContext]:
    """Activate a validated context's capability for the duration of a single guarded operation.

    The capability is registered on entry and removed on exit (even on error), giving each authorized
    operation a one-run scope and preventing capability leakage across calls or tests."""
    if not isinstance(context, AuthorizationContext):
        raise AuthorizationRecordError("active_authorization requires a validated AuthorizationContext")
    key = context.capability
    if key in _ACTIVE_CAPABILITIES:
        raise AuthorizationRecordError("authorization capability is already active")
    _ACTIVE_CAPABILITIES[key] = context
    try:
        yield context
    finally:
        _ACTIVE_CAPABILITIES.pop(key, None)


# ---------------------------------------------------------------------------
# Record + artifact digests
# ---------------------------------------------------------------------------

def _record_payload(record: dict) -> dict:
    """The canonical payload whose digest is bound in `record_digest` (everything but the digest)."""
    return {k: v for k, v in record.items() if k != "record_digest"}


def compute_record_digest(record: dict) -> str:
    from .manifest import digest_json  # local import: keep execution.py import-light

    return digest_json(_record_payload(record))


def artifact_digest(artifact: dict) -> str:
    """Canonical digest of an approved authorization artifact (used to bind a scientific record)."""
    from .manifest import digest_json

    return digest_json(artifact)


def build_fixture_authorization_record(seed: int, cohort: str, *, scope: str = "one-run") -> dict:
    """Construct a VALID FIXTURE authorization record bound to a single fixture seed.

    Used only by fixture-level unit tests. It is NOT a scientific authorization record: the state is
    the fixture state and the seed must be a fixture seed (scientific/reserved seeds fail closed)."""
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


# ---------------------------------------------------------------------------
# Central validation -> immutable context. The ONLY way to obtain an AuthorizationContext.
# ---------------------------------------------------------------------------

def _validate_core(record: dict, *, seed: int, cohort: str) -> None:
    from .manifest import frozen_recipe_source_hashes

    if not isinstance(record, dict):
        raise AuthorizationRecordError("authorization record must be a mapping")
    missing = [k for k in _CORE_RECORD_KEYS if k not in record]
    if missing:
        raise AuthorizationRecordError(f"authorization record is missing keys: {missing}")

    state = record["authorization_state"]
    if state not in RECOGNIZED_STATES:
        raise AuthorizationRecordError(
            f"unknown/unauthorized authorization state {state!r} (recognized: {sorted(RECOGNIZED_STATES)})"
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

    # State-to-seed-role matrix: the command seed AND every permitted seed must belong to the
    # state's own role. Every cross-role combination (e.g. smoke state + final seed) is rejected.
    allowed = STATE_SEED_ROLES[state]
    if int(seed) not in allowed:
        raise AuthorizationRecordError(
            f"seed {seed} is not permitted under state {state!r} (allowed role seeds: {sorted(allowed)})"
        )
    off_role = [s for s in permitted if int(s) not in allowed]
    if off_role:
        raise AuthorizationRecordError(
            f"permitted seeds {off_role} are outside state {state!r}'s role (cross-role authorization rejected)"
        )

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

    if record["scope"] not in RECOGNIZED_SCOPES:
        raise AuthorizationRecordError(
            f"unknown authorization scope {record['scope']!r} (recognized: {sorted(RECOGNIZED_SCOPES)})"
        )


def _validate_scientific_provenance(record: dict, *, authorization_artifact: dict | None) -> None:
    """Bind a scientific record to an APPROVED repository authorization artifact (data-driven).

    A self-hash of the record alone is insufficient (anyone can recompute it), so a scientific state
    is valid ONLY when the caller supplies a separate approved authorization artifact whose canonical
    digest the record binds and whose declared approval state/seed-role/commit matches the record.
    This is the data-driven digest+commit binding preferred by merged PR #1374 (Decision 3) and this
    correction.

    TRUST BOUNDARY (for the independent re-audit): the trust root is the SUPPLIED approved artifact
    document — validation proves the record is bound to *that* document and its approved commit, not
    that the document is itself merged/authentic. In the disciplined multi-session workflow the
    approved artifact is the real merged execution-authorization document, confirmed by independent
    audit; a stronger, non-repudiable binding (e.g. git-ancestry verification of `approved_commit`
    against the trusted default branch, or a signed artifact) is a separate design decision NOT frozen
    by PR #1374 and intentionally NOT invented here. No approved scientific artifact exists or is
    committed in this session, so scientific records always fail closed and no scientific token is
    minted."""
    if _ARTIFACT_DIGEST_KEY not in record:
        raise AuthorizationRecordError(
            f"scientific record must bind {_ARTIFACT_DIGEST_KEY!r} to an approved authorization artifact"
        )
    if authorization_artifact is None:
        raise AuthorizationRecordError(
            "scientific authorization requires the approved authorization artifact to be supplied explicitly"
        )
    if not isinstance(authorization_artifact, dict):
        raise AuthorizationRecordError("authorization artifact must be a mapping")
    if authorization_artifact.get("approved") is not True:
        raise AuthorizationRecordError("authorization artifact is not marked approved")
    if artifact_digest(authorization_artifact) != record[_ARTIFACT_DIGEST_KEY]:
        raise AuthorizationRecordError("authorization artifact digest does not match the record's binding")
    if authorization_artifact.get("authorization_state") != record["authorization_state"]:
        raise AuthorizationRecordError("authorization artifact state does not match the record state")
    if authorization_artifact.get("approved_commit") != record["implementation_authorization_commit"]:
        raise AuthorizationRecordError(
            "record's implementation_authorization_commit does not match the artifact's approved commit"
        )
    artifact_seeds = authorization_artifact.get("permitted_seeds")
    if not isinstance(artifact_seeds, list) or not set(record["permitted_seeds"]).issubset(set(artifact_seeds)):
        raise AuthorizationRecordError("record permitted seeds are not covered by the approved artifact")


def authorize(
    record: dict,
    *,
    seed: int,
    cohort: str,
    authorization_artifact: dict | None = None,
) -> AuthorizationContext:
    """Validate a record and return an immutable AuthorizationContext (the ONLY constructor).

    Fail-closed on: missing/malformed record, unknown state, digest tamper, wrong cohort, wrong seed,
    cross-role seed/state combination, empty commits, parameter/hash mismatch, and — for scientific
    states — a missing/unapproved/mismatched authorization artifact. Recognition of a scientific
    state never activates it: without an approved artifact (none exists here) it fails closed."""
    _validate_core(record, seed=seed, cohort=cohort)
    if record["authorization_state"] in SCIENTIFIC_STATES:
        _validate_scientific_provenance(record, authorization_artifact=authorization_artifact)
    return AuthorizationContext(
        authorization_state=record["authorization_state"],
        seed=int(seed),
        cohort=cohort,
        record_digest=record["record_digest"],
        protocol_lock_commit=record["protocol_lock_commit"],
        implementation_authorization_commit=record["implementation_authorization_commit"],
        implementation_commit=record["implementation_commit"],
        model_recipe_hashes=tuple(sorted(record["model_recipe_hashes"].items())),
        parameter_count=int(record["parameter_count"]),
        scope=record["scope"],
    )


def validate_authorization_record(
    record: dict,
    *,
    seed: int,
    cohort: str,
    authorization_artifact: dict | None = None,
) -> None:
    """Back-compatible thin wrapper over `authorize` (discards the context)."""
    authorize(record, seed=seed, cohort=cohort, authorization_artifact=authorization_artifact)


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


def load_authorization_artifact(path: str) -> dict:
    """Load an approved authorization artifact from a JSON file (fail-closed on read errors)."""
    import json

    try:
        with open(path, "r", encoding="utf-8") as handle:
            artifact = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorizationRecordError(f"authorization artifact could not be read: {exc}") from exc
    if not isinstance(artifact, dict):
        raise AuthorizationRecordError("authorization artifact file must contain a JSON object")
    return artifact
