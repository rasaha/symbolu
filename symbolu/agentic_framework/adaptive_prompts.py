"""
Automated Adaptive AI Prompts for Phase-Quad LLM Model
=======================================================

Generates more complex reasoning chains AUTOMATICALLY without user asking.
The system detects when deeper reasoning is needed and escalates transparently,
while still exposing results to the user in an accessible way.

CORE IDEA:
    User sends simple query -> System detects complexity -> Auto-generates
    multi-step reasoning chain -> Returns enriched response the user can use.

THREE-STAGE PIPELINE:
    1. ComplexityDetector: Analyzes input to classify reasoning depth needed
    2. AdaptivePromptEngine: Builds multi-step prompt chains for each depth level
    3. AutoReasoningPipeline: Orchestrates execution, fusing results back together

REASONING DEPTH LEVELS:
    - SHALLOW: Direct answer, no chain needed (simple facts, greetings)
    - MODERATE: 2-step chain (decompose + synthesize)
    - DEEP: 3-step chain (decompose + analyze + synthesize)
    - RECURSIVE: 4-step chain (decompose + analyze + critique + synthesize)

INTEGRATION:
    Works with existing:
    - ReflectiveGenerator (self-revision loop)
    - ConfidenceGate (behavioral confidence control)
    - AdaptivePolicyEngine (session trajectory tuning)
    - Phase-Quad ReflectivePhaseState (quality tracking)

INVARIANTS:
    - INV-AP-1: Never downgrades user-requested depth
    - INV-AP-2: Auto-escalation is transparent (metadata always exposed)
    - INV-AP-3: Reasoning chain is deterministic for same input + state
    - INV-AP-4: User can always access the full reasoning trace

Author: Symbol-U Adaptive Prompts System
Version: 1.0
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple


# =============================================================================
# PROTOCOLS
# =============================================================================


class LLMClient(Protocol):
    """Protocol for LLM client interface."""

    def call(self, prompt: str) -> str:
        """Call LLM with prompt and return response."""
        ...


# =============================================================================
# ENUMS
# =============================================================================


class ReasoningDepth(IntEnum):
    """
    Reasoning depth levels.

    Higher levels produce more complex reasoning chains automatically.
    Each level adds one reasoning stage.
    """
    SHALLOW = 1     # Direct answer
    MODERATE = 2    # Decompose + Synthesize
    DEEP = 3        # Decompose + Analyze + Synthesize
    RECURSIVE = 4   # Decompose + Analyze + Critique + Synthesize


class ComplexitySignal(Enum):
    """Signals that indicate input complexity."""
    MULTI_PART_QUESTION = "multi_part_question"
    CAUSAL_REASONING = "causal_reasoning"
    COMPARISON_REQUEST = "comparison_request"
    ABSTRACT_CONCEPT = "abstract_concept"
    CONDITIONAL_LOGIC = "conditional_logic"
    TEMPORAL_REASONING = "temporal_reasoning"
    CREATIVE_SYNTHESIS = "creative_synthesis"
    DOMAIN_EXPERTISE = "domain_expertise"
    AMBIGUITY_DETECTED = "ambiguity_detected"
    META_REASONING = "meta_reasoning"


class ReasoningStage(Enum):
    """Stages in a reasoning chain."""
    DECOMPOSE = "decompose"       # Break problem into parts
    ANALYZE = "analyze"           # Deep analysis of each part
    CRITIQUE = "critique"         # Self-critique and identify gaps
    SYNTHESIZE = "synthesize"     # Fuse into coherent response


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ComplexityAnalysis:
    """
    Result of analyzing input complexity.

    Contains detected signals, recommended depth, and reasoning.
    """
    # Detected complexity signals
    signals: List[ComplexitySignal] = field(default_factory=list)

    # Computed scores
    lexical_complexity: float = 0.0     # Word/sentence complexity [0, 1]
    structural_complexity: float = 0.0  # Question structure complexity [0, 1]
    semantic_complexity: float = 0.0    # Conceptual depth [0, 1]

    # Overall
    overall_complexity: float = 0.0     # Weighted aggregate [0, 1]
    recommended_depth: ReasoningDepth = ReasoningDepth.SHALLOW

    # Reasoning trace
    reasoning: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signals": [s.value for s in self.signals],
            "lexical_complexity": self.lexical_complexity,
            "structural_complexity": self.structural_complexity,
            "semantic_complexity": self.semantic_complexity,
            "overall_complexity": self.overall_complexity,
            "recommended_depth": self.recommended_depth.name,
            "reasoning": self.reasoning,
        }


@dataclass
class ReasoningStep:
    """
    A single step in a reasoning chain.

    Contains the prompt sent, the response received, and metadata.
    """
    stage: ReasoningStage
    prompt: str
    response: str = ""
    quality_score: float = 0.0
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "prompt_preview": self.prompt[:200] + "..." if len(self.prompt) > 200 else self.prompt,
            "response_preview": self.response[:200] + "..." if len(self.response) > 200 else self.response,
            "quality_score": self.quality_score,
            "duration_ms": self.duration_ms,
        }


@dataclass
class AdaptivePromptResult:
    """
    Complete result from adaptive prompt pipeline.

    Contains final response, full reasoning chain, and metadata.
    The user can access both the polished response and the reasoning trace.
    """
    # Final output
    final_response: str
    quality_score: float

    # Reasoning chain (exposed to user)
    reasoning_chain: List[ReasoningStep] = field(default_factory=list)
    depth_used: ReasoningDepth = ReasoningDepth.SHALLOW
    was_auto_escalated: bool = False

    # Complexity analysis
    complexity_analysis: Optional[ComplexityAnalysis] = None

    # Performance
    total_duration_ms: float = 0.0
    total_llm_calls: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_response": self.final_response,
            "quality_score": self.quality_score,
            "reasoning_chain": [step.to_dict() for step in self.reasoning_chain],
            "depth_used": self.depth_used.name,
            "was_auto_escalated": self.was_auto_escalated,
            "complexity_analysis": self.complexity_analysis.to_dict() if self.complexity_analysis else None,
            "total_duration_ms": self.total_duration_ms,
            "total_llm_calls": self.total_llm_calls,
        }

    def get_reasoning_trace(self) -> str:
        """
        Get human-readable reasoning trace for user inspection.

        Users can call this to see HOW the system arrived at its answer.
        """
        parts = []
        parts.append(f"[Reasoning Depth: {self.depth_used.name}]")
        if self.was_auto_escalated:
            parts.append("[Auto-escalated: deeper reasoning was triggered automatically]")
        parts.append("")

        for i, step in enumerate(self.reasoning_chain, 1):
            parts.append(f"--- Step {i}: {step.stage.value.upper()} ---")
            parts.append(step.response[:500] if step.response else "(no output)")
            parts.append("")

        return "\n".join(parts)


# =============================================================================
# COMPLEXITY DETECTOR
# =============================================================================


# Patterns that signal different types of complexity
_MULTI_PART_PATTERNS = [
    r"\band\b.*\?",                    # "X and Y?"
    r"\b(?:also|additionally|plus)\b", # additional requests
    r"\d+\.\s",                        # numbered lists
    r"(?:first|second|third|finally)", # enumerated
    r"\?.*\?",                         # multiple questions
]

_CAUSAL_PATTERNS = [
    r"\b(?:why|because|cause|effect|result|lead to|due to)\b",
    r"\b(?:how does|how do|how can|how would)\b",
    r"\b(?:explain|reasoning|rationale)\b",
]

_COMPARISON_PATTERNS = [
    r"\b(?:compare|contrast|difference|versus|vs\.?|better|worse)\b",
    r"\b(?:pros and cons|advantages|disadvantages|tradeoff)\b",
    r"\b(?:which is|what are the differences)\b",
]

_ABSTRACT_PATTERNS = [
    r"\b(?:concept|theory|philosophy|principle|paradigm|framework)\b",
    r"\b(?:meaning|essence|nature of|fundamentally)\b",
    r"\b(?:implications|ramifications|consequences)\b",
]

_CONDITIONAL_PATTERNS = [
    r"\b(?:if|unless|assuming|given that|suppose|hypothetically)\b",
    r"\b(?:would|could|might|should)\b.*\b(?:if|when|while)\b",
    r"\b(?:scenario|edge case|what happens when)\b",
]

_TEMPORAL_PATTERNS = [
    r"\b(?:timeline|history|evolution|progression|over time)\b",
    r"\b(?:before|after|during|since|until|while)\b.*\b(?:how|what|why)\b",
    r"\b(?:sequence|order|steps|phases|stages)\b",
]

_CREATIVE_PATTERNS = [
    r"\b(?:design|create|build|architect|propose|suggest)\b",
    r"\b(?:novel|innovative|creative|original|new approach)\b",
    r"\b(?:combine|integrate|synthesize|merge|fuse)\b",
]

_META_PATTERNS = [
    r"\b(?:how to think about|meta|recursive|self-referential)\b",
    r"\b(?:reasoning about reasoning|think about thinking)\b",
    r"\b(?:approach|strategy|methodology|framework for)\b",
]


class ComplexityDetector:
    """
    Detects input complexity to determine reasoning depth needed.

    Uses multi-signal analysis:
    1. Lexical analysis (word complexity, sentence structure)
    2. Structural analysis (question patterns, multi-part detection)
    3. Semantic analysis (concept density, abstraction level)

    The detector runs AUTOMATICALLY on every input. No user action needed.
    """

    def __init__(
        self,
        shallow_threshold: float = 0.25,
        moderate_threshold: float = 0.45,
        deep_threshold: float = 0.65,
        complexity_boost_per_signal: float = 0.08,
    ):
        """
        Initialize complexity detector.

        Args:
            shallow_threshold: Below this -> SHALLOW
            moderate_threshold: Below this -> MODERATE
            deep_threshold: Below this -> DEEP, above -> RECURSIVE
            complexity_boost_per_signal: Complexity boost per detected signal
        """
        self.shallow_threshold = shallow_threshold
        self.moderate_threshold = moderate_threshold
        self.deep_threshold = deep_threshold
        self.complexity_boost_per_signal = complexity_boost_per_signal

    def analyze(self, text: str) -> ComplexityAnalysis:
        """
        Analyze input text complexity.

        This runs automatically on every user input to determine
        whether deeper reasoning should be triggered.

        Args:
            text: User input text

        Returns:
            ComplexityAnalysis with signals, scores, and recommended depth
        """
        signals: List[ComplexitySignal] = []
        reasoning: List[str] = []

        # 1. Detect complexity signals
        signals.extend(self._detect_signals(text, reasoning))

        # 2. Compute lexical complexity
        lexical = self._compute_lexical_complexity(text, reasoning)

        # 3. Compute structural complexity
        structural = self._compute_structural_complexity(text, reasoning)

        # 4. Compute semantic complexity (from signals)
        semantic = self._compute_semantic_complexity(signals, reasoning)

        # 5. Aggregate
        overall = self._aggregate_complexity(
            lexical, structural, semantic, len(signals), reasoning
        )

        # 6. Determine recommended depth
        depth = self._determine_depth(overall, signals, reasoning)

        return ComplexityAnalysis(
            signals=signals,
            lexical_complexity=lexical,
            structural_complexity=structural,
            semantic_complexity=semantic,
            overall_complexity=overall,
            recommended_depth=depth,
            reasoning=reasoning,
        )

    def _detect_signals(
        self, text: str, reasoning: List[str]
    ) -> List[ComplexitySignal]:
        """Detect complexity signals from text patterns."""
        signals = []
        text_lower = text.lower()

        signal_patterns = [
            (ComplexitySignal.MULTI_PART_QUESTION, _MULTI_PART_PATTERNS),
            (ComplexitySignal.CAUSAL_REASONING, _CAUSAL_PATTERNS),
            (ComplexitySignal.COMPARISON_REQUEST, _COMPARISON_PATTERNS),
            (ComplexitySignal.ABSTRACT_CONCEPT, _ABSTRACT_PATTERNS),
            (ComplexitySignal.CONDITIONAL_LOGIC, _CONDITIONAL_PATTERNS),
            (ComplexitySignal.TEMPORAL_REASONING, _TEMPORAL_PATTERNS),
            (ComplexitySignal.CREATIVE_SYNTHESIS, _CREATIVE_PATTERNS),
            (ComplexitySignal.META_REASONING, _META_PATTERNS),
        ]

        for signal, patterns in signal_patterns:
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    if signal not in signals:
                        signals.append(signal)
                        reasoning.append(f"Detected signal: {signal.value}")
                    break

        # Check for ambiguity (short question with multiple interpretations)
        if len(text.split()) < 8 and "?" in text and not signals:
            signals.append(ComplexitySignal.AMBIGUITY_DETECTED)
            reasoning.append("Short ambiguous question detected")

        return signals

    def _compute_lexical_complexity(
        self, text: str, reasoning: List[str]
    ) -> float:
        """Compute lexical complexity from text properties."""
        words = text.split()
        if not words:
            return 0.0

        # Average word length (normalized)
        avg_word_len = sum(len(w) for w in words) / len(words)
        word_len_score = min(1.0, avg_word_len / 10.0)

        # Sentence count and length
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        sentence_count = max(1, len(sentences))
        avg_sentence_len = len(words) / sentence_count
        sentence_score = min(1.0, avg_sentence_len / 25.0)

        # Vocabulary diversity (unique words / total words)
        unique_ratio = len(set(w.lower() for w in words)) / len(words) if words else 0
        diversity_score = unique_ratio

        # Total word count factor
        length_score = min(1.0, len(words) / 50.0)

        # Weighted combination
        lexical = (
            word_len_score * 0.20 +
            sentence_score * 0.25 +
            diversity_score * 0.25 +
            length_score * 0.30
        )

        reasoning.append(f"Lexical complexity: {lexical:.2f} (words={len(words)}, "
                        f"avg_word_len={avg_word_len:.1f}, sentences={sentence_count})")

        return min(1.0, lexical)

    def _compute_structural_complexity(
        self, text: str, reasoning: List[str]
    ) -> float:
        """Compute structural complexity from question patterns."""
        score = 0.0

        # Multiple questions
        question_marks = text.count("?")
        if question_marks > 1:
            score += 0.3
            reasoning.append(f"Multiple questions detected ({question_marks})")

        # Nested clauses (commas, semicolons, parentheses)
        clause_markers = text.count(",") + text.count(";") + text.count("(")
        if clause_markers > 3:
            score += 0.2
        elif clause_markers > 1:
            score += 0.1

        # Enumeration or listing
        if re.search(r'\d+\.\s|[a-z]\)\s|•|[-*]\s', text):
            score += 0.2
            reasoning.append("Enumerated/listed structure detected")

        # Code or technical markers
        if re.search(r'```|`[^`]+`|def |class |import |function ', text):
            score += 0.15
            reasoning.append("Technical/code content detected")

        # Conditional structure
        if re.search(r'\bif\b.*\bthen\b|\bif\b.*\belse\b', text.lower()):
            score += 0.15

        reasoning.append(f"Structural complexity: {min(1.0, score):.2f}")
        return min(1.0, score)

    def _compute_semantic_complexity(
        self, signals: List[ComplexitySignal], reasoning: List[str]
    ) -> float:
        """Compute semantic complexity from detected signals."""
        if not signals:
            return 0.0

        # Weight signals by conceptual difficulty
        signal_weights = {
            ComplexitySignal.MULTI_PART_QUESTION: 0.3,
            ComplexitySignal.CAUSAL_REASONING: 0.5,
            ComplexitySignal.COMPARISON_REQUEST: 0.4,
            ComplexitySignal.ABSTRACT_CONCEPT: 0.6,
            ComplexitySignal.CONDITIONAL_LOGIC: 0.5,
            ComplexitySignal.TEMPORAL_REASONING: 0.4,
            ComplexitySignal.CREATIVE_SYNTHESIS: 0.6,
            ComplexitySignal.DOMAIN_EXPERTISE: 0.5,
            ComplexitySignal.AMBIGUITY_DETECTED: 0.3,
            ComplexitySignal.META_REASONING: 0.7,
        }

        weighted_sum = sum(signal_weights.get(s, 0.3) for s in signals)
        # Normalize to [0, 1], cap at 1.0
        semantic = min(1.0, weighted_sum / 2.0)

        reasoning.append(f"Semantic complexity: {semantic:.2f} ({len(signals)} signals)")
        return semantic

    def _aggregate_complexity(
        self,
        lexical: float,
        structural: float,
        semantic: float,
        signal_count: int,
        reasoning: List[str],
    ) -> float:
        """Aggregate all complexity dimensions."""
        # Weighted combination (semantic matters most)
        base = (
            lexical * 0.20 +
            structural * 0.25 +
            semantic * 0.55
        )

        # Boost for multiple signals (compounding complexity)
        boost = min(0.2, signal_count * self.complexity_boost_per_signal)
        overall = min(1.0, base + boost)

        reasoning.append(
            f"Overall complexity: {overall:.2f} "
            f"(base={base:.2f}, signal_boost={boost:.2f})"
        )
        return overall

    def _determine_depth(
        self,
        overall: float,
        signals: List[ComplexitySignal],
        reasoning: List[str],
    ) -> ReasoningDepth:
        """Determine recommended reasoning depth."""
        # Signal-based overrides
        if ComplexitySignal.META_REASONING in signals:
            reasoning.append("Meta-reasoning detected -> RECURSIVE depth")
            return ReasoningDepth.RECURSIVE

        if (ComplexitySignal.CAUSAL_REASONING in signals and
                ComplexitySignal.ABSTRACT_CONCEPT in signals):
            reasoning.append("Causal + abstract reasoning -> DEEP depth minimum")
            if overall >= self.moderate_threshold:
                return ReasoningDepth.DEEP

        # Threshold-based
        if overall < self.shallow_threshold:
            depth = ReasoningDepth.SHALLOW
        elif overall < self.moderate_threshold:
            depth = ReasoningDepth.MODERATE
        elif overall < self.deep_threshold:
            depth = ReasoningDepth.DEEP
        else:
            depth = ReasoningDepth.RECURSIVE

        reasoning.append(f"Recommended depth: {depth.name} (complexity={overall:.2f})")
        return depth


# =============================================================================
# ADAPTIVE PROMPT TEMPLATES
# =============================================================================


class AdaptivePromptTemplates:
    """
    Templates for each reasoning stage.

    These are injected automatically based on detected complexity.
    The user never needs to write these prompts themselves.
    """

    DECOMPOSE_TEMPLATE = """You are a reasoning decomposition expert.

