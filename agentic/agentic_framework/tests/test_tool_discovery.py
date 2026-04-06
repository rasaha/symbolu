"""
Tests for MCP Discovery / Tool Introspection (R8)

Validates:
1. Listed tools reflect registered MCP tools accurately
2. Metadata fields are surfaced correctly
3. Filtering by capability works
4. Filtering by risk level works
5. Filtering by requires_confirmation works
6. Name substring search works
7. Describe/get-by-name works
8. Serialization is stable / JSON-safe
9. No execution behavior changed
"""

import json

import pytest

from agentic.agentic_framework.mcp_gateway import (
    MCPToolDefinition,
    SafeMCPGateway,
    ToolRiskLevel,
    MockMCPClient,
    create_mock_mcp_gateway,
)
from agentic.agentic_framework.tool_discovery import DiscoveredTool, ToolCatalog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool_def(
    name: str,
    description: str = "",
    risk_level: ToolRiskLevel = ToolRiskLevel.READ_ONLY,
    capabilities: list | None = None,
    requires_confirmation: bool = False,
    min_confidence: float = 0.5,
    timeout_seconds: float = 30.0,
    input_schema: dict | None = None,
) -> MCPToolDefinition:
    return MCPToolDefinition(
        name=name,
        description=description,
        risk_level=risk_level,
        capabilities=capabilities or [],
        requires_confirmation=requires_confirmation,
        min_confidence=min_confidence,
        timeout_seconds=timeout_seconds,
        input_schema=input_schema or {},
    )


def _make_gateway_with_tools(tool_defs: list[MCPToolDefinition]) -> SafeMCPGateway:
    """Create a gateway with *only* the supplied tool definitions."""
    gateway = create_mock_mcp_gateway()
    # Clear any pre-registered tools so tests control the exact set
    gateway.tool_definitions.clear()
    for tdef in tool_defs:
        gateway.tool_definitions[tdef.name] = tdef
    return gateway


def _sample_tools() -> list[MCPToolDefinition]:
    return [
        _make_tool_def(
            "file_read",
            description="Read a file from disk",
            risk_level=ToolRiskLevel.READ_ONLY,
            capabilities=["file_operations"],
        ),
        _make_tool_def(
            "file_write",
            description="Write content to a file",
            risk_level=ToolRiskLevel.WRITE,
            capabilities=["file_operations", "destructive_file_operations"],
            requires_confirmation=True,
            min_confidence=0.8,
            timeout_seconds=60.0,
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        ),
        _make_tool_def(
            "web_search",
            description="Search the web",
            risk_level=ToolRiskLevel.READ_ONLY,
            capabilities=["network"],
        ),
        _make_tool_def(
            "shell_exec",
            description="Execute a shell command",
            risk_level=ToolRiskLevel.EXECUTE,
            capabilities=["shell", "destructive_file_operations"],
            requires_confirmation=True,
            min_confidence=0.9,
        ),
        _make_tool_def(
            "db_drop",
            description="Drop a database table",
            risk_level=ToolRiskLevel.DESTRUCTIVE,
            capabilities=["database", "destructive_file_operations"],
            requires_confirmation=True,
        ),
    ]


# ===================================================================
# 1. Listed tools reflect registered MCP tools accurately
# ===================================================================


