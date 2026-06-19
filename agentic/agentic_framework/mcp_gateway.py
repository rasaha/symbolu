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
    safe_jepa_governance_check,
    apply_jepa_override,
    approximate_layer_weights,
    approximate_vritti,
)
from agentic.agentic_framework.signal_adapters.vritti_adapter import (
    resolve_vritti_signal,
    VrittiResolution,
    VrittiSignalSource,
)
from agentic.agentic_framework.signal_adapters.entropy_adapter import (
    resolve_entropy_signal,
    EntropyResolution,
)
from agentic.agentic_framework.signal_adapters.raw_entropy_adapter import (
    resolve_raw_entropy_signal,
)
from agentic.agentic_framework.signal_adapters.confidence_risk_gap import (
    assess_confidence_risk_gap,
)
from agentic.agentic_framework.signal_config import (
    DEFAULT_SIGNAL_CONFIG,
    SignalConfig,
)
from agentic.agentic_framework.domain_policy import (
    DomainActionMode,
    DomainPolicyResult,
    DomainRegistry,
    resolve_domain_policy,
    fail_closed_result as _domain_fail_closed,
)
from agentic.agentic_framework.shadow_ai import (
    ShadowAssessment,
    ShadowContainmentMode,
    ShadowRegistry,
    is_memory_write_intent,
    resolve_shadow_asset_id,
    safe_resolve_shadow_policy,
    shadow_containment_to_governance,
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
class ToolSpec:
    """Bundle a tool handler with its governance metadata.

    Convenience type for :meth:`SafeMCPGateway.register_tool_with_handler`
    and :func:`build_agent`.  Combines the callable that does the work
    with the ``MCPToolDefinition`` that tells the gateway how to gate it.

    Example::

        spec = ToolSpec(
            handler=lambda p: {"results": search(p["query"])},
            description="Search academic papers",
            risk_level=ToolRiskLevel.READ_ONLY,
            capabilities=["research"],
        )
    """
    handler: Callable[[Dict[str, Any]], Any]
    description: str = ""
    risk_level: ToolRiskLevel = ToolRiskLevel.READ_ONLY
    capabilities: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    min_confidence: float = 0.3
    timeout_seconds: float = 30.0
    input_schema: Dict[str, Any] = field(default_factory=dict)


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

    # Entropy signal (optional — canonical producer: agentic/entropy/EntropyEngine)
    # Duck-typed: must expose .combined_entropy, .guna_entropy, .kosha_entropy,
    # .cross_domain_entropy, .gate. Absent entropy does not weaken governance
    # posture (fail-closed). Consumed by _jepa_check() via entropy_adapter.
    # NOTE: this is the CG 32-D sovereign-state entropy — EXPERIMENTAL since the
    # 2026-06 falsification (off by default; see SignalConfig.enable_cg_state_signals).
    entropy_result: Optional[Any] = field(default=None)

    # Raw next-token uncertainty (FIRST-CLASS, provider-agnostic). Supply ONE of:
    #   raw_entropy: precomputed normalized predictive entropy in [0, 1], or
    #   raw_logprobs: a (possibly top-k) logprobs list to compute it from.
    # All optional — absence degrades to verbalized confidence + risk taxonomy.
    raw_entropy: Optional[float] = field(default=None)
    raw_logprobs: Optional[Any] = field(default=None)
    # The model's self-reported "is this action safe?" confidence in [0, 1]
    # (higher = safer). Pairs with raw_entropy to drive the confidence-risk gap.
    verbalized_safety_confidence: Optional[float] = field(default=None)

    # Phase 2: optional permission profile (requested vs granted) for the deterministic
    # permission-overclaim observable. Dormant by default — when None the observable is
    # inert and the recorded/authoritative decision is unchanged.
    permission_context: Optional[Any] = None

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

    # JEPA governance fields (populated when JEPA check runs)
    jepa_regime: Optional[str] = None
    jepa_recommended_action: Optional[str] = None
    jepa_reason_codes: Optional[List[str]] = None
    jepa_confidence_adjustment: Optional[float] = None
    jepa_execution_mode_override: Optional[str] = None
    jepa_escalation_override: Optional[str] = None
    jepa_overrode: bool = False

    # Domain policy fields (populated when domain policy check runs)
    domain_policy: Optional[Dict[str, Any]] = None
    domain_overrode: bool = False

    # Shadow AI Control Layer fields
    shadow_assessment: Optional[Dict[str, Any]] = None
    shadow_overrode: bool = False

    # Phase 1: Signal source provenance
    vritti_signal_source: Optional[str] = None
    vritti_signal_degraded: Optional[bool] = None
    vritti_signal_detail: Optional[str] = None
    entropy_available: Optional[bool] = None
    entropy_combined: Optional[float] = None
    entropy_confidence_penalty: Optional[float] = None
    entropy_gate: Optional[str] = None
    entropy_detail: Optional[str] = None
    # 2026-06 pivot: raw next-token entropy (first-class signal) + confidence-risk gap.
    raw_entropy_available: Optional[bool] = None
    raw_entropy: Optional[float] = None
    raw_entropy_source: Optional[str] = None
    confidence_risk_gap_escalate: Optional[bool] = None
    confidence_risk_gap_value: Optional[float] = None
    confidence_risk_gap_reason: Optional[str] = None
    confidence_risk_gap_verbalized_safety: Optional[float] = None

    # Phase 3: Session enrichment provenance
    session_identity_type: Optional[str] = None
    session_identity_unstable: Optional[bool] = None
    session_motivation_type: Optional[str] = None
    session_motivation_risk: Optional[bool] = None
    session_temporal_state: Optional[str] = None
    session_temporal_tense: Optional[bool] = None
    session_confidence_adjustment: Optional[float] = None
    session_enrichment_detail: Optional[str] = None

    # Phase 1.5: trust-core shadow comparison (populated when trust_mode != legacy).
    # The trust decision is computed in PARALLEL and recorded; in shadow/trust_core the
    # gateway still ACTS on the legacy decision (the flip to authoritative is parity-gated).
    trust_decision: Optional[str] = None            # trust core's parallel decision
    trust_legacy_decision: Optional[str] = None     # legacy decision mapped to trust space
    trust_mismatch: Optional[bool] = None           # do they disagree?
    trust_mismatch_class: Optional[str] = None      # match | intended | unintended | unsafe_relaxation
    trust_drivers: Optional[List[str]] = None       # which observables drove the trust decision
    trust_reason: Optional[str] = None              # human-readable trust rationale


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
        domain_registry: Optional[DomainRegistry] = None,
        domain_id: Optional[str] = None,
        shadow_registry: Optional[ShadowRegistry] = None,
        signal_config: Optional[SignalConfig] = None,
        trust_mode: Optional[Any] = None,
        trust_authority_policy: Optional[Any] = None,
        enable_outcome_reputation: bool = False,
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
            domain_registry: Optional DomainRegistry for domain-specific policy.
            domain_id: Which domain profile to use from the registry.
            shadow_registry: Optional ShadowRegistry for shadow AI control.
            trust_mode: Trust decision-core mode — "legacy" (default; not computed),
                        "shadow" (computed + recorded, legacy acts), or "trust_core"
                        (authoritative for the reviewed JEPA-relax path only, when paired
                        with the "reviewed" authority policy). Reverting to "shadow"/"legacy"
                        instantly disables the relax.
            trust_authority_policy: Authority policy — "parity" (default; reproduce legacy,
                        no relax even under trust_core) or "reviewed" (JEPA demoted to
                        confirm-only; the flip candidate). May also be an AuthorityPolicy.
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

        # Domain Semantic Policy Layer
        self._domain_registry: Optional[DomainRegistry] = domain_registry
        self._domain_id: Optional[str] = domain_id

        # Shadow AI Control Layer
        self._shadow_registry: Optional[ShadowRegistry] = shadow_registry

        # Model-uncertainty signal configuration. Default: raw next-token entropy is
        # the first-class signal; the CG 32-D sovereign-state signals are demoted to
        # experimental (off). The confidence-risk gap (confident-but-uncertain ->
        # escalate) is on. See signal_config.py / the 2026-06 falsification result.
        self._signal_config: SignalConfig = signal_config or DEFAULT_SIGNAL_CONFIG

        # Phase 1.5 migration: trust decision core mode (legacy | shadow | trust_core).
        # Default LEGACY = zero behavior change. SHADOW computes the trust decision in
        # parallel and records it (still acts on legacy). TRUST_CORE makes the trust core
        # AUTHORITATIVE for the reviewed JEPA-relax path ONLY — and only when paired with
        # the REVIEWED authority policy below: a JEPA-SOLE block is relaxed to a human
        # CONFIRM (never a silent ALLOW). The parity gate for this flip is met (0 unintended,
        # 0 unsafe_relaxation over the parity/shadow-volume corpora); it stays opt-in.
        from agentic.agentic_framework.trust.parity import (
            PARITY_POLICY, REVIEWED_POLICY, TrustMode)
        self._trust_mode: TrustMode = (
            TrustMode(trust_mode) if trust_mode is not None else TrustMode.LEGACY)
        # Authority policy for the shadow/parity mapping AND the TRUST_CORE relax (which
        # heuristics may BLOCK vs only CONFIRM). Default PARITY = reproduce legacy exactly
        # (no relax even under TRUST_CORE). REVIEWED demotes JEPA to confirm-only (Phase
        # 1.5A) — the flip candidate. Accepts a policy object or the strings "parity" /
        # "reviewed". Under SHADOW this affects only the recorded comparison, never legacy;
        # under TRUST_CORE+REVIEWED it relaxes JEPA-sole blocks to human confirmation.
        _policy_by_name = {"parity": PARITY_POLICY, "reviewed": REVIEWED_POLICY}
        if trust_authority_policy is None:
            self._trust_authority_policy = PARITY_POLICY
        elif isinstance(trust_authority_policy, str):
            self._trust_authority_policy = _policy_by_name[trust_authority_policy.lower()]
        else:
            self._trust_authority_policy = trust_authority_policy

        # Phase 2: outcome-reputation observable. Off by default → never computed, so the
        # recorded/authoritative decision is unchanged. When True, reputation is derived from
        # the gateway's own audit log (the in-memory view of the durable chain) and fed to the
        # shadow comparison only (still advisory/PROVISIONAL). No new production behaviour.
        self._enable_outcome_reputation = bool(enable_outcome_reputation)

    def register_tool(self, tool_def: MCPToolDefinition) -> None:
        """
        Register a tool definition (metadata only).

        The handler must already be registered on the underlying MCP
        client.  For a one-step alternative that registers both the
        handler and metadata, see :meth:`register_tool_with_handler`.

        Args:
            tool_def: Tool definition with risk metadata
        """
        self.tool_definitions[tool_def.name] = tool_def

    def register_tool_with_handler(
        self,
        name: str,
        spec: "ToolSpec",
    ) -> None:
        """Register a tool handler AND its governance metadata in one call.

        This is the preferred registration path for custom tools.  It
        registers the callable on the underlying ``MockMCPClient`` (or
        any client with a ``register_tool`` method) **and** stores the
        ``MCPToolDefinition`` on the gateway — eliminating the two-step
        dance that was previously required.

        Args:
            name: Tool name (used for routing and audit).
            spec: ``ToolSpec`` bundling the handler with risk metadata.

        Raises:
            TypeError: If the underlying MCP client does not support
                handler registration (i.e. is not a ``MockMCPClient``).
        """
        # Register handler on the underlying client
        client = self.mcp_client
        if not hasattr(client, "register_tool"):
            raise TypeError(
                f"Underlying MCP client ({type(client).__name__}) does "
                "not support handler registration.  "
                "register_tool_with_handler requires a MockMCPClient "
                "or compatible client."
            )
        client.register_tool(name, spec.handler, spec.risk_level)

        # Register governance metadata on the gateway
        self.tool_definitions[name] = MCPToolDefinition(
            name=name,
            description=spec.description,
            risk_level=spec.risk_level,
            capabilities=spec.capabilities,
            requires_confirmation=spec.requires_confirmation,
            min_confidence=spec.min_confidence,
            timeout_seconds=spec.timeout_seconds,
            input_schema=spec.input_schema,
        )

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
    ) -> tuple:
        """Run JEPA residual check. Always returns an assessment.

        Uses safe_jepa_governance_check which catches internal errors
        and returns an explicit UNKNOWN-regime assessment. Never returns
        None — the caller always gets a full assessment object.

        JEPA can only make decisions stricter, never more permissive.

        Phase 1: Now uses vritti signal adapter (prefers real chitta_vritti)
        and resolves entropy for governance context.

        Returns:
            Tuple of (JEPAGovernanceAssessment, VrittiResolution, EntropyResolution).
        """
        q = tool_call.quality_score
        c = tool_call.coherence_score
        overall = gate_decision.confidence.overall

        layer_weights = approximate_layer_weights(
            quality=q,
            coherence=c,
            internal_consistency=c,
            goal_alignment=c,
            trajectory_confidence=overall,
            overall_confidence=overall,
        )

        # CG-state off-by-default GATE (2026-06 falsification). enable_cg_state_signals
        # gates the DECISION, not observability: a caller-attached CG vritti_result /
        # entropy_result is STILL resolved and recorded in audit (as experimental), but
        # when CG is OFF it must not DRIVE the decision. Previously only the CG-entropy
        # confidence *penalty* was gated (below); a real CG vritti_result still flowed
        # into the JEPA regime (which can DEGRADE/CONFIRM/BLOCK) — a partial off-switch.
        # Fix: keep the real resolutions for AUDIT, but feed the JEPA *assessment* (the
        # decision path) the non-CG approximation when CG is off. With the default cloud
        # adapters (no CG metadata) this is a no-op.
        _cg_on = self._signal_config.enable_cg_state_signals

        # Phase 1: Resolve vritti via adapter (real > approximation) — for AUDIT.
        attached_vritti = getattr(tool_call, "vritti_result", None)
        vritti_resolution = resolve_vritti_signal(
            vritti_result=attached_vritti,
            quality=q,
            coherence=c,
            overall_confidence=overall,
            layer_weights=layer_weights,
        )
        # Distribution that actually FEEDS the decision: CG-real only when enabled;
        # otherwise the non-CG approximation (CG decision effect gated off).
        if _cg_on or attached_vritti is None:
            decision_vritti = vritti_resolution
        else:
            decision_vritti = resolve_vritti_signal(
                vritti_result=None,
                quality=q,
                coherence=c,
                overall_confidence=overall,
                layer_weights=layer_weights,
            )
        vritti_dist = decision_vritti.distribution

        # Phase 1: Resolve entropy for governance context — recorded for AUDIT. Its
        # confidence PENALTY is separately gated by enable_cg_state_signals at the call
        # site (cg_entropy_penalty); entropy never feeds the JEPA regime.
        entropy_result = getattr(tool_call, "entropy_result", None)
        combined_entropy = getattr(tool_call, "combined_entropy", None)
        entropy_resolution = resolve_entropy_signal(
            entropy_result=entropy_result,
            combined_entropy=combined_entropy,
        )

        assessment = safe_jepa_governance_check(
            layer_weights=layer_weights,
            vritti_distribution=vritti_dist,
            coherence=decision_vritti.coherence,
            score=decision_vritti.score,
            action_type="call_tool",
            tool_name=tool_call.tool_name,
            risk_level=tool_def.risk_level.value,
            confidence_score=overall,
            agency_level="FULL",
            execution_mode=gate_decision.execution.mode.value
                if hasattr(gate_decision.execution.mode, "value")
                else str(gate_decision.execution.mode),
            escalation_level=gate_decision.escalation.level.value
                if hasattr(gate_decision.escalation.level, "value")
                else str(gate_decision.escalation.level),
            session_id=tool_call.session_id or "",
            actor_id="",
            capabilities=list(tool_def.capabilities),
        )

        return assessment, vritti_resolution, entropy_resolution

    def _audit(
        self,
        tool_call: MCPToolCall,
        tool_def: MCPToolDefinition,
        result: MCPToolResult,
        gate_decision: ConfidenceGateDecision,
        jepa_assessment: Optional[Any] = None,
        jepa_overrode: bool = False,
        domain_result: Optional[Any] = None,
        domain_overrode: bool = False,
        shadow_assessment: Optional[ShadowAssessment] = None,
        shadow_overrode: bool = False,
        vritti_resolution: Optional[VrittiResolution] = None,
        entropy_resolution: Optional[EntropyResolution] = None,
        raw_entropy_resolution: Optional[Any] = None,
        confidence_risk_gap: Optional[Any] = None,
        session_enrichment: Optional[Any] = None,
    ) -> None:
        """Log audit entry to in-memory cache and durable store."""
        if not self.audit_enabled:
            return

        domain_audit = (
            domain_result.to_audit_dict()
            if domain_result is not None and hasattr(domain_result, "to_audit_dict")
            else None
        )
        shadow_audit = (
            shadow_assessment.to_audit_dict()
            if shadow_assessment is not None
            else None
        )

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
            jepa_regime=(
                jepa_assessment.regime.value if jepa_assessment else None
            ),
            jepa_recommended_action=(
                jepa_assessment.recommended_action if jepa_assessment else None
            ),
            jepa_reason_codes=(
                list(jepa_assessment.reason_codes) if jepa_assessment else None
            ),
            jepa_confidence_adjustment=(
                jepa_assessment.confidence_adjustment if jepa_assessment else None
            ),
            jepa_execution_mode_override=(
                jepa_assessment.execution_mode_override if jepa_assessment else None
            ),
            jepa_escalation_override=(
                jepa_assessment.escalation_override if jepa_assessment else None
            ),
            jepa_overrode=jepa_overrode,
            domain_policy=domain_audit,
            domain_overrode=domain_overrode,
            shadow_assessment=shadow_audit,
            shadow_overrode=shadow_overrode,
            # Phase 1: Signal source provenance
            vritti_signal_source=(
                vritti_resolution.source.value if vritti_resolution else None
            ),
            vritti_signal_degraded=(
                vritti_resolution.degraded if vritti_resolution else None
            ),
            vritti_signal_detail=(
                vritti_resolution.source_detail if vritti_resolution else None
            ),
            entropy_available=(
                entropy_resolution.available if entropy_resolution else None
            ),
            entropy_combined=(
                entropy_resolution.combined_entropy if entropy_resolution else None
            ),
            entropy_confidence_penalty=(
                entropy_resolution.confidence_penalty if entropy_resolution else None
            ),
            entropy_gate=(
                entropy_resolution.gate if entropy_resolution else None
            ),
            entropy_detail=(
                entropy_resolution.source_detail if entropy_resolution else None
            ),
            raw_entropy_available=(
                raw_entropy_resolution.available if raw_entropy_resolution else None
            ),
            raw_entropy=(
                raw_entropy_resolution.raw_entropy if raw_entropy_resolution else None
            ),
            raw_entropy_source=(
                raw_entropy_resolution.source if raw_entropy_resolution else None
            ),
            confidence_risk_gap_escalate=(
                confidence_risk_gap.escalate if confidence_risk_gap else None
            ),
            confidence_risk_gap_value=(
                confidence_risk_gap.gap if confidence_risk_gap else None
            ),
            confidence_risk_gap_reason=(
                confidence_risk_gap.reason if confidence_risk_gap else None
            ),
            confidence_risk_gap_verbalized_safety=(
                confidence_risk_gap.verbalized_safety if confidence_risk_gap else None
            ),
            # Phase 3: Session enrichment provenance
            session_identity_type=(
                session_enrichment.identity_type if session_enrichment else None
            ),
            session_identity_unstable=(
                session_enrichment.identity_unstable if session_enrichment else None
            ),
            session_motivation_type=(
                session_enrichment.motivation_type if session_enrichment else None
            ),
            session_motivation_risk=(
                session_enrichment.motivation_risk_relevant if session_enrichment else None
            ),
            session_temporal_state=(
                session_enrichment.temporal_state if session_enrichment else None
            ),
            session_temporal_tense=(
                session_enrichment.temporal_tense if session_enrichment else None
            ),
            session_confidence_adjustment=(
                session_enrichment.confidence_adjustment if session_enrichment else None
            ),
            session_enrichment_detail=(
                session_enrichment.source_detail if session_enrichment else None
            ),
        )

        # Phase 1.5: shadow the trust decision core. This runs AFTER the legacy decision
        # is final (the `result` is already decided), so it can NEVER change runtime
        # behavior — it only records the parallel trust decision and any mismatch. The
        # flip to trust_core being authoritative is a separate, parity-gated step.
        from agentic.agentic_framework.trust.parity import TrustMode
        if self._trust_mode != TrustMode.LEGACY:
            try:
                from agentic.agentic_framework.trust.parity import shadow_compare
                # Phase 2: outcome reputation from PRIOR history (audit_log holds entries from
                # earlier calls; the current entry is appended below, so this is historical).
                reputation_context = None
                if self._enable_outcome_reputation:
                    from agentic.agentic_framework.trust.outcome_reputation import (
                        compute_reputation)
                    reputation_context = compute_reputation(
                        self.audit_log, tool_name=tool_call.tool_name)
                cmp = shadow_compare(
                    tool_def=tool_def, result=result, gate_decision=gate_decision,
                    jepa_assessment=jepa_assessment, domain_result=domain_result,
                    shadow_assessment=shadow_assessment, confidence_risk_gap=confidence_risk_gap,
                    forbidden_capabilities=self.forbidden_capabilities,
                    permission_context=getattr(tool_call, "permission_context", None),
                    reputation_context=reputation_context,
                    policy=self._trust_authority_policy)
                entry.trust_decision = cmp.trust.value
                entry.trust_legacy_decision = cmp.legacy.value
                entry.trust_mismatch = cmp.mismatch
                entry.trust_mismatch_class = cmp.classification
                entry.trust_drivers = [o.name for o in cmp.outcome.drivers]
                entry.trust_reason = cmp.outcome.reason
                if cmp.mismatch:
                    logger.warning(
                        "TRUST SHADOW MISMATCH [%s] %s: legacy=%s trust=%s (%s) — drivers=%s",
                        self._trust_mode.value, tool_call.tool_name,
                        cmp.legacy.value, cmp.trust.value, cmp.classification,
                        entry.trust_drivers)
            except Exception:  # pragma: no cover - shadow must never break governance
                logger.exception("trust shadow comparison failed (non-fatal)")

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
                jepa_regime=entry.jepa_regime,
                jepa_recommended_action=entry.jepa_recommended_action,
                jepa_reason_codes=entry.jepa_reason_codes,
                jepa_confidence_adjustment=entry.jepa_confidence_adjustment,
                jepa_execution_mode_override=entry.jepa_execution_mode_override,
                jepa_escalation_override=entry.jepa_escalation_override,
                jepa_overrode=entry.jepa_overrode,
                domain_policy=entry.domain_policy,
                domain_overrode=entry.domain_overrode,
                shadow_assessment=entry.shadow_assessment,
                shadow_overrode=entry.shadow_overrode,
                # Phase 1.5: persist the parallel trust-core shadow decision durably
                # (in-memory only until now) so mismatch data survives for analysis.
                trust_decision=entry.trust_decision,
                trust_legacy_decision=entry.trust_legacy_decision,
                trust_mismatch=entry.trust_mismatch,
                trust_mismatch_class=entry.trust_mismatch_class,
                trust_drivers=entry.trust_drivers,
                trust_reason=entry.trust_reason,
                # Phase 1.5: persist raw-entropy + confidence-risk-gap provenance
                # (already on the entry) so shadow-volume analysis is sliceable by
                # model-uncertainty. Provenance only — no decision observable.
                raw_entropy_available=entry.raw_entropy_available,
                raw_entropy=entry.raw_entropy,
                raw_entropy_source=entry.raw_entropy_source,
                confidence_risk_gap_escalate=entry.confidence_risk_gap_escalate,
                confidence_risk_gap_value=entry.confidence_risk_gap_value,
                confidence_risk_gap_reason=entry.confidence_risk_gap_reason,
                confidence_risk_gap_verbalized_safety=entry.confidence_risk_gap_verbalized_safety,
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
        # Always returns a full assessment (never None). Uses
        # safe_jepa_governance_check which catches errors and returns
        # explicit UNKNOWN-regime assessment on failure.
        jepa_assessment, vritti_resolution, entropy_resolution = self._jepa_check(
            tool_call, tool_def, gate_decision,
        )
        regime = jepa_assessment.regime

        # ---- Model-uncertainty signals (raw entropy is first-class) --------
        # Raw next-token entropy is the DEFAULT uncertainty signal. The CG 32-D
        # sovereign-state entropy (entropy_resolution) is EXPERIMENTAL and only
        # penalizes confidence when explicitly enabled (default off). See the
        # 2026-06 falsification result / signal_config.py.
        raw_entropy_resolution = resolve_raw_entropy_signal(
            raw_entropy=getattr(tool_call, "raw_entropy", None),
            logprobs=getattr(tool_call, "raw_logprobs", None),
            enabled=self._signal_config.enable_raw_entropy_signal,
        )
        cg_entropy_penalty = (
            entropy_resolution.confidence_penalty
            if self._signal_config.enable_cg_state_signals else 0.0
        )

        # Compute JEPA-adjusted confidence and escalation (stricter-only).
        # These are used in all MCPToolResult construction below so that
        # MCP results reflect JEPA overrides, matching GovernanceService.
        effective_confidence = max(
            0.0,
            gate_decision.confidence.overall
            + jepa_assessment.confidence_adjustment
            - raw_entropy_resolution.confidence_penalty
            - cg_entropy_penalty,
        )
        effective_escalation = gate_decision.escalation.level
        _ESC_SEVERITY = {"none": 0, "notify": 1, "confirm": 2, "halt": 3}
        if jepa_assessment.escalation_override is not None:
            jepa_esc = jepa_assessment.escalation_override.lower()
            gate_esc = gate_decision.escalation.level.value
            if _ESC_SEVERITY.get(jepa_esc, 0) > _ESC_SEVERITY.get(gate_esc, 0):
                effective_escalation = EscalationLevel(jepa_esc)

        # ---- Confidence-risk gap: confident-but-uncertain -> escalate ------
        # The falsification finding operationalized: if the model SAYS the action
        # is safe but its raw next-token entropy is high, escalate (stricter-only).
        gap_result = assess_confidence_risk_gap(
            verbalized_safety_confidence=getattr(
                tool_call, "verbalized_safety_confidence", None),
            raw_entropy_resolution=raw_entropy_resolution,
            tool_risk_level=tool_def.risk_level.value,
            config=self._signal_config,
        )
        if gap_result.escalate:
            if (_ESC_SEVERITY.get(gap_result.level, 0)
                    > _ESC_SEVERITY.get(effective_escalation.value, 0)):
                effective_escalation = EscalationLevel(gap_result.level)
            logger.info(
                "confidence-risk gap escalation [%s]: %s",
                tool_call.tool_name, gap_result.reason,
            )
        # Whether the gap demands a human even if the gate would otherwise allow.
        gap_requires_human = gap_result.escalate and gap_result.level in ("confirm", "halt")

        # Domain Semantic Policy Layer check.
        # Computed BEFORE JEPA regime handling so that domain policy
        # is always evaluated and always present in audit — even when
        # JEPA returns early for non-NORMAL regimes (fixes F3).
        domain_result: Optional["DomainPolicyResult"] = None
        domain_overrode = False
        if self._domain_registry is not None and self._domain_id is not None:
            domain_result = resolve_domain_policy(
                jepa_assessment,
                self._domain_registry,
                self._domain_id,
                tool_name=tool_call.tool_name,
            )

        # Phase 1.5B: trust_core authoritative path (ONLY when explicitly selected). When
        # the authority policy demotes JEPA (REVIEWED) and trust_mode is TRUST_CORE, a
        # JEPA-DRIVEN block (not domain-driven) is RELAXED to a human-confirmation instead
        # of a hard block — routed through the EXISTING async confirmation flow below, never
        # a silent allow. Domain/shadow blocks and the confidence floor are unaffected.
        # In LEGACY/SHADOW (default) and under PARITY policy this is inert.
        from agentic.agentic_framework.trust.observables import EvidenceStatus as _Ev
        from agentic.agentic_framework.trust.parity import TrustMode as _TM
        force_confirm = False
        _jepa_relax = (self._trust_mode == _TM.TRUST_CORE
                       and self._trust_authority_policy.jepa != _Ev.PROVEN)

        if regime != GovernanceRegime.NORMAL:
            # Use shared override to determine action
            jepa_override = apply_jepa_override(
                baseline_decision="ALLOW",  # MCP baseline is "proceed"
                baseline_eligible=True,
                assessment=jepa_assessment,
            )

            # Merge domain result with JEPA override (stricter wins).
            # If domain says BLOCKED but JEPA only says DEFER, upgrade.
            merged_decision = jepa_override["decision"]
            if domain_result is not None:
                if domain_result.mode == DomainActionMode.BLOCKED:
                    merged_decision = "DENY"
                    domain_overrode = True
                elif (domain_result.mode.severity
                      >= DomainActionMode.CONFIRM_REQUIRED.severity
                      and merged_decision == "ALLOW"):
                    merged_decision = "DEFER"
                    domain_overrode = True

            # trust_core + JEPA demoted: a JEPA-driven block becomes a human-confirm.
            if _jepa_relax and not domain_overrode and merged_decision in ("DENY", "DEFER"):
                logger.info("TRUST_CORE: JEPA demoted — relaxing %s/%s block to "
                            "human-confirm on %s", regime.value, merged_decision,
                            tool_call.tool_name)
                force_confirm = True
                merged_decision = "ALLOW"  # skip the block returns; confirm enforced below

            if merged_decision == "DENY":
                # DUAL_ANOMALY / UNKNOWN / HALT / domain BLOCKED → hard block
                reason = (
                    f"JEPA residual governor: {regime.value} — "
                    f"{jepa_assessment.rationale}"
                )
                if domain_overrode and domain_result is not None:
                    reason += f" | Domain '{self._domain_id}': {domain_result.rationale}"
                logger.warning("MCP JEPA BLOCK: %s on %s — %s",
                               regime.value, tool_call.tool_name, reason)
                result = MCPToolResult(
                    request_id=tool_call.request_id,
                    tool_name=tool_call.tool_name,
                    decision=GatewayDecision.BLOCKED,
                    success=False,
                    confidence=effective_confidence,
                    escalation_level=effective_escalation,
                    blocked_reason=reason,
                    risk_level=tool_def.risk_level,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
                self._audit(tool_call, tool_def, result, gate_decision,
                            jepa_assessment, jepa_overrode=True,
                            domain_result=domain_result,
                            domain_overrode=domain_overrode,
                            vritti_resolution=vritti_resolution,
                            entropy_resolution=entropy_resolution, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
                return result

            if merged_decision == "DEFER":
                # PROCESS_DRIFT / SEMANTIC_SHIFT → block non-read-only,
                # escalate read-only (consistent with GovernanceService)
                if tool_def.risk_level != ToolRiskLevel.READ_ONLY:
                    reason = (
                        f"JEPA residual governor: {regime.value} — "
                        f"blocking {tool_def.risk_level.value} tool. "
                        f"{jepa_assessment.rationale}"
                    )
                    logger.warning("MCP JEPA BLOCK: %s on %s — %s",
                                   regime.value, tool_call.tool_name, reason)
                    result = MCPToolResult(
                        request_id=tool_call.request_id,
                        tool_name=tool_call.tool_name,
                        decision=GatewayDecision.BLOCKED,
                        success=False,
                        confidence=effective_confidence,
                        escalation_level=effective_escalation,
                        blocked_reason=reason,
                        risk_level=tool_def.risk_level,
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                    self._audit(tool_call, tool_def, result, gate_decision,
                                jepa_assessment, jepa_overrode=True,
                                domain_result=domain_result,
                                domain_overrode=domain_overrode, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
                    return result
                else:
                    # Read-only during drift/shift → escalate (match DEFER)
                    logger.info("MCP JEPA ESCALATE: %s on read-only %s",
                                regime.value, tool_call.tool_name)
                    result = MCPToolResult(
                        request_id=tool_call.request_id,
                        tool_name=tool_call.tool_name,
                        decision=GatewayDecision.ESCALATE,
                        success=False,
                        confidence=effective_confidence,
                        escalation_level=effective_escalation,
                        blocked_reason=(
                            f"JEPA {regime.value}: read-only tool escalated. "
                            f"{jepa_assessment.rationale}"
                        ),
                        risk_level=tool_def.risk_level,
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                    self._audit(tool_call, tool_def, result, gate_decision,
                                jepa_assessment, jepa_overrode=True,
                                domain_result=domain_result,
                                domain_overrode=domain_overrode, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
                    return result

        # JEPA NORMAL — log success and proceed
        if regime == GovernanceRegime.NORMAL:
            logger.debug("MCP JEPA OK: %s on %s — regime NORMAL",
                         jepa_assessment.regime.value, tool_call.tool_name)

        # Domain enforcement for NORMAL regime (domain_result already computed).
        if domain_result is not None:
            if domain_result.mode == DomainActionMode.BLOCKED:
                reason = (
                    f"Domain policy '{self._domain_id}': BLOCKED — "
                    f"{domain_result.rationale}"
                )
                logger.warning("MCP DOMAIN BLOCK: %s on %s — %s",
                               self._domain_id, tool_call.tool_name, reason)
                result = MCPToolResult(
                    request_id=tool_call.request_id,
                    tool_name=tool_call.tool_name,
                    decision=GatewayDecision.BLOCKED,
                    success=False,
                    confidence=effective_confidence,
                    escalation_level=effective_escalation,
                    blocked_reason=reason,
                    risk_level=tool_def.risk_level,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
                self._audit(tool_call, tool_def, result, gate_decision,
                            jepa_assessment, jepa_overrode=False,
                            domain_result=domain_result, domain_overrode=True,
                            vritti_resolution=vritti_resolution,
                            entropy_resolution=entropy_resolution, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
                return result
            elif domain_result.mode in (
                DomainActionMode.CONFIRM_REQUIRED,
                DomainActionMode.SANDBOX_ONLY,
                DomainActionMode.MEMORY_WRITE_DENIED,
            ):
                # Escalate: require human confirmation
                logger.info("MCP DOMAIN ESCALATE: %s on %s — mode=%s",
                            self._domain_id, tool_call.tool_name,
                            domain_result.mode.value)
                result = MCPToolResult(
                    request_id=tool_call.request_id,
                    tool_name=tool_call.tool_name,
                    decision=GatewayDecision.ESCALATE,
                    success=False,
                    confidence=effective_confidence,
                    escalation_level=effective_escalation,
                    blocked_reason=(
                        f"Domain policy '{self._domain_id}': "
                        f"{domain_result.mode.value} — "
                        f"{domain_result.rationale}"
                    ),
                    risk_level=tool_def.risk_level,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
                self._audit(tool_call, tool_def, result, gate_decision,
                            jepa_assessment, jepa_overrode=False,
                            domain_result=domain_result, domain_overrode=True,
                            vritti_resolution=vritti_resolution,
                            entropy_resolution=entropy_resolution, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
                return result
            elif domain_result.mode in (
                DomainActionMode.READ_ONLY,
                DomainActionMode.DRAFT_ONLY,
            ):
                # Block non-read-only tools
                if tool_def.risk_level != ToolRiskLevel.READ_ONLY:
                    reason = (
                        f"Domain policy '{self._domain_id}': "
                        f"{domain_result.mode.value} — blocking "
                        f"{tool_def.risk_level.value} tool. "
                        f"{domain_result.rationale}"
                    )
                    logger.warning("MCP DOMAIN BLOCK: %s on %s — %s",
                                   self._domain_id, tool_call.tool_name,
                                   reason)
                    result = MCPToolResult(
                        request_id=tool_call.request_id,
                        tool_name=tool_call.tool_name,
                        decision=GatewayDecision.BLOCKED,
                        success=False,
                        confidence=effective_confidence,
                        escalation_level=effective_escalation,
                        blocked_reason=reason,
                        risk_level=tool_def.risk_level,
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                    self._audit(tool_call, tool_def, result, gate_decision,
                                jepa_assessment, jepa_overrode=False,
                                domain_result=domain_result,
                                domain_overrode=True,
                                vritti_resolution=vritti_resolution,
                                entropy_resolution=entropy_resolution, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
                    return result

        # Shadow AI Control Layer check
        shadow_assessment: Optional[ShadowAssessment] = None
        shadow_overrode = False
        if self._shadow_registry is not None:
            _risk_to_action = {
                ToolRiskLevel.READ_ONLY: "read_only",
                ToolRiskLevel.WRITE: "mutating",
                ToolRiskLevel.EXECUTE: "mutating",
                ToolRiskLevel.DESTRUCTIVE: "destructive",
                ToolRiskLevel.PRIVILEGED: "privileged",
            }
            action_cat = _risk_to_action.get(tool_def.risk_level, "unknown")
            mutation = action_cat in ("mutating", "destructive", "privileged")

            _sem_mismatch = 0.0
            if regime.value in ("process_drift", "semantic_shift"):
                _sem_mismatch = 0.5
            elif regime.value in ("dual_anomaly", "unknown"):
                _sem_mismatch = 0.8

            _dom_mismatch = 0.0
            if domain_result is not None and domain_result.mode != DomainActionMode.ALLOW:
                _dom_mismatch = domain_result.mode.severity / 6.0

            _shadow_asset_id = resolve_shadow_asset_id(
                tool_name=tool_call.tool_name,
            )
            shadow_assessment = safe_resolve_shadow_policy(
                asset_id=_shadow_asset_id,
                tool_name=tool_call.tool_name,
                registry=self._shadow_registry,
                action_category=action_cat,
                risk_level=tool_def.risk_level.value,
                domain_id=self._domain_id or "",
                memory_write_intent=is_memory_write_intent(
                    tool_name=tool_call.tool_name,
                ),
                mutation_intent=mutation,
                jepa_regime=regime.value,
                semantic_mismatch=_sem_mismatch,
                domain_policy_mismatch=_dom_mismatch,
                confidence=effective_confidence,
            )

            shadow_gov = shadow_containment_to_governance(
                shadow_assessment.containment_mode,
            )
            if shadow_gov == "DENY":
                shadow_overrode = True
                reason = (
                    f"Shadow AI policy: {shadow_assessment.containment_mode.value} — "
                    f"{shadow_assessment.rationale}"
                )
                logger.warning("MCP SHADOW BLOCK: %s on %s — %s",
                               shadow_assessment.containment_mode.value,
                               tool_call.tool_name, reason)
                result = MCPToolResult(
                    request_id=tool_call.request_id,
                    tool_name=tool_call.tool_name,
                    decision=GatewayDecision.BLOCKED,
                    success=False,
                    confidence=effective_confidence,
                    escalation_level=effective_escalation,
                    blocked_reason=reason,
                    risk_level=tool_def.risk_level,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
                self._audit(tool_call, tool_def, result, gate_decision,
                            jepa_assessment, jepa_overrode=False,
                            domain_result=domain_result,
                            shadow_assessment=shadow_assessment,
                            shadow_overrode=True,
                            vritti_resolution=vritti_resolution,
                            entropy_resolution=entropy_resolution, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
                return result
            elif shadow_gov == "DEFER":
                shadow_overrode = True
                reason = (
                    f"Shadow AI policy: {shadow_assessment.containment_mode.value} — "
                    f"{shadow_assessment.rationale}"
                )
                logger.info("MCP SHADOW ESCALATE: %s on %s — %s",
                            shadow_assessment.containment_mode.value,
                            tool_call.tool_name, reason)
                result = MCPToolResult(
                    request_id=tool_call.request_id,
                    tool_name=tool_call.tool_name,
                    decision=GatewayDecision.ESCALATE,
                    success=False,
                    confidence=effective_confidence,
                    escalation_level=effective_escalation,
                    blocked_reason=reason,
                    risk_level=tool_def.risk_level,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
                self._audit(tool_call, tool_def, result, gate_decision,
                            jepa_assessment, jepa_overrode=False,
                            domain_result=domain_result,
                            shadow_assessment=shadow_assessment,
                            shadow_overrode=True,
                            vritti_resolution=vritti_resolution,
                            entropy_resolution=entropy_resolution, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
                return result

        # Check minimum confidence for risk level (use JEPA-adjusted)
        if effective_confidence < tool_def.min_confidence:
            result = MCPToolResult(
                request_id=tool_call.request_id,
                tool_name=tool_call.tool_name,
                decision=GatewayDecision.BLOCKED,
                success=False,
                confidence=effective_confidence,
                escalation_level=effective_escalation,
                blocked_reason=(
                    f"Confidence {effective_confidence:.2f} below "
                    f"minimum {tool_def.min_confidence:.2f} for {tool_def.risk_level.value} tool"
                ),
                risk_level=tool_def.risk_level,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            self._audit(tool_call, tool_def, result, gate_decision,
                        jepa_assessment,
                        domain_result=domain_result,
                        shadow_assessment=shadow_assessment,
                        shadow_overrode=shadow_overrode,
                        vritti_resolution=vritti_resolution,
                        entropy_resolution=entropy_resolution, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
            return result

        # Check execution permission. The confidence-risk gap can require a human
        # even when the gate would allow execution (the gate keys off verbalized
        # confidence alone; the gap adds raw model-uncertainty). `force_confirm` is the
        # trust_core JEPA-demotion path: a relaxed JEPA block MUST require human
        # confirmation here (never a silent allow).
        # Tracks whether a force_confirm/gap escalation was APPROVED by a human, so the
        # executed result records human_confirmed=True and audits as CONFIRM (not a plain
        # ALLOW). Without this, a relaxed JEPA block that a human approves would mis-audit
        # as legacy=allow/trust=confirm (a spurious "unintended" mismatch).
        escalation_confirmed = False
        if not gate_decision.execution.can_execute or gap_requires_human or force_confirm:
            # Check if we need escalation
            if (gate_decision.escalation.requires_human
                    or tool_def.requires_confirmation
                    or gap_requires_human
                    or force_confirm):
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
                        confidence=effective_confidence,
                        escalation_level=effective_escalation,
                        blocked_reason="Human confirmation denied or timed out",
                        risk_level=tool_def.risk_level,
                        human_confirmed=False,
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                    self._audit(tool_call, tool_def, result, gate_decision,
                                jepa_assessment,
                                domain_result=domain_result,
                                shadow_assessment=shadow_assessment,
                                shadow_overrode=shadow_overrode,
                                vritti_resolution=vritti_resolution,
                                entropy_resolution=entropy_resolution, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
                    return result
                # Confirmed: a human approved (force_confirm / gap / requires_human path).
                escalation_confirmed = True
            else:
                result = MCPToolResult(
                    request_id=tool_call.request_id,
                    tool_name=tool_call.tool_name,
                    decision=GatewayDecision.BLOCKED,
                    success=False,
                    confidence=effective_confidence,
                    escalation_level=effective_escalation,
                    blocked_reason=f"Execution blocked: {gate_decision.execution.mode.value}",
                    risk_level=tool_def.risk_level,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
                self._audit(tool_call, tool_def, result, gate_decision,
                            jepa_assessment,
                            domain_result=domain_result,
                            shadow_assessment=shadow_assessment,
                            shadow_overrode=shadow_overrode,
                            vritti_resolution=vritti_resolution,
                            entropy_resolution=entropy_resolution, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
                return result

        # Handle notification escalation
        if gate_decision.escalation.level == EscalationLevel.NOTIFY:
            await self.escalation.notify(tool_call, tool_def, gate_decision)

        # Check if tool explicitly requires confirmation. Seed from any force_confirm/gap
        # approval above so a relaxed-then-approved JEPA block records human_confirmed=True.
        human_confirmed = escalation_confirmed
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
                    confidence=effective_confidence,
                    escalation_level=effective_escalation,
                    blocked_reason="Required confirmation denied",
                    risk_level=tool_def.risk_level,
                    human_confirmed=False,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
                self._audit(tool_call, tool_def, result, gate_decision,
                            jepa_assessment,
                            domain_result=domain_result,
                            shadow_assessment=shadow_assessment,
                            shadow_overrode=shadow_overrode,
                            vritti_resolution=vritti_resolution,
                            entropy_resolution=entropy_resolution, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
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
                confidence=effective_confidence,
                escalation_level=effective_escalation,
                risk_level=tool_def.risk_level,
                human_confirmed=human_confirmed,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            self._audit(tool_call, tool_def, result, gate_decision,
                        jepa_assessment,
                        domain_result=domain_result,
                        shadow_assessment=shadow_assessment,
                        shadow_overrode=shadow_overrode,
                        vritti_resolution=vritti_resolution,
                        entropy_resolution=entropy_resolution, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
            return result

        except asyncio.TimeoutError:
            result = MCPToolResult(
                request_id=tool_call.request_id,
                tool_name=tool_call.tool_name,
                decision=GatewayDecision.TIMEOUT,
                success=False,
                error=f"Execution timed out after {tool_def.timeout_seconds}s",
                confidence=effective_confidence,
                escalation_level=effective_escalation,
                risk_level=tool_def.risk_level,
                human_confirmed=human_confirmed,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            self._audit(tool_call, tool_def, result, gate_decision,
                        jepa_assessment,
                        domain_result=domain_result,
                        shadow_assessment=shadow_assessment,
                        shadow_overrode=shadow_overrode,
                        vritti_resolution=vritti_resolution,
                        entropy_resolution=entropy_resolution, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
            return result

        except Exception as e:
            result = MCPToolResult(
                request_id=tool_call.request_id,
                tool_name=tool_call.tool_name,
                decision=GatewayDecision.ERROR,
                success=False,
                error=str(e),
                confidence=effective_confidence,
                escalation_level=effective_escalation,
                risk_level=tool_def.risk_level,
                human_confirmed=human_confirmed,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            self._audit(tool_call, tool_def, result, gate_decision,
                        jepa_assessment,
                        domain_result=domain_result,
                        shadow_assessment=shadow_assessment,
                        shadow_overrode=shadow_overrode,
                        vritti_resolution=vritti_resolution,
                        entropy_resolution=entropy_resolution, raw_entropy_resolution=raw_entropy_resolution, confidence_risk_gap=gap_result)
            return result

    async def call_tool_simple(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        quality_score: float = 0.5,
        coherence_score: float = 0.5,
        *,
        cg_metadata: Optional[Dict[str, Any]] = None,
        tier: str = "consumer",
        raw_entropy: Optional[float] = None,
        raw_logprobs: Optional[Any] = None,
        verbalized_safety_confidence: Optional[float] = None,
    ) -> MCPToolResult:
        """
        Simplified tool call with minimal parameters.

        Args:
            tool_name: Name of the tool
            parameters: Tool parameters
            quality_score: Quality score from context
            coherence_score: Coherence score from context
            cg_metadata: Optional CG-capable LLM adapter metadata (e.g.
                ``MistralCGAdapter.last_cg_metadata``) carrying the 32D
                sovereign ``state`` and optional ``delta_S``. When
                provided, the sovereign bridge derives a canonical
                ``EntropyResult`` and ``ChittaVrittiResult`` and attaches
                both to the ``MCPToolCall`` before governance evaluation.
                Absent metadata preserves prior behavior exactly.
            tier: Governance tier selector passed through to the bridge
                helper (``"consumer"`` or ``"enterprise"``). Ignored when
                ``cg_metadata`` is None.

        Returns:
            MCPToolResult
        """
        call = MCPToolCall(
            tool_name=tool_name,
            parameters=parameters,
            quality_score=quality_score,
            coherence_score=coherence_score,
            raw_entropy=raw_entropy,
            raw_logprobs=raw_logprobs,
            verbalized_safety_confidence=verbalized_safety_confidence,
        )
        # Request-boundary enrichment seam (Phase 2): a single helper
        # standardizes the "CG metadata → governance kwargs" translation
        # for every boundary caller (here today, AuthorizationRequest
        # tomorrow). Neutral when cg_metadata is None (returns {}), so
        # the default path stays exactly as before.
        from agentic.agentic_framework.request_enrichment import (
            build_governance_enrichment_kwargs,
        )
        enrichment = build_governance_enrichment_kwargs(
            cg_metadata=cg_metadata, tier=tier,
        )
        if "entropy_result" in enrichment:
            call.entropy_result = enrichment["entropy_result"]
        if "vritti_result" in enrichment:
            # vritti_result is duck-typed on MCPToolCall (no formal
            # dataclass field) — the governance consumer reads it via
            # getattr(tool_call, "vritti_result", None). Attach by
            # setattr to honor that contract without widening the model.
            call.vritti_result = enrichment["vritti_result"]
        return await self.call_tool(call)

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
    # Compute/validate tools added to support the
    # DEFAULT_ACTION_TYPE_TO_TOOL mapping in cg_tool_dispatcher.py so
    # AgenticLLMWrapper runtime wiring has concrete endpoints for the
    # "compute" and "validate" action types produced by
    # goal_decomposition without further caller configuration.
    mock_client.register_tool(
        "compute",
        lambda p: {"result": "computed", "input": p},
        ToolRiskLevel.READ_ONLY,
    )
    mock_client.register_tool(
        "validate",
        lambda p: {"valid": True, "input": p},
        ToolRiskLevel.READ_ONLY,
    )

    gateway = create_safe_mcp_gateway(
        mcp_client=mock_client,
        strict=strict,
        audit_enabled=audit_enabled,
    )
    # Pin risk metadata for the compute/validate tools: their names
    # do not match any READ_ONLY pattern in ``ToolRiskClassifier`` and
    # would otherwise fall through to the WRITE default — blocking the
    # DEFAULT_ACTION_TYPE_TO_TOOL path under JEPA drift regimes. The
    # mock handlers are pure functions (no side effects), so READ_ONLY
    # is the honest classification.
    for _name in ("compute", "validate"):
        gateway.register_tool(
            MCPToolDefinition(
                name=_name,
                description=f"Mock {_name} tool (pure, read-only)",
                risk_level=ToolRiskLevel.READ_ONLY,
                min_confidence=0.3,
                requires_confirmation=False,
            )
        )
    return gateway


# =============================================================================
# Public API
# =============================================================================


__all__ = [
    # Enums
    "ToolRiskLevel",
    "GatewayDecision",
    # Data classes
    "ToolSpec",
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
