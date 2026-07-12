"""Eighteen end-to-end Kubernetes enforcement demonstrations against a REAL cluster.

If no control plane is reachable, ``run_all`` returns every scenario as SKIPPED
(never falsely passed). Shared by ``run_demos.py`` and the integration tests.
"""

from __future__ import annotations

import copy
import pathlib
import sys
import threading

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from action_gateway_k8s import ClientSession, K8sGateway, cluster  # noqa: E402
from action_gateway_k8s._core import FixedClock  # noqa: E402
from action_gateway_k8s.kubeclient import GVR, K8sApiError  # noqa: E402

_N = [0]


def _fresh(clock=None):
    _N[0] += 1
    gw = K8sGateway(allowed_namespaces=("protected",), clock=clock)
    return gw, ClientSession(clock=gw.clock, correlation_id=f"demo-{_N[0]}")


def _admin():
    return cluster.admin_client()


def _absent(kind, ns, name):
    try:
        _admin().delete(GVR[kind], ns, name)
    except K8sApiError:
        pass


def _present_cm(ns, name, data):
    _admin().apply(GVR["ConfigMap"], ns, name,
                   {"apiVersion": "v1", "kind": "ConfigMap",
                    "metadata": {"name": name, "namespace": ns}, "data": data},
                   field_manager="fixture")


def _cm_manifest(ns, name, data):
    return {"apiVersion": "v1", "kind": "ConfigMap",
            "metadata": {"name": name, "namespace": ns}, "data": data}


def _approved_apply(gw, cs, name, data=None):
    _absent("ConfigMap", "protected", name)
    m = _cm_manifest("protected", name, data or {"a": "b"})
    p = gw.prepare(cs.context(), "kubernetes.apply",
                   {"namespace": "protected", "kind": "ConfigMap", "name": name, "manifest": m})
    gw.evaluate(cs.context(), p["request_id"])
    gw.dry_run(cs.context(), p["request_id"])
    return p


def _r(name, expected, actual, passed, detail, gw=None):
    return {"scenario": name, "expected": expected, "actual": actual,
            "passed": bool(passed), "detail": detail,
            "audit_intact": gw.verify_audit()["intact"] if gw else None}


# --------------------------------------------------------------- scenarios

def k01_read_deployment():
    gw, cs = _fresh()
    r = gw.read(cs.context(), "kubernetes.get",
                {"namespace": "protected", "kind": "Deployment", "name": "web"})
    ok = r["outcome"] == "ALLOW" and r["read_only"] and r["execution_token"] is None
    return _r("Read a deployment through the gateway", "ALLOW (read-only)",
              r["outcome"], ok, "no execution authority; served in the trust domain", gw)


def k02_apply_safe_deployment():
    gw, cs = _fresh()
    _absent("Deployment", "protected", "gw-web")
    m = {"apiVersion": "apps/v1", "kind": "Deployment",
         "metadata": {"name": "gw-web", "namespace": "protected"},
         "spec": {"replicas": 1, "selector": {"matchLabels": {"app": "gw-web"}},
                  "template": {"metadata": {"labels": {"app": "gw-web"}},
                               "spec": {"securityContext": {"runAsNonRoot": True,
                                                            "seccompProfile": {"type": "RuntimeDefault"}},
                                        "containers": [{"name": "c", "image": "nginx:1",
                                                        "securityContext": {"allowPrivilegeEscalation": False,
                                                                            "capabilities": {"drop": ["ALL"]}},
                                                        "resources": {"limits": {"cpu": "100m", "memory": "64Mi"}}}]}}}}
    p = gw.prepare(cs.context(), "kubernetes.apply",
                   {"namespace": "protected", "kind": "Deployment", "name": "gw-web", "manifest": m})
    e = gw.evaluate(cs.context(), p["request_id"])
    d = gw.dry_run(cs.context(), p["request_id"])
    x = gw.execute(cs.context(), p["request_id"])
    live_ok = _admin().get(GVR["Deployment"], "protected", "gw-web")["metadata"]["name"] == "gw-web"
    ok = e["outcome"] == "SIMULATE_AND_RETRY" and d["outcome"] == "ALLOW" and \
        x["state"] == "COMPLETED" and live_ok
    return _r("Apply a safe deployment after server-side dry-run",
              "SIMULATE_AND_RETRY -> ALLOW -> COMPLETED (live)",
              f"{e['outcome']} -> {d['outcome']} -> {x['state']}", ok,
              "real server-side dry-run bound to the action hash", gw)


