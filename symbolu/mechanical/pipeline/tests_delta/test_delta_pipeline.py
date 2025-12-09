"""
Delta Snapshot Test Suite (v1.0)
================================

Detects and quantifies behavioral changes across all AGI pipeline components.

Delta Snapshots compare:
    - Current run output
    - Last-known-stable baseline snapshot

And produce:
    - Structural diffs (added/removed/changed keys)
    - Semantic diffs (symbolic density, contradictions)
    - Numeric deltas (SMI, Bhava, Ontology, Kosha)
    - Temporal deltas (tension corridor, recovery, momentum)
    - Change classification (NO_CHANGE / SAFE / UNSAFE / BREAKING)

Layers Tested:
    - Persona Layer
    - MLCR Layer
    - Fusion Layer
    - DHA Layer
    - Renderer Outputs
    - Full Pipeline Outputs
    - Temporal Pipeline Outputs

CRITICAL: These tests are LLM-free and fully deterministic.
All randomness (UUIDs, timestamps) is controlled via mocking.
"""

import pytest
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from unittest.mock import MagicMock

# Import Pipeline and models
from symbolu.mechanical.pipeline.orchestrator import SymbolUPipeline
from symbolu.mechanical.pipeline.models import (
    UserRequest,
    RenderedOutput,
    PipelineContext,
)

# Import Temporal tracking
from symbolu.temporal import TemporalBhavaTracker, CrossDomainIntelligence


# =============================================================================
# PATHS AND CONSTANTS
# =============================================================================

SNAPSHOT_DIR = Path(__file__).parent.parent / "snapshots"
DELTA_BASELINE_PATH = SNAPSHOT_DIR / "delta_baseline.json"
DELTA_REPORT_PATH = Path(__file__).parent / "delta_report.json"

# Delta thresholds for classification
NUMERIC_THRESHOLD_SAFE = 0.05      # 5% change is safe
NUMERIC_THRESHOLD_UNSAFE = 0.15   # 15% change is unsafe (above = breaking)
SYMBOLIC_DENSITY_THRESHOLD = 0.10  # 10% density change threshold


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class StructuralDiff:
    """Captures structural differences between baseline and current."""
    added_keys: List[str] = field(default_factory=list)
    removed_keys: List[str] = field(default_factory=list)
    changed_values: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    is_different: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SemanticDiff:
    """Captures semantic-level differences."""
    symbolic_density_delta: float = 0.0
    contradiction_delta: int = 0
    tone_shift: Optional[str] = None
    persona_shift: Optional[str] = None
    is_different: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NumericDiff:
    """Captures numerical metric differences."""
    smi_delta: float = 0.0
    bhava_delta: int = 0
    bhava_direction_change: bool = False
    kosha_delta: int = 0
    ontology_delta: int = 0
    entropy_delta: Dict[str, float] = field(default_factory=dict)
    is_different: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TemporalDiff:
    """Captures temporal analysis differences."""
    tension_corridor_delta: int = 0
    recovery_delta: float = 0.0
    momentum_slope_delta: float = 0.0
    trajectory_trend_change: bool = False
    state_change: Optional[str] = None
    is_different: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeltaReport:
    """Complete delta analysis report."""
    pipeline: Dict[str, Any] = field(default_factory=dict)
    temporal: Dict[str, Any] = field(default_factory=dict)
    deltas: Dict[str, Any] = field(default_factory=dict)
    classification: str = "NO_CHANGE"
    timestamp: str = ""
    baseline_version: str = ""
    current_version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# DETERMINISTIC MOCK FIXTURES
# =============================================================================

class DeterministicUUIDGenerator:
    """
    Generate deterministic UUIDs for testing.
    Ensures reproducible candidate IDs across test runs.
    """

    def __init__(self, prefix: str = "delta") -> None:
        self.counter = 0
        self.prefix = prefix

    def generate(self) -> str:
        self.counter += 1
        return f"{self.prefix}_{self.counter:08d}"


# Deterministic analysis results for temporal testing
DETERMINISTIC_TEMPORAL_INPUTS = [
    "I'm very stressed today.",
    "Things feel slightly better now.",
    "I think I'm stabilizing.",
    "Now I feel I'm recovering gradually.",
]

DETERMINISTIC_ANALYSIS_RESULTS = [
    {"smi": 0.78, "bhava_id": 3, "bhava_direction": "downward", "kosha_id": 2, "ontology_id": 3},
    {"smi": 0.62, "bhava_id": 4, "bhava_direction": "neutral", "kosha_id": 3, "ontology_id": 4},
    {"smi": 0.48, "bhava_id": 5, "bhava_direction": "upward", "kosha_id": 4, "ontology_id": 5},
    {"smi": 0.35, "bhava_id": 6, "bhava_direction": "upward", "kosha_id": 4, "ontology_id": 6},
]


