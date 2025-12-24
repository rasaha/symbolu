"""
Phase-11A: Generative Differentiation Evaluation Harness
=========================================================

WHAT THIS MEASURES:
    - Does changing ontological path produce different outputs?
    - Does changing PPV vector dimensions produce different outputs?
    - Does changing temperature produce different outputs?
    - Does changing mode (OPEN vs GOVERNED) produce different outputs?
    - Are outputs deterministic under identical conditions?

WHAT THIS DOES NOT MEASURE:
    - Quality of output
    - Correctness of output
    - Semantic meaning of output
    - Whether output is "good" or "bad"
    - Whether output is appropriate or inappropriate
    - Any scoring or ranking of outputs

CONSTRAINTS:
    - No ML/NLP imports
    - No embeddings or probability models
    - No semantic interpretation
    - No quality judgments
    - Only structural/surface statistics
    - Observation and recording only

DESIGN PRINCIPLES:
    - Controlled variation: Change one dimension at a time
    - Immutable records: All outputs captured as frozen dataclasses
    - Surface metrics only: Hash, length, token set
    - No interpretation: Raw data, no conclusions
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum, unique
from typing import (
    Dict,
    FrozenSet,
    List,
    Optional,
    Sequence,
    Tuple,
)


# =============================================================================
# Version
# =============================================================================

PHASE11A_VERSION = "1.0.0"


# =============================================================================
# Frozen Intent Set (Opaque Labels Only)
# =============================================================================

# These are OPAQUE LABELS - no interpretation, no semantics
# They are passed into Phase-11 unchanged
INTENTS: Tuple[str, ...] = (
    "EXPRESS_LOSS",
    "EXPRESS_RESOLVE",
    "EXPRESS_CURIOSITY",
)


# =============================================================================
# Ontological Layer Definitions (10-Layer Backbone)
# =============================================================================

@unique
class OntologicalLayer(str, Enum):
    """
    10-layer ontological backbone.

    These are structural layers for path selection.
    NO semantic interpretation is applied.
    """
    ACTING = "ACTING"                 # Layer 1
    TAGGING = "TAGGING"               # Layer 2
    FORMING = "FORMING"               # Layer 3
    THINKING = "THINKING"             # Layer 4
    DIRECTING = "DIRECTING"           # Layer 5
    REASONING = "REASONING"           # Layer 6
    PURPOSING = "PURPOSING"           # Layer 7
    META_OBSERVING = "META_OBSERVING" # Layer 8
    UNIFYING = "UNIFYING"             # Layer 9
    ABSOLVING = "ABSOLVING"           # Layer 10


# Fixed order for deterministic iteration
ONTOLOGICAL_LAYER_ORDER: Tuple[OntologicalLayer, ...] = (
    OntologicalLayer.EXECUTION,
    OntologicalLayer.IDENTITY,
    OntologicalLayer.STRUCTURE,
    OntologicalLayer.COGNITION,
    OntologicalLayer.AGENCY,
    OntologicalLayer.REASONING,
    OntologicalLayer.PURPOSE,
    OntologicalLayer.WITNESSES,
    OntologicalLayer.UNIFYING,
    OntologicalLayer.ABSOLVING,
)


# =============================================================================
# PPV Dimension Definitions
# =============================================================================

@unique
class PPVDimension(str, Enum):
    """
    PPV dimension axes (8 fixed dimensions).

    These are structural signal dimensions.
    NO semantic interpretation is applied.
    """
    EDGE_TENSION = "edge_tension"
    EDGE_RELEASE = "edge_release"
    ONSET_SHARPNESS = "onset_sharpness"
    SONORITY_LIFT = "sonority_lift"
    CONTINUITY = "continuity"
    DISCONTINUITY = "discontinuity"
    RHYTHMIC_IMPULSE = "rhythmic_impulse"
    STABILITY_PRESSURE = "stability_pressure"


# Fixed order for deterministic iteration
PPV_DIMENSION_ORDER: Tuple[PPVDimension, ...] = (
    PPVDimension.EDGE_TENSION,
    PPVDimension.EDGE_RELEASE,
    PPVDimension.ONSET_SHARPNESS,
    PPVDimension.SONORITY_LIFT,
    PPVDimension.CONTINUITY,
    PPVDimension.DISCONTINUITY,
    PPVDimension.RHYTHMIC_IMPULSE,
    PPVDimension.STABILITY_PRESSURE,
)

# Value bounds (0-7)
PPV_VALUE_MIN = 0
PPV_VALUE_MAX = 7


# =============================================================================
# Temperature Levels
# =============================================================================

@unique
class TemperatureLevel(str, Enum):
    """
    Temperature levels for generation.

    These are control parameters.
    NO semantic interpretation is applied.
    """
    LOW = "low"       # 0.2
    MID = "mid"       # 0.5
    HIGH = "high"     # 0.8


TEMPERATURE_VALUES: Dict[TemperatureLevel, float] = {
    TemperatureLevel.LOW: 0.2,
    TemperatureLevel.MID: 0.5,
    TemperatureLevel.HIGH: 0.8,
}


# =============================================================================
# Render Mode
# =============================================================================

@unique
class RenderMode(str, Enum):
    """
    Render mode for Phase-11 output gating.

    OPEN: Output released regardless of verifier
    GOVERNED: Output blocked if verifier fails
    """
    OPEN = "open"
    GOVERNED = "governed"


# =============================================================================
# Experiment Configuration (Frozen)
# =============================================================================

@dataclass(frozen=True)
class ExperimentConfig:
    """
    Immutable experiment configuration.

    Captures all parameters for a single generation run.
    """
    # Intent (opaque label)
    intent: str

    # Ontological path (layer sequence)
    ontological_path: Tuple[OntologicalLayer, ...]

    # PPV vector (8 dimensions, values 0-7)
    ppv_values: Tuple[int, ...]

    # Temperature
    temperature: float

    # Mode
    mode: RenderMode

    # Experiment metadata
    variation_axis: str  # Which axis is being varied
    variation_index: int  # Index within the variation series

    def __post_init__(self) -> None:
        """Validate experiment configuration."""
        # Validate intent
        if not isinstance(self.intent, str) or not self.intent.strip():
            raise ValueError("ExperimentConfig.intent must be non-empty string")

        # Validate ontological_path
        if not isinstance(self.ontological_path, tuple):
            raise ValueError("ExperimentConfig.ontological_path must be tuple")
        for layer in self.ontological_path:
            if not isinstance(layer, OntologicalLayer):
                raise ValueError(
                    f"ExperimentConfig.ontological_path elements must be OntologicalLayer, "
                    f"got {type(layer).__name__}"
                )

        # Validate ppv_values
        if not isinstance(self.ppv_values, tuple):
            raise ValueError("ExperimentConfig.ppv_values must be tuple")
        if len(self.ppv_values) != 8:
            raise ValueError(
                f"ExperimentConfig.ppv_values must have exactly 8 elements, "
                f"got {len(self.ppv_values)}"
            )
        for i, val in enumerate(self.ppv_values):
            if not isinstance(val, int):
                raise ValueError(f"ExperimentConfig.ppv_values[{i}] must be int")
            if val < PPV_VALUE_MIN or val > PPV_VALUE_MAX:
                raise ValueError(
                    f"ExperimentConfig.ppv_values[{i}] must be in range "
                    f"[{PPV_VALUE_MIN}, {PPV_VALUE_MAX}], got {val}"
                )

        # Validate temperature
        if not isinstance(self.temperature, (int, float)):
            raise ValueError("ExperimentConfig.temperature must be numeric")
        if self.temperature < 0.0 or self.temperature > 1.0:
            raise ValueError(
                f"ExperimentConfig.temperature must be in range [0.0, 1.0], "
                f"got {self.temperature}"
            )

        # Validate mode
        if not isinstance(self.mode, RenderMode):
            raise ValueError("ExperimentConfig.mode must be RenderMode")

    def config_hash(self) -> str:
        """Compute deterministic hash of configuration."""
        canonical = (
            f"intent:{self.intent}|"
            f"path:{tuple(l.value for l in self.ontological_path)}|"
            f"ppv:{self.ppv_values}|"
            f"temp:{self.temperature}|"
            f"mode:{self.mode.value}"
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Output Record (Frozen, Immutable)
# =============================================================================

@dataclass(frozen=True)
class Phase11OutputRecord:
    """
    Immutable record of a single Phase-11 generation output.

    This captures ONLY structural/surface statistics.
    NO semantic interpretation.
    NO quality scoring.
    NO ranking.
    """
    # Input configuration
    intent: str
    ontological_path: Tuple[str, ...]  # Layer names as strings
    ppv_vector: Tuple[int, ...]
    temperature: float
    mode: str

    # Output characteristics (surface only)
    output_hash: str          # SHA256 of output text
    output_length: int        # Character count
    lexical_signature: Tuple[str, ...]  # Sorted unique tokens

    # Metadata
    config_hash: str          # Hash of input configuration
    run_index: int            # Index within experiment series

    def __post_init__(self) -> None:
        """Validate output record."""
        # Validate intent
        if not isinstance(self.intent, str):
            raise ValueError("Phase11OutputRecord.intent must be str")

        # Validate ontological_path
        if not isinstance(self.ontological_path, tuple):
            raise ValueError("Phase11OutputRecord.ontological_path must be tuple")

        # Validate ppv_vector
        if not isinstance(self.ppv_vector, tuple):
            raise ValueError("Phase11OutputRecord.ppv_vector must be tuple")
        if len(self.ppv_vector) != 8:
            raise ValueError("Phase11OutputRecord.ppv_vector must have 8 elements")

        # Validate temperature
        if not isinstance(self.temperature, (int, float)):
            raise ValueError("Phase11OutputRecord.temperature must be numeric")

        # Validate mode
        if not isinstance(self.mode, str):
            raise ValueError("Phase11OutputRecord.mode must be str")

        # Validate output_hash
        if not isinstance(self.output_hash, str) or len(self.output_hash) != 64:
            raise ValueError("Phase11OutputRecord.output_hash must be 64-char hex")

        # Validate output_length
        if not isinstance(self.output_length, int) or self.output_length < 0:
            raise ValueError("Phase11OutputRecord.output_length must be non-negative int")

        # Validate lexical_signature
        if not isinstance(self.lexical_signature, tuple):
            raise ValueError("Phase11OutputRecord.lexical_signature must be tuple")


# =============================================================================
# Evaluation Signals (Non-Semantic Only)
# =============================================================================

@dataclass(frozen=True)
class DifferentiationSignals:
    """
    Non-semantic differentiation signals.

    These signals measure WHETHER outputs differ, not HOW GOOD they are.
    NO quality judgments.
    NO scoring.
    NO ranking.
    """
    # Hash uniqueness
    unique_hash_count: int
    total_output_count: int
    hash_uniqueness_ratio: float  # unique_hashes / total_outputs

    # Length variance
    min_length: int
    max_length: int
    length_range: int  # max - min

    # Token set statistics
    common_tokens: Tuple[str, ...]     # Tokens appearing in ALL outputs
    variable_tokens: Tuple[str, ...]   # Tokens appearing in SOME outputs
    token_overlap_ratio: float         # common / (common + variable)

    # Variation axis
    variation_axis: str

    def __post_init__(self) -> None:
        """Validate differentiation signals."""
        if self.unique_hash_count < 0:
            raise ValueError("unique_hash_count must be non-negative")
        if self.total_output_count < 0:
            raise ValueError("total_output_count must be non-negative")
        if self.min_length < 0:
            raise ValueError("min_length must be non-negative")
        if self.max_length < 0:
            raise ValueError("max_length must be non-negative")


@dataclass(frozen=True)
class StabilitySignals:
    """
    Determinism/stability signals for repeated identical runs.

    Measures whether same input produces same output.
    NO quality judgments.
    """
    # Run parameters
    config_hash: str
    run_count: int

    # Stability metrics
    unique_output_hashes: int      # Should be 1 for deterministic
    all_hashes_identical: bool     # True if fully deterministic

    # Mode
    mode: str

    def __post_init__(self) -> None:
        """Validate stability signals."""
        if self.run_count < 1:
            raise ValueError("run_count must be at least 1")
        if self.unique_output_hashes < 1:
            raise ValueError("unique_output_hashes must be at least 1")


# =============================================================================
# Mock Generator (Structural Variation Simulator)
# =============================================================================

class MockPhase11Generator:
    """
    Mock Phase-11 generator for evaluation harness testing.

    This generator produces outputs that vary based on input parameters,
    allowing the harness to verify it can detect differentiation.

    The outputs are DETERMINISTIC given identical inputs.
    NO ML/NLP.
    NO randomness (unless mode is OPEN and seed is None).
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        """
        Initialize the mock generator.

        Args:
            seed: Optional seed for reproducibility. If None and mode is OPEN,
                  minimal variation may occur. If provided, output is deterministic.
        """
        self._seed = seed

    def generate(self, config: ExperimentConfig) -> str:
        """
        Generate output text based on configuration.

        This produces structured output that varies based on:
            - Intent (opaque label included in output)
            - Ontological path (layer names included)
            - PPV values (numeric summary included)
            - Temperature (affects output structure deterministically)
            - Mode (affects output format)

        Args:
            config: The experiment configuration.

        Returns:
            Output text (deterministic given identical config + seed).
        """
        # Build deterministic output components
        parts: List[str] = []

        # Intent marker
        parts.append(f"[INTENT:{config.intent}]")

        # Ontological path
        path_str = "->".join(layer.value for layer in config.ontological_path)
        parts.append(f"[PATH:{path_str}]")

        # PPV summary
        ppv_sum = sum(config.ppv_values)
        ppv_str = ",".join(str(v) for v in config.ppv_values)
        parts.append(f"[PPV:{ppv_sum}|{ppv_str}]")

        # Temperature marker
        temp_marker = "L" if config.temperature < 0.3 else ("M" if config.temperature < 0.7 else "H")
        parts.append(f"[T:{temp_marker}:{config.temperature:.2f}]")

        # Mode marker
        parts.append(f"[MODE:{config.mode.value.upper()}]")

        # Generate content based on temperature (deterministic variation)
        # Higher temperature = more structural elements
        content_parts: List[str] = []

        # Base content from intent
        content_parts.append(f"output_{config.intent.lower()}")

        # Add layer-derived tokens
        for layer in config.ontological_path:
            content_parts.append(f"layer_{layer.value.lower()}")

        # Add PPV-derived tokens (based on dominant dimensions)
        for i, val in enumerate(config.ppv_values):
            if val > 4:  # High values add tokens
                dim_name = PPV_DIMENSION_ORDER[i].value
                content_parts.append(f"ppv_{dim_name}_{val}")

        # Temperature affects number of repetitions
        if config.temperature > 0.5:
            # Higher temp: add more structural variation
            for i, layer in enumerate(config.ontological_path):
                if i < int(config.temperature * 5):
                    content_parts.append(f"ext_{layer.value.lower()}_{i}")

        # Mode affects format
        if config.mode == RenderMode.GOVERNED:
            content_parts.append("governed_output")
        else:
            content_parts.append("open_output")

        # Combine content
        content = " ".join(content_parts)
        parts.append(content)

        # Final output
        output = " ".join(parts)

        return output


