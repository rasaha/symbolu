"""
Sentinel - Agentic LLM Framework

A framework for building agentic AI systems that wrap existing LLM APIs
(ChatGPT, Gemini, Claude, etc.) with:

1. Goal Decomposition - Extract structured intent from user input
2. Memory Store - Persistent context management external to LLM
3. Reflective Generation - Self-revising responses with quality critic
4. Coherence Tracking - Track conversation-level coherence metrics
5. Safety Contract - Fail-closed action gating
6. Local Critic - Cost-optimized quality evaluation (10-100x cheaper)
7. Adaptive Policy Engine - Policy-level memory that modifies behavior
8. Confidence Gate - Behavioral confidence control (gates execution, not annotations)
9. MCP Gateway - Safe tool integration with risk-based access control
10. Proactive Scheduler - Autonomous task execution with safety controls

Usage:
    from agentic.agentic_framework import AgenticLLMWrapper

    # With OpenAI
    from agentic.agentic_framework.llm_adapters import OpenAIAdapter
    llm = OpenAIAdapter(api_key="...")
    agent = AgenticLLMWrapper(llm)

    # Start session
    agent.new_session()

    # Run conversation
    result = agent.run("What is the capital of France?")
    print(result["response"])
"""

from agentic.agentic_framework.agent import AgenticLLMWrapper
from agentic.agentic_framework.goal_decomposition import GoalState, ActionItem, decompose_goal
from agentic.agentic_framework.memory_store import AgentMemory, TurnSnapshot, MemoryStore
from agentic.agentic_framework.reflective_loop import (
    ReflectiveGenerator,
    QualityCritic,
    RuleBasedCritic,
    LLMBasedCritic,
    QualityCritique,
    GenerationResult,
)
from agentic.agentic_framework.coherence_tracker import (
    CoherenceMetrics,
    CoherenceState,
    CoherenceEngine,
)
from agentic.agentic_framework.safety_contract import (
    SafetyContract,
    SafetyContractEvaluator,
)
from agentic.agentic_framework.local_critic import (
    LocalCritic,
    OllamaBackend,
    TransformersBackend,
    LlamaCppBackend,
    CostAwareCriticSelector,
    SelectionStrategy,
    create_ollama_critic,
    create_transformers_critic,
    create_llamacpp_critic,
    create_cost_aware_critic,
)
from agentic.agentic_framework.adaptive_policy import (
    AdaptivePolicyEngine,
    SessionTrajectory,
    ToolPermission,
    PolicyDecision,
    PolicyParameters,
    SessionPerformanceHistory,
    PerformanceSnapshot,
    create_adaptive_policy_engine,
)
from agentic.agentic_framework.confidence_gate import (
    ConfidenceGate,
    ConfidenceSignals,
    UnifiedConfidence,
    EscalationLevel,
    EscalationDecision,
    ExecutionMode,
    ExecutionPermission,
    BudgetAllocation,
    MemoryWeight,
    ConfidenceGateDecision,
    create_confidence_gate,
    create_strict_confidence_gate,
    create_permissive_confidence_gate,
    signals_from_critique,
    signals_from_coherence_metrics,
    signals_from_policy_decision,
    merge_signals,
)
from agentic.agentic_framework.sovereign_bridge import (
    signals_from_sovereign_state,
    coherence_from_sovereign_state,
    SovereignCoherenceState,
)
from agentic.agentic_framework.mcp_gateway import (
    SafeMCPGateway,
    MCPToolCall,
    MCPToolResult,
    ToolRiskLevel,
    ToolRiskClassifier,
    AuditEntry,
    MCPClientInterface,
    MockMCPClient,
    create_safe_mcp_gateway,
    create_mock_mcp_gateway,
)
from agentic.agentic_framework.proactive_scheduler import (
    ProactiveScheduler,
    ScheduledTask,
    ExecutionRecord,
    CronExpression,
    TaskStatus,
    ScheduleType,
    create_proactive_scheduler,
    create_task,
)
from agentic.agentic_framework.streaming_events import (
    AgentRunEvent,
    make_event,
    RUN_STARTED,
    GENERATION_STARTED,
    TEXT_CHUNK,
    GENERATION_COMPLETED,
    SAFETY_GATE_RESULT,
    ACTION_STARTED,
    ACTION_COMPLETED,
    RUN_COMPLETED,
    RUN_ERROR,
    REVISION_STARTED,
    REVISION_COMPLETED,
)
from agentic.agentic_framework.llm_adapters import (
    MistralAdapter,
    MistralCGAdapter,
)
from agentic.agentic_framework.adaptive_prompts import (
    AutoReasoningPipeline,
    AdaptivePromptEngine,
    AdaptivePromptTemplates,
    ComplexityDetector,
    ReasoningDepth,
    ComplexitySignal,
    ReasoningStage,
    ComplexityAnalysis,
    ReasoningStep,
    AdaptivePromptResult,
    create_adaptive_pipeline,
    create_progressive_pipeline,
    create_always_deep_pipeline,
    create_conservative_pipeline,
)

