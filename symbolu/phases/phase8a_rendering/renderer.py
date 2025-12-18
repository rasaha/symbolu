"""
Phase-8A Rendering Layer - Renderer Interface and Base Implementation

Defines the Renderer protocol and provides base functionality.
All renderers must be:
  - Deterministic: same input → same output
  - Stateless: no state between invocations
  - Non-selective: does not access score/rank
  - One-way: no feedback to earlier phases

Contract: docs/contracts/PHASE_8A_RENDERING_CONTRACT.md
"""

from abc import ABC, abstractmethod
from typing import FrozenSet

from symbolu.phases.phase8a_rendering.types import (
    RenderInput,
    RenderOutput,
    RenderModality,
    RendererConfig,
    ValidationResult,
    RenderError,
    RenderErrorType,
    RenderMetadata,
    compute_input_hash,
)


class Renderer(ABC):
    """
    Abstract base class for all renderers.

    Implements the Renderer protocol from Phase-8A contract Section 4.
    Subclasses must implement:
      - _do_render(): actual rendering logic
      - supported_formats: set of valid output formats
    """

    def __init__(self, renderer_id: str, modality: RenderModality):
        """
        Initialize renderer with immutable properties.

        Args:
            renderer_id: Unique identifier for this renderer
            modality: Output modality this renderer produces
        """
        self._renderer_id = renderer_id
        self._modality = modality

    @property
    def renderer_id(self) -> str:
        """Unique identifier for this renderer. Immutable."""
        return self._renderer_id

    @property
    def modality(self) -> RenderModality:
        """Output modality this renderer produces. Immutable."""
        return self._modality

    @property
    @abstractmethod
    def supported_formats(self) -> FrozenSet[str]:
        """Set of output_format values this renderer accepts. Immutable."""
        pass

    def validate_config(self, config: RendererConfig) -> ValidationResult:
        """
        Validate renderer configuration before rendering.

        Args:
            config: Configuration to validate

        Returns:
            ValidationResult with is_valid and error details
        """
        if config.output_format not in self.supported_formats:
            return ValidationResult(
                is_valid=False,
                error_type=RenderErrorType.UNSUPPORTED_FORMAT,
                error_details=f"Format '{config.output_format}' not in {self.supported_formats}",
            )
        return ValidationResult(is_valid=True)

    def compute_input_hash(self, render_input: RenderInput) -> str:
        """
        Compute deterministic hash of input for verification.

        Uses only accessible fields (not score/rank).
        """
        return compute_input_hash(render_input)

    def render(self, render_input: RenderInput) -> RenderOutput:
        """
        Transform input into rendered artifact.

        This method handles validation and error cases, delegating
        actual rendering to _do_render().

        Args:
            render_input: Input containing RankedResult and config

        Returns:
            RenderOutput with artifact or error
        """
        # Compute hash first (using only accessible fields)
        input_hash = self.compute_input_hash(render_input)

        # Validate config if present
        config = render_input.renderer_config or RendererConfig(output_format="default")
        validation = self.validate_config(config)
        if not validation.is_valid:
            return RenderOutput(
                renderer_id=self.renderer_id,
                input_hash=input_hash,
                modality=self.modality,
                artifact=None,
                metadata=None,
                error=RenderError(
                    error_type=validation.error_type,
                    error_message=validation.error_details or "Validation failed",
                ),
            )

        # Validate input structure
        trajectory = render_input.ranked_result.trajectory
        sequence = trajectory.sequence
        steps = trajectory.steps

        if len(sequence) == 0:
            return RenderOutput(
                renderer_id=self.renderer_id,
                input_hash=input_hash,
                modality=self.modality,
                artifact=None,
                metadata=None,
                error=RenderError(
                    error_type=RenderErrorType.EMPTY_SEQUENCE,
                    error_message="Sequence has length 0",
                ),
            )

        if len(steps) == 0:
            return RenderOutput(
                renderer_id=self.renderer_id,
                input_hash=input_hash,
                modality=self.modality,
                artifact=None,
                metadata=None,
                error=RenderError(
                    error_type=RenderErrorType.EMPTY_TRAJECTORY,
                    error_message="Trajectory has 0 steps",
                ),
            )

        if len(sequence) != len(steps):
            return RenderOutput(
                renderer_id=self.renderer_id,
                input_hash=input_hash,
                modality=self.modality,
                artifact=None,
                metadata=None,
                error=RenderError(
                    error_type=RenderErrorType.SEQUENCE_TRAJECTORY_MISMATCH,
                    error_message=f"Sequence length {len(sequence)} != steps length {len(steps)}",
                ),
            )

        # Compute metadata if requested
        metadata = None
        if config.include_metadata:
            metadata = self._compute_metadata(trajectory)

        # Delegate to subclass implementation
        try:
            artifact = self._do_render(render_input, config)
            return RenderOutput(
                renderer_id=self.renderer_id,
                input_hash=input_hash,
                modality=self.modality,
                artifact=artifact,
                metadata=metadata,
                error=None,
            )
        except Exception as e:
            return RenderOutput(
                renderer_id=self.renderer_id,
                input_hash=input_hash,
                modality=self.modality,
                artifact=None,
                metadata=None,
                error=RenderError(
                    error_type=RenderErrorType.INTERNAL_ERROR,
                    error_message=str(e),
                ),
            )

    def _compute_metadata(self, trajectory) -> RenderMetadata:
        """Compute metadata from trajectory (accessible fields only)."""
        steps = trajectory.steps
        reset_count = sum(1 for s in steps if s.event == "reset")
        modulate_count = sum(1 for s in steps if s.event == "modulate")
        magnitudes = [s.magnitude for s in steps]

        return RenderMetadata(
            sequence_length=len(trajectory.sequence),
            step_count=len(steps),
            final_magnitude=trajectory.final_magnitude,
            event_counts=(("reset", reset_count), ("modulate", modulate_count)),
            magnitude_range=(min(magnitudes), max(magnitudes)),
        )

    @abstractmethod
    def _do_render(self, render_input: RenderInput, config: RendererConfig):
        """
        Perform actual rendering. Must be deterministic.

        Args:
            render_input: Validated input
            config: Validated config

        Returns:
            Appropriate artifact type for this renderer's modality
        """
        pass