# =============================================================================
# Controlled Variation Matrix Generator
# =============================================================================

class VariationMatrixGenerator:
    """
    Generates controlled variation experiments.

    For each intent, generates experiment configurations that vary
    EXACTLY ONE dimension at a time:
        - Ontological path
        - PPV vector (single dimension)
        - Temperature
        - Mode

    All other parameters remain identical.
    """

    # Default baseline configuration
    DEFAULT_PATH: Tuple[OntologicalLayer, ...] = (
        OntologicalLayer.STRUCTURE,
        OntologicalLayer.COGNITION,
        OntologicalLayer.AGENCY,
    )
    DEFAULT_PPV: Tuple[int, ...] = (3, 3, 3, 3, 3, 3, 3, 3)
    DEFAULT_TEMP: float = TEMPERATURE_VALUES[TemperatureLevel.MID]
    DEFAULT_MODE: RenderMode = RenderMode.GOVERNED

    def __init__(self) -> None:
        """Initialize the variation matrix generator."""
        pass

    def generate_path_variations(
        self,
        intent: str,
    ) -> List[ExperimentConfig]:
        """
        Generate experiments varying ontological path only.

        Args:
            intent: The intent label.

        Returns:
            List of experiment configurations with varying paths.
        """
        configs: List[ExperimentConfig] = []

        # Generate paths starting from each layer
        for i, start_layer in enumerate(ONTOLOGICAL_LAYER_ORDER):
            # Create a 3-layer path starting from this layer
            path_indices = [
                i,
                (i + 1) % len(ONTOLOGICAL_LAYER_ORDER),
                (i + 2) % len(ONTOLOGICAL_LAYER_ORDER),
            ]
            path = tuple(ONTOLOGICAL_LAYER_ORDER[idx] for idx in path_indices)

            config = ExperimentConfig(
                intent=intent,
                ontological_path=path,
                ppv_values=self.DEFAULT_PPV,
                temperature=self.DEFAULT_TEMP,
                mode=self.DEFAULT_MODE,
                variation_axis="ontological_path",
                variation_index=i,
            )
            configs.append(config)

        return configs

    def generate_ppv_variations(
        self,
        intent: str,
    ) -> List[ExperimentConfig]:
        """
        Generate experiments varying single PPV dimension.

        For each PPV dimension, generates configurations with that
        dimension set to MIN and MAX, while others remain at baseline.

        Args:
            intent: The intent label.

        Returns:
            List of experiment configurations with varying PPV.
        """
        configs: List[ExperimentConfig] = []
        variation_index = 0

        for dim_idx, dimension in enumerate(PPV_DIMENSION_ORDER):
            # Variation: dimension at minimum (0)
            ppv_min = list(self.DEFAULT_PPV)
            ppv_min[dim_idx] = PPV_VALUE_MIN

            config_min = ExperimentConfig(
                intent=intent,
                ontological_path=self.DEFAULT_PATH,
                ppv_values=tuple(ppv_min),
                temperature=self.DEFAULT_TEMP,
                mode=self.DEFAULT_MODE,
                variation_axis=f"ppv_{dimension.value}_min",
                variation_index=variation_index,
            )
            configs.append(config_min)
            variation_index += 1

            # Variation: dimension at maximum (7)
            ppv_max = list(self.DEFAULT_PPV)
            ppv_max[dim_idx] = PPV_VALUE_MAX

            config_max = ExperimentConfig(
                intent=intent,
                ontological_path=self.DEFAULT_PATH,
                ppv_values=tuple(ppv_max),
                temperature=self.DEFAULT_TEMP,
                mode=self.DEFAULT_MODE,
                variation_axis=f"ppv_{dimension.value}_max",
                variation_index=variation_index,
            )
            configs.append(config_max)
            variation_index += 1

        return configs

    def generate_temperature_variations(
        self,
        intent: str,
    ) -> List[ExperimentConfig]:
        """
        Generate experiments varying temperature only.

        Args:
            intent: The intent label.

        Returns:
            List of experiment configurations with varying temperature.
        """
        configs: List[ExperimentConfig] = []

        for i, (level, temp_value) in enumerate(TEMPERATURE_VALUES.items()):
            config = ExperimentConfig(
                intent=intent,
                ontological_path=self.DEFAULT_PATH,
                ppv_values=self.DEFAULT_PPV,
                temperature=temp_value,
                mode=self.DEFAULT_MODE,
                variation_axis=f"temperature_{level.value}",
                variation_index=i,
            )
            configs.append(config)

        return configs

    def generate_mode_variations(
        self,
        intent: str,
    ) -> List[ExperimentConfig]:
        """
        Generate experiments varying mode only.

        Args:
            intent: The intent label.

        Returns:
            List of experiment configurations with varying mode.
        """
        configs: List[ExperimentConfig] = []

        for i, mode in enumerate([RenderMode.GOVERNED, RenderMode.OPEN]):
            config = ExperimentConfig(
                intent=intent,
                ontological_path=self.DEFAULT_PATH,
                ppv_values=self.DEFAULT_PPV,
                temperature=self.DEFAULT_TEMP,
                mode=mode,
                variation_axis=f"mode_{mode.value}",
                variation_index=i,
            )
            configs.append(config)

        return configs

    def generate_all_variations(
        self,
        intent: str,
    ) -> Dict[str, List[ExperimentConfig]]:
        """
        Generate all variation experiments for an intent.

        Args:
            intent: The intent label.

        Returns:
            Dictionary mapping variation type to list of configurations.
        """
        return {
            "ontological_path": self.generate_path_variations(intent),
            "ppv_dimension": self.generate_ppv_variations(intent),
            "temperature": self.generate_temperature_variations(intent),
            "mode": self.generate_mode_variations(intent),
        }

    def generate_full_matrix(self) -> Dict[str, Dict[str, List[ExperimentConfig]]]:
        """
        Generate full variation matrix for all intents.

        Returns:
            Nested dictionary: intent -> variation_type -> configurations.
        """
        matrix: Dict[str, Dict[str, List[ExperimentConfig]]] = {}

        for intent in INTENTS:
            matrix[intent] = self.generate_all_variations(intent)

        return matrix


