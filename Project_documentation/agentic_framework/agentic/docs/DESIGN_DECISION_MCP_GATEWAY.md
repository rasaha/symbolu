# Design Decision: MCP Gateway

**Status:** Implemented
**Version:** 1.4.0
**Date:** 2026-02-02

## Summary

The MCP Gateway provides safe integration with external tools using the Model Context Protocol (MCP), with risk-based access control that integrates with Sentinel's existing safety components.

## Problem Statement

AI agents need to interact with external tools (file systems, databases, APIs, etc.) to be useful. However, unrestricted tool access creates significant risks:

1. **Data Loss** - Agents could delete critical files or drop database tables
2. **Security Breaches** - Agents could access sensitive credentials or escalate privileges
3. **Unintended Actions** - Ambiguous requests could lead to destructive operations
4. **No Audit Trail** - Actions taken without logging prevent accountability

## Decision

Implement a SafeMCPGateway that:

1. **Classifies tools by risk level** - Not all tools are equal
2. **Gates execution through ConfidenceGate** - Use existing behavioral confidence control
3. **Requires human confirmation for destructive operations** - Fail-closed design
4. **Maintains full audit trail** - Every operation logged

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SafeMCPGateway                           │
├─────────────────────────────────────────────────────────────┤
│  ToolRiskClassifier                                          │
│  ├── Pattern matching on tool names                         │
│  ├── Description analysis                                   │
│  └── Manual overrides for known tools                       │
├─────────────────────────────────────────────────────────────┤
│  Confidence Integration                                      │
│  ├── Builds ConfidenceSignals from MCPToolCall              │
│  ├── Calls ConfidenceGate.evaluate()                        │
│  └── Maps risk level → minimum confidence threshold         │
├─────────────────────────────────────────────────────────────┤
│  Human Escalation                                            │
│  ├── Async callback for confirmation                        │
│  ├── Required for DESTRUCTIVE/PRIVILEGED tools              │
│  └── Blocks execution until confirmed                       │
├─────────────────────────────────────────────────────────────┤
│  Audit Logging                                               │
│  ├── Every call recorded with timestamp                     │
│  ├── Risk level, decision, result, duration                 │
│  └── Filterable by tool, decision, time range               │
└─────────────────────────────────────────────────────────────┘
```

## Risk Classification

| Level | Examples | Min Confidence | Human Confirm |
|-------|----------|----------------|---------------|
| READ_ONLY | list_files, search, get_config | 0.30 | Never |
| WRITE | create_file, update_record | 0.50 | If uncertain |
| EXECUTE | run_script, send_email | 0.70 | Often |
| DESTRUCTIVE | delete_files, drop_table | 0.85 | Always |
| PRIVILEGED | admin_access, modify_permissions | 0.95 | Always |

## Why MCP?

The Model Context Protocol (MCP) is becoming the industry standard for AI tool integration:

- **Adopted by major providers:** OpenAI, Google, Linux Foundation
- **Well-defined interface:** Standard for tool definitions, calls, and results
- **Growing ecosystem:** Thousands of MCP servers and tools available
- **Future-proof:** Building on MCP means compatibility with the broader ecosystem

## Why Not Just Pass-Through?

A naive implementation would simply forward tool calls to MCP servers. This is dangerous because:

```
❌ Naive Approach:
   Agent: "I need to clean up files"
   MCP: delete_files(pattern="*")
   Result: All files deleted, no recovery

✅ Our Approach:
   Agent: "I need to clean up files"
   Gateway: Classify → DESTRUCTIVE
   Gateway: Confidence check → Below threshold
   Gateway: Escalate → "Delete all files matching '*'? [y/n]"
   User: "n"
   Result: No action taken, agent informed
```

## Integration Points

### With ConfidenceGate

The gateway builds `ConfidenceSignals` from the tool call context:

```python
signals = ConfidenceSignals(
    quality_score=tool_call.quality_score,
    coherence_score=tool_call.coherence_score,
    action_complexity=self._estimate_complexity(tool_call),
    action_reversibility=self._estimate_reversibility(risk_level),
)