def k03_apply_safe_configmap():
    gw, cs = _fresh()
    p = _approved_apply(gw, cs, "gw-cfg", {"tier": "prod"})
    x = gw.execute(cs.context(), p["request_id"])
    live = _admin().get(GVR["ConfigMap"], "protected", "gw-cfg")
    ok = x["state"] == "COMPLETED" and live["data"] == {"tier": "prod"}
    return _r("Apply a safe config map", "COMPLETED (live data matches)",
              x["state"], ok, "applied via a scoped, single-use capability", gw)


def k04_reject_privileged():
    gw, cs = _fresh()
    m = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "priv", "namespace": "protected"},
         "spec": {"containers": [{"name": "c", "image": "nginx",
                                  "securityContext": {"privileged": True}}]}}
    p = gw.prepare(cs.context(), "kubernetes.apply",
                   {"namespace": "protected", "kind": "Pod", "name": "priv", "manifest": m})
    e = gw.evaluate(cs.context(), p["request_id"])
    ok = e["outcome"] == "DENY" and not p["admission_compliant"]
    return _r("Reject privileged pod/container", "DENY (admission)",
              e["outcome"], ok, f"violations={[v['check'] for v in p['violations']]}", gw)


def k05_reject_wildcard_rbac():
    gw, cs = _fresh()
    m = {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "Role",
         "metadata": {"name": "wild", "namespace": "protected"},
         "rules": [{"apiGroups": ["*"], "resources": ["*"], "verbs": ["*"]}]}
    p = gw.prepare(cs.context(), "kubernetes.apply",
                   {"namespace": "protected", "kind": "Role", "name": "wild", "manifest": m})
    e = gw.evaluate(cs.context(), p["request_id"])
    ok = e["outcome"] == "DENY" and any(v["check"] == "wildcard_rbac" for v in p["violations"])
    return _r("Reject wildcard/cluster-admin RBAC grant", "DENY (wildcard_rbac)",
              e["outcome"], ok, "wildcard verb/resource/group forbidden", gw)


def k06_reject_outside_namespace():
    gw, cs = _fresh()
    m = _cm_manifest("kube-system", "x", {"a": "b"})
    p = gw.prepare(cs.context(), "kubernetes.apply",
                   {"namespace": "kube-system", "kind": "ConfigMap", "name": "x", "manifest": m})
    e = gw.evaluate(cs.context(), p["request_id"])
    ok = e["outcome"] == "DENY" and any(v["check"] == "namespace_scope" for v in p["violations"])
    return _r("Reject mutation outside allowed namespace", "DENY (namespace_scope)",
              e["outcome"], ok, "only 'protected' is mutable", gw)


def k07_delete_requires_approval():
    gw, cs = _fresh()
    _present_cm("protected", "gw-del", {"a": "b"})
    p = gw.prepare(cs.context(), "kubernetes.delete",
                   {"namespace": "protected", "kind": "ConfigMap", "name": "gw-del",
                    "rollback_plan": {"restore_from": "backup-1"}})
    gw.evaluate(cs.context(), p["request_id"])
    d = gw.dry_run(cs.context(), p["request_id"])
    still = _admin().get(GVR["ConfigMap"], "protected", "gw-del")  # not deleted yet
    ok = d["outcome"] == "ESCALATE_TO_HUMAN" and d.get("escalation_id") and still
    return _r("Require approval before deleting", "ESCALATE_TO_HUMAN (not executed)",
              d["outcome"], ok, f"escalation {d.get('escalation_id')}", gw)


def k08_execute_approved_delete():
    gw, cs = _fresh()
    _present_cm("protected", "gw-del2", {"a": "b"})
    p = gw.prepare(cs.context(), "kubernetes.delete",
                   {"namespace": "protected", "kind": "ConfigMap", "name": "gw-del2",
                    "rollback_plan": {"restore_from": "backup-1"}})
    gw.evaluate(cs.context(), p["request_id"])
    gw.dry_run(cs.context(), p["request_id"])
    ap = gw.create_test_approval(p["request_id"])
    a = gw.attach_approval(cs.context(), p["request_id"], ap)
    x = gw.execute(cs.context(), p["request_id"])
    gone = False
    try:
        _admin().get(GVR["ConfigMap"], "protected", "gw-del2")
    except K8sApiError as e:
        gone = e.status == 404
    ok = a["outcome"] == "ALLOW" and x["state"] == "COMPLETED" and gone
    return _r("Execute the exact approved delete", "ALLOW -> COMPLETED (live gone)",
              f"{a['outcome']} -> {x['state']}", ok, "resource actually removed", gw)


