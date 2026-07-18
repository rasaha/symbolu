"""Kubernetes-layer error codes (mapping/admission/cluster concerns).

Enforcement failures from the runtime gateway or frozen harness (token replay,
expiry, action-hash mismatch, scope violation, policy mismatch, stale state,
credential errors) propagate unchanged.
"""

from __future__ import annotations

from ._core import ref_errors

GateError = ref_errors.GateError


class K8sGatewayError(Exception):
    code = "E_K8S"

    def __init__(self, message: str = ""):
        super().__init__(f"{self.code}: {message}" if message else self.code)


class UnknownKindError(K8sGatewayError):
    code = "E_K8S_UNKNOWN_KIND"


class UnknownNamespaceError(K8sGatewayError):
    code = "E_K8S_UNKNOWN_NAMESPACE"


class BadK8sArgumentError(K8sGatewayError):
    code = "E_K8S_BAD_ARGUMENT"


class ClusterUnavailableError(K8sGatewayError):
    code = "E_K8S_CLUSTER_UNAVAILABLE"


class AdmissionViolation(K8sGatewayError):
    code = "E_K8S_ADMISSION"