# =============================================================================
# Output Capture
# =============================================================================

def compute_output_hash(output_text: str) -> str:
    """
    Compute deterministic hash of output text.

    Args:
        output_text: The output text to hash.

    Returns:
        64-character hex SHA256 hash.
    """
    return hashlib.sha256(output_text.encode("utf-8")).hexdigest()


def compute_lexical_signature(output_text: str) -> Tuple[str, ...]:
    """
    Compute lexical signature (sorted unique tokens).

    Tokenization is simple whitespace split - NO NLP.

    Args:
        output_text: The output text to analyze.

    Returns:
        Tuple of sorted unique tokens.
    """
    # Simple whitespace tokenization (no NLP)
    tokens = output_text.split()

    # Remove duplicates and sort
    unique_tokens = sorted(set(tokens))

    return tuple(unique_tokens)


def capture_output(
    config: ExperimentConfig,
    output_text: str,
    run_index: int,
) -> Phase11OutputRecord:
    """
    Capture output as immutable record.

    Args:
        config: The experiment configuration.
        output_text: The generated output text.
        run_index: The run index within experiment series.

    Returns:
        Immutable Phase11OutputRecord.
    """
    return Phase11OutputRecord(
        intent=config.intent,
        ontological_path=tuple(layer.value for layer in config.ontological_path),
        ppv_vector=config.ppv_values,
        temperature=config.temperature,
        mode=config.mode.value,
        output_hash=compute_output_hash(output_text),
        output_length=len(output_text),
        lexical_signature=compute_lexical_signature(output_text),
        config_hash=config.config_hash(),
        run_index=run_index,
    )


