"""Tests for the two-key execution-authorization mechanism. Stdlib only; no reserved seed is run.

The 'granted' path is exercised only through the pure `_evaluate_authorization` logic with MOCK records
(no cohort is generated, nothing is trained). The real `guard_seed` is tested end-to-end against the
committed (unsigned, all-false) record, which must keep every reserved seed closed.
"""
from __future__ import annotations

import hashlib

from .. import manifest as MAN
from ..execution import (ExecutionNotAuthorized, GrantedAuthorization, _evaluate_authorization,
                         guard_seed, load_signed_record)

TOKEN = "operator-secret-example"
HASH = hashlib.sha256(TOKEN.encode()).hexdigest()


def _record(role="smoke", *, authorized=True, seeds=(8100,), token_hash=HASH,
            digest=None, expires_at=None):
    digest = MAN.config_digest() if digest is None else digest
    return {"schema": "btrr/execution_authorization_record/v1",
            "roles": {role: {"authorized": authorized, "scope_seeds": list(seeds),
                             "token_sha256": token_hash, "protocol_lock_digest": digest,
                             "expires_at": expires_at}}}


# ---- committed record keeps everything closed (default fail-closed) ----
def test_committed_record_is_unsigned_and_closed():
    rec = load_signed_record()                       # the committed all-false template
    assert rec is not None                           # file exists
    assert all(not r["authorized"] for r in rec["roles"].values())
    for s in (8100, 8101, 8102, 8103, 81600, 81601, 81602, 81603, 81604):
        try:
            guard_seed(s); assert False, f"seed {s} must be closed"
        except ExecutionNotAuthorized:
            pass

def test_fixtures_and_nonreserved_still_pass():
    assert guard_seed(883000).authorized                 # fixture -> non-reserved -> granted
    assert guard_seed(12345).role == "non_reserved"


# ---- pure two-key logic (mock records; no cohort generated) ----
def test_grant_requires_both_keys():
    g = _evaluate_authorization("smoke", 8100, TOKEN, _record())
    assert isinstance(g, GrantedAuthorization) and g.authorized and g.role == "smoke"

def _rejects(role, seed, token, record):
    try:
        _evaluate_authorization(role, seed, token, record); return False
    except ExecutionNotAuthorized:
        return True

def test_absent_record_rejected():
    assert _rejects("smoke", 8100, TOKEN, None)

def test_unauthorized_role_rejected():
    assert _rejects("smoke", 8100, TOKEN, _record(authorized=False))

def test_out_of_scope_seed_rejected():
    assert _rejects("smoke", 8101, TOKEN, _record(seeds=(8100,)))   # 8101 not in smoke scope

def test_protocol_digest_mismatch_rejected():
    assert _rejects("smoke", 8100, TOKEN, _record(digest="deadbeef"))

def test_expired_rejected():
    assert _rejects("smoke", 8100, TOKEN, _record(expires_at="2000-01-01T00:00:00+00:00"))

def test_missing_operator_token_rejected():
    assert _rejects("smoke", 8100, None, _record())

def test_wrong_operator_token_rejected():
    assert _rejects("smoke", 8100, "wrong", _record())

def test_role_isolation_smoke_does_not_authorize_final():
    # a record that signs ONLY smoke must leave final closed
    rec = _record("smoke")
    assert _evaluate_authorization("smoke", 8100, TOKEN, rec).authorized
    assert _rejects("final", 81600, TOKEN, rec)

def test_no_bypass_flag_in_guard_signature():
    import inspect
    from .. import execution
    params = inspect.signature(execution.guard_seed).parameters
    assert set(params) == {"seed", "token"}          # no 'authorized' / bypass kwarg
    assert "authorized" not in inspect.signature(execution.assert_generation_allowed).parameters


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p = f = 0
    for t in tests:
        try:
            t(); p += 1; print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            f += 1; print(f"FAIL {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{p} passed, {f} failed, {len(tests)} total")
    return 1 if f else 0


if __name__ == "__main__":
    raise SystemExit(main())
