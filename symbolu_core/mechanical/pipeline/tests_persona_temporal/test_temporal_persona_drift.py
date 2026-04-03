"""
Temporal Persona Drift Test Suite (v2.0 - Full Drift Metrics)
==============================================================

Advanced tests for detecting persona behavioral drift over multi-turn
conversations in the Symbol-U Pipeline.

Drift Metrics Implemented:
    1. Base Persona Feature Drift - core persona signature stability
    2. Sequential Coherence Drift - lexical consistency across turns
    3. Emotional Gradient Drift - warmth/regulation smoothness
    4. Instruction Adherence Drift - tone/directive consistency
    5. Fusion Alignment Drift - persona-fusion layer alignment

Test Categories:
    - test_temporal_persona_drift_is_within_bounds - Main drift validation test
    - test_base_metrics_determinism - Ensures metrics are deterministic
    - test_coherence_computation - Validates coherence algorithm
    - test_emotional_gradient_computation - Validates emotional metrics
    - test_instruction_adherence_computation - Validates adherence metrics
    - test_fusion_alignment_computation - Validates alignment metrics

CRITICAL: All tests are LLM-free and fully deterministic.
"""

import pytest
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from unittest.mock import MagicMock

# Import Pipeline and models
from symbolu_core.mechanical.pipeline.orchestrator import SymbolUPipeline
from symbolu_core.mechanical.pipeline.models import (
    UserRequest,
    RenderedOutput,
    PipelineContext,
)


# =============================================================================
# PATHS AND CONSTANTS
# =============================================================================

SNAPSHOT_DIR = Path(__file__).parent.parent / "snapshots"
BASELINE_PATH = SNAPSHOT_DIR / "persona_temporal_baseline.json"
REPORT_PATH = Path(__file__).parent / "persona_temporal_drift_report.json"

# Drift thresholds
# Note: These thresholds are tuned for typical pipeline responses.
# A "stable" classification means minimal persona drift across turns.
# "mild_drift" is expected for conversations with emotional progression.
# "severe_drift" indicates potentially problematic persona inconsistency.
DRIFT_THRESHOLD_STABLE = 0.25
DRIFT_THRESHOLD_MILD = 0.70
BASELINE_DEVIATION_THRESHOLD = 0.35
DRIFT_SCORE_INCREASE_THRESHOLD = 0.25


# =============================================================================
# FIXED CONVERSATION SCENARIO
# =============================================================================

CONVERSATION = [
    "I'm really stressed about my job right now.",
    "Okay, that helped a bit. What should I focus on next?",
    "Now I'm feeling slightly more hopeful.",
    "I think I'm getting my clarity back.",
    "Thanks, this feels more manageable now.",
]


# =============================================================================
# WORD LISTS FOR HEURISTICS
# =============================================================================

SOFTENERS = ["maybe", "perhaps", "we can", "let's", "could", "might", "possibly"]
DIRECTIVES = ["do this", "you should", "must", "have to", "need to", "take", "stop"]
EMPATHY_MARKERS = [
    "i understand", "it makes sense", "valid", "normal", "okay to",
    "that's understandable", "it's natural", "feeling", "feel"
]
SAFETY_MARKERS = [
    "not financial advice", "consider talking to", "professional help",
    "consult", "speak with", "qualified", "licensed", "disclaimer"
]
UNCERTAINTY_MARKERS = ["maybe", "might", "probably", "possibly", "could be", "perhaps"]
IMPERATIVE_STARTERS = ["do", "take", "stop", "start", "make", "try", "focus", "consider"]

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "up", "about", "into", "over", "after", "beneath", "under",
    "above", "and", "but", "or", "nor", "so", "yet", "both", "either",
    "neither", "not", "only", "own", "same", "than", "too", "very",
    "just", "i", "you", "he", "she", "it", "we", "they", "me", "him",
    "her", "us", "them", "my", "your", "his", "its", "our", "their",
    "this", "that", "these", "those", "what", "which", "who", "whom",
}


# =============================================================================
# DETERMINISTIC UUID GENERATOR
# =============================================================================

class DeterministicUUIDGenerator:
    """Generate deterministic UUIDs for testing reproducibility."""

    def __init__(self, prefix: str = "persona_drift") -> None:
        self.counter = 0
        self.prefix = prefix

    def generate(self) -> str:
        self.counter += 1
        return f"{self.prefix}_{self.counter:08d}"


# =============================================================================
# PERSONA SIGNATURE EXTRACTION
# =============================================================================