Given the following query, break it down into its constituent sub-problems
or sub-questions. Identify what needs to be addressed and in what order.

QUERY: {query}

{context}

Decompose this into clear, ordered sub-problems. For each, identify:
1. What specific question it asks
2. What knowledge or reasoning is needed
3. How it connects to the other sub-problems

DECOMPOSITION:"""

    ANALYZE_TEMPLATE = """You are a deep analysis expert.

Given the original query and its decomposition, provide thorough analysis
of each sub-problem. Use precise reasoning and cite relevant principles.

ORIGINAL QUERY: {query}

DECOMPOSITION:
{decomposition}

{context}

For each sub-problem, provide:
1. Detailed analysis with reasoning steps
2. Key insights or principles that apply
3. Potential edge cases or nuances
4. Confidence level in your analysis

ANALYSIS:"""

    CRITIQUE_TEMPLATE = """You are a rigorous self-critic.

Review the following analysis for gaps, errors, and missed perspectives.
Be thorough but constructive.

ORIGINAL QUERY: {query}

ANALYSIS:
{analysis}

Evaluate:
1. Are there logical gaps or unsupported claims?
2. Are there alternative perspectives not considered?
3. Are there edge cases or exceptions missed?
4. Is the reasoning chain sound from start to finish?
5. What would make this analysis stronger?

