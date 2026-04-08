"""
Goal Decomposition Component

Extracts structured goal representation from user input.
Inspired by 12D Ontology (O8_PURPOSE, O7_REASONING, O6_AGENCY, O3_EXECUTION).

LAYER MAPPING:
- O8_PURPOSE: High-level goal and intent
- O7_REASONING: Strategy and logical approach
- O6_AGENCY: Autonomy level (FULL, CONFIRM, INFORM)
- O3_EXECUTION: Concrete action items
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol


class LLMClient(Protocol):
    """Protocol for LLM client interface."""

    def call(self, prompt: str) -> str:
        """Call LLM with prompt and return response."""
        ...


@dataclass
class ActionItem:
    """
    Single executable action.

    Represents an atomic, verifiable step in goal execution.
    """

    action_id: str
    description: str
    action_type: str  # "search", "compute", "generate", "validate", "execute"
    status: str = "pending"  # "pending", "in_progress", "completed", "failed", "blocked"
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    original_action_type: Optional[str] = None  # set when normalization changed the type

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        d = {
            "action_id": self.action_id,
            "description": self.description,
            "action_type": self.action_type,
            "status": self.status,
            "parameters": self.parameters,
            "result": self.result,
            "error": self.error,
        }
        if self.original_action_type is not None:
            d["original_action_type"] = self.original_action_type
        return d


@dataclass
class GoalState:
    """
    Structured representation of user intent.

    Maps to 12D Ontology layers:
    - O8_PURPOSE: purpose, purpose_type
    - O7_REASONING: reasoning_strategy, reasoning_steps
    - O6_AGENCY: agency_level, requires_confirmation
    - O3_EXECUTION: actions, dependencies
    """

    # O8_PURPOSE: High-level goal
    purpose: str
    purpose_type: str  # "informational", "task", "creative", "analysis"

    # O7_REASONING: Approach/strategy
    reasoning_strategy: str
    reasoning_steps: List[str] = field(default_factory=list)

    # O6_AGENCY: Autonomy level
    agency_level: str = "CONFIRM"  # "FULL", "CONFIRM", "INFORM"
    requires_confirmation: bool = True

    # O3_EXECUTION: Concrete actions
    actions: List[ActionItem] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)  # action_id -> prerequisites

    # Metadata
    complexity_estimate: float = 0.5  # [0.0, 1.0]
    confidence: float = 0.8  # [0.0, 1.0]
    decomposed_at: datetime = field(default_factory=datetime.utcnow)

    def get_next_action(self) -> Optional[ActionItem]:
        """Get next pending action with satisfied dependencies."""
        completed_ids = {a.action_id for a in self.actions if a.status == "completed"}

        for action in self.actions:
            if action.status != "pending":
                continue

            # Check dependencies
            deps = self.dependencies.get(action.action_id, [])
            if all(dep in completed_ids for dep in deps):
                return action

        return None

    def get_pending_actions(self) -> List[ActionItem]:
        """Get all pending actions."""
        return [a for a in self.actions if a.status == "pending"]

    def get_completed_actions(self) -> List[ActionItem]:
        """Get all completed actions."""
        return [a for a in self.actions if a.status == "completed"]

    def is_complete(self) -> bool:
        """Check if all actions are completed."""
        return all(a.status in ("completed", "skipped") for a in self.actions)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "purpose": self.purpose,
            "purpose_type": self.purpose_type,
            "reasoning_strategy": self.reasoning_strategy,
            "reasoning_steps": self.reasoning_steps,
            "agency_level": self.agency_level,
            "requires_confirmation": self.requires_confirmation,
            "actions": [a.to_dict() for a in self.actions],
            "dependencies": self.dependencies,
            "complexity_estimate": self.complexity_estimate,
            "confidence": self.confidence,
            "decomposed_at": self.decomposed_at.isoformat(),
        }


# Decomposition prompt template
DECOMPOSITION_PROMPT = """
Analyze this user request and extract structured goal information.

User Request: {user_input}

Extract the following:

1. PURPOSE: What is the high-level goal?
   - Type: "informational" (asking for info), "task" (do something),
           "creative" (generate content), "analysis" (analyze/evaluate)

2. REASONING: What approach should be used?
   - Strategy: Brief description of approach
   - Steps: List of logical steps to achieve the goal

3. AGENCY: What level of autonomy is appropriate?
   - "FULL": Act without confirmation (simple, low-risk, clear intent)
   - "CONFIRM": Propose actions, wait for approval (moderate risk, needs verification)
   - "INFORM": Just provide information, no actions (high risk, unclear, or just informational)

4. ACTIONS: List concrete steps to execute (if applicable)
   - Each action should be atomic and verifiable
   - Types: "search", "compute", "generate", "validate", "execute"

5. COMPLEXITY: Estimate complexity from 0.0 (trivial) to 1.0 (very complex)

