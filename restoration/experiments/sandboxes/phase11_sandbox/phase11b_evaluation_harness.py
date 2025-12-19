"""
Phase-11B: Governed Structural Generator Evaluation Harness
=============================================================

This harness evaluates Phase-11B against the success criteria:
    - Overall differentiation score: ~0.85+ (up from ~0.29 in 11A)
    - Stability: >= 0.95
    - No silent collapse detected
    - Ontological path is strongest clustering axis
    - PPV dimensions produce distinct structural effects

WHAT THIS MEASURES:
    - Does changing ontological path produce different outputs? (→ family routing)
    - Does changing PPV values produce different outputs? (→ band signatures)
    - Does changing mode affect registry selection?
    - Are outputs deterministic under identical conditions?
    - Is there any silent collapse?

WHAT THIS DOES NOT MEASURE:
    - Quality, correctness, semantic meaning of output
    - Any scoring or ranking

CONSTRAINTS:
    - No ML/NLP imports
    - No embeddings or probability models
    - No semantic interpretation
    - Only structural/surface statistics
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum, unique
from typing import Dict, List, Optional, Sequence, Set, Tuple

# Phase-11B imports
from symbolu.mechanical.pipeline.p11_controller.p11_schema import (
    Phase10Result,
    RenderMode,
)
from symbolu.mechanical.pipeline.p11b_controller import (
    OntologicalFamily,
    PPVBand,
    SlotPlan,
    RegistryType,
    PPVBandSignature,
    TemplateKey,
    Phase11BRequest,
    Phase11BResponse,
    Phase11BController,
    run_phase11b_controller,
    create_ppv_band_signature,
    compute_variant_id,
    get_template_family,
    validate_no_silent_collapse,
    get_registry_stats,
)


# =============================================================================
# Version
# =============================================================================

PHASE11B_EVALUATION_VERSION = "1.0.0"


# =============================================================================
# Ontological Layer Definitions (10-Layer Backbone)
# =============================================================================

@unique
class OntologicalLayer(str, Enum):
    """10-layer ontological backbone."""
    ACTING = "ACTING"
    TAGGING = "TAGGING"
    FORMING = "FORMING"
    THINKING = "THINKING"
    DIRECTING = "DIRECTING"
    REASONING = "REASONING"
    PURPOSING = "PURPOSING"
    META_OBSERVING = "META_OBSERVING"
    UNIFYING = "UNIFYING"
    ABSOLVING = "ABSOLVING"


ONTOLOGICAL_LAYER_ORDER: Tuple[OntologicalLayer, ...] = tuple(OntologicalLayer)


# =============================================================================
# PPV Configuration
# =============================================================================

PPV_DIM_COUNT = 8
PPV_VALUE_MIN = 0
PPV_VALUE_MAX = 7

# Sample PPV configurations for testing
SAMPLE_PPV_CONFIGS: Tuple[Tuple[int, ...], ...] = (
    (0, 0, 0, 0, 0, 0, 0, 0),  # All LOW
    (3, 3, 3, 3, 3, 3, 3, 3),  # All MID
    (7, 7, 7, 7, 7, 7, 7, 7),  # All HIGH
    (0, 3, 6, 0, 3, 6, 0, 3),  # Gradient
    (6, 3, 0, 6, 3, 0, 6, 3),  # Reverse gradient
    (0, 7, 0, 7, 0, 7, 0, 7),  # Alternating LOW/HIGH
    (7, 0, 7, 0, 7, 0, 7, 0),  # Alternating HIGH/LOW
    (1, 2, 3, 4, 5, 6, 7, 0),  # Sequential
)


# =============================================================================
# Experiment Configuration
# =============================================================================

@dataclass(frozen=True)
class P11BExperimentConfig:
    """
    Configuration for a single Phase-11B experiment run.

    Attributes:
        intent: Opaque label (EXPRESS_LOSS, etc.)
        ontological_path: Tuple of layer names
        ppv_values: Tuple of 8 PPV values (0-7)
        render_mode: OPEN or GOVERNED
        variation_axis: Which axis is being varied
        variation_index: Index within the variation series
    """
    intent: str
    ontological_path: Tuple[str, ...]
    ppv_values: Tuple[int, ...]
    render_mode: RenderMode
    variation_axis: str
    variation_index: int

    def config_hash(self) -> str:
        """Compute deterministic hash of configuration."""
        canonical = (
            f"intent:{self.intent}|"
            f"path:{self.ontological_path}|"
            f"ppv:{self.ppv_values}|"
            f"mode:{self.render_mode.value}"
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Output Record
# =============================================================================

@dataclass(frozen=True)
class P11BOutputRecord:
    """
    Record of a single Phase-11B generation output.

    Captures structural/surface statistics only.
    """
    # Input
    intent: str
    ontological_path: Tuple[str, ...]
    ppv_values: Tuple[int, ...]
    render_mode: str
    config_hash: str

    # Template info
    template_family: str
    template_id: str
    variant_id: str
    slot_plan: str
    registry_type: str

    # Output
    output_hash: str
    output_length: int
    lexical_signature: Tuple[str, ...]

    # Metadata
    run_index: int
    is_fallback: bool


# =============================================================================
# Differentiation Signals
# =============================================================================

@dataclass(frozen=True)
class P11BDifferentiationSignals:
    """
    Differentiation signals for Phase-11B.

    Measures WHETHER outputs differ, not HOW GOOD they are.
    """
    # Hash uniqueness
    unique_hash_count: int
    total_output_count: int
    hash_uniqueness_ratio: float

    # Template uniqueness
    unique_template_ids: int
    template_uniqueness_ratio: float

    # Length variance
    min_length: int
    max_length: int
    length_range: int

    # Variation axis
    variation_axis: str

    # Family distribution
    family_distribution: Dict[str, int]


@dataclass(frozen=True)
class P11BStabilitySignals:
    """Stability signals for Phase-11B."""
    config_hash: str
    run_count: int
    unique_output_hashes: int
    unique_template_ids: int
    all_hashes_identical: bool
    all_templates_identical: bool
    mode: str


# =============================================================================
# Helper Functions
# =============================================================================

def make_artifact_hash() -> str:
    """Create a valid 64-char hex hash."""
    return hashlib.sha256(b"phase11b_evaluation").hexdigest()


def make_phase10_result(
    vc_facts: Tuple[str, ...] = ("VC-1", "VC-2", "VC-3"),
) -> Phase10Result:
    """Create a Phase10Result for evaluation."""
    return Phase10Result(
        artifact_hash=make_artifact_hash(),
        vc_facts=vc_facts,
        acoustic_regime="neutral",
        source_data={
            "vc_1_data": "observation_datum",
            "vc_2_data": "state_datum",
            "vc_3_data": "context_datum",
            "vc_4_data": "reference_datum",
            "vc_5_data": "marker_datum",
        },
    )


def compute_lexical_signature(output_text: str) -> Tuple[str, ...]:
    """Compute lexical signature (sorted unique tokens)."""
    tokens = output_text.split()
    return tuple(sorted(set(tokens)))


# =============================================================================
# Variation Matrix Generator
# =============================================================================

class P11BVariationMatrixGenerator:
    """
    Generates controlled variation experiments for Phase-11B.

    Varies ONE dimension at a time to measure differentiation.
    """

    DEFAULT_PATH: Tuple[str, ...] = ("THINKING", "DIRECTING", "REASONING")
    DEFAULT_PPV: Tuple[int, ...] = (3, 3, 3, 3, 3, 3, 3, 3)
    DEFAULT_MODE: RenderMode = RenderMode.GOVERNED

    def generate_path_variations(
        self,
        intent: str,
    ) -> List[P11BExperimentConfig]:
        """Generate experiments varying ontological path."""
        configs: List[P11BExperimentConfig] = []

        for i, layer in enumerate(ONTOLOGICAL_LAYER_ORDER):
            path = (layer.value,)

            config = P11BExperimentConfig(
                intent=intent,
                ontological_path=path,
                ppv_values=self.DEFAULT_PPV,
                render_mode=self.DEFAULT_MODE,
                variation_axis="ontological_path",
                variation_index=i,
            )
            configs.append(config)

        return configs

    def generate_ppv_variations(
        self,
        intent: str,
    ) -> List[P11BExperimentConfig]:
        """Generate experiments varying PPV values."""
        configs: List[P11BExperimentConfig] = []

        for i, ppv in enumerate(SAMPLE_PPV_CONFIGS):
            config = P11BExperimentConfig(
                intent=intent,
                ontological_path=self.DEFAULT_PATH,
                ppv_values=ppv,
                render_mode=self.DEFAULT_MODE,
                variation_axis="ppv_values",
                variation_index=i,
            )
            configs.append(config)

        return configs

    def generate_ppv_single_dim_variations(
        self,
        intent: str,
    ) -> List[P11BExperimentConfig]:
        """Generate experiments varying single PPV dimension at a time."""
        configs: List[P11BExperimentConfig] = []
        variation_index = 0

        base_ppv = list(self.DEFAULT_PPV)

        for dim in range(PPV_DIM_COUNT):
            # Vary to LOW
            ppv_low = base_ppv.copy()
            ppv_low[dim] = PPV_VALUE_MIN
            configs.append(P11BExperimentConfig(
                intent=intent,
                ontological_path=self.DEFAULT_PATH,
                ppv_values=tuple(ppv_low),
                render_mode=self.DEFAULT_MODE,
                variation_axis=f"ppv_dim_{dim}_low",
                variation_index=variation_index,
            ))
            variation_index += 1

            # Vary to HIGH
            ppv_high = base_ppv.copy()
            ppv_high[dim] = PPV_VALUE_MAX
            configs.append(P11BExperimentConfig(
                intent=intent,
                ontological_path=self.DEFAULT_PATH,
                ppv_values=tuple(ppv_high),
                render_mode=self.DEFAULT_MODE,
                variation_axis=f"ppv_dim_{dim}_high",
                variation_index=variation_index,
            ))
            variation_index += 1

        return configs

    def generate_mode_variations(
        self,
        intent: str,
    ) -> List[P11BExperimentConfig]:
        """Generate experiments varying mode."""
        return [
            P11BExperimentConfig(
                intent=intent,
                ontological_path=self.DEFAULT_PATH,
                ppv_values=self.DEFAULT_PPV,
                render_mode=RenderMode.GOVERNED,
                variation_axis="mode_governed",
                variation_index=0,
            ),
            P11BExperimentConfig(
                intent=intent,
                ontological_path=self.DEFAULT_PATH,
                ppv_values=self.DEFAULT_PPV,
                render_mode=RenderMode.OPEN,
                variation_axis="mode_open",
                variation_index=1,
            ),
        ]

    def generate_cross_axis_variations(
        self,
        intent: str,
    ) -> List[P11BExperimentConfig]:
        """Generate cross-axis variations (path × PPV)."""
        configs: List[P11BExperimentConfig] = []
        variation_index = 0

        # Sample paths
        paths = [
            ("THINKING",),
            ("ACTING",),
            ("FORMING",),
            ("DIRECTING",),
            ("REASONING",),
        ]

        # Sample PPVs
        ppvs = [
            (0, 0, 0, 0, 0, 0, 0, 0),
            (3, 3, 3, 3, 3, 3, 3, 3),
            (7, 7, 7, 7, 7, 7, 7, 7),
        ]

        for path in paths:
            for ppv in ppvs:
                configs.append(P11BExperimentConfig(
                    intent=intent,
                    ontological_path=path,
                    ppv_values=ppv,
                    render_mode=self.DEFAULT_MODE,
                    variation_axis="cross_axis",
                    variation_index=variation_index,
                ))
                variation_index += 1

        return configs


# =============================================================================
# Evaluation Harness
# =============================================================================

class Phase11BEvaluationHarness:
    """
    Phase-11B Evaluation Harness.

    Runs controlled variation experiments and computes differentiation signals.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        """Initialize the evaluation harness."""
        self._controller = Phase11BController()
        self._variation_generator = P11BVariationMatrixGenerator()
        self._output_records: List[P11BOutputRecord] = []
        self._differentiation_signals: List[P11BDifferentiationSignals] = []
        self._stability_signals: List[P11BStabilitySignals] = []

    @property
    def output_records(self) -> Tuple[P11BOutputRecord, ...]:
        """Return all captured output records."""
        return tuple(self._output_records)

    @property
    def differentiation_signals(self) -> Tuple[P11BDifferentiationSignals, ...]:
        """Return all computed differentiation signals."""
        return tuple(self._differentiation_signals)

    @property
    def stability_signals(self) -> Tuple[P11BStabilitySignals, ...]:
        """Return all computed stability signals."""
        return tuple(self._stability_signals)

    def run_experiment(
        self,
        config: P11BExperimentConfig,
        run_index: int = 0,
    ) -> P11BOutputRecord:
        """Run a single experiment and capture output."""
        # Create request
        request = Phase11BRequest(
            artifact_id=f"eval-{config.config_hash()[:8]}",
            artifact_hash=make_artifact_hash(),
            phase10_result=make_phase10_result(),
            ontological_path=config.ontological_path,
            ppv_values=config.ppv_values,
            render_mode=config.render_mode,
        )

        # Execute
        response = self._controller.execute(request)

        # Capture as record
        record = P11BOutputRecord(
            intent=config.intent,
            ontological_path=config.ontological_path,
            ppv_values=config.ppv_values,
            render_mode=config.render_mode.value,
            config_hash=config.config_hash(),
            template_family=response.template_key.family.value,
            template_id=response.template_id,
            variant_id=response.template_key.variant_id,
            slot_plan=response.template_key.slot_plan.value,
            registry_type=response.registry_used.value,
            output_hash=hashlib.sha256(response.output_text.encode()).hexdigest(),
            output_length=len(response.output_text),
            lexical_signature=compute_lexical_signature(response.output_text),
            run_index=run_index,
            is_fallback="FALLBACK" in response.template_id,
        )

        self._output_records.append(record)
        return record

    def run_variation_series(
        self,
        configs: Sequence[P11BExperimentConfig],
        variation_axis: str,
    ) -> Tuple[Tuple[P11BOutputRecord, ...], P11BDifferentiationSignals]:
        """Run a series of variation experiments."""
        records: List[P11BOutputRecord] = []

        for i, config in enumerate(configs):
            record = self.run_experiment(config, run_index=i)
            records.append(record)

        # Compute differentiation signals
        signals = self._compute_differentiation_signals(records, variation_axis)
        self._differentiation_signals.append(signals)

        return tuple(records), signals

    def _compute_differentiation_signals(
        self,
        records: Sequence[P11BOutputRecord],
        variation_axis: str,
    ) -> P11BDifferentiationSignals:
        """Compute differentiation signals from records."""
        if not records:
            return P11BDifferentiationSignals(
                unique_hash_count=0,
                total_output_count=0,
                hash_uniqueness_ratio=0.0,
                unique_template_ids=0,
                template_uniqueness_ratio=0.0,
                min_length=0,
                max_length=0,
                length_range=0,
                variation_axis=variation_axis,
                family_distribution={},
            )

        # Hash uniqueness
        all_hashes = [r.output_hash for r in records]
        unique_hashes = len(set(all_hashes))
        total = len(records)
        hash_ratio = unique_hashes / total if total > 0 else 0.0

        # Template uniqueness
        all_templates = [r.template_id for r in records]
        unique_templates = len(set(all_templates))
        template_ratio = unique_templates / total if total > 0 else 0.0

        # Length
        lengths = [r.output_length for r in records]
        min_len = min(lengths)
        max_len = max(lengths)

        # Family distribution
        family_dist: Dict[str, int] = {}
        for r in records:
            family_dist[r.template_family] = family_dist.get(r.template_family, 0) + 1

        return P11BDifferentiationSignals(
            unique_hash_count=unique_hashes,
            total_output_count=total,
            hash_uniqueness_ratio=hash_ratio,
            unique_template_ids=unique_templates,
            template_uniqueness_ratio=template_ratio,
            min_length=min_len,
            max_length=max_len,
            length_range=max_len - min_len,
            variation_axis=variation_axis,
            family_distribution=family_dist,
        )

    def run_stability_check(
        self,
        config: P11BExperimentConfig,
        run_count: int = 10,
    ) -> P11BStabilitySignals:
        """Run stability check with repeated identical runs."""
        records: List[P11BOutputRecord] = []

        for i in range(run_count):
            record = self.run_experiment(config, run_index=i)
            records.append(record)

        all_hashes = [r.output_hash for r in records]
        all_templates = [r.template_id for r in records]

        signals = P11BStabilitySignals(
            config_hash=config.config_hash(),
            run_count=run_count,
            unique_output_hashes=len(set(all_hashes)),
            unique_template_ids=len(set(all_templates)),
            all_hashes_identical=(len(set(all_hashes)) == 1),
            all_templates_identical=(len(set(all_templates)) == 1),
            mode=config.render_mode.value,
        )

        self._stability_signals.append(signals)
        return signals

    def run_full_evaluation(
        self,
        intents: Tuple[str, ...] = ("EXPRESS_LOSS", "EXPRESS_RESOLVE", "EXPRESS_CURIOSITY"),
        stability_runs: int = 10,
    ) -> Dict[str, Dict[str, P11BDifferentiationSignals]]:
        """Run full evaluation across all intents and variation axes."""
        results: Dict[str, Dict[str, P11BDifferentiationSignals]] = {}

        for intent in intents:
            results[intent] = {}

            # Path variations
            path_configs = self._variation_generator.generate_path_variations(intent)
            _, path_signals = self.run_variation_series(path_configs, "ontological_path")
            results[intent]["ontological_path"] = path_signals

            # PPV variations
            ppv_configs = self._variation_generator.generate_ppv_variations(intent)
            _, ppv_signals = self.run_variation_series(ppv_configs, "ppv_values")
            results[intent]["ppv_values"] = ppv_signals

            # Single dimension PPV
            dim_configs = self._variation_generator.generate_ppv_single_dim_variations(intent)
            _, dim_signals = self.run_variation_series(dim_configs, "ppv_single_dim")
            results[intent]["ppv_single_dim"] = dim_signals

            # Mode variations
            mode_configs = self._variation_generator.generate_mode_variations(intent)
            _, mode_signals = self.run_variation_series(mode_configs, "mode")
            results[intent]["mode"] = mode_signals

            # Cross-axis
            cross_configs = self._variation_generator.generate_cross_axis_variations(intent)
            _, cross_signals = self.run_variation_series(cross_configs, "cross_axis")
            results[intent]["cross_axis"] = cross_signals

        # Stability checks
        for intent in intents:
            baseline = P11BExperimentConfig(
                intent=intent,
                ontological_path=P11BVariationMatrixGenerator.DEFAULT_PATH,
                ppv_values=P11BVariationMatrixGenerator.DEFAULT_PPV,
                render_mode=RenderMode.GOVERNED,
                variation_axis="stability",
                variation_index=0,
            )
            self.run_stability_check(baseline, run_count=stability_runs)

        return results

    def clear(self) -> None:
        """Clear all stored records and signals."""
        self._output_records.clear()
        self._differentiation_signals.clear()
        self._stability_signals.clear()


