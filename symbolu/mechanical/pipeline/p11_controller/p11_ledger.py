"""
P11 Ledger - Ledger Recording for Phase-11 Controller
=======================================================

This module provides ledger recording for Phase-11 controlled rendering.

Ledger Recording Rules:
    - ALWAYS records (regardless of RenderMode)
    - Records: artifact_id, artifact_hash, candidate_output_hash,
               verifier_report_hash, render_mode, span_id
    - span_id is timestamp-free (hash-only)
    - NO timestamps, NO randomness

Hard Constraints:
    - MUST be deterministic (same input -> same output)
    - NO time/datetime imports
    - NO randomness
    - Append-only semantics
    - Hash-stable across replays
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional, Tuple

from symbolu.mechanical.pipeline.p11_controller.p11_schema import RenderMode


# =============================================================================
# Version Constant
# =============================================================================

LEDGER_VERSION = "1.0.0"


# =============================================================================
# Ledger Entry
# =============================================================================


@dataclass(frozen=True)
class Phase11LedgerEntry:
    """
    Ledger entry for Phase-11 Controller execution.

    This entry captures the complete execution record for audit and replay.

    Attributes:
        artifact_id: Opaque artifact identifier
        artifact_hash: Precomputed artifact hash (64-char hex)
        candidate_output_hash: Hash of candidate output (16-char hex)
        verifier_report_hash: Hash of verifier report (16-char hex)
        render_mode: The RenderMode that was applied
        verifier_passed: Whether verifier check passed
        output_released: Whether output was actually released
        span_id: Deterministic span ID (hash-only, no timestamp)
        phase_id: Always "PHASE_11_CONTROLLER"
        ledger_version: Version of the ledger format
    """
    artifact_id: str
    artifact_hash: str
    candidate_output_hash: str
    verifier_report_hash: str
    render_mode: RenderMode
    verifier_passed: bool
    output_released: bool
    span_id: str
    phase_id: str = "PHASE_11_CONTROLLER"
    ledger_version: str = LEDGER_VERSION

    def __post_init__(self) -> None:
        """Validate Phase11LedgerEntry invariants."""
        # Validate artifact_id
        if not isinstance(self.artifact_id, str) or len(self.artifact_id) == 0:
            raise ValueError(
                "Phase11LedgerEntry.artifact_id must be non-empty string"
            )

        # Validate artifact_hash (64 hex chars)
        if not isinstance(self.artifact_hash, str) or len(self.artifact_hash) != 64:
            raise ValueError(
                f"Phase11LedgerEntry.artifact_hash must be 64 hex chars, "
                f"got {len(self.artifact_hash) if isinstance(self.artifact_hash, str) else type(self.artifact_hash).__name__}"
            )
        try:
            int(self.artifact_hash, 16)
        except ValueError:
            raise ValueError(
                "Phase11LedgerEntry.artifact_hash must contain only hex characters"
            )

        # Validate candidate_output_hash (16 hex chars)
        if not isinstance(self.candidate_output_hash, str) or len(self.candidate_output_hash) != 16:
            raise ValueError(
                f"Phase11LedgerEntry.candidate_output_hash must be 16 hex chars, "
                f"got {len(self.candidate_output_hash) if isinstance(self.candidate_output_hash, str) else type(self.candidate_output_hash).__name__}"
            )
        try:
            int(self.candidate_output_hash, 16)
        except ValueError:
            raise ValueError(
                "Phase11LedgerEntry.candidate_output_hash must contain only hex characters"
            )

        # Validate verifier_report_hash (16 hex chars)
        if not isinstance(self.verifier_report_hash, str) or len(self.verifier_report_hash) != 16:
            raise ValueError(
                f"Phase11LedgerEntry.verifier_report_hash must be 16 hex chars, "
                f"got {len(self.verifier_report_hash) if isinstance(self.verifier_report_hash, str) else type(self.verifier_report_hash).__name__}"
            )
        try:
            int(self.verifier_report_hash, 16)
        except ValueError:
            raise ValueError(
                "Phase11LedgerEntry.verifier_report_hash must contain only hex characters"
            )

        # Validate render_mode
        if not isinstance(self.render_mode, RenderMode):
            raise ValueError(
                f"Phase11LedgerEntry.render_mode must be RenderMode enum, "
                f"got {type(self.render_mode).__name__}"
            )

        # Validate verifier_passed
        if not isinstance(self.verifier_passed, bool):
            raise ValueError(
                f"Phase11LedgerEntry.verifier_passed must be bool, "
                f"got {type(self.verifier_passed).__name__}"
            )

        # Validate output_released
        if not isinstance(self.output_released, bool):
            raise ValueError(
                f"Phase11LedgerEntry.output_released must be bool, "
                f"got {type(self.output_released).__name__}"
            )

        # Validate span_id
        if not isinstance(self.span_id, str) or len(self.span_id) == 0:
            raise ValueError(
                "Phase11LedgerEntry.span_id must be non-empty string"
            )

        # Validate phase_id
        if self.phase_id != "PHASE_11_CONTROLLER":
            raise ValueError(
                f"Phase11LedgerEntry.phase_id must be 'PHASE_11_CONTROLLER', "
                f"got '{self.phase_id}'"
            )

        # CRITICAL INVARIANT: In GOVERNED mode, output_released IFF verifier_passed
        if self.render_mode == RenderMode.GOVERNED:
            if self.output_released and not self.verifier_passed:
                raise ValueError(
                    "Phase11LedgerEntry: GOVERNED mode with output_released=True "
                    "requires verifier_passed=True"
                )
            if not self.output_released and self.verifier_passed:
                # This is valid - verifier passed but output not released for other reasons
                pass

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "artifact_id": self.artifact_id,
            "artifact_hash": self.artifact_hash,
            "candidate_output_hash": self.candidate_output_hash,
            "verifier_report_hash": self.verifier_report_hash,
            "render_mode": self.render_mode.value,
            "verifier_passed": self.verifier_passed,
            "output_released": self.output_released,
            "span_id": self.span_id,
            "phase_id": self.phase_id,
            "ledger_version": self.ledger_version,
        }


# =============================================================================
# Span ID Generation (Timestamp-Free)
# =============================================================================


def compute_span_id(
    artifact_id: str,
    artifact_hash: str,
    candidate_output_hash: str,
    verifier_report_hash: str,
    render_mode: RenderMode,
) -> str:
    """
    Compute deterministic span ID for ledger recording.

    This function produces a timestamp-free, hash-only span ID.

    Args:
        artifact_id: Opaque artifact identifier.
        artifact_hash: Precomputed artifact hash.
        candidate_output_hash: Hash of candidate output.
        verifier_report_hash: Hash of verifier report.
        render_mode: The render mode applied.

    Returns:
        Deterministic 16-char hex span ID.

    Note:
        - NO timestamps
        - NO randomness
        - Same inputs -> identical span_id
    """
    # Build deterministic hash input
    hash_components = [
        f"artifact_id:{artifact_id}",
        f"artifact_hash:{artifact_hash}",
        f"candidate_output_hash:{candidate_output_hash}",
        f"verifier_report_hash:{verifier_report_hash}",
        f"render_mode:{render_mode.value}",
        f"phase:PHASE_11_CONTROLLER",
        f"version:{LEDGER_VERSION}",
    ]

    hash_input = "|".join(hash_components)
    span_id = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return span_id


# =============================================================================
# Ledger Recording
# =============================================================================


def create_ledger_entry(
    artifact_id: str,
    artifact_hash: str,
    candidate_output_hash: str,
    verifier_report_hash: str,
    render_mode: RenderMode,
    verifier_passed: bool,
    output_released: bool,
) -> Phase11LedgerEntry:
    """
    Create a Phase-11 ledger entry.

    This function creates a complete ledger entry with computed span_id.

    Args:
        artifact_id: Opaque artifact identifier.
        artifact_hash: Precomputed artifact hash.
        candidate_output_hash: Hash of candidate output.
        verifier_report_hash: Hash of verifier report.
        render_mode: The render mode applied.
        verifier_passed: Whether verifier check passed.
        output_released: Whether output was actually released.

    Returns:
        Phase11LedgerEntry with computed span_id.
    """
    span_id = compute_span_id(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        candidate_output_hash=candidate_output_hash,
        verifier_report_hash=verifier_report_hash,
        render_mode=render_mode,
    )

    return Phase11LedgerEntry(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        candidate_output_hash=candidate_output_hash,
        verifier_report_hash=verifier_report_hash,
        render_mode=render_mode,
        verifier_passed=verifier_passed,
        output_released=output_released,
        span_id=span_id,
    )


# =============================================================================
# Ledger Store (In-Memory for Phase-11)
# =============================================================================


class Phase11LedgerStore:
    """
    Append-only ledger store for Phase-11 Controller entries.

    Rules:
        - Append-only
        - No deletion
        - No mutation
        - Deterministic ordering

    This store is compatible with the broader Symbol-U ledger system.
    """

    def __init__(self) -> None:
        """Initialize an empty Phase-11 ledger store."""
        self._entries: list[Phase11LedgerEntry] = []
        self._index_by_span_id: dict[str, int] = {}

    def append(self, entry: Phase11LedgerEntry) -> str:
        """
        Append an entry to the ledger.

        Args:
            entry: The Phase11LedgerEntry to append.

        Returns:
            The span_id of the appended entry.

        Raises:
            ValueError: If an entry with the same span_id already exists.
        """
        if entry.span_id in self._index_by_span_id:
            raise ValueError(
                f"Entry with span_id {entry.span_id} already exists"
            )

        idx = len(self._entries)
        self._entries.append(entry)
        self._index_by_span_id[entry.span_id] = idx

        return entry.span_id

    def get(self, span_id: str) -> Optional[Phase11LedgerEntry]:
        """
        Get an entry by its span_id.

        Args:
            span_id: The span_id to look up.

        Returns:
            The Phase11LedgerEntry if found, None otherwise.
        """
        idx = self._index_by_span_id.get(span_id)
        if idx is None:
            return None
        return self._entries[idx]

    def head(self) -> Optional[Phase11LedgerEntry]:
        """
        Get the most recent (head) entry.

        Returns:
            The last Phase11LedgerEntry if any entries exist, None otherwise.
        """
        if not self._entries:
            return None
        return self._entries[-1]

    def read_all(self) -> Tuple[Phase11LedgerEntry, ...]:
        """
        Read all entries from the ledger.

        Returns:
            Tuple of all Phase11LedgerEntry instances in order.
        """
        return tuple(self._entries)

    def __len__(self) -> int:
        """Return the number of entries in the ledger."""
        return len(self._entries)


# =============================================================================
# Ledger Metadata
# =============================================================================


def get_ledger_version() -> str:
    """Return the ledger version."""
    return LEDGER_VERSION


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "LEDGER_VERSION",
    # Dataclasses
    "Phase11LedgerEntry",
    # Functions
    "compute_span_id",
    "create_ledger_entry",
    "get_ledger_version",
    # Store
    "Phase11LedgerStore",
]
