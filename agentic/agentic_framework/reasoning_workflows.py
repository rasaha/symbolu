"""
Reasoning Workflows for Adaptive AI Prompts
=============================================

Seven distinct reasoning workflow patterns, each suited to different
problem types. The WorkflowSelector maps ComplexitySignals from the
ComplexityDetector to the optimal workflow automatically.

WORKFLOW CATALOG:
    1. LinearChain       - Sequential: DECOMPOSE → ANALYZE → CRITIQUE → SYNTHESIZE
    2. TreeOfThought     - Branching: explore N decompositions, score, pursue best
    3. IterativeRefinement - Looping: GENERATE → CRITIC → REVISE until quality met
    4. Debate            - Adversarial: ADVOCATE_A ↔ ADVOCATE_B → JUDGE
    5. MapReduce         - Parallel: DECOMPOSE → solve each part → REDUCE
    6. SocraticProgressive - Dialogic: answer → clarify → focused deep dive
    7. Metacognitive     - Meta: detect problem type → select workflow → execute

SIGNAL → WORKFLOW MAPPING:
    COMPARISON_REQUEST  → MapReduce (evaluate options independently)
    CAUSAL_REASONING    → LinearChain (cause → effect → implication)
    AMBIGUITY_DETECTED  → TreeOfThought (explore multiple framings)
    CREATIVE_SYNTHESIS  → IterativeRefinement (draft → revise → refine)
    CONDITIONAL_LOGIC   → Debate (argue for/against each branch)
    TEMPORAL_REASONING  → LinearChain (sequence → analyze → synthesize)
    ABSTRACT_CONCEPT    → TreeOfThought (multiple conceptual lenses)
    META_REASONING      → Metacognitive (reason about which workflow)
    MULTI_PART_QUESTION → MapReduce (solve parts independently)
    DOMAIN_EXPERTISE    → LinearChain (structured expert analysis)

PROGRESSIVE DISCLOSURE:
    All workflows respect the progressive disclosure model.
    Each returns a WorkflowResult with can_deepen / depth_hint.

INVARIANTS:
    - INV-WF-1: Every workflow produces a WorkflowResult with full trace
    - INV-WF-2: No workflow exceeds max_llm_calls budget
    - INV-WF-3: WorkflowSelector mapping is deterministic
    - INV-WF-4: All workflows start at SHALLOW in progressive mode

Author: Symbol-U Reasoning Workflows
Version: 1.0
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from agentic.agentic_framework.adaptive_prompts import (
    ComplexityAnalysis,
    ComplexityDetector,
    ComplexitySignal,
    ReasoningDepth,
    ReasoningStage,
    ReasoningStep,
)


# =============================================================================
# PROTOCOLS
# =============================================================================


class LLMClient(Protocol):
    """Protocol for LLM client interface."""

    def call(self, prompt: str) -> str: ...


# =============================================================================
# ENUMS
# =============================================================================


class WorkflowType(Enum):
    """Available reasoning workflow types."""
    LINEAR_CHAIN = "linear_chain"
    TREE_OF_THOUGHT = "tree_of_thought"
    ITERATIVE_REFINEMENT = "iterative_refinement"
    DEBATE = "debate"
    MAP_REDUCE = "map_reduce"
    SOCRATIC_PROGRESSIVE = "socratic_progressive"
    METACOGNITIVE = "metacognitive"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class WorkflowStep:
    """A single step in any workflow's execution trace."""
    stage_name: str
    prompt: str
    response: str = ""
    quality_score: float = 0.0
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "prompt_preview": self.prompt[:200] + "..." if len(self.prompt) > 200 else self.prompt,
            "response_preview": self.response[:200] + "..." if len(self.response) > 200 else self.response,
            "quality_score": self.quality_score,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


@dataclass
class WorkflowResult:
    """
    Unified result from any reasoning workflow.

    All 7 workflows return this same structure so downstream code
    doesn't need to know which workflow was used.
    """
    # Core output
    final_response: str
    quality_score: float

    # Which workflow was used
    workflow_type: WorkflowType
    workflow_description: str = ""

    # Full execution trace
    steps: List[WorkflowStep] = field(default_factory=list)

    # Progressive disclosure
    depth_used: ReasoningDepth = ReasoningDepth.SHALLOW
    depth_available: ReasoningDepth = ReasoningDepth.SHALLOW
    can_deepen: bool = False
    depth_hint: str = ""

    # Complexity analysis
    complexity_analysis: Optional[ComplexityAnalysis] = None

    # Performance
    total_duration_ms: float = 0.0
    total_llm_calls: int = 0

    # Internal for deepen
    _query: str = field(default="", repr=False)
    _context: str = field(default="", repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_response": self.final_response,
            "quality_score": self.quality_score,
            "workflow_type": self.workflow_type.value,
            "workflow_description": self.workflow_description,
            "steps": [s.to_dict() for s in self.steps],
            "depth_used": self.depth_used.name,
            "depth_available": self.depth_available.name,
            "can_deepen": self.can_deepen,
            "depth_hint": self.depth_hint,
            "total_duration_ms": self.total_duration_ms,
            "total_llm_calls": self.total_llm_calls,
        }

    def get_reasoning_trace(self) -> str:
        """Human-readable trace of the workflow execution."""
        parts = [
            f"[Workflow: {self.workflow_type.value}]",
            f"[Depth: {self.depth_used.name}]",
        ]
        if self.can_deepen:
            parts.append(f"[{self.depth_hint}]")
        parts.append("")

        for i, step in enumerate(self.steps, 1):
            parts.append(f"--- Step {i}: {step.stage_name} ---")
            parts.append(step.response[:500] if step.response else "(no output)")
            if step.metadata:
                for k, v in step.metadata.items():
                    parts.append(f"  [{k}: {v}]")
            parts.append("")

        return "\n".join(parts)