# =============================================================================
# Evaluation Summary
# =============================================================================

@dataclass(frozen=True)
class P11BEvaluationSummary:
    """
    Summary of Phase-11B evaluation results.

    Contains ONLY structural observations.
    """
    # Totals
    total_experiments: int
    total_unique_outputs: int
    total_unique_templates: int

    # By variation axis
    path_uniqueness_ratio: float
    ppv_uniqueness_ratio: float
    mode_uniqueness_ratio: float
    cross_axis_uniqueness_ratio: float

    # Overall differentiation score
    overall_differentiation_score: float

    # Stability
    stability_score: float
    governed_deterministic: bool

    # Silent collapse
    no_silent_collapse: bool
    collapse_validation_details: str

    # Family clustering
    family_count: int
    family_is_strongest_axis: bool


def compute_evaluation_summary(
    harness: Phase11BEvaluationHarness,
) -> P11BEvaluationSummary:
    """Compute evaluation summary from harness results."""
    records = harness.output_records
    diff_signals = harness.differentiation_signals
    stability_signals = harness.stability_signals

    # Totals
    all_hashes = set(r.output_hash for r in records)
    all_templates = set(r.template_id for r in records)

    # Uniqueness by axis
    path_ratios = [s.hash_uniqueness_ratio for s in diff_signals if "path" in s.variation_axis]
    ppv_ratios = [s.hash_uniqueness_ratio for s in diff_signals if "ppv" in s.variation_axis]
    mode_ratios = [s.hash_uniqueness_ratio for s in diff_signals if "mode" in s.variation_axis]
    cross_ratios = [s.hash_uniqueness_ratio for s in diff_signals if "cross" in s.variation_axis]

    def avg(lst: List[float]) -> float:
        return sum(lst) / len(lst) if lst else 0.0

    # Overall differentiation score
    all_ratios = [s.hash_uniqueness_ratio for s in diff_signals]
    overall_score = avg(all_ratios)

    # Stability
    governed_stable = all(
        s.all_hashes_identical
        for s in stability_signals
        if s.mode == "governed"
    )
    stability_score = sum(
        1 for s in stability_signals if s.all_hashes_identical
    ) / len(stability_signals) if stability_signals else 0.0

    # Silent collapse validation
    collapse_result = validate_no_silent_collapse(RegistryType.GOVERNED)

    # Family clustering
    families = set(r.template_family for r in records)
    path_signals = [s for s in diff_signals if "path" in s.variation_axis]
    family_is_strongest = (
        avg(path_ratios) >= avg(ppv_ratios) if path_ratios and ppv_ratios else True
    )

    return P11BEvaluationSummary(
        total_experiments=len(records),
        total_unique_outputs=len(all_hashes),
        total_unique_templates=len(all_templates),
        path_uniqueness_ratio=avg(path_ratios),
        ppv_uniqueness_ratio=avg(ppv_ratios),
        mode_uniqueness_ratio=avg(mode_ratios),
        cross_axis_uniqueness_ratio=avg(cross_ratios),
        overall_differentiation_score=overall_score,
        stability_score=stability_score,
        governed_deterministic=governed_stable,
        no_silent_collapse=collapse_result.passed,
        collapse_validation_details=str(collapse_result.collision_details),
        family_count=len(families),
        family_is_strongest_axis=family_is_strongest,
    )


