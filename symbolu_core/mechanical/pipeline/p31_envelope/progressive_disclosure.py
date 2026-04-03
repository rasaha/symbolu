"""
Progressive Disclosure
=======================

Structures output into expandable layers that reveal increasing detail:
- TL;DR: One-sentence summary
- Key Points: Bullet point highlights
- Full Response: Complete content
- Deep Dive: Technical details, citations, context

This enables adaptive UI that shows appropriate detail level based on
user preference, device, or context.

Integration:
    Used by P31 envelope phase to wrap output in progressive structure.

Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import re

# =============================================================================
# VERSION
# =============================================================================

VERSION = "1.0.0"


# =============================================================================
# ENUMS
# =============================================================================


class DisclosureLevel(Enum):
    """Levels of progressive disclosure."""
    TLDR = "tldr"               # One sentence summary
    KEY_POINTS = "key_points"   # Bullet point highlights
    FULL = "full"               # Complete response
    DEEP_DIVE = "deep_dive"     # Full + technical details


class ContentType(Enum):
    """Type of content being disclosed."""
    EXPLANATION = "explanation"
    INSTRUCTIONS = "instructions"
    ANALYSIS = "analysis"
    CREATIVE = "creative"
    CONVERSATIONAL = "conversational"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class DisclosureLayer:
    """A single layer of disclosed content."""
    level: DisclosureLevel
    content: str
    word_count: int
    is_generated: bool = False  # True if auto-generated from full text


@dataclass(frozen=True)
class ProgressiveResponse:
    """Response structured for progressive disclosure."""
    tldr: Optional[str]
    key_points: Tuple[str, ...]
    full_response: str
    deep_dive: Optional[str]
    content_type: ContentType
    layers: Tuple[DisclosureLayer, ...]
    default_level: DisclosureLevel = DisclosureLevel.FULL

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tldr": self.tldr,
            "key_points": list(self.key_points),
            "full_response": self.full_response,
            "deep_dive": self.deep_dive,
            "content_type": self.content_type.value,
            "default_level": self.default_level.value,
            "layers": [
                {
                    "level": layer.level.value,
                    "content": layer.content,
                    "word_count": layer.word_count,
                    "is_generated": layer.is_generated,
                }
                for layer in self.layers
            ],
        }

    def get_layer(self, level: DisclosureLevel) -> Optional[DisclosureLayer]:
        """Get content at specified disclosure level."""
        for layer in self.layers:
            if layer.level == level:
                return layer
        return None

    def get_content_at_level(self, level: DisclosureLevel) -> str:
        """Get content string at specified level, with fallback."""
        layer = self.get_layer(level)
        if layer:
            return layer.content

        # Fallback hierarchy
        if level == DisclosureLevel.TLDR:
            return self.tldr or self.full_response[:100] + "..."
        elif level == DisclosureLevel.KEY_POINTS:
            return "\n".join(f"• {p}" for p in self.key_points) if self.key_points else self.full_response
        elif level == DisclosureLevel.DEEP_DIVE:
            return self.deep_dive or self.full_response

        return self.full_response


# =============================================================================
# PROGRESSIVE DISCLOSURE ENGINE
# =============================================================================


class ProgressiveDisclosureEngine:
    """
    Transforms text into progressive disclosure layers.

    Uses heuristic extraction for deterministic, LLM-free operation:
    - TL;DR: First sentence or extracted topic sentence
    - Key Points: Sentences containing key terms or bullet points
    - Full: Original text
    - Deep Dive: Full text with any available technical context
    """

    # Indicators that a sentence is a key point
    KEY_POINT_INDICATORS = frozenset({
        "important", "key", "main", "critical", "essential", "notably",
        "significantly", "primarily", "fundamentally", "crucially",
        "first", "second", "third", "finally", "additionally",
    })

    # Indicators of summary/conclusion sentences
    SUMMARY_INDICATORS = frozenset({
        "in summary", "to summarize", "in conclusion", "overall",
        "the main point", "essentially", "in short", "briefly",
        "to conclude", "in essence",
    })

    # Technical depth indicators
    TECHNICAL_INDICATORS = frozenset({
        "specifically", "technically", "implementation", "architecture",
        "algorithm", "parameter", "configuration", "protocol",
        "specification", "performance", "optimization", "complexity",
    })

    def __init__(
        self,
        max_tldr_words: int = 30,
        max_key_points: int = 5,
        min_key_point_words: int = 5,
    ):
        """
        Initialize progressive disclosure engine.

        Args:
            max_tldr_words: Maximum words in TL;DR.
            max_key_points: Maximum number of key points.
            min_key_point_words: Minimum words for a valid key point.
        """
        self.max_tldr_words = max_tldr_words
        self.max_key_points = max_key_points
        self.min_key_point_words = min_key_point_words

    def process(
        self,
        text: str,
        content_type: Optional[ContentType] = None,
        deep_dive_context: Optional[str] = None,
    ) -> ProgressiveResponse:
        """
        Process text into progressive disclosure layers.

        Args:
            text: Full response text.
            content_type: Type of content (auto-detected if not provided).
            deep_dive_context: Optional additional context for deep dive.

        Returns:
            ProgressiveResponse with disclosure layers.
        """
        # Detect content type
        if content_type is None:
            content_type = self._detect_content_type(text)

        # Extract sentences
        sentences = self._split_sentences(text)

        # Generate TL;DR
        tldr = self._extract_tldr(sentences)

        # Extract key points
        key_points = self._extract_key_points(text, sentences)

        # Build deep dive
        deep_dive = self._build_deep_dive(text, deep_dive_context)

        # Build layers
        layers = self._build_layers(tldr, key_points, text, deep_dive)

        # Determine default level based on content length
        word_count = len(text.split())
        if word_count < 50:
            default_level = DisclosureLevel.FULL
        elif word_count < 200:
            default_level = DisclosureLevel.KEY_POINTS
        else:
            default_level = DisclosureLevel.KEY_POINTS

        return ProgressiveResponse(
            tldr=tldr,
            key_points=tuple(key_points),
            full_response=text,
            deep_dive=deep_dive,
            content_type=content_type,
            layers=tuple(layers),
            default_level=default_level,
        )

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _detect_content_type(self, text: str) -> ContentType:
        """Detect content type from text."""
        text_lower = text.lower()

        # Check for instructions (imperative mood)
        if re.search(r'\b(do|don\'t|try|use|make|create|follow|avoid)\b', text_lower):
            instruction_count = len(re.findall(r'\b(step|first|then|next|finally)\b', text_lower))
            if instruction_count >= 2:
                return ContentType.INSTRUCTIONS

        # Check for analysis
        if any(term in text_lower for term in ["analysis", "examine", "evaluate", "compare", "assess"]):
            return ContentType.ANALYSIS

        # Check for creative
        if any(term in text_lower for term in ["story", "poem", "once upon", "imagine"]):
            return ContentType.CREATIVE

        # Check for conversational
        if len(text) < 200 and re.search(r'\?|!{2,}|\bhi\b|\bhello\b|\bthanks\b', text_lower):
            return ContentType.CONVERSATIONAL

        return ContentType.EXPLANATION

    def _extract_tldr(self, sentences: List[str]) -> Optional[str]:
        """Extract TL;DR from sentences."""
        if not sentences:
            return None

        # Look for explicit summary sentence
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(ind in sentence_lower for ind in self.SUMMARY_INDICATORS):
                if len(sentence.split()) <= self.max_tldr_words:
                    return sentence

        # Use first sentence if short enough
        first = sentences[0]
        if len(first.split()) <= self.max_tldr_words:
            return first

        # Truncate first sentence
        words = first.split()[:self.max_tldr_words]
        return " ".join(words) + "..."

    def _extract_key_points(
        self,
        text: str,
        sentences: List[str],
    ) -> List[str]:
        """Extract key points from text."""
        key_points = []

        # Check for existing bullet points
        bullet_matches = re.findall(r'[•\-\*]\s*(.+?)(?=\n|$)', text)
        if bullet_matches:
            for point in bullet_matches[:self.max_key_points]:
                if len(point.split()) >= self.min_key_point_words:
                    key_points.append(point.strip())
            if key_points:
                return key_points

        # Check for numbered points
        numbered_matches = re.findall(r'\d+[.)]\s*(.+?)(?=\n|$)', text)
        if numbered_matches:
            for point in numbered_matches[:self.max_key_points]:
                if len(point.split()) >= self.min_key_point_words:
                    key_points.append(point.strip())
            if key_points:
                return key_points

        # Extract sentences with key point indicators
        for sentence in sentences:
            if len(key_points) >= self.max_key_points:
                break

            sentence_lower = sentence.lower()
            if any(ind in sentence_lower for ind in self.KEY_POINT_INDICATORS):
                if len(sentence.split()) >= self.min_key_point_words:
                    key_points.append(sentence)

        # If still no points, take important-looking sentences
        if not key_points and len(sentences) > 2:
            # Take sentences from different parts of the text
            indices = [0, len(sentences) // 2, -1]
            for i in indices:
                if len(key_points) >= self.max_key_points:
                    break
                sentence = sentences[i]
                if len(sentence.split()) >= self.min_key_point_words:
                    if sentence not in key_points:
                        key_points.append(sentence)

        return key_points

    def _build_deep_dive(
        self,
        text: str,
        additional_context: Optional[str],
    ) -> Optional[str]:
        """Build deep dive content."""
        # Check if text contains technical content
        text_lower = text.lower()
        has_technical = any(term in text_lower for term in self.TECHNICAL_INDICATORS)

        if not has_technical and not additional_context:
            return None

        parts = [text]

        if additional_context:
            parts.append("\n\n---\n**Additional Context:**\n")
            parts.append(additional_context)

        return "".join(parts)

    def _build_layers(
        self,
        tldr: Optional[str],
        key_points: List[str],
        full_text: str,
        deep_dive: Optional[str],
    ) -> List[DisclosureLayer]:
        """Build disclosure layers."""
        layers = []

        # TL;DR layer
        if tldr:
            layers.append(DisclosureLayer(
                level=DisclosureLevel.TLDR,
                content=tldr,
                word_count=len(tldr.split()),
                is_generated=True,
            ))

        # Key points layer
        if key_points:
            key_points_text = "\n".join(f"• {p}" for p in key_points)
            layers.append(DisclosureLayer(
                level=DisclosureLevel.KEY_POINTS,
                content=key_points_text,
                word_count=sum(len(p.split()) for p in key_points),
                is_generated=True,
            ))

        # Full response layer
        layers.append(DisclosureLayer(
            level=DisclosureLevel.FULL,
            content=full_text,
            word_count=len(full_text.split()),
            is_generated=False,
        ))

        # Deep dive layer
        if deep_dive:
            layers.append(DisclosureLayer(
                level=DisclosureLevel.DEEP_DIVE,
                content=deep_dive,
                word_count=len(deep_dive.split()),
                is_generated=True,
            ))

        return layers


# =============================================================================
# SINGLETON
# =============================================================================

_engine: Optional[ProgressiveDisclosureEngine] = None


def get_progressive_disclosure_engine() -> ProgressiveDisclosureEngine:
    """Get or create singleton ProgressiveDisclosureEngine instance."""
    global _engine
    if _engine is None:
        _engine = ProgressiveDisclosureEngine()
    return _engine


def create_progressive_response(
    text: str,
    content_type: Optional[ContentType] = None,
    deep_dive_context: Optional[str] = None,
) -> ProgressiveResponse:
    """
    Convenience function to create progressive response.

    Args:
        text: Full response text.
        content_type: Type of content.
        deep_dive_context: Additional context for deep dive.

    Returns:
        ProgressiveResponse with disclosure layers.
    """
    return get_progressive_disclosure_engine().process(
        text, content_type, deep_dive_context
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "DisclosureLevel",
    "ContentType",
    "DisclosureLayer",
    "ProgressiveResponse",
    "ProgressiveDisclosureEngine",
    "get_progressive_disclosure_engine",
    "create_progressive_response",
]