# =============================================================================
# BASE WORKFLOW
# =============================================================================


class ReasoningWorkflow(ABC):
    """
    Abstract base for all reasoning workflows.

    Every workflow must implement execute() and return a WorkflowResult.
    """

    @property
    @abstractmethod
    def workflow_type(self) -> WorkflowType:
        """Return the type of this workflow."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of this workflow."""
        ...

    @property
    @abstractmethod
    def best_for(self) -> List[ComplexitySignal]:
        """Which complexity signals this workflow handles best."""
        ...

    @abstractmethod
    def execute(
        self,
        query: str,
        llm: LLMClient,
        context: str = "",
        max_llm_calls: int = 10,
    ) -> WorkflowResult:
        """Execute this workflow and return result."""
        ...

    def _call_llm(
        self,
        llm: LLMClient,
        prompt: str,
        stage_name: str,
        steps: List[WorkflowStep],
        call_counter: List[int],
        max_calls: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowStep:
        """Helper: call LLM, track timing, append to steps."""
        if call_counter[0] >= max_calls:
            step = WorkflowStep(
                stage_name=stage_name,
                prompt=prompt,
                response="(budget exhausted)",
                metadata=metadata or {},
            )
            steps.append(step)
            return step

        start = time.time()
        response = llm.call(prompt)
        duration = (time.time() - start) * 1000
        call_counter[0] += 1

        step = WorkflowStep(
            stage_name=stage_name,
            prompt=prompt,
            response=response,
            duration_ms=duration,
            quality_score=self._basic_quality(response),
            metadata=metadata or {},
        )
        steps.append(step)
        return step

    def _basic_quality(self, response: str) -> float:
        """Basic quality heuristic."""
        if not response or response == "(budget exhausted)":
            return 0.0
        score = 0.3
        words = len(response.split())
        if words > 20:
            score += 0.2
        if words > 50:
            score += 0.15
        if words > 100:
            score += 0.1
        if "\n" in response:
            score += 0.1
        sentences = [s.strip() for s in response.split(".") if s.strip()]
        if sentences:
            unique = len(set(s.lower() for s in sentences)) / len(sentences)
            score += unique * 0.15
        return min(1.0, score)


# =============================================================================
# WORKFLOW 1: LINEAR CHAIN
# =============================================================================


class LinearChainWorkflow(ReasoningWorkflow):
    """
    Sequential reasoning: DECOMPOSE → ANALYZE → CRITIQUE → SYNTHESIZE

    Each step feeds into the next. The most straightforward multi-step
    pattern. Works well for problems with clear causal or logical structure.

    Flow:
        QUERY
          ↓
        DECOMPOSE (break into sub-problems)
          ↓
        ANALYZE (deep analysis of each part)
          ↓
        CRITIQUE (find gaps and weaknesses)
          ↓
        SYNTHESIZE (fuse into coherent answer)

    Strengths:
        - Deterministic and easy to trace
        - Each step has clear purpose
        - Works well for structured problems

    Weaknesses:
        - One bad step poisons downstream
        - Linear cost (N calls for N steps)
        - Doesn't explore alternative framings

    Best for: CAUSAL_REASONING, TEMPORAL_REASONING, DOMAIN_EXPERTISE
    """

    @property
    def workflow_type(self) -> WorkflowType:
        return WorkflowType.LINEAR_CHAIN

    @property
    def description(self) -> str:
        return "Sequential: DECOMPOSE → ANALYZE → CRITIQUE → SYNTHESIZE"

    @property
    def best_for(self) -> List[ComplexitySignal]:
        return [
            ComplexitySignal.CAUSAL_REASONING,
            ComplexitySignal.TEMPORAL_REASONING,
            ComplexitySignal.DOMAIN_EXPERTISE,
        ]

    def execute(
        self,
        query: str,
        llm: LLMClient,
        context: str = "",
        max_llm_calls: int = 4,
    ) -> WorkflowResult:
        start_time = time.time()
        steps: List[WorkflowStep] = []
        calls = [0]
        ctx = f"\nCONTEXT:\n{context}" if context else ""

        # Step 1: DECOMPOSE
        decompose = self._call_llm(llm, (
            f"Break this query into ordered sub-problems. "
            f"For each, state what it asks and what reasoning is needed.\n\n"
            f"QUERY: {query}{ctx}\n\nDECOMPOSITION:"
        ), "DECOMPOSE", steps, calls, max_llm_calls)

        # Step 2: ANALYZE
        analyze = self._call_llm(llm, (
            f"Provide thorough analysis of each sub-problem. "
            f"Use precise reasoning.\n\n"
            f"QUERY: {query}\nDECOMPOSITION:\n{decompose.response}{ctx}\n\nANALYSIS:"
        ), "ANALYZE", steps, calls, max_llm_calls)

        # Step 3: CRITIQUE
        critique = self._call_llm(llm, (
            f"Review this analysis for gaps, errors, and missed perspectives.\n\n"
            f"QUERY: {query}\nANALYSIS:\n{analyze.response}\n\nCRITIQUE:"
        ), "CRITIQUE", steps, calls, max_llm_calls)

        # Step 4: SYNTHESIZE
        synthesize = self._call_llm(llm, (
            f"Synthesize a clear, coherent response integrating all reasoning.\n\n"
            f"QUERY: {query}\n"
            f"ANALYSIS:\n{analyze.response}\n"
            f"CRITIQUE:\n{critique.response}{ctx}\n\nSYNTHESIS:"
        ), "SYNTHESIZE", steps, calls, max_llm_calls)

        return WorkflowResult(
            final_response=synthesize.response,
            quality_score=synthesize.quality_score,
            workflow_type=self.workflow_type,
            workflow_description=self.description,
            steps=steps,
            total_duration_ms=(time.time() - start_time) * 1000,
            total_llm_calls=calls[0],
            _query=query,
            _context=context,
        )


# =============================================================================
# WORKFLOW 2: TREE OF THOUGHT
# =============================================================================


class TreeOfThoughtWorkflow(ReasoningWorkflow):
    """
    Branching exploration: generate N decompositions, score, pursue best.

    Instead of committing to one framing, explores multiple angles
    and selects the most promising one for deep analysis.

    Flow:
              QUERY
           /    |    \\
        Path1 Path2 Path3   ← 3 different decompositions
          |     |     |
        Score Score Score   ← LLM scores each path
           \\    |
           Best path
              |
           SYNTHESIZE

    Strengths:
        - Explores alternative framings
        - Catches the right angle for ambiguous problems
        - Self-selects the most promising approach

    Weaknesses:
        - More LLM calls (N branches + scoring + synthesis)
        - Scoring step may not pick the truly best path
        - Wasted computation on discarded branches

    Best for: AMBIGUITY_DETECTED, ABSTRACT_CONCEPT
    """

    def __init__(self, num_branches: int = 3):
        self.num_branches = num_branches

    @property
    def workflow_type(self) -> WorkflowType:
        return WorkflowType.TREE_OF_THOUGHT

    @property
    def description(self) -> str:
        return f"Branching: explore {self.num_branches} decompositions, score, pursue best"

    @property
    def best_for(self) -> List[ComplexitySignal]:
        return [
            ComplexitySignal.AMBIGUITY_DETECTED,
            ComplexitySignal.ABSTRACT_CONCEPT,
        ]

    def execute(
        self,
        query: str,
        llm: LLMClient,
        context: str = "",
        max_llm_calls: int = 8,
    ) -> WorkflowResult:
        start_time = time.time()
        steps: List[WorkflowStep] = []
        calls = [0]
        ctx = f"\nCONTEXT:\n{context}" if context else ""

        # Generate N different decompositions
        branches: List[WorkflowStep] = []
        for i in range(self.num_branches):
            branch = self._call_llm(llm, (
                f"Provide decomposition #{i+1} of {self.num_branches} for this query. "
                f"Each decomposition should take a DIFFERENT angle or framing. "
                f"Be creative and distinct from other approaches.\n\n"
                f"QUERY: {query}{ctx}\n\n"
                f"APPROACH #{i+1}:"
            ), f"BRANCH_{i+1}", steps, calls, max_llm_calls,
                metadata={"branch_index": i + 1})
            branches.append(branch)

        # Score all branches
        branch_summaries = "\n\n".join(
            f"APPROACH {i+1}:\n{b.response[:300]}"
            for i, b in enumerate(branches)
        )
        scoring = self._call_llm(llm, (
            f"Evaluate these {self.num_branches} approaches to the query. "
            f"Score each 1-10 for: relevance, completeness, insight quality. "
            f"State which is BEST and why.\n\n"
            f"QUERY: {query}\n\n{branch_summaries}\n\n"
            f"EVALUATION (include 'BEST: #N'):"
        ), "SCORE_BRANCHES", steps, calls, max_llm_calls)

        # Parse best branch (default to first if parsing fails)
        best_idx = 0
        for i in range(self.num_branches):
            if f"BEST: #{i+1}" in scoring.response or \
               f"best: #{i+1}" in scoring.response.lower() or \
               f"approach {i+1}" in scoring.response.lower() and "best" in scoring.response.lower():
                best_idx = i
                break

        best_branch = branches[best_idx] if branches else branches[0] if branches else None

        # Deep synthesis of best path
        best_response = best_branch.response if best_branch else ""
        synthesize = self._call_llm(llm, (
            f"Using the best approach identified, provide a thorough response.\n\n"
            f"QUERY: {query}\n"
            f"BEST APPROACH:\n{best_response}\n"
            f"SCORING NOTES:\n{scoring.response}{ctx}\n\n"
            f"FINAL RESPONSE:"
        ), "SYNTHESIZE_BEST", steps, calls, max_llm_calls,
            metadata={"best_branch": best_idx + 1})

        return WorkflowResult(
            final_response=synthesize.response,
            quality_score=synthesize.quality_score,
            workflow_type=self.workflow_type,
            workflow_description=self.description,
            steps=steps,
            total_duration_ms=(time.time() - start_time) * 1000,
            total_llm_calls=calls[0],
            _query=query,
            _context=context,
        )


# =============================================================================
# WORKFLOW 3: ITERATIVE REFINEMENT
# =============================================================================


class IterativeRefinementWorkflow(ReasoningWorkflow):
    """
    Loop-based: GENERATE → CRITIC → REVISE until quality threshold met.

    Closest to how humans actually think. Draft, evaluate, improve, repeat.
    Uses the existing Reflective Phase-Quad pattern.

    Flow:
        GENERATE initial draft
            ↓
        CRITIC evaluates (score + feedback)
            ↓ score < threshold?
        REVISE incorporating feedback
            ↓
        CRITIC evaluates again
            ↓ score >= threshold? → OUTPUT
            ↓ score < threshold?  → REVISE again
            ↓ max_revisions hit?  → OUTPUT best so far

    Strengths:
        - Converges toward quality through iteration
        - Each revision is targeted (guided by critic feedback)
        - Natural stopping condition (quality threshold)

    Weaknesses:
        - Variable cost (1-N iterations)
        - May loop without meaningful improvement
        - Critic quality bounds overall quality

    Best for: CREATIVE_SYNTHESIS
    """

    def __init__(
        self,
        max_revisions: int = 3,
        quality_threshold: float = 0.8,
    ):
        self.max_revisions = max_revisions
        self.quality_threshold = quality_threshold

    @property
    def workflow_type(self) -> WorkflowType:
        return WorkflowType.ITERATIVE_REFINEMENT

    @property
    def description(self) -> str:
        return f"Loop: GENERATE → CRITIC → REVISE (max {self.max_revisions} rounds, threshold {self.quality_threshold})"

    @property
    def best_for(self) -> List[ComplexitySignal]:
        return [ComplexitySignal.CREATIVE_SYNTHESIS]

    def execute(
        self,
        query: str,
        llm: LLMClient,
        context: str = "",
        max_llm_calls: int = 8,
    ) -> WorkflowResult:
        start_time = time.time()
        steps: List[WorkflowStep] = []
        calls = [0]
        ctx = f"\nCONTEXT:\n{context}" if context else ""

        # Initial generation
        draft = self._call_llm(llm, (
            f"Provide a thorough response to this query.\n\n"
            f"QUERY: {query}{ctx}\n\nRESPONSE:"
        ), "GENERATE_v1", steps, calls, max_llm_calls)

        best_draft = draft
        best_score = draft.quality_score

        for revision in range(self.max_revisions):
            # Critic evaluates
            critique = self._call_llm(llm, (
                f"Evaluate this response critically. Score it 1-10. "
                f"List specific improvements needed.\n\n"
                f"QUERY: {query}\n"
                f"RESPONSE:\n{best_draft.response}\n\n"
                f"CRITIQUE (format: SCORE: N/10 then IMPROVEMENTS:):"
            ), f"CRITIC_v{revision+1}", steps, calls, max_llm_calls,
                metadata={"revision": revision + 1})

            # Parse score from critique (basic extraction)
            critic_score = self._extract_score(critique.response)
            critique.metadata["parsed_score"] = critic_score

            if critic_score >= self.quality_threshold:
                break

            # Revise incorporating feedback
            revised = self._call_llm(llm, (
                f"Revise this response based on the critique feedback.\n\n"
                f"QUERY: {query}\n"
                f"CURRENT RESPONSE:\n{best_draft.response}\n"
                f"CRITIQUE:\n{critique.response}{ctx}\n\n"
                f"REVISED RESPONSE:"
            ), f"REVISE_v{revision+2}", steps, calls, max_llm_calls,
                metadata={"revision": revision + 2})

            if revised.quality_score >= best_score:
                best_draft = revised
                best_score = revised.quality_score

        return WorkflowResult(
            final_response=best_draft.response,
            quality_score=best_score,
            workflow_type=self.workflow_type,
            workflow_description=self.description,
            steps=steps,
            total_duration_ms=(time.time() - start_time) * 1000,
            total_llm_calls=calls[0],
            _query=query,
            _context=context,
        )

    def _extract_score(self, critique: str) -> float:
        """Extract numeric score from critic response."""
        import re
        match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)\s*/\s*10', critique, re.IGNORECASE)
        if match:
            return float(match.group(1)) / 10.0
        match = re.search(r'(\d+(?:\.\d+)?)\s*/\s*10', critique)
        if match:
            return float(match.group(1)) / 10.0
        return 0.5  # Default if can't parse