CRITIQUE:"""

    SYNTHESIZE_TEMPLATE = """You are a synthesis expert.

Combine the following reasoning into a clear, coherent, and actionable
response that directly addresses the original query.

ORIGINAL QUERY: {query}

{previous_reasoning}

{context}

Synthesize a response that:
1. Directly answers the query
2. Integrates insights from all reasoning stages
3. Is clear, well-structured, and actionable
4. Acknowledges key nuances and limitations
5. Is accessible to the user (not overly academic)

RESPONSE:"""

    # Single-pass template for SHALLOW depth
    DIRECT_TEMPLATE = """Answer the following query directly and concisely.

QUERY: {query}

{context}

RESPONSE:"""


# =============================================================================
# ADAPTIVE PROMPT ENGINE
# =============================================================================


class AdaptivePromptEngine:
    """
    Builds reasoning prompt chains based on complexity depth.

    Automatically constructs multi-step prompt sequences that the LLM
    will execute in order. Each step builds on the previous one.
    """

    def __init__(
        self,
        templates: Optional[AdaptivePromptTemplates] = None,
    ):
        self.templates = templates or AdaptivePromptTemplates()

    def build_chain(
        self,
        query: str,
        depth: ReasoningDepth,
        context: str = "",
    ) -> List[ReasoningStep]:
        """
        Build a reasoning chain for the given depth.

        Args:
            query: User's original query
            depth: Reasoning depth to use
            context: Optional context from memory/session

        Returns:
            List of ReasoningStep objects (prompts populated, responses empty)
        """
        context_block = f"CONTEXT:\n{context}" if context else ""
        steps = []

        if depth == ReasoningDepth.SHALLOW:
            # Single direct step
            steps.append(ReasoningStep(
                stage=ReasoningStage.SYNTHESIZE,
                prompt=self.templates.DIRECT_TEMPLATE.format(
                    query=query, context=context_block
                ),
            ))

        elif depth == ReasoningDepth.MODERATE:
            # Decompose + Synthesize
            steps.append(ReasoningStep(
                stage=ReasoningStage.DECOMPOSE,
                prompt=self.templates.DECOMPOSE_TEMPLATE.format(
                    query=query, context=context_block
                ),
            ))
            steps.append(ReasoningStep(
                stage=ReasoningStage.SYNTHESIZE,
                prompt="",  # Built dynamically after decompose
            ))

        elif depth == ReasoningDepth.DEEP:
            # Decompose + Analyze + Synthesize
            steps.append(ReasoningStep(
                stage=ReasoningStage.DECOMPOSE,
                prompt=self.templates.DECOMPOSE_TEMPLATE.format(
                    query=query, context=context_block
                ),
            ))
            steps.append(ReasoningStep(
                stage=ReasoningStage.ANALYZE,
                prompt="",  # Built dynamically
            ))
            steps.append(ReasoningStep(
                stage=ReasoningStage.SYNTHESIZE,
                prompt="",  # Built dynamically
            ))

        elif depth == ReasoningDepth.RECURSIVE:
            # Decompose + Analyze + Critique + Synthesize
            steps.append(ReasoningStep(
                stage=ReasoningStage.DECOMPOSE,
                prompt=self.templates.DECOMPOSE_TEMPLATE.format(
                    query=query, context=context_block
                ),
            ))
            steps.append(ReasoningStep(
                stage=ReasoningStage.ANALYZE,
                prompt="",
            ))
            steps.append(ReasoningStep(
                stage=ReasoningStage.CRITIQUE,
                prompt="",
            ))
            steps.append(ReasoningStep(
                stage=ReasoningStage.SYNTHESIZE,
                prompt="",
            ))

        return steps

    def build_step_prompt(
        self,
        query: str,
        step: ReasoningStep,
        previous_steps: List[ReasoningStep],
        context: str = "",
    ) -> str:
        """
        Build the prompt for a specific step using previous step outputs.

        This is called dynamically as each step completes.

        Args:
            query: Original query
            step: Current step to build prompt for
            previous_steps: Already-completed steps with responses
            context: Optional context

        Returns:
            Fully formed prompt string
        """
        context_block = f"CONTEXT:\n{context}" if context else ""

        if step.stage == ReasoningStage.DECOMPOSE:
            return step.prompt  # Already built

        elif step.stage == ReasoningStage.ANALYZE:
            decomposition = self._get_response_for_stage(
                previous_steps, ReasoningStage.DECOMPOSE
            )
            return self.templates.ANALYZE_TEMPLATE.format(
                query=query,
                decomposition=decomposition,
                context=context_block,
            )

        elif step.stage == ReasoningStage.CRITIQUE:
            analysis = self._get_response_for_stage(
                previous_steps, ReasoningStage.ANALYZE
            )
            return self.templates.CRITIQUE_TEMPLATE.format(
                query=query,
                analysis=analysis,
            )

        elif step.stage == ReasoningStage.SYNTHESIZE:
            previous_reasoning = self._build_reasoning_summary(previous_steps)
            return self.templates.SYNTHESIZE_TEMPLATE.format(
                query=query,
                previous_reasoning=previous_reasoning,
                context=context_block,
            )

        return step.prompt

    def _get_response_for_stage(
        self, steps: List[ReasoningStep], stage: ReasoningStage
    ) -> str:
        """Get the response from a specific stage."""
        for s in steps:
            if s.stage == stage and s.response:
                return s.response
        return "(no prior output available)"

    def _build_reasoning_summary(self, steps: List[ReasoningStep]) -> str:
        """Build a summary of all previous reasoning steps."""
        parts = []
        for step in steps:
            if step.response:
                parts.append(f"[{step.stage.value.upper()}]:\n{step.response}")
        return "\n\n".join(parts) if parts else "(no prior reasoning)"


# =============================================================================
# AUTO-REASONING PIPELINE
# =============================================================================


class AutoReasoningPipeline:
    """
    Orchestrates automatic multi-step reasoning without user asking.

    This is the main entry point. It:
    1. Detects input complexity automatically
    2. Builds the appropriate reasoning chain
    3. Executes each step through the LLM
    4. Fuses results into a coherent response
    5. Exposes the full reasoning trace to the user

    The user just calls `pipeline.run(query)` and gets a rich result
    with both the answer and the reasoning chain they can inspect.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        complexity_detector: Optional[ComplexityDetector] = None,
        prompt_engine: Optional[AdaptivePromptEngine] = None,
        min_depth: ReasoningDepth = ReasoningDepth.SHALLOW,
        max_depth: ReasoningDepth = ReasoningDepth.RECURSIVE,
        auto_escalate: bool = True,
        quality_evaluator: Optional[Callable[[str, str], float]] = None,
    ):
        """
        Initialize the auto-reasoning pipeline.

        Args:
            llm_client: LLM client for generation
            complexity_detector: Complexity detector (auto-created if None)
            prompt_engine: Prompt engine (auto-created if None)
            min_depth: Minimum reasoning depth to use
            max_depth: Maximum reasoning depth to use
            auto_escalate: Whether to auto-escalate depth based on complexity
            quality_evaluator: Optional function(query, response) -> score [0, 1]
        """
        self.llm = llm_client
        self.detector = complexity_detector or ComplexityDetector()
        self.engine = prompt_engine or AdaptivePromptEngine()
        self.min_depth = min_depth
        self.max_depth = max_depth
        self.auto_escalate = auto_escalate
        self.quality_evaluator = quality_evaluator

    def run(
        self,
        query: str,
        context: str = "",
        forced_depth: Optional[ReasoningDepth] = None,
    ) -> AdaptivePromptResult:
        """
        Run the full adaptive reasoning pipeline.

        If forced_depth is provided, uses that depth.
        Otherwise, auto-detects complexity and escalates as needed.

        Args:
            query: User's query
            context: Optional conversation context
            forced_depth: Override depth (bypasses auto-detection)

        Returns:
            AdaptivePromptResult with response, chain, and metadata
        """
        start_time = time.time()

        # 1. Analyze complexity (always, even if forced)
        complexity = self.detector.analyze(query)

        # 2. Determine depth
        if forced_depth is not None:
            depth = forced_depth
            was_auto_escalated = False
        elif self.auto_escalate:
            depth = complexity.recommended_depth
            was_auto_escalated = depth > ReasoningDepth.SHALLOW
        else:
            depth = self.min_depth
            was_auto_escalated = False

        # Enforce bounds (INV-AP-1: never downgrade below min)
        depth = ReasoningDepth(max(self.min_depth, min(self.max_depth, depth)))

        # 3. Build reasoning chain
        chain = self.engine.build_chain(query, depth, context)

        # 4. Execute chain step by step
        completed_steps: List[ReasoningStep] = []
        total_calls = 0

        for step in chain:
            step_start = time.time()

            # Build prompt dynamically from previous outputs
            if not step.prompt or step.stage != ReasoningStage.DECOMPOSE:
                if step.stage != ReasoningStage.SYNTHESIZE or completed_steps:
                    step.prompt = self.engine.build_step_prompt(
                        query, step, completed_steps, context
                    )

            # Execute LLM call
            step.response = self.llm.call(step.prompt)
            total_calls += 1

            # Evaluate quality
            if self.quality_evaluator:
                step.quality_score = self.quality_evaluator(query, step.response)
            else:
                step.quality_score = self._basic_quality_check(step.response)

            step.duration_ms = (time.time() - step_start) * 1000
            completed_steps.append(step)

        # 5. Extract final response (last step's output)
        final_response = completed_steps[-1].response if completed_steps else ""
        final_quality = completed_steps[-1].quality_score if completed_steps else 0.0

        total_duration = (time.time() - start_time) * 1000

        return AdaptivePromptResult(
            final_response=final_response,
            quality_score=final_quality,
            reasoning_chain=completed_steps,
            depth_used=depth,
            was_auto_escalated=was_auto_escalated,
            complexity_analysis=complexity,
            total_duration_ms=total_duration,
            total_llm_calls=total_calls,
        )

    def run_with_escalation(
        self,
        query: str,
        context: str = "",
        quality_threshold: float = 0.7,
    ) -> AdaptivePromptResult:
        """
        Run with automatic quality-based escalation.

        Starts at detected depth. If quality is below threshold,
        automatically re-runs at the next deeper level.

        Args:
            query: User's query
            context: Conversation context
            quality_threshold: Minimum quality to accept

        Returns:
            AdaptivePromptResult (possibly from escalated run)
        """
        result = self.run(query, context)

        # Check if quality is sufficient
        if (result.quality_score < quality_threshold and
                result.depth_used < self.max_depth):
            # Escalate to next depth
            next_depth = ReasoningDepth(min(result.depth_used + 1, self.max_depth))
            escalated_result = self.run(query, context, forced_depth=next_depth)
            escalated_result.was_auto_escalated = True

            # Use escalated result if it's better
            if escalated_result.quality_score > result.quality_score:
                return escalated_result

        return result

    def _basic_quality_check(self, response: str) -> float:
        """Basic quality heuristic when no evaluator is provided."""
        if not response:
            return 0.0

        score = 0.3  # Base

        # Length check
        words = len(response.split())
        if words > 20:
            score += 0.2
        if words > 50:
            score += 0.1
        if words > 100:
            score += 0.1

        # Structure check (paragraphs, lists)
        if "\n" in response:
            score += 0.1

        # Non-repetition check
        sentences = [s.strip() for s in response.split(".") if s.strip()]
        if sentences:
            unique_ratio = len(set(s.lower() for s in sentences)) / len(sentences)
            score += unique_ratio * 0.2

        return min(1.0, score)


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_adaptive_pipeline(
    llm_client: LLMClient,
    auto_escalate: bool = True,
    min_depth: ReasoningDepth = ReasoningDepth.SHALLOW,
    max_depth: ReasoningDepth = ReasoningDepth.RECURSIVE,
) -> AutoReasoningPipeline:
    """
    Create an adaptive reasoning pipeline with default configuration.

    Args:
        llm_client: LLM client
        auto_escalate: Enable automatic depth escalation
        min_depth: Minimum reasoning depth
        max_depth: Maximum reasoning depth

    Returns:
        Configured AutoReasoningPipeline
    """
    return AutoReasoningPipeline(
        llm_client=llm_client,
        auto_escalate=auto_escalate,
        min_depth=min_depth,
        max_depth=max_depth,
    )