# =============================================================================
# DELTA COMPUTATION FUNCTIONS
# =============================================================================

def compute_structural_diff(
    baseline: Dict[str, Any],
    current: Dict[str, Any],
    path: str = ""
) -> StructuralDiff:
    """
    Recursively compute structural differences between two dictionaries.

    Args:
        baseline: The baseline dictionary.
        current: The current dictionary.
        path: Current path in the nested structure (for key naming).

    Returns:
        StructuralDiff with added, removed, and changed keys.
    """
    diff = StructuralDiff()

    baseline_keys = set(baseline.keys()) if isinstance(baseline, dict) else set()
    current_keys = set(current.keys()) if isinstance(current, dict) else set()

    # Find added keys
    for key in current_keys - baseline_keys:
        full_path = f"{path}.{key}" if path else key
        diff.added_keys.append(full_path)
        diff.is_different = True

    # Find removed keys
    for key in baseline_keys - current_keys:
        full_path = f"{path}.{key}" if path else key
        diff.removed_keys.append(full_path)
        diff.is_different = True

    # Find changed values
    for key in baseline_keys & current_keys:
        full_path = f"{path}.{key}" if path else key
        b_val = baseline[key]
        c_val = current[key]

        if isinstance(b_val, dict) and isinstance(c_val, dict):
            # Recurse into nested dicts
            nested_diff = compute_structural_diff(b_val, c_val, full_path)
            diff.added_keys.extend(nested_diff.added_keys)
            diff.removed_keys.extend(nested_diff.removed_keys)
            diff.changed_values.update(nested_diff.changed_values)
            if nested_diff.is_different:
                diff.is_different = True
        elif b_val != c_val:
            diff.changed_values[full_path] = {
                "baseline": _serialize_value(b_val),
                "current": _serialize_value(c_val),
            }
            diff.is_different = True

    return diff