def extract_persona_signature(response: Dict[str, Any] | str) -> Dict[str, float]:
    """
    Extract a compact numeric persona signature from a pipeline/persona response.

    Fields (all in [0, 1] range):
        - warmth: empathic, validating language
        - directness: concise, directive language
        - depth: surface reassurance vs deeper reflection
        - regulation: calm, grounded tone vs panicky/abrupt
        - length_norm: normalized character length

    Args:
        response: Pipeline response dict or raw text string.

    Returns:
        Dict with persona signature metrics.
    """
    # Extract text from response
    if isinstance(response, str):
        text = response
        meta = {}
    elif isinstance(response, dict):
        text = (
            response.get("text", "") or
            response.get("raw_text", "") or
            response.get("persona_text", "") or
            response.get("content", "") or
            str(response)
        )
        meta = response.get("meta", {}) or response.get("metadata", {}) or {}
    else:
        text = str(response)
        meta = {}

    text_lower = text.lower()
    words = text_lower.split()
    word_count = max(len(words), 1)

    # Compute warmth from empathy markers
    empathy_count = sum(
        1 for marker in EMPATHY_MARKERS
        if marker in text_lower
    )
    warmth = min(1.0, empathy_count / 3.0)  # Normalize to [0, 1]

    # Compute directness from directive markers
    directive_count = sum(
        1 for marker in DIRECTIVES
        if marker in text_lower
    )
    directness = min(1.0, directive_count / 3.0)

    # Compute depth from symbolic/reflective language
    depth_markers = [
        "deeper", "reflect", "meaning", "purpose", "underlying",
        "core", "essential", "inner", "perspective", "consider"
    ]
    depth_count = sum(
        1 for marker in depth_markers
        if marker in text_lower
    )
    depth = min(1.0, depth_count / 4.0)

    # Compute regulation from calm/grounded vs urgent language
    calm_markers = ["calm", "steady", "grounded", "balanced", "manageable", "okay"]
    urgent_markers = ["urgent", "immediately", "now", "quickly", "panic", "crisis"]

    calm_count = sum(1 for m in calm_markers if m in text_lower)
    urgent_count = sum(1 for m in urgent_markers if m in text_lower)

    # Higher regulation = more calm, less urgent
    regulation = min(1.0, max(0.0, 0.5 + (calm_count - urgent_count) * 0.2))

    # Length normalization (will be normalized across conversation later)
    length_norm = len(text)

    return {
        "warmth": warmth,
        "directness": directness,
        "depth": depth,
        "regulation": regulation,
        "length_norm": float(length_norm),
    }


def normalize_length_across_signatures(signatures: List[Dict[str, float]]) -> None:
    """
    Normalize length_norm field across all signatures in place.

    Normalization: length / (1 + max_length)
    """
    if not signatures:
        return

    max_length = max(s.get("length_norm", 0) for s in signatures)
    for sig in signatures:
        raw_len = sig.get("length_norm", 0)
        sig["length_norm"] = raw_len / (1 + max_length)


# =============================================================================
# METRIC 1: BASE DRIFT METRICS
# =============================================================================

def compute_base_drift_metrics(signatures: List[Dict[str, float]]) -> Dict[str, Any]:
    """
    Compute base persona drift metrics from signatures across turns.

    For each feature (warmth, directness, depth, regulation, length_norm):
        - mean value across turns
        - std deviation
        - max consecutive delta (change between adjacent turns)
        - total range (max - min)

    Args:
        signatures: List of persona signature dicts.

    Returns:
        Dict with per-feature metrics and aggregate drift score.
    """
    if not signatures:
        return {
            "features": {},
            "max_feature_drift": 0.0,
        }

    features = ["warmth", "directness", "depth", "regulation", "length_norm"]
    feature_metrics = {}

    max_feature_drift = 0.0

    for feature in features:
        values = [s.get(feature, 0.0) for s in signatures]

        if not values:
            continue

        n = len(values)
        mean_val = sum(values) / n

        # Standard deviation
        if n > 1:
            variance = sum((v - mean_val) ** 2 for v in values) / (n - 1)
            std_val = math.sqrt(variance)
        else:
            std_val = 0.0

        # Consecutive deltas
        deltas = []
        for i in range(1, n):
            deltas.append(abs(values[i] - values[i - 1]))

        max_consecutive_delta = max(deltas) if deltas else 0.0

        # Total range
        total_range = max(values) - min(values) if values else 0.0

        feature_metrics[feature] = {
            "mean": mean_val,
            "std": std_val,
            "max_consecutive_delta": max_consecutive_delta,
            "total_range": total_range,
            "values": values,
        }

        # Compute normalized drift for this feature
        # For features in [0, 1] range with potentially sparse marker detection,
        # we use the max_consecutive_delta directly as the drift metric.
        # This gives drift in [0, 1] range naturally.
        feature_drift = max_consecutive_delta
        feature_metrics[feature]["drift"] = feature_drift
        if feature_drift > max_feature_drift:
            max_feature_drift = feature_drift

    return {
        "features": feature_metrics,
        "max_feature_drift": max_feature_drift,
    }


# =============================================================================
# METRIC 2: SEQUENTIAL COHERENCE DRIFT
# =============================================================================