class TestListToolsAccuracy:
    def test_empty_gateway(self):
        gateway = create_mock_mcp_gateway()
        gateway.tool_definitions.clear()
        catalog = ToolCatalog.from_gateway(gateway)
        assert len(catalog) == 0
        assert catalog.list_tools() == []

    def test_tools_match_registered(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        assert len(catalog) == len(tools)

    def test_tool_names_match(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        names = {t.name for t in catalog.list_tools()}
        expected = {t.name for t in tools}
        assert names == expected

    def test_list_tools_sorted_by_name(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        listed = catalog.list_tools()
        assert listed == sorted(listed, key=lambda t: t.name)


# ===================================================================
# 2. Metadata fields are surfaced correctly
# ===================================================================


class TestMetadataFields:
    def test_description_surfaced(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        fr = catalog.describe_tool("file_read")
        assert fr is not None
        assert fr.description == "Read a file from disk"

    def test_risk_level_surfaced_as_string(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        fw = catalog.describe_tool("file_write")
        assert fw is not None
        assert fw.risk_level == ToolRiskLevel.WRITE.value

    def test_capabilities_surfaced(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        fw = catalog.describe_tool("file_write")
        assert fw is not None
        assert "file_operations" in fw.capabilities
        assert "destructive_file_operations" in fw.capabilities

    def test_requires_confirmation_surfaced(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        assert catalog.describe_tool("file_read").requires_confirmation is False
        assert catalog.describe_tool("file_write").requires_confirmation is True

    def test_min_confidence_surfaced(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        assert catalog.describe_tool("file_write").min_confidence == 0.8

    def test_timeout_seconds_surfaced(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        assert catalog.describe_tool("file_write").timeout_seconds == 60.0

    def test_input_schema_surfaced(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        fw = catalog.describe_tool("file_write")
        assert fw.input_schema == {"type": "object", "properties": {"path": {"type": "string"}}}


# ===================================================================
# 3. Filtering by capability works
# ===================================================================


class TestFilterByCapability:
    def test_filter_file_operations(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(capability="file_operations")
        names = {t.name for t in results}
        assert names == {"file_read", "file_write"}

    def test_filter_destructive(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(capability="destructive_file_operations")
        names = {t.name for t in results}
        assert names == {"file_write", "shell_exec", "db_drop"}

    def test_filter_nonexistent_capability(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(capability="teleportation")
        assert results == []


# ===================================================================
# 4. Filtering by risk level works
# ===================================================================


class TestFilterByRiskLevel:
    def test_filter_read_only(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(risk_level=ToolRiskLevel.READ_ONLY.value)
        names = {t.name for t in results}
        assert names == {"file_read", "web_search"}

    def test_filter_destructive(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(risk_level=ToolRiskLevel.DESTRUCTIVE.value)
        assert len(results) == 1
        assert results[0].name == "db_drop"

    def test_filter_no_match(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(risk_level=ToolRiskLevel.PRIVILEGED.value)
        assert results == []


# ===================================================================
# 5. Filtering by requires_confirmation works
# ===================================================================


class TestFilterByConfirmation:
    def test_filter_requires_confirmation_true(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(requires_confirmation=True)
        names = {t.name for t in results}
        assert names == {"file_write", "shell_exec", "db_drop"}

    def test_filter_requires_confirmation_false(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(requires_confirmation=False)
        names = {t.name for t in results}
        assert names == {"file_read", "web_search"}


# ===================================================================
# 6. Name substring search works
# ===================================================================


class TestNameSearch:
    def test_search_by_prefix(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(name="file")
        names = {t.name for t in results}
        assert names == {"file_read", "file_write"}

    def test_search_case_insensitive(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(name="FILE")
        names = {t.name for t in results}
        assert names == {"file_read", "file_write"}

    def test_search_substring(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(name="search")
        assert len(results) == 1
        assert results[0].name == "web_search"

    def test_search_no_match(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(name="nonexistent")
        assert results == []


# ===================================================================
# 7. Describe/get-by-name works
# ===================================================================


class TestDescribeTool:
    def test_describe_existing(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        tool = catalog.describe_tool("shell_exec")
        assert tool is not None
        assert tool.name == "shell_exec"
        assert tool.risk_level == ToolRiskLevel.EXECUTE.value

    def test_describe_nonexistent(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        assert catalog.describe_tool("does_not_exist") is None

    def test_describe_returns_full_metadata(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        tool = catalog.describe_tool("db_drop")
        assert tool is not None
        assert tool.description == "Drop a database table"
        assert tool.requires_confirmation is True
        assert "database" in tool.capabilities


# ===================================================================
# 8. Serialization is stable / JSON-safe
# ===================================================================


class TestSerialization:
    def test_discovered_tool_to_dict(self):
        dt = DiscoveredTool(
            name="test", description="A test tool",
            risk_level="read_only", capabilities=["a", "b"],
        )
        d = dt.to_dict()
        assert isinstance(d, dict)
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["name"] == "test"
        assert parsed["capabilities"] == ["a", "b"]

    def test_catalog_to_dict(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        d = catalog.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["tool_count"] == 5
        assert len(parsed["tools"]) == 5

    def test_empty_catalog_to_dict(self):
        catalog = ToolCatalog()
        d = catalog.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["tool_count"] == 0
        assert parsed["tools"] == []

    def test_round_trip_stability(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        d1 = json.dumps(catalog.to_dict(), sort_keys=True)
        d2 = json.dumps(catalog.to_dict(), sort_keys=True)
        assert d1 == d2


# ===================================================================
# 9. No execution behavior changed
# ===================================================================


class TestNoSideEffects:
    def test_catalog_is_read_only_snapshot(self):
        """Modifying catalog does not affect gateway."""
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        # Mutate list returned by list_tools
        listed = catalog.list_tools()
        listed.clear()
        # Catalog still has tools
        assert len(catalog) == 5

    def test_from_gateway_with_none(self):
        """Passing an object without tool_definitions returns empty catalog."""
        catalog = ToolCatalog.from_gateway(object())
        assert len(catalog) == 0

    def test_from_agent_without_dispatcher(self):
        """Agent without dispatcher returns empty catalog."""
        class FakeAgent:
            pass
        catalog = ToolCatalog.from_agent(FakeAgent())
        assert len(catalog) == 0

    def test_from_agent_without_gateway(self):
        """Agent with dispatcher but no gateway returns empty catalog."""
        class FakeDispatcher:
            pass
        class FakeAgent:
            dispatcher = FakeDispatcher()
        catalog = ToolCatalog.from_agent(FakeAgent())
        assert len(catalog) == 0

    def test_repr(self):
        catalog = ToolCatalog([DiscoveredTool(name="a"), DiscoveredTool(name="b")])
        assert repr(catalog) == "ToolCatalog(tools=2)"


# ===================================================================
# 10. Combined filters (AND semantics)
# ===================================================================


class TestCombinedFilters:
    def test_name_and_risk_level(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(
            name="file", risk_level=ToolRiskLevel.WRITE.value,
        )
        assert len(results) == 1
        assert results[0].name == "file_write"

    def test_capability_and_confirmation(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(
            capability="destructive_file_operations",
            requires_confirmation=True,
        )
        names = {t.name for t in results}
        assert names == {"file_write", "shell_exec", "db_drop"}

    def test_all_filters_no_match(self):
        tools = _sample_tools()
        gateway = _make_gateway_with_tools(tools)
        catalog = ToolCatalog.from_gateway(gateway)
        results = catalog.find_tools(
            name="file", risk_level=ToolRiskLevel.DESTRUCTIVE.value,
        )
        assert results == []