Respond ONLY with valid JSON in this exact format:
{{
    "purpose": "string describing the goal",
    "purpose_type": "informational|task|creative|analysis",
    "reasoning_strategy": "string describing approach",
    "reasoning_steps": ["step 1", "step 2", ...],
    "agency_level": "FULL|CONFIRM|INFORM",
    "actions": [
        {{
            "description": "what to do",
            "type": "search|compute|generate|validate|execute",
            "parameters": {{}}
        }}
    ],
    "dependencies": {{"action_1": ["action_0"]}},
    "complexity": 0.5
}}
"""


# The five generic action types the DECOMPOSITION_PROMPT asks the LLM
# to produce.  These are the *prompt-side* vocabulary.
GENERIC_ACTION_TYPES = frozenset({"search", "compute", "generate", "validate", "execute"})

# Description keywords that signal specific domain actions.
# Used by context-aware normalization when a generic type (execute,
# generate) could map to multiple domain tools.
# Keys: signal words (lowercase).  Values: set of domain tool names
# they indicate.  Only words with unambiguous signal are included.
_DESCRIPTION_SIGNALS: Dict[str, str] = {
    # send/notify signals
    "send": "send_update",
    "notify": "send_update",
    "post": "send_update",
    "broadcast": "send_update",
    "channel": "send_update",
    "slack": "send_update",
    "message": "send_update",
    "announce": "send_update",
    "alert": "send_update",
    # save/draft signals
    "save": "save_draft",
    "draft": "save_draft",
    "store": "save_draft",
    "persist": "save_draft",
    "write": "save_draft",
    "record": "save_draft",
    # escalate signals
    "escalate": "escalate",
    "incident": "escalate",
    "page": "escalate",
    "on-call": "escalate",
    "oncall": "escalate",
    "urgent": "escalate",
    "emergency": "escalate",
}


def _resolve_by_description(
    description: str,
    candidate_tools: set,
) -> Optional[str]:
    """Pick a domain tool from the description's keyword signals.

    Only returns a tool name when exactly one candidate is signalled.
    Returns ``None`` (ambiguous / no signal) otherwise.
    """
    if not description or not candidate_tools:
        return None

    desc_lower = description.lower()
    # Split into words for matching
    words = set(desc_lower.split())
    # Also check for multi-word phrases by scanning the raw string
    signalled: Dict[str, int] = {}  # tool_name → signal count
    for keyword, tool_name in _DESCRIPTION_SIGNALS.items():
        if tool_name not in candidate_tools:
            continue
        if keyword in words or keyword in desc_lower:
            signalled[tool_name] = signalled.get(tool_name, 0) + 1

    if len(signalled) == 1:
        return next(iter(signalled))
    if len(signalled) > 1:
        # Multiple tools signalled — pick the one with the most signals
        # but only if it has strictly more signals than the runner-up
        ranked = sorted(signalled.items(), key=lambda x: x[1], reverse=True)
        if ranked[0][1] > ranked[1][1]:
            return ranked[0][0]
        # Tied — ambiguous, return None
        return None
    return None


def normalize_action_type(
    raw_type: str,
    action_type_aliases: Optional[Dict[str, str]] = None,
    description: str = "",
) -> tuple:
    """Normalize a raw LLM action type into a canonical runtime type.

    Resolution order:
    1. If ``raw_type`` is already a canonical name (appears as a key
       with identity mapping, or as an alias value), return unchanged.
    2. If ``action_type_aliases`` contains ``raw_type`` as a key with
       a non-identity mapping, return the mapped value.
    3. **Context-aware resolution** (new): If ``raw_type`` is a generic
       prompt type (execute, generate) AND no direct alias exists, use
       the action ``description`` to pick among the domain tools
       registered as alias values.  Only fires when description
       keywords unambiguously signal a single domain tool.
    4. If ``raw_type`` is one of the five generic prompt types and no
       context resolution matched, return it unchanged.
    5. Otherwise, return the raw type unchanged.

    Returns:
        ``(canonical_type, original_type_or_None)``.
        ``original_type_or_None`` is set only when the type was
        remapped (for traceability); ``None`` means no change.
    """
    if action_type_aliases is None:
        action_type_aliases = {}

    raw = raw_type.strip().lower()

    # Exact match in alias keys → remap
    if raw in action_type_aliases:
        target = action_type_aliases[raw]
        if target == raw:
            return raw, None  # identity mapping, no change
        return target, raw

    # Already a known canonical name (appears as an alias value)?
    alias_values = set(action_type_aliases.values())
    if raw in alias_values:
        return raw, None

    # Context-aware resolution for generic types
    if raw in GENERIC_ACTION_TYPES and description and alias_values:
        resolved = _resolve_by_description(description, alias_values)
        if resolved is not None:
            return resolved, raw

    # Generic prompt type that isn't aliased — pass through
    if raw in GENERIC_ACTION_TYPES:
        return raw, None

    # Unknown type — pass through unchanged (runtime will handle)
    return raw, None


def decompose_goal(
    user_input: str,
    llm_client: LLMClient,
    action_type_aliases: Optional[Dict[str, str]] = None,
) -> GoalState:
    """
    Decompose user input into structured GoalState.

    Uses LLM to extract goal structure from natural language.

    Args:
        user_input: Raw user input string
        llm_client: LLM client implementing call() method
        action_type_aliases: Optional mapping from generic/prompt action
            types to canonical runtime action types.  For example,
            ``{"execute": "save_draft"}`` remaps the LLM's "execute"
            label to the runtime's "save_draft" tool.  Types not in
            this mapping pass through unchanged.

    Returns:
        GoalState with extracted structure
    """
    # Build prompt
    prompt = DECOMPOSITION_PROMPT.format(user_input=user_input)

    # Call LLM
    response = llm_client.call(prompt)

    # Parse response
    try:
        # Try to extract JSON from response
        parsed = _extract_json(response)
    except (json.JSONDecodeError, ValueError):
        # Fall back to simple extraction
        parsed = _simple_extraction(user_input)

    # Build GoalState
    actions = []
    for i, action_data in enumerate(parsed.get("actions", [])):
        raw_type = action_data.get("type", "generate")
        desc = action_data.get("description", f"Action {i}")
        canonical, original = normalize_action_type(
            raw_type, action_type_aliases, description=desc,
        )
        actions.append(
            ActionItem(
                action_id=f"action_{i}",
                description=desc,
                action_type=canonical,
                parameters=action_data.get("parameters", {}),
                original_action_type=original,
            )
        )

    agency_level = parsed.get("agency_level", "CONFIRM")

    return GoalState(
        purpose=parsed.get("purpose", user_input),
        purpose_type=parsed.get("purpose_type", "informational"),
        reasoning_strategy=parsed.get("reasoning_strategy", "Direct response"),
        reasoning_steps=parsed.get("reasoning_steps", []),
        agency_level=agency_level,
        requires_confirmation=agency_level != "FULL",
        actions=actions,
        dependencies=parsed.get("dependencies", {}),
        complexity_estimate=parsed.get("complexity", 0.5),
        confidence=0.8,
        decomposed_at=datetime.utcnow(),
    )


def _extract_json(response: str) -> Dict[str, Any]:
    """Extract JSON from LLM response."""
    # Try to find JSON block
    json_match = re.search(r"\{[\s\S]*\}", response)
    if json_match:
        return json.loads(json_match.group())
    raise ValueError("No JSON found in response")


def _simple_extraction(user_input: str) -> Dict[str, Any]:
    """
    Simple rule-based extraction when LLM parsing fails.

    Provides reasonable defaults based on input patterns.
    """
    user_lower = user_input.lower()

    # Detect purpose type
    if any(q in user_lower for q in ["what", "who", "where", "when", "why", "how", "?"]):
        purpose_type = "informational"
        agency_level = "INFORM"
    elif any(w in user_lower for w in ["create", "write", "generate", "make", "build"]):
        purpose_type = "creative"
        agency_level = "CONFIRM"
    elif any(w in user_lower for w in ["analyze", "evaluate", "compare", "assess"]):
        purpose_type = "analysis"
        agency_level = "CONFIRM"
    else:
        purpose_type = "task"
        agency_level = "CONFIRM"

    # Estimate complexity
    word_count = len(user_input.split())
    complexity = min(1.0, word_count / 50)

    return {
        "purpose": user_input,
        "purpose_type": purpose_type,
        "reasoning_strategy": "Analyze request and respond appropriately",
        "reasoning_steps": ["Understand request", "Process information", "Generate response"],
        "agency_level": agency_level,
        "actions": [
            {
                "description": "Generate appropriate response",
                "type": "generate",
                "parameters": {},
            }
        ],
        "dependencies": {},
        "complexity": complexity,
    }


def decompose_goal_simple(user_input: str) -> GoalState:
    """
    Decompose goal without LLM (rule-based only).

    Use when LLM is not available or for simple inputs.
    """
    parsed = _simple_extraction(user_input)

    actions = [
        ActionItem(
            action_id="action_0",
            description=parsed["actions"][0]["description"],
            action_type=parsed["actions"][0]["type"],
            parameters={},
        )
    ]

    return GoalState(
        purpose=parsed["purpose"],
        purpose_type=parsed["purpose_type"],
        reasoning_strategy=parsed["reasoning_strategy"],
        reasoning_steps=parsed["reasoning_steps"],
        agency_level=parsed["agency_level"],
        requires_confirmation=parsed["agency_level"] != "FULL",
        actions=actions,
        dependencies={},
        complexity_estimate=parsed["complexity"],
        confidence=0.6,  # Lower confidence for rule-based
        decomposed_at=datetime.utcnow(),
    )