# =============================================================================
# WORKFLOW 4: DEBATE (ADVERSARIAL)
# =============================================================================


class DebateWorkflow(ReasoningWorkflow):
    """
    Adversarial: two advocates argue opposing positions, a judge synthesizes.

    Catches blind spots better than self-critique because opposing
    positions force examination of assumptions.

    Flow:
        QUERY
          ↓
        ADVOCATE_A (argues FOR / one position)
        ADVOCATE_B (argues AGAINST / opposing position)
          ↓
        REBUTTAL_A (responds to B's arguments)
        REBUTTAL_B (responds to A's arguments)
          ↓
        JUDGE (synthesizes, weighs evidence, decides)

    Strengths:
        - Surfaces hidden assumptions
        - Explores genuine tradeoffs
        - Correlated blind spots broken by opposing positions

    Weaknesses:
        - More LLM calls (5: 2 advocates + 2 rebuttals + 1 judge)
        - Debate framing doesn't fit all question types
        - Judge may be biased toward more eloquent advocate

    Best for: CONDITIONAL_LOGIC (if/then tradeoffs)
    """

    @property
    def workflow_type(self) -> WorkflowType:
        return WorkflowType.DEBATE

    @property
    def description(self) -> str:
        return "Adversarial: ADVOCATE_A ↔ ADVOCATE_B → REBUTTALS → JUDGE"

    @property
    def best_for(self) -> List[ComplexitySignal]:
        return [ComplexitySignal.CONDITIONAL_LOGIC]

    def execute(
        self,
        query: str,
        llm: LLMClient,
        context: str = "",
        max_llm_calls: int = 5,
    ) -> WorkflowResult:
        start_time = time.time()
        steps: List[WorkflowStep] = []
        calls = [0]
        ctx = f"\nCONTEXT:\n{context}" if context else ""

        # Advocate A: argue FOR / first position
        advocate_a = self._call_llm(llm, (
            f"You are ADVOCATE A. Argue strongly FOR one position on this query. "
            f"Present your strongest evidence and reasoning. "
            f"Be thorough and persuasive.\n\n"
            f"QUERY: {query}{ctx}\n\nADVOCATE A POSITION:"
        ), "ADVOCATE_A", steps, calls, max_llm_calls,
            metadata={"role": "advocate_for"})

        # Advocate B: argue AGAINST / opposing position
        advocate_b = self._call_llm(llm, (
            f"You are ADVOCATE B. Argue strongly for the OPPOSING position. "
            f"Challenge every assumption made by Advocate A. "
            f"Present your strongest counter-evidence.\n\n"
            f"QUERY: {query}\n"
            f"ADVOCATE A ARGUED:\n{advocate_a.response}\n\n"
            f"ADVOCATE B POSITION:"
        ), "ADVOCATE_B", steps, calls, max_llm_calls,
            metadata={"role": "advocate_against"})

        # Rebuttal from A
        rebuttal_a = self._call_llm(llm, (
            f"You are ADVOCATE A. Respond to Advocate B's arguments. "
            f"Address their strongest points and defend your position.\n\n"
            f"QUERY: {query}\n"
            f"YOUR POSITION:\n{advocate_a.response}\n"
            f"B's CHALLENGE:\n{advocate_b.response}\n\n"
            f"REBUTTAL:"
        ), "REBUTTAL_A", steps, calls, max_llm_calls,
            metadata={"role": "rebuttal_for"})

        # Judge synthesizes
        judge = self._call_llm(llm, (
            f"You are an impartial JUDGE. You've heard both sides debate. "
            f"Weigh the evidence, identify the strongest arguments from each side, "
            f"and provide a balanced, well-reasoned conclusion.\n\n"
            f"QUERY: {query}\n"
            f"ADVOCATE A:\n{advocate_a.response}\n"
            f"ADVOCATE B:\n{advocate_b.response}\n"
            f"A's REBUTTAL:\n{rebuttal_a.response}{ctx}\n\n"
            f"JUDGMENT:"
        ), "JUDGE", steps, calls, max_llm_calls,
            metadata={"role": "judge"})

        return WorkflowResult(
            final_response=judge.response,
            quality_score=judge.quality_score,
            workflow_type=self.workflow_type,
            workflow_description=self.description,
            steps=steps,
            total_duration_ms=(time.time() - start_time) * 1000,
            total_llm_calls=calls[0],
            _query=query,
            _context=context,
        )


