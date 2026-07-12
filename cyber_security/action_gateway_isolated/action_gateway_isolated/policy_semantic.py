"""Strengthened Kubernetes semantic policy for the red-team experiment.

Deterministic checks run by BOTH the gateway (to gate the decision) and,
independently, the broker (defence in depth before the privileged write). A
violation withholds the admission evidence, so the frozen gate DENYs — the checks
feed the gate, never bypass it.

Distinguished invariant layers (documented in README):
  * gateway invariant       — these deterministic checks + the frozen gate
  * admission-controller     — the real apiserver PodSecurity at dry-run/commit
  * broker scope restriction — RBAC resourceNames/verbs on the minted credential
  * runtime/network control  — netns egress (documented limits)
"""

from __future__ import annotations

import re

_DIGEST_IMAGE = re.compile(r"^registry\.example\.com/[\w./-]+@sha256:[0-9a-f]{64}$")
_DANGEROUS_VERBS = {"*", "bind", "escalate", "impersonate"}
_POWERFUL_ROLES = {"cluster-admin", "admin", "edit"}
_PROTECTED_NAMES = {"gatekeeper", "admission-policy", "monitoring", "audit-webhook"}


def _pod_spec(manifest):
    if manifest.get("kind") == "Deployment":
        return manifest.get("spec", {}).get("template", {}).get("spec", {}) or {}
    return manifest.get("spec", {}) or {}


def check(env, manifest, *, allowed_namespaces, backup_exists=lambda n: False) -> list:
    """Return a list of violation dicts (empty == compliant)."""
    v = []
    ns, kind, name = env["namespace"], env["kind"], env["name"]

    if ns not in allowed_namespaces:
        v.append({"check": "namespace_scope", "detail": f"ns {ns} not allowed"})
    if name in _PROTECTED_NAMES:
        v.append({"check": "protected_resource", "detail": f"{name} is a protected control"})
    if kind in ("ClusterRole", "ClusterRoleBinding"):
        v.append({"check": "cluster_scope_rbac", "detail": "cluster-scoped RBAC forbidden"})

    if manifest is None:
        return v

    if kind in ("Role", "ClusterRole"):
        for rule in manifest.get("rules", []):
            if _DANGEROUS_VERBS & set(rule.get("verbs", [])):
                v.append({"check": "dangerous_verb", "detail": "bind/escalate/impersonate/*"})
            if "*" in rule.get("resources", []) or "*" in rule.get("apiGroups", []):
                v.append({"check": "wildcard_rbac", "detail": "wildcard resource/group"})
    if kind in ("RoleBinding", "ClusterRoleBinding"):
        if manifest.get("roleRef", {}).get("name") in _POWERFUL_ROLES:
            v.append({"check": "powerful_rolebinding",
                      "detail": f"binds {manifest['roleRef']['name']}"})

    if kind in ("Deployment", "Pod"):
        spec = _pod_spec(manifest)
        if spec.get("hostNetwork") or spec.get("hostPID") or spec.get("hostIPC"):
            v.append({"check": "host_namespaces", "detail": "hostNetwork/PID/IPC"})
        for vol in spec.get("volumes", []) or []:
            if "hostPath" in vol:
                v.append({"check": "host_path", "detail": "hostPath volume"})
            if "secret" in vol:
                v.append({"check": "secret_mount", "detail": f"secret volume {vol.get('name')}"})
        for c in spec.get("containers", []) or []:
            sc = c.get("securityContext", {}) or {}
            if sc.get("privileged"):
                v.append({"check": "privileged", "detail": c.get("name")})
            img = c.get("image", "")
            if not _DIGEST_IMAGE.match(img):
                v.append({"check": "image_provenance",
                          "detail": f"image not a pinned allowed digest: {img}"})
            for e in c.get("env", []) or []:
                if isinstance(e, dict) and "secretKeyRef" in (e.get("valueFrom") or {}):
                    v.append({"check": "secret_env", "detail": f"env {e.get('name')} from secret"})
    if kind == "Service" and manifest.get("spec", {}).get("type") in ("LoadBalancer", "NodePort"):
        v.append({"check": "public_service", "detail": manifest["spec"]["type"]})
    return v


def rollback_verified(rollback_plan, *, backup_exists) -> bool:
    """Rollback evidence must reference an ACTUAL existing backup, not a non-empty dict."""
    if not isinstance(rollback_plan, dict):
        return False
    ref = rollback_plan.get("backup_ref")
    return bool(ref) and backup_exists(ref)
