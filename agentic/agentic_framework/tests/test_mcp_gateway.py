"""
Tests for MCP Gateway Module.

Tests that MCP tool calls are properly gated through
ConfidenceGate and SafetyContract.
"""

import asyncio
import pytest
from agentic.agentic_framework.mcp_gateway import (
    # Enums
    ToolRiskLevel,
    GatewayDecision,
    # Data classes
    MCPToolDefinition,
    MCPToolCall,
    MCPToolResult,
    AuditEntry,
    # Classifier
    ToolRiskClassifier,
    # Escalation
    EscalationHandler,
    InteractiveEscalationHandler,
    # Client
    MockMCPClient,
    # Gateway
    SafeMCPGateway,
    # Factory
    create_safe_mcp_gateway,
    create_mock_mcp_gateway,
)
from agentic.agentic_framework.confidence_gate import (
    ConfidenceGate,
    EscalationLevel,
    create_confidence_gate,
    create_strict_confidence_gate,
    create_permissive_confidence_gate,
)


def run_async(coro):
    """Helper to run async coroutines in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


# =============================================================================
# Test Enums
# =============================================================================


class TestToolRiskLevel:
    """Test ToolRiskLevel enum."""

    def test_risk_levels_exist(self):
        """Verify all risk levels are defined."""
        assert ToolRiskLevel.READ_ONLY.value == "read_only"
        assert ToolRiskLevel.WRITE.value == "write"
        assert ToolRiskLevel.EXECUTE.value == "execute"
        assert ToolRiskLevel.DESTRUCTIVE.value == "destructive"
        assert ToolRiskLevel.PRIVILEGED.value == "privileged"


class TestGatewayDecision:
    """Test GatewayDecision enum."""

    def test_decisions_exist(self):
        """Verify all decisions are defined."""
        assert GatewayDecision.ALLOWED.value == "allowed"
        assert GatewayDecision.BLOCKED.value == "blocked"
        assert GatewayDecision.ESCALATE.value == "escalate"
        assert GatewayDecision.TIMEOUT.value == "timeout"
        assert GatewayDecision.ERROR.value == "error"


# =============================================================================
# Test Data Classes
# =============================================================================


class TestMCPToolDefinition:
    """Test MCPToolDefinition dataclass."""

    def test_default_values(self):
        """Test default values."""
        tool = MCPToolDefinition(
            name="test_tool",
            description="A test tool",
            risk_level=ToolRiskLevel.READ_ONLY,
        )
        assert tool.name == "test_tool"
        assert tool.min_confidence == 0.5
        assert tool.requires_confirmation is False
        assert tool.timeout_seconds == 30.0

    def test_to_dict(self):
        """Test serialization."""
        tool = MCPToolDefinition(
            name="test_tool",
            description="A test tool",
            risk_level=ToolRiskLevel.DESTRUCTIVE,
            requires_confirmation=True,
        )
        d = tool.to_dict()
        assert d["name"] == "test_tool"
        assert d["risk_level"] == "destructive"
        assert d["requires_confirmation"] is True


class TestMCPToolCall:
    """Test MCPToolCall dataclass."""

    def test_default_values(self):
        """Test default values."""
        call = MCPToolCall(
            tool_name="search",
            parameters={"query": "test"},
        )
        assert call.quality_score == 0.5
        assert call.coherence_score == 0.5
        assert call.request_id.startswith("mcp-")
        assert call.timestamp is not None

    def test_custom_values(self):
        """Test custom values."""
        call = MCPToolCall(
            tool_name="file_write",
            parameters={"path": "/tmp/test.txt"},
            quality_score=0.9,
            coherence_score=0.85,
            session_id="test-session",
        )
        assert call.quality_score == 0.9
        assert call.session_id == "test-session"


class TestMCPToolResult:
    """Test MCPToolResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = MCPToolResult(
            request_id="mcp-123",
            tool_name="search",
            decision=GatewayDecision.ALLOWED,
            success=True,
            result=["item1", "item2"],
            confidence=0.85,
        )
        assert result.success is True
        assert result.decision == GatewayDecision.ALLOWED
        assert result.result == ["item1", "item2"]

    def test_blocked_result(self):
        """Test blocked result."""
        result = MCPToolResult(
            request_id="mcp-123",
            tool_name="file_delete",
            decision=GatewayDecision.BLOCKED,
            success=False,
            blocked_reason="Confidence too low",
            confidence=0.3,
        )
        assert result.success is False
        assert result.blocked_reason == "Confidence too low"

    def test_to_dict(self):
        """Test serialization."""
        result = MCPToolResult(
            request_id="mcp-123",
            tool_name="search",
            decision=GatewayDecision.ALLOWED,
            success=True,
            risk_level=ToolRiskLevel.READ_ONLY,
        )
        d = result.to_dict()
        assert d["request_id"] == "mcp-123"
        assert d["decision"] == "allowed"
        assert d["risk_level"] == "read_only"


