"""Reuse the frozen gate, runtime gateway, MCP, and Kubernetes packages."""

from __future__ import annotations

import pathlib
import sys

_CS = pathlib.Path(__file__).resolve().parents[2]
for _d in ("action_gateway", "action_gateway_mcp", "action_gateway_k8s"):
    p = _CS / _d
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from action_gateway._ref import errors as ref_errors  # noqa: E402,F401
from action_gateway._ref import hashing as ref_hashing  # noqa: E402,F401
from action_gateway_k8s.kubeclient import GVR, KubeClient, K8sApiError  # noqa: E402,F401