# =============================================================================
# WORKFLOW 5: MAP-REDUCE
# =============================================================================


class MapReduceWorkflow(ReasoningWorkflow):
    """
    Parallel decomposition: break into parts, solve each independently, reduce.

    Each sub-problem gets its own focused LLM call. Sub-problems are
    independent -- solving one doesn't inform another.

    Flow:
        DECOMPOSE into N sub-problems
            ↓
        SOLVE Sub1  SOLVE Sub2  SOLVE Sub3  (independent)
            \\          |          /
              REDUCE (merge all solutions)

    Strengths:
        - Each sub-problem gets focused attention
        - No cross-contamination between sub-problems
        - Naturally handles comparison queries

    Weaknesses:
        - Assumes sub-problems are independent (may not be true)
        - Decomposition quality is critical
        - More LLM calls (1 + N + 1)

    Best for: COMPARISON_REQUEST, MULTI_PART_QUESTION
    """

    def __init__(self, max_sub_problems: int = 4):
        self.max_sub_problems = max_sub_problems

    @property
    def workflow_type(self) -> WorkflowType:
        return WorkflowType.MAP_REDUCE

    @property
    def description(self) -> str:
        return f"Parallel: DECOMPOSE → SOLVE each (max {self.max_sub_problems}) → REDUCE"

    @property
    def best_for(self) -> List[ComplexitySignal]:
        return [
            ComplexitySignal.COMPARISON_REQUEST,
            ComplexitySignal.MULTI_PART_QUESTION,
        ]

    def execute(
        self,
        query: str,
        llm: LLMClient,
        context: str = "",
        max_llm_calls: int = 8,
    ) -> WorkflowResult:
        start_time = time.time()
        steps: List[WorkflowStep] = []
        calls = [0]
        ctx = f"\nCONTEXT:\n{context}" if context else ""

        # DECOMPOSE: identify sub-problems
        decompose = self._call_llm(llm, (
            f"Break this query into {self.max_sub_problems} or fewer INDEPENDENT "
            f"sub-problems that can each be answered separately. "
            f"Number them clearly.\n\n"
            f"QUERY: {query}{ctx}\n\n"
            f"SUB-PROBLEMS (numbered list):"
        ), "DECOMPOSE", steps, calls, max_llm_calls)

        # Parse sub-problems (extract numbered items)
        sub_problems = self._parse_sub_problems(decompose.response)

        # MAP: solve each sub-problem independently
        solutions: List[WorkflowStep] = []
        for i, sub in enumerate(sub_problems[:self.max_sub_problems]):
            solution = self._call_llm(llm, (
                f"Answer this specific sub-problem thoroughly and independently. "
                f"Focus ONLY on this sub-problem.\n\n"
                f"ORIGINAL QUERY: {query}\n"
                f"SUB-PROBLEM {i+1}: {sub}{ctx}\n\n"
                f"ANSWER:"
            ), f"SOLVE_{i+1}", steps, calls, max_llm_calls,
                metadata={"sub_problem": sub[:100], "index": i + 1})
            solutions.append(solution)

        # REDUCE: merge all solutions
        solution_text = "\n\n".join(
            f"Sub-problem {i+1}: {s.metadata.get('sub_problem', '?')}\n"
            f"Solution: {s.response}"
            for i, s in enumerate(solutions)
        )

        reduce_step = self._call_llm(llm, (
            f"Merge these independent solutions into a single coherent response "
            f"that addresses the original query completely.\n\n"
            f"QUERY: {query}\n\n{solution_text}{ctx}\n\n"
            f"MERGED RESPONSE:"
        ), "REDUCE", steps, calls, max_llm_calls)

        return WorkflowResult(
            final_response=reduce_step.response,
            quality_score=reduce_step.quality_score,
            workflow_type=self.workflow_type,
            workflow_description=self.description,
            steps=steps,
            total_duration_ms=(time.time() - start_time) * 1000,
            total_llm_calls=calls[0],
            _query=query,
            _context=context,
        )

    def _parse_sub_problems(self, text: str) -> List[str]:
        """Extract numbered sub-problems from decomposition."""
        import re
        items = re.findall(r'\d+[.)]\s*(.+?)(?=\n\d+[.)]|\Z)', text, re.DOTALL)
        if items:
            return [item.strip() for item in items if item.strip()]
        # Fallback: split by newlines
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return lines[:self.max_sub_problems] if lines else [text]


