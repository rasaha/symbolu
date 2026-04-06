"""
Reflective Generation Component

Generates responses with self-evaluation and revision loop.
Inspired by Reflective Phase-Quad Architecture (generate -> critic -> revise).

ARCHITECTURE:
    Generator (LLM) -> Critic (Quality Estimator) -> Decision Gate -> [Revise or Output]

LOOP BEHAVIOR:
    1. Generate initial response
    2. Evaluate quality with critic
    3. If quality < threshold and revisions < max:
       - Generate revision context
       - Loop back to step 1 with revision prompt
    4. Return best response

INVARIANTS:
    - INV-REF-1: Always returns best quality response seen
    - INV-REF-2: Never exceeds max_revisions
    - INV-REF-3: Critic evaluation is deterministic for same inputs
"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Protocol, Union


class LLMClient(Protocol):
    """Protocol for LLM client interface."""

    def call(self, prompt: str) -> str:
        """Call LLM with prompt and return response."""
        ...


@dataclass
class QualityCritique:
    """
    Quality assessment from critic.

    Contains overall score and dimension-specific scores,
    plus revision guidance.
    """

    # Overall quality score [0.0, 1.0]
    overall_score: float

    # Dimension scores [0.0, 1.0]
    coherence: float  # Is the response logically consistent?
    correctness: float  # Is the information accurate?
    completeness: float  # Does it fully address the request?
    relevance: float  # Is it on-topic?

    # Revision guidance
    revision_needed: bool
    revision_type: str  # "none", "minor", "major"
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "overall_score": self.overall_score,
            "coherence": self.coherence,
            "correctness": self.correctness,
            "completeness": self.completeness,
            "relevance": self.relevance,
            "revision_needed": self.revision_needed,
            "revision_type": self.revision_type,
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


@dataclass
class GenerationResult:
    """
    Result from reflective generation.

    Contains final output plus metadata about the generation process.
    """

    final_output: str
    quality_score: float

    # Revision history
    revision_count: int
    quality_trajectory: List[float] = field(default_factory=list)

    # Metadata
    generation_time_ms: float = 0.0
    token_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "final_output": self.final_output,
            "quality_score": self.quality_score,
            "revision_count": self.revision_count,
            "quality_trajectory": self.quality_trajectory,
            "generation_time_ms": self.generation_time_ms,
            "token_count": self.token_count,
        }


class QualityCritic(ABC):
    """
    Abstract base class for quality critics.

    Critics evaluate response quality and provide revision guidance.
    Can be implemented as:
    1. Rule-based (deterministic checks)
    2. LLM-based (use smaller model to evaluate)
    3. Hybrid (rules + LLM)
    """

    @abstractmethod
    def evaluate(
        self,
        prompt: str,
        response: str,
        goal_state: Optional[Any] = None,
    ) -> QualityCritique:
        """
        Evaluate response quality.

        Args:
            prompt: Original user prompt
            response: Generated response to evaluate
            goal_state: Optional GoalState for context

        Returns:
            QualityCritique with scores and guidance
        """
        pass


class RuleBasedCritic(QualityCritic):
    """
    Simple rule-based critic for basic quality checks.

    Uses heuristics to evaluate:
    - Response length
    - Keyword coverage
    - Common issues detection
    """

    def __init__(
        self,
        min_length: int = 50,
        target_length: int = 500,
    ):
        self.min_length = min_length
        self.target_length = target_length

    def evaluate(
        self,
        prompt: str,
        response: str,
        goal_state: Optional[Any] = None,
    ) -> QualityCritique:
        """Evaluate using rule-based heuristics."""
        issues = []
        suggestions = []

        # Check response length
        response_length = len(response)
        if response_length < self.min_length:
            issues.append("Response too short")
            suggestions.append("Provide more detail and explanation")

        # Check for non-informative responses
        non_informative_phrases = [
            "I don't know",
            "I cannot",
            "I'm not sure",
            "I'm unable",
        ]
        for phrase in non_informative_phrases:
            if phrase.lower() in response.lower() and response_length < 100:
                issues.append("Non-informative response")
                suggestions.append("Try to provide partial information or alternatives")
                break

        # Check goal alignment (keyword overlap)
        goal_alignment_score = 0.7
        if goal_state is not None:
            purpose = getattr(goal_state, "purpose", "")
            if purpose:
                keywords = [w for w in purpose.lower().split() if len(w) > 4]
                response_lower = response.lower()
                if keywords:
                    matched = sum(1 for k in keywords if k in response_lower)
                    goal_alignment_score = min(1.0, 0.3 + (matched / len(keywords)) * 0.7)

                    if matched < len(keywords) // 2:
                        missing = [k for k in keywords if k not in response_lower][:3]
                        issues.append("Response may not fully address the goal")
                        suggestions.append(f"Consider addressing: {', '.join(missing)}")

        # Compute dimension scores
        coherence = 0.8  # Assume coherent unless specific issues detected
        correctness = 0.7 if not issues else 0.5
        completeness = min(1.0, response_length / self.target_length)
        relevance = goal_alignment_score

        # Check for formatting issues
        if response.count("\n\n\n") > 2:
            issues.append("Excessive whitespace")
            suggestions.append("Improve formatting")
            coherence -= 0.1

        # Check for repetition
        sentences = response.split(".")
        if len(sentences) > 3:
            unique_sentences = set(s.strip().lower() for s in sentences if s.strip())
            if len(unique_sentences) < len(sentences) * 0.7:
                issues.append("Repetitive content detected")
                suggestions.append("Avoid repeating the same points")
                coherence -= 0.15

        # Compute overall score
        overall = (coherence + correctness + completeness + relevance) / 4

        # Determine revision need
        revision_needed = overall < 0.7 or len(issues) > 1
        if overall < 0.5:
            revision_type = "major"
        elif overall < 0.7:
            revision_type = "minor"
        else:
            revision_type = "none"

        return QualityCritique(
            overall_score=max(0.0, min(1.0, overall)),
            coherence=max(0.0, min(1.0, coherence)),
            correctness=max(0.0, min(1.0, correctness)),
            completeness=max(0.0, min(1.0, completeness)),
            relevance=max(0.0, min(1.0, relevance)),
            revision_needed=revision_needed,
            revision_type=revision_type,
            issues=issues,
            suggestions=suggestions,
        )


class LLMBasedCritic(QualityCritic):
    """
    LLM-based critic using a model to evaluate quality.

    Can use a smaller/faster model for evaluation to reduce costs.
    """

    EVALUATION_PROMPT = """
