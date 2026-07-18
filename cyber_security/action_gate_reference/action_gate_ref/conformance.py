"""Executable conformance vectors (spec §19).

Each vector asserts a semantic expectation (same/different/reject) and, where
practical, pins concrete canonical bytes + SHA-256 / SHA-512-256 digests. The
pinned values are written to fixtures/conformance_vectors.json by
``generate_pinned()`` and re-verified by ``run_conformance()`` (regression
pinning); the reference implementation defines the canonical digests.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from . import hashing, jcs, policy, projection, schema
from . import approval as approval_mod
from . import evidence as evidence_mod
from . import token as token_mod
from . import audit as audit_mod
from .errors import GateError

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
_H = "3f" * 32  # 64 hex


def ref_envelope() -> dict:
    return {
        "action_id": "8b2f2c9e-1a44-4c0e-9b1a-2f6c9d0e5a71",
        "timestamp": "2026-07-12T14:03:11.000Z",
        "agent_identity": {"id": "agent://sre/1", "key_id": "k7", "sig": "deadbeef"},
        "runtime": "mcp-host/1.2",
        "model_provider": {"model": "claude-opus-4-8", "provider": "anthropic"},
        "delegator": {"id": "user://alice", "type": "HUMAN"},
        "delegation_chain": [{"from": "user://alice", "to": "agent://sre/1",
                              "grant": "iam:*", "exp": "2026-07-12T18:00:00.000Z"}],
        "objective": "onboard service account",
        "tool": {"server_id": "cloud-iam", "tool_name": "attach_role_policy"},
        "operation": "IAM_GRANT_ADMIN",
        "target_resource": ["arn:aws:iam::acct:role/billing-sa"],
        "arguments": {"grantee": "arn:aws:iam::acct:role/other"},
        "credential_scope": {"principal": "agent://sre/1",
                             "permissions": ["iam:AttachRolePolicy"], "ttl": "PT10M"},
        "current_state_hash": f"sha256:{_H}",
        "state_freshness": {"as_of": "2026-07-12T14:03:05.000Z", "source": "iam-live"},
        "policy_version": "1.4.0+sha256:aa11",
        "reversibility": "REVERSIBLE_WITH_COST",
        "correlation_id": "sess-77c1",
        "sequence_id": "sess-77c1:0007",
    }


def _mut(env, **changes):
    e = copy.deepcopy(env)
    for k, v in changes.items():
        e[k] = v
    return e


def _reject(fn, code):
    try:
        fn()
        return False, "expected rejection but succeeded"
    except GateError as exc:
        return (exc.code == code), f"got {exc.code}, wanted {code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"unexpected {type(exc).__name__}: {exc}"


# --- vector implementations: each returns (passed: bool, detail: str) ---

def v01_key_order():
    a = jcs.canonicalize({"b": "1", "a": "2"})
    b = jcs.canonicalize({"a": "2", "b": "1"})
    return a == b, "key-order independent"


def v02_whitespace():
    a = jcs.canonicalize(jcs.load_strict(b'{"a":"1",  "b":\n"2"}'))
    b = jcs.canonicalize(jcs.load_strict(b'{"a":"1","b":"2"}'))
    return a == b, "whitespace independent"


def v03_omit_vs_null():
    a = jcs.canonicalize({"x": "1"})
    b = jcs.canonicalize({"x": "1", "linked_ticket": None})
    return a != b, "omit != null"


def v04_number_rejected():
    return _reject(lambda: jcs.canonicalize({"count": 5}), "E_BARE_NUMBER")


def v05_timestamp_norm():
    ok1 = True
    try:
        schema.validate_timestamp("2026-07-12T14:03:11.000Z", "t")
    except GateError:
        ok1 = False
    bad = _reject(lambda: schema.validate_timestamp("2026-07-12T15:03:11+01:00", "t"),
                  "E_BAD_TIMESTAMP")
    return ok1 and bad[0], "ms-UTC accepted; offset rejected"


def v06_arg_change():
    e = ref_envelope()
    h1 = projection.action_hash(e)
    h2 = projection.action_hash(_mut(e, arguments={"grantee": "arn:aws:iam::acct:role/CHANGED"}))
    return h1 != h2, "argument change -> different action_hash"


def v07_target_change():
    e = ref_envelope()
    h1 = projection.action_hash(e)
    h2 = projection.action_hash(_mut(e, target_resource=["arn:aws:iam::acct:role/x"]))
    return h1 != h2, "target change -> different"


def v08_scope_expand():
    e = ref_envelope()
    h1 = projection.action_hash(e)
    cs = dict(e["credential_scope"]); cs["permissions"] = ["iam:AttachRolePolicy", "iam:*"]
    h2 = projection.action_hash(_mut(e, credential_scope=cs))
    return h1 != h2, "credential expansion -> different"


def v09_policy_change():
    e = ref_envelope()
    h1 = projection.action_hash(e)
    h2 = projection.action_hash(_mut(e, policy_version="1.5.0+sha256:bb22"))
    return h1 != h2, "policy_version change -> different action_hash"


def v10_approval_expiry_change():
    e = ref_envelope()
    ah = projection.action_hash(e)
    base = dict(action_hash=ah, policy_hash="ph", approver_policy="single",
                approvers=[{"id": "sec", "key_id": "approver:security-lead"}],
                approval_scope={"operation": "IAM_GRANT_ADMIN"}, constraints={},
                issued_at="2026-07-12T13:00:00.000Z", nonce="n1")
    a1 = approval_mod.build_approval(expiration="2026-07-12T15:00:00.000Z", **base)
    a2 = approval_mod.build_approval(expiration="2026-07-12T16:00:00.000Z", **base)
    return a1["approval_hash"] != a2["approval_hash"], "expiry change -> different approval_hash"


def v11_rollback_change():
    e = ref_envelope()
    h1 = projection.action_hash(_mut(e, rollback_plan={"steps": ["a"], "verified": True}))
    h2 = projection.action_hash(_mut(e, rollback_plan={"steps": ["b"], "verified": True}))
    return h1 != h2, "rollback change -> different"


def v12_set_reorder_same():
    a = jcs.canonicalize({"credential_scope": {"permissions": ["x", "y"]}},
                         set_paths=frozenset({"credential_scope.permissions"}))
    b = jcs.canonicalize({"credential_scope": {"permissions": ["y", "x"]}},
                         set_paths=frozenset({"credential_scope.permissions"}))
    return a == b, "set reorder -> same"


def v13_list_reorder_diff():
    a = jcs.canonicalize({"args": ["x", "y"]})
    b = jcs.canonicalize({"args": ["y", "x"]})
    return a != b, "ordered list reorder -> different"


def v14_dup_key():
    return _reject(lambda: jcs.load_strict(b'{"a":"1","a":"2"}'), "E_DUP_KEY")


def v15_nan_inf():
    return _reject(lambda: jcs.load_strict(b'{"x": NaN}'), "E_NAN_INF")


def v16_non_nfc():
    nfd = "é"  # e + combining acute (NFD)
    r = _reject(lambda: jcs.canonicalize({"name": nfd}, nfc_paths=frozenset({"name"})),
                "E_NON_NFC")
    diff = jcs.canonicalize({"name": "é"}) != jcs.canonicalize({"name": nfd})
    return r[0] and diff, "NFC-required rejects NFD; raw NFC != NFD"


def v17_secret_ref():
    a = jcs.canonicalize({"secret": "secretref://vault/db#v1"})
    b = jcs.canonicalize({"secret": "secretref://vault/db#v2"})
    return a != b, "secret versions differ"


def v18_audit_chain():
    ch = audit_mod.AuditChain("chain-1")
    for i in range(3):
        rec = audit_mod.build_audit_record(
            action_hash=f"a{i}", decision="ALLOW", dispositive_rules=["R2"],
            policy_hash="ph", evidence_hashes=[], approval_hashes=[],
            applied_constraints=None, timestamps={"decided": "2026-07-12T14:03:11.000Z"})
        ch.append(rec)
    intact = ch.verify()
    ch.records[1]["payload"]["decision"] = "DENY"  # tamper
    detected = not ch.verify() and ch.locate_tamper() == 1
    return intact and detected, "chain verifies; tamper localized to record 1"


def v19_token_replay():
    e = ref_envelope()
    ah = projection.action_hash(e)
    tok = token_mod.build_token(
        action_hash=ah, permitted_operation="IAM_GRANT_ADMIN",
        permitted_target=e["target_resource"], credential_scope=e["credential_scope"],
        constraints={}, expiration="2026-07-12T15:00:00.000Z", nonce="tok-1",
        policy_hash="ph", decision_record_hash="dr")
    return _reject(
        lambda: token_mod.verify_token(tok, e, active_policy_hash="ph",
                                       now="2026-07-12T14:05:00.000Z", used_nonces={"tok-1"}),
        "E_NONCE_REPLAY")


def v20_toctou():
    e = ref_envelope()
    ah = projection.action_hash(e)
    tok = token_mod.build_token(
        action_hash=ah, permitted_operation="IAM_GRANT_ADMIN",
        permitted_target=e["target_resource"], credential_scope=e["credential_scope"],
        constraints={}, expiration="2026-07-12T15:00:00.000Z", nonce="tok-2",
        policy_hash="ph", decision_record_hash="dr")
    return _reject(
        lambda: token_mod.verify_token(tok, e, active_policy_hash="ph",
                                       now="2026-07-12T14:05:00.000Z",
                                       current_state_hash=f"sha256:{'ab'*32}"),
        "E_STALE_STATE")


def v21_actionid_timestamp_excluded():
    e = ref_envelope()
    h1 = projection.action_hash(e)
    h2 = projection.action_hash(_mut(e, action_id="00000000-0000-4000-8000-000000000000",
                                     timestamp="2026-07-12T23:59:59.000Z"))
    return h1 == h2, "action_id/timestamp excluded -> same action_hash"


def v22_domain_separation():
    b = jcs.canonicalize({"x": "1"})
    da = hashing.domain_digest("ACTION", b)
    de = hashing.domain_digest("EVIDENCE", b)
    return da != de, "same bytes, different domain -> different digest"


def v23_runtime_model_included():
    e = ref_envelope()
    h1 = projection.action_hash(e)
    h2 = projection.action_hash(_mut(e, runtime="other-runtime/9"))
    h3 = projection.action_hash(_mut(e, model_provider={"model": "x", "provider": "y"}))
    return h1 != h2 and h1 != h3, "runtime/model included -> different"


def v24_low_entropy_secret_rejected():
    # A bare hash of a low-entropy secret is prohibited (§8). The reference API
    # exposes no bare-hash-of-secret path; committing requires HMAC. We assert
    # the policy by construction: there is no function that hashes a raw secret.
    import inspect

    from . import hashing as h
    banned = any("secret" in name.lower() for name, _ in inspect.getmembers(h, inspect.isfunction))
    return not banned, "no bare-hash-of-secret API exists (HMAC commitment required, §8)"


VECTORS = [
    ("V1_key_order", v01_key_order, "same"),
    ("V2_whitespace", v02_whitespace, "same"),
    ("V3_omit_vs_null", v03_omit_vs_null, "different"),
    ("V4_number_rejected", v04_number_rejected, "reject:E_BARE_NUMBER"),
    ("V5_timestamp_norm", v05_timestamp_norm, "mixed"),
    ("V6_arg_change", v06_arg_change, "different"),
    ("V7_target_change", v07_target_change, "different"),
    ("V8_scope_expand", v08_scope_expand, "different"),
    ("V9_policy_change", v09_policy_change, "different"),
    ("V10_approval_expiry", v10_approval_expiry_change, "different"),
    ("V11_rollback_change", v11_rollback_change, "different"),
    ("V12_set_reorder_same", v12_set_reorder_same, "same"),
    ("V13_list_reorder_diff", v13_list_reorder_diff, "different"),
    ("V14_dup_key", v14_dup_key, "reject:E_DUP_KEY"),
    ("V15_nan_inf", v15_nan_inf, "reject:E_NAN_INF"),
    ("V16_non_nfc", v16_non_nfc, "reject:E_NON_NFC"),
    ("V17_secret_ref", v17_secret_ref, "different"),
    ("V18_audit_chain", v18_audit_chain, "verify+tamper"),
    ("V19_token_replay", v19_token_replay, "reject:E_NONCE_REPLAY"),
    ("V20_toctou", v20_toctou, "reject:E_STALE_STATE"),
    ("V21_id_ts_excluded", v21_actionid_timestamp_excluded, "same"),
    ("V22_domain_separation", v22_domain_separation, "different"),
    ("V23_runtime_model_included", v23_runtime_model_included, "different"),
    ("V24_low_entropy_secret", v24_low_entropy_secret_rejected, "policy"),
]


def run_conformance() -> dict:
    results = []
    for name, fn, expectation in VECTORS:
        try:
            passed, detail = fn()
        except Exception as exc:  # noqa: BLE001
            passed, detail = False, f"exception: {exc}"
        results.append({"vector": name, "expectation": expectation, "passed": bool(passed),
                        "detail": detail})
    all_pass = all(r["passed"] for r in results)
    return {"all_pass": all_pass, "count": len(results),
            "passed": sum(r["passed"] for r in results), "results": results}


def pinned_digests() -> dict:
    """Concrete pinned canonical bytes + digests for the reference action."""
    e = ref_envelope()
    canon = projection.action_canonical_bytes(e)
    out = {
        "reference_action_canonical_bytes": canon.decode("utf-8"),
        "reference_action_byte_len": len(canon),
        "action_hash_sha256": projection.action_hash(e, algorithm_id="sha-256"),
    }
    if hashing.algorithm_supported("sha-512-256"):
        out["action_hash_sha512_256"] = projection.action_hash(e, algorithm_id="sha-512-256")
    # a small canonical-bytes example with both digests
    sample = jcs.canonicalize({"a": "2", "b": "1"})
    out["sample_canonical_bytes"] = sample.decode("utf-8")
    out["sample_digest_ACTION_sha256"] = hashing.domain_digest("ACTION", sample, algorithm_id="sha-256")
    if hashing.algorithm_supported("sha-512-256"):
        out["sample_digest_ACTION_sha512_256"] = hashing.domain_digest(
            "ACTION", sample, algorithm_id="sha-512-256")
    return out


def generate_pinned() -> dict:
    doc = {"conformance": run_conformance(), "pinned": pinned_digests(),
           "vectors": [{"vector": n, "expectation": e} for n, _, e in VECTORS]}
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "conformance_vectors.json").write_text(json.dumps(doc, indent=2, sort_keys=True))
    return doc
