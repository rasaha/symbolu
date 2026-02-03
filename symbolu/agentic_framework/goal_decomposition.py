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


# =============================================================================
# Action Type Definitions
# =============================================================================

# Core action types (original)
CORE_ACTION_TYPES = {
    "search": "Search for information",
    "compute": "Perform computation",
    "generate": "Generate content",
    "validate": "Validate data or results",
    "execute": "Execute a general action",
}

# Code-specific action types (extension for coding capabilities)
CODE_ACTION_TYPES = {
    # File Operations
    "code_read": "Read source file contents with line numbers",
    "code_write": "Create or overwrite a source file",
    "code_edit": "Modify existing source file with precise edits",

    # Code Analysis
    "code_search": "Search for code patterns (glob/grep)",
    "code_lint": "Run static analysis on code",
    "code_analyze": "Analyze code structure and dependencies",

    # Code Execution
    "code_execute": "Run code in sandboxed environment",
    "test_run": "Run test suite",
    "build": "Build/compile the project",

    # Version Control
    "git_read": "Git read operations (status, diff, log)",
    "git_write": "Git write operations (add, commit)",
    "git_network": "Git network operations (push, pull, fetch)",
}

# All valid action types
ALL_ACTION_TYPES = {**CORE_ACTION_TYPES, **CODE_ACTION_TYPES}


@dataclass
class ActionItem:
    """
    Single executable action.

    Represents an atomic, verifiable step in goal execution.

    Supported action_types:
    - Core: search, compute, generate, validate, execute
    - Code: code_read, code_write, code_edit, code_search, code_lint,
            code_analyze, code_execute, test_run, build,
            git_read, git_write, git_network
    """

    action_id: str
    description: str
    action_type: str  # See ALL_ACTION_TYPES for valid types
    status: str = "pending"  # "pending", "in_progress", "completed", "failed", "blocked"
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None

    def is_code_action(self) -> bool:
        """Check if this is a code-related action."""
        return self.action_type in CODE_ACTION_TYPES

    def is_destructive(self) -> bool:
        """Check if this action could be destructive."""
        return self.action_type in ["code_write", "code_edit", "git_write", "git_network"]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "action_id": self.action_id,
            "description": self.description,
            "action_type": self.action_type,
            "status": self.status,
            "parameters": self.parameters,
            "result": self.result,
            "error": self.error,
        }


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
           "creative" (generate content), "analysis" (analyze/evaluate),
           "coding" (write/modify code)

2. REASONING: What approach should be used?
   - Strategy: Brief description of approach
   - Steps: List of logical steps to achieve the goal

3. AGENCY: What level of autonomy is appropriate?
   - "FULL": Act without confirmation (simple, low-risk, clear intent)
   - "CONFIRM": Propose actions, wait for approval (moderate risk, needs verification)
   - "INFORM": Just provide information, no actions (high risk, unclear, or just informational)

4. ACTIONS: List concrete steps to execute (if applicable)
   - Each action should be atomic and verifiable
   - Core types: "search", "compute", "generate", "validate", "execute"
   - Code types: "code_read", "code_write", "code_edit", "code_search",
                 "code_lint", "code_analyze", "code_execute", "test_run", "build",
                 "git_read", "git_write", "git_network"

5. COMPLEXITY: Estimate complexity from 0.0 (trivial) to 1.0 (very complex)