# =============================================================================
# Evaluation Signal Computation (Non-Semantic Only)
# =============================================================================

def compute_differentiation_signals(
    records: Sequence[Phase11OutputRecord],
    variation_axis: str,
) -> DifferentiationSignals:
    """
    Compute differentiation signals from output records.

    This measures WHETHER outputs differ, not HOW GOOD they are.
    NO quality judgments.

    Args:
        records: Sequence of output records to analyze.
        variation_axis: The axis being varied.

    Returns:
        DifferentiationSignals with non-semantic metrics.
    """
    if not records:
        return DifferentiationSignals(
            unique_hash_count=0,
            total_output_count=0,
            hash_uniqueness_ratio=0.0,
            min_length=0,
            max_length=0,
            length_range=0,
            common_tokens=(),
            variable_tokens=(),
            token_overlap_ratio=0.0,
            variation_axis=variation_axis,
        )

    # Hash uniqueness
    all_hashes = [r.output_hash for r in records]
    unique_hashes = set(all_hashes)
    unique_hash_count = len(unique_hashes)
    total_count = len(records)
    hash_uniqueness_ratio = unique_hash_count / total_count if total_count > 0 else 0.0

    # Length variance
    lengths = [r.output_length for r in records]
    min_length = min(lengths)
    max_length = max(lengths)
    length_range = max_length - min_length

    # Token set analysis
    all_token_sets = [set(r.lexical_signature) for r in records]

    # Common tokens: appear in ALL outputs
    common_tokens_set = set.intersection(*all_token_sets) if all_token_sets else set()

    # Variable tokens: appear in SOME but not ALL outputs
    all_tokens = set.union(*all_token_sets) if all_token_sets else set()
    variable_tokens_set = all_tokens - common_tokens_set

    # Token overlap ratio
    total_unique_tokens = len(all_tokens)
    token_overlap_ratio = (
        len(common_tokens_set) / total_unique_tokens
        if total_unique_tokens > 0 else 0.0
    )

    return DifferentiationSignals(
        unique_hash_count=unique_hash_count,
        total_output_count=total_count,
        hash_uniqueness_ratio=hash_uniqueness_ratio,
        min_length=min_length,
        max_length=max_length,
        length_range=length_range,
        common_tokens=tuple(sorted(common_tokens_set)),
        variable_tokens=tuple(sorted(variable_tokens_set)),
        token_overlap_ratio=token_overlap_ratio,
        variation_axis=variation_axis,
    )