# =============================================================================
# Comparison with Phase-11A
# =============================================================================

def compare_with_phase11a() -> Dict[str, Dict[str, float]]:
    """
    Compare Phase-11B metrics with Phase-11A baseline.

    Returns comparison dictionary.
    """
    # Run Phase-11B evaluation
    harness = Phase11BEvaluationHarness()
    harness.run_full_evaluation()
    summary = compute_evaluation_summary(harness)

    # Phase-11A baseline values (from structural ceiling analysis)
    phase11a_baseline = {
        "overall_differentiation": 0.29,
        "stability": 1.0,
        "path_uniqueness": 0.0,
        "ppv_uniqueness": 0.0,
    }

    return {
        "phase11a": phase11a_baseline,
        "phase11b": {
            "overall_differentiation": summary.overall_differentiation_score,
            "stability": summary.stability_score,
            "path_uniqueness": summary.path_uniqueness_ratio,
            "ppv_uniqueness": summary.ppv_uniqueness_ratio,
            "no_silent_collapse": 1.0 if summary.no_silent_collapse else 0.0,
            "governed_deterministic": 1.0 if summary.governed_deterministic else 0.0,
        },
        "improvement": {
            "overall_differentiation": (
                summary.overall_differentiation_score - phase11a_baseline["overall_differentiation"]
            ),
            "stability": summary.stability_score - phase11a_baseline["stability"],
        },
    }