__all__ = [
    # Main agent
    "AgenticLLMWrapper",
    # Goal decomposition
    "GoalState",
    "ActionItem",
    "decompose_goal",
    # Memory
    "AgentMemory",
    "TurnSnapshot",
    "MemoryStore",
    # Reflective generation
    "ReflectiveGenerator",
    "QualityCritic",
    "RuleBasedCritic",
    "LLMBasedCritic",
    "QualityCritique",
    "GenerationResult",
    # Coherence
    "CoherenceMetrics",
    "CoherenceState",
    "CoherenceEngine",
    # Safety
    "SafetyContract",
    "SafetyContractEvaluator",
    # Local Critics (cheap reflection)
    "LocalCritic",
    "OllamaBackend",
    "TransformersBackend",
    "LlamaCppBackend",
    "CostAwareCriticSelector",
    "SelectionStrategy",
    "create_ollama_critic",
    "create_transformers_critic",
    "create_llamacpp_critic",
    "create_cost_aware_critic",
    # Adaptive Policy Engine (policy-level memory)
    "AdaptivePolicyEngine",
    "SessionTrajectory",
    "ToolPermission",
    "PolicyDecision",
    "PolicyParameters",
    "SessionPerformanceHistory",
    "PerformanceSnapshot",
    "create_adaptive_policy_engine",
    # Confidence Gate (behavioral confidence control)
    "ConfidenceGate",
    "ConfidenceSignals",
    "UnifiedConfidence",
    "EscalationLevel",
    "EscalationDecision",
    "ExecutionMode",
    "ExecutionPermission",
    "BudgetAllocation",
    "MemoryWeight",
    "ConfidenceGateDecision",
    "create_confidence_gate",
    "create_strict_confidence_gate",
    "create_permissive_confidence_gate",
    "signals_from_critique",
    "signals_from_coherence_metrics",
    "signals_from_policy_decision",
    "merge_signals",
    # Sovereign State Bridge (V11.0.0: tensor → agentic wiring)
    "signals_from_sovereign_state",
    "coherence_from_sovereign_state",
    "SovereignCoherenceState",
    # MCP Gateway (safe tool integration)
    "SafeMCPGateway",
    "MCPToolCall",
    "MCPToolResult",
    "ToolRiskLevel",
    "ToolRiskClassifier",
    "AuditEntry",
    "MCPClientInterface",
    "MockMCPClient",
    "create_safe_mcp_gateway",
    "create_mock_mcp_gateway",
    # Proactive Scheduler (autonomous task execution)
    "ProactiveScheduler",
    "ScheduledTask",
    "ExecutionRecord",
    "CronExpression",
    "TaskStatus",
    "ScheduleType",
    "create_proactive_scheduler",
    "create_task",
    # Streaming Events (R1)
    "AgentRunEvent",
    "make_event",
    "RUN_STARTED",
    "GENERATION_STARTED",
    "TEXT_CHUNK",
    "GENERATION_COMPLETED",
    "SAFETY_GATE_RESULT",
    "ACTION_STARTED",
    "ACTION_COMPLETED",
    "RUN_COMPLETED",
    "RUN_ERROR",
    "REVISION_STARTED",
    "REVISION_COMPLETED",
    # LLM Adapters (Mistral API + local MistralCG)
    "MistralAdapter",
    "MistralCGAdapter",
    # Adaptive Prompts (automated AI reasoning)
    "AutoReasoningPipeline",
    "AdaptivePromptEngine",
    "AdaptivePromptTemplates",
    "ComplexityDetector",
    "ReasoningDepth",
    "ComplexitySignal",
    "ReasoningStage",
    "ComplexityAnalysis",
    "ReasoningStep",
    "AdaptivePromptResult",
    "create_adaptive_pipeline",
    "create_progressive_pipeline",
    "create_always_deep_pipeline",
    "create_conservative_pipeline",
]

__version__ = "1.7.0"  # V11.0.0: Sovereign State Bridge (tensor → agentic wiring)