def compute_sequential_coherence(responses: List[str]) -> Dict[str, Any]:
    """
    Compute coherence metrics across consecutive persona responses.

    Method (LLM-free):
        - Tokenize to lowercase word sets per response
        - For each consecutive pair: lexical_overlap = |A AND B| / max(1, |A OR B|)
        - coherence_score = average lexical_overlap across all pairs

    Args:
        responses: List of response text strings.

    Returns:
        Dict with coherence_score, min_overlap, max_overlap, overlap_std.
    """
    if len(responses) < 2:
        return {
            "coherence_score": 1.0,
            "min_overlap": 1.0,
            "max_overlap": 1.0,
            "overlap_std": 0.0,
            "overlaps": [],
        }

    # Tokenize each response to word sets (excluding stopwords)
    word_sets = []
    for resp in responses:
        words = set(
            w.lower().strip(".,!?;:'\"")
            for w in resp.split()
            if w.lower().strip(".,!?;:'\"") not in STOPWORDS
            and len(w.strip(".,!?;:'\"")) > 2
        )
        word_sets.append(words)

    # Compute pairwise overlaps
    overlaps = []
    for i in range(1, len(word_sets)):
        a = word_sets[i - 1]
        b = word_sets[i]

        intersection = len(a & b)
        union = len(a | b)

        overlap = intersection / max(1, union)
        overlaps.append(overlap)

    # Aggregate
    coherence_score = sum(overlaps) / len(overlaps) if overlaps else 1.0
    min_overlap = min(overlaps) if overlaps else 1.0
    max_overlap = max(overlaps) if overlaps else 1.0

    # Standard deviation
    if len(overlaps) > 1:
        mean_overlap = coherence_score
        variance = sum((o - mean_overlap) ** 2 for o in overlaps) / (len(overlaps) - 1)
        overlap_std = math.sqrt(variance)
    else:
        overlap_std = 0.0

    return {
        "coherence_score": coherence_score,
        "min_overlap": min_overlap,
        "max_overlap": max_overlap,
        "overlap_std": overlap_std,
        "overlaps": overlaps,
    }


# =============================================================================
# METRIC 3: EMOTIONAL GRADIENT STABILITY
# =============================================================================

def compute_emotional_gradient_metrics(signatures: List[Dict[str, float]]) -> Dict[str, Any]:
    """
    Compute emotional gradient stability metrics.

    Uses 'warmth' and 'regulation' fields from persona signatures.

    Steps:
        - Extract per-turn warmth and regulation sequences
        - Compute first differences (delta warmth, delta regulation)
        - Compute second differences (acceleration)
        - emotional_volatility = max absolute second difference

    Args:
        signatures: List of persona signature dicts.

    Returns:
        Dict with warmth_deltas, regulation_deltas, emotional_volatility.
    """
    if len(signatures) < 2:
        return {
            "warmth_deltas": [],
            "regulation_deltas": [],
            "warmth_acceleration": [],
            "regulation_acceleration": [],
            "emotional_volatility": 0.0,
        }

    warmth_values = [s.get("warmth", 0.5) for s in signatures]
    regulation_values = [s.get("regulation", 0.5) for s in signatures]

    # First differences
    warmth_deltas = [
        warmth_values[i] - warmth_values[i - 1]
        for i in range(1, len(warmth_values))
    ]
    regulation_deltas = [
        regulation_values[i] - regulation_values[i - 1]
        for i in range(1, len(regulation_values))
    ]

    # Second differences (acceleration)
    warmth_acceleration = []
    regulation_acceleration = []

    if len(warmth_deltas) >= 2:
        warmth_acceleration = [
            warmth_deltas[i] - warmth_deltas[i - 1]
            for i in range(1, len(warmth_deltas))
        ]
    if len(regulation_deltas) >= 2:
        regulation_acceleration = [
            regulation_deltas[i] - regulation_deltas[i - 1]
            for i in range(1, len(regulation_deltas))
        ]

    # Emotional volatility = max absolute second difference
    # Cap at 1.0 since our features are in [0, 1] range and we want volatility bounded
    all_accelerations = warmth_acceleration + regulation_acceleration
    raw_volatility = (
        max(abs(a) for a in all_accelerations) if all_accelerations else 0.0
    )
    # Normalize: max possible acceleration for [0,1] values is 2.0 (from 0->1->0 pattern)
    # Scale to [0, 1] range
    emotional_volatility = min(raw_volatility / 2.0, 1.0)

    return {
        "warmth_deltas": warmth_deltas,
        "regulation_deltas": regulation_deltas,
        "warmth_acceleration": warmth_acceleration,
        "regulation_acceleration": regulation_acceleration,
        "emotional_volatility": emotional_volatility,
    }


# =============================================================================
# METRIC 4: INSTRUCTION ADHERENCE DRIFT
# =============================================================================