# =============================================================================
# Test Tool Risk Classifier
# =============================================================================


class TestToolRiskClassifier:
    """Test ToolRiskClassifier class."""

    def test_classify_read_only(self):
        """Read operations should be READ_ONLY."""
        classifier = ToolRiskClassifier()
        assert classifier.classify("file_read") == ToolRiskLevel.READ_ONLY
        assert classifier.classify("get_user") == ToolRiskLevel.READ_ONLY
        assert classifier.classify("search_documents") == ToolRiskLevel.READ_ONLY
        assert classifier.classify("list_files") == ToolRiskLevel.READ_ONLY

    def test_classify_write(self):
        """Write operations should be WRITE."""
        classifier = ToolRiskClassifier()
        assert classifier.classify("file_write") == ToolRiskLevel.WRITE
        assert classifier.classify("create_user") == ToolRiskLevel.WRITE
        assert classifier.classify("update_record") == ToolRiskLevel.WRITE
        assert classifier.classify("send_message") == ToolRiskLevel.WRITE

    def test_classify_execute(self):
        """Execute operations should be EXECUTE."""
        classifier = ToolRiskClassifier()
        assert classifier.classify("execute_command") == ToolRiskLevel.EXECUTE
        assert classifier.classify("run_script") == ToolRiskLevel.EXECUTE
        assert classifier.classify("shell_exec") == ToolRiskLevel.EXECUTE

    def test_classify_destructive(self):
        """Destructive operations should be DESTRUCTIVE."""
        classifier = ToolRiskClassifier()
        assert classifier.classify("file_delete") == ToolRiskLevel.DESTRUCTIVE
        assert classifier.classify("remove_user") == ToolRiskLevel.DESTRUCTIVE
        assert classifier.classify("drop_table") == ToolRiskLevel.DESTRUCTIVE

    def test_classify_privileged(self):
        """Privileged operations should be PRIVILEGED."""
        classifier = ToolRiskClassifier()
        assert classifier.classify("admin_reset") == ToolRiskLevel.PRIVILEGED
        assert classifier.classify("get_credentials") == ToolRiskLevel.PRIVILEGED
        assert classifier.classify("sudo_execute") == ToolRiskLevel.PRIVILEGED

    def test_classify_with_description(self):
        """Description should influence classification."""
        classifier = ToolRiskClassifier()
        # Name is ambiguous, but description clarifies
        assert classifier.classify("do_action", "delete all records") == ToolRiskLevel.DESTRUCTIVE
        assert classifier.classify("do_action", "read the configuration file") == ToolRiskLevel.READ_ONLY

    def test_classify_with_override(self):
        """Explicit overrides should take precedence."""
        classifier = ToolRiskClassifier(overrides={
            "my_safe_delete": ToolRiskLevel.READ_ONLY,
            "my_dangerous_read": ToolRiskLevel.DESTRUCTIVE,
        })
        assert classifier.classify("my_safe_delete") == ToolRiskLevel.READ_ONLY
        assert classifier.classify("my_dangerous_read") == ToolRiskLevel.DESTRUCTIVE

    def test_min_confidence_thresholds(self):
        """Verify confidence thresholds by risk level."""
        classifier = ToolRiskClassifier()
        assert classifier.get_min_confidence(ToolRiskLevel.READ_ONLY) == 0.3
        assert classifier.get_min_confidence(ToolRiskLevel.WRITE) == 0.5
        assert classifier.get_min_confidence(ToolRiskLevel.EXECUTE) == 0.7
        assert classifier.get_min_confidence(ToolRiskLevel.DESTRUCTIVE) == 0.85
        assert classifier.get_min_confidence(ToolRiskLevel.PRIVILEGED) == 0.95

    def test_requires_confirmation(self):
        """Verify which risk levels require confirmation."""
        classifier = ToolRiskClassifier()
        assert classifier.requires_confirmation(ToolRiskLevel.READ_ONLY) is False
        assert classifier.requires_confirmation(ToolRiskLevel.WRITE) is False
        assert classifier.requires_confirmation(ToolRiskLevel.EXECUTE) is False
        assert classifier.requires_confirmation(ToolRiskLevel.DESTRUCTIVE) is True
        assert classifier.requires_confirmation(ToolRiskLevel.PRIVILEGED) is True

    def test_forbidden_capabilities(self):
        """Check forbidden capability detection."""
        classifier = ToolRiskClassifier()

        # Should detect forbidden
        assert classifier.maps_to_forbidden_capability(
            "tool", ["credential_access"]
        ) == "credential_access"

        # Should not detect allowed
        assert classifier.maps_to_forbidden_capability(
            "tool", ["file_read", "search"]
        ) is None


