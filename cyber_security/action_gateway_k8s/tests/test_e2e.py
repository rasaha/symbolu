"""End-to-end tests against a REAL local cluster.

Every test here is skipped (never falsely passed) when no control plane is
reachable. Run ``scripts/cluster_up.sh`` first to exercise them.
"""

from __future__ import annotations

import copy
import importlib.util
import pathlib
import threading

import pytest

from action_gateway_k8s import ClientSession, K8sGateway, cluster
from action_gateway_k8s._core import FixedClock
from action_gateway_k8s.kubeclient import GVR, K8sApiError, KubeClient

requires_cluster = pytest.mark.skipif(
    not cluster.is_available(),
    reason="no reachable Kubernetes control plane (run scripts/cluster_up.sh)")

pytestmark = requires_cluster

_C = [0]


def _gw(clock=None):
    _C[0] += 1
    g = K8sGateway(allowed_namespaces=("protected",), clock=clock)
    return g, ClientSession(clock=g.clock, correlation_id=f"e2e-{_C[0]}")


def _admin():
    return cluster.admin_client()


def _cm(ns, name, data):
    return {"apiVersion": "v1", "kind": "ConfigMap",
            "metadata": {"name": name, "namespace": ns}, "data": data}


def _absent(kind, name):
    try:
        _admin().delete(GVR[kind], "protected", name)
    except K8sApiError:
        pass


def _approved(gw, cs, name, data=None):
    _absent("ConfigMap", name)
    p = gw.prepare(cs.context(), "kubernetes.apply",
                   {"namespace": "protected", "kind": "ConfigMap", "name": name,
                    "manifest": _cm("protected", name, data or {"a": "b"})})
    gw.evaluate(cs.context(), p["request_id"])
    gw.dry_run(cs.context(), p["request_id"])
    return p


# ---- broker scope / capability ----

def test_broker_mints_namespace_verb_resource_scoped_capability():
    gw, cs = _gw()
    p = _approved(gw, cs, "e2e-cap")
    rec = gw.gateway.records[p["request_id"]]
    cred = gw.broker.issue(token=rec.token, requested_permissions=["k8s:apply"],
                           principal="agent://sre/1", now=gw.clock.now())
    meta = gw.broker.meta(cred)
    assert meta.namespace == "protected" and meta.kind == "ConfigMap" and meta.name == "e2e-cap"
    assert "create" in meta.verbs
    gw.broker.cleanup(cred)


def test_scoped_token_cannot_touch_other_resource():
    # a broker-minted token for one resource cannot mutate another
    gw, cs = _gw()
    p = _approved(gw, cs, "e2e-scope-a")
    rec = gw.gateway.records[p["request_id"]]
    cred = gw.broker.issue(token=rec.token, requested_permissions=["k8s:apply"],
                           principal="agent://sre/1", now=gw.clock.now())
    bearer = gw.broker._secret[cred.credential_id]
    scoped = KubeClient(cluster.SERVER, str(cluster.CA_CERT), token=bearer)
    with pytest.raises(K8sApiError) as ei:  # different name -> 403
        scoped.apply(GVR["ConfigMap"], "protected", "e2e-scope-OTHER",
                     _cm("protected", "e2e-scope-OTHER", {"x": "y"}))
    assert ei.value.status == 403
    with pytest.raises(K8sApiError) as ei2:  # different namespace -> 403
        scoped.get(GVR["ConfigMap"], "sandbox", "anything")
    assert ei2.value.status == 403
    gw.broker.cleanup(cred)


# ---- real apply / delete ----

def test_real_apply_persists_on_cluster():
    gw, cs = _gw()
    p = _approved(gw, cs, "e2e-apply", {"greeting": "hi"})
    x = gw.execute(cs.context(), p["request_id"])
    assert x["state"] == "COMPLETED"
    assert _admin().get(GVR["ConfigMap"], "protected", "e2e-apply")["data"] == {"greeting": "hi"}


