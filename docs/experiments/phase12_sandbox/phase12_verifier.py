"""
Phase-12: Output Verifier
=========================

This module implements deterministic verification of LLM-generated output.

Architecture:
    LLM Output
        ↓
    Structural Check ─────────┐
        ↓                      │
    Ontological Check ────────┼──> VerificationResult
        ↓                      │
    PPV Alignment Check ──────┤
        ↓                      │
    Content Policy Check ─────┘
        ↓
    PASS or BLOCK

INVARIANT:
    Verification is deterministic.
    Same (context, generation) → identical VerificationResult.

MODE HANDLING:
    - GOVERNED mode has stricter thresholds
    - Same checks run in both modes, but pass/fail thresholds differ
    - GOVERNED may reject what OPEN accepts
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from phase12_schema import (
    GenerationContext,
    OntologicalFamily,
    RawGenerationResult,
    RenderMode,
    VerificationCheck,
    VerificationResult,
    VerificationStatus,
    Verifier,
)


# =============================================================================
# Verification Thresholds
# =============================================================================

@dataclass(frozen=True)
class VerificationThresholds:
    """Thresholds for verification checks."""

    # Structural thresholds
    min_length: int = 10
    max_length: int = 4096
    min_words: int = 3

    # Ontological thresholds
    ontological_score_pass: float = 0.5  # Minimum score to pass

    # PPV alignment thresholds
    ppv_alignment_pass: float = 0.3  # Minimum alignment score

    # Content policy (list of forbidden patterns)
    forbidden_patterns: Tuple[str, ...] = ()


# Default thresholds per mode
OPEN_THRESHOLDS = VerificationThresholds(
    min_length=5,
    max_length=8192,
    min_words=1,
    ontological_score_pass=0.3,
    ppv_alignment_pass=0.2,
    forbidden_patterns=(),
)

GOVERNED_THRESHOLDS = VerificationThresholds(
    min_length=10,
    max_length=4096,
    min_words=3,
    ontological_score_pass=0.5,
    ppv_alignment_pass=0.4,
    forbidden_patterns=(
        r"<script>",
        r"javascript:",
        r"data:text/html",
    ),
)


# =============================================================================
# Ontological Family Markers
# =============================================================================

# Keywords/patterns associated with each family (for presence detection)
FAMILY_MARKERS: Dict[OntologicalFamily, Tuple[str, ...]] = {
    OntologicalFamily.THINKING: (
        "consider", "perhaps", "might", "reflect", "ponder", "wonder",
        "think", "believe", "suppose", "imagine",
    ),
    OntologicalFamily.FORMING: (
        "create", "build", "make", "form", "construct", "shape",
        "design", "craft", "develop", "establish",
    ),
    OntologicalFamily.ACTING: (
        "do", "act", "perform", "execute", "carry out", "implement",
        "take action", "proceed", "move", "engage",
    ),
    OntologicalFamily.TAGGING: (
        "label", "tag", "mark", "identify", "classify", "categorize",
        "name", "designate", "denote", "specify",
    ),
    OntologicalFamily.DIRECTING: (
        "guide", "direct", "lead", "steer", "navigate", "point",
        "aim", "focus", "orient", "channel",
    ),
    OntologicalFamily.REASONING: (
        "because", "therefore", "thus", "hence", "consequently",
        "reason", "logic", "deduce", "infer", "conclude",
    ),
    OntologicalFamily.PURPOSING: (
        "purpose", "goal", "aim", "objective", "intention",
        "intent", "target", "mission", "end", "aspiration",
    ),
    OntologicalFamily.META_OBSERVING: (
        "observe", "notice", "perceive", "see", "watch",
        "witness", "note", "detect", "discern", "recognize",
    ),
    OntologicalFamily.UNIFYING: (
        "unite", "unify", "combine", "merge", "integrate",
        "synthesize", "harmonize", "consolidate", "blend", "fuse",
    ),
    OntologicalFamily.ABSOLVING: (
        "release", "free", "let go", "absolve", "forgive",
        "liberate", "surrender", "accept", "allow", "permit",
    ),
}


# =============================================================================
# PPV-Based Style Markers
# =============================================================================

# Style markers for low/mid/high energy levels
LOW_ENERGY_MARKERS = (
    "quietly", "gently", "softly", "calmly", "peacefully",
    "still", "slowly", "carefully", "delicately",
)

MID_ENERGY_MARKERS = (
    "steadily", "consistently", "regularly", "normally",
    "moderately", "reasonably", "fairly", "adequately",
)

HIGH_ENERGY_MARKERS = (
    "intensely", "powerfully", "strongly", "vigorously",
    "passionately", "fiercely", "dramatically", "boldly",
)


# =============================================================================
# Structural Verification
# =============================================================================

def check_structural(
    text: str,
    thresholds: VerificationThresholds,
) -> VerificationCheck:
    """
    Check structural properties of generated text.

    Checks:
        - Length within bounds
        - Minimum word count
        - Not empty/whitespace only
    """
    # Strip and check for empty
    stripped = text.strip()
    if not stripped:
        return VerificationCheck(
            check_name="structural",
            passed=False,
            score=0.0,
            details="Output is empty or whitespace only",
        )

    # Check length
    length = len(stripped)
    if length < thresholds.min_length:
        return VerificationCheck(
            check_name="structural",
            passed=False,
            score=length / thresholds.min_length,
            details=f"Length {length} below minimum {thresholds.min_length}",
        )

    if length > thresholds.max_length:
        return VerificationCheck(
            check_name="structural",
            passed=False,
            score=thresholds.max_length / length,
            details=f"Length {length} exceeds maximum {thresholds.max_length}",
        )

    # Check word count
    words = stripped.split()
    word_count = len(words)
    if word_count < thresholds.min_words:
        return VerificationCheck(
            check_name="structural",
            passed=False,
            score=word_count / thresholds.min_words,
            details=f"Word count {word_count} below minimum {thresholds.min_words}",
        )

    # Calculate score based on how well it fits bounds
    length_score = 1.0 - abs(length - (thresholds.min_length + thresholds.max_length) / 2) / (
        thresholds.max_length - thresholds.min_length
    )
    length_score = max(0.5, min(1.0, length_score))  # Clamp to [0.5, 1.0]

    return VerificationCheck(
        check_name="structural",
        passed=True,
        score=length_score,
        details=f"Length {length}, words {word_count}",
    )


# =============================================================================
# Ontological Verification
# =============================================================================

def check_ontological(
    text: str,
    family: OntologicalFamily,
    thresholds: VerificationThresholds,
) -> VerificationCheck:
    """
    Check ontological consistency of generated text.

    Verifies that output contains markers appropriate for the target family.
    """
    text_lower = text.lower()
    markers = FAMILY_MARKERS.get(family, ())

    if not markers:
        # Unknown family - neutral pass
        return VerificationCheck(
            check_name="ontological",
            passed=True,
            score=0.5,
            details=f"No markers defined for family {family.value}",
        )

    # Count marker presence
    found_markers = []
    for marker in markers:
        if marker in text_lower:
            found_markers.append(marker)

    # Calculate score
    presence_ratio = len(found_markers) / len(markers)

    # Bonus for having multiple distinct markers
    diversity_bonus = min(0.3, len(found_markers) * 0.05)

    score = min(1.0, presence_ratio + diversity_bonus)

    passed = score >= thresholds.ontological_score_pass

    return VerificationCheck(
        check_name="ontological",
        passed=passed,
        score=score,
        details=f"Found {len(found_markers)}/{len(markers)} markers for {family.value}: {found_markers[:3]}",
    )


# =============================================================================
# PPV Alignment Verification
# =============================================================================

def check_ppv_alignment(
    text: str,
    canonical_signature: str,
    thresholds: VerificationThresholds,
) -> VerificationCheck:
    """
    Check PPV alignment of generated text.

    Verifies that output style matches the PPV conditioning.
    Uses canonical signature to determine expected style profile.
    """
    text_lower = text.lower()

    # Parse signature to determine expected energy profile
    parts = canonical_signature.split("_")
    if len(parts) != 8:
        return VerificationCheck(
            check_name="ppv_alignment",
            passed=True,
            score=0.5,
            details="Invalid signature format - skipping alignment check",
        )

    # Count band representation
    low_count = sum(1 for p in parts if p.startswith("L"))
    mid_count = sum(1 for p in parts if p.startswith("M"))
    high_count = sum(1 for p in parts if p.startswith("H"))

    # Determine dominant band
    if high_count >= low_count and high_count >= mid_count:
        dominant = "HIGH"
        expected_markers = HIGH_ENERGY_MARKERS
    elif low_count >= mid_count:
        dominant = "LOW"
        expected_markers = LOW_ENERGY_MARKERS
    else:
        dominant = "MID"
        expected_markers = MID_ENERGY_MARKERS

    # Check for expected markers
    found = sum(1 for m in expected_markers if m in text_lower)
    expected_score = found / len(expected_markers) if expected_markers else 0

    # Check for misaligned markers (opposing energy level)
    if dominant == "HIGH":
        opposing_markers = LOW_ENERGY_MARKERS
    elif dominant == "LOW":
        opposing_markers = HIGH_ENERGY_MARKERS
    else:
        opposing_markers = ()

    misaligned = sum(1 for m in opposing_markers if m in text_lower)
    penalty = misaligned * 0.1

    # Calculate final score
    score = max(0.0, min(1.0, expected_score * 0.7 + 0.3 - penalty))

    passed = score >= thresholds.ppv_alignment_pass

    return VerificationCheck(
        check_name="ppv_alignment",
        passed=passed,
        score=score,
        details=f"Dominant band: {dominant}, found {found} markers, {misaligned} misaligned",
    )


# =============================================================================
# Content Policy Verification
# =============================================================================

def check_content_policy(
    text: str,
    thresholds: VerificationThresholds,
) -> VerificationCheck:
    """
    Check content policy compliance.

    Ensures output doesn't contain forbidden patterns.
    """
    if not thresholds.forbidden_patterns:
        return VerificationCheck(
            check_name="content_policy",
            passed=True,
            score=1.0,
            details="No forbidden patterns configured",
        )

    violations = []
    for pattern in thresholds.forbidden_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            violations.append(pattern)

    if violations:
        return VerificationCheck(
            check_name="content_policy",
            passed=False,
            score=0.0,
            details=f"Found forbidden patterns: {violations}",
        )

    return VerificationCheck(
        check_name="content_policy",
        passed=True,
        score=1.0,
        details="No policy violations",
    )


# =============================================================================
# Phase12 Verifier Implementation
# =============================================================================

@dataclass
class Phase12Verifier:
    """
    Deterministic output verifier for Phase-12.

    INVARIANT: Same inputs → same verification result.

    Verification layers:
        1. Structural - length, format
        2. Ontological - family consistency
        3. PPV Alignment - style consistency
        4. Content Policy - forbidden patterns
    """

    open_thresholds: VerificationThresholds = field(
        default_factory=lambda: OPEN_THRESHOLDS
    )
    governed_thresholds: VerificationThresholds = field(
        default_factory=lambda: GOVERNED_THRESHOLDS
    )

    def verify(
        self,
        context: GenerationContext,
        generation: RawGenerationResult,
    ) -> VerificationResult:
        """
        Verify generated output against context requirements.

        Args:
            context: The generation context (includes mode, PPV, ontological info)
            generation: The raw generation result from LLM

        Returns:
            VerificationResult with pass/fail status and detailed checks
        """
        # Select thresholds based on mode
        thresholds = (
            self.governed_thresholds
            if context.mode == RenderMode.GOVERNED
            else self.open_thresholds
        )

        # Run all checks
        checks: List[VerificationCheck] = []

        # 1. Structural check
        structural = check_structural(generation.text, thresholds)
        checks.append(structural)

        # 2. Ontological check
        ontological = check_ontological(
            generation.text,
            context.ontological.family,
            thresholds,
        )
        checks.append(ontological)

        # 3. PPV alignment check
        ppv_alignment = check_ppv_alignment(
            generation.text,
            context.ppv_signal.canonical_signature,
            thresholds,
        )
        checks.append(ppv_alignment)

        # 4. Content policy check
        content_policy = check_content_policy(generation.text, thresholds)
        checks.append(content_policy)

        # Calculate aggregate scores
        structural_score = structural.score
        ontological_score = ontological.score
        ppv_alignment_score = ppv_alignment.score

        # Determine overall status
        if not structural.passed:
            status = VerificationStatus.FAILED_STRUCTURAL
        elif not ontological.passed:
            status = VerificationStatus.FAILED_ONTOLOGICAL
        elif not ppv_alignment.passed:
            status = VerificationStatus.FAILED_PPV_ALIGNMENT
        elif not content_policy.passed:
            status = VerificationStatus.FAILED_CONTENT_POLICY
        else:
            status = VerificationStatus.PASSED

        # Calculate mode-specific allowance
        # For OPEN: just check structural and content policy
        allowed_in_open = (
            check_structural(generation.text, self.open_thresholds).passed
            and check_content_policy(generation.text, self.open_thresholds).passed
        )

        # For GOVERNED: all checks must pass
        allowed_in_governed = status == VerificationStatus.PASSED

        return VerificationResult(
            status=status,
            checks=tuple(checks),
            structural_score=structural_score,
            ontological_score=ontological_score,
            ppv_alignment_score=ppv_alignment_score,
            allowed_in_open=allowed_in_open,
            allowed_in_governed=allowed_in_governed,
        )

    def verify_hash(
        self,
        context: GenerationContext,
        generation: RawGenerationResult,
    ) -> str:
        """
        Compute deterministic hash of verification inputs.

        Used for audit trail and reproducibility verification.
        """
        canonical = (
            f"context:{context.context_hash()}|"
            f"gen:{generation.output_hash()}|"
            f"mode:{context.mode.value}"
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# =============================================================================
# Factory Functions
# =============================================================================

def create_default_verifier() -> Phase12Verifier:
    """Create verifier with default thresholds."""
    return Phase12Verifier()


def create_strict_verifier() -> Phase12Verifier:
    """Create verifier with stricter thresholds for both modes."""
    return Phase12Verifier(
        open_thresholds=VerificationThresholds(
            min_length=10,
            max_length=4096,
            min_words=3,
            ontological_score_pass=0.4,
            ppv_alignment_pass=0.3,
            forbidden_patterns=(r"<script>", r"javascript:"),
        ),
        governed_thresholds=VerificationThresholds(
            min_length=20,
            max_length=2048,
            min_words=5,
            ontological_score_pass=0.6,
            ppv_alignment_pass=0.5,
            forbidden_patterns=(
                r"<script>",
                r"javascript:",
                r"data:text/html",
                r"onclick=",
                r"onerror=",
            ),
        ),
    )


def create_lenient_verifier() -> Phase12Verifier:
    """Create verifier with lenient thresholds."""
    return Phase12Verifier(
        open_thresholds=VerificationThresholds(
            min_length=1,
            max_length=16384,
            min_words=1,
            ontological_score_pass=0.1,
            ppv_alignment_pass=0.1,
            forbidden_patterns=(),
        ),
        governed_thresholds=VerificationThresholds(
            min_length=5,
            max_length=8192,
            min_words=2,
            ontological_score_pass=0.3,
            ppv_alignment_pass=0.2,
            forbidden_patterns=(r"<script>",),
        ),
    )


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Thresholds
    "VerificationThresholds",
    "OPEN_THRESHOLDS",
    "GOVERNED_THRESHOLDS",
    # Markers
    "FAMILY_MARKERS",
    "LOW_ENERGY_MARKERS",
    "MID_ENERGY_MARKERS",
    "HIGH_ENERGY_MARKERS",
    # Check functions
    "check_structural",
    "check_ontological",
    "check_ppv_alignment",
    "check_content_policy",
    # Verifier
    "Phase12Verifier",
    # Factory functions
    "create_default_verifier",
    "create_strict_verifier",
    "create_lenient_verifier",
]