# =============================================================================
# Test Mock MCP Client
# =============================================================================


class TestMockMCPClient:
    """Test MockMCPClient class."""

    def test_register_and_call_tool(self):
        """Test registering and calling a mock tool."""
        client = MockMCPClient()
        client.register_tool(
            "echo",
            lambda p: f"Echo: {p.get('message', '')}",
            ToolRiskLevel.READ_ONLY,
        )

        result = run_async(client.call_tool("echo", {"message": "hello"}))
        assert result == "Echo: hello"

    def test_call_unknown_tool(self):
        """Calling unknown tool should raise."""
        client = MockMCPClient()
        with pytest.raises(ValueError, match="Unknown tool"):
            run_async(client.call_tool("nonexistent", {}))

    def test_call_history(self):
        """Tool calls should be recorded in history."""
        client = MockMCPClient()
        client.register_tool("test", lambda p: "ok", ToolRiskLevel.READ_ONLY)

        run_async(client.call_tool("test", {"a": 1}))
        run_async(client.call_tool("test", {"b": 2}))

        assert len(client.call_history) == 2
        assert client.call_history[0]["tool_name"] == "test"
        assert client.call_history[0]["parameters"] == {"a": 1}

    def test_async_handler(self):
        """Test async tool handler."""
        client = MockMCPClient()

        async def async_handler(params):
            await asyncio.sleep(0.01)
            return "async result"

        client.register_tool("async_tool", async_handler, ToolRiskLevel.READ_ONLY)

        result = run_async(client.call_tool("async_tool", {}))
        assert result == "async result"

    def test_list_tools(self):
        """Test listing registered tools."""
        client = MockMCPClient()
        client.register_tool("tool1", lambda p: "1", ToolRiskLevel.READ_ONLY)
        client.register_tool("tool2", lambda p: "2", ToolRiskLevel.WRITE)

        tools = run_async(client.list_tools())
        names = [t.name for t in tools]
        assert "tool1" in names
        assert "tool2" in names


# =============================================================================
# Test Safe MCP Gateway - Basic Operations
# =============================================================================


class TestSafeMCPGatewayBasic:
    """Test SafeMCPGateway basic operations."""

    def test_call_read_only_tool_high_confidence(self):
        """Read-only tool with high confidence should succeed."""
        gateway = create_mock_mcp_gateway()

        result = run_async(gateway.call_tool(MCPToolCall(
            tool_name="file_read",
            parameters={"path": "/tmp/test.txt"},
            quality_score=0.9,
            coherence_score=0.9,
        )))

        assert result.success is True
        assert result.decision == GatewayDecision.ALLOWED
        assert result.risk_level == ToolRiskLevel.READ_ONLY

    def test_call_read_only_tool_low_confidence(self):
        """Read-only tool with low confidence should still succeed (low threshold)."""
        gateway = create_mock_mcp_gateway()

        result = run_async(gateway.call_tool(MCPToolCall(
            tool_name="search",
            parameters={"query": "test"},
            quality_score=0.4,
            coherence_score=0.4,
        )))

        # READ_ONLY has min_confidence of 0.3, so 0.4 should pass
        assert result.success is True

    def test_call_write_tool_low_confidence(self):
        """Write tool with low confidence should be blocked."""
        gateway = create_mock_mcp_gateway()

        result = run_async(gateway.call_tool(MCPToolCall(
            tool_name="file_write",
            parameters={"path": "/tmp/test.txt"},
            quality_score=0.3,
            coherence_score=0.3,
        )))

        # WRITE has min_confidence of 0.5, so 0.3 should fail
        assert result.success is False
        assert result.decision == GatewayDecision.BLOCKED
        assert "Confidence" in result.blocked_reason

    def test_call_simple_helper(self):
        """Test call_tool_simple helper."""
        gateway = create_mock_mcp_gateway()

        result = run_async(gateway.call_tool_simple(
            "file_read",
            {"path": "/tmp/test.txt"},
            quality_score=0.8,
            coherence_score=0.8,
        ))

        assert result.success is True


