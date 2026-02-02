"""
Agentic LLM Framework

A framework for building agentic AI systems that wrap existing LLM APIs
(ChatGPT, Gemini, Claude, etc.) with:

1. Goal Decomposition - Extract structured intent from user input
2. Memory Store - Persistent context management external to LLM
3. Reflective Generation - Self-revising responses with quality critic
4. Coherence Tracking - Track conversation-level coherence metrics
5. Safety Contract - Fail-closed action gating
6. Local Critic - Cost-optimized quality evaluation (10-100x cheaper)
7. Adaptive Policy Engine - Policy-level memory that modifies behavior

Usage:
    from symbolu.agentic_framework import AgenticLLMWrapper

    # With OpenAI
    from symbolu.agentic_framework.llm_adapters import OpenAIAdapter
    llm = OpenAIAdapter(api_key="...")
    agent = AgenticLLMWrapper(llm)

    # Start session
    agent.new_session()

    # Run conversation
    result = agent.run("What is the capital of France?")
    print(result["response"])
"""

from symbolu.agentic_framework.agent import AgenticLLMWrapper
from symbolu.agentic_framework.goal_decomposition import GoalState, ActionItem, decompose_goal
from symbolu.agentic_framework.memory_store import AgentMemory, TurnSnapshot, MemoryStore
from symbolu.agentic_framework.reflective_loop import (
    ReflectiveGenerator,
    QualityCritic,
    RuleBasedCritic,
    LLMBasedCritic,
    QualityCritique,
    GenerationResult,
)
from symbolu.agentic_framework.coherence_tracker import (
    CoherenceMetrics,
    CoherenceState,
    CoherenceEngine,
)
from symbolu.agentic_framework.safety_contract import (
    SafetyContract,
    SafetyContractEvaluator,
)
from symbolu.agentic_framework.local_critic import (
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
from symbolu.agentic_framework.adaptive_policy import (
    AdaptivePolicyEngine,
    SessionTrajectory,
    ToolPermission,
    PolicyDecision,
    PolicyParameters,
    SessionPerformanceHistory,
    PerformanceSnapshot,
    create_adaptive_policy_engine,
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
]

__version__ = "1.2.0"  # Added Adaptive Policy Engine