# =============================================================================
# Main Entry Point
# =============================================================================

def run_phase11b_evaluation() -> P11BEvaluationSummary:
    """
    Run full Phase-11B evaluation and return summary.

    This is the main entry point for evaluation.
    """
    harness = Phase11BEvaluationHarness()
    harness.run_full_evaluation()
    return compute_evaluation_summary(harness)


def print_evaluation_report() -> None:
    """Print a formatted evaluation report."""
    summary = run_phase11b_evaluation()
    comparison = compare_with_phase11a()

    print("=" * 70)
    print("Phase-11B Evaluation Report")
    print("=" * 70)
    print()
    print(f"Total Experiments:      {summary.total_experiments}")
    print(f"Unique Outputs:         {summary.total_unique_outputs}")
    print(f"Unique Templates:       {summary.total_unique_templates}")
    print()
    print("Differentiation Scores:")
    print(f"  Overall:              {summary.overall_differentiation_score:.4f}")
    print(f"  Path Uniqueness:      {summary.path_uniqueness_ratio:.4f}")
    print(f"  PPV Uniqueness:       {summary.ppv_uniqueness_ratio:.4f}")
    print(f"  Mode Uniqueness:      {summary.mode_uniqueness_ratio:.4f}")
    print(f"  Cross-Axis:           {summary.cross_axis_uniqueness_ratio:.4f}")
    print()
    print("Stability:")
    print(f"  Stability Score:      {summary.stability_score:.4f}")
    print(f"  GOVERNED Deterministic: {summary.governed_deterministic}")
    print()
    print("Silent Collapse Prevention:")
    print(f"  No Silent Collapse:   {summary.no_silent_collapse}")
    print()
    print("Family Clustering:")
    print(f"  Family Count:         {summary.family_count}")
    print(f"  Path is Strongest:    {summary.family_is_strongest_axis}")
    print()
    print("-" * 70)
    print("Comparison with Phase-11A:")
    print("-" * 70)
    print(f"  11A Overall Diff:     {comparison['phase11a']['overall_differentiation']:.4f}")
    print(f"  11B Overall Diff:     {comparison['phase11b']['overall_differentiation']:.4f}")
    print(f"  Improvement:          +{comparison['improvement']['overall_differentiation']:.4f}")
    print()
    print("=" * 70)
    print("SUCCESS CRITERIA:")
    print(f"  Differentiation >= 0.85: {'PASS' if summary.overall_differentiation_score >= 0.85 else 'FAIL'}")
    print(f"  Stability >= 0.95:       {'PASS' if summary.stability_score >= 0.95 else 'FAIL'}")
    print(f"  No Silent Collapse:      {'PASS' if summary.no_silent_collapse else 'FAIL'}")
    print(f"  Path Strongest Axis:     {'PASS' if summary.family_is_strongest_axis else 'FAIL'}")
    print("=" * 70)


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "PHASE11B_EVALUATION_VERSION",
    # Configuration
    "P11BExperimentConfig",
    "P11BVariationMatrixGenerator",
    # Records
    "P11BOutputRecord",
    # Signals
    "P11BDifferentiationSignals",
    "P11BStabilitySignals",
    # Harness
    "Phase11BEvaluationHarness",
    # Summary
    "P11BEvaluationSummary",
    # Functions
    "compute_evaluation_summary",
    "compare_with_phase11a",
    "run_phase11b_evaluation",
    "print_evaluation_report",
]


if __name__ == "__main__":
    print_evaluation_report()
