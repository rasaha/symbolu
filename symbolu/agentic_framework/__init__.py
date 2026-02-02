"""
Agentic LLM Framework

A framework for building agentic AI systems that wrap existing LLM APIs
(ChatGPT, Gemini, Claude, etc.) with:

1. Goal Decomposition - Extract structured intent from user input
2. Memory Store - Persistent context management external to LLM
3. Reflective Generation - Self-revising responses with quality critic
4. Coherence Tracking - Track conversation-level coherence metrics
5. Safety Contract - Fail-closed action gating

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
]

__version__ = "1.0.0"