def compute_stability_signals(
    records: Sequence[Phase11OutputRecord],
    config_hash: str,
    mode: str,
) -> StabilitySignals:
    """
    Compute stability signals from repeated identical runs.

    Args:
        records: Sequence of output records from identical configurations.
        config_hash: The configuration hash.
        mode: The render mode.

    Returns:
        StabilitySignals indicating determinism.
    """
    if not records:
        return StabilitySignals(
            config_hash=config_hash,
            run_count=0,
            unique_output_hashes=0,
            all_hashes_identical=True,
            mode=mode,
        )

    all_hashes = [r.output_hash for r in records]
    unique_hashes = set(all_hashes)

    return StabilitySignals(
        config_hash=config_hash,
        run_count=len(records),
        unique_output_hashes=len(unique_hashes),
        all_hashes_identical=(len(unique_hashes) == 1),
        mode=mode,
    )


# =============================================================================
# Evaluation Harness
# =============================================================================

class Phase11AEvaluationHarness:
    """
    Phase-11A Generative Differentiation Evaluation Harness.

    This harness:
        - Runs controlled variation experiments
        - Captures outputs as immutable records
        - Computes non-semantic differentiation signals
        - Verifies determinism

    This harness does NOT:
        - Score quality
        - Judge correctness
        - Interpret semantics
        - Rank outputs
    """

    def __init__(
        self,
        generator: Optional[MockPhase11Generator] = None,
        seed: Optional[int] = None,
    ) -> None:
        """
        Initialize the evaluation harness.

        Args:
            generator: Optional mock generator. If None, creates default.
            seed: Optional seed for reproducibility.
        """
        self._generator = generator if generator is not None else MockPhase11Generator(seed=seed)
        self._seed = seed
        self._variation_generator = VariationMatrixGenerator()

        # Storage for records and signals
        self._output_records: List[Phase11OutputRecord] = []
        self._differentiation_signals: List[DifferentiationSignals] = []
        self._stability_signals: List[StabilitySignals] = []

    @property
    def output_records(self) -> Tuple[Phase11OutputRecord, ...]:
        """Return all captured output records."""
        return tuple(self._output_records)

    @property
    def differentiation_signals(self) -> Tuple[DifferentiationSignals, ...]:
        """Return all computed differentiation signals."""
        return tuple(self._differentiation_signals)

    @property
    def stability_signals(self) -> Tuple[StabilitySignals, ...]:
        """Return all computed stability signals."""
        return tuple(self._stability_signals)

    def run_experiment(
        self,
        config: ExperimentConfig,
        run_index: int = 0,
    ) -> Phase11OutputRecord:
        """
        Run a single experiment and capture output.

        Args:
            config: The experiment configuration.
            run_index: The run index.

        Returns:
            Immutable output record.
        """
        # Generate output
        output_text = self._generator.generate(config)

        # Capture as immutable record
        record = capture_output(config, output_text, run_index)

        # Store
        self._output_records.append(record)

        return record

    def run_variation_series(
        self,
        configs: Sequence[ExperimentConfig],
        variation_axis: str,
    ) -> Tuple[Tuple[Phase11OutputRecord, ...], DifferentiationSignals]:
        """
        Run a series of variation experiments.

        Args:
            configs: Sequence of experiment configurations.
            variation_axis: The axis being varied.

        Returns:
            Tuple of (output records, differentiation signals).
        """
        records: List[Phase11OutputRecord] = []

        for i, config in enumerate(configs):
            record = self.run_experiment(config, run_index=i)
            records.append(record)

        # Compute differentiation signals
        signals = compute_differentiation_signals(records, variation_axis)
        self._differentiation_signals.append(signals)

        return tuple(records), signals

    def run_determinism_check(
        self,
        config: ExperimentConfig,
        run_count: int = 5,
    ) -> StabilitySignals:
        """
        Run determinism check with repeated identical runs.

        Args:
            config: The experiment configuration.
            run_count: Number of repeated runs.

        Returns:
            Stability signals.
        """
        records: List[Phase11OutputRecord] = []

        for i in range(run_count):
            record = self.run_experiment(config, run_index=i)
            records.append(record)

        # Compute stability signals
        signals = compute_stability_signals(
            records,
            config_hash=config.config_hash(),
            mode=config.mode.value,
        )
        self._stability_signals.append(signals)

        return signals

    def run_full_evaluation(
        self,
        determinism_runs: int = 3,
    ) -> Dict[str, Dict[str, DifferentiationSignals]]:
        """
        Run full evaluation across all intents and variation axes.

        Args:
            determinism_runs: Number of runs for determinism check.

        Returns:
            Nested dictionary of differentiation signals.
        """
        results: Dict[str, Dict[str, DifferentiationSignals]] = {}

        for intent in INTENTS:
            results[intent] = {}

            # Get all variation configurations
            variations = self._variation_generator.generate_all_variations(intent)

            for variation_type, configs in variations.items():
                _, signals = self.run_variation_series(configs, variation_type)
                results[intent][variation_type] = signals

        # Run determinism checks for baseline configuration
        for intent in INTENTS:
            baseline_config = ExperimentConfig(
                intent=intent,
                ontological_path=VariationMatrixGenerator.DEFAULT_PATH,
                ppv_values=VariationMatrixGenerator.DEFAULT_PPV,
                temperature=VariationMatrixGenerator.DEFAULT_TEMP,
                mode=VariationMatrixGenerator.DEFAULT_MODE,
                variation_axis="determinism_check",
                variation_index=0,
            )
            self.run_determinism_check(baseline_config, run_count=determinism_runs)

        return results

    def clear(self) -> None:
        """Clear all stored records and signals."""
        self._output_records.clear()
        self._differentiation_signals.clear()
        self._stability_signals.clear()


