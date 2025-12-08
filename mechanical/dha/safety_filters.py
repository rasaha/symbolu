"""
Safety Filters Module (v3.0)
============================

Minimal guardrails for message safety.

Provides:
    - Harmful pattern detection and removal
    - Text validation for safety compliance
    - Content screening before delivery

This module is intentionally minimal and focused on clear safety boundaries.
"""

from typing import Dict, Any, List, Optional, Tuple
import re


# ============================================================================
# SAFETY CONSTANTS
# ============================================================================

# Patterns that should be flagged or removed
HARMFUL_PATTERNS = [
    # Self-harm related
    r'\b(kill\s+(yourself|myself)|suicide\s+method|how\s+to\s+die)\b',
    # Violence encouragement
    r'\b(hurt\s+(someone|others)|harm\s+(someone|others))\b',
    # Extreme negativity that could damage
    r'\b(worthless|hopeless|nobody\s+cares|give\s+up)\b',
]

# Patterns that should trigger warnings but not removal
WARNING_PATTERNS = [
    # Heavy emotional content
    r'\b(deeply\s+painful|unbearable|devastating)\b',
    # Identity challenging content
    r'\b(fundamentally\s+wrong|everything\s+you\s+believe)\b',
]

# Validation rules for safe text
VALIDATION_RULES = {
    "max_length": 10000,           # Maximum characters
    "min_length": 1,               # Minimum characters
    "max_consecutive_caps": 50,    # Prevent SHOUTING
    "max_special_chars_ratio": 0.3 # Limit special characters
}


