"""Action Gateway — runtime enforcement path for the frozen admissibility gate.

Transport-agnostic runtime that sits between an autonomous agent and external
tools. It consumes tool/action requests, invokes the frozen Stage-1 reference
gate (``action_gate_ref``) to decide admissibility, and enforces that decision:
nothing executes without a verified, single-use execution token and a scoped,
broker-minted credential. No AI reasoning, no BCVF/USE/SCC, no real cloud
integrations — see README.md.
"""

from __future__ import annotations

__version__ = "0.1.0-gw"

from ._ref import REF_VERSION  # noqa: F401
from .adapters import (  # noqa: F401
    FilesystemTool, HTTPTool, IamTool, KubernetesTool, MonitoringTool,
    ShellCommandTool, TerraformTool, ToolAdapter, default_adapters,
)
from .broker import CredentialBroker, MockCredentialBroker, ScopedCredential  # noqa: F401
from .clock import FixedClock, RealClock  # noqa: F401
from .gateway import Gateway, MockStateOracle, Record  # noqa: F401
from .mapping import ToolRequest, build_envelope  # noqa: F401
from . import state  # noqa: F401