def create_always_deep_pipeline(
    llm_client: LLMClient,
) -> AutoReasoningPipeline:
    """
    Create a pipeline that always uses DEEP reasoning.

    Useful for applications that always want thorough analysis.
    """
    return AutoReasoningPipeline(
        llm_client=llm_client,
        min_depth=ReasoningDepth.DEEP,
        max_depth=ReasoningDepth.RECURSIVE,
        auto_escalate=True,
    )


def create_conservative_pipeline(
    llm_client: LLMClient,
) -> AutoReasoningPipeline:
    """
    Create a pipeline with conservative escalation thresholds.

    Only escalates for clearly complex queries, saving LLM calls.
    """
    detector = ComplexityDetector(
        shallow_threshold=0.35,
        moderate_threshold=0.55,
        deep_threshold=0.75,
    )
    return AutoReasoningPipeline(
        llm_client=llm_client,
        complexity_detector=detector,
        auto_escalate=True,
        min_depth=ReasoningDepth.SHALLOW,
        max_depth=ReasoningDepth.DEEP,
    )


# =============================================================================
# PUBLIC API
# =============================================================================


__all__ = [
    # Enums
    "ReasoningDepth",
    "ComplexitySignal",
    "ReasoningStage",
    # Data classes
    "ComplexityAnalysis",
    "ReasoningStep",
    "AdaptivePromptResult",
    # Core classes
    "ComplexityDetector",
    "AdaptivePromptTemplates",
    "AdaptivePromptEngine",
    "AutoReasoningPipeline",
    # Factory functions
    "create_adaptive_pipeline",
    "create_always_deep_pipeline",
    "create_conservative_pipeline",
]
