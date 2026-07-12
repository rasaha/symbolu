"""Unit tests that do NOT require a cluster (mapping, admission, client paths)."""

from __future__ import annotations

import pytest

from action_gateway_k8s import mapping, policy
from action_gateway_k8s.errors import (
    BadK8sArgumentError, UnknownKindError, UnknownNamespaceError,
)
from action_gateway_k8s.kubeclient import GVR
from action_gateway_mcp import ClientSession
from action_gateway_k8s._core import FixedClock


def _ctx():
    return ClientSession(clock=FixedClock("2026-07-12T14:00:00.000Z")).context()


# ---- mapping / fail-closed ----

def test_registry_exposes_expected_tools():
    assert set(mapping.EXPOSED_TOOLS) == {
        "kubernetes.get", "kubernetes.inspect_rbac", "kubernetes.apply", "kubernetes.delete"}


def test_unknown_tool_fails_closed():
    with pytest.raises(UnknownKindError):
        mapping.get_spec("kubernetes.nuke")


def test_unknown_kind_fails_closed():
    spec = mapping.get_spec("kubernetes.apply")
    with pytest.raises(UnknownKindError):
        mapping.validate_and_extract(spec, {"namespace": "protected", "kind": "Frobnicate",
                                            "name": "x", "manifest": {}})


def test_unknown_namespace_fails_closed():
    spec = mapping.get_spec("kubernetes.apply")
    with pytest.raises(UnknownNamespaceError):
        mapping.validate_and_extract(spec, {"namespace": "nope", "kind": "ConfigMap",
                                            "name": "x", "manifest": {}})


def test_manifest_coordinate_smuggling_rejected():
    spec = mapping.get_spec("kubernetes.apply")
    m = {"apiVersion": "v1", "kind": "ConfigMap",
         "metadata": {"name": "OTHER", "namespace": "protected"}}
    with pytest.raises(BadK8sArgumentError):
        mapping.validate_and_extract(spec, {"namespace": "protected", "kind": "ConfigMap",
                                            "name": "x", "manifest": m})


def test_to_tool_request_binds_manifest_digest_and_target():
    spec = mapping.get_spec("kubernetes.apply")
    m = {"apiVersion": "v1", "kind": "ConfigMap",
         "metadata": {"name": "x", "namespace": "protected"}, "data": {"a": "b"}}
    req = mapping.to_tool_request(spec, {"namespace": "protected", "kind": "ConfigMap",
                                         "name": "x", "manifest": m}, _ctx(),
                                  current_state_hash="")
    assert req.target == ["k8s://protected/ConfigMap/x"]
    assert req.args["verb"] == "apply"
    assert "manifest_digest" in req.args and "manifest_json" in req.args
    assert req.permissions == ["k8s:apply"]


# ---- admission checks (deterministic) ----

def test_admission_passes_compliant():
    ev, viol = policy.admission_evidence(
        "a" * 64, {"namespace": "protected", "kind": "ConfigMap", "name": "x"}, {},
        allowed_namespaces={"protected"}, clock=FixedClock())
    assert ev is not None and viol == []
    assert ev["payload"]["kind"] == "kubernetes_admission"


def test_admission_flags_privileged():
    m = {"kind": "Pod", "spec": {"containers": [
        {"name": "c", "securityContext": {"privileged": True}}]}}
    v = policy.admission_check({"namespace": "protected", "kind": "Pod", "name": "p"}, m,
                              allowed_namespaces={"protected"})
    checks = {x["check"] for x in v}
    assert "privileged_container" in checks and "missing_resource_limits" in checks


def test_admission_flags_wildcard_rbac():
    m = {"kind": "Role", "rules": [{"apiGroups": ["*"], "resources": ["*"], "verbs": ["*"]}]}
    v = policy.admission_check({"namespace": "protected", "kind": "Role", "name": "r"}, m,
                              allowed_namespaces={"protected"})
    assert any(x["check"] == "wildcard_rbac" for x in v)


def test_admission_flags_outside_namespace():
    v = policy.admission_check({"namespace": "kube-system", "kind": "ConfigMap", "name": "x"},
                              {"kind": "ConfigMap"}, allowed_namespaces={"protected"})
    assert any(x["check"] == "namespace_scope" for x in v)


def test_admission_flags_public_service():
    m = {"kind": "Service", "spec": {"type": "LoadBalancer"}}
    v = policy.admission_check({"namespace": "protected", "kind": "Service", "name": "s"}, m,
                              allowed_namespaces={"protected"})
    assert any(x["check"] == "public_service" for x in v)


def test_admission_withholds_evidence_on_violation():
    m = {"kind": "Pod", "spec": {"containers": [{"name": "c",
         "securityContext": {"privileged": True}}]}}
    ev, viol = policy.admission_evidence(
        "a" * 64, {"namespace": "protected", "kind": "Pod", "name": "p"}, m,
        allowed_namespaces={"protected"}, clock=FixedClock())
    assert ev is None and viol


# ---- policy bundle ----

def test_k8s_policy_bundle_has_operation_rules():
    b = policy.build_bundle(allowed_namespaces=("protected",))
    ops = {r["operation"] for r in b["rules"]}
    assert ops == {"DEPLOY", "DB_DELETE"}


# ---- kubeclient path building (no network) ----

def test_gvr_paths():
    assert GVR["ConfigMap"].object_path("protected", "x") == "/api/v1/namespaces/protected/configmaps/x"
    assert GVR["Deployment"].object_path("protected", "web") == \
        "/apis/apps/v1/namespaces/protected/deployments/web"
    assert GVR["ClusterRole"].namespaced is False
