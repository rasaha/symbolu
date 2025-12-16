"""
Ledger Generation Attestation v1.0
===================================

Minimal helper for producing hash-stable attestation blobs
for generation gate operations.

CRITICAL INVARIANTS:
- Frozen dict output (immutable)
- Hash-stable ordering (sorted keys)
- No mutation of existing ledger format
- Deterministic only (no timestamps, UUIDs, randomness)
- Additive attestation blob

Author: Symbolu Core Team
Version: 1.0.0
"""

from typing import FrozenSet, Mapping, Any, Optional
from symbolu.core.generation_gate import GenerationGate, GateStatus, GenerationMode


# ============================================================================
# Attestation Builder
# ============================================================================

class AttestationBuilder:
    """
    Builder for creating immutable, hash-stable attestation blobs.

    Produces frozen dictionaries with sorted keys for deterministic hashing.
    """

    @staticmethod
    def _freeze_dict(data: dict) -> Mapping[str, Any]:
        """
        Convert a dict to an immutable mapping with sorted keys.

        Args:
            data: Dictionary to freeze

        Returns:
            Immutable mapping with sorted keys (hash-stable)
        """
        # Sort keys for hash stability
        sorted_items = sorted(data.items())

        # Convert to types.MappingProxyType for true immutability
        from types import MappingProxyType
        return MappingProxyType(dict(sorted_items))

    @staticmethod
    def create_generation_attestation(
        render_attempted: bool,
        render_outcome: Optional[str] = None
    ) -> Mapping[str, Any]:
        """
        Create a generation gate attestation blob.

        Args:
            render_attempted: Whether rendering was attempted
            render_outcome: Outcome code (if render was attempted)

        Returns:
            Frozen, hash-stable attestation mapping

        Example:
            >>> attest = create_generation_attestation(
            ...     render_attempted=True,
            ...     render_outcome="GATE_BLOCKED"
            ... )
            >>> attest['generation_mode']
            'ENABLED'
        """
        # Query gate status (deterministic)
        gate_status = GenerationGate.gate_status()

        # Determine generation_mode string
        try:
            mode = GenerationGate.mode()
            mode_str = mode.value
        except Exception:
            # Gate unsealed
            mode_str = "UNSEALED"

        # Build attestation data
        attestation_data = {
            "generation_mode": mode_str,
            "gate_status": gate_status.value,
            "render_attempted": render_attempted,
            "render_outcome": render_outcome if render_outcome is not None else "NONE",
        }

        # Freeze and return
        return AttestationBuilder._freeze_dict(attestation_data)


# ============================================================================
# Public API
# ============================================================================

def attest_generation_attempt(
    render_attempted: bool,
    render_outcome: Optional[str] = None
) -> Mapping[str, Any]:
    """
    Create an attestation blob for a generation attempt.

    This is the primary public API for creating attestations.

    Args:
        render_attempted: Whether rendering was attempted
        render_outcome: Outcome code (if render was attempted)

    Returns:
        Frozen, hash-stable attestation mapping

    Example:
        >>> # Gate blocked scenario
        >>> blob = attest_generation_attempt(
        ...     render_attempted=True,
        ...     render_outcome="GATE_BLOCKED"
        ... )

        >>> # Successful render
        >>> blob = attest_generation_attempt(
        ...     render_attempted=True,
        ...     render_outcome="RENDER_SUCCESS"
        ... )
    """
    return AttestationBuilder.create_generation_attestation(
        render_attempted=render_attempted,
        render_outcome=render_outcome
    )


__all__ = [
    "AttestationBuilder",
    "attest_generation_attempt",
]