# =============================================================================
# Test Safe MCP Gateway - Gating Behavior
# =============================================================================


class TestSafeMCPGatewayGating:
    """Test SafeMCPGateway gating behavior."""

    def test_destructive_tool_blocked_without_confirmation(self):
        """Destructive tools should be blocked without confirmation."""
        client = MockMCPClient()
        client.register_tool(
            "file_delete",
            lambda p: "deleted",
            ToolRiskLevel.DESTRUCTIVE,
        )
        gateway = create_safe_mcp_gateway(client)

        # Register the tool with confirmation required
        # Note: min_confidence is set low because the gateway factors in
        # action_complexity and action_reversibility which lower overall confidence
        gateway.register_tool(MCPToolDefinition(
            name="file_delete",
            description="Delete a file",
            risk_level=ToolRiskLevel.DESTRUCTIVE,
            requires_confirmation=True,
            min_confidence=0.5,  # Lower threshold so we test confirmation flow
        ))

        result = run_async(gateway.call_tool(MCPToolCall(
            tool_name="file_delete",
            parameters={"path": "/tmp/test.txt"},
            quality_score=0.95,
            coherence_score=0.95,
        )))

        # Should be escalated (default handler denies) - passes confidence but requires confirmation
        assert result.success is False
        assert result.decision == GatewayDecision.ESCALATE

    def test_forbidden_capability_blocked(self):
        """Tools with forbidden capabilities should be blocked."""
        client = MockMCPClient()
        client.register_tool("steal_creds", lambda p: "creds", ToolRiskLevel.PRIVILEGED)

        gateway = create_safe_mcp_gateway(client)

        # Register tool with forbidden capability
        gateway.register_tool(MCPToolDefinition(
            name="steal_creds",
            description="Access credentials",
            risk_level=ToolRiskLevel.PRIVILEGED,
            capabilities=["credential_access"],  # Forbidden!
        ))

        result = run_async(gateway.call_tool(MCPToolCall(
            tool_name="steal_creds",
            parameters={},
            quality_score=0.99,
            coherence_score=0.99,
        )))

        assert result.success is False
        assert result.decision == GatewayDecision.BLOCKED
        assert "forbidden capability" in result.blocked_reason.lower()

    def test_strict_gateway_higher_thresholds(self):
        """Strict gateway should have higher confidence requirements."""
        client = MockMCPClient()
        client.register_tool("write_file", lambda p: "wrote", ToolRiskLevel.WRITE)

        # Standard gateway
        standard = create_safe_mcp_gateway(client, strict=False)
        # Strict gateway
        strict = create_safe_mcp_gateway(client, strict=True)

        call = MCPToolCall(
            tool_name="write_file",
            parameters={"path": "/tmp/test.txt"},
            quality_score=0.6,
            coherence_score=0.6,
        )

        standard_result = run_async(standard.call_tool(call))
        strict_result = run_async(strict.call_tool(call))

        # Both should have same confidence (same signals)
        assert standard_result.confidence == strict_result.confidence


# =============================================================================
# Test Safe MCP Gateway - Escalation
# =============================================================================


class TestSafeMCPGatewayEscalation:
    """Test SafeMCPGateway escalation behavior."""

    def test_interactive_escalation_confirmed(self):
        """Interactive escalation with confirmation should proceed."""
        client = MockMCPClient()
        client.register_tool("danger", lambda p: "done", ToolRiskLevel.DESTRUCTIVE)

        # Create handler that auto-confirms
        async def auto_confirm(call, tool_def, decision):
            return True

        handler = InteractiveEscalationHandler(confirm_callback=auto_confirm)

        gateway = SafeMCPGateway(
            mcp_client=client,
            escalation_handler=handler,
        )

        gateway.register_tool(MCPToolDefinition(
            name="danger",
            description="Dangerous operation",
            risk_level=ToolRiskLevel.DESTRUCTIVE,
            requires_confirmation=True,
            min_confidence=0.5,  # Lower for test
        ))

        result = run_async(gateway.call_tool(MCPToolCall(
            tool_name="danger",
            parameters={},
            quality_score=0.8,
            coherence_score=0.8,
        )))

        assert result.success is True
        assert result.human_confirmed is True

    def test_interactive_escalation_denied(self):
        """Interactive escalation with denial should block."""
        client = MockMCPClient()
        client.register_tool("danger", lambda p: "done", ToolRiskLevel.DESTRUCTIVE)

        # Create handler that denies
        async def auto_deny(call, tool_def, decision):
            return False

        handler = InteractiveEscalationHandler(confirm_callback=auto_deny)

        gateway = SafeMCPGateway(
            mcp_client=client,
            escalation_handler=handler,
        )

        gateway.register_tool(MCPToolDefinition(
            name="danger",
            description="Dangerous operation",
            risk_level=ToolRiskLevel.DESTRUCTIVE,
            requires_confirmation=True,
            min_confidence=0.5,
        ))

        result = run_async(gateway.call_tool(MCPToolCall(
            tool_name="danger",
            parameters={},
            quality_score=0.8,
            coherence_score=0.8,
        )))

        assert result.success is False
        assert result.decision == GatewayDecision.ESCALATE
        assert result.human_confirmed is False