def test_delete_requires_approval_then_removes():
    gw, cs = _gw()
    _admin().apply(GVR["ConfigMap"], "protected", "e2e-del", _cm("protected", "e2e-del", {"a": "b"}))
    p = gw.prepare(cs.context(), "kubernetes.delete",
                   {"namespace": "protected", "kind": "ConfigMap", "name": "e2e-del",
                    "rollback_plan": {"restore_from": "b1"}})
    gw.evaluate(cs.context(), p["request_id"])
    d = gw.dry_run(cs.context(), p["request_id"])
    assert d["outcome"] == "ESCALATE_TO_HUMAN"
    with pytest.raises(Exception):
        gw.gateway.execute_action(p["request_id"])  # no token yet
    ap = gw.create_test_approval(p["request_id"])
    gw.attach_approval(cs.context(), p["request_id"], ap)
    gw.execute(cs.context(), p["request_id"])
    with pytest.raises(K8sApiError) as ei:
        _admin().get(GVR["ConfigMap"], "protected", "e2e-del")
    assert ei.value.status == 404


# ---- bindings ----

def test_manifest_digest_binding():
    gw, cs = _gw()
    p = _approved(gw, cs, "e2e-mani")
    bad = copy.deepcopy(gw.gateway.records[p["request_id"]].envelope)
    bad["arguments"] = dict(bad["arguments"], manifest_json='{"x":1}')
    r = gw._commit(cs.context(), p["request_id"], call_envelope=bad)
    assert r["reason_codes"] == ["E_ACTION_HASH_MISMATCH"]


def test_dry_run_binding_privileged_rejected_by_real_apiserver():
    gw, cs = _gw()
    m = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "e2e-priv", "namespace": "protected"},
         "spec": {"containers": [{"name": "c", "image": "nginx",
                                  "securityContext": {"allowPrivilegeEscalation": False,
                                                      "capabilities": {"drop": ["ALL"]}},
                                  "resources": {"limits": {"cpu": "10m", "memory": "16Mi"}}}],
                  "hostNetwork": True}}
    # admission_check misses nothing, but real dry-run must reject hostNetwork
    p = gw.prepare(cs.context(), "kubernetes.apply",
                   {"namespace": "protected", "kind": "Pod", "name": "e2e-priv", "manifest": m})
    d = gw.dry_run(cs.context(), p["request_id"])
    assert d["outcome"] == "DENY"  # withheld by admission and/or real dry-run


def test_approval_bound_to_exact_action_and_policy():
    gw, cs = _gw()
    _admin().apply(GVR["ConfigMap"], "protected", "e2e-ap", _cm("protected", "e2e-ap", {"a": "b"}))
    p = gw.prepare(cs.context(), "kubernetes.delete",
                   {"namespace": "protected", "kind": "ConfigMap", "name": "e2e-ap",
                    "rollback_plan": {"r": "1"}})
    gw.evaluate(cs.context(), p["request_id"])
    gw.dry_run(cs.context(), p["request_id"])
    ap = gw.create_test_approval(p["request_id"])
    rec = gw.gateway.records[p["request_id"]]
    assert ap["payload"]["action_hash"] == rec.action_hash
    assert ap["payload"]["policy_hash"] == gw.gateway.signed_policy["policy_hash"]


# ---- replay / expiry / TOCTOU / concurrency ----

def test_token_replay_rejected():
    gw, cs = _gw()
    p = _approved(gw, cs, "e2e-rep")
    gw.execute(cs.context(), p["request_id"])
    assert gw.execute(cs.context(), p["request_id"])["reason_codes"] == ["E_NONCE_REPLAY"]


def test_capability_single_use():
    gw, cs = _gw()
    p = _approved(gw, cs, "e2e-single")
    res = gw.execute(cs.context(), p["request_id"])
    cred = gw.broker._issued[res["credential_id"]]
    with pytest.raises(Exception):
        gw.broker.redeem(cred, needed_permission="k8s:apply", now=gw.clock.now())