# =============================================================================
# WORKFLOW 6: SOCRATIC PROGRESSIVE
# =============================================================================


class SocraticProgressiveWorkflow(ReasoningWorkflow):
    """
    Dialogic: answer → ask clarifying question → focused deep dive.

    Instead of deepening everything, asks WHICH PART the user wants
    deeper. Then goes deep on only that aspect. Most aligned with
    the progressive disclosure philosophy.

    Flow:
        SHALLOW answer to full query
            ↓
        IDENTIFY which aspect has most depth potential
            ↓
        Generate CLARIFYING QUESTION for the user
            ↓
        (In auto mode: self-answers the clarifying question)
            ↓
        FOCUSED DEEP DIVE on the identified aspect

    Strengths:
        - Maximum relevance (deep on what matters to user)
        - Avoids information overload (selective depth)
        - Surfaces what the user actually needs

    Weaknesses:
        - Requires interaction (or self-answering in auto mode)
        - May miss important aspects user didn't ask about
        - Clarifying question quality varies

    Best for: General use, especially when user intent is unclear
    """

    @property
    def workflow_type(self) -> WorkflowType:
        return WorkflowType.SOCRATIC_PROGRESSIVE

    @property
    def description(self) -> str:
        return "Dialogic: answer → clarify → focused deep dive"

    @property
    def best_for(self) -> List[ComplexitySignal]:
        return [ComplexitySignal.AMBIGUITY_DETECTED]

    def execute(
        self,
        query: str,
        llm: LLMClient,
        context: str = "",
        max_llm_calls: int = 4,
    ) -> WorkflowResult:
        start_time = time.time()
        steps: List[WorkflowStep] = []
        calls = [0]
        ctx = f"\nCONTEXT:\n{context}" if context else ""

        # Step 1: Quick shallow answer
        shallow = self._call_llm(llm, (
            f"Answer this query concisely and directly.\n\n"
            f"QUERY: {query}{ctx}\n\nRESPONSE:"
        ), "SHALLOW_ANSWER", steps, calls, max_llm_calls)

        # Step 2: Identify the aspect with most depth potential
        identify = self._call_llm(llm, (
            f"Given this query and initial answer, identify the single "
            f"aspect that would benefit MOST from deeper analysis. "
            f"Then formulate a specific clarifying question that would "
            f"guide that deeper analysis.\n\n"
            f"QUERY: {query}\n"
            f"INITIAL ANSWER:\n{shallow.response}\n\n"
            f"Format:\n"
            f"DEEPEST ASPECT: <aspect>\n"
            f"CLARIFYING QUESTION: <question>"
        ), "IDENTIFY_DEPTH", steps, calls, max_llm_calls)

        # Step 3: Self-answer the clarifying question (auto mode)
        self_answer = self._call_llm(llm, (
            f"Based on the identified aspect needing depth, provide "
            f"a thorough deep-dive analysis.\n\n"
            f"ORIGINAL QUERY: {query}\n"
            f"INITIAL ANSWER:\n{shallow.response}\n"
            f"DEPTH ANALYSIS:\n{identify.response}{ctx}\n\n"
            f"DEEP DIVE:"
        ), "FOCUSED_DEEP_DIVE", steps, calls, max_llm_calls)

        # Step 4: Synthesize shallow + deep into final
        synthesize = self._call_llm(llm, (
            f"Combine the initial answer with the focused deep dive "
            f"into a single comprehensive response.\n\n"
            f"QUERY: {query}\n"
            f"INITIAL ANSWER:\n{shallow.response}\n"
            f"DEEP DIVE:\n{self_answer.response}\n\n"
            f"COMBINED RESPONSE:"
        ), "SYNTHESIZE", steps, calls, max_llm_calls)

        return WorkflowResult(
            final_response=synthesize.response,
            quality_score=synthesize.quality_score,
            workflow_type=self.workflow_type,
            workflow_description=self.description,
            steps=steps,
            total_duration_ms=(time.time() - start_time) * 1000,
            total_llm_calls=calls[0],
            _query=query,
            _context=context,
        )


