"""
Delivery Modulator Module (v3.0)
================================

Applies delivery style modifications to renderer text based on selected profile.

Transforms raw renderer output into an adapted message that aligns with
the chosen delivery profile:
    - SWEET_RESONANCE: Softens tone, adds warmth
    - INVERSE_JOLT: Makes direct, compresses wording
    - SYMBOLIC_METAPHOR: Wraps in metaphorical/symbolic framing
"""

from typing import Dict, Any, Optional, List
from .adaptation_rules import (
    DeliveryProfile,
    get_profile_transform_hints,
    SOFTENING_PREFIXES,
    DIRECT_PREFIXES,
    SYMBOLIC_FRAMES
)


class DeliveryModulator:
    """
    Modulates message delivery based on selected profile.

    Takes renderer output and transforms the text to match
    the delivery profile's tone and style.
    """

    def __init__(self, preserve_original: bool = True):
        """
        Initialize DeliveryModulator.

        Args:
            preserve_original: Whether to include original text in output
        """
        self.preserve_original = preserve_original

    def modulate(
        self,
        text: str,
        profile: DeliveryProfile,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Modulate text according to delivery profile.

        Args:
            text: Original renderer output text
            profile: Selected delivery profile
            context: Optional additional context for modulation

        Returns:
            Modulation result with:
                - adapted_message: Transformed text
                - original_text: Original text (if preserve_original)
                - profile_applied: Profile name
                - transformations: List of transformations applied
        """
        context = context or {}
        transformations = []

        # Apply profile-specific transformation
        if profile == DeliveryProfile.SWEET_RESONANCE:
            adapted = self._apply_sweet_resonance(text, context)
            transformations.append("soften_tone")
            transformations.append("add_warmth")

        elif profile == DeliveryProfile.INVERSE_JOLT:
            adapted = self._apply_inverse_jolt(text, context)
            transformations.append("make_direct")
            transformations.append("compress_wording")

        elif profile == DeliveryProfile.SYMBOLIC_METAPHOR:
            adapted = self._apply_symbolic_metaphor(text, context)
            transformations.append("add_metaphor_frame")
            transformations.append("indirect_delivery")

        else:
            # Fallback: return text unchanged
            adapted = text
            transformations.append("none")

        result = {
            "adapted_message": adapted,
            "profile_applied": profile.value,
            "transformations": transformations,
            "transform_hints": get_profile_transform_hints(profile)
        }

        if self.preserve_original:
            result["original_text"] = text

        return result

    def _apply_sweet_resonance(
        self,
        text: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Apply SWEET_RESONANCE transformation.

        Characteristics:
            - Soft, gentle language
            - Encouraging phrasing
            - Non-confrontational
            - Warm and supportive

        Args:
            text: Original text
            context: Additional context

        Returns:
            Softened text
        """
        # Start with a softening prefix
        prefix = self._select_prefix(SOFTENING_PREFIXES, text)

        # Soften harsh words
        softened = self._soften_language(text)

        # Add supportive closing
        closing = self._get_supportive_closing(context)

        return f"{prefix}{softened}{closing}"

    def _apply_inverse_jolt(
        self,
        text: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Apply INVERSE_JOLT transformation.

        Characteristics:
            - Direct, clear language
            - Compressed, essential wording
            - Confrontational but not harsh
            - Truth-forward

        Args:
            text: Original text
            context: Additional context

        Returns:
            Direct, compressed text
        """
        # Start with direct prefix
        prefix = self._select_prefix(DIRECT_PREFIXES, text)

        # Compress and clarify
        compressed = self._compress_text(text)

        return f"{prefix}{compressed}"

    def _apply_symbolic_metaphor(
        self,
        text: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Apply SYMBOLIC_METAPHOR transformation.

        Characteristics:
            - Metaphorical framing
            - Indirect delivery
            - Symbolic language
            - Invites reflection

        Args:
            text: Original text
            context: Additional context

        Returns:
            Metaphorically framed text
        """
        # Select opening frame
        opening = self._select_symbolic_frame("opening", context)

        # Select closing frame
        closing = self._select_symbolic_frame("closing", context)

        # Wrap the core message
        return f"{opening}{text}\n\n{closing}"

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _select_prefix(
        self,
        prefixes: List[str],
        text: str
    ) -> str:
        """
        Select an appropriate prefix based on text characteristics.

        Uses a deterministic selection based on text hash.

        Args:
            prefixes: List of possible prefixes
            text: Text to analyze

        Returns:
            Selected prefix
        """
        # Deterministic selection based on text length
        index = len(text) % len(prefixes)
        return prefixes[index]

    def _select_symbolic_frame(
        self,
        frame_type: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Select symbolic frame (opening or closing).

        Args:
            frame_type: "opening" or "closing"
            context: Context for selection hints

        Returns:
            Selected frame text
        """
        frames = SYMBOLIC_FRAMES.get(frame_type, [])
        if not frames:
            return ""

        # Use context hint if available, otherwise use first frame
        hint_index = context.get("frame_hint", 0)
        index = hint_index % len(frames)
        return frames[index]

    def _soften_language(self, text: str) -> str:
        """
        Soften harsh or direct language in text.

        Args:
            text: Original text

        Returns:
            Softened text
        """
        # Replacement map for softening
        replacements = {
            "You must": "You might consider",
            "You should": "It may help to",
            "You need to": "Perhaps you could",
            "You have to": "When you're ready, you could",
            "Always": "Often",
            "Never": "Rarely",
            "Wrong": "Not quite aligned",
            "Failure": "Learning opportunity",
            "Problem": "Challenge",
            "must": "might",
            "should": "could",
        }

        result = text
        for harsh, soft in replacements.items():
            result = result.replace(harsh, soft)

        return result

    def _compress_text(self, text: str) -> str:
        """
        Compress text to essential points.

        Args:
            text: Original text

        Returns:
            Compressed text
        """
        # Remove hedging language
        hedges = [
            "perhaps ", "maybe ", "it seems that ",
            "it might be that ", "possibly ", "kind of ",
            "sort of ", "I think ", "In my opinion, "
        ]

        result = text
        for hedge in hedges:
            result = result.replace(hedge, "")
            result = result.replace(hedge.capitalize(), "")

        # Remove filler phrases
        fillers = [
            "to be honest, ", "actually, ", "basically, ",
            "you know, ", "well, "
        ]

        for filler in fillers:
            result = result.replace(filler, "")
            result = result.replace(filler.capitalize(), "")

        return result.strip()

    def _get_supportive_closing(self, context: Dict[str, Any]) -> str:
        """
        Get supportive closing phrase.

        Args:
            context: Context for customization

        Returns:
            Closing phrase
        """
        closings = [
            "\n\nTake your time with this.",
            "\n\nThere's no rush to process everything at once.",
            "\n\nYou're doing meaningful work here.",
            "\n\nThis understanding will unfold in its own time.",
        ]

        index = context.get("closing_hint", 0) % len(closings)
        return closings[index]


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def modulate_delivery(
    text: str,
    profile: DeliveryProfile,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to modulate delivery.

    Args:
        text: Original text
        profile: Delivery profile
        context: Optional context

    Returns:
        Modulation result dictionary
    """
    modulator = DeliveryModulator()
    return modulator.modulate(text, profile, context)


def get_adapted_message(
    text: str,
    profile: DeliveryProfile,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Convenience function to get adapted message only.

    Args:
        text: Original text
        profile: Delivery profile
        context: Optional context

    Returns:
        Adapted message string
    """
    modulator = DeliveryModulator()
    result = modulator.modulate(text, profile, context)
    return result["adapted_message"]


if __name__ == "__main__":
    print("DHA Delivery Modulator v3.0")
    print("=" * 40)
    print("Transforms text based on delivery profile")
    print("\nAvailable transformations:")
    print("  - SWEET_RESONANCE: Softens tone, adds warmth")
    print("  - INVERSE_JOLT: Makes direct, compresses wording")
    print("  - SYMBOLIC_METAPHOR: Wraps in metaphorical framing")
