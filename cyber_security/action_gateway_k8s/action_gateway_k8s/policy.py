"""Signed Kubernetes policy bundle + deterministic admission checks.

The frozen gate decides admissibility; Kubernetes-specific risk checks are
expressed as REQUIRED EVIDENCE the gate demands (they never bypass the gate). The
custom rule set (built with the frozen rule schema + operators) requires, per
operation:

  * ``kubernetes_admission`` evidence (hard) — produced only when the deterministic
    admission checks find no violation;
  * ``simulation`` evidence (server-side dry-run) via REQUIRE_SIMULATION;
  * for deletes: ``rollback_attestation`` evidence (hard) + dual-control approval.

A non-compliant manifest withholds the admission evidence, so the gate itself
DENYs (hard MUST_HAVE unmet). Manifest-level violations (privileged, hostNetwork)
are ALSO rejected by the real apiserver at dry-run — defence in depth.
"""

from __future__ import annotations

import json

from ._core import ref_evidence, ref_hashing, ref_policy

# Kubernetes rule set, in the frozen compact rule schema (operators only; no new facts)
K8S_RULES = [
    {"id": "K8S_DEPLOY", "operation": "DEPLOY", "effects": [
        {"op": "MUST_HAVE", "evidence": "kubernetes_admission", "hard": True},
        {"op": "REQUIRE_SIMULATION", "fidelity": "HIGH"},
        {"op": "ALLOW"},
    ]},
    {"id": "K8S_DELETE", "operation": "DB_DELETE", "effects": [
        {"op": "MUST_HAVE", "evidence": "kubernetes_admission", "hard": True},
        {"op": "MUST_HAVE", "evidence": "rollback_attestation", "hard": True},
        {"op": "REQUIRE_SIMULATION", "fidelity": "HIGH"},
        {"op": "REQUIRE_APPROVER", "approver_policy": "dual_control"},
        {"op": "ALLOW"},
    ]},
]

# human-readable summary of the admission checks (documented in README)
ADMISSION_CHECKS = (
    "namespace_scope", "cluster_scope_rbac", "wildcard_rbac", "privileged_container",
    "host_namespaces", "host_path", "missing_resource_limits", "public_service",
)


def build_bundle(*, allowed_namespaces=("protected",)):
    """Unsigned Kubernetes policy bundle (the runtime gateway signs it)."""
    # version must be semver (schema requires \d+\.\d+\.\d+); the k8s ruleset is
    # identified by its signed hash + metadata name, not a non-semver label.
    bundle = ref_policy.build_bundle(rules=K8S_RULES, version="1.0.0")
    bundle["metadata"]["name"] = "reference-kubernetes"
    bundle["kubernetes"] = {"allowed_namespaces": sorted(allowed_namespaces),
                            "admission_checks": list(ADMISSION_CHECKS)}
    return bundle


# ---------------------------------------------------------------- admission checks

def _containers(manifest):
    spec = manifest.get("spec", {})
    pod = spec.get("template", {}).get("spec", spec) if manifest.get("kind") == "Deployment" else spec
    return pod, pod.get("containers", []) or []


def admission_check(env_args, manifest, *, allowed_namespaces) -> list:
    """Deterministic policy checks. Returns a list of violation dicts (empty = OK)."""
    v = []
    ns, kind = env_args["namespace"], env_args["kind"]
    if ns not in allowed_namespaces:
        v.append({"check": "namespace_scope",
                  "detail": f"mutation of namespace {ns!r} outside allowed {sorted(allowed_namespaces)}"})
    if kind in ("ClusterRole", "ClusterRoleBinding"):
        v.append({"check": "cluster_scope_rbac", "detail": "cluster-scoped RBAC forbidden"})
    if manifest is not None:
        if kind in ("Role", "ClusterRole"):
            for rule in manifest.get("rules", []):
                if "*" in rule.get("verbs", []) or "*" in rule.get("resources", []) \
                        or "*" in rule.get("apiGroups", []):
                    v.append({"check": "wildcard_rbac", "detail": "wildcard verb/resource/group"})
                    break
        if kind in ("RoleBinding", "ClusterRoleBinding"):
            if manifest.get("roleRef", {}).get("name") in ("cluster-admin", "admin", "edit"):
                v.append({"check": "wildcard_rbac",
                          "detail": f"binds privileged role {manifest['roleRef']['name']}"})
        if kind in ("Deployment", "Pod"):
            pod, containers = _containers(manifest)
            if pod.get("hostNetwork") or pod.get("hostPID") or pod.get("hostIPC"):
                v.append({"check": "host_namespaces", "detail": "hostNetwork/PID/IPC set"})
            for vol in pod.get("volumes", []) or []:
                if "hostPath" in vol:
                    v.append({"check": "host_path", "detail": "hostPath volume"})
            for c in containers:
                sc = c.get("securityContext", {}) or {}
                if sc.get("privileged"):
                    v.append({"check": "privileged_container",
                              "detail": f"container {c.get('name')} privileged"})
                if not (c.get("resources", {}) or {}).get("limits"):
                    v.append({"check": "missing_resource_limits",
                              "detail": f"container {c.get('name')} has no resource limits"})
        if kind == "Service" and manifest.get("spec", {}).get("type") in ("LoadBalancer", "NodePort"):
            v.append({"check": "public_service",
                      "detail": f"public service type {manifest['spec']['type']}"})
    return v


def admission_evidence(action_hash, env_args, manifest, *, allowed_namespaces, clock):
    """Return (evidence_or_None, violations). Evidence produced only when compliant."""
    violations = admission_check(env_args, manifest, allowed_namespaces=allowed_namespaces)
    if violations:
        return None, violations
    ev = ref_evidence.build_evidence(
        bound_to=action_hash, producer="k8s-admission/1.0", generated_at=clock.now(),
        valid_until=clock.plus(900), evidence_version="1", kind="kubernetes_admission",
        fidelity_or_confidence="HIGH",
        content={"compliant": True, "checks": list(ADMISSION_CHECKS),
                 "namespace": env_args["namespace"], "kind": env_args["kind"],
                 "name": env_args["name"]})
    return ev, []


def rollback_evidence(action_hash, rollback_plan, *, clock):
    if not rollback_plan:
        return None
    digest = ref_hashing.domain_digest(
        "EVIDENCE", json.dumps(rollback_plan, sort_keys=True).encode("utf-8"))
    return ref_evidence.build_evidence(
        bound_to=action_hash, producer="rollback-checker/1.0", generated_at=clock.now(),
        valid_until=clock.plus(900), evidence_version="1", kind="rollback_attestation",
        fidelity_or_confidence="HIGH",
        content={"plan_digest": digest, "verified": True})
