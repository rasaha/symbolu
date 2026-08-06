"""Fail-closed execution authorization for the unseen-identifier diagnostic (security-hardened).

Two forgery defects discovered after PR #1375 merged are closed here:

* AUTHORIZATION_PROVENANCE_FORGEABLE — a self-consistent JSON artifact plus a recomputed digest is
  no longer sufficient. A scientific authorization is valid only when its authorization document is
  read *from local Git* at a claimed commit that is (a) a real commit object, (b) reachable from the
  configured authoritative-default reference (i.e. actually merged, not merely on a feature branch),
  and (c) a descendant of the frozen implementation merge being authorized; the committed bytes'
  digest must match the record's binding, and every authoritative value (approval, state, cohort,
  seed role, commits, hashes, parameter count, scope) is read from the COMMITTED document, never from
  a caller-supplied duplicate.

* AUTHORIZATION_CONTEXT_FORGEABLE — the authority-bearing context can no longer be forged through
  public APIs. `AuthorizationContext` cannot be constructed directly (construction requires a
  module-private mint key), and — independently — `active_authorization` accepts only the exact
  object identity minted by a successful `authorize()` (a copied / replaced / pickled / hand-built
  object fails), bound to one exact seed/cohort/state/scope/commit invocation.

Threat model (honest): these protections stop bypass through supported/public APIs and ordinary
object construction. Code with arbitrary interpreter access — reassigning module-private globals,
reaching into `execution`'s internals, or monkeypatching Git — is OUTSIDE this capability boundary.
No cryptographic guarantee against a malicious process controlling the interpreter is claimed. The
runtime path uses bounded LOCAL Git only (no network).

Recognition of the scientific states is structural; no scientific state is active until a committed,
provenance-valid authorization document exists. None exists in this repository, so every
scientific/reserved seed still fails closed and no authority capability is minted for the real repo.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Iterator
import contextlib

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
# Frozen authorization states + state-to-seed-role matrix (unchanged).
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

STATE_SEED_ROLES: Final = MappingProxyType(
    {
        FIXTURE_AUTHORIZATION_STATE: frozenset(FIXTURE_SEEDS),
        SMOKE_EXECUTION_STATE: frozenset(SMOKE_SEEDS),
        DEVELOPMENT_EXECUTION_STATE: frozenset(DEVELOPMENT_SEEDS),
        FINAL_EXECUTION_STATE: frozenset(FINAL_SEEDS),
    }
)

FROZEN_PARAMETER_COUNT: Final[int] = 209_728
RECOGNIZED_SCOPES: Final[frozenset[str]] = frozenset({"one-run"})

# ---------------------------------------------------------------------------
# Repository authority root (frozen; operator-overridable via environment).
# The authoritative-default reference and the authorized-implementation merge are NEVER read from the
# artifact being validated — they come from frozen config or an explicit operator-controlled value.
# ---------------------------------------------------------------------------

AUTHORITATIVE_DEFAULT_REF: Final[str] = (
    "refs/remotes/origin/claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF"
)
_AUTHORITATIVE_DEFAULT_REF_ENV: Final[str] = "UNSEEN_ID_AUTHORITATIVE_REF"
# The implementation merge being authorized (PR #1375 merge). A scientific authorization document
# must be committed AFTER this merge and must bind an implementation commit that is this merge or a
# descendant of it.
AUTHORIZED_IMPLEMENTATION_MERGE: Final[str] = "e30b0efaa3ab12b1648174af0f996d2a0c7e8fcb"

# The only repository path a committed authorization document may live at (allow-list; no traversal).
AUTHORIZATION_DOCUMENT_PATHS: Final[frozenset[str]] = frozenset(
    {"docs/research/hybrid_llm/benchmarks/UNSEEN_IDENTIFIER_EXECUTION_AUTHORIZATION.json"}
)

DOC_SCHEMA_VERSION: Final[str] = "unseen-id-exec-authorization/1"
_DOC_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "approved",
        "authorization_state",
        "permitted_cohort",
        "permitted_seeds",
        "protocol_lock_commit",
        "implementation_authorization_commit",
        "implementation_commit",
        "model_recipe_hashes",
        "parameter_count",
        "authorization_scope",
    }
)
_DOC_OPTIONAL_KEYS: Final[frozenset[str]] = frozenset({"expiry"})

_FULL_OID = re.compile(r"^[0-9a-f]{40}$")
_GIT_TIMEOUT_SECONDS: Final[int] = 15


class AuthorizationRecordError(ExecutionNotAuthorized):
    """Raised (fail-closed) when an authorization record/document is missing, malformed, or unproven."""


# ---------------------------------------------------------------------------
# Digests
# ---------------------------------------------------------------------------

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record_payload(record: dict) -> dict:
    return {k: v for k, v in record.items() if k != "record_digest"}


def compute_record_digest(record: dict) -> str:
    from .manifest import digest_json  # local import keeps this module import-light

    return digest_json(_record_payload(record))


# ---------------------------------------------------------------------------
# Bounded local-Git helpers (no shell, arg lists, timeouts, deterministic failures).
# ---------------------------------------------------------------------------

def _git_raw(repo_dir: str, args: list[str]) -> subprocess.CompletedProcess:
    if any(not isinstance(a, str) for a in args):
        raise AuthorizationRecordError("git arguments must be strings")
    try:
        return subprocess.run(
            ["git", "-C", repo_dir, *args],
            capture_output=True,
            shell=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AuthorizationRecordError(f"git invocation failed: {exc}") from exc


def _assert_oid(oid: str) -> str:
    if not isinstance(oid, str) or not _FULL_OID.match(oid):
        raise AuthorizationRecordError(f"commit identity {oid!r} is not a full 40-hex object id")
    return oid


def _assert_doc_path(path: str) -> str:
    if path not in AUTHORIZATION_DOCUMENT_PATHS:
        raise AuthorizationRecordError(f"authorization document path {path!r} is not allow-listed")
    if ".." in path.split("/") or path.startswith("/"):
        raise AuthorizationRecordError("authorization document path traversal rejected")
    return path


def _object_type(repo_dir: str, oid: str) -> str:
    proc = _git_raw(repo_dir, ["cat-file", "-t", oid])
    if proc.returncode != 0:
        raise AuthorizationRecordError(f"object {oid} does not exist in the repository")
    return proc.stdout.decode("ascii", "replace").strip()


def _is_ancestor(repo_dir: str, ancestor: str, descendant: str) -> bool:
    proc = _git_raw(repo_dir, ["merge-base", "--is-ancestor", ancestor, descendant])
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    raise AuthorizationRecordError(
        f"ancestry check failed ({ancestor}->{descendant}): {proc.stderr.decode('ascii', 'replace')[:120]}"
    )


def _resolve_ref(repo_dir: str, ref: str) -> str:
    proc = _git_raw(repo_dir, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
    oid = proc.stdout.decode("ascii", "replace").strip()
    if proc.returncode != 0 or not _FULL_OID.match(oid):
        raise AuthorizationRecordError(f"authoritative reference {ref!r} does not resolve to a commit")
    return oid


def _read_committed_bytes(repo_dir: str, commit: str, path: str) -> bytes:
    # `<commit>:<path>` addressing; path is allow-listed so injection/traversal is already excluded.
    proc = _git_raw(repo_dir, ["cat-file", "-e", f"{commit}:{path}"])
    if proc.returncode != 0:
        raise AuthorizationRecordError(f"authorization document {path!r} is absent from commit {commit}")
    show = _git_raw(repo_dir, ["show", f"{commit}:{path}"])
    if show.returncode != 0:
        raise AuthorizationRecordError(f"authorization document {path!r} could not be read from commit {commit}")
    return show.stdout


# ---------------------------------------------------------------------------
# Committed authorization-document schema
# ---------------------------------------------------------------------------

def _reject_duplicate_keys(pairs):
    seen: dict = {}
    for key, value in pairs:
        if key in seen:
            raise AuthorizationRecordError(f"duplicate key {key!r} in authorization document")
        seen[key] = value
    return seen


def _parse_committed_document(raw: bytes) -> dict:
    import json

    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorizationRecordError(f"authorization document is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise AuthorizationRecordError("authorization document must be a JSON object")
    keys = set(doc)
    missing = _DOC_REQUIRED_KEYS - keys
    if missing:
        raise AuthorizationRecordError(f"authorization document missing fields: {sorted(missing)}")
    unknown = keys - _DOC_REQUIRED_KEYS - _DOC_OPTIONAL_KEYS
    if unknown:
        raise AuthorizationRecordError(f"authorization document has unknown fields: {sorted(unknown)}")
    if doc["schema_version"] != DOC_SCHEMA_VERSION:
        raise AuthorizationRecordError(f"authorization document schema {doc['schema_version']!r} unsupported")
    # Any expiry field fails closed: without a trusted clock, an expiry cannot be verified as unexpired.
    if "expiry" in doc and doc["expiry"] is not None:
        raise AuthorizationRecordError("time-based authorization expiry cannot be verified (fails closed)")
    return doc


# ---------------------------------------------------------------------------
# Non-forgeable authorization context (mint-gated + minted-identity registry).
# ---------------------------------------------------------------------------

_MINT_KEY: Final[object] = object()          # module-private construction capability
_MINTED_CONTEXTS: dict[int, "AuthorizationContext"] = {}   # id(ctx) -> ctx (exact minted identities)
_REVOKED: set[int] = set()
# Capabilities honoured by the primitive guards, live only inside `active_authorization`.
_ACTIVE_CAPABILITIES: dict[str, "AuthorizationContext"] = {}


@dataclass(frozen=True)
class AuthorizationContext:
    """Immutable, validated authorization. Constructible ONLY by the module-private mint path.

    Direct construction, `dataclasses.replace`, copy, and unpickling do not yield an object the guard
    honours: `active_authorization` accepts only the exact identity minted by a successful
    `authorize()` (see `_MINTED_CONTEXTS`)."""

    mint_key: object
    authorization_state: str
    seed: int
    cohort: str
    record_digest: str
    document_commit: str
    document_digest: str
    protocol_lock_commit: str
    implementation_authorization_commit: str
    implementation_commit: str
    model_recipe_hashes: tuple
    parameter_count: int
    scope: str

    def __post_init__(self) -> None:
        if self.mint_key is not _MINT_KEY:
            raise AuthorizationRecordError(
                "AuthorizationContext cannot be constructed directly; obtain one from authorize()"
            )

    @property
    def capability(self) -> str:
        return self.record_digest

    @property
    def role_seeds(self) -> frozenset:
        return STATE_SEED_ROLES[self.authorization_state]


def _mint_context(**fields) -> AuthorizationContext:
    context = AuthorizationContext(mint_key=_MINT_KEY, **fields)
    _MINTED_CONTEXTS[id(context)] = context   # strong ref: id cannot be recycled while minted
    return context


def _is_minted(context: object) -> bool:
    return (
        isinstance(context, AuthorizationContext)
        and _MINTED_CONTEXTS.get(id(context)) is context
        and id(context) not in _REVOKED
    )


# ---------------------------------------------------------------------------
# Primitive guard + one-run activation
# ---------------------------------------------------------------------------

def require_execution_authorization(seed: int, token: str | None = None) -> None:
    """Fail closed for reserved seeds. Non-reserved (fixture) seeds are ungated.

    For a reserved seed the `token` must be the capability of an ACTIVE, minted, validated context
    whose seed and state-role match. An unknown/None token, a mismatched capability, or a capability
    whose backing context was not minted by `authorize()` fails closed."""
    if int(seed) not in RESERVED_SEEDS:
        return
    context = _ACTIVE_CAPABILITIES.get(token) if token is not None else None
    if context is None or not _is_minted(context):
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
    """Activate a MINTED context's capability for one guarded operation.

    Only the exact object identity produced by a successful `authorize()` is honoured: a forged,
    copied, replaced, deserialized, or hand-built object raises here and can never reach the guard.
    The capability is registered on entry and removed on exit (even on error), giving one-run scope."""
    if not _is_minted(context):
        raise AuthorizationRecordError(
            "active_authorization requires the exact AuthorizationContext minted by authorize()"
        )
    key = context.capability
    if not isinstance(key, str) or not key:
        raise AuthorizationRecordError("authorization capability is malformed")
    if key in _ACTIVE_CAPABILITIES:
        raise AuthorizationRecordError("authorization capability is already active")
    _ACTIVE_CAPABILITIES[key] = context
    try:
        yield context
    finally:
        _ACTIVE_CAPABILITIES.pop(key, None)


def revoke_minted_context(context: AuthorizationContext) -> None:
    """Permanently revoke a minted context (defensive; used by tests)."""
    _REVOKED.add(id(context))


# ---------------------------------------------------------------------------
# Fixture records (unchanged trust: fixture seeds are non-reserved and need no Git provenance).
# ---------------------------------------------------------------------------

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


def build_fixture_authorization_record(seed: int, cohort: str, *, scope: str = "one-run") -> dict:
    """A VALID FIXTURE record bound to a single fixture seed (unit tests only; not scientific)."""
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
# Central validation -> minted context. The ONLY way to obtain an AuthorizationContext.
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


def _verify_scientific_provenance(
    record: dict,
    *,
    seed: int,
    cohort: str,
    repo_dir: str,
    authoritative_ref: str,
    implementation_merge: str,
) -> tuple[str, str]:
    """Prove a scientific record against LOCAL Git. Returns (document_commit, document_digest).

    The authoritative values come from the COMMITTED document, never from caller-supplied duplicates."""
    from .manifest import frozen_recipe_source_hashes

    for key in ("authorization_document_commit", "authorization_document_path", "authorization_document_digest"):
        if key not in record:
            raise AuthorizationRecordError(f"scientific record must bind {key!r}")

    commit = _assert_oid(record["authorization_document_commit"])
    path = _assert_doc_path(record["authorization_document_path"])

    # (1-2) the claimed authorization commit is a real commit object
    if _object_type(repo_dir, commit) != "commit":
        raise AuthorizationRecordError(f"authorization object {commit} is not a commit")

    # (3-4) reachable from the configured authoritative default (merged), not merely a feature branch
    authoritative_commit = _resolve_ref(repo_dir, authoritative_ref)
    if not _is_ancestor(repo_dir, commit, authoritative_commit):
        raise AuthorizationRecordError(
            f"authorization commit {commit} is not reachable from the authoritative default reference"
        )

    # (10) chronology: the authorization commit must descend from (or equal) the authorized impl merge
    merge_oid = _assert_oid(implementation_merge)
    if _object_type(repo_dir, merge_oid) != "commit":
        raise AuthorizationRecordError("authorized implementation merge is not a commit in this repository")
    if not _is_ancestor(repo_dir, merge_oid, commit):
        raise AuthorizationRecordError(
            f"authorization commit {commit} does not descend from the authorized implementation merge"
        )

    # (5-7) load committed bytes; digest must match the record's binding
    raw = _read_committed_bytes(repo_dir, commit, path)
    document_digest = sha256_hex(raw)
    if document_digest != record["authorization_document_digest"]:
        raise AuthorizationRecordError("committed authorization document digest does not match the record binding")

    # (8) parse the COMMITTED document and take authoritative values from it
    doc = _parse_committed_document(raw)
    if doc["approved"] is not True:
        raise AuthorizationRecordError("committed authorization document is not approved")
    if doc["authorization_state"] != record["authorization_state"]:
        raise AuthorizationRecordError("committed document state does not match the record state")
    if doc["permitted_cohort"] != cohort:
        raise AuthorizationRecordError("committed document cohort does not permit the requested cohort")
    doc_seeds = doc["permitted_seeds"]
    if not isinstance(doc_seeds, list) or int(seed) not in doc_seeds:
        raise AuthorizationRecordError("requested seed is not permitted by the committed document")
    if any(int(s) not in STATE_SEED_ROLES[doc["authorization_state"]] for s in doc_seeds):
        raise AuthorizationRecordError("committed document binds seeds outside its state's role")
    if doc["model_recipe_hashes"] != frozen_recipe_source_hashes():
        raise AuthorizationRecordError("committed document model hashes do not match the frozen recipe")
    if doc["parameter_count"] != FROZEN_PARAMETER_COUNT:
        raise AuthorizationRecordError("committed document parameter count mismatch")
    if doc["authorization_scope"] not in RECOGNIZED_SCOPES:
        raise AuthorizationRecordError("committed document authorization scope unrecognized")

    # (9) the document's implementation commit must equal/descend from the authorized impl merge
    impl_commit = _assert_oid(doc["implementation_commit"])
    if _object_type(repo_dir, impl_commit) != "commit":
        raise AuthorizationRecordError("committed document implementation_commit is not a commit")
    if not _is_ancestor(repo_dir, merge_oid, impl_commit):
        raise AuthorizationRecordError(
            "committed document implementation_commit does not descend from the authorized implementation merge"
        )
    # record's own commit fields must agree with the committed document's
    if record["implementation_authorization_commit"] != doc["implementation_authorization_commit"]:
        raise AuthorizationRecordError("record implementation_authorization_commit disagrees with committed document")
    if record["implementation_commit"] != doc["implementation_commit"]:
        raise AuthorizationRecordError("record implementation_commit disagrees with committed document")

    return commit, document_digest


def authorize(
    record: dict,
    *,
    seed: int,
    cohort: str,
    repo_dir: str | None = None,
    authoritative_ref: str | None = None,
    implementation_merge: str | None = None,
) -> AuthorizationContext:
    """Validate a record and return a MINTED, non-forgeable AuthorizationContext (the ONLY constructor).

    Fixture-state records are validated structurally (fixture seeds are non-reserved). Scientific-state
    records are additionally proven against LOCAL Git: the authorization document must be committed and
    reachable from the authoritative default reference, descend from the authorized implementation
    merge, match its bound digest, and supply all authoritative values from the committed bytes. No
    approved scientific document exists in this repository, so scientific authorization fails closed."""
    _validate_core(record, seed=seed, cohort=cohort)

    document_commit = "FIXTURE"
    document_digest = "FIXTURE"
    if record["authorization_state"] in SCIENTIFIC_STATES:
        resolved_repo = repo_dir if repo_dir is not None else os.getcwd()
        resolved_ref = (
            authoritative_ref
            if authoritative_ref is not None
            else os.environ.get(_AUTHORITATIVE_DEFAULT_REF_ENV, AUTHORITATIVE_DEFAULT_REF)
        )
        resolved_merge = implementation_merge if implementation_merge is not None else AUTHORIZED_IMPLEMENTATION_MERGE
        document_commit, document_digest = _verify_scientific_provenance(
            record,
            seed=seed,
            cohort=cohort,
            repo_dir=resolved_repo,
            authoritative_ref=resolved_ref,
            implementation_merge=resolved_merge,
        )

    return _mint_context(
        authorization_state=record["authorization_state"],
        seed=int(seed),
        cohort=cohort,
        record_digest=record["record_digest"],
        document_commit=document_commit,
        document_digest=document_digest,
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
    repo_dir: str | None = None,
    authoritative_ref: str | None = None,
    implementation_merge: str | None = None,
) -> None:
    """Back-compatible thin wrapper over `authorize` (discards the minted context)."""
    authorize(
        record,
        seed=seed,
        cohort=cohort,
        repo_dir=repo_dir,
        authoritative_ref=authoritative_ref,
        implementation_merge=implementation_merge,
    )


def load_authorization_record(path: str) -> dict:
    """Load an authorization record from a JSON file (no validation here; fail-closed on read errors)."""
    import json

    try:
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorizationRecordError(f"authorization record could not be read: {exc}") from exc
    if not isinstance(record, dict):
        raise AuthorizationRecordError("authorization record file must contain a JSON object")
    return record
