"""
Phase-7 Targeted Generation - Error Types

All errors are deterministic and produce reproducible error reports.
"""

from typing import Optional, Tuple

from .types import ErrorType, ExecutionError


class Phase7Error(Exception):
    """Base exception for Phase-7 errors."""

    def __init__(
        self,
        error_type: ErrorType,
        message: str,
        sequence: Optional[Tuple[str, ...]] = None,
        field: Optional[str] = None,
        value: Optional[str] = None,
        stage: Optional[str] = None,
    ):
        self.error_type = error_type
        self.message = message
        self.sequence = sequence
        self.field = field
        self.value = value
        self.stage = stage
        super().__init__(message)

    def to_execution_error(self) -> ExecutionError:
        """Convert to ExecutionError for result."""
        return ExecutionError(
            error_type=self.error_type,
            message=self.message,
            sequence=self.sequence,
            field=self.field,
            value=self.value,
            stage=self.stage,
        )


class Phase7ValidationError(Phase7Error):
    """Raised during target/config validation."""
    pass


class Phase7SimulationError(Phase7Error):
    """Raised during Phase-6 simulation."""
    pass


class Phase7ContradictionError(Phase7Error):
    """Raised when contradictory constraints detected."""
    pass


def create_error(
    error_type: ErrorType,
    message: str,
    sequence: Optional[Tuple[str, ...]] = None,
    field: Optional[str] = None,
    value: Optional[str] = None,
    stage: Optional[str] = None,
) -> ExecutionError:
    """Factory function for ExecutionError."""
    return ExecutionError(
        error_type=error_type,
        message=message,
        sequence=sequence,
        field=field,
        value=value,
        stage=stage,
    )