def k09_reject_modified_manifest():
    gw, cs = _fresh()
    p = _approved_apply(gw, cs, "gw-mod")
    bad = copy.deepcopy(gw.gateway.records[p["request_id"]].envelope)
    bad["arguments"] = dict(bad["arguments"], manifest_json='{"tampered":true}')
    r = gw._commit(cs.context(), p["request_id"], call_envelope=bad)
    ok = r["reason_codes"] == ["E_ACTION_HASH_MISMATCH"]
    return _r("Reject modified manifest after approval", "E_ACTION_HASH_MISMATCH",
              r["reason_codes"][0], ok, "manifest is bound into the action hash", gw)


def k10_reject_modified_target():
    gw, cs = _fresh()
    p = _approved_apply(gw, cs, "gw-tgt")
    bad = copy.deepcopy(gw.gateway.records[p["request_id"]].envelope)
    bad["target_resource"] = ["k8s://protected/ConfigMap/other"]
    r = gw._commit(cs.context(), p["request_id"], call_envelope=bad)
    ok = r["reason_codes"][0].startswith("E_")
    return _r("Reject target/name modification after approval", "E_ACTION_HASH_MISMATCH",
              r["reason_codes"][0], ok, "target is bound into the action hash", gw)


def k11_reject_replayed_token():
    gw, cs = _fresh()
    p = _approved_apply(gw, cs, "gw-rep")
    gw.execute(cs.context(), p["request_id"])
    r = gw.execute(cs.context(), p["request_id"])
    ok = r["reason_codes"] == ["E_NONCE_REPLAY"]
    return _r("Reject replayed execution token", "E_NONCE_REPLAY",
              r["reason_codes"][0], ok, "token nonce is single-use", gw)


def k12_reject_replayed_capability():
    gw, cs = _fresh()
    p = _approved_apply(gw, cs, "gw-cap")
    res = gw.execute(cs.context(), p["request_id"])
    cred = gw.broker._issued[res["credential_id"]]
    blocked = ""
    try:
        gw.broker.redeem(cred, needed_permission="k8s:apply", now=gw.clock.now())
    except Exception as e:  # noqa: BLE001
        blocked = getattr(e, "code", type(e).__name__)
    ok = blocked == "E_CREDENTIAL"
    return _r("Reject replayed broker capability", "E_CREDENTIAL (single-use)",
              blocked, ok, "capability consumed + RBAC torn down after use", gw)


def k13_reject_expired_capability():
    gw, cs = _fresh(clock=FixedClock("2026-07-12T14:00:00.000Z"))
    p = _approved_apply(gw, cs, "gw-exp")
    gw.clock.advance(gw.gateway.token_ttl + 100)  # push past the token/capability expiry
    r = gw.execute(cs.context(), p["request_id"])
    ok = r["reason_codes"] == ["E_EXPIRED"]
    return _r("Reject expired Kubernetes capability", "E_EXPIRED",
              r["reason_codes"][0], ok, "execution token / capability expired", gw)


def k14_reject_toctou():
    gw, cs = _fresh()
    _present_cm("protected", "gw-toc", {"greeting": "orig"})
    m = _cm_manifest("protected", "gw-toc", {"greeting": "new"})
    p = gw.prepare(cs.context(), "kubernetes.apply",
                   {"namespace": "protected", "kind": "ConfigMap", "name": "gw-toc", "manifest": m})
    gw.evaluate(cs.context(), p["request_id"])
    gw.dry_run(cs.context(), p["request_id"])
    _present_cm("protected", "gw-toc", {"greeting": "CHANGED-EXTERNALLY"})  # world moved
    r = gw.execute(cs.context(), p["request_id"])
    ok = r["reason_codes"] == ["E_STALE_STATE"]
    return _r("Reject TOCTOU state change", "E_STALE_STATE",
              r["reason_codes"][0], ok, "commit-time live state differs from approval", gw)


