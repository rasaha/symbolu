"""
MCP Gateway Module - Safe Model Context Protocol Integration

Connects to the MCP ecosystem (100+ tools) while maintaining safety
through ConfidenceGate and SafetyContract.

THIS IS NOT RAW MCP ACCESS:
    ❌ Direct tool execution without checks
    ❌ Trust all MCP servers equally
    ❌ Execute regardless of confidence

THIS IS GATED MCP ACCESS:
    ✅ Every tool call goes through ConfidenceGate
    ✅ SafetyContract blocks forbidden capabilities
    ✅ Tool risk classification affects confidence thresholds
    ✅ Human escalation for dangerous operations
    ✅ Full audit trail

ARCHITECTURE:
    ┌─────────────────────────────────────────────────────────────┐
    │                    MCP Tool Request                          │
    │                          ↓                                   │
    │  ┌─────────────────────────────────────────────────────────┐│
    │  │              SafeMCPGateway                              ││
    │  │                                                          ││
    │  │  1. Classify tool risk level                            ││
    │  │  2. Build ConfidenceSignals from context                ││
    │  │  3. ConfidenceGate.evaluate() → Can we proceed?         ││
    │  │  4. SafetyContract.check() → Is action allowed?         ││
    │  │  5. Human escalation if required                        ││
    │  │  6. Execute MCP call with timeout                       ││
    │  │  7. Audit log the result                                ││
    │  └─────────────────────────────────────────────────────────┘│
    │                          ↓                                   │
    │                    Gated Result                              │
    └─────────────────────────────────────────────────────────────┘

MCP PROTOCOL:
    This module implements a safety layer over the Model Context Protocol.
    It does NOT implement MCP transport - use an MCP client library for that.
    This module wraps MCP calls with safety checks.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable
import logging

from agentic.agentic_framework.confidence_gate import (
    ConfidenceGate,
    ConfidenceSignals,
    ConfidenceGateDecision,
    EscalationLevel,
    ExecutionMode,
    create_confidence_gate,
)
from agentic.ledger.governance_audit_store import (
    GovernanceAuditStore,
    GovernanceAuditError,
    event_from_mcp_audit,
)
from agentic.agentic_framework.jepa_governance import (
    GovernanceRegime,
    jepa_governance_check,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class ToolRiskLevel(Enum):
    """Risk classification for MCP tools."""
    READ_ONLY = "read_only"        # No side effects (search, fetch, read)
    WRITE = "write"                # Creates/modifies data (write file, send message)
    EXECUTE = "execute"            # Runs code or commands
    DESTRUCTIVE = "destructive"    # Deletes data, irreversible actions
    PRIVILEGED = "privileged"      # Admin operations, credential access


class GatewayDecision(Enum):
    """Decision from the gateway."""
    ALLOWED = "allowed"            # Proceed with execution
    BLOCKED = "blocked"            # Cannot execute
    ESCALATE = "escalate"          # Requires human confirmation
    TIMEOUT = "timeout"            # Execution timed out
    ERROR = "error"                # Execution failed


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class MCPToolDefinition:
    """Definition of an MCP tool with risk metadata."""
    name: str
    description: str
    risk_level: ToolRiskLevel
    input_schema: Dict[str, Any] = field(default_factory=dict)

    # Safety metadata
    requires_confirmation: bool = False
    min_confidence: float = 0.5    # Minimum confidence to execute
    timeout_seconds: float = 30.0  # Execution timeout

    # Capability tags for SafetyContract filtering
    capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "input_schema": self.input_schema,
            "requires_confirmation": self.requires_confirmation,
            "min_confidence": self.min_confidence,
            "capabilities": self.capabilities,
        }


@dataclass
class MCPToolCall:
    """A request to call an MCP tool."""
    tool_name: str
    parameters: Dict[str, Any]

    # Context for confidence calculation
    session_id: Optional[str] = None
    turn_id: Optional[int] = None

    # Caller-provided signals
    quality_score: float = 0.5
    coherence_score: float = 0.5

    # Request metadata
    request_id: str = field(default_factory=lambda: f"mcp-{int(time.time() * 1000)}")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class MCPToolResult:
    """Result from an MCP tool call."""
    request_id: str
    tool_name: str

    # Outcome
    decision: GatewayDecision
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None

    # Gate decision details
    confidence: float = 0.0
    escalation_level: EscalationLevel = EscalationLevel.NONE
    blocked_reason: Optional[str] = None

    # Execution metadata
    execution_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Audit trail
    risk_level: Optional[ToolRiskLevel] = None
    human_confirmed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "decision": self.decision.value,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "confidence": self.confidence,
            "escalation_level": self.escalation_level.value,
            "blocked_reason": self.blocked_reason,
            "execution_time_ms": self.execution_time_ms,
            "risk_level": self.risk_level.value if self.risk_level else None,
            "human_confirmed": self.human_confirmed,
        }


@dataclass
class AuditEntry:
    """Audit log entry for MCP operations."""
    timestamp: str
    request_id: str
    tool_name: str
    parameters: Dict[str, Any]
    decision: GatewayDecision
    confidence: float
    risk_level: ToolRiskLevel
    session_id: Optional[str]
    execution_time_ms: float
    success: bool
    error: Optional[str]
    human_confirmed: bool


# =============================================================================
# Tool Risk Classification
# =============================================================================


class ToolRiskClassifier:
    """
    Classifies MCP tools by risk level.

    Uses pattern matching on tool names and explicit overrides.
    """

    # Default patterns for risk classification
    READ_ONLY_PATTERNS = [
        "read", "get", "fetch", "search", "list", "query", "find",
        "describe", "show", "view", "check", "inspect", "analyze",
    ]

    WRITE_PATTERNS = [
        "write", "create", "add", "insert", "update", "set", "put",
        "post", "send", "upload", "save", "modify", "edit",
    ]

    EXECUTE_PATTERNS = [
        "execute", "run", "eval", "shell", "command", "script",
        "invoke", "call", "spawn", "process",
    ]

    DESTRUCTIVE_PATTERNS = [
        "delete", "remove", "drop", "truncate", "clear", "purge",
        "destroy", "wipe", "reset", "revoke",
    ]

    PRIVILEGED_PATTERNS = [
        "admin", "sudo", "root", "credential", "secret", "token",
        "password", "key", "certificate", "permission", "grant",
    ]

    # Forbidden capabilities that SafetyContract blocks
    FORBIDDEN_CAPABILITIES = {
        "destructive_file_operations",
        "network_attacks",
        "credential_access",
        "privilege_escalation",
        "system_modification",
        "data_exfiltration",
        "malware_execution",
    }

    def __init__(self, overrides: Optional[Dict[str, ToolRiskLevel]] = None):
        """
        Initialize classifier.

        Args:
            overrides: Explicit tool_name → risk_level mappings
        """
        self.overrides = overrides or {}

    def classify(self, tool_name: str, description: str = "") -> ToolRiskLevel:
        """
        Classify a tool's risk level.

        Args:
            tool_name: Name of the MCP tool
            description: Tool description for additional context

        Returns:
            ToolRiskLevel classification
        """
        # Check explicit overrides first
        if tool_name in self.overrides:
            return self.overrides[tool_name]

        # Normalize for pattern matching
        name_lower = tool_name.lower()
        desc_lower = description.lower()
        combined = f"{name_lower} {desc_lower}"

        # Check patterns in order of severity (most severe first)
        if any(p in combined for p in self.PRIVILEGED_PATTERNS):
            return ToolRiskLevel.PRIVILEGED

        if any(p in combined for p in self.DESTRUCTIVE_PATTERNS):
            return ToolRiskLevel.DESTRUCTIVE

        if any(p in combined for p in self.EXECUTE_PATTERNS):
            return ToolRiskLevel.EXECUTE

        if any(p in combined for p in self.WRITE_PATTERNS):
            return ToolRiskLevel.WRITE

        if any(p in combined for p in self.READ_ONLY_PATTERNS):
            return ToolRiskLevel.READ_ONLY

        # Default to WRITE (safer than assuming READ_ONLY)
        return ToolRiskLevel.WRITE

    def get_min_confidence(self, risk_level: ToolRiskLevel) -> float:
        """Get minimum confidence threshold for a risk level."""
        thresholds = {
            ToolRiskLevel.READ_ONLY: 0.3,
            ToolRiskLevel.WRITE: 0.5,
            ToolRiskLevel.EXECUTE: 0.7,
            ToolRiskLevel.DESTRUCTIVE: 0.85,
            ToolRiskLevel.PRIVILEGED: 0.95,
        }
        return thresholds.get(risk_level, 0.5)

    def requires_confirmation(self, risk_level: ToolRiskLevel) -> bool:
        """Check if risk level requires human confirmation."""
        return risk_level in [
            ToolRiskLevel.DESTRUCTIVE,
            ToolRiskLevel.PRIVILEGED,
        ]

    def maps_to_forbidden_capability(
        self,
        tool_name: str,
        capabilities: List[str]
    ) -> Optional[str]:
        """
        Check if tool capabilities map to forbidden capabilities.

        Returns the first forbidden capability found, or None.
        """
        for cap in capabilities:
            if cap in self.FORBIDDEN_CAPABILITIES:
                return cap
        return None


# =============================================================================
# Human Escalation Handler
# =============================================================================


class EscalationHandler:
    """
    Handles human escalation for tool calls.

    Default implementation logs and auto-denies.
    Override for interactive confirmation.
    """

    async def request_confirmation(
        self,
        tool_call: MCPToolCall,
        tool_def: MCPToolDefinition,
        gate_decision: ConfidenceGateDecision,
    ) -> bool:
        """
        Request human confirmation for a tool call.

        Args:
            tool_call: The tool call request
            tool_def: Tool definition with risk metadata
            gate_decision: The confidence gate decision

        Returns:
            True if human confirms, False otherwise
        """
        # Default: log and deny
        logger.warning(
            f"Human confirmation required for {tool_call.tool_name} "
            f"(risk={tool_def.risk_level.value}, confidence={gate_decision.confidence.overall:.2f})"
        )
        logger.info(f"Escalation reasons: {gate_decision.escalation.reasons}")
        logger.info(f"Suggested questions: {gate_decision.escalation.suggested_questions}")

        # Default behavior: deny without human present
        return False

    async def notify(
        self,
        tool_call: MCPToolCall,
        tool_def: MCPToolDefinition,
        gate_decision: ConfidenceGateDecision,
    ) -> None:
        """
        Notify human about a tool call (but don't block).

        Args:
            tool_call: The tool call request
            tool_def: Tool definition
            gate_decision: The confidence gate decision
        """
        logger.info(
            f"Tool call notification: {tool_call.tool_name} "
            f"(risk={tool_def.risk_level.value}, confidence={gate_decision.confidence.overall:.2f})"
        )


class InteractiveEscalationHandler(EscalationHandler):
    """
    Escalation handler that calls a confirmation callback.

    Use this when you have a UI or messaging interface.
    """

    def __init__(
        self,
        confirm_callback: Callable[[MCPToolCall, MCPToolDefinition, ConfidenceGateDecision], Awaitable[bool]],
        notify_callback: Optional[Callable[[MCPToolCall, MCPToolDefinition, ConfidenceGateDecision], Awaitable[None]]] = None,
        timeout_seconds: float = 300.0,
    ):
        self.confirm_callback = confirm_callback
        self.notify_callback = notify_callback
        self.timeout_seconds = timeout_seconds

    async def request_confirmation(
        self,
        tool_call: MCPToolCall,
        tool_def: MCPToolDefinition,
        gate_decision: ConfidenceGateDecision,
    ) -> bool:
        try:
            return await asyncio.wait_for(
                self.confirm_callback(tool_call, tool_def, gate_decision),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Confirmation timeout for {tool_call.tool_name}")
            return False

    async def notify(
        self,
        tool_call: MCPToolCall,
        tool_def: MCPToolDefinition,
        gate_decision: ConfidenceGateDecision,
    ) -> None:
        if self.notify_callback:
            await self.notify_callback(tool_call, tool_def, gate_decision)


# =============================================================================
# MCP Client Interface
# =============================================================================


class MCPClientInterface:
    """
    Interface for MCP client implementations.

    Implement this to connect to actual MCP servers.
    """

    async def call_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Any:
        """
        Call an MCP tool.

        Args:
            tool_name: Name of the tool to call
            parameters: Tool parameters
            timeout: Execution timeout in seconds

        Returns:
            Tool result

        Raises:
            Exception on failure
        """
        raise NotImplementedError("Implement in subclass")

    async def list_tools(self) -> List[MCPToolDefinition]:
        """
        List available MCP tools.

        Returns:
            List of tool definitions
        """
        raise NotImplementedError("Implement in subclass")


class MockMCPClient(MCPClientInterface):
    """Mock MCP client for testing."""

    def __init__(self, tools: Optional[Dict[str, Any]] = None):
        self.tools = tools or {}
        self.call_history: List[Dict[str, Any]] = []

    def register_tool(
        self,
        name: str,
        handler: Callable[[Dict[str, Any]], Any],
        risk_level: ToolRiskLevel = ToolRiskLevel.READ_ONLY,
    ):
        """Register a mock tool."""
        self.tools[name] = {"handler": handler, "risk_level": risk_level}

    async def call_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Any:
        self.call_history.append({
            "tool_name": tool_name,
            "parameters": parameters,
            "timestamp": datetime.now().isoformat(),
        })

        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        handler = self.tools[tool_name]["handler"]

        # Support both sync and async handlers
        if asyncio.iscoroutinefunction(handler):
            return await asyncio.wait_for(handler(parameters), timeout=timeout)
        else:
            return handler(parameters)

    async def list_tools(self) -> List[MCPToolDefinition]:
        return [
            MCPToolDefinition(
                name=name,
                description=f"Mock tool: {name}",
                risk_level=info["risk_level"],
            )
            for name, info in self.tools.items()
        ]


# =============================================================================
# Safe MCP Gateway
# =============================================================================


class SafeMCPGateway:
    """
    Safe gateway for MCP tool calls.

    Every tool call goes through:
    1. Risk classification
    2. Confidence gating
    3. Safety contract checking
    4. Human escalation (if required)
    5. Execution with timeout
    6. Audit logging

    USAGE:
        # Create gateway with MCP client
        gateway = SafeMCPGateway(mcp_client=my_mcp_client)

        # Call a tool
        result = await gateway.call_tool(MCPToolCall(
            tool_name="file_read",
            parameters={"path": "/tmp/data.txt"},
            quality_score=0.8,
            coherence_score=0.9,
        ))

        # Check result
        if result.success:
            print(result.result)
        else:
            print(f"Blocked: {result.blocked_reason}")
    """

    def __init__(
        self,
        mcp_client: MCPClientInterface,
        confidence_gate: Optional[ConfidenceGate] = None,
        risk_classifier: Optional[ToolRiskClassifier] = None,
        escalation_handler: Optional[EscalationHandler] = None,
        tool_definitions: Optional[Dict[str, MCPToolDefinition]] = None,
        audit_enabled: bool = True,
        forbidden_capabilities: Optional[set] = None,
        audit_store: Optional[GovernanceAuditStore] = None,
    ):
        """
        Initialize Safe MCP Gateway.

        Args:
            mcp_client: MCP client for actual tool execution
            confidence_gate: Gate for confidence-based control (default: create new)
            risk_classifier: Tool risk classifier (default: create new)
            escalation_handler: Handler for human escalation (default: logging handler)
            tool_definitions: Explicit tool definitions (overrides auto-classification)
            audit_enabled: Whether to log all operations
            forbidden_capabilities: Capabilities to always block
            audit_store: Durable audit store for persistence (default: None,
                         in-memory only).  When provided, every audit entry is
                         persisted to the store in addition to the in-memory log.
        """
        self.mcp_client = mcp_client
        self.gate = confidence_gate or create_confidence_gate()
        self.classifier = risk_classifier or ToolRiskClassifier()
        self.escalation = escalation_handler or EscalationHandler()
        self.tool_definitions = tool_definitions or {}
        self.audit_enabled = audit_enabled
        self.forbidden_capabilities = forbidden_capabilities or ToolRiskClassifier.FORBIDDEN_CAPABILITIES

        # In-memory audit log (cache / view)
        self.audit_log: List[AuditEntry] = []

        # Durable persistent audit store (source of truth when present)
        self._audit_store: Optional[GovernanceAuditStore] = audit_store

    def register_tool(self, tool_def: MCPToolDefinition) -> None:
        """
        Register a tool definition.

        Args:
            tool_def: Tool definition with risk metadata
        """
        self.tool_definitions[tool_def.name] = tool_def

    def _get_tool_definition(self, tool_name: str) -> MCPToolDefinition:
        """Get or create tool definition."""
        if tool_name in self.tool_definitions:
            return self.tool_definitions[tool_name]

        # Auto-classify
        risk_level = self.classifier.classify(tool_name)
        return MCPToolDefinition(
            name=tool_name,
            description=f"Auto-classified tool: {tool_name}",
            risk_level=risk_level,
            min_confidence=self.classifier.get_min_confidence(risk_level),
            requires_confirmation=self.classifier.requires_confirmation(risk_level),
        )

    def _build_signals(
        self,
        tool_call: MCPToolCall,
        tool_def: MCPToolDefinition,
    ) -> ConfidenceSignals:
        """Build confidence signals for gating."""
        # Map risk level to action complexity/reversibility
        complexity_map = {
            ToolRiskLevel.READ_ONLY: 0.1,
            ToolRiskLevel.WRITE: 0.4,
            ToolRiskLevel.EXECUTE: 0.7,
            ToolRiskLevel.DESTRUCTIVE: 0.9,
            ToolRiskLevel.PRIVILEGED: 0.95,
        }

        reversibility_map = {
            ToolRiskLevel.READ_ONLY: 1.0,
            ToolRiskLevel.WRITE: 0.7,
            ToolRiskLevel.EXECUTE: 0.5,
            ToolRiskLevel.DESTRUCTIVE: 0.0,
            ToolRiskLevel.PRIVILEGED: 0.2,
        }

        return ConfidenceSignals(
            quality_score=tool_call.quality_score,
            coherence_score=tool_call.coherence_score,
            correctness_score=tool_call.quality_score,
            internal_consistency=tool_call.coherence_score,
            action_complexity=complexity_map.get(tool_def.risk_level, 0.5),
            action_reversibility=reversibility_map.get(tool_def.risk_level, 0.5),
        )

    def _check_forbidden_capabilities(
        self,
        tool_def: MCPToolDefinition,
    ) -> Optional[str]:
        """Check if tool uses forbidden capabilities."""
        for cap in tool_def.capabilities:
            if cap in self.forbidden_capabilities:
                return cap
        return None

    def _jepa_check(
        self,
        tool_call: MCPToolCall,
        tool_def: MCPToolDefinition,
        gate_decision: ConfidenceGateDecision,
    ) -> Optional[str]:
        """Run JEPA residual check. Returns block reason or None if OK.

        JEPA can only block; it cannot make a blocked call allowed.
        Returns None for NORMAL regime, a blocking reason string for
        DUAL_ANOMALY or UNKNOWN, and None (pass-through) for PROCESS_DRIFT
        and SEMANTIC_SHIFT on read-only tools.
        """
        try:
            # Approximate vritti from confidence signals
            q = tool_call.quality_score
            c = tool_call.coherence_score
            overall = gate_decision.confidence.overall
            pramana = min(1.0, q * 0.6 + c * 0.4)
            viparyaya = max(0.0, 0.5 - q * 0.8)
            vikalpa = max(0.0, 0.4 - c * 0.5)
            nidra = max(0.0, 0.3 - overall * 0.5)
            smrti = 0.1
            total = pramana + viparyaya + vikalpa + smrti + nidra
            if total <= 0:
                vritti_dist = {"pramana": 0.0, "viparyaya": 0.0,
                               "vikalpa": 0.0, "smrti": 0.0, "nidra": 1.0}
            else:
                vritti_dist = {
                    "pramana": pramana / total, "viparyaya": viparyaya / total,
                    "vikalpa": vikalpa / total, "smrti": smrti / total,
                    "nidra": nidra / total,
                }

            assessment = jepa_governance_check(
                layer_weights={
                    "O1_POTENTIAL": 0.3, "O2_IDENTITY": c * 0.8,
                    "O3_EXECUTION": overall * 0.7, "O4_STRUCTURE": c * 0.6,
                    "O5_COGNITION": q * 0.8, "O6_AGENCY": q * 0.7,
                    "O7_REASONING": q * 0.9, "O8_PURPOSE": q * 0.8,
                    "O9_WITNESSES": overall * 0.6, "O10_UNIFYING": c * 0.7,
                    "O11_INTEGRATION": overall * 0.5, "O12_ABSOLVING": overall * 0.4,
                },
                vritti_distribution=vritti_dist,
                coherence=c,
                score=overall,
                action_type="call_tool",
                tool_name=tool_call.tool_name,
                risk_level=tool_def.risk_level.value,
                confidence_score=overall,
                session_id=tool_call.session_id or "",
            )

            if assessment.regime in (GovernanceRegime.DUAL_ANOMALY,
                                     GovernanceRegime.UNKNOWN):
                return (
                    f"JEPA residual governor: {assessment.regime.value} — "
                    f"{assessment.rationale}"
                )

            # PROCESS_DRIFT and SEMANTIC_SHIFT block destructive/privileged tools
            if assessment.regime in (GovernanceRegime.PROCESS_DRIFT,
                                     GovernanceRegime.SEMANTIC_SHIFT):
                if tool_def.risk_level in (ToolRiskLevel.DESTRUCTIVE,
                                           ToolRiskLevel.PRIVILEGED):
                    return (
                        f"JEPA residual governor: {assessment.regime.value} — "
                        f"blocking {tool_def.risk_level.value} tool. "
                        f"{assessment.rationale}"
                    )

            return None  # No block

        except Exception as e:
            logger.error("JEPA check failed in MCP gateway (fail-closed): %s", e)
            return (
                f"JEPA residual governor: UNAVAILABLE — "
                f"JEPA check raised {type(e).__name__}: {e}. Fail-closed."
            )

    def _audit(
        self,
        tool_call: MCPToolCall,
        tool_def: MCPToolDefinition,
        result: MCPToolResult,
        gate_decision: ConfidenceGateDecision,
    ) -> None:
        """Log audit entry to in-memory cache and durable store."""
        if not self.audit_enabled:
            return

        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            request_id=tool_call.request_id,
            tool_name=tool_call.tool_name,
            parameters=tool_call.parameters,
            decision=result.decision,
            confidence=gate_decision.confidence.overall,
            risk_level=tool_def.risk_level,
            session_id=tool_call.session_id,
            execution_time_ms=result.execution_time_ms,
            success=result.success,
            error=result.error,
            human_confirmed=result.human_confirmed,
        )
        self.audit_log.append(entry)

        # Persist to durable store
        if self._audit_store is not None:
            canonical_event = event_from_mcp_audit(
                timestamp=entry.timestamp,
                request_id=entry.request_id,
                tool_name=entry.tool_name,
                parameters=entry.parameters,
                decision=entry.decision.value,
                confidence=entry.confidence,
                risk_level=entry.risk_level.value,
                session_id=entry.session_id or "",
                execution_time_ms=entry.execution_time_ms,
                success=entry.success,
                error=entry.error,
                human_confirmed=entry.human_confirmed,
            )
            try:
                self._audit_store.append(canonical_event)
            except GovernanceAuditError:
                logger.error(
                    "GOVERNANCE AUDIT PERSISTENCE FAILURE for MCP call %s/%s — "
                    "event recorded in-memory but NOT persisted durably",
                    entry.request_id,
                    entry.tool_name,
                    exc_info=True,
                )
                raise

        logger.debug(
            f"MCP Audit: {tool_call.tool_name} "
            f"decision={result.decision.value} "
            f"confidence={gate_decision.confidence.overall:.2f} "
            f"risk={tool_def.risk_level.value}"
        )

    async def call_tool(self, tool_call: MCPToolCall) -> MCPToolResult:
        """
        Call an MCP tool with safety gating.

        Args:
            tool_call: The tool call request

        Returns:
            MCPToolResult with outcome and audit data
        """
        start_time = time.time()

        # Get tool definition
        tool_def = self._get_tool_definition(tool_call.tool_name)

        # Check forbidden capabilities first
        forbidden = self._check_forbidden_capabilities(tool_def)
        if forbidden:
            result = MCPToolResult(
                request_id=tool_call.request_id,
                tool_name=tool_call.tool_name,
                decision=GatewayDecision.BLOCKED,
                success=False,
                blocked_reason=f"Tool uses forbidden capability: {forbidden}",
                risk_level=tool_def.risk_level,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            # Create minimal gate decision for audit
            signals = self._build_signals(tool_call, tool_def)
            gate_decision = self.gate.evaluate(signals, tool_call.tool_name)
            self._audit(tool_call, tool_def, result, gate_decision)
            return result

        # Build confidence signals
        signals = self._build_signals(tool_call, tool_def)

        # Gate the call
        gate_decision = self.gate.evaluate(signals, tool_call.tool_name)

        # JEPA residual governance check
        jepa_block = self._jepa_check(tool_call, tool_def, gate_decision)
        if jepa_block is not None:
            result = MCPToolResult(
                request_id=tool_call.request_id,
                tool_name=tool_call.tool_name,
                decision=GatewayDecision.BLOCKED,
                success=False,
                confidence=gate_decision.confidence.overall,
                escalation_level=gate_decision.escalation.level,
                blocked_reason=jepa_block,
                risk_level=tool_def.risk_level,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            self._audit(tool_call, tool_def, result, gate_decision)
            return result

        # Check minimum confidence for risk level
        if gate_decision.confidence.overall < tool_def.min_confidence:
            result = MCPToolResult(
                request_id=tool_call.request_id,
                tool_name=tool_call.tool_name,
                decision=GatewayDecision.BLOCKED,
                success=False,
                confidence=gate_decision.confidence.overall,
                escalation_level=gate_decision.escalation.level,
                blocked_reason=(
                    f"Confidence {gate_decision.confidence.overall:.2f} below "
                    f"minimum {tool_def.min_confidence:.2f} for {tool_def.risk_level.value} tool"
                ),
                risk_level=tool_def.risk_level,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            self._audit(tool_call, tool_def, result, gate_decision)
            return result

        # Check execution permission
        if not gate_decision.execution.can_execute:
            # Check if we need escalation
            if gate_decision.escalation.requires_human or tool_def.requires_confirmation:
                # Request human confirmation
                confirmed = await self.escalation.request_confirmation(
                    tool_call, tool_def, gate_decision
                )

                if not confirmed:
                    result = MCPToolResult(
                        request_id=tool_call.request_id,
                        tool_name=tool_call.tool_name,
                        decision=GatewayDecision.ESCALATE,
                        success=False,
                        confidence=gate_decision.confidence.overall,
                        escalation_level=gate_decision.escalation.level,
                        blocked_reason="Human confirmation denied or timed out",
                        risk_level=tool_def.risk_level,
                        human_confirmed=False,
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                    self._audit(tool_call, tool_def, result, gate_decision)
                    return result
            else:
                result = MCPToolResult(
                    request_id=tool_call.request_id,
                    tool_name=tool_call.tool_name,
                    decision=GatewayDecision.BLOCKED,
                    success=False,
                    confidence=gate_decision.confidence.overall,
                    escalation_level=gate_decision.escalation.level,
                    blocked_reason=f"Execution blocked: {gate_decision.execution.mode.value}",
                    risk_level=tool_def.risk_level,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
                self._audit(tool_call, tool_def, result, gate_decision)
                return result

        # Handle notification escalation
        if gate_decision.escalation.level == EscalationLevel.NOTIFY:
            await self.escalation.notify(tool_call, tool_def, gate_decision)

        # Check if tool explicitly requires confirmation
        human_confirmed = False
        if tool_def.requires_confirmation:
            confirmed = await self.escalation.request_confirmation(
                tool_call, tool_def, gate_decision
            )
            if not confirmed:
                result = MCPToolResult(
                    request_id=tool_call.request_id,
                    tool_name=tool_call.tool_name,
                    decision=GatewayDecision.ESCALATE,
                    success=False,
                    confidence=gate_decision.confidence.overall,
                    escalation_level=gate_decision.escalation.level,
                    blocked_reason="Required confirmation denied",
                    risk_level=tool_def.risk_level,
                    human_confirmed=False,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
                self._audit(tool_call, tool_def, result, gate_decision)
                return result
            human_confirmed = True

        # Execute the tool call
        try:
            tool_result = await self.mcp_client.call_tool(
                tool_call.tool_name,
                tool_call.parameters,
                timeout=tool_def.timeout_seconds,
            )

            result = MCPToolResult(
                request_id=tool_call.request_id,
                tool_name=tool_call.tool_name,
                decision=GatewayDecision.ALLOWED,
                success=True,
                result=tool_result,
                confidence=gate_decision.confidence.overall,
                escalation_level=gate_decision.escalation.level,
                risk_level=tool_def.risk_level,
                human_confirmed=human_confirmed,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            self._audit(tool_call, tool_def, result, gate_decision)
            return result

        except asyncio.TimeoutError:
            result = MCPToolResult(
                request_id=tool_call.request_id,
                tool_name=tool_call.tool_name,
                decision=GatewayDecision.TIMEOUT,
                success=False,
                error=f"Execution timed out after {tool_def.timeout_seconds}s",
                confidence=gate_decision.confidence.overall,
                escalation_level=gate_decision.escalation.level,
                risk_level=tool_def.risk_level,
                human_confirmed=human_confirmed,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            self._audit(tool_call, tool_def, result, gate_decision)
            return result

        except Exception as e:
            result = MCPToolResult(
                request_id=tool_call.request_id,
                tool_name=tool_call.tool_name,
                decision=GatewayDecision.ERROR,
                success=False,
                error=str(e),
                confidence=gate_decision.confidence.overall,
                escalation_level=gate_decision.escalation.level,
                risk_level=tool_def.risk_level,
                human_confirmed=human_confirmed,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            self._audit(tool_call, tool_def, result, gate_decision)
            return result

    async def call_tool_simple(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        quality_score: float = 0.5,
        coherence_score: float = 0.5,
    ) -> MCPToolResult:
        """
        Simplified tool call with minimal parameters.

        Args:
            tool_name: Name of the tool
            parameters: Tool parameters
            quality_score: Quality score from context
            coherence_score: Coherence score from context

        Returns:
            MCPToolResult
        """
        return await self.call_tool(MCPToolCall(
            tool_name=tool_name,
            parameters=parameters,
            quality_score=quality_score,
            coherence_score=coherence_score,
        ))

    def get_audit_log(
        self,
        tool_name: Optional[str] = None,
        decision: Optional[GatewayDecision] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """
        Get audit log entries.

        Args:
            tool_name: Filter by tool name
            decision: Filter by decision type
            limit: Maximum entries to return

        Returns:
            List of matching audit entries
        """
        entries = self.audit_log

        if tool_name:
            entries = [e for e in entries if e.tool_name == tool_name]

        if decision:
            entries = [e for e in entries if e.decision == decision]

        return entries[-limit:]

    def get_blocked_count(self) -> int:
        """Get count of blocked tool calls."""
        return sum(1 for e in self.audit_log if e.decision == GatewayDecision.BLOCKED)

    def get_success_rate(self) -> float:
        """Get success rate of tool calls."""
        if not self.audit_log:
            return 1.0
        successful = sum(1 for e in self.audit_log if e.success)
        return successful / len(self.audit_log)


# =============================================================================
# Factory Functions
# =============================================================================


def create_safe_mcp_gateway(
    mcp_client: MCPClientInterface,
    strict: bool = False,
    audit_enabled: bool = True,
) -> SafeMCPGateway:
    """
    Create a SafeMCPGateway with standard configuration.

    Args:
        mcp_client: MCP client for tool execution
        strict: Use strict confidence thresholds
        audit_enabled: Enable audit logging

    Returns:
        Configured SafeMCPGateway
    """
    from agentic.agentic_framework.confidence_gate import (
        create_confidence_gate,
        create_strict_confidence_gate,
    )

    gate = create_strict_confidence_gate() if strict else create_confidence_gate()

    return SafeMCPGateway(
        mcp_client=mcp_client,
        confidence_gate=gate,
        audit_enabled=audit_enabled,
    )


def create_mock_mcp_gateway(
    strict: bool = False,
    audit_enabled: bool = True,
) -> SafeMCPGateway:
    """
    Create a SafeMCPGateway with mock client for testing.

    Args:
        strict: Use strict confidence thresholds
        audit_enabled: Enable audit logging

    Returns:
        SafeMCPGateway with MockMCPClient
    """
    mock_client = MockMCPClient()

    # Register some default mock tools
    mock_client.register_tool(
        "file_read",
        lambda p: f"Contents of {p.get('path', 'unknown')}",
        ToolRiskLevel.READ_ONLY,
    )
    mock_client.register_tool(
        "file_write",
        lambda p: f"Wrote to {p.get('path', 'unknown')}",
        ToolRiskLevel.WRITE,
    )
    mock_client.register_tool(
        "search",
        lambda p: [f"Result for {p.get('query', '')}"],
        ToolRiskLevel.READ_ONLY,
    )

    return create_safe_mcp_gateway(
        mcp_client=mock_client,
        strict=strict,
        audit_enabled=audit_enabled,
    )


# =============================================================================
# Public API
# =============================================================================


__all__ = [
    # Enums
    "ToolRiskLevel",
    "GatewayDecision",
    # Data classes
    "MCPToolDefinition",
    "MCPToolCall",
    "MCPToolResult",
    "AuditEntry",
    # Classifier
    "ToolRiskClassifier",
    # Escalation
    "EscalationHandler",
    "InteractiveEscalationHandler",
    # Client interface
    "MCPClientInterface",
    "MockMCPClient",
    # Main gateway
    "SafeMCPGateway",
    # Factory functions
    "create_safe_mcp_gateway",
    "create_mock_mcp_gateway",
]
