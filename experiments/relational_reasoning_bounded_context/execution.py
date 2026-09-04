"""Fail-closed execution-authorization gate (two-key). Torch-free.

Reserved BTRR scientific seeds (smoke 8100, dev 8101-8103, final 81600-81604) cannot enter any
generation/training/evaluation path unless BOTH keys are present:

  (a) a committed, owner-signed authorization record (BTRR_EXECUTION_AUTHORIZATION_RECORD.json) whose
      per-role entry is `authorized`, in-scope for the seed, bound to the current frozen protocol digest,
      and not expired; and
  (b) an operator-supplied plaintext token (env BTRR_EXEC_TOKEN or the `token=` argument) whose SHA-256
      equals the record's `token_sha256`.

Neither key alone suffices. The repository never stores a usable token (only its hash). If the record is
absent, unreadable, not authorized, out of scope, protocol-mismatched, expired, or the token is missing/
wrong, the guard raises. The shipped record template has every role `authorized:false`, so execution
remains closed until an owner signs it. Unit-fixture seeds (883000-883004) and any non-reserved seed are
ungated (implementation testing only). Implements BTRR_EXECUTION_AUTHORIZATION_MECHANISM_SPEC.md.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
from dataclasses import dataclass

from .config import ARM_ABS, ARMS, RESERVED_SEED_ARM_ROLES, RESERVED_SEED_ROLES, UNIT_FIXTURE_SEEDS

# Canonical committed record paths (repo_root/docs/research/hybrid_llm/benchmarks/...), one per arm.
_BENCHMARKS_DIR = pathlib.Path(__file__).resolve().parents[2] / "docs/research/hybrid_llm/benchmarks"
RECORD_PATH = _BENCHMARKS_DIR / ARMS[ARM_ABS]["record_file"]          # BTRR-ABS (parent arm)
OPERATOR_TOKEN_ENV = "BTRR_EXEC_TOKEN"


def record_path_for(arm: str) -> pathlib.Path:
    """Committed authorization record for `arm`; each arm has its own record and token hash."""
    return _BENCHMARKS_DIR / ARMS[arm]["record_file"]


class ExecutionNotAuthorized(PermissionError):
    """Raised before any side effect when a reserved seed is used without valid authorization."""


@dataclass(frozen=True)
class GrantedAuthorization:
    role: str
    authorized: bool = True


def load_signed_record(path: str | os.PathLike | None = None) -> dict | None:
    """Read the committed authorization record. Returns None if absent; raises if unreadable."""
    p = pathlib.Path(path) if path is not None else RECORD_PATH
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except (OSError, ValueError) as exc:
        raise ExecutionNotAuthorized("authorization record is unreadable — refusing to run") from exc
    if not isinstance(data, dict):
        raise ExecutionNotAuthorized("authorization record is malformed")
    return data


def _evaluate_authorization(role: str, seed: int, supplied_token: str | None,
                            record: dict | None, arm: str = ARM_ABS) -> GrantedAuthorization:
    """Pure two-key evaluation (no I/O). Returns a grant or raises. Never self-authorizes: the caller
    cannot supply a grant, only the record (owner key) and token (operator key), both of which are
    checked here against the current frozen protocol."""
    if record is None:
        raise ExecutionNotAuthorized(f"seed {seed} ({role}): no signed authorization record present")
    entry = (record.get("roles") or {}).get(role)
    if not isinstance(entry, dict) or not entry.get("authorized"):
        raise ExecutionNotAuthorized(f"seed {seed}: role {role} is not authorized (record unsigned)")
    scope = [int(x) for x in entry.get("scope_seeds", [])]
    if int(seed) not in scope:
        raise ExecutionNotAuthorized(f"seed {seed} is outside the authorized scope for {role}")
    # protocol binding: the authorization must match the current frozen protocol/config digest
    from . import manifest  # lazy; manifest imports config+tokenizer only (no cycle)
    if entry.get("protocol_lock_digest") != manifest.config_digest(arm):
        raise ExecutionNotAuthorized(
            f"seed {seed} ({ARMS[arm]['name']}): authorization was signed for a different frozen protocol "
            f"(config drift)")
    expires_at = entry.get("expires_at")
    if expires_at:
        try:
            expired = _dt.datetime.now(_dt.timezone.utc) > _dt.datetime.fromisoformat(expires_at)
        except ValueError as exc:
            raise ExecutionNotAuthorized(f"seed {seed}: invalid expires_at in record") from exc
        if expired:
            raise ExecutionNotAuthorized(f"seed {seed}: authorization for {role} has expired")
    if supplied_token is None:
        raise ExecutionNotAuthorized(f"seed {seed}: operator token not supplied ({OPERATOR_TOKEN_ENV})")
    token_hash = entry.get("token_sha256")
    if not token_hash or hashlib.sha256(supplied_token.encode("utf-8")).hexdigest() != token_hash:
        raise ExecutionNotAuthorized(f"seed {seed}: operator token does not match the signed hash")
    return GrantedAuthorization(role, True)


def guard_seed(seed: int, token: str | None = None) -> GrantedAuthorization:
    """Return a granted authorization, or raise ExecutionNotAuthorized before any side effect.

    Non-reserved seeds (fixtures included) are ungated. Reserved seeds require the two-key check against
    the committed record + operator token. There is NO bypass flag: the record comes only from the
    canonical committed path, and the token is checked by hash."""
    owner = RESERVED_SEED_ARM_ROLES.get(int(seed))
    if owner is None:
        return GrantedAuthorization("non_reserved", True)
    arm, role = owner
    if ARMS[arm].get("status") == "CLOSED":
        raise ExecutionNotAuthorized(
            f"seed {seed}: arm {ARMS[arm]['name']} is CLOSED on its calibration record; reserved-seed execution "
            f"is not permitted without an owner-ratified reopening (config.ARMS status)")
    supplied = token if token is not None else os.environ.get(OPERATOR_TOKEN_ENV)
    return _evaluate_authorization(role, int(seed), supplied, load_signed_record(record_path_for(arm)), arm)


def assert_generation_allowed(seed: int, token: str | None = None) -> int:
    """Centralized fail-closed guard for EVERY scientific primitive (generation/training/eval/replay).

    Raises ExecutionNotAuthorized before any cohort is materialized unless the reserved seed passes the
    two-key authorization check. Non-reserved seeds (including inadmissible fixtures 883000-883004) pass.
    """
    guard_seed(int(seed), token)  # raises for reserved seeds without valid two-key authorization
    return int(seed)


def is_unit_fixture(seed: int) -> bool:
    return int(seed) in UNIT_FIXTURE_SEEDS


def require_unit_fixture(seed: int) -> int:
    """Executable implementation tests may use ONLY inadmissible unit-fixture seeds."""
    if not is_unit_fixture(seed):
        raise ExecutionNotAuthorized(
            f"seed {seed} is not an inadmissible unit-fixture seed (883000-883004); "
            f"reserved scientific seeds must not enter any generator/training/eval path"
        )
    return int(seed)