# =============================================================================
# WORKFLOW 7: METACOGNITIVE
# =============================================================================


class MetacognitiveWorkflow(ReasoningWorkflow):
    """
    Meta-level: analyzes the problem type, selects the best workflow,
    then delegates execution to that workflow.

    This is the "master" workflow that reasons about reasoning.
    It uses the ComplexityDetector to classify the problem, then
    picks from the other 6 workflows.

    Flow:
        QUERY
          ↓
        COMPLEXITY DETECTION (10 signal types)
          ↓
        WORKFLOW SELECTION (signal → workflow mapping)
          ↓
        DELEGATE to selected workflow
          ↓
        RESULT (tagged with which workflow was chosen and why)

    Strengths:
        - Right tool for the right problem
        - Avoids forcing one pattern onto all problems
        - Self-documenting (explains why it chose a workflow)

    Weaknesses:
        - Selection may be wrong (garbage in → wrong workflow)
        - Adds complexity/indirection
        - Overhead of the selection step

    Best for: META_REASONING, or as the default when problem type is unclear
    """

    def __init__(
        self,
        workflows: Optional[Dict[WorkflowType, ReasoningWorkflow]] = None,
        detector: Optional[ComplexityDetector] = None,
    ):
        self._detector = detector or ComplexityDetector()
        self._workflows = workflows or self._default_workflows()

    def _default_workflows(self) -> Dict[WorkflowType, ReasoningWorkflow]:
        return {
            WorkflowType.LINEAR_CHAIN: LinearChainWorkflow(),
            WorkflowType.TREE_OF_THOUGHT: TreeOfThoughtWorkflow(),
            WorkflowType.ITERATIVE_REFINEMENT: IterativeRefinementWorkflow(),
            WorkflowType.DEBATE: DebateWorkflow(),
            WorkflowType.MAP_REDUCE: MapReduceWorkflow(),
            WorkflowType.SOCRATIC_PROGRESSIVE: SocraticProgressiveWorkflow(),
        }

    @property
    def workflow_type(self) -> WorkflowType:
        return WorkflowType.METACOGNITIVE

    @property
    def description(self) -> str:
        return "Meta: detect problem type → select best workflow → delegate"

    @property
    def best_for(self) -> List[ComplexitySignal]:
        return [ComplexitySignal.META_REASONING]

    def execute(
        self,
        query: str,
        llm: LLMClient,
        context: str = "",
        max_llm_calls: int = 10,
    ) -> WorkflowResult:
        start_time = time.time()

        # Step 1: Detect complexity
        analysis = self._detector.analyze(query)

        # Step 2: Select workflow
        selected_type = self.select_workflow(analysis)
        selected_workflow = self._workflows.get(
            selected_type,
            self._workflows[WorkflowType.LINEAR_CHAIN]
        )

        # Step 3: Delegate
        result = selected_workflow.execute(
            query, llm, context, max_llm_calls
        )

        # Tag result with metacognitive info
        result.workflow_description = (
            f"Metacognitive → selected {selected_type.value} "
            f"(signals: {[s.value for s in analysis.signals]})"
        )
        result.complexity_analysis = analysis
        result.total_duration_ms = (time.time() - start_time) * 1000

        return result

    def select_workflow(self, analysis: ComplexityAnalysis) -> WorkflowType:
        """
        Map complexity signals to the optimal workflow.

        Priority-ordered: first matching rule wins.
        """
        signals = set(analysis.signals)

        # Priority 1: Meta-reasoning → Metacognitive delegates to LinearChain
        # (to avoid infinite recursion)
        if ComplexitySignal.META_REASONING in signals:
            return WorkflowType.LINEAR_CHAIN

        # Priority 2: Conditional logic → Debate
        if ComplexitySignal.CONDITIONAL_LOGIC in signals:
            return WorkflowType.DEBATE

        # Priority 3: Comparison or multi-part → MapReduce
        if ComplexitySignal.COMPARISON_REQUEST in signals:
            return WorkflowType.MAP_REDUCE
        if ComplexitySignal.MULTI_PART_QUESTION in signals:
            return WorkflowType.MAP_REDUCE

        # Priority 4: Ambiguity or abstract → TreeOfThought
        if ComplexitySignal.AMBIGUITY_DETECTED in signals:
            return WorkflowType.TREE_OF_THOUGHT
        if ComplexitySignal.ABSTRACT_CONCEPT in signals:
            return WorkflowType.TREE_OF_THOUGHT

        # Priority 5: Creative → IterativeRefinement
        if ComplexitySignal.CREATIVE_SYNTHESIS in signals:
            return WorkflowType.ITERATIVE_REFINEMENT

        # Priority 6: Causal or temporal → LinearChain
        if ComplexitySignal.CAUSAL_REASONING in signals:
            return WorkflowType.LINEAR_CHAIN
        if ComplexitySignal.TEMPORAL_REASONING in signals:
            return WorkflowType.LINEAR_CHAIN

        # Default: LinearChain
        return WorkflowType.LINEAR_CHAIN


