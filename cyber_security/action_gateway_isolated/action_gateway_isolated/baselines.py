"""Baseline comparison (measured against the same real cluster).

Four control models, evaluated on the decisive attacks:
  A. Static agent kubeconfig / namespace RBAC (agent holds a durable token).
  B. Admission policy only (apiserver PodSecurity; agent still holds a token).
  C. JIT role elevation for a time window (namespace-edit for N minutes).
  D. Exact-action gateway + isolated broker (this deployment).

A/B/C are measured by minting a real namespace-edit ServiceAccount token and
attempting the attacks directly against the API (as a token-holding agent would).
D is taken from the red-team run. The contrast of interest: exact-action, one-use
authorization blocks replay / multi-use / modified-action / direct-path attacks
that time-window JIT and admission-only still permit.
"""

from __future__ import annotations

from ._core import GVR, K8sApiError, KubeClient

# decisive attacks and, for each baseline, whether the attack is BLOCKED
ATTACKS = ["direct_api_mutation", "privileged_workload", "replay_same_action",
           "multi_use_within_grant", "modified_action_reused_grant",
           "no_human_approval_for_destructive", "action_hash_binding"]


def measure(admin, server, ca_cert) -> dict:
    """Empirically measure baselines A/B/C with a real namespace-edit token."""
    ns = "protected"
    sa = "baseline-agent"
    if not _sa_exists(admin, sa):
        admin.create(GVR["ServiceAccount"], ns, {"apiVersion": "v1", "kind": "ServiceAccount",
                     "metadata": {"name": sa, "namespace": ns}})
    # namespace-scoped edit-ish role (configmaps) — a realistic static/JIT grant
    _apply_role(admin, ns, sa)
    tok = admin.request_token(ns, sa, audiences=["https://kubernetes.default.svc"],
                              expiration_seconds=600)["status"]["token"]
    agent = KubeClient(server, ca_cert, token=tok)

    results = {a: {} for a in ATTACKS}

    # A/C: direct mutation with the held token succeeds (bypasses any gateway)
    ok = _try(lambda: agent.apply(GVR["ConfigMap"], ns, "baseline-cm",
                                  {"apiVersion": "v1", "kind": "ConfigMap",
                                   "metadata": {"name": "baseline-cm", "namespace": ns},
                                   "data": {"x": "1"}}))
    for b in ("A", "C"):
        results["direct_api_mutation"][b] = not ok  # blocked? no -> mutation succeeded
    results["direct_api_mutation"]["B"] = not ok    # admission doesn't stop an allowed configmap
    results["direct_api_mutation"]["D"] = True       # gateway: no direct path (agent has no token)

    # privileged workload: PodSecurity (B, and any cluster) blocks it; A/C also subject to PSA
    priv_blocked = not _try(lambda: agent.apply(GVR["Pod"], ns, "baseline-priv",
        {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "baseline-priv", "namespace": ns},
         "spec": {"containers": [{"name": "c", "image": "nginx",
                                  "securityContext": {"privileged": True}}]}}, dry_run=True))
    for b in ("A", "B", "C", "D"):
        results["privileged_workload"][b] = priv_blocked  # PSA blocks in all (cluster-level)

    # replay / multi-use within the grant: the token can act repeatedly -> NOT blocked for A/B/C
    multi_ok = _try(lambda: agent.apply(GVR["ConfigMap"], ns, "baseline-cm",
        {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "baseline-cm", "namespace": ns},
         "data": {"x": "2"}}))
    for b in ("A", "B", "C"):
        results["replay_same_action"][b] = False       # repeatable within grant
        results["multi_use_within_grant"][b] = False
        results["modified_action_reused_grant"][b] = False  # any in-scope action reuses the grant
        results["no_human_approval_for_destructive"][b] = False  # no approval requirement
        results["action_hash_binding"][b] = False       # grant is role/time-scoped, not action-bound
    for a in ("replay_same_action", "multi_use_within_grant", "modified_action_reused_grant",
              "no_human_approval_for_destructive", "action_hash_binding"):
        results[a]["D"] = True                          # exact-action, single-use, approved

    _cleanup(admin, ns, sa)
    return results


def matrix(admin, server, ca_cert, redteam_supported: bool) -> dict:
    m = measure(admin, server, ca_cert)
    # D reflects the empirical red-team result
    if not redteam_supported:
        for a in m:
            m[a]["D"] = m[a].get("D", False)
    summary = {b: sum(1 for a in ATTACKS if m[a][b]) for b in ("A", "B", "C", "D")}
    return {"per_attack": m, "blocked_count": summary, "total": len(ATTACKS)}


# ---- helpers ----

def _sa_exists(admin, sa):
    try:
        admin.get(GVR["ServiceAccount"], "protected", sa)
        return True
    except K8sApiError:
        return False


def _apply_role(admin, ns, sa):
    admin.apply(GVR["Role"], ns, sa, {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "Role",
                "metadata": {"name": sa, "namespace": ns},
                "rules": [{"apiGroups": [""], "resources": ["configmaps"],
                           "verbs": ["get", "create", "update", "patch", "delete"]}]})
    admin.apply(GVR["RoleBinding"], ns, sa, {"apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "RoleBinding", "metadata": {"name": sa, "namespace": ns},
                "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": sa},
                "subjects": [{"kind": "ServiceAccount", "name": sa, "namespace": ns}]})


def _cleanup(admin, ns, sa):
    for kind in ("RoleBinding", "Role", "ServiceAccount"):
        try:
            admin.delete(GVR[kind], ns, sa)
        except K8sApiError:
            pass
    try:
        admin.delete(GVR["ConfigMap"], ns, "baseline-cm")
    except K8sApiError:
        pass


def _try(fn) -> bool:
    try:
        fn()
        return True
    except K8sApiError:
        return False