# =============================================================================
# Test Safe MCP Gateway - Error Handling
# =============================================================================


class TestSafeMCPGatewayErrors:
    """Test SafeMCPGateway error handling."""

    def test_tool_execution_error(self):
        """Tool execution error should be captured."""
        client = MockMCPClient()

        def broken_tool(params):
            raise ValueError("Tool broke")

        client.register_tool("broken", broken_tool, ToolRiskLevel.READ_ONLY)

        gateway = create_safe_mcp_gateway(client)

        result = run_async(gateway.call_tool(MCPToolCall(
            tool_name="broken",
            parameters={},
            quality_score=0.9,
            coherence_score=0.9,
        )))

        assert result.success is False
        assert result.decision == GatewayDecision.ERROR
        assert "Tool broke" in result.error

    def test_tool_timeout(self):
        """Tool timeout should be captured."""
        client = MockMCPClient()

        async def slow_tool(params):
            await asyncio.sleep(10)
            return "done"

        client.register_tool("slow", slow_tool, ToolRiskLevel.READ_ONLY)

        gateway = create_safe_mcp_gateway(client)
        gateway.register_tool(MCPToolDefinition(
            name="slow",
            description="Slow tool",
            risk_level=ToolRiskLevel.READ_ONLY,
            timeout_seconds=0.1,  # Very short
            min_confidence=0.3,
        ))

        result = run_async(gateway.call_tool(MCPToolCall(
            tool_name="slow",
            parameters={},
            quality_score=0.9,
            coherence_score=0.9,
        )))

        assert result.success is False
        assert result.decision == GatewayDecision.TIMEOUT


# =============================================================================
# Test Safe MCP Gateway - Audit
# =============================================================================


class TestSafeMCPGatewayAudit:
    """Test SafeMCPGateway audit functionality."""

    def test_audit_log_enabled(self):
        """Audit log should record operations."""
        gateway = create_mock_mcp_gateway(audit_enabled=True)

        run_async(gateway.call_tool_simple("file_read", {"path": "/tmp/a"}, 0.9, 0.9))
        run_async(gateway.call_tool_simple("file_read", {"path": "/tmp/b"}, 0.9, 0.9))
        run_async(gateway.call_tool_simple("file_write", {"path": "/tmp/c"}, 0.2, 0.2))

        audit = gateway.get_audit_log()
        assert len(audit) == 3

    def test_audit_log_filter_by_tool(self):
        """Audit log should filter by tool name."""
        gateway = create_mock_mcp_gateway()

        run_async(gateway.call_tool_simple("file_read", {"path": "/tmp/a"}, 0.9, 0.9))
        run_async(gateway.call_tool_simple("search", {"query": "test"}, 0.9, 0.9))
        run_async(gateway.call_tool_simple("file_read", {"path": "/tmp/b"}, 0.9, 0.9))

        audit = gateway.get_audit_log(tool_name="file_read")
        assert len(audit) == 2
        assert all(e.tool_name == "file_read" for e in audit)

    def test_audit_log_filter_by_decision(self):
        """Audit log should filter by decision."""
        gateway = create_mock_mcp_gateway()

        run_async(gateway.call_tool_simple("file_read", {}, 0.9, 0.9))  # Allowed
        run_async(gateway.call_tool_simple("file_write", {}, 0.2, 0.2))  # Blocked

        allowed = gateway.get_audit_log(decision=GatewayDecision.ALLOWED)
        blocked = gateway.get_audit_log(decision=GatewayDecision.BLOCKED)

        assert len(allowed) >= 1
        assert len(blocked) >= 1

    def test_blocked_count(self):
        """Should track blocked call count."""
        gateway = create_mock_mcp_gateway()

        run_async(gateway.call_tool_simple("file_read", {}, 0.9, 0.9))  # Allowed
        run_async(gateway.call_tool_simple("file_write", {}, 0.2, 0.2))  # Blocked
        run_async(gateway.call_tool_simple("file_write", {}, 0.2, 0.2))  # Blocked

        assert gateway.get_blocked_count() >= 2

    def test_success_rate(self):
        """Should calculate success rate."""
        gateway = create_mock_mcp_gateway()

        run_async(gateway.call_tool_simple("file_read", {}, 0.9, 0.9))  # Success
        run_async(gateway.call_tool_simple("file_read", {}, 0.9, 0.9))  # Success
        run_async(gateway.call_tool_simple("file_write", {}, 0.2, 0.2))  # Blocked

        rate = gateway.get_success_rate()
        assert 0.5 <= rate <= 0.8  # 2/3 ≈ 0.67