# =============================================================================
# WORKFLOW SELECTOR (standalone)
# =============================================================================


class WorkflowSelector:
    """
    Maps ComplexitySignals to the optimal workflow.

    Can be used independently of the MetacognitiveWorkflow for
    cases where you want to select a workflow but run it yourself.

    Signal → Workflow mapping:
        COMPARISON_REQUEST  → MapReduce
        CAUSAL_REASONING    → LinearChain
        AMBIGUITY_DETECTED  → TreeOfThought
        CREATIVE_SYNTHESIS  → IterativeRefinement
        CONDITIONAL_LOGIC   → Debate
        TEMPORAL_REASONING  → LinearChain
        ABSTRACT_CONCEPT    → TreeOfThought
        META_REASONING      → LinearChain (avoids recursion)
        MULTI_PART_QUESTION → MapReduce
        DOMAIN_EXPERTISE    → LinearChain
    """

    # Default signal → workflow mapping
    SIGNAL_MAP: Dict[ComplexitySignal, WorkflowType] = {
        ComplexitySignal.COMPARISON_REQUEST: WorkflowType.MAP_REDUCE,
        ComplexitySignal.CAUSAL_REASONING: WorkflowType.LINEAR_CHAIN,
        ComplexitySignal.AMBIGUITY_DETECTED: WorkflowType.TREE_OF_THOUGHT,
        ComplexitySignal.CREATIVE_SYNTHESIS: WorkflowType.ITERATIVE_REFINEMENT,
        ComplexitySignal.CONDITIONAL_LOGIC: WorkflowType.DEBATE,
        ComplexitySignal.TEMPORAL_REASONING: WorkflowType.LINEAR_CHAIN,
        ComplexitySignal.ABSTRACT_CONCEPT: WorkflowType.TREE_OF_THOUGHT,
        ComplexitySignal.META_REASONING: WorkflowType.LINEAR_CHAIN,
        ComplexitySignal.MULTI_PART_QUESTION: WorkflowType.MAP_REDUCE,
        ComplexitySignal.DOMAIN_EXPERTISE: WorkflowType.LINEAR_CHAIN,
    }

    # Priority order for signal evaluation (first match wins)
    SIGNAL_PRIORITY: List[ComplexitySignal] = [
        ComplexitySignal.CONDITIONAL_LOGIC,
        ComplexitySignal.COMPARISON_REQUEST,
        ComplexitySignal.MULTI_PART_QUESTION,
        ComplexitySignal.AMBIGUITY_DETECTED,
        ComplexitySignal.ABSTRACT_CONCEPT,
        ComplexitySignal.CREATIVE_SYNTHESIS,
        ComplexitySignal.CAUSAL_REASONING,
        ComplexitySignal.TEMPORAL_REASONING,
        ComplexitySignal.META_REASONING,
        ComplexitySignal.DOMAIN_EXPERTISE,
    ]

    def __init__(
        self,
        custom_mapping: Optional[Dict[ComplexitySignal, WorkflowType]] = None,
    ):
        self.signal_map = {**self.SIGNAL_MAP}
        if custom_mapping:
            self.signal_map.update(custom_mapping)

    def select(
        self, analysis: ComplexityAnalysis
    ) -> Tuple[WorkflowType, str]:
        """
        Select the best workflow for the given complexity analysis.

        Returns:
            Tuple of (WorkflowType, reason_string)
        """
        signals = set(analysis.signals)

        for signal in self.SIGNAL_PRIORITY:
            if signal in signals:
                wf = self.signal_map[signal]
                return wf, f"Signal {signal.value} → {wf.value}"

        return WorkflowType.LINEAR_CHAIN, "No specific signal → default LinearChain"

    def get_mapping_table(self) -> List[Dict[str, str]]:
        """Return the full mapping table for documentation."""
        return [
            {"signal": s.value, "workflow": w.value}
            for s, w in self.signal_map.items()
        ]


