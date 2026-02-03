"""
Barge-in handler for voice agent interruptions.

Manages user interruptions during agent speech, supporting multiple
strategies for different use cases.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from ..providers.base import TranscriptEvent, TranscriptType

logger = logging.getLogger(__name__)


class BargeInStrategy(Enum):
    """Strategy for handling user interruptions."""
    IMMEDIATE = "immediate"     # Stop immediately on any speech
    CONFIRMED = "confirmed"     # Wait for significant speech
    IGNORE = "ignore"           # Complete current response
    SMART = "smart"             # Context-aware decision


@dataclass
class BargeInConfig:
    """Configuration for barge-in detection."""
    # Default strategy
    default_strategy: BargeInStrategy = BargeInStrategy.CONFIRMED

    # Confirmation thresholds
    word_threshold: int = 2              # Min words to confirm interruption
    duration_threshold_ms: float = 500   # Min duration to confirm
    confidence_threshold: float = 0.6    # Min transcript confidence

    # Smart strategy settings
    critical_keywords: tuple = ("stop", "wait", "hold", "cancel", "no")
    continuation_keywords: tuple = ("and", "but", "also", "um", "uh")

    # Timing
    min_speech_gap_ms: float = 200  # Min gap after agent speech to detect


class BargeInHandler:
    """
    Handles user interruptions during agent speech.

    Supports multiple strategies:
    - IMMEDIATE: Stop immediately on any speech detection
    - CONFIRMED: Wait for significant speech before stopping
    - IGNORE: Complete current response (for critical info)
    - SMART: Context-aware decision based on content

    Usage:
        handler = BargeInHandler(config=BargeInConfig(
            default_strategy=BargeInStrategy.CONFIRMED
        ))

        if handler.should_interrupt(transcript_event):
            # Stop TTS and handle interruption
            pass
    """

    def __init__(self, config: Optional[BargeInConfig] = None):
        """
        Initialize barge-in handler.

        Args:
            config: Configuration for barge-in detection
        """
        self.config = config or BargeInConfig()
        self._last_agent_speech_end: Optional[datetime] = None
        self._accumulated_text: str = ""
        self._accumulated_duration_ms: float = 0.0

    def should_interrupt(
        self,
        transcript_event: TranscriptEvent,
        current_strategy: Optional[BargeInStrategy] = None,
        response_priority: str = "normal"
    ) -> bool:
        """
        Determine if current speech should be interrupted.

        Args:
            transcript_event: Current transcription event
            current_strategy: Override strategy for this check
            response_priority: Priority of current response
                              ("normal", "high", "critical")

        Returns:
            True if agent speech should be interrupted
        """
        strategy = current_strategy or self.config.default_strategy

        # Critical responses cannot be interrupted
        if response_priority == "critical":
            return False

        # Check timing - ignore if too close to agent speech end
        if self._last_agent_speech_end:
            time_since_agent = (
                datetime.utcnow() - self._last_agent_speech_end
            ).total_seconds() * 1000
            if time_since_agent < self.config.min_speech_gap_ms:
                return False

        # Strategy-specific handling
        if strategy == BargeInStrategy.IGNORE:
            return False

        if strategy == BargeInStrategy.IMMEDIATE:
            return self._check_immediate(transcript_event)

        if strategy == BargeInStrategy.CONFIRMED:
            return self._check_confirmed(transcript_event)

        if strategy == BargeInStrategy.SMART:
            return self._check_smart(transcript_event)

        return False

    def _check_immediate(self, event: TranscriptEvent) -> bool:
        """Check for immediate interruption (any speech)."""
        text = event.text.strip()
        return len(text) > 0

    def _check_confirmed(self, event: TranscriptEvent) -> bool:
        """Check for confirmed interruption (significant speech)."""
        text = event.text.strip()

        # Check word count
        word_count = len(text.split())
        if word_count >= self.config.word_threshold:
            logger.debug(f"Barge-in: word threshold met ({word_count} words)")
            return True

        # Check duration if word timestamps available
        duration_ms = event.duration_ms
        if duration_ms and duration_ms >= self.config.duration_threshold_ms:
            logger.debug(f"Barge-in: duration threshold met ({duration_ms}ms)")
            return True

        # Check confidence
        if event.confidence < self.config.confidence_threshold:
            return False

        # Accumulate for threshold checking
        if event.transcript_type == TranscriptType.PARTIAL:
            self._accumulated_text = text
            if duration_ms:
                self._accumulated_duration_ms = duration_ms
        else:
            # Final transcript - reset accumulation
            self._accumulated_text = ""
            self._accumulated_duration_ms = 0.0

        return False

    def _check_smart(self, event: TranscriptEvent) -> bool:
        """Check using smart context-aware strategy."""
        text = event.text.strip().lower()

        # Check for critical keywords (immediate interrupt)
        for keyword in self.config.critical_keywords:
            if keyword in text:
                logger.debug(f"Barge-in: critical keyword detected ('{keyword}')")
                return True

        # Check for continuation keywords (don't interrupt)
        for keyword in self.config.continuation_keywords:
            if text.startswith(keyword):
                logger.debug(f"Barge-in: continuation detected ('{keyword}')")
                return False

        # Fall back to confirmed strategy
        return self._check_confirmed(event)

    def record_agent_speech_end(self) -> None:
        """Record when agent speech ends."""
        self._last_agent_speech_end = datetime.utcnow()
        self._accumulated_text = ""
        self._accumulated_duration_ms = 0.0

    def reset(self) -> None:
        """Reset handler state."""
        self._last_agent_speech_end = None
        self._accumulated_text = ""
        self._accumulated_duration_ms = 0.0

    def get_continuation_context(
        self,
        interrupted_text: str,
        spoken_portion: str
    ) -> str:
        """
        Generate context for continuing after interruption.

        This allows the agent to acknowledge what was said and
        either continue or adapt based on the interruption.

        Args:
            interrupted_text: Full text that was being spoken
            spoken_portion: Portion that was actually spoken before interrupt

        Returns:
            Context string for continuation
        """
        # HIGH FIX: Add bounds checking to prevent issues with string slicing
        if not interrupted_text:
            return ""

        spoken_len = len(spoken_portion) if spoken_portion else 0

        # Ensure spoken_len doesn't exceed interrupted_text length
        spoken_len = min(spoken_len, len(interrupted_text))

        # Calculate remaining unsaid portion
        remaining = interrupted_text[spoken_len:].strip()

        if not remaining:
            return ""

        # Truncate if too long
        if len(remaining) > 100:
            remaining = remaining[:100] + "..."

        return f"[Interrupted. Remaining unsaid: '{remaining}']"

    def classify_interruption(
        self,
        transcript_event: TranscriptEvent
    ) -> Tuple[str, float]:
        """
        Classify the type of user interruption.

        Args:
            transcript_event: The transcript that caused interruption

        Returns:
            Tuple of (classification, confidence)
            Classifications: "correction", "question", "redirect",
                           "agreement", "disagreement", "unknown"
        """
        text = transcript_event.text.strip().lower()

        # Question detection
        question_words = ("what", "why", "how", "when", "where", "who", "which")
        if any(text.startswith(w) for w in question_words) or text.endswith("?"):
            return ("question", 0.8)

        # Agreement detection
        agreement_words = ("yes", "yeah", "yep", "right", "okay", "sure", "correct")
        if any(text.startswith(w) for w in agreement_words):
            return ("agreement", 0.7)

        # Disagreement detection
        disagreement_words = ("no", "nope", "wrong", "incorrect", "not")
        if any(text.startswith(w) for w in disagreement_words):
            return ("disagreement", 0.7)

        # Redirect detection
        redirect_words = ("actually", "instead", "rather", "let's", "can we")
        if any(w in text for w in redirect_words):
            return ("redirect", 0.6)

        # Correction detection
        correction_words = ("i meant", "i said", "no i", "not that")
        if any(w in text for w in correction_words):
            return ("correction", 0.7)

        return ("unknown", 0.3)


class AdaptiveBargeInHandler(BargeInHandler):
    """
    Adaptive barge-in handler that learns from user patterns.

    Adjusts thresholds based on how often the user interrupts
    and the types of interruptions they make.
    """

    def __init__(self, config: Optional[BargeInConfig] = None):
        super().__init__(config)

        # Learning state
        self._total_interruptions: int = 0
        self._false_positive_count: int = 0
        self._interruption_types: dict = {}

        # Adaptive thresholds
        self._word_threshold_adjustment: int = 0
        self._duration_threshold_adjustment: float = 0.0

    def record_interruption_feedback(
        self,
        was_valid: bool,
        interruption_type: Optional[str] = None
    ) -> None:
        """
        Record feedback about an interruption for learning.

        Args:
            was_valid: Whether the interruption was valid (not false positive)
            interruption_type: Type of interruption if known
        """
        self._total_interruptions += 1

        if not was_valid:
            self._false_positive_count += 1
            # Increase thresholds to reduce false positives
            self._word_threshold_adjustment += 1
            self._duration_threshold_adjustment += 100

        if interruption_type:
            self._interruption_types[interruption_type] = (
                self._interruption_types.get(interruption_type, 0) + 1
            )

    @property
    def effective_word_threshold(self) -> int:
        """Get effective word threshold with adjustments."""
        base = self.config.word_threshold
        return max(1, base + self._word_threshold_adjustment)

    @property
    def effective_duration_threshold(self) -> float:
        """Get effective duration threshold with adjustments."""
        base = self.config.duration_threshold_ms
        return max(200, base + self._duration_threshold_adjustment)

    @property
    def false_positive_rate(self) -> float:
        """Calculate false positive rate."""
        if self._total_interruptions == 0:
            return 0.0
        return self._false_positive_count / self._total_interruptions