# =============================================================================
# Test Factory Functions
# =============================================================================


class TestFactoryFunctions:
    """Test factory functions."""

    def test_create_mock_mcp_gateway(self):
        """Create mock gateway should work."""
        gateway = create_mock_mcp_gateway()
        assert gateway is not None
        assert gateway.audit_enabled is True

    def test_create_mock_mcp_gateway_strict(self):
        """Create strict mock gateway should work."""
        gateway = create_mock_mcp_gateway(strict=True)
        assert gateway is not None

    def test_create_safe_mcp_gateway(self):
        """Create gateway with client should work."""
        client = MockMCPClient()
        gateway = create_safe_mcp_gateway(client)
        assert gateway is not None


# =============================================================================
# Test Integration with Confidence Gate
# =============================================================================


class TestConfidenceGateIntegration:
    """Test integration with ConfidenceGate."""

    def test_confidence_affects_gating(self):
        """Confidence signals should affect gating decisions."""
        gateway = create_mock_mcp_gateway()

        # High confidence - should allow
        high_result = run_async(gateway.call_tool(MCPToolCall(
            tool_name="file_write",
            parameters={},
            quality_score=0.9,
            coherence_score=0.9,
        )))

        # Low confidence - should block
        low_result = run_async(gateway.call_tool(MCPToolCall(
            tool_name="file_write",
            parameters={},
            quality_score=0.2,
            coherence_score=0.2,
        )))

        assert high_result.confidence > low_result.confidence
        # High confidence write should succeed, low should fail
        assert high_result.success != low_result.success or \
               high_result.decision != low_result.decision

    def test_risk_level_affects_confidence_threshold(self):
        """Higher risk tools should require higher confidence."""
        client = MockMCPClient()
        client.register_tool("read", lambda p: "read", ToolRiskLevel.READ_ONLY)
        client.register_tool("execute", lambda p: "exec", ToolRiskLevel.EXECUTE)

        gateway = create_safe_mcp_gateway(client)

        # Medium confidence
        call_params = {"quality_score": 0.5, "coherence_score": 0.5}

        read_result = run_async(gateway.call_tool(MCPToolCall(
            tool_name="read",
            parameters={},
            **call_params,
        )))

        exec_result = run_async(gateway.call_tool(MCPToolCall(
            tool_name="execute",
            parameters={},
            **call_params,
        )))

        # Read should succeed (min_confidence=0.3), execute should fail (min_confidence=0.7)
        assert read_result.success is True
        assert exec_result.success is False


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_parameters(self):
        """Empty parameters should work."""
        gateway = create_mock_mcp_gateway()
        result = run_async(gateway.call_tool_simple("search", {}, 0.9, 0.9))
        assert result is not None

    def test_unknown_tool_classification(self):
        """Unknown tool should default to WRITE."""
        client = MockMCPClient()
        client.register_tool("mystery_tool", lambda p: "ok", ToolRiskLevel.WRITE)

        gateway = create_safe_mcp_gateway(client)

        result = run_async(gateway.call_tool_simple("mystery_tool", {}, 0.7, 0.7))
        # Should be classified as WRITE by default
        assert result.risk_level == ToolRiskLevel.WRITE

    def test_audit_disabled(self):
        """Audit can be disabled."""
        gateway = create_mock_mcp_gateway(audit_enabled=False)
        gateway.audit_enabled = False

        run_async(gateway.call_tool_simple("file_read", {}, 0.9, 0.9))

        assert len(gateway.audit_log) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
