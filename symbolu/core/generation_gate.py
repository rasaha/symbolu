"""
GenerationGate v1.0
===================

Sealed binary boundary preventing expressive/generative output paths
unless explicitly enabled at boot.

CRITICAL INVARIANTS:
- Deterministic only (no random, time, uuid, timestamps)
- Fail-closed: any ambiguity -> deny all
- One-time seal (second call raises)
- No ML/NLP imports
- Immutable sealed state

Author: Symbolu Core Team
Version: 1.0.0
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


# ============================================================================
# Enums
# ============================================================================

class GenerationMode(Enum):
    """Binary mode for generation capability."""
    DISABLED = "DISABLED"
    ENABLED = "ENABLED"


class GateStatus(Enum):
    """Status of the generation gate."""
    UNSEALED = "UNSEALED"
    SEALED_DISABLED = "SEALED_DISABLED"
    SEALED_ENABLED = "SEALED_ENABLED"


# ============================================================================
# Exceptions
# ============================================================================

@dataclass(frozen=True)
class GateViolation(Exception):
    """
    Raised when generation gate policy is violated.

    Frozen dataclass ensures immutability.
    Error codes are deterministic strings.
    """
    code: str
    context: str = ""

    def __str__(self) -> str:
        if self.context:
            return f"GateViolation[{self.code}]: {self.context}"
        return f"GateViolation[{self.code}]"


# ============================================================================
# Error Codes (Deterministic)
# ============================================================================

class ErrorCode:
    """Deterministic error code strings."""
    GATE_UNSEALED = "GATE_UNSEALED"
    GATE_ALREADY_SEALED = "GATE_ALREADY_SEALED"
    GENERATION_DISABLED = "GENERATION_DISABLED"
    INVALID_MODE = "INVALID_MODE"


# ============================================================================
# GenerationGate Singleton
# ============================================================================

class _GenerationGateSingleton:
    """
    Singleton implementation of GenerationGate.

    Thread-safety not required per spec (boot-time only).
    Deterministic seal behavior enforced.
    """

    def __init__(self) -> None:
        self._sealed: bool = False
        self._mode: Optional[GenerationMode] = None

    def seal(self, mode: GenerationMode) -> None:
        """
        One-time seal of the generation gate.

        Args:
            mode: GenerationMode to seal with

        Raises:
            GateViolation: If already sealed or invalid mode
        """
        if not isinstance(mode, GenerationMode):
            raise GateViolation(
                code=ErrorCode.INVALID_MODE,
                context=f"Expected GenerationMode, got {type(mode).__name__}"
            )

        if self._sealed:
            raise GateViolation(
                code=ErrorCode.GATE_ALREADY_SEALED,
                context=f"Gate already sealed with mode={self._mode.value}"
            )

        # Seal is irrevocable
        self._sealed = True
        self._mode = mode

    def mode(self) -> GenerationMode:
        """
        Return the sealed generation mode.

        Returns:
            GenerationMode: The sealed mode

        Raises:
            GateViolation: If gate is not sealed
        """
        if not self._sealed:
            raise GateViolation(
                code=ErrorCode.GATE_UNSEALED,
                context="Cannot query mode before gate is sealed"
            )

        # Type narrowing: _mode is not None when _sealed is True
        assert self._mode is not None
        return self._mode

    def gate_status(self) -> GateStatus:
        """
        Return the current gate status.

        Returns:
            GateStatus: Current status
        """
        if not self._sealed:
            return GateStatus.UNSEALED

        # _mode is guaranteed non-None when _sealed is True
        assert self._mode is not None

        if self._mode == GenerationMode.DISABLED:
            return GateStatus.SEALED_DISABLED
        else:
            return GateStatus.SEALED_ENABLED

    def assert_generation_enabled(self) -> None:
        """
        Assert that generation is enabled.

        Raises:
            GateViolation: If gate unsealed or mode is DISABLED
        """
        if not self._sealed:
            raise GateViolation(
                code=ErrorCode.GATE_UNSEALED,
                context="Gate must be sealed before generation attempts"
            )

        assert self._mode is not None

        if self._mode == GenerationMode.DISABLED:
            raise GateViolation(
                code=ErrorCode.GENERATION_DISABLED,
                context="Generation mode is DISABLED"
            )

    def _reset(self) -> None:
        """
        Internal reset for testing only.

        NOT part of public API. Should only be used in test fixtures.
        """
        self._sealed = False
        self._mode = None


# Global singleton instance
GenerationGate = _GenerationGateSingleton()


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "GenerationMode",
    "GateStatus",
    "GateViolation",
    "ErrorCode",
    "GenerationGate",
]