# =============================================================================
# WORKFLOW REGISTRY
# =============================================================================


class WorkflowRegistry:
    """
    Registry of all available workflows.

    Provides a single place to look up workflows by type,
    list all available workflows, and get workflow metadata.
    """

    def __init__(self):
        self._workflows: Dict[WorkflowType, ReasoningWorkflow] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register all built-in workflows."""
        self.register(LinearChainWorkflow())
        self.register(TreeOfThoughtWorkflow())
        self.register(IterativeRefinementWorkflow())
        self.register(DebateWorkflow())
        self.register(MapReduceWorkflow())
        self.register(SocraticProgressiveWorkflow())
        self.register(MetacognitiveWorkflow())

    def register(self, workflow: ReasoningWorkflow):
        """Register a workflow."""
        self._workflows[workflow.workflow_type] = workflow

    def get(self, workflow_type: WorkflowType) -> ReasoningWorkflow:
        """Get a workflow by type."""
        if workflow_type not in self._workflows:
            raise KeyError(f"Unknown workflow type: {workflow_type}")
        return self._workflows[workflow_type]

    def list_all(self) -> List[Dict[str, Any]]:
        """List all registered workflows with metadata."""
        return [
            {
                "type": wf.workflow_type.value,
                "description": wf.description,
                "best_for": [s.value for s in wf.best_for],
            }
            for wf in self._workflows.values()
        ]

    @property
    def available_types(self) -> List[WorkflowType]:
        """Get all available workflow types."""
        return list(self._workflows.keys())


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_workflow_registry() -> WorkflowRegistry:
    """Create a registry with all default workflows."""
    return WorkflowRegistry()


def create_workflow_selector(
    custom_mapping: Optional[Dict[ComplexitySignal, WorkflowType]] = None,
) -> WorkflowSelector:
    """Create a workflow selector with optional custom mapping."""
    return WorkflowSelector(custom_mapping=custom_mapping)


def create_metacognitive_workflow(
    detector: Optional[ComplexityDetector] = None,
) -> MetacognitiveWorkflow:
    """Create the metacognitive workflow (auto-selects best workflow)."""
    return MetacognitiveWorkflow(detector=detector)


# =============================================================================
# PUBLIC API
# =============================================================================


__all__ = [
    # Enums
    "WorkflowType",
    # Data classes
    "WorkflowStep",
    "WorkflowResult",
    # Base class
    "ReasoningWorkflow",
    # Workflow implementations
    "LinearChainWorkflow",
    "TreeOfThoughtWorkflow",
    "IterativeRefinementWorkflow",
    "DebateWorkflow",
    "MapReduceWorkflow",
    "SocraticProgressiveWorkflow",
    "MetacognitiveWorkflow",
    # Selection
    "WorkflowSelector",
    "WorkflowRegistry",
    # Factory functions
    "create_workflow_registry",
    "create_workflow_selector",
    "create_metacognitive_workflow",
]