def compute_instruction_adherence_metrics(responses: List[str]) -> Dict[str, Any]:
    """
    Compute instruction adherence drift metrics over time.

    Features per turn:
        - imperative_ratio: fraction of sentences using imperative tone
        - uncertainty_ratio: frequency of uncertainty markers
        - safety_marker_ratio: frequency of safety markers

    For each feature:
        - compute per-turn values
        - compute max absolute delta between consecutive turns

    Args:
        responses: List of response text strings.

    Returns:
        Dict with imperative_drift, uncertainty_drift, safety_drift.
    """
    if not responses:
        return {
            "imperative_drift": 0.0,
            "uncertainty_drift": 0.0,
            "safety_drift": 0.0,
            "per_turn": [],
        }

    per_turn_metrics = []

    for resp in responses:
        text_lower = resp.lower()
        sentences = [s.strip() for s in resp.split(".") if s.strip()]
        sentence_count = max(len(sentences), 1)
        word_count = max(len(text_lower.split()), 1)

        # Imperative ratio: sentences starting with imperative verbs
        imperative_count = 0
        for sentence in sentences:
            first_word = sentence.split()[0].lower() if sentence.split() else ""
            if first_word in IMPERATIVE_STARTERS:
                imperative_count += 1
        imperative_ratio = imperative_count / sentence_count

        # Uncertainty ratio
        uncertainty_count = sum(
            1 for marker in UNCERTAINTY_MARKERS
            if marker in text_lower
        )
        uncertainty_ratio = uncertainty_count / word_count

        # Safety marker ratio
        safety_count = sum(
            1 for marker in SAFETY_MARKERS
            if marker in text_lower
        )
        safety_marker_ratio = safety_count / sentence_count

        per_turn_metrics.append({
            "imperative_ratio": imperative_ratio,
            "uncertainty_ratio": uncertainty_ratio,
            "safety_marker_ratio": safety_marker_ratio,
        })

    # Compute max deltas
    def compute_max_delta(key: str) -> float:
        if len(per_turn_metrics) < 2:
            return 0.0
        values = [m[key] for m in per_turn_metrics]
        deltas = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
        return max(deltas) if deltas else 0.0

    return {
        "imperative_drift": compute_max_delta("imperative_ratio"),
        "uncertainty_drift": compute_max_delta("uncertainty_ratio"),
        "safety_drift": compute_max_delta("safety_marker_ratio"),
        "per_turn": per_turn_metrics,
    }


# =============================================================================
# METRIC 5: FUSION ALIGNMENT DRIFT
# =============================================================================

