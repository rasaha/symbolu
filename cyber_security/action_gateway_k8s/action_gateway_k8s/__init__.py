"""Bypass-resistant Kubernetes enforcement deployment.

Proves that an autonomous agent cannot modify a protected Kubernetes target
except through the admissibility gateway and a broker-issued, short-lived,
action-bound credential — against a REAL local disposable control plane (etcd +
kube-apiserver). Reuses the frozen gate (``action_gate_ref``), the runtime gateway
(``action_gateway``), and the MCP mapping/audit patterns (``action_gateway_mcp``).

No AI/BCVF/USE/SCC, no cloud providers. See README.md.
"""

from __future__ import annotations

__version__ = "0.1.0-k8s"

from ._core import AG_VERSION, MCP_VERSION  # noqa: F401
from . import cluster  # noqa: F401
from .broker import KubernetesCredentialBroker  # noqa: F401
from .adapter import KubernetesAdapter  # noqa: F401
from .kubeclient import KubeClient, GVR  # noqa: F401
from .server import K8sGateway, K8sStateOracle  # noqa: F401
from action_gateway_mcp import ClientSession, RequestContext  # noqa: F401