def _serialize_value(value: Any) -> Any:
    """Serialize a value for JSON storage."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    elif isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    elif isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    else:
        return str(value)


def compute_semantic_diff(
    baseline: Dict[str, Any],
    current: Dict[str, Any]
) -> SemanticDiff:
    """
    Compute semantic-level differences.

    Analyzes:
        - Symbolic density changes
        - Contradiction count changes
        - Tone profile shifts
        - Persona shifts

    Args:
        baseline: Baseline pipeline output.
        current: Current pipeline output.

    Returns:
        SemanticDiff with semantic analysis.
    """
    diff = SemanticDiff()

    # Extract symbolic density (count of symbolic markers)
    baseline_density = _compute_symbolic_density(baseline)
    current_density = _compute_symbolic_density(current)
    diff.symbolic_density_delta = current_density - baseline_density

    if abs(diff.symbolic_density_delta) > 0.001:
        diff.is_different = True

    # Extract contradiction counts
    baseline_contradictions = _count_contradictions(baseline)
    current_contradictions = _count_contradictions(current)
    diff.contradiction_delta = current_contradictions - baseline_contradictions

    if diff.contradiction_delta != 0:
        diff.is_different = True

    # Check tone profile shift
    baseline_tone = _extract_nested(baseline, "meta.tone_profile")
    current_tone = _extract_nested(current, "meta.tone_profile")
    if baseline_tone != current_tone and (baseline_tone or current_tone):
        diff.tone_shift = f"{baseline_tone} -> {current_tone}"
        diff.is_different = True

    # Check persona shift
    baseline_persona = _extract_nested(baseline, "meta.persona_id")
    current_persona = _extract_nested(current, "meta.persona_id")
    if baseline_persona != current_persona and (baseline_persona or current_persona):
        diff.persona_shift = f"{baseline_persona} -> {current_persona}"
        diff.is_different = True

    return diff


def _compute_symbolic_density(output: Dict[str, Any]) -> float:
    """
    Compute symbolic density from pipeline output.

    Density is calculated as ratio of symbolic markers to total content.
    """
    raw_text = output.get("raw_text", "")
    if not raw_text:
        return 0.0

    # Count symbolic markers (common metaphorical/symbolic phrases)
    symbolic_markers = [
        "deeper", "perspective", "reflect", "journey",
        "path", "meaning", "symbolic", "essence",
        "inner", "consciousness", "awareness", "truth",
    ]

    text_lower = raw_text.lower()
    marker_count = sum(1 for marker in symbolic_markers if marker in text_lower)
    word_count = len(raw_text.split())

    return marker_count / max(word_count, 1)


def _count_contradictions(output: Dict[str, Any]) -> int:
    """
    Count potential contradictions in output.

    Simple heuristic: count contradiction indicators.
    """
    raw_text = output.get("raw_text", "")
    if not raw_text:
        return 0

    # Count contradiction patterns
    contradiction_patterns = [
        "however", "but ", "although", "despite",
        "on the other hand", "nevertheless", "yet ",
    ]

    text_lower = raw_text.lower()
    return sum(1 for pattern in contradiction_patterns if pattern in text_lower)


def _extract_nested(data: Dict[str, Any], path: str) -> Any:
    """Extract a value from nested dict using dot notation."""
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def compute_numeric_diff(
    baseline: Dict[str, Any],
    current: Dict[str, Any]
) -> NumericDiff:
    """
    Compute numerical metric differences.

    Compares:
        - SMI values
        - Bhava IDs and directions
        - Kosha IDs
        - Ontology IDs
        - Entropy values

    Args:
        baseline: Baseline temporal/pipeline data.
        current: Current temporal/pipeline data.

    Returns:
        NumericDiff with numerical deltas.
    """
    diff = NumericDiff()

    # SMI delta
    baseline_smi = baseline.get("smi", 0.5)
    current_smi = current.get("smi", 0.5)
    diff.smi_delta = current_smi - baseline_smi

    if abs(diff.smi_delta) > 0.001:
        diff.is_different = True

    # Bhava delta
    baseline_bhava = baseline.get("bhava_id", 5)
    current_bhava = current.get("bhava_id", 5)
    diff.bhava_delta = current_bhava - baseline_bhava

    if diff.bhava_delta != 0:
        diff.is_different = True

    # Bhava direction change
    baseline_direction = baseline.get("bhava_direction", "neutral")
    current_direction = current.get("bhava_direction", "neutral")
    diff.bhava_direction_change = baseline_direction != current_direction

    if diff.bhava_direction_change:
        diff.is_different = True

    # Kosha delta
    baseline_kosha = baseline.get("kosha_id", 3)
    current_kosha = current.get("kosha_id", 3)
    diff.kosha_delta = current_kosha - baseline_kosha

    if diff.kosha_delta != 0:
        diff.is_different = True

    # Ontology delta
    baseline_ontology = baseline.get("ontology_id", 4)
    current_ontology = current.get("ontology_id", 4)
    diff.ontology_delta = current_ontology - baseline_ontology

    if diff.ontology_delta != 0:
        diff.is_different = True

    # Entropy deltas
    baseline_entropy = baseline.get("entropy", {})
    current_entropy = current.get("entropy", {})

    for key in set(baseline_entropy.keys()) | set(current_entropy.keys()):
        b_val = baseline_entropy.get(key, 0.5)
        c_val = current_entropy.get(key, 0.5)
        delta = c_val - b_val
        if abs(delta) > 0.001:
            diff.entropy_delta[key] = delta
            diff.is_different = True

    return diff


def compute_temporal_diff(
    baseline: Dict[str, Any],
    current: Dict[str, Any]
) -> TemporalDiff:
    """
    Compute temporal analysis differences.

    Compares:
        - Tension corridor length
        - Recovery progress
        - Momentum slope
        - Trajectory trend
        - State classification

    Args:
        baseline: Baseline temporal summary.
        current: Current temporal summary.

    Returns:
        TemporalDiff with temporal deltas.
    """
    diff = TemporalDiff()

    # Tension corridor delta
    baseline_tension = baseline.get("tension", {})
    current_tension = current.get("tension", {})

    b_corridor = baseline_tension.get("corridor_length", 0)
    c_corridor = current_tension.get("corridor_length", 0)
    diff.tension_corridor_delta = c_corridor - b_corridor

    if diff.tension_corridor_delta != 0:
        diff.is_different = True

    # Recovery delta
    baseline_recovery = baseline.get("recovery", {})
    current_recovery = current.get("recovery", {})

    b_progress = baseline_recovery.get("progress", 0.0)
    c_progress = current_recovery.get("progress", 0.0)
    diff.recovery_delta = c_progress - b_progress

    if abs(diff.recovery_delta) > 0.001:
        diff.is_different = True

    # Momentum slope delta
    baseline_momentum = baseline.get("momentum", {})
    current_momentum = current.get("momentum", {})

    b_slope = baseline_momentum.get("slope", 0.0)
    c_slope = current_momentum.get("slope", 0.0)
    diff.momentum_slope_delta = c_slope - b_slope

    if abs(diff.momentum_slope_delta) > 0.001:
        diff.is_different = True

    # Trajectory trend change
    baseline_trajectory = baseline.get("trajectory", {})
    current_trajectory = current.get("trajectory", {})

    b_trend = baseline_trajectory.get("trend", "stable")
    c_trend = current_trajectory.get("trend", "stable")
    diff.trajectory_trend_change = b_trend != c_trend

    if diff.trajectory_trend_change:
        diff.is_different = True

    # State change
    b_state = baseline.get("state", "STABLE")
    c_state = current.get("state", "STABLE")
    if b_state != c_state:
        diff.state_change = f"{b_state} -> {c_state}"
        diff.is_different = True

    return diff


def classify_change(
    structural: StructuralDiff,
    semantic: SemanticDiff,
    numeric: NumericDiff,
    temporal: TemporalDiff
) -> str:
    """
    Classify the overall change based on delta analysis.

    Classification logic:
        - BREAKING: Structural changes (added/removed keys) or large numeric shifts
        - UNSAFE: Moderate shifts in semantic, numeric, or temporal metrics
        - SAFE: Small deltas within acceptable thresholds
        - NO_CHANGE: No differences detected

    Args:
        structural: Structural diff results.
        semantic: Semantic diff results.
        numeric: Numeric diff results.
        temporal: Temporal diff results.

    Returns:
        Classification string: "NO_CHANGE", "SAFE", "UNSAFE", or "BREAKING"
    """
    # Check for no changes
    if not any([
        structural.is_different,
        semantic.is_different,
        numeric.is_different,
        temporal.is_different,
    ]):
        return "NO_CHANGE"

    # Check for BREAKING changes
    # Structural changes (added/removed keys) are breaking
    if structural.added_keys or structural.removed_keys:
        return "BREAKING"

    # Large numeric shifts are breaking
    if abs(numeric.smi_delta) > NUMERIC_THRESHOLD_UNSAFE:
        return "BREAKING"

    if abs(numeric.bhava_delta) > 2:  # More than 2 bhava levels
        return "BREAKING"

    # Check for UNSAFE changes
    # Moderate numeric shifts
    if abs(numeric.smi_delta) > NUMERIC_THRESHOLD_SAFE:
        return "UNSAFE"

    # Symbolic density beyond threshold
    if abs(semantic.symbolic_density_delta) > SYMBOLIC_DENSITY_THRESHOLD:
        return "UNSAFE"

    # Bhava direction change
    if numeric.bhava_direction_change:
        return "UNSAFE"

    # Trajectory trend change
    if temporal.trajectory_trend_change:
        return "UNSAFE"

    # State change
    if temporal.state_change:
        return "UNSAFE"

    # Persona or tone shifts
    if semantic.persona_shift or semantic.tone_shift:
        return "UNSAFE"

    # All other changes are SAFE
    return "SAFE"


# =============================================================================
# PIPELINE OUTPUT GENERATION
# =============================================================================

def generate_pipeline_output(
    pipeline: SymbolUPipeline,
    text: str,
    mode: str,
    user_id: str,
) -> Dict[str, Any]:
    """
    Generate deterministic pipeline output for a given mode.

    Args:
        pipeline: Pipeline instance.
        text: Input text.
        mode: Render mode (minimal, standard, enhanced, regulated).
        user_id: User ID for the request.

    Returns:
        Serialized pipeline output as dict.
    """
    request = UserRequest(
        text=text,
        user_id=user_id,
        render_mode=mode,
        metadata={
            "domain": "personal" if mode != "regulated" else "medical",
            "readiness_score": 0.7,
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

    # Serialize output
    return {
        "raw_text": result.raw_text,
        "mode": result.mode,
        "meta": result.meta,
        "context": {
            "persona_id": ctx.persona.active_persona_id if ctx.persona else None,
            "mlcr_tier": ctx.mlcr.explain_log.get("meta", {}).get("tier") if ctx.mlcr else None,
            "fusion_candidate_count": ctx.fusion.trace.get("candidate_count") if ctx.fusion else None,
            "dha_tone": ctx.dha.tone_profile if ctx.dha else None,
        },
    }


def generate_temporal_output(
    tracker: TemporalBhavaTracker,
    intel: CrossDomainIntelligence,
) -> Dict[str, Any]:
    """
    Generate deterministic temporal analysis output.

    Args:
        tracker: TemporalBhavaTracker instance.
        intel: CrossDomainIntelligence instance.

    Returns:
        Serialized temporal output as dict.
    """
    turns = []

    for turn_num, (input_text, analysis) in enumerate(
        zip(DETERMINISTIC_TEMPORAL_INPUTS, DETERMINISTIC_ANALYSIS_RESULTS),
        start=1
    ):
        tracker.add_analysis(
            text=input_text,
            smi=analysis["smi"],
            bhava_id=analysis["bhava_id"],
            bhava_direction=analysis["bhava_direction"],
            kosha_id=analysis["kosha_id"],
            ontology_id=analysis["ontology_id"],
        )

        pattern_summary = tracker.get_pattern_summary()

        detected_patterns = intel.detect_pattern(
            smi=analysis["smi"],
            bhava_id=analysis["bhava_id"],
            bhava_direction=analysis["bhava_direction"],
            kosha_id=analysis["kosha_id"],
            ontology_id=analysis["ontology_id"],
            temporal_trend=pattern_summary["trajectory"]["trend"],
        )

        turn_data = {
            "turn_number": turn_num,
            "input_text": input_text,
            "analysis": analysis,
            "trajectory": pattern_summary["trajectory"],
            "momentum": pattern_summary["momentum"],
            "tension": pattern_summary["tension"],
            "recovery": pattern_summary["recovery"],
            "state": pattern_summary["state"],
            "detected_patterns": [
                {"name": p[0], "confidence": p[1]}
                for p in detected_patterns[:3]
            ],
        }

        turns.append(turn_data)

    final_summary = tracker.get_pattern_summary()

    return {
        "turns": turns,
        "final_state": final_summary["state"],
        "trajectory": final_summary["trajectory"],
        "momentum": final_summary["momentum"],
        "tension": final_summary["tension"],
        "recovery": final_summary["recovery"],
        "stats": final_summary["stats"],
        "smi": DETERMINISTIC_ANALYSIS_RESULTS[-1]["smi"],
        "bhava_id": DETERMINISTIC_ANALYSIS_RESULTS[-1]["bhava_id"],
        "bhava_direction": DETERMINISTIC_ANALYSIS_RESULTS[-1]["bhava_direction"],
        "kosha_id": DETERMINISTIC_ANALYSIS_RESULTS[-1]["kosha_id"],
        "ontology_id": DETERMINISTIC_ANALYSIS_RESULTS[-1]["ontology_id"],
        "entropy": {},  # Placeholder for entropy values
    }


# =============================================================================
# BASELINE MANAGEMENT
# =============================================================================

def load_baseline() -> Optional[Dict[str, Any]]:
    """
    Load delta baseline from file.

    Returns:
        Baseline dict or None if not found.
    """
    if not DELTA_BASELINE_PATH.exists():
        return None

    with open(DELTA_BASELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_baseline(baseline: Dict[str, Any]) -> None:
    """
    Save delta baseline to file.

    Args:
        baseline: Baseline data to save.
    """
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    with open(DELTA_BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, sort_keys=True)


def create_baseline(
    pipeline: SymbolUPipeline,
    tracker: TemporalBhavaTracker,
    intel: CrossDomainIntelligence,
) -> Dict[str, Any]:
    """
    Create a new delta baseline from current pipeline outputs.

    Args:
        pipeline: Pipeline instance.
        tracker: TemporalBhavaTracker instance.
        intel: CrossDomainIntelligence instance.

    Returns:
        New baseline dict.
    """
    test_text = "I feel conflicted about my progress today."
    regulated_text = "I have been experiencing frequent headaches and want guidance."

    baseline = {
        "pipeline": {
            "minimal": generate_pipeline_output(
                pipeline, test_text, "minimal", "baseline_user_minimal"
            ),
            "standard": generate_pipeline_output(
                pipeline, test_text, "standard", "baseline_user_standard"
            ),
            "symbolic": generate_pipeline_output(
                pipeline, test_text, "enhanced", "baseline_user_symbolic"
            ),
            "regulated": generate_pipeline_output(
                pipeline, regulated_text, "regulated", "baseline_user_regulated"
            ),
        },
        "temporal": {
            "temporal_single": generate_temporal_output(tracker, intel),
            "temporal_multiturn": generate_temporal_output(
                TemporalBhavaTracker(window_size=10),
                CrossDomainIntelligence(),
            ),
        },
        "meta": {
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "pipeline_version": "3.0",
        },
    }

    return baseline


def save_delta_report(report: DeltaReport) -> None:
    """
    Save delta report to file.

    Args:
        report: DeltaReport to save.
    """
    DELTA_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(DELTA_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, sort_keys=True)


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def deterministic_pipeline():
    """
    Create a pipeline instance with mocked components for deterministic testing.
    """
    pipeline = SymbolUPipeline()
    uuid_gen = DeterministicUUIDGenerator("delta_candidate")

    def mock_generate_candidates(ctx, explain_log, activation_plan):
        from symbolu.mechanical.fusion.schemas.candidate import Candidate, CandidateSource

        query_text = ctx.request.text
        domain = explain_log.get("meta", {}).get("domain", "general")

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


@pytest.fixture
def temporal_tracker():
    """Create a fresh TemporalBhavaTracker instance."""
    return TemporalBhavaTracker(window_size=10)


@pytest.fixture
def cross_domain_intel():
    """Create a CrossDomainIntelligence instance."""
    return CrossDomainIntelligence()


# =============================================================================
# MAIN DELTA TEST
# =============================================================================

class TestDeltaPipeline:
    """
    Delta Snapshot Tests for Symbol-U Pipeline.

    These tests detect and quantify behavioral changes by comparing
    current outputs against a stable baseline.
    """

    def test_delta_pipeline_full(
        self,
        deterministic_pipeline: SymbolUPipeline,
        temporal_tracker: TemporalBhavaTracker,
        cross_domain_intel: CrossDomainIntelligence,
    ):
        """
        Full delta test: generates outputs, computes deltas, classifies changes.

        Test Flow:
            1. Load baseline (or create if missing)
            2. Generate current pipeline outputs
            3. Generate current temporal outputs
            4. Compute all deltas
            5. Classify overall change
            6. Save delta report
            7. Assert classification != BREAKING
        """
        # ==================================================================
        # STEP 1: Load or create baseline
        # ==================================================================
        baseline = load_baseline()

        if baseline is None:
            # First run: create baseline
            print("[DELTA] Creating baseline for first run...")
            baseline = create_baseline(
                deterministic_pipeline,
                temporal_tracker,
                cross_domain_intel,
            )
            save_baseline(baseline)

            # Create minimal report for first run
            report = DeltaReport(
                pipeline={},
                temporal={},
                deltas={
                    "structural": {"is_different": False},
                    "semantic": {"is_different": False},
                    "numeric": {"is_different": False},
                    "temporal": {"is_different": False},
                    "classification": "NO_CHANGE",
                },
                classification="NO_CHANGE",
                timestamp=datetime.utcnow().isoformat() + "Z",
                baseline_version=baseline["meta"]["version"],
                current_version=baseline["meta"]["version"],
            )
            save_delta_report(report)

            # First run passes immediately
            return

        # ==================================================================
        # STEP 2: Generate current outputs
        # ==================================================================
        test_text = "I feel conflicted about my progress today."
        regulated_text = "I have been experiencing frequent headaches and want guidance."

        # Reset the UUID generator for consistent candidate IDs
        uuid_gen = DeterministicUUIDGenerator("delta_candidate")

        def mock_generate_candidates(ctx, explain_log, activation_plan):
            from symbolu.mechanical.fusion.schemas.candidate import Candidate, CandidateSource

            query_text = ctx.request.text
            domain = explain_log.get("meta", {}).get("domain", "general")

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

        deterministic_pipeline._generate_candidates = mock_generate_candidates

        current_pipeline = {
            "minimal": generate_pipeline_output(
                deterministic_pipeline, test_text, "minimal", "delta_user_minimal"
            ),
            "standard": generate_pipeline_output(
                deterministic_pipeline, test_text, "standard", "delta_user_standard"
            ),
            "symbolic": generate_pipeline_output(
                deterministic_pipeline, test_text, "enhanced", "delta_user_symbolic"
            ),
            "regulated": generate_pipeline_output(
                deterministic_pipeline, regulated_text, "regulated", "delta_user_regulated"
            ),
        }

        # ==================================================================
        # STEP 3: Generate current temporal outputs
        # ==================================================================
        current_temporal = {
            "temporal_single": generate_temporal_output(
                temporal_tracker,
                cross_domain_intel,
            ),
            "temporal_multiturn": generate_temporal_output(
                TemporalBhavaTracker(window_size=10),
                CrossDomainIntelligence(),
            ),
        }

        # ==================================================================
        # STEP 4: Compute deltas
        # ==================================================================

        # Aggregate all deltas
        all_structural = StructuralDiff()
        all_semantic = SemanticDiff()
        all_numeric = NumericDiff()
        all_temporal = TemporalDiff()

        pipeline_deltas = {}
        temporal_deltas = {}

        # Pipeline deltas (per mode)
        for mode in ["minimal", "standard", "symbolic", "regulated"]:
            b_output = baseline["pipeline"].get(mode, {})
            c_output = current_pipeline.get(mode, {})

            struct_diff = compute_structural_diff(b_output, c_output, f"pipeline.{mode}")
            semantic_diff = compute_semantic_diff(b_output, c_output)

            pipeline_deltas[mode] = {
                "structural": struct_diff.to_dict(),
                "semantic": semantic_diff.to_dict(),
            }

            # Merge into aggregates
            all_structural.added_keys.extend(struct_diff.added_keys)
            all_structural.removed_keys.extend(struct_diff.removed_keys)
            all_structural.changed_values.update(struct_diff.changed_values)
            if struct_diff.is_different:
                all_structural.is_different = True

            if semantic_diff.is_different:
                all_semantic.is_different = True
                # Take max symbolic density delta
                if abs(semantic_diff.symbolic_density_delta) > abs(all_semantic.symbolic_density_delta):
                    all_semantic.symbolic_density_delta = semantic_diff.symbolic_density_delta
                all_semantic.contradiction_delta += semantic_diff.contradiction_delta
                if semantic_diff.tone_shift:
                    all_semantic.tone_shift = semantic_diff.tone_shift
                if semantic_diff.persona_shift:
                    all_semantic.persona_shift = semantic_diff.persona_shift

        # Temporal deltas
        for key in ["temporal_single", "temporal_multiturn"]:
            b_temporal = baseline["temporal"].get(key, {})
            c_temporal = current_temporal.get(key, {})

            struct_diff = compute_structural_diff(b_temporal, c_temporal, f"temporal.{key}")
            numeric_diff = compute_numeric_diff(b_temporal, c_temporal)
            temp_diff = compute_temporal_diff(b_temporal, c_temporal)

            temporal_deltas[key] = {
                "structural": struct_diff.to_dict(),
                "numeric": numeric_diff.to_dict(),
                "temporal": temp_diff.to_dict(),
            }

            # Merge into aggregates
            all_structural.added_keys.extend(struct_diff.added_keys)
            all_structural.removed_keys.extend(struct_diff.removed_keys)
            all_structural.changed_values.update(struct_diff.changed_values)
            if struct_diff.is_different:
                all_structural.is_different = True

            if numeric_diff.is_different:
                all_numeric.is_different = True
                # Take largest deltas
                if abs(numeric_diff.smi_delta) > abs(all_numeric.smi_delta):
                    all_numeric.smi_delta = numeric_diff.smi_delta
                if abs(numeric_diff.bhava_delta) > abs(all_numeric.bhava_delta):
                    all_numeric.bhava_delta = numeric_diff.bhava_delta
                all_numeric.bhava_direction_change = (
                    all_numeric.bhava_direction_change or numeric_diff.bhava_direction_change
                )

            if temp_diff.is_different:
                all_temporal.is_different = True
                all_temporal.trajectory_trend_change = (
                    all_temporal.trajectory_trend_change or temp_diff.trajectory_trend_change
                )
                if temp_diff.state_change:
                    all_temporal.state_change = temp_diff.state_change

        # ==================================================================
        # STEP 5: Classify overall change
        # ==================================================================
        classification = classify_change(
            all_structural,
            all_semantic,
            all_numeric,
            all_temporal,
        )

        # ==================================================================
        # STEP 6: Build and save delta report
        # ==================================================================
        report = DeltaReport(
            pipeline=pipeline_deltas,
            temporal=temporal_deltas,
            deltas={
                "structural": all_structural.to_dict(),
                "semantic": all_semantic.to_dict(),
                "numeric": all_numeric.to_dict(),
                "temporal": all_temporal.to_dict(),
                "classification": classification,
            },
            classification=classification,
            timestamp=datetime.utcnow().isoformat() + "Z",
            baseline_version=baseline["meta"]["version"],
            current_version="1.0.0",
        )

        save_delta_report(report)

        # ==================================================================
        # STEP 7: Assert classification is not BREAKING
        # ==================================================================
        assert classification != "BREAKING", (
            f"Delta test detected BREAKING changes!\n"
            f"Classification: {classification}\n"
            f"Structural: {all_structural.to_dict()}\n"
            f"Semantic: {all_semantic.to_dict()}\n"
            f"Numeric: {all_numeric.to_dict()}\n"
            f"Temporal: {all_temporal.to_dict()}\n"
            f"Full report saved to: {DELTA_REPORT_PATH}"
        )

        # Log result
        print(f"[DELTA] Classification: {classification}")
        print(f"[DELTA] Report saved to: {DELTA_REPORT_PATH}")


# =============================================================================
# INDIVIDUAL DELTA COMPONENT TESTS
# =============================================================================

class TestStructuralDiff:
    """Test structural diff computation."""

    def test_no_diff_identical_dicts(self):
        """Test that identical dicts produce no diff."""
        d1 = {"a": 1, "b": {"c": 2}}
        d2 = {"a": 1, "b": {"c": 2}}

        diff = compute_structural_diff(d1, d2)

        assert not diff.is_different
        assert len(diff.added_keys) == 0
        assert len(diff.removed_keys) == 0
        assert len(diff.changed_values) == 0

    def test_added_keys_detected(self):
        """Test that added keys are detected."""
        d1 = {"a": 1}
        d2 = {"a": 1, "b": 2}

        diff = compute_structural_diff(d1, d2)

        assert diff.is_different
        assert "b" in diff.added_keys

    def test_removed_keys_detected(self):
        """Test that removed keys are detected."""
        d1 = {"a": 1, "b": 2}
        d2 = {"a": 1}

        diff = compute_structural_diff(d1, d2)

        assert diff.is_different
        assert "b" in diff.removed_keys

    def test_changed_values_detected(self):
        """Test that changed values are detected."""
        d1 = {"a": 1}
        d2 = {"a": 2}

        diff = compute_structural_diff(d1, d2)

        assert diff.is_different
        assert "a" in diff.changed_values
        assert diff.changed_values["a"]["baseline"] == 1
        assert diff.changed_values["a"]["current"] == 2


class TestSemanticDiff:
    """Test semantic diff computation."""

    def test_symbolic_density_computation(self):
        """Test symbolic density calculation."""
        output = {
            "raw_text": "From a deeper perspective, reflect on your inner journey."
        }

        density = _compute_symbolic_density(output)

        # "deeper", "perspective", "reflect", "inner", "journey" = 5 markers
        # ~8 words total -> density ~0.625
        assert density > 0.5

    def test_semantic_diff_detects_tone_shift(self):
        """Test that tone shifts are detected."""
        baseline = {"meta": {"tone_profile": "SWEET_RESONANCE"}}
        current = {"meta": {"tone_profile": "INVERSE_JOLT"}}

        diff = compute_semantic_diff(baseline, current)

        assert diff.is_different
        assert diff.tone_shift is not None
        assert "SWEET_RESONANCE" in diff.tone_shift
        assert "INVERSE_JOLT" in diff.tone_shift


class TestNumericDiff:
    """Test numeric diff computation."""

    def test_smi_delta_computed(self):
        """Test SMI delta computation."""
        baseline = {"smi": 0.5}
        current = {"smi": 0.7}

        diff = compute_numeric_diff(baseline, current)

        assert diff.is_different
        assert abs(diff.smi_delta - 0.2) < 0.001

    def test_bhava_direction_change_detected(self):
        """Test bhava direction change detection."""
        baseline = {"bhava_direction": "upward"}
        current = {"bhava_direction": "downward"}

        diff = compute_numeric_diff(baseline, current)

        assert diff.is_different
        assert diff.bhava_direction_change


class TestTemporalDiff:
    """Test temporal diff computation."""

    def test_trajectory_trend_change_detected(self):
        """Test trajectory trend change detection."""
        baseline = {"trajectory": {"trend": "rising"}}
        current = {"trajectory": {"trend": "falling"}}

        diff = compute_temporal_diff(baseline, current)

        assert diff.is_different
        assert diff.trajectory_trend_change

    def test_state_change_detected(self):
        """Test state change detection."""
        baseline = {"state": "STABLE"}
        current = {"state": "TENSE"}

        diff = compute_temporal_diff(baseline, current)

        assert diff.is_different
        assert diff.state_change == "STABLE -> TENSE"


class TestChangeClassification:
    """Test change classification logic."""

    def test_no_change_classification(self):
        """Test NO_CHANGE classification."""
        structural = StructuralDiff()
        semantic = SemanticDiff()
        numeric = NumericDiff()
        temporal = TemporalDiff()

        classification = classify_change(structural, semantic, numeric, temporal)

        assert classification == "NO_CHANGE"

    def test_breaking_on_structural_change(self):
        """Test BREAKING classification on structural changes."""
        structural = StructuralDiff(added_keys=["new_key"], is_different=True)
        semantic = SemanticDiff()
        numeric = NumericDiff()
        temporal = TemporalDiff()

        classification = classify_change(structural, semantic, numeric, temporal)

        assert classification == "BREAKING"

    def test_breaking_on_large_smi_shift(self):
        """Test BREAKING classification on large SMI shift."""
        structural = StructuralDiff()
        semantic = SemanticDiff()
        numeric = NumericDiff(smi_delta=0.20, is_different=True)
        temporal = TemporalDiff()

        classification = classify_change(structural, semantic, numeric, temporal)

        assert classification == "BREAKING"

    def test_unsafe_on_moderate_smi_shift(self):
        """Test UNSAFE classification on moderate SMI shift."""
        structural = StructuralDiff()
        semantic = SemanticDiff()
        numeric = NumericDiff(smi_delta=0.08, is_different=True)
        temporal = TemporalDiff()

        classification = classify_change(structural, semantic, numeric, temporal)

        assert classification == "UNSAFE"

    def test_safe_on_small_changes(self):
        """Test SAFE classification on small changes."""
        structural = StructuralDiff(
            changed_values={"a": {"baseline": 1, "current": 2}},
            is_different=True,
        )
        semantic = SemanticDiff()
        numeric = NumericDiff()
        temporal = TemporalDiff()

        classification = classify_change(structural, semantic, numeric, temporal)

        assert classification == "SAFE"


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