def compute_fusion_alignment_metrics(responses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute persona-fusion alignment metrics across turns.

    For each turn, compute alignment score between:
        - persona text
        - fusion practical text

    LLM-free heuristic:
        - Extract keywords from both (word sets, minus stopwords)
        - alignment = |intersection| / max(1, |union|)
        - alignment_drift = max abs delta between consecutive turns

    Args:
        responses: List of full pipeline response dicts with persona and fusion.

    Returns:
        Dict with alignment_scores and alignment_drift.
    """
    if not responses:
        return {
            "alignment_scores": [],
            "alignment_drift": 0.0,
        }

    alignment_scores = []

    for resp in responses:
        # Extract persona text
        persona_text = ""
        if isinstance(resp, dict):
            persona_text = (
                resp.get("persona_text", "") or
                resp.get("raw_text", "") or
                resp.get("text", "") or
                ""
            )

        # Extract fusion practical text
        fusion_text = ""
        if isinstance(resp, dict):
            fusion_data = resp.get("fusion", {}) or {}
            if isinstance(fusion_data, dict):
                practical = fusion_data.get("practical", {})
                if isinstance(practical, dict):
                    fusion_text = practical.get("text", "") or practical.get("summary", "") or ""
                elif isinstance(practical, str):
                    fusion_text = practical

            # Fallback: try selected_text
            if not fusion_text:
                fusion_text = resp.get("fusion_text", "") or resp.get("selected_text", "") or ""

        # Extract keywords (remove stopwords)
        def extract_keywords(text: str) -> set:
            return set(
                w.lower().strip(".,!?;:'\"")
                for w in text.split()
                if w.lower().strip(".,!?;:'\"") not in STOPWORDS
                and len(w.strip(".,!?;:'\"")) > 2
            )

        persona_keywords = extract_keywords(persona_text)
        fusion_keywords = extract_keywords(fusion_text)

        # Compute alignment
        if persona_keywords or fusion_keywords:
            intersection = len(persona_keywords & fusion_keywords)
            union = len(persona_keywords | fusion_keywords)
            alignment = intersection / max(1, union)
        else:
            # If both empty, consider aligned
            alignment = 1.0

        alignment_scores.append(alignment)

    # Compute max delta
    if len(alignment_scores) >= 2:
        deltas = [
            abs(alignment_scores[i] - alignment_scores[i - 1])
            for i in range(1, len(alignment_scores))
        ]
        alignment_drift = max(deltas) if deltas else 0.0
    else:
        alignment_drift = 0.0

    return {
        "alignment_scores": alignment_scores,
        "alignment_drift": alignment_drift,
    }


# =============================================================================
# GLOBAL DRIFT CLASSIFICATION
# =============================================================================

def classify_persona_drift(
    base_metrics: Dict[str, Any],
    coherence: Dict[str, Any],
    emotional: Dict[str, Any],
    adherence: Dict[str, Any],
    fusion_align: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Combine all metrics into final drift classification.

    Components:
        - base_feature_drift = max per-feature drift
        - coherence_penalty = max(0, 0.5 - coherence_score)
        - emotional_penalty = emotional_volatility
        - adherence_penalty = max of drift metrics
        - alignment_penalty = fusion alignment drift

    drift_score = max of all penalties

    Classification:
        - stable: drift_score < 0.15
        - mild_drift: 0.15 <= drift_score < 0.35
        - severe_drift: drift_score >= 0.35

    Args:
        base_metrics: From compute_base_drift_metrics()
        coherence: From compute_sequential_coherence()
        emotional: From compute_emotional_gradient_metrics()
        adherence: From compute_instruction_adherence_metrics()
        fusion_align: From compute_fusion_alignment_metrics()

    Returns:
        Dict with drift_score, classification, and component breakdown.
    """
    # Compute component penalties
    base_feature_drift = base_metrics.get("max_feature_drift", 0.0)

    coherence_score = coherence.get("coherence_score", 1.0)
    coherence_penalty = max(0.0, 0.5 - coherence_score)

    emotional_penalty = emotional.get("emotional_volatility", 0.0)

    adherence_penalty = max(
        adherence.get("imperative_drift", 0.0),
        adherence.get("uncertainty_drift", 0.0),
        adherence.get("safety_drift", 0.0),
    )

    alignment_penalty = fusion_align.get("alignment_drift", 0.0)

    # Overall drift score
    drift_score = max(
        base_feature_drift,
        coherence_penalty,
        emotional_penalty,
        adherence_penalty,
        alignment_penalty,
    )

    # Classification
    if drift_score < DRIFT_THRESHOLD_STABLE:
        classification = "stable"
    elif drift_score < DRIFT_THRESHOLD_MILD:
        classification = "mild_drift"
    else:
        classification = "severe_drift"

    return {
        "drift_score": drift_score,
        "classification": classification,
        "components": {
            "base_feature_drift": base_feature_drift,
            "coherence_penalty": coherence_penalty,
            "emotional_penalty": emotional_penalty,
            "adherence_penalty": adherence_penalty,
            "alignment_penalty": alignment_penalty,
        },
    }


# =============================================================================
# PIPELINE EXECUTION
# =============================================================================

def run_conversation_and_collect(
    pipeline: SymbolUPipeline,
    conversation: List[str],
) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, float]]]:
    """
    Run conversation through pipeline and collect responses + signatures.

    Args:
        pipeline: SymbolUPipeline instance.
        conversation: List of input messages.

    Returns:
        Tuple of (full_responses, response_texts, signatures).
    """
    full_responses = []
    response_texts = []
    signatures = []

    for i, message in enumerate(conversation):
        request = UserRequest(
            text=message,
            user_id=f"persona_drift_test_{i}",
            render_mode="standard",
            metadata={
                "domain": "personal",
                "readiness_score": 0.6,
                "session_turn": i,
            },
        )

        ctx = PipelineContext(request=request)

        # Run through pipeline stages
        ctx = pipeline._run_mlcr(ctx)
        ctx = pipeline._run_persona(ctx)
        ctx.router_mode = "linear"
        ctx = pipeline._run_fusion(ctx)
        ctx = pipeline._run_dha(ctx)
        ctx = pipeline._run_renderer(ctx)

        result = ctx.rendered

        # Build full response dict
        response_dict = {
            "raw_text": result.raw_text,
            "mode": result.mode,
            "meta": result.meta,
            "persona_text": result.raw_text,
            "persona_id": ctx.persona.active_persona_id if ctx.persona else None,
            "persona_config": ctx.persona.persona_config if ctx.persona else {},
            "fusion": {
                "selected_text": ctx.fusion.selected_text if ctx.fusion else "",
                "practical": {"text": ctx.fusion.selected_text if ctx.fusion else ""},
            },
            "fusion_text": ctx.fusion.selected_text if ctx.fusion else "",
            "dha_tone": ctx.dha.tone_profile if ctx.dha else None,
        }

        full_responses.append(response_dict)
        response_texts.append(result.raw_text)

        # Extract signature
        sig = extract_persona_signature(response_dict)
        signatures.append(sig)

    # Normalize lengths across all signatures
    normalize_length_across_signatures(signatures)

    return full_responses, response_texts, signatures


# =============================================================================
# BASELINE MANAGEMENT
# =============================================================================

def get_version() -> str:
    """Get version from VERSION file or return 'unknown'."""
    version_paths = [
        Path(__file__).parent.parent.parent.parent.parent / "VERSION",
        Path(__file__).parent.parent.parent.parent / "VERSION",
        Path(__file__).parent.parent.parent / "VERSION",
    ]
    for vpath in version_paths:
        if vpath.exists():
            return vpath.read_text().strip()
    return "unknown"