decision = self.confidence_gate.evaluate(signals, action=tool_call.tool_name)
```

### With SafetyContract

The gateway checks forbidden capabilities before execution:

```python
if tool_name in self.forbidden_capabilities:
    return MCPToolResult(
        success=False,
        error=f"Tool '{tool_name}' is forbidden",
        decision=GatewayDecision.BLOCKED_FORBIDDEN,
    )
```

## Alternatives Considered

### 1. Per-Tool Whitelisting

**Rejected:** Too restrictive. New tools require explicit configuration.

### 2. LLM-Based Risk Assessment

**Rejected:** Expensive and potentially inconsistent. Pattern matching is sufficient for classification.

### 3. No Gating (Trust the Agent)

**Rejected:** Violates fail-closed safety principle. Agents make mistakes.

### 4. Blocking All Destructive Operations

**Rejected:** Too restrictive. Human confirmation allows necessary destructive actions when appropriate.

## Testing

The MCP Gateway has comprehensive test coverage:

| Category | Tests | Coverage |
|----------|-------|----------|
| Risk Classification | 10 | All risk levels, patterns, overrides |
| Mock Client | 5 | Registration, history, async handlers |
| Basic Gating | 4 | Allow/block based on confidence |
| Escalation | 2 | Confirm/deny flows |
| Errors | 2 | Execution errors, timeouts |
| Audit | 5 | Logging, filtering, statistics |
| Factory Functions | 3 | Gateway creation helpers |
| Integration | 3 | ConfidenceGate integration |
| Edge Cases | 3 | Empty params, unknown tools |
| **Total** | **48** | **All passing** |

## API Surface

### Core Classes

```python
# Gateway
SafeMCPGateway(mcp_client, confidence_gate, classifier, ...)
  .call_tool(MCPToolCall) -> MCPToolResult
  .call_tool_simple(
      tool_name, parameters,
      quality_score=0.5, coherence_score=0.5,
      *, cg_metadata=None, tier="consumer",
  ) -> MCPToolResult
  .get_audit_log() -> List[AuditEntry]

# When cg_metadata is provided (e.g. MistralCGAdapter.last_cg_metadata),
# the gateway calls build_governance_enrichment_kwargs() and attaches
# canonical entropy_result + vritti_result to the MCPToolCall before
# the normal governance path runs. See
# Project_documentation/agentic_framework/agentic/AGENTIC_ARCHITECTURE.md § "Inference CG Metadata ↔ MCP Gateway".

# Data Classes
MCPToolCall(tool_name, parameters, quality_score, coherence_score, ...)
MCPToolResult(success, result, error, decision, risk_level, ...)
AuditEntry(timestamp, tool_name, risk_level, decision, success, ...)

# Classification
ToolRiskClassifier()
  .classify(tool_name, description) -> ToolRiskLevel
  .get_min_confidence(risk_level) -> float
  .requires_confirmation(risk_level) -> bool

# Enums
ToolRiskLevel: READ_ONLY, WRITE, EXECUTE, DESTRUCTIVE, PRIVILEGED
GatewayDecision: ALLOWED, BLOCKED_LOW_CONFIDENCE, BLOCKED_FORBIDDEN, ...
```

### Factory Functions

```python
# Production use
gateway = create_safe_mcp_gateway(mcp_client, strict=False)

# Testing
gateway = create_mock_mcp_gateway(strict=False, audit_enabled=True)
```

## Future Considerations

1. **Rate Limiting** - Add per-tool rate limits to prevent abuse
2. **Cost Tracking** - Track tool execution costs for budget management
3. **Tool Discovery** - Auto-discover and classify tools from MCP servers
4. **Caching** - Cache read-only tool results to reduce API calls

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [ConfidenceGate Design Decision](./DESIGN_DECISION_CONFIDENCE_GATE.md)
- [Sentinel Guide - MCP Gateway Section](../AGENTIC_FRAMEWORK_GUIDE.md#9-mcp-gateway)
