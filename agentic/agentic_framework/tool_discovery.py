"""
MCP Discovery / Tool Introspection (R8)

Lightweight developer-facing surface for listing, inspecting, and
filtering the MCP tools registered in a ``SafeMCPGateway``.

This module does **not** change governance or execution behaviour —
it is a read-only view over the existing tool registration state.

Usage::

    from agentic.agentic_framework.tool_discovery import ToolCatalog

    catalog = ToolCatalog.from_gateway(gateway)

    # List everything
    for tool in catalog.list_tools():
        print(tool.name, tool.risk_level)

    # Filter
    dangerous = catalog.find_tools(risk_level="destructive")
    needs_ok  = catalog.find_tools(requires_confirmation=True)
    search    = catalog.find_tools(name="search")
    file_ops  = catalog.find_tools(capability="destructive_file_operations")

    # Single lookup
    info = catalog.describe_tool("file_read")
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Discovered tool model
# ---------------------------------------------------------------------------


@dataclass
class DiscoveredTool:
    """Read-only snapshot of a registered MCP tool's metadata.

    All fields are JSON-safe primitives.
    """

    name: str = ""
    description: str = ""
    risk_level: str = ""            # ToolRiskLevel.value string
    capabilities: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    min_confidence: float = 0.5
    timeout_seconds: float = 30.0
    input_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-safe dict."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Tool catalog
# ---------------------------------------------------------------------------


class ToolCatalog:
    """Read-only catalog of MCP tools for developer introspection.

    Build from a ``SafeMCPGateway`` via :meth:`from_gateway`, or
    construct directly with a list of ``DiscoveredTool`` instances.

    This class is intentionally simple — no query languages, no
    remote registries, no fuzzy ranking.
    """

    def __init__(self, tools: Sequence[DiscoveredTool] = ()) -> None:
        self._tools: List[DiscoveredTool] = list(tools)
        self._by_name: Dict[str, DiscoveredTool] = {
            t.name: t for t in self._tools
        }

    # ----- construction helpers -----

    @classmethod
    def from_gateway(cls, gateway: Any) -> ToolCatalog:
        """Build a catalog from a ``SafeMCPGateway`` instance.

        Reads ``gateway.tool_definitions`` (the source of truth for
        registered tools) and converts each ``MCPToolDefinition`` into
        a ``DiscoveredTool``.
        """
        tool_defs = getattr(gateway, "tool_definitions", None)
        if not tool_defs or not isinstance(tool_defs, dict):
            return cls()

        discovered: List[DiscoveredTool] = []
        for _name, tdef in tool_defs.items():
            risk_val = tdef.risk_level
            if hasattr(risk_val, "value"):
                risk_val = risk_val.value
            discovered.append(DiscoveredTool(
                name=tdef.name,
                description=getattr(tdef, "description", ""),
                risk_level=str(risk_val),
                capabilities=list(getattr(tdef, "capabilities", [])),
                requires_confirmation=getattr(tdef, "requires_confirmation", False),
                min_confidence=getattr(tdef, "min_confidence", 0.5),
                timeout_seconds=getattr(tdef, "timeout_seconds", 30.0),
                input_schema=dict(getattr(tdef, "input_schema", {})),
            ))

        return cls(discovered)

    @classmethod
    def from_agent(cls, agent: Any) -> ToolCatalog:
        """Build a catalog from an ``AgenticLLMWrapper`` instance.

        Delegates to :meth:`from_gateway` using the agent's dispatcher's
        gateway, if available.  Returns an empty catalog when no
        dispatcher or gateway is configured.
        """
        dispatcher = getattr(agent, "dispatcher", None)
        if dispatcher is None:
            return cls()
        gateway = getattr(dispatcher, "gateway", None)
        if gateway is None:
            return cls()
        return cls.from_gateway(gateway)

    # ----- query API -----

    def list_tools(self) -> List[DiscoveredTool]:
        """Return all discovered tools (sorted by name)."""
        return sorted(self._tools, key=lambda t: t.name)

    def describe_tool(self, name: str) -> Optional[DiscoveredTool]:
        """Look up a single tool by exact name.

        Returns ``None`` if no tool with that name is registered.
        """
        return self._by_name.get(name)

    def find_tools(
        self,
        *,
        name: Optional[str] = None,
        risk_level: Optional[str] = None,
        capability: Optional[str] = None,
        requires_confirmation: Optional[bool] = None,
    ) -> List[DiscoveredTool]:
        """Filter tools by one or more criteria.

        All supplied criteria are AND-ed.  Omitted criteria match
        everything.

        Args:
            name: Substring match on tool name (case-insensitive).
            risk_level: Exact match on risk level value string.
            capability: Membership test — tool must list this capability.
            requires_confirmation: Exact bool match.

        Returns:
            List of matching ``DiscoveredTool`` instances, sorted by name.
        """
        results = self._tools

        if name is not None:
            lower = name.lower()
            results = [t for t in results if lower in t.name.lower()]

        if risk_level is not None:
            results = [t for t in results if t.risk_level == risk_level]

        if capability is not None:
            results = [t for t in results if capability in t.capabilities]

        if requires_confirmation is not None:
            results = [
                t for t in results
                if t.requires_confirmation == requires_confirmation
            ]

        return sorted(results, key=lambda t: t.name)

    # ----- serialisation -----

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the full catalog to a JSON-safe dict."""
        return {
            "tool_count": len(self._tools),
            "tools": [t.to_dict() for t in self.list_tools()],
        }

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"ToolCatalog(tools={len(self._tools)})"