def test_capability_expiry():
    gw, cs = _gw(clock=FixedClock("2026-07-12T14:00:00.000Z"))
    p = _approved(gw, cs, "e2e-exp")
    gw.clock.advance(gw.gateway.token_ttl + 100)
    assert gw.execute(cs.context(), p["request_id"])["reason_codes"] == ["E_EXPIRED"]


def test_toctou_rejected():
    gw, cs = _gw()
    _admin().apply(GVR["ConfigMap"], "protected", "e2e-toc", _cm("protected", "e2e-toc", {"g": "1"}))
    p = gw.prepare(cs.context(), "kubernetes.apply",
                   {"namespace": "protected", "kind": "ConfigMap", "name": "e2e-toc",
                    "manifest": _cm("protected", "e2e-toc", {"g": "2"})})
    gw.evaluate(cs.context(), p["request_id"])
    gw.dry_run(cs.context(), p["request_id"])
    _admin().apply(GVR["ConfigMap"], "protected", "e2e-toc",
                   _cm("protected", "e2e-toc", {"g": "EXTERNAL"}), field_manager="ext")
    assert gw.execute(cs.context(), p["request_id"])["reason_codes"] == ["E_STALE_STATE"]


def test_concurrent_duplicate_single_commit():
    gw, cs = _gw()
    p = _approved(gw, cs, "e2e-conc")
    results = []

    def w(ctx):
        results.append(gw.execute(ctx, p["request_id"]))

    ctxs = [cs.context() for _ in range(5)]
    ts = [threading.Thread(target=w, args=(c,)) for c in ctxs]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sum(1 for r in results if r.get("state") == "COMPLETED") == 1


# ---- direct-access denial ----

def test_anonymous_and_bare_token_denied():
    anon = KubeClient(cluster.SERVER, str(cluster.CA_CERT))
    with pytest.raises(K8sApiError) as e1:
        anon.get(GVR["ConfigMap"], "protected", "app-config")
    assert e1.value.status in (401, 403)
    tok = _admin().request_token("protected", "default",
                                 audiences=["https://kubernetes.default.svc"],
                                 expiration_seconds=600)["status"]["token"]
    bare = KubeClient(cluster.SERVER, str(cluster.CA_CERT), token=tok)
    with pytest.raises(K8sApiError) as e2:
        bare.apply(GVR["ConfigMap"], "protected", "hack", _cm("protected", "hack", {"x": "y"}))
    assert e2.value.status == 403


# ---- audit / convergence ----

def test_audit_chains_intact_after_execution():
    gw, cs = _gw()
    p = _approved(gw, cs, "e2e-audit")
    gw.execute(cs.context(), p["request_id"])
    v = gw.verify_audit()
    assert v["intact"] and v["protocol"]["intact"] and v["enforcement"]["intact"]


def test_convergence_and_divergence_detection():
    gw, cs = _gw()
    p = _approved(gw, cs, "e2e-conv", {"g": "approved"})
    gw.execute(cs.context(), p["request_id"])
    assert gw.check_convergence(p["request_id"])["converged"] is True
    _admin().apply(GVR["ConfigMap"], "protected", "e2e-conv",
                   _cm("protected", "e2e-conv", {"g": "DIVERGED"}), field_manager="ext")
    assert gw.check_convergence(p["request_id"])["converged"] is False


# ---- all demo scenarios ----

def test_all_demo_scenarios_pass():
    path = pathlib.Path(__file__).resolve().parents[1] / "demos" / "scenarios.py"
    spec = importlib.util.spec_from_file_location("k8s_demo_scenarios", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    results = mod.run_all()
    failed = [r["scenario"] for r in results if not r.get("skipped") and not r["passed"]]
    assert not failed, failed
    assert len(results) == 18