Respond ONLY with valid JSON in this exact format:
{{
    "purpose": "string describing the goal",
    "purpose_type": "informational|task|creative|analysis|coding",
    "reasoning_strategy": "string describing approach",
    "reasoning_steps": ["step 1", "step 2", ...],
    "agency_level": "FULL|CONFIRM|INFORM",
    "actions": [
        {{
            "description": "what to do",
            "type": "search|compute|generate|validate|execute|code_read|code_write|code_edit|...",
            "parameters": {{}}
        }}
    ],
    "dependencies": {{"action_1": ["action_0"]}},
    "complexity": 0.5
}}
"""


def decompose_goal(user_input: str, llm_client: LLMClient) -> GoalState:
    """
    Decompose user input into structured GoalState.

    Uses LLM to extract goal structure from natural language.

    Args:
        user_input: Raw user input string
        llm_client: LLM client implementing call() method

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
        actions.append(
            ActionItem(
                action_id=f"action_{i}",
                description=action_data.get("description", f"Action {i}"),
                action_type=action_data.get("type", "generate"),
                parameters=action_data.get("parameters", {}),
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

    # Code-related keywords
    code_keywords = [
        "code", "function", "class", "method", "variable", "file",
        "implement", "fix", "bug", "error", "refactor", "test",
        "commit", "push", "pull", "git", "branch", "merge",
        "import", "module", "package", "dependency", "lint",
        ".py", ".js", ".ts", ".java", ".go", ".rs", ".cpp",
    ]

    # Detect purpose type
    is_coding = any(kw in user_lower for kw in code_keywords)

    if is_coding:
        purpose_type = "coding"
        agency_level = "CONFIRM"
        actions = _extract_code_actions(user_lower)
    elif any(q in user_lower for q in ["what", "who", "where", "when", "why", "how", "?"]):
        purpose_type = "informational"
        agency_level = "INFORM"
        actions = [{"description": "Generate appropriate response", "type": "generate", "parameters": {}}]
    elif any(w in user_lower for w in ["create", "write", "generate", "make", "build"]):
        purpose_type = "creative"
        agency_level = "CONFIRM"
        actions = [{"description": "Generate creative content", "type": "generate", "parameters": {}}]
    elif any(w in user_lower for w in ["analyze", "evaluate", "compare", "assess"]):
        purpose_type = "analysis"
        agency_level = "CONFIRM"
        actions = [{"description": "Analyze and provide assessment", "type": "compute", "parameters": {}}]
    else:
        purpose_type = "task"
        agency_level = "CONFIRM"
        actions = [{"description": "Generate appropriate response", "type": "generate", "parameters": {}}]

    # Estimate complexity
    word_count = len(user_input.split())
    complexity = min(1.0, word_count / 50)
    if is_coding:
        complexity = min(1.0, complexity + 0.2)  # Coding tasks tend to be more complex

    return {
        "purpose": user_input,
        "purpose_type": purpose_type,
        "reasoning_strategy": "Analyze request and respond appropriately",
        "reasoning_steps": ["Understand request", "Process information", "Generate response"],
        "agency_level": agency_level,
        "actions": actions,
        "dependencies": {},
        "complexity": complexity,
    }


def _extract_code_actions(user_lower: str) -> List[Dict[str, Any]]:
    """Extract code-specific actions from user input."""
    actions = []

    # File reading
    if any(kw in user_lower for kw in ["read", "show", "view", "look at", "open"]):
        actions.append({
            "description": "Read source file",
            "type": "code_read",
            "parameters": {},
        })

    # File editing
    if any(kw in user_lower for kw in ["edit", "change", "modify", "update", "fix"]):
        actions.append({
            "description": "Edit source file",
            "type": "code_edit",
            "parameters": {},
        })

    # File creation
    if any(kw in user_lower for kw in ["create", "new", "add file", "write file"]):
        actions.append({
            "description": "Create source file",
            "type": "code_write",
            "parameters": {},
        })

    # Searching
    if any(kw in user_lower for kw in ["find", "search", "grep", "where is", "locate"]):
        actions.append({
            "description": "Search codebase",
            "type": "code_search",
            "parameters": {},
        })

    # Testing
    if any(kw in user_lower for kw in ["test", "pytest", "jest", "unittest", "run test"]):
        actions.append({
            "description": "Run tests",
            "type": "test_run",
            "parameters": {},
        })

    # Building
    if any(kw in user_lower for kw in ["build", "compile", "make"]):
        actions.append({
            "description": "Build project",
            "type": "build",
            "parameters": {},
        })

    # Git operations
    if any(kw in user_lower for kw in ["commit", "add", "stage"]):
        actions.append({
            "description": "Git commit changes",
            "type": "git_write",
            "parameters": {},
        })

    if any(kw in user_lower for kw in ["push", "pull", "fetch"]):
        actions.append({
            "description": "Git network operation",
            "type": "git_network",
            "parameters": {},
        })

    if any(kw in user_lower for kw in ["status", "diff", "log", "git show"]):
        actions.append({
            "description": "Git status check",
            "type": "git_read",
            "parameters": {},
        })

    # Linting
    if any(kw in user_lower for kw in ["lint", "format", "check style", "flake", "eslint"]):
        actions.append({
            "description": "Run linter",
            "type": "code_lint",
            "parameters": {},
        })

    # Default if no specific action detected
    if not actions:
        actions.append({
            "description": "Analyze and implement code changes",
            "type": "code_edit",
            "parameters": {},
        })

    return actions


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