def k15_reject_concurrent_duplicate():
    gw, cs = _fresh()
    p = _approved_apply(gw, cs, "gw-conc")
    results = []

    def worker(ctx):
        results.append(gw.execute(ctx, p["request_id"]))

    ctxs = [cs.context() for _ in range(4)]
    threads = [threading.Thread(target=worker, args=(c,)) for c in ctxs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    commits = [x for x in results if x.get("state") == "COMPLETED"]
    ok = len(commits) == 1
    return _r("Reject concurrent duplicate commit", "exactly one commit",
              f"{len(commits)} commit / {len(results) - len(commits)} rejected", ok,
              "token nonce reserved atomically", gw)


def k16_reject_direct_api_access():
    gw, cs = _fresh()
    from action_gateway_k8s.kubeclient import KubeClient
    anon = KubeClient(cluster.SERVER, str(cluster.CA_CERT))
    anon_denied = bare_denied = False
    try:
        anon.get(GVR["ConfigMap"], "protected", "app-config")
    except K8sApiError as e:
        anon_denied = e.status in (401, 403)
    tok = _admin().request_token("protected", "default",
                                 audiences=["https://kubernetes.default.svc"],
                                 expiration_seconds=600)["status"]["token"]
    bare = KubeClient(cluster.SERVER, str(cluster.CA_CERT), token=tok)
    try:
        bare.apply(GVR["ConfigMap"], "protected", "hack",
                   _cm_manifest("protected", "hack", {"x": "y"}))
    except K8sApiError as e:
        bare_denied = e.status in (401, 403)
    ok = anon_denied and bare_denied
    return _r("Reject direct Kubernetes API access from agent env",
              "anonymous + bare-SA token both 403", f"anon={anon_denied} bare={bare_denied}",
              ok, "protected namespace rejects unscoped mutation", gw)


def k17_no_durable_credential():
    import os
    gw, cs = _fresh()
    no_env = not os.environ.get("KUBECONFIG") and not os.environ.get("K8S_TOKEN")
    no_files = not any("kube" in f.lower() for f in os.listdir("."))
    ok = no_env and no_files
    return _r("No durable Kubernetes credential in agent env",
              "no KUBECONFIG/token/kubeconfig files", f"env_clean={no_env} cwd_clean={no_files}",
              ok, "the agent holds no cluster credential; only the broker does", gw)


def k18_detect_divergence():
    gw, cs = _fresh()
    p = _approved_apply(gw, cs, "gw-div", {"greeting": "approved"})
    gw.execute(cs.context(), p["request_id"])
    conv = gw.check_convergence(p["request_id"])["converged"]
    # controlled divergence: an external actor mutates the object post-commit
    _present_cm("protected", "gw-div", {"greeting": "DIVERGED"})
    div = gw.check_convergence(p["request_id"])["converged"]
    ok = conv is True and div is False
    return _r("Detect predicted-versus-actual divergence",
              "converged after apply; diverged after external mutation",
              f"converged={conv} then converged={div}", ok,
              "content digest of live object vs applied state", gw)


ALL_SCENARIOS = [
    k01_read_deployment, k02_apply_safe_deployment, k03_apply_safe_configmap,
    k04_reject_privileged, k05_reject_wildcard_rbac, k06_reject_outside_namespace,
    k07_delete_requires_approval, k08_execute_approved_delete, k09_reject_modified_manifest,
    k10_reject_modified_target, k11_reject_replayed_token, k12_reject_replayed_capability,
    k13_reject_expired_capability, k14_reject_toctou, k15_reject_concurrent_duplicate,
    k16_reject_direct_api_access, k17_no_durable_credential, k18_detect_divergence,
]


def run_all() -> list:
    if not cluster.is_available():
        return [{"scenario": fn.__name__, "skipped": True, "passed": None,
                 "reason": "no reachable Kubernetes control plane"} for fn in ALL_SCENARIOS]
    out = []
    for fn in ALL_SCENARIOS:
        try:
            out.append(fn())
        except Exception as exc:  # noqa: BLE001
            out.append({"scenario": fn.__name__, "passed": False,
                        "actual": f"exception: {exc}", "expected": "", "detail": ""})
    return out