# =============================================================================
# Summary Report (Structural Only, No Judgments)
# =============================================================================

@dataclass(frozen=True)
class EvaluationSummary:
    """
    Summary of evaluation results.

    This contains ONLY structural observations.
    NO quality judgments.
    NO interpretations.
    """
    # Totals
    total_experiments: int
    total_unique_outputs: int

    # By variation axis
    path_variations_unique_ratio: float
    ppv_variations_unique_ratio: float
    temperature_variations_unique_ratio: float
    mode_variations_unique_ratio: float

    # Determinism
    governed_mode_deterministic: bool
    open_mode_deterministic: bool


def compute_evaluation_summary(
    harness: Phase11AEvaluationHarness,
) -> EvaluationSummary:
    """
    Compute evaluation summary from harness results.

    Args:
        harness: The evaluation harness with results.

    Returns:
        Evaluation summary with structural observations only.
    """
    records = harness.output_records
    diff_signals = harness.differentiation_signals
    stability_signals = harness.stability_signals

    # Total unique outputs
    all_hashes = set(r.output_hash for r in records)

    # Compute average uniqueness by variation axis
    path_ratios: List[float] = []
    ppv_ratios: List[float] = []
    temp_ratios: List[float] = []
    mode_ratios: List[float] = []

    for sig in diff_signals:
        axis = sig.variation_axis
        if axis == "ontological_path":
            path_ratios.append(sig.hash_uniqueness_ratio)
        elif axis.startswith("ppv_"):
            ppv_ratios.append(sig.hash_uniqueness_ratio)
        elif axis.startswith("temperature_"):
            temp_ratios.append(sig.hash_uniqueness_ratio)
        elif axis.startswith("mode_"):
            mode_ratios.append(sig.hash_uniqueness_ratio)

    # Compute averages
    def avg(lst: List[float]) -> float:
        return sum(lst) / len(lst) if lst else 0.0

    # Determinism by mode
    governed_deterministic = all(
        s.all_hashes_identical for s in stability_signals
        if s.mode == "governed"
    )
    open_deterministic = all(
        s.all_hashes_identical for s in stability_signals
        if s.mode == "open"
    )

    return EvaluationSummary(
        total_experiments=len(records),
        total_unique_outputs=len(all_hashes),
        path_variations_unique_ratio=avg(path_ratios),
        ppv_variations_unique_ratio=avg(ppv_ratios),
        temperature_variations_unique_ratio=avg(temp_ratios),
        mode_variations_unique_ratio=avg(mode_ratios),
        governed_mode_deterministic=governed_deterministic,
        open_mode_deterministic=open_deterministic,
    )


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "PHASE11A_VERSION",
    # Constants
    "INTENTS",
    "ONTOLOGICAL_LAYER_ORDER",
    "PPV_DIMENSION_ORDER",
    "PPV_VALUE_MIN",
    "PPV_VALUE_MAX",
    "TEMPERATURE_VALUES",
    # Enums
    "OntologicalLayer",
    "PPVDimension",
    "TemperatureLevel",
    "RenderMode",
    # Configuration
    "ExperimentConfig",
    # Output Records
    "Phase11OutputRecord",
    # Signals
    "DifferentiationSignals",
    "StabilitySignals",
    # Generator
    "MockPhase11Generator",
    # Variation Generator
    "VariationMatrixGenerator",
    # Harness
    "Phase11AEvaluationHarness",
    # Summary
    "EvaluationSummary",
    # Functions
    "compute_output_hash",
    "compute_lexical_signature",
    "capture_output",
    "compute_differentiation_signals",
    "compute_stability_signals",
    "compute_evaluation_summary",
]
