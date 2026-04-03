"""
Phase-8A Rendering Layer - Type Definitions

All types are frozen (immutable) dataclasses.
All collections are immutable (tuple, frozenset).

Contract: docs/contracts/PHASE_8A_RENDERING_CONTRACT.md
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, Dict, Any, FrozenSet
import hashlib
import json

# Re-export Phase-7 types that we consume
from symbolu_extensions.phases.phase7_targeted_generation.types import (
    RankedResult,
    TrajectoryResult,
    TrajectoryStep,
)


class RenderModality(Enum):
    """Output modality for renderers."""
    PHONETIC = "phonetic"    # IPA or phonetic transcription
    ACOUSTIC = "acoustic"    # Audio parameters or waveform specification
    VISUAL = "visual"        # Graphical representation specification
    SYMBOLIC = "symbolic"    # Abstract symbol sequence
    NUMERIC = "numeric"      # Numeric encoding


class RenderErrorType(Enum):
    """Error types for rendering failures."""
    UNKNOWN_RENDERER = "UNKNOWN_RENDERER"
    INVALID_CONFIG = "INVALID_CONFIG"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    MALFORMED_INPUT = "MALFORMED_INPUT"
    EMPTY_SEQUENCE = "EMPTY_SEQUENCE"
    EMPTY_TRAJECTORY = "EMPTY_TRAJECTORY"
    SEQUENCE_TRAJECTORY_MISMATCH = "SEQUENCE_TRAJECTORY_MISMATCH"
    INVALID_TOKEN = "INVALID_TOKEN"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class RendererConfig:
    """Configuration for a renderer."""
    output_format: str
    precision: Optional[int] = None
    include_metadata: bool = False
    # Note: custom_params would need FrozenDict but we use tuple of pairs for immutability
    custom_params: Tuple[Tuple[str, Any], ...] = ()


@dataclass(frozen=True)
class RenderInput:
    """Input to a renderer - wraps Phase-7 RankedResult."""
    ranked_result: RankedResult
    renderer_id: str
    renderer_config: Optional[RendererConfig] = None


@dataclass(frozen=True)
class RenderError:
    """Error details for failed rendering."""
    error_type: RenderErrorType
    error_message: str
    recoverable: bool = False  # Always false per contract


@dataclass(frozen=True)
class ValidationResult:
    """Result of config validation."""
    is_valid: bool
    error_type: Optional[RenderErrorType] = None
    error_details: Optional[str] = None


# --- Artifact Types ---

@dataclass(frozen=True)
class PhoneticArtifact:
    """Phonetic rendering artifact."""
    transcription: Tuple[str, ...]      # IPA symbols per token
    syllable_breaks: Tuple[int, ...]    # Indices where syllables break
    stress_pattern: Tuple[int, ...]     # Stress markers (0=unstressed, 1=stressed)


@dataclass(frozen=True)
class AcousticArtifact:
    """Acoustic rendering artifact."""
    sample_rate: int                    # Samples per second
    duration_ms: Tuple[int, ...]        # Duration per token in milliseconds
    frequency_hz: Tuple[float, ...]     # Base frequency per token
    amplitude: Tuple[float, ...]        # Amplitude per token (from magnitude)
    waveform_type: str                  # "sine" | "square" | "sawtooth" | "triangle"


@dataclass(frozen=True)
class VisualElement:
    """Single visual element in a visual artifact."""
    element_type: str                   # "circle" | "line" | "rectangle" | "arc"
    x: float                            # X position
    y: float                            # Y position
    size: float                         # Size (from magnitude)
    color_index: int                    # Index into deterministic palette
    rotation: float                     # Rotation in degrees


@dataclass(frozen=True)
class VisualArtifact:
    """Visual rendering artifact."""
    width: int                          # Canvas width in units
    height: int                         # Canvas height in units
    elements: Tuple[VisualElement, ...] # Ordered visual elements


@dataclass(frozen=True)
class SymbolicArtifact:
    """Symbolic rendering artifact."""
    symbols: Tuple[str, ...]                    # Abstract symbol per token
    groupings: Tuple[Tuple[int, ...], ...]      # Symbol grouping indices
    connectors: Tuple[str, ...]                 # Connector types between groups


@dataclass(frozen=True)
class NumericArtifact:
    """Numeric encoding artifact."""
    encoding: Tuple[float, ...]         # Numeric encoding per token
    checksum: int                       # Deterministic checksum of encoding


# Union type for artifacts (Python 3.9 compatible)
RenderArtifact = (
    PhoneticArtifact | AcousticArtifact | VisualArtifact |
    SymbolicArtifact | NumericArtifact
)


@dataclass(frozen=True)
class RenderMetadata:
    """Metadata about the rendered input."""
    sequence_length: int
    step_count: int
    final_magnitude: float
    event_counts: Tuple[Tuple[str, int], ...]  # (("reset", n), ("modulate", m))
    magnitude_range: Tuple[float, float]       # (min, max)


@dataclass(frozen=True)
class RenderOutput:
    """Output from a renderer."""
    renderer_id: str
    input_hash: str                             # Deterministic hash of input
    modality: RenderModality
    artifact: Optional[RenderArtifact]          # None if error
    metadata: Optional[RenderMetadata]          # None if error or not requested
    error: Optional[RenderError] = None         # Populated on failure


def compute_input_hash(render_input: RenderInput) -> str:
    """
    Compute deterministic hash of RenderInput.

    Uses only accessible fields per contract (not score/rank).
    Deterministic: same input always produces same hash.
    """
    # Extract only accessible fields (NOT score, NOT rank)
    trajectory = render_input.ranked_result.trajectory

    hash_data = {
        "sequence": trajectory.sequence,
        "final_magnitude": trajectory.final_magnitude,
        "steps": tuple(
            (s.idx, s.token, s.token_type, s.magnitude, s.event)
            for s in trajectory.steps
        ),
        "renderer_id": render_input.renderer_id,
        "config": (
            (render_input.renderer_config.output_format,
             render_input.renderer_config.precision,
             render_input.renderer_config.include_metadata,
             render_input.renderer_config.custom_params)
            if render_input.renderer_config else None
        ),
    }

    # Deterministic JSON serialization
    json_str = json.dumps(hash_data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()[:16]
