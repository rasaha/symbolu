"""MCP-facing enforcement integration for the agent-action admissibility gate.

An MCP-compatible tool gateway that intercepts every tool invocation, converts it
into the canonical action envelope, invokes the runtime gateway (``action_gateway``,
which consumes the frozen reference gate ``action_gate_ref``), and permits
execution only through a valid execution token and a broker-issued scoped
capability. MCP is an adapter here, not an architectural dependency — the same
server core is reusable by an HTTP/gRPC adapter.

No AI reasoning, no BCVF/USE/SCC, no production cloud credentials. See README.md.
"""

from __future__ import annotations

__version__ = "0.1.0-mcp"

from ._core import AG_VERSION  # noqa: F401
from .clientkit import ClientSession  # noqa: F401
from .context import RequestContext  # noqa: F401
from .escalation import EscalationQueue  # noqa: F401
from .server import McpGateway  # noqa: F401
from . import protocol, registry, simulation  # noqa: F401