class SafetyFilters:
    """
    Safety filter system for DHA message delivery.

    Applies minimal but essential guardrails to ensure
    delivered messages don't cause harm.
    """

    def __init__(
        self,
        strict_mode: bool = False,
        custom_patterns: Optional[List[str]] = None
    ):
        """
        Initialize SafetyFilters.

        Args:
            strict_mode: If True, applies stricter filtering
            custom_patterns: Additional patterns to filter
        """
        self.strict_mode = strict_mode
        self.harmful_patterns = HARMFUL_PATTERNS.copy()
        self.warning_patterns = WARNING_PATTERNS.copy()

        if custom_patterns:
            self.harmful_patterns.extend(custom_patterns)

        # Compile patterns for efficiency
        self._compiled_harmful = [
            re.compile(p, re.IGNORECASE) for p in self.harmful_patterns
        ]
        self._compiled_warning = [
            re.compile(p, re.IGNORECASE) for p in self.warning_patterns
        ]

    def filter(self, text: str) -> Dict[str, Any]:
        """
        Apply safety filters to text.

        Args:
            text: Text to filter

        Returns:
            Filter result with:
                - filtered_text: Safe version of text
                - is_safe: Boolean safety status
                - modifications: List of modifications made
                - warnings: List of warnings triggered
        """
        modifications = []
        warnings = []

        # Step 1: Validate basic structure
        validation_result = self._validate_text(text)
        if not validation_result["valid"]:
            return {
                "filtered_text": "",
                "is_safe": False,
                "modifications": ["text_invalid"],
                "warnings": validation_result["issues"],
                "blocked": True
            }

        # Step 2: Check for harmful patterns
        filtered_text, harmful_mods = self._remove_harmful_patterns(text)
        modifications.extend(harmful_mods)

        # Step 3: Check for warning patterns
        warnings = self._check_warning_patterns(filtered_text)

        # Step 4: Apply strict mode filters if enabled
        if self.strict_mode:
            filtered_text, strict_mods = self._apply_strict_filters(filtered_text)
            modifications.extend(strict_mods)

        is_safe = len(harmful_mods) == 0

        return {
            "filtered_text": filtered_text,
            "is_safe": is_safe,
            "modifications": modifications,
            "warnings": warnings,
            "blocked": False
        }

    def is_safe(self, text: str) -> bool:
        """
        Quick check if text passes safety filters.

        Args:
            text: Text to check

        Returns:
            True if text is safe
        """
        result = self.filter(text)
        return result["is_safe"]

    def validate_only(self, text: str) -> Dict[str, Any]:
        """
        Validate text without filtering.

        Args:
            text: Text to validate

        Returns:
            Validation result dictionary
        """
        return self._validate_text(text)

    def _validate_text(self, text: str) -> Dict[str, Any]:
        """
        Validate text structure and format.

        Args:
            text: Text to validate

        Returns:
            Validation result with valid status and issues
        """
        issues = []

        # Check length bounds
        if len(text) > VALIDATION_RULES["max_length"]:
            issues.append(f"Text exceeds maximum length of {VALIDATION_RULES['max_length']}")

        if len(text) < VALIDATION_RULES["min_length"]:
            issues.append("Text is empty or too short")

        # Check for excessive caps (shouting)
        caps_match = re.search(r'[A-Z]{' + str(VALIDATION_RULES["max_consecutive_caps"]) + ',}', text)
        if caps_match:
            issues.append("Excessive capitalization detected")

        # Check special character ratio
        if len(text) > 0:
            special_chars = len(re.findall(r'[^a-zA-Z0-9\s.,!?\'"-]', text))
            ratio = special_chars / len(text)
            if ratio > VALIDATION_RULES["max_special_chars_ratio"]:
                issues.append("Excessive special characters detected")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "length": len(text)
        }

    def _remove_harmful_patterns(self, text: str) -> Tuple[str, List[str]]:
        """
        Remove harmful patterns from text.

        Args:
            text: Text to process

        Returns:
            Tuple of (filtered text, list of modifications)
        """
        modifications = []
        result = text

        for i, pattern in enumerate(self._compiled_harmful):
            matches = pattern.findall(result)
            if matches:
                modifications.append(f"removed_harmful_pattern_{i}")
                # Replace with a safe placeholder
                result = pattern.sub("[content removed for safety]", result)

        return result, modifications

    def _check_warning_patterns(self, text: str) -> List[str]:
        """
        Check for warning patterns (don't remove, just flag).

        Args:
            text: Text to check

        Returns:
            List of triggered warnings
        """
        warnings = []

        for i, pattern in enumerate(self._compiled_warning):
            if pattern.search(text):
                warnings.append(f"warning_pattern_{i}_detected")

        return warnings

    def _apply_strict_filters(self, text: str) -> Tuple[str, List[str]]:
        """
        Apply additional strict mode filters.

        Args:
            text: Text to process

        Returns:
            Tuple of (filtered text, list of modifications)
        """
        modifications = []
        result = text

        # In strict mode, also soften strong language
        strong_words = {
            "hate": "strongly dislike",
            "destroy": "significantly impact",
            "terrible": "very challenging",
            "horrible": "very difficult",
            "disaster": "significant setback"
        }

        for strong, soft in strong_words.items():
            if strong in result.lower():
                # Case-insensitive replacement
                pattern = re.compile(re.escape(strong), re.IGNORECASE)
                result = pattern.sub(soft, result)
                modifications.append(f"softened_{strong}")

        return result, modifications


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def filter_text(text: str, strict: bool = False) -> Dict[str, Any]:
    """
    Convenience function to filter text.

    Args:
        text: Text to filter
        strict: Whether to use strict mode

    Returns:
        Filter result dictionary
    """
    filters = SafetyFilters(strict_mode=strict)
    return filters.filter(text)


def is_text_safe(text: str) -> bool:
    """
    Convenience function to check text safety.

    Args:
        text: Text to check

    Returns:
        True if safe
    """
    filters = SafetyFilters()
    return filters.is_safe(text)


def get_safe_text(text: str, strict: bool = False) -> str:
    """
    Convenience function to get filtered safe text.

    Args:
        text: Text to filter
        strict: Whether to use strict mode

    Returns:
        Filtered text
    """
    filters = SafetyFilters(strict_mode=strict)
    result = filters.filter(text)
    return result["filtered_text"]


if __name__ == "__main__":
    print("DHA Safety Filters v3.0")
    print("=" * 40)
    print("Minimal guardrails for message safety")
    print(f"Harmful patterns: {len(HARMFUL_PATTERNS)}")
    print(f"Warning patterns: {len(WARNING_PATTERNS)}")
