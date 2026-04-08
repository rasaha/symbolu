"""
ClarifyRenderer: Deterministic Clarification Questions for BLOCKED State

When PO1 (Observer–Observed Grounding) analysis results in a BLOCKED state
(ambiguous grounding that cannot be safely resolved), this renderer produces
deterministic clarification questions to help establish proper grounding.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Design:
- No LLM calls (fully deterministic)
- Template-based question generation
- Deterministic selection (hash of run_id mod N)
- Supports multiple question types based on ambiguity source

Question Categories:
- Perspective: "Are you describing how you feel, or someone else?"
- Reference: "When you say 'you', who are you referring to?"
- Subject: "Is this about a specific person or a general observation?"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import hashlib

from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_schema import (
    PhaseMinusOneEnvelope,
    ClauseGroundingResult,
    ObservationMode,
)


@dataclass
class ClarificationQuestion:
    """
    A clarification question to establish grounding.

    Attributes:
        question_text: The question to ask the user.
        question_type: Category of question (perspective/reference/subject).
        target_clause_index: Which clause needs clarification.
        possible_answers: Suggested answer options (for UI hints).
        run_id: Run ID used for selection.
    """
    question_text: str
    question_type: str
    target_clause_index: int
    possible_answers: List[str]
    run_id: str


class ClarifyRenderer:
    """
    Renderer for generating clarification questions when grounding is BLOCKED.

    Usage:
        renderer = ClarifyRenderer()
        question = renderer.render(envelope)
        # question.question_text = "Are you describing how you feel personally, ..."
    """

    # Perspective clarification templates
    # Used when ambiguous between SELF and OTHER
    PERSPECTIVE_TEMPLATES: List[str] = [
        "Are you describing how you feel personally, or describing someone else's experience?",
        "I want to make sure I understand correctly - are these your own feelings, or are you telling me about someone else?",
        "Is this something you're experiencing yourself, or something you've observed in another person?",
        "Just to clarify: are you sharing your own perspective, or conveying someone else's?",
    ]

    # Reference clarification templates
    # Used when "you" is ambiguous
    REFERENCE_TEMPLATES: List[str] = [
        "When you say 'you', are you referring to yourself, me, or another person?",
        "I want to make sure I follow - who does 'you' refer to in what you shared?",
        "Could you clarify who 'you' is referring to in your message?",
        "Just checking: is 'you' referring to yourself (in a general sense), or someone else?",
    ]

    # Subject clarification templates
    # Used when ambiguous between specific person and general phenomenon
    SUBJECT_TEMPLATES: List[str] = [
        "Is this about a specific person or situation, or a general observation?",
        "Are you talking about someone in particular, or describing something more general?",
        "I'd like to understand better - is this specific to someone, or a broader pattern you've noticed?",
        "Could you help me understand if this is about a particular case or a general experience?",
    ]

    # Generic fallback templates
    GENERIC_TEMPLATES: List[str] = [
        "I want to make sure I understand the context correctly. Could you tell me a bit more about whose perspective or experience this relates to?",
        "Before I respond, I'd like to understand better - could you clarify who or what specifically you're asking about?",
        "I want to be thoughtful in my response. Could you share a bit more about the context or whose experience this involves?",
    ]

    # Answer options by template type
    PERSPECTIVE_ANSWERS: List[str] = [
        "My own feelings/experience",
        "Someone else's feelings/experience",
        "Both / Mixed",
    ]

    REFERENCE_ANSWERS: List[str] = [
        "Referring to myself",
        "Referring to you (the assistant)",
        "Referring to another person",
    ]

    SUBJECT_ANSWERS: List[str] = [
        "A specific person/situation",
        "A general observation",
        "Not sure / Both",
    ]

    def __init__(self) -> None:
        """Initialize the clarification renderer."""
        pass

    def render(self, envelope: PhaseMinusOneEnvelope) -> ClarificationQuestion:
        """
        Generate a clarification question for a BLOCKED envelope.

        Args:
            envelope: PO1 envelope with BLOCKED policy.

        Returns:
            ClarificationQuestion to present to user.
        """
        if not envelope.is_blocked():
            # Not blocked - return generic if called anyway
            return self._render_generic(envelope)

        # Find the first clause that needs clarification
        target_clause = self._find_ambiguous_clause(envelope)

        if target_clause is None:
            return self._render_generic(envelope)

        # Determine question type based on ambiguity
        question_type = self._determine_question_type(target_clause, envelope)

        # Select template deterministically
        templates, answers = self._get_templates_for_type(question_type)
        template_index = self._deterministic_select(envelope.run_id, len(templates))

        return ClarificationQuestion(
            question_text=templates[template_index],
            question_type=question_type,
            target_clause_index=target_clause.clause_index,
            possible_answers=answers,
            run_id=envelope.run_id,
        )

    def _find_ambiguous_clause(
        self, envelope: PhaseMinusOneEnvelope
    ) -> Optional[ClauseGroundingResult]:
        """Find the first clause that caused ambiguity."""
        for clause in envelope.clauses:
            if clause.selected is None:
                return clause
            if clause.grounding_status.value == "AMBIGUOUS":
                return clause
        return envelope.clauses[0] if envelope.clauses else None

    def _determine_question_type(
        self,
        clause: ClauseGroundingResult,
        envelope: PhaseMinusOneEnvelope,
    ) -> str:
        """
        Determine the type of clarification question needed.

        Returns: 'perspective', 'reference', 'subject', or 'generic'
        """
        # Check candidates for clues about ambiguity source
        if not clause.candidates:
            return "generic"

        # Get top two candidates if available
        top_modes = [c.mode for c in clause.candidates[:2]]

        # Check for SELF vs OTHER ambiguity
        if (ObservationMode.REFLEXIVE in top_modes and
                ObservationMode.RELATIONAL in top_modes):
            return "perspective"

        # Check for SELF/OTHER vs PHENOMENON ambiguity
        if ObservationMode.DETACHED in top_modes:
            if (ObservationMode.REFLEXIVE in top_modes or
                    ObservationMode.RELATIONAL in top_modes):
                return "subject"

        # Check for "you" reference ambiguity
        text_lower = clause.clause_text.lower()
        if "you" in text_lower.split():
            return "reference"

        return "generic"

    def _get_templates_for_type(
        self, question_type: str
    ) -> tuple:
        """Get templates and answers for question type."""
        if question_type == "perspective":
            return self.PERSPECTIVE_TEMPLATES, self.PERSPECTIVE_ANSWERS
        elif question_type == "reference":
            return self.REFERENCE_TEMPLATES, self.REFERENCE_ANSWERS
        elif question_type == "subject":
            return self.SUBJECT_TEMPLATES, self.SUBJECT_ANSWERS
        else:
            return self.GENERIC_TEMPLATES, []

    def _deterministic_select(self, run_id: str, n: int) -> int:
        """
        Deterministically select an index based on run_id.

        Uses hash of run_id mod n for reproducible selection.
        """
        if n <= 0:
            return 0
        hash_bytes = hashlib.md5(run_id.encode()).digest()
        hash_int = int.from_bytes(hash_bytes[:4], byteorder='big')
        return hash_int % n

    def _render_generic(
        self, envelope: PhaseMinusOneEnvelope
    ) -> ClarificationQuestion:
        """Render a generic clarification question."""
        template_index = self._deterministic_select(
            envelope.run_id, len(self.GENERIC_TEMPLATES)
        )
        return ClarificationQuestion(
            question_text=self.GENERIC_TEMPLATES[template_index],
            question_type="generic",
            target_clause_index=0,
            possible_answers=[],
            run_id=envelope.run_id,
        )

    def render_text(self, envelope: PhaseMinusOneEnvelope) -> str:
        """
        Convenience method to render just the question text.

        Args:
            envelope: PO1 envelope.

        Returns:
            Question text string.
        """
        question = self.render(envelope)
        return question.question_text


# Singleton instance
_clarify_renderer: Optional[ClarifyRenderer] = None


def get_clarify_renderer() -> ClarifyRenderer:
    """Get the singleton ClarifyRenderer instance."""
    global _clarify_renderer
    if _clarify_renderer is None:
        _clarify_renderer = ClarifyRenderer()
    return _clarify_renderer


def render_clarification(envelope: PhaseMinusOneEnvelope) -> ClarificationQuestion:
    """Convenience function to render clarification question."""
    return get_clarify_renderer().render(envelope)


def render_clarification_text(envelope: PhaseMinusOneEnvelope) -> str:
    """Convenience function to render clarification question text."""
    return get_clarify_renderer().render_text(envelope)


__all__ = [
    "ClarifyRenderer",
    "ClarificationQuestion",
    "get_clarify_renderer",
    "render_clarification",
    "render_clarification_text",
]