Evaluate the quality of this response on a scale of 0.0 to 1.0.

User request: {prompt}

Response to evaluate:
{response}

Rate the following dimensions from 0.0 (poor) to 1.0 (excellent):
1. Coherence: Is the response logically consistent and well-structured?
2. Correctness: Is the information accurate (to the best of your knowledge)?
3. Completeness: Does it fully address the user's request?
4. Relevance: Is it on-topic and focused?

Also identify any issues and provide specific suggestions for improvement.

Respond ONLY with valid JSON:
{{
    "coherence": 0.0-1.0,
    "correctness": 0.0-1.0,
    "completeness": 0.0-1.0,
    "relevance": 0.0-1.0,
    "issues": ["issue1", "issue2"],
    "suggestions": ["suggestion1", "suggestion2"]
}}
"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def evaluate(
        self,
        prompt: str,
        response: str,
        goal_state: Optional[Any] = None,
    ) -> QualityCritique:
        """Evaluate using LLM."""
        eval_prompt = self.EVALUATION_PROMPT.format(prompt=prompt, response=response)

        try:
            result = self.llm.call(eval_prompt)
            parsed = self._extract_json(result)
        except Exception:
            # Fall back to moderate scores on parsing failure
            parsed = {
                "coherence": 0.6,
                "correctness": 0.6,
                "completeness": 0.6,
                "relevance": 0.6,
                "issues": ["Unable to parse evaluation"],
                "suggestions": ["Review response manually"],
            }

        coherence = float(parsed.get("coherence", 0.6))
        correctness = float(parsed.get("correctness", 0.6))
        completeness = float(parsed.get("completeness", 0.6))
        relevance = float(parsed.get("relevance", 0.6))

        overall = (coherence + correctness + completeness + relevance) / 4

        revision_needed = overall < 0.7
        if overall < 0.5:
            revision_type = "major"
        elif overall < 0.7:
            revision_type = "minor"
        else:
            revision_type = "none"

        return QualityCritique(
            overall_score=max(0.0, min(1.0, overall)),
            coherence=max(0.0, min(1.0, coherence)),
            correctness=max(0.0, min(1.0, correctness)),
            completeness=max(0.0, min(1.0, completeness)),
            relevance=max(0.0, min(1.0, relevance)),
            revision_needed=revision_needed,
            revision_type=revision_type,
            issues=parsed.get("issues", []),
            suggestions=parsed.get("suggestions", []),
        )

    def _extract_json(self, response: str) -> Dict[str, Any]:
        """Extract JSON from LLM response."""
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError("No JSON found in response")