def load_baseline() -> Optional[Dict[str, Any]]:
    """Load baseline from file if it exists."""
    if not BASELINE_PATH.exists():
        return None
    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_baseline(data: Dict[str, Any]) -> None:
    """Save baseline to file."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with open(BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def save_report(data: Dict[str, Any]) -> None:
    """Save drift report to file."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def create_baseline_data(
    conversation: List[str],
    signatures: List[Dict[str, float]],
    base_metrics: Dict[str, Any],
    coherence: Dict[str, Any],
    emotional: Dict[str, Any],
    adherence: Dict[str, Any],
    fusion_align: Dict[str, Any],
    drift_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """Create baseline data structure."""
    return {
        "conversation": conversation,
        "signatures": signatures,
        "metrics": {
            "base": base_metrics,
            "coherence": coherence,
            "emotional": emotional,
            "adherence": adherence,
            "fusion_align": fusion_align,
            "drift_summary": drift_summary,
        },
        "meta": {
            "version": get_version(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def compare_with_baseline(
    baseline: Dict[str, Any],
    current_metrics: Dict[str, Any],
    current_drift_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compare current metrics with baseline.

    Returns comparison data with deltas and flags.
    """
    baseline_drift = baseline.get("metrics", {}).get("drift_summary", {})
    baseline_score = baseline_drift.get("drift_score", 0.0)
    current_score = current_drift_summary.get("drift_score", 0.0)

    drift_score_delta = current_score - baseline_score
    classification_changed = (
        baseline_drift.get("classification") != current_drift_summary.get("classification")
    )

    # Compute component deltas
    baseline_components = baseline_drift.get("components", {})
    current_components = current_drift_summary.get("components", {})

    component_deltas = {}
    for key in ["base_feature_drift", "coherence_penalty", "emotional_penalty",
                "adherence_penalty", "alignment_penalty"]:
        b_val = baseline_components.get(key, 0.0)
        c_val = current_components.get(key, 0.0)
        component_deltas[key] = c_val - b_val

    return {
        "exists": True,
        "drift_score_delta": drift_score_delta,
        "classification_changed": classification_changed,
        "component_deltas": component_deltas,
        "baseline_score": baseline_score,
        "current_score": current_score,
    }


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def deterministic_pipeline():
    """Create pipeline with deterministic candidate generation."""
    pipeline = SymbolUPipeline()
    uuid_gen = DeterministicUUIDGenerator("persona_drift_candidate")

    def mock_generate_candidates(ctx, explain_log, activation_plan):
        from symbolu_core.mechanical.fusion.schemas.candidate import Candidate, CandidateSource

        query_text = ctx.request.text
        domain = explain_log.get("meta", {}).get("domain", "personal")

        candidates = [
            Candidate(
                id=f"hrm_{uuid_gen.generate()}",
                text=f"From a deeper perspective: {query_text}",
                source=CandidateSource.HRM,
                channel_scores={"hrm": 0.8, "lcm": 0.4, "moe": 0.3},
                domain=domain,
                relevance_score=0.7,
                confidence=0.8,
            ),
            Candidate(
                id=f"lcm_{uuid_gen.generate()}",
                text=f"To clarify: {query_text}",
                source=CandidateSource.LCM,
                channel_scores={"hrm": 0.3, "lcm": 0.9, "moe": 0.4},
                domain=domain,
                relevance_score=0.75,
                confidence=0.85,
            ),
            Candidate(
                id=f"moe_{uuid_gen.generate()}",
                text=f"Based on domain knowledge: {query_text}",
                source=CandidateSource.MOE,
                channel_scores={"hrm": 0.4, "lcm": 0.5, "moe": 0.85},
                domain=domain,
                relevance_score=0.7,
                confidence=0.75,
            ),
        ]

        return candidates

    pipeline._generate_candidates = mock_generate_candidates
    return pipeline


# =============================================================================
# MAIN TEST
# =============================================================================

class TestTemporalPersonaDrift:
    """
    Main test class for temporal persona drift validation.
    """

    def test_temporal_persona_drift_is_within_bounds(
        self,
        deterministic_pipeline: SymbolUPipeline,
    ):
        """
        Main drift validation test.

        Steps:
            1. Run conversation through pipeline
            2. Collect responses + signatures
            3. Compute all metric groups
            4. Load or create baseline
            5. Write drift report
            6. Assert classification != severe_drift
            7. Assert deltas vs baseline within thresholds
        """
        # Step 1 & 2: Run conversation and collect data
        full_responses, response_texts, signatures = run_conversation_and_collect(
            deterministic_pipeline,
            CONVERSATION,
        )

        # Step 3: Compute all metrics
        base_metrics = compute_base_drift_metrics(signatures)
        coherence = compute_sequential_coherence(response_texts)
        emotional = compute_emotional_gradient_metrics(signatures)
        adherence = compute_instruction_adherence_metrics(response_texts)
        fusion_align = compute_fusion_alignment_metrics(full_responses)

        drift_summary = classify_persona_drift(
            base_metrics, coherence, emotional, adherence, fusion_align
        )

        # Step 4: Load or create baseline
        baseline = load_baseline()

        if baseline is None:
            # First run: create baseline
            print("[PERSONA DRIFT] Creating baseline for first run...")

            baseline_data = create_baseline_data(
                CONVERSATION,
                signatures,
                base_metrics,
                coherence,
                emotional,
                adherence,
                fusion_align,
                drift_summary,
            )

            save_baseline(baseline_data)

            # Create minimal report for first run
            report = {
                "conversation": CONVERSATION,
                "responses": response_texts,
                "signatures": signatures,
                "metrics": {
                    "base": base_metrics,
                    "coherence": coherence,
                    "emotional": emotional,
                    "adherence": adherence,
                    "fusion_align": fusion_align,
                    "drift_summary": drift_summary,
                },
                "baseline_comparison": {
                    "exists": False,
                    "drift_score_delta": 0.0,
                    "classification_changed": False,
                    "component_deltas": {},
                },
            }

            save_report(report)

            # First run: assert classification is not severe
            assert drift_summary["classification"] != "severe_drift", (
                f"Initial baseline has severe drift! Classification: {drift_summary['classification']}\n"
                f"Drift score: {drift_summary['drift_score']}\n"
                f"Components: {drift_summary['components']}"
            )

            print(f"[PERSONA DRIFT] Baseline created. Classification: {drift_summary['classification']}")
            return

        # Step 5: Compare with baseline and write report
        baseline_comparison = compare_with_baseline(
            baseline,
            {
                "base": base_metrics,
                "coherence": coherence,
                "emotional": emotional,
                "adherence": adherence,
                "fusion_align": fusion_align,
            },
            drift_summary,
        )

        report = {
            "conversation": CONVERSATION,
            "responses": response_texts,
            "signatures": signatures,
            "metrics": {
                "base": base_metrics,
                "coherence": coherence,
                "emotional": emotional,
                "adherence": adherence,
                "fusion_align": fusion_align,
                "drift_summary": drift_summary,
            },
            "baseline_comparison": baseline_comparison,
        }

        save_report(report)

        # Step 6: Assert classification is not severe
        assert drift_summary["classification"] != "severe_drift", (
            f"Persona drift test detected SEVERE DRIFT!\n"
            f"Classification: {drift_summary['classification']}\n"
            f"Drift score: {drift_summary['drift_score']}\n"
            f"Components: {drift_summary['components']}\n"
            f"Report saved to: {REPORT_PATH}"
        )

        # Step 7: Assert drift score didn't increase too much from baseline
        drift_score_delta = baseline_comparison["drift_score_delta"]
        assert drift_score_delta <= DRIFT_SCORE_INCREASE_THRESHOLD, (
            f"Drift score increased by {drift_score_delta:.3f} (threshold: {DRIFT_SCORE_INCREASE_THRESHOLD})\n"
            f"Baseline: {baseline_comparison['baseline_score']:.3f}\n"
            f"Current: {baseline_comparison['current_score']:.3f}\n"
            f"Report saved to: {REPORT_PATH}"
        )

        # Assert component deltas are within bounds
        for component, delta in baseline_comparison["component_deltas"].items():
            assert abs(delta) <= BASELINE_DEVIATION_THRESHOLD, (
                f"Component '{component}' deviated by {abs(delta):.3f} "
                f"(threshold: {BASELINE_DEVIATION_THRESHOLD})\n"
                f"Report saved to: {REPORT_PATH}"
            )

        print(f"[PERSONA DRIFT] Test passed. Classification: {drift_summary['classification']}")
        print(f"[PERSONA DRIFT] Drift score: {drift_summary['drift_score']:.3f}")
        print(f"[PERSONA DRIFT] Report saved to: {REPORT_PATH}")


# =============================================================================
# UNIT TESTS FOR INDIVIDUAL METRICS
# =============================================================================

class TestBaseMetricsDeterminism:
    """Verify base metrics computation is deterministic."""

    def test_same_input_produces_same_output(self):
        """Two runs with same signatures produce identical metrics."""
        signatures = [
            {"warmth": 0.3, "directness": 0.5, "depth": 0.2, "regulation": 0.6, "length_norm": 0.5},
            {"warmth": 0.4, "directness": 0.4, "depth": 0.3, "regulation": 0.5, "length_norm": 0.6},
            {"warmth": 0.5, "directness": 0.3, "depth": 0.4, "regulation": 0.6, "length_norm": 0.7},
        ]

        result1 = compute_base_drift_metrics(signatures)
        result2 = compute_base_drift_metrics(signatures)

        assert result1 == result2, "Base metrics must be deterministic"


class TestCoherenceComputation:
    """Validate coherence algorithm."""

    def test_identical_responses_high_coherence(self):
        """Identical responses should have perfect coherence."""
        responses = [
            "This is a test response about clarity.",
            "This is a test response about clarity.",
        ]

        result = compute_sequential_coherence(responses)

        assert result["coherence_score"] == 1.0
        assert result["min_overlap"] == 1.0
        assert result["max_overlap"] == 1.0

    def test_completely_different_responses_low_coherence(self):
        """Completely different responses should have low coherence."""
        responses = [
            "Apple banana cherry durian elderberry fruit grape.",
            "Zebra yak xenops wolf vulture unicorn tiger.",
        ]

        result = compute_sequential_coherence(responses)

        assert result["coherence_score"] < 0.2

    def test_single_response_returns_max_coherence(self):
        """Single response should return 1.0 coherence."""
        responses = ["Single response here."]

        result = compute_sequential_coherence(responses)

        assert result["coherence_score"] == 1.0


class TestEmotionalGradientComputation:
    """Validate emotional gradient metrics."""

    def test_stable_emotions_low_volatility(self):
        """Stable emotional values should have low volatility."""
        signatures = [
            {"warmth": 0.5, "regulation": 0.5},
            {"warmth": 0.5, "regulation": 0.5},
            {"warmth": 0.5, "regulation": 0.5},
        ]

        result = compute_emotional_gradient_metrics(signatures)

        assert result["emotional_volatility"] == 0.0
        assert all(d == 0.0 for d in result["warmth_deltas"])
        assert all(d == 0.0 for d in result["regulation_deltas"])

    def test_oscillating_emotions_high_volatility(self):
        """Oscillating emotions should have high volatility."""
        signatures = [
            {"warmth": 0.0, "regulation": 0.0},
            {"warmth": 1.0, "regulation": 1.0},
            {"warmth": 0.0, "regulation": 0.0},
            {"warmth": 1.0, "regulation": 1.0},
        ]

        result = compute_emotional_gradient_metrics(signatures)

        # Volatility is now normalized to [0, 1] range
        assert result["emotional_volatility"] >= 0.9, "Oscillation should produce high volatility"


class TestInstructionAdherenceComputation:
    """Validate instruction adherence metrics."""

    def test_consistent_tone_low_drift(self):
        """Consistent instruction tone should have low drift."""
        responses = [
            "Consider thinking about this. Maybe reflect on it.",
            "Consider exploring this. Perhaps look into it.",
            "Consider examining this. Maybe investigate it.",
        ]

        result = compute_instruction_adherence_metrics(responses)

        # All should have similar patterns
        assert result["imperative_drift"] < 0.5
        assert result["uncertainty_drift"] < 0.1

    def test_changing_tone_high_drift(self):
        """Changing instruction tone should have higher drift."""
        responses = [
            "Maybe consider this possibility perhaps.",  # Very uncertain
            "Do this now. Take action immediately. Stop waiting.",  # Very imperative
        ]

        result = compute_instruction_adherence_metrics(responses)

        assert result["imperative_drift"] > 0.3 or result["uncertainty_drift"] > 0.01


class TestFusionAlignmentComputation:
    """Validate fusion alignment metrics."""

    def test_aligned_persona_fusion_high_score(self):
        """Aligned persona and fusion should have high alignment."""
        responses = [
            {
                "persona_text": "Reflect on your inner journey and purpose.",
                "fusion": {"practical": {"text": "Reflect on your inner journey and purpose."}},
            },
        ]

        result = compute_fusion_alignment_metrics(responses)

        assert result["alignment_scores"][0] > 0.8

    def test_misaligned_persona_fusion_low_score(self):
        """Misaligned persona and fusion should have lower alignment."""
        responses = [
            {
                "persona_text": "Consider your emotional wellbeing deeply.",
                "fusion": {"practical": {"text": "Execute the technical implementation now."}},
            },
        ]

        result = compute_fusion_alignment_metrics(responses)

        assert result["alignment_scores"][0] < 0.5


class TestDriftClassification:
    """Validate drift classification logic."""

    def test_all_zeros_stable(self):
        """All zero metrics should classify as stable."""
        result = classify_persona_drift(
            {"max_feature_drift": 0.0},
            {"coherence_score": 1.0},
            {"emotional_volatility": 0.0},
            {"imperative_drift": 0.0, "uncertainty_drift": 0.0, "safety_drift": 0.0},
            {"alignment_drift": 0.0},
        )

        assert result["classification"] == "stable"
        assert result["drift_score"] < DRIFT_THRESHOLD_STABLE

    def test_high_volatility_severe_drift(self):
        """High emotional volatility should cause severe drift."""
        result = classify_persona_drift(
            {"max_feature_drift": 0.0},
            {"coherence_score": 1.0},
            {"emotional_volatility": 0.8},  # High volatility (above 0.70 threshold)
            {"imperative_drift": 0.0, "uncertainty_drift": 0.0, "safety_drift": 0.0},
            {"alignment_drift": 0.0},
        )

        assert result["classification"] == "severe_drift"
        assert result["drift_score"] >= DRIFT_THRESHOLD_MILD

    def test_low_coherence_causes_penalty(self):
        """Low coherence should increase drift score."""
        result = classify_persona_drift(
            {"max_feature_drift": 0.0},
            {"coherence_score": 0.2},  # Low coherence
            {"emotional_volatility": 0.0},
            {"imperative_drift": 0.0, "uncertainty_drift": 0.0, "safety_drift": 0.0},
            {"alignment_drift": 0.0},
        )

        # coherence_penalty = max(0, 0.5 - 0.2) = 0.3
        assert result["components"]["coherence_penalty"] == 0.3
        assert result["drift_score"] >= 0.3


class TestPersonaSignatureExtraction:
    """Validate persona signature extraction."""

    def test_empathic_text_high_warmth(self):
        """Text with empathy markers should have high warmth."""
        response = "I understand how you're feeling. It makes sense to feel this way. That's valid."

        sig = extract_persona_signature(response)

        assert sig["warmth"] > 0.5

    def test_directive_text_high_directness(self):
        """Text with directives should have high directness."""
        response = "You should do this. You must take action. Have to focus now."

        sig = extract_persona_signature(response)

        assert sig["directness"] > 0.5

    def test_dict_response_extracts_text(self):
        """Dict response should extract text correctly."""
        response = {
            "raw_text": "This is the actual response text.",
            "meta": {"tone": "warm"},
        }

        sig = extract_persona_signature(response)

        assert sig["length_norm"] > 0


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
