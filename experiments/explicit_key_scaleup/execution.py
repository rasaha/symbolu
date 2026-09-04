"""Two-key fail-closed execution guard for E1-S (decision [5]; same mechanism as BTRR execution.py).

Reserved seeds (development 6100-6102, final 6140-6144) run only if BOTH keys are present: (a) the
committed owner-signed record E1S_EXECUTION_AUTHORIZATION_RECORD.json with the role authorized, the seed
in scope, protocol_lock_digest == manifest.config_digest(), not expired; and (b) an operator token (env
E1S_EXEC_TOKEN or token=) whose sha256 equals the record's token_sha256. Fixture seeds 886000-886004 and
any non-reserved seed are ungated (implementation testing only; scientifically inadmissible).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
from dataclasses import dataclass

from .config import PRIOR_SEED_BLOCKS, RESERVED_SEED_ROLES, UNIT_FIXTURE_SEEDS

_PRIOR_BLOCK_OF = {s: name for name, block in PRIOR_SEED_BLOCKS for s in block}

RECORD_PATH = (pathlib.Path(__file__).resolve().parents[2]
               / "docs/research/hybrid_llm/benchmarks/E1S_EXECUTION_AUTHORIZATION_RECORD.json")
OPERATOR_TOKEN_ENV = "E1S_EXEC_TOKEN"


class ExecutionNotAuthorized(PermissionError):
    """Raised before any side effect when a reserved seed is used without valid two-key authorization."""


@dataclass(frozen=True)
class GrantedAuthorization:
    role: str
    authorized: bool = True


def load_signed_record(path=None):
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


def _evaluate_authorization(role, seed, supplied_token, record) -> GrantedAuthorization:
    if record is None:
        raise ExecutionNotAuthorized(f"seed {seed} ({role}): no signed authorization record present")
    entry = (record.get("roles") or {}).get(role)
    if not isinstance(entry, dict) or not entry.get("authorized"):
        raise ExecutionNotAuthorized(f"seed {seed}: role {role} is not authorized (record unsigned)")
    if int(seed) not in [int(x) for x in entry.get("scope_seeds", [])]:
        raise ExecutionNotAuthorized(f"seed {seed} is outside the authorized scope for {role}")
    from . import manifest
    if entry.get("protocol_lock_digest") != manifest.config_digest():
        raise ExecutionNotAuthorized(f"seed {seed}: authorization was signed for a different frozen protocol")
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
    want = entry.get("token_sha256")
    if not want or hashlib.sha256(supplied_token.encode("utf-8")).hexdigest() != want:
        raise ExecutionNotAuthorized(f"seed {seed}: operator token does not match the signed hash")
    return GrantedAuthorization(role, True)


def guard_seed(seed: int, token: str | None = None) -> GrantedAuthorization:
    if int(seed) in _PRIOR_BLOCK_OF:      # seeds of earlier experiments are never consumed by this line
        raise ExecutionNotAuthorized(f"seed {seed} belongs to a prior block ({_PRIOR_BLOCK_OF[int(seed)]}); "
                                     f"E1-S must not consume it")
    role = RESERVED_SEED_ROLES.get(int(seed))
    if role is None:
        return GrantedAuthorization("non_reserved", True)
    supplied = token if token is not None else os.environ.get(OPERATOR_TOKEN_ENV)
    return _evaluate_authorization(role, int(seed), supplied, load_signed_record())


def assert_generation_allowed(seed: int, token: str | None = None) -> int:
    guard_seed(int(seed), token)
    return int(seed)


def is_unit_fixture(seed: int) -> bool:
    return int(seed) in UNIT_FIXTURE_SEEDS