class HybridCritic(QualityCritic):
    """
    Hybrid critic combining rule-based and LLM-based evaluation.

    Uses rule-based for fast checks, LLM for deeper analysis.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        use_llm_threshold: float = 0.8,
    ):
        self.rule_critic = RuleBasedCritic()
        self.llm_critic = LLMBasedCritic(llm_client)
        self.use_llm_threshold = use_llm_threshold

    def evaluate(
        self,
        prompt: str,
        response: str,
        goal_state: Optional[Any] = None,
    ) -> QualityCritique:
        """
        Evaluate using hybrid approach.

        First runs rule-based checks. If score is below threshold,
        runs LLM-based evaluation for deeper analysis.
        """
        # First pass: rule-based
        rule_result = self.rule_critic.evaluate(prompt, response, goal_state)

        # If rule-based score is high enough, return it
        if rule_result.overall_score >= self.use_llm_threshold:
            return rule_result

        # Otherwise, use LLM for deeper analysis
        llm_result = self.llm_critic.evaluate(prompt, response, goal_state)

        # Combine insights
        combined_issues = list(set(rule_result.issues + llm_result.issues))
        combined_suggestions = list(set(rule_result.suggestions + llm_result.suggestions))

        # Use LLM scores but keep rule-based issues
        return QualityCritique(
            overall_score=llm_result.overall_score,
            coherence=llm_result.coherence,
            correctness=llm_result.correctness,
            completeness=llm_result.completeness,
            relevance=llm_result.relevance,
            revision_needed=llm_result.revision_needed,
            revision_type=llm_result.revision_type,
            issues=combined_issues,
            suggestions=combined_suggestions,
        )


class ReflectiveGenerator:
    """
    Generator with self-revision capability.

    LOOP:
    1. Generate initial response
    2. Evaluate quality with critic
    3. If quality < threshold and revisions < max:
       - Generate revision context
       - Loop back to step 1 with revision prompt
    4. Return best response

    INVARIANTS:
    - Always returns best quality response seen
    - Never exceeds max_revisions
    """

    def __init__(
        self,
        llm_client: LLMClient,
        critic: Optional[QualityCritic] = None,
        threshold_high: float = 0.85,
        threshold_low: float = 0.50,
        max_revisions: int = 3,
    ):
        """
        Initialize reflective generator.

        Args:
            llm_client: LLM client for generation
            critic: Quality critic (defaults to RuleBasedCritic)
            threshold_high: Quality threshold for immediate acceptance
            threshold_low: Quality threshold below which major revision needed
            max_revisions: Maximum number of revision attempts
        """
        self.llm = llm_client
        self.critic = critic or RuleBasedCritic()
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low
        self.max_revisions = max_revisions

    def generate(
        self,
        prompt: str,
        context: Optional[str] = None,
        goal_state: Optional[Any] = None,
    ) -> GenerationResult:
        """
        Generate response with optional self-revision.

        Args:
            prompt: User prompt
            context: Optional context from memory
            goal_state: Optional GoalState for alignment

        Returns:
            GenerationResult with final output and metadata
        """
        start_time = time.time()

        # Build full prompt with context
        full_prompt = self._build_prompt(prompt, context, goal_state)

        # Initial generation
        response = self.llm.call(full_prompt)

        quality_trajectory = []
        revision_count = 0
        best_response = response
        best_quality = 0.0

        for revision in range(self.max_revisions + 1):
            # Evaluate quality
            critique = self.critic.evaluate(prompt, response, goal_state)
            quality = critique.overall_score
            quality_trajectory.append(quality)

            # Track best response
            if quality > best_quality:
                best_quality = quality
                best_response = response

            # Decision gate
            if quality >= self.threshold_high:
                # Good enough, output
                break

            if revision >= self.max_revisions:
                # Max revisions reached, output best
                break

            if not critique.revision_needed:
                # Critic says no revision needed
                break

            # Generate revision
            revision_count += 1
            revision_prompt = self._build_revision_prompt(
                original_prompt=prompt,
                previous_response=response,
                critique=critique,
            )
            response = self.llm.call(revision_prompt)

        generation_time_ms = (time.time() - start_time) * 1000

        return GenerationResult(
            final_output=best_response,
            quality_score=best_quality,
            revision_count=revision_count,
            quality_trajectory=quality_trajectory,
            generation_time_ms=generation_time_ms,
            token_count=len(best_response.split()),
        )

    def _build_prompt(
        self,
        prompt: str,
        context: Optional[str],
        goal_state: Optional[Any],
    ) -> str:
        """Build complete prompt with context and goal."""
        parts = []

        if context:
            parts.append(f"Context from previous conversation:\n{context}\n")

        if goal_state is not None:
            purpose = getattr(goal_state, "purpose", "")
            reasoning = getattr(goal_state, "reasoning_strategy", "")
            agency = getattr(goal_state, "agency_level", "CONFIRM")

            if purpose:
                parts.append(
                    f"""
