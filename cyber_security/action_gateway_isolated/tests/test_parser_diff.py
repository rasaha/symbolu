"""N11 — parser-differential + adversarial-input tests.

The gateway and the broker MUST canonicalize an action identically, or a signed
intent could mean one thing to the signer and another to the enforcer. Because both
sides call the single ``canon`` module, identical canonicalization is structural;
these tests demonstrate it holds across adversarial inputs (unicode, key ordering,
duplicate keys, escaping, malformed/truncated/oversized transport) and that the
bounded transport rejects malformed frames deterministically.
"""

from __future__ import annotations

import json
import socket
import struct

import pytest

from action_gateway_isolated import canon, policy_semantic, rpc


# ---- the gateway and broker use the SAME canonicalizer (no duplicate impl) ----

def test_gateway_and_broker_share_one_canonicalizer():
    import action_gateway_isolated.broker_core as bc
    import action_gateway_isolated.gateway_core as gc
    assert bc.canon is gc.canon is canon  # exactly one implementation (N9/N11)


def _ah(manifest, **over):
    base = dict(cluster="c", namespace="protected", api_group="", api_version="v1",
                kind="ConfigMap", name="x", verb="update", manifest=manifest,
                policy_hash="ph", state_present=True, state_rv="7")
    base.update(over)
    return canon.action_hash(**base)


# ---- key ordering is irrelevant (JCS) ----

def test_key_ordering_does_not_change_digest():
    a = {"apiVersion": "v1", "kind": "ConfigMap", "data": {"x": "1", "y": "2"}}
    b = {"data": {"y": "2", "x": "1"}, "kind": "ConfigMap", "apiVersion": "v1"}
    assert canon.manifest_digest(a) == canon.manifest_digest(b)
    assert _ah(a) == _ah(b)


# ---- duplicate keys collapse deterministically (last wins), both sides agree ----

def test_duplicate_keys_deterministic():
    raw = '{"data": {"k": "first", "k": "second"}, "kind": "ConfigMap"}'
    parsed_gateway = json.loads(raw)
    parsed_broker = json.loads(raw)
    assert parsed_gateway == parsed_broker == {"data": {"k": "second"}, "kind": "ConfigMap"}
    assert canon.manifest_digest(parsed_gateway) == canon.manifest_digest(parsed_broker)


# ---- unicode / escaping: distinct code points stay distinct; identical stay identical ----

def test_unicode_is_stable_and_not_silently_unified():
    precomposed = {"data": {"n": "café"}}        # e-acute as U+00E9
    decomposed = {"data": {"n": "café"}}        # e + combining acute U+0301
    assert canon.manifest_digest(precomposed) == canon.manifest_digest(precomposed)
    # the two normalization forms are different code-point sequences -> different
    # digests, so an attacker cannot smuggle one past a check that saw the other.
    assert canon.manifest_digest(precomposed) != canon.manifest_digest(decomposed)


def test_escaping_roundtrip_stable():
    tricky = {"data": {"s": "a\"b\\c\n\t /"}}
    assert canon.manifest_digest(tricky) == canon.manifest_digest(json.loads(json.dumps(tricky)))


# ---- fail-closed parsing feeds the policy (N1 x N11): unknown fields are caught ----

def test_unknown_pod_field_fails_closed():
    m = {"kind": "Pod", "spec": {"containers": [], "smuggled": {"privileged": True}}}
    checks = {c["check"] for c in policy_semantic.check(
        {"namespace": "protected", "kind": "Pod", "name": "p"}, m,
        allowed_namespaces={"protected"})}
    assert any(c.startswith("unrecognized_pod_spec_field") for c in checks)


def test_unknown_container_field_fails_closed():
    m = {"kind": "Pod", "spec": {"containers": [
        {"name": "c", "image": "registry.example.com/x@sha256:" + "a" * 64, "backdoor": 1}]}}
    checks = {c["check"] for c in policy_semantic.check(
        {"namespace": "protected", "kind": "Pod", "name": "p"}, m,
        allowed_namespaces={"protected"})}
    assert any(c.startswith("unrecognized_container_field") for c in checks)


# ---- bounded transport rejects malformed / truncated / oversized frames ----

def _pair():
    return socket.socketpair()


def test_oversized_length_prefix_rejected_before_allocation():
    a, b = _pair()
    try:
        a.sendall(struct.pack(">I", rpc.MAX_FRAME_BYTES + 1) + b"{}")
        with pytest.raises(ValueError):
            rpc._recv(b)
    finally:
        a.close(); b.close()


def test_oversized_response_send_rejected():
    a, b = _pair()
    try:
        with pytest.raises(ValueError):
            rpc._send(a, {"blob": "z" * (rpc.MAX_FRAME_BYTES + 10)})
    finally:
        a.close(); b.close()


def test_truncated_transport_rejected():
    a, b = _pair()
    try:
        a.sendall(struct.pack(">I", 100) + b"{")  # promises 100 bytes, sends 1
        a.close()
        with pytest.raises((ConnectionError, ValueError, json.JSONDecodeError)):
            rpc._recv(b)
    finally:
        b.close()


def test_malformed_json_rejected():
    a, b = _pair()
    try:
        payload = b"{not valid json"
        a.sendall(struct.pack(">I", len(payload)) + payload)
        with pytest.raises(json.JSONDecodeError):
            rpc._recv(b)
    finally:
        a.close(); b.close()


# ---- N4: bounded concurrency sheds load deterministically (back-pressure) ----

def test_backpressure_sheds_load_deterministically(tmp_path, monkeypatch):
    import threading
    import time
    monkeypatch.setattr(rpc, "MAX_CONCURRENCY", 2)  # only 2 in-flight slots

    def handler(req):
        time.sleep(0.4)                              # hold the slot so others contend
        return {"ok": True}

    sock = str(tmp_path / "gw.sock")
    t = threading.Thread(target=rpc.serve_unix, args=(sock, handler), daemon=True)
    t.start()
    for _ in range(50):
        if __import__("os").path.exists(sock):
            break
        time.sleep(0.02)

    results = {}

    def fire(i):
        try:
            results[i] = rpc.unix_call(sock, {"ping": i}, timeout=5)
        except Exception as e:  # noqa: BLE001
            results[i] = {"error": type(e).__name__}

    threads = [threading.Thread(target=fire, args=(i,)) for i in range(12)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    overloaded = sum(1 for v in results.values() if v.get("error") == "E_OVERLOADED")
    served = sum(1 for v in results.values() if v.get("ok"))
    assert len(results) == 12                # every request terminated (no hang) — no DoS
    assert 1 <= served <= 2, results         # capacity is used AND really capped at 2
    assert overloaded >= 1, results          # excess load is shed with E_OVERLOADED