Current goal: {purpose}
Approach: {reasoning}
Agency level: {agency}
"""
                )

        parts.append(f"User request: {prompt}")

        return "\n".join(parts)

    def _build_revision_prompt(
        self,
        original_prompt: str,
        previous_response: str,
        critique: QualityCritique,
    ) -> str:
        """Build prompt for revision."""
        issues_text = "\n".join(f"- {issue}" for issue in critique.issues) or "- General quality improvement needed"
        suggestions_text = "\n".join(f"- {s}" for s in critique.suggestions) or "- Improve clarity and completeness"

        return f"""
Your previous response needs improvement.

Original request: {original_prompt}

Your previous response:
{previous_response}

Quality score: {critique.overall_score:.2f}

Issues identified:
{issues_text}

Suggestions for improvement:
{suggestions_text}

Please provide an improved response that addresses these issues.
Focus on: coherence ({critique.coherence:.2f}), correctness ({critique.correctness:.2f}),
completeness ({critique.completeness:.2f}), and relevance ({critique.relevance:.2f}).
"""

    def generate_single_pass(
        self,
        prompt: str,
        context: Optional[str] = None,
        goal_state: Optional[Any] = None,
    ) -> GenerationResult:
        """
        Generate without revision (single pass).

        Useful for speed-critical situations.
        """
        start_time = time.time()

        full_prompt = self._build_prompt(prompt, context, goal_state)
        response = self.llm.call(full_prompt)

        # Still evaluate quality for metrics
        critique = self.critic.evaluate(prompt, response, goal_state)

        generation_time_ms = (time.time() - start_time) * 1000

        return GenerationResult(
            final_output=response,
            quality_score=critique.overall_score,
            revision_count=0,
            quality_trajectory=[critique.overall_score],
            generation_time_ms=generation_time_ms,
            token_count=len(response.split()),
        )

    def generate_stream(
        self,
        prompt: str,
        context: Optional[str] = None,
        goal_state: Optional[Any] = None,
    ) -> Iterator[Union[str, GenerationResult]]:
        """
        Streaming variant of :meth:`generate`.

        Yields a mixture of:
        - ``str`` — incremental text chunks from the LLM
        - ``("revision_started", int)`` — tuple marking revision *n*
        - ``("revision_completed", int)`` — tuple marking revision *n* done
        - ``GenerationResult`` — final result (always last item)

        The adapter's ``call_stream()`` is used for the initial
        generation.  Revisions use ``call()`` (non-streaming) and
        their full text is yielded as a single chunk.
        """
        start_time = time.time()

        full_prompt = self._build_prompt(prompt, context, goal_state)

        # --- initial generation (streamed) ---
        chunks: list[str] = []
        call_stream = getattr(self.llm, "call_stream", None)
        if callable(call_stream):
            for chunk in call_stream(full_prompt):
                chunks.append(chunk)
                yield chunk
        else:
            # Adapter has no streaming support — fall back
            text = self.llm.call(full_prompt)
            chunks.append(text)
            yield text

        response = "".join(chunks)

        quality_trajectory: list[float] = []
        revision_count = 0
        best_response = response
        best_quality = 0.0

        for revision in range(self.max_revisions + 1):
            critique = self.critic.evaluate(prompt, response, goal_state)
            quality = critique.overall_score
            quality_trajectory.append(quality)

            if quality > best_quality:
                best_quality = quality
                best_response = response

            if quality >= self.threshold_high:
                break
            if revision >= self.max_revisions:
                break
            if not critique.revision_needed:
                break

            # --- revision (non-streaming) ---
            revision_count += 1
            yield ("revision_started", revision_count)

            revision_prompt = self._build_revision_prompt(
                original_prompt=prompt,
                previous_response=response,
                critique=critique,
            )
            response = self.llm.call(revision_prompt)
            # Yield revised text as single chunk
            yield response

            yield ("revision_completed", revision_count)

        generation_time_ms = (time.time() - start_time) * 1000

        yield GenerationResult(
            final_output=best_response,
            quality_score=best_quality,
            revision_count=revision_count,
            quality_trajectory=quality_trajectory,
            generation_time_ms=generation_time_ms,
            token_count=len(best_response.split()),
        )
