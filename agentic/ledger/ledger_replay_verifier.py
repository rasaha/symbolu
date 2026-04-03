"""
Ledger Replay Verifier (Stable-Experimental)
=============================================

Deterministic verification of recorded ontological projections by reconstruction.

This verifier:
    - Recomputes expected projection records using existing R1 router logic
    - Compares them against recorded ledger entries
    - Fails closed on any mismatch
    - Is fully replayable, auditable, and hash-stable

Hard Constraints:
    - NO NLP / ML / probabilistic libraries
    - NO random, uuid, datetime, time
    - NO free-form text output
    - NO semantics, meaning, intent, emotion
    - NO mutation of existing artifacts or router tables
    - NO routing changes
    - NO generation of new projections

Allowed imports:
    - hashlib
    - json
    - dataclasses
    - typing
    - enum
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Mapping, Optional, Sequence, Tuple

from agentic.ontology.router.ontological_router_r1 import (
    LedgerAdapter,
    LedgerSpanInput,
    OntologicalLayer,
    OntologicalLayerRouter,
    ProjectionRequest,
)


# =============================================================================
# Constants
# =============================================================================

MAPPING_VERSION = "M1.0"


# =============================================================================
# Invariants (Must Hold)
# =============================================================================

LEDGER_REPLAY_INVARIANTS: Mapping[str, bool] = {
    "DETERMINISTIC": True,
    "REPLAYABLE": True,
    "FAIL_CLOSED": True,
    "NO_GENERATION": True,
    "NO_ROUTING_CHANGES": True,
    "NO_SEMANTICS": True,
    "HASH_STABLE": True,
    "APPEND_ONLY": True,
}


# =============================================================================
# Replay Error Codes (Enum)
# =============================================================================

class ReplayError(Enum):
    """Deterministic failure codes for replay verification."""
    ENTRY_ID_MISMATCH = "ENTRY_ID_MISMATCH"
    SPAN_ID_MISMATCH = "SPAN_ID_MISMATCH"
    LAYER_MISMATCH = "LAYER_MISMATCH"
    ORDER_MISMATCH = "ORDER_MISMATCH"
    MISSING_ENTRY = "MISSING_ENTRY"
    EXTRA_ENTRY = "EXTRA_ENTRY"
    ROUTER_VERSION_MISMATCH = "ROUTER_VERSION_MISMATCH"
    HASH_CHAIN_MISMATCH = "HASH_CHAIN_MISMATCH"
    SEQ_MISMATCH = "SEQ_MISMATCH"


# =============================================================================
# Verification Result (Frozen)
# =============================================================================

@dataclass(frozen=True)
class VerificationResult:
    """
    Result of ledger replay verification.

    Attributes:
        success: True if all entries verified successfully.
        error: The ReplayError code if verification failed, None if success.
        failed_index: The index of the first failed entry, None if success.
    """
    success: bool
    error: Optional[ReplayError]
    failed_index: Optional[int]


# =============================================================================
# Ledger Projection Entry (Frozen)
# =============================================================================

@dataclass(frozen=True)
class LedgerProjectionEntry:
    """
    A single ledger entry recording an ontological projection.

    Attributes:
        ledger_index: Sequential index in the ledger (0-based).
        artifact_id: Opaque artifact identifier.
        artifact_hash: Precomputed, immutable hash of the artifact.
        phase_id: Phase identifier (e.g., "1b", "2", ..., "9").
        projected_layers: Tuple of projected ontological layers.
        span_id: Deterministic span ID generated via LedgerAdapter.
        router_version: Version string of the router used.
        entry_hash: SHA-256 hash of canonical serialization (first 16 hex chars).

    Invariants:
        - All fields are immutable after construction
        - entry_hash is derived from canonical serialization
        - projected_layers are sorted by layer value
    """
    ledger_index: int
    artifact_id: str
    artifact_hash: str
    phase_id: str
    projected_layers: Tuple[OntologicalLayer, ...]
    span_id: str
    router_version: str
    entry_hash: str

    def __post_init__(self) -> None:
        """Validate invariants on construction (fail-closed)."""
        if not isinstance(self.ledger_index, int) or self.ledger_index < 0:
            raise ValueError("ledger_index must be a non-negative integer")
        if not isinstance(self.artifact_id, str) or len(self.artifact_id) == 0:
            raise ValueError("artifact_id must be a non-empty string")
        if not isinstance(self.artifact_hash, str) or len(self.artifact_hash) == 0:
            raise ValueError("artifact_hash must be a non-empty string")
        if not isinstance(self.phase_id, str) or len(self.phase_id) == 0:
            raise ValueError("phase_id must be a non-empty string")
        if not isinstance(self.projected_layers, tuple):
            raise ValueError("projected_layers must be a tuple")
        if not all(isinstance(layer, OntologicalLayer) for layer in self.projected_layers):
            raise ValueError("all projected_layers must be OntologicalLayer instances")
        if not isinstance(self.span_id, str) or len(self.span_id) == 0:
            raise ValueError("span_id must be a non-empty string")
        if not isinstance(self.router_version, str) or len(self.router_version) == 0:
            raise ValueError("router_version must be a non-empty string")
        if not isinstance(self.entry_hash, str) or len(self.entry_hash) != 16:
            raise ValueError("entry_hash must be a 16-character hex string")


# =============================================================================
# LedgerEntry (New Spec-Compliant)
# =============================================================================

@dataclass(frozen=True)
class LedgerEntry:
    """
    Append-only ledger entry with hash chain linkage.

    Fields (per specification):
        entry_id: str - SHA-256 derived from canonical JSON (16 hex chars)
        prev_entry_id: Optional[str] - Hash chain link to previous entry
        span_id: str - Deterministic span ID
        artifact_id: str - Opaque artifact identifier
        artifact_hash: str - Precomputed artifact hash
        phase_id: str - Phase identifier
        projected_layers: Tuple[OntologicalLayer, ...] - Projected layers
        router_version: str - Router version string
        mapping_version: str - Mapping version string
        seq: int - Monotonic sequence number (NO timestamps)

    Invariants:
        - All fields are immutable after construction
        - entry_id is derived from canonical JSON serialization
        - prev_entry_id links to previous entry (None for first)
        - Same input produces identical output (deterministic)
        - No timestamps, no randomness
    """
    entry_id: str
    prev_entry_id: Optional[str]
    span_id: str
    artifact_id: str
    artifact_hash: str
    phase_id: str
    projected_layers: Tuple[OntologicalLayer, ...]
    router_version: str
    mapping_version: str
    seq: int

    def __post_init__(self) -> None:
        """Validate invariants on construction (fail-closed)."""
        if not isinstance(self.entry_id, str) or len(self.entry_id) != 16:
            raise ValueError("entry_id must be a 16-character hex string")
        if self.prev_entry_id is not None:
            if not isinstance(self.prev_entry_id, str) or len(self.prev_entry_id) != 16:
                raise ValueError("prev_entry_id must be None or a 16-character hex string")
        if not isinstance(self.span_id, str) or len(self.span_id) == 0:
            raise ValueError("span_id must be a non-empty string")
        if not isinstance(self.artifact_id, str) or len(self.artifact_id) == 0:
            raise ValueError("artifact_id must be a non-empty string")
        if not isinstance(self.artifact_hash, str) or len(self.artifact_hash) == 0:
            raise ValueError("artifact_hash must be a non-empty string")
        if not isinstance(self.phase_id, str) or len(self.phase_id) == 0:
            raise ValueError("phase_id must be a non-empty string")
        if not isinstance(self.projected_layers, tuple):
            raise ValueError("projected_layers must be a tuple")
        if not all(isinstance(layer, OntologicalLayer) for layer in self.projected_layers):
            raise ValueError("all projected_layers must be OntologicalLayer instances")
        if not isinstance(self.router_version, str) or len(self.router_version) == 0:
            raise ValueError("router_version must be a non-empty string")
        if not isinstance(self.mapping_version, str) or len(self.mapping_version) == 0:
            raise ValueError("mapping_version must be a non-empty string")
        if not isinstance(self.seq, int) or self.seq < 0:
            raise ValueError("seq must be a non-negative integer")


# =============================================================================
# Canonical Serialization
# =============================================================================

def canonical_serialize(entry: LedgerProjectionEntry) -> bytes:
    """
    Serialize a ledger entry to canonical bytes for hashing.

    Rules:
        - Deterministic key ordering
        - Sorted ontological layers
        - No whitespace variance
        - No optional fields omitted
        - Stable across platforms

    Args:
        entry: The LedgerProjectionEntry to serialize.

    Returns:
        Canonical byte representation suitable for hashing.
    """
    sorted_layers = sorted(entry.projected_layers, key=lambda l: l.value)
    layer_names = [layer.name for layer in sorted_layers]

    canonical_dict = {
        "artifact_hash": entry.artifact_hash,
        "artifact_id": entry.artifact_id,
        "ledger_index": entry.ledger_index,
        "phase_id": entry.phase_id,
        "projected_layers": layer_names,
        "router_version": entry.router_version,
        "span_id": entry.span_id,
    }

    canonical_json = json.dumps(
        canonical_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return canonical_json.encode("utf-8")


def compute_entry_hash(
    ledger_index: int,
    artifact_id: str,
    artifact_hash: str,
    phase_id: str,
    projected_layers: Tuple[OntologicalLayer, ...],
    span_id: str,
    router_version: str,
) -> str:
    """
    Compute the entry hash for a ledger projection entry.

    Args:
        ledger_index: Sequential index in the ledger.
        artifact_id: Opaque artifact identifier.
        artifact_hash: Precomputed artifact hash.
        phase_id: Phase identifier.
        projected_layers: Tuple of projected layers.
        span_id: Deterministic span ID.
        router_version: Router version string.

    Returns:
        First 16 hex characters of SHA-256 hash.
    """
    sorted_layers = sorted(projected_layers, key=lambda l: l.value)
    layer_names = [layer.name for layer in sorted_layers]

    canonical_dict = {
        "artifact_hash": artifact_hash,
        "artifact_id": artifact_id,
        "ledger_index": ledger_index,
        "phase_id": phase_id,
        "projected_layers": layer_names,
        "router_version": router_version,
        "span_id": span_id,
    }

    canonical_json = json.dumps(
        canonical_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    full_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return full_hash[:16]


def create_entry(
    ledger_index: int,
    artifact_id: str,
    artifact_hash: str,
    phase_id: str,
    projected_layers: Tuple[OntologicalLayer, ...],
    span_id: str,
    router_version: str,
) -> LedgerProjectionEntry:
    """
    Create a LedgerProjectionEntry with computed entry_hash.

    Args:
        ledger_index: Sequential index in the ledger.
        artifact_id: Opaque artifact identifier.
        artifact_hash: Precomputed artifact hash.
        phase_id: Phase identifier.
        projected_layers: Tuple of projected layers.
        span_id: Deterministic span ID.
        router_version: Router version string.

    Returns:
        A new LedgerProjectionEntry with computed entry_hash.
    """
    entry_hash = compute_entry_hash(
        ledger_index=ledger_index,
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        phase_id=phase_id,
        projected_layers=projected_layers,
        span_id=span_id,
        router_version=router_version,
    )

    return LedgerProjectionEntry(
        ledger_index=ledger_index,
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        phase_id=phase_id,
        projected_layers=projected_layers,
        span_id=span_id,
        router_version=router_version,
        entry_hash=entry_hash,
    )


# =============================================================================
# LedgerEntry Canonical Serialization and Hashing
# =============================================================================

def compute_entry_id(
    prev_entry_id: Optional[str],
    span_id: str,
    artifact_id: str,
    artifact_hash: str,
    phase_id: str,
    projected_layers: Tuple[OntologicalLayer, ...],
    router_version: str,
    mapping_version: str,
    seq: int,
) -> str:
    """
    Compute the entry_id for a LedgerEntry using SHA-256.

    The entry_id is derived from a canonical JSON representation.
    Rules:
        - Keys sorted alphabetically
        - No timestamps
        - No randomness
        - Same entry -> same hash byte-for-byte

    Args:
        prev_entry_id: Hash chain link to previous entry (None for first).
        span_id: Deterministic span ID.
        artifact_id: Opaque artifact identifier.
        artifact_hash: Precomputed artifact hash.
        phase_id: Phase identifier.
        projected_layers: Tuple of projected layers.
        router_version: Router version string.
        mapping_version: Mapping version string.
        seq: Monotonic sequence number.

    Returns:
        First 16 hex characters of SHA-256 hash.
    """
    sorted_layers = sorted(projected_layers, key=lambda l: l.value)
    layer_names = [layer.name for layer in sorted_layers]

    canonical_dict = {
        "artifact_hash": artifact_hash,
        "artifact_id": artifact_id,
        "mapping_version": mapping_version,
        "phase_id": phase_id,
        "prev_entry_id": prev_entry_id,
        "projected_layers": layer_names,
        "router_version": router_version,
        "seq": seq,
        "span_id": span_id,
    }

    canonical_json = json.dumps(
        canonical_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    full_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return full_hash[:16]


def create_ledger_entry(
    prev_entry_id: Optional[str],
    span_id: str,
    artifact_id: str,
    artifact_hash: str,
    phase_id: str,
    projected_layers: Tuple[OntologicalLayer, ...],
    router_version: str,
    mapping_version: str,
    seq: int,
) -> LedgerEntry:
    """
    Create a LedgerEntry with computed entry_id.

    Args:
        prev_entry_id: Hash chain link to previous entry (None for first).
        span_id: Deterministic span ID.
        artifact_id: Opaque artifact identifier.
        artifact_hash: Precomputed artifact hash.
        phase_id: Phase identifier.
        projected_layers: Tuple of projected layers.
        router_version: Router version string.
        mapping_version: Mapping version string.
        seq: Monotonic sequence number.

    Returns:
        A new LedgerEntry with computed entry_id.
    """
    entry_id = compute_entry_id(
        prev_entry_id=prev_entry_id,
        span_id=span_id,
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        phase_id=phase_id,
        projected_layers=projected_layers,
        router_version=router_version,
        mapping_version=mapping_version,
        seq=seq,
    )

    return LedgerEntry(
        entry_id=entry_id,
        prev_entry_id=prev_entry_id,
        span_id=span_id,
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        phase_id=phase_id,
        projected_layers=projected_layers,
        router_version=router_version,
        mapping_version=mapping_version,
        seq=seq,
    )


def ledger_entry_to_dict(entry: LedgerEntry) -> Mapping[str, object]:
    """
    Convert a LedgerEntry to a JSON-serializable dict.

    Args:
        entry: The entry to convert.

    Returns:
        A dictionary suitable for JSON serialization.
    """
    return {
        "entry_id": entry.entry_id,
        "prev_entry_id": entry.prev_entry_id,
        "span_id": entry.span_id,
        "artifact_id": entry.artifact_id,
        "artifact_hash": entry.artifact_hash,
        "phase_id": entry.phase_id,
        "projected_layers": [layer.name for layer in entry.projected_layers],
        "router_version": entry.router_version,
        "mapping_version": entry.mapping_version,
        "seq": entry.seq,
    }


def dict_to_ledger_entry(data: Mapping[str, object]) -> LedgerEntry:
    """
    Convert a dictionary to a LedgerEntry.

    Args:
        data: The dictionary containing entry data.

    Returns:
        A LedgerEntry instance.
    """
    layer_names = data["projected_layers"]
    if not isinstance(layer_names, list):
        raise ValueError("projected_layers must be a list")

    projected_layers = tuple(
        OntologicalLayer[name] for name in layer_names
    )

    prev_entry_id = data.get("prev_entry_id")
    if prev_entry_id is not None:
        prev_entry_id = str(prev_entry_id)

    return LedgerEntry(
        entry_id=str(data["entry_id"]),
        prev_entry_id=prev_entry_id,
        span_id=str(data["span_id"]),
        artifact_id=str(data["artifact_id"]),
        artifact_hash=str(data["artifact_hash"]),
        phase_id=str(data["phase_id"]),
        projected_layers=projected_layers,
        router_version=str(data["router_version"]),
        mapping_version=str(data["mapping_version"]),
        seq=int(data["seq"]),  # type: ignore[arg-type]
    )


# =============================================================================
# Ledger Replay Verifier
# =============================================================================

class LedgerReplayVerifier:
    """
    Deterministic verifier for ledger replay.

    Verifies recorded ontological projections by reconstruction:
        1. Recomputes expected projection records using R1 router logic
        2. Compares them against recorded ledger entries
        3. Fails closed on any mismatch
        4. Is fully replayable, auditable, and hash-stable
    """

    def verify(
        self,
        recorded_entries: Tuple[LedgerProjectionEntry, ...],
        router: OntologicalLayerRouter,
    ) -> VerificationResult:
        """
        Verify recorded ledger entries against R1 router recomputation.

        Args:
            recorded_entries: Tuple of recorded ledger projection entries.
            router: The OntologicalLayerRouter to use for recomputation.

        Returns:
            VerificationResult indicating success or failure with error code.

        Verification Steps:
            1. For each entry, validate ledger_index matches position
            2. Recompute projected_layers via R1 router
            3. Recompute span_id via LedgerAdapter
            4. Recompute entry_hash via canonical serialization
            5. Compare byte-for-byte
            6. Fail closed on any mismatch
        """
        for idx, entry in enumerate(recorded_entries):
            if entry.ledger_index != idx:
                return VerificationResult(
                    success=False,
                    error=ReplayError.ORDER_MISMATCH,
                    failed_index=idx,
                )

            if entry.router_version != router.ROUTER_VERSION:
                return VerificationResult(
                    success=False,
                    error=ReplayError.ROUTER_VERSION_MISMATCH,
                    failed_index=idx,
                )

            request = ProjectionRequest(
                artifact_id=entry.artifact_id,
                phase_id=entry.phase_id,
                artifact_hash=entry.artifact_hash,
                declared_projection_hint=self._infer_hint_from_layers(
                    entry.projected_layers,
                    entry.phase_id,
                    router,
                ),
            )

            try:
                response = router.project(request)
            except Exception:
                return VerificationResult(
                    success=False,
                    error=ReplayError.LAYER_MISMATCH,
                    failed_index=idx,
                )

            if response.projected_layers != entry.projected_layers:
                return VerificationResult(
                    success=False,
                    error=ReplayError.LAYER_MISMATCH,
                    failed_index=idx,
                )

            expected_span_id = LedgerAdapter.generate_span_id(
                LedgerSpanInput(
                    artifact_hash=entry.artifact_hash,
                    phase_id=entry.phase_id,
                    projected_layers=entry.projected_layers,
                )
            )

            if expected_span_id != entry.span_id:
                return VerificationResult(
                    success=False,
                    error=ReplayError.SPAN_ID_MISMATCH,
                    failed_index=idx,
                )

            expected_entry_hash = compute_entry_hash(
                ledger_index=entry.ledger_index,
                artifact_id=entry.artifact_id,
                artifact_hash=entry.artifact_hash,
                phase_id=entry.phase_id,
                projected_layers=entry.projected_layers,
                span_id=entry.span_id,
                router_version=entry.router_version,
            )

            if expected_entry_hash != entry.entry_hash:
                return VerificationResult(
                    success=False,
                    error=ReplayError.ENTRY_ID_MISMATCH,
                    failed_index=idx,
                )

        return VerificationResult(
            success=True,
            error=None,
            failed_index=None,
        )

    def _infer_hint_from_layers(
        self,
        projected_layers: Tuple[OntologicalLayer, ...],
        phase_id: str,
        router: OntologicalLayerRouter,
    ) -> Optional[OntologicalLayer]:
        """
        Infer the declared projection hint needed to produce the recorded layers.

        This is a reverse lookup: given the recorded layers and phase,
        determine what hint (if any) was used.

        Args:
            projected_layers: The recorded projected layers.
            phase_id: The phase identifier.
            router: The router to check default projection.

        Returns:
            The inferred hint, or None if default projection matches.
        """
        from agentic.ontology.router.ontological_router_r1 import (
            PHASE_TO_LAYER_DEFAULT,
        )

        default_layers = PHASE_TO_LAYER_DEFAULT.get(phase_id)
        if default_layers is None:
            return None

        if projected_layers == default_layers:
            return None

        if len(projected_layers) == 1:
            return projected_layers[0]

        return None


# =============================================================================
# Standalone verify_ledger_replay Function (Spec-Compliant)
# =============================================================================

def verify_ledger_replay(
    entries: Sequence[LedgerEntry],
    router: OntologicalLayerRouter,
) -> VerificationResult:
    """
    Verify ledger entries with hash chain integrity.

    Checks (ALL REQUIRED - FAIL-CLOSED on any mismatch):
        1. Hash chain integrity (prev_entry_id)
        2. Recomputed entry_id matches stored
        3. Recomputed span_id matches stored
        4. Recomputed router projection matches projected_layers
        5. Sequence ordering is strict and monotonic

    Args:
        entries: Sequence of LedgerEntry to verify.
        router: The OntologicalLayerRouter to use for recomputation.

    Returns:
        VerificationResult indicating PASS or FAIL.

    Note:
        No recovery. No warnings. Only PASS / FAIL.
    """
    from agentic.ontology.router.ontological_router_r1 import (
        PHASE_TO_LAYER_DEFAULT,
    )

    prev_entry_id: Optional[str] = None

    for idx, entry in enumerate(entries):
        # Check 5: Sequence ordering is strict and monotonic
        if entry.seq != idx:
            return VerificationResult(
                success=False,
                error=ReplayError.SEQ_MISMATCH,
                failed_index=idx,
            )

        # Check 1: Hash chain integrity (prev_entry_id)
        if entry.prev_entry_id != prev_entry_id:
            return VerificationResult(
                success=False,
                error=ReplayError.HASH_CHAIN_MISMATCH,
                failed_index=idx,
            )

        # Check router version
        if entry.router_version != router.ROUTER_VERSION:
            return VerificationResult(
                success=False,
                error=ReplayError.ROUTER_VERSION_MISMATCH,
                failed_index=idx,
            )

        # Infer hint for router replay
        default_layers = PHASE_TO_LAYER_DEFAULT.get(entry.phase_id)
        declared_hint: Optional[OntologicalLayer] = None
        if default_layers is not None and entry.projected_layers != default_layers:
            if len(entry.projected_layers) == 1:
                declared_hint = entry.projected_layers[0]

        # Check 4: Recomputed router projection matches projected_layers
        request = ProjectionRequest(
            artifact_id=entry.artifact_id,
            phase_id=entry.phase_id,
            artifact_hash=entry.artifact_hash,
            declared_projection_hint=declared_hint,
        )

        try:
            response = router.project(request)
        except Exception:
            return VerificationResult(
                success=False,
                error=ReplayError.LAYER_MISMATCH,
                failed_index=idx,
            )

        if response.projected_layers != entry.projected_layers:
            return VerificationResult(
                success=False,
                error=ReplayError.LAYER_MISMATCH,
                failed_index=idx,
            )

        # Check 3: Recomputed span_id matches stored
        expected_span_id = LedgerAdapter.generate_span_id(
            LedgerSpanInput(
                artifact_hash=entry.artifact_hash,
                phase_id=entry.phase_id,
                projected_layers=entry.projected_layers,
            )
        )

        if expected_span_id != entry.span_id:
            return VerificationResult(
                success=False,
                error=ReplayError.SPAN_ID_MISMATCH,
                failed_index=idx,
            )

        # Check 2: Recomputed entry_id matches stored
        expected_entry_id = compute_entry_id(
            prev_entry_id=entry.prev_entry_id,
            span_id=entry.span_id,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
            router_version=entry.router_version,
            mapping_version=entry.mapping_version,
            seq=entry.seq,
        )

        if expected_entry_id != entry.entry_id:
            return VerificationResult(
                success=False,
                error=ReplayError.ENTRY_ID_MISMATCH,
                failed_index=idx,
            )

        # Update prev_entry_id for next iteration
        prev_entry_id = entry.entry_id

    return VerificationResult(
        success=True,
        error=None,
        failed_index=None,
    )


# =============================================================================
# Fixture Serialization/Deserialization
# =============================================================================

def entry_to_dict(entry: LedgerProjectionEntry) -> Mapping[str, object]:
    """
    Convert a LedgerProjectionEntry to a JSON-serializable dict.

    Args:
        entry: The entry to convert.

    Returns:
        A dictionary suitable for JSON serialization.
    """
    return {
        "ledger_index": entry.ledger_index,
        "artifact_id": entry.artifact_id,
        "artifact_hash": entry.artifact_hash,
        "phase_id": entry.phase_id,
        "projected_layers": [layer.name for layer in entry.projected_layers],
        "span_id": entry.span_id,
        "router_version": entry.router_version,
        "entry_hash": entry.entry_hash,
    }


def dict_to_entry(data: Mapping[str, object]) -> LedgerProjectionEntry:
    """
    Convert a dictionary to a LedgerProjectionEntry.

    Args:
        data: The dictionary containing entry data.

    Returns:
        A LedgerProjectionEntry instance.
    """
    layer_names = data["projected_layers"]
    if not isinstance(layer_names, list):
        raise ValueError("projected_layers must be a list")

    projected_layers = tuple(
        OntologicalLayer[name] for name in layer_names
    )

    return LedgerProjectionEntry(
        ledger_index=int(data["ledger_index"]),  # type: ignore[arg-type]
        artifact_id=str(data["artifact_id"]),
        artifact_hash=str(data["artifact_hash"]),
        phase_id=str(data["phase_id"]),
        projected_layers=projected_layers,
        span_id=str(data["span_id"]),
        router_version=str(data["router_version"]),
        entry_hash=str(data["entry_hash"]),
    )


def load_fixture(fixture_path: str) -> Tuple[LedgerProjectionEntry, ...]:
    """
    Load ledger entries from a JSON fixture file.

    Args:
        fixture_path: Path to the fixture JSON file.

    Returns:
        Tuple of LedgerProjectionEntry instances.
    """
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries_data = data.get("entries", [])
    if not isinstance(entries_data, list):
        raise ValueError("fixture must contain an 'entries' list")

    return tuple(dict_to_entry(entry_data) for entry_data in entries_data)


def save_fixture(
    fixture_path: str,
    entries: Tuple[LedgerProjectionEntry, ...],
    metadata: Optional[Mapping[str, object]] = None,
) -> None:
    """
    Save ledger entries to a JSON fixture file.

    Args:
        fixture_path: Path to the fixture JSON file.
        entries: Tuple of LedgerProjectionEntry instances.
        metadata: Optional metadata to include in the fixture.
    """
    fixture_data: dict[str, object] = {
        "entries": [entry_to_dict(entry) for entry in entries],
    }

    if metadata is not None:
        fixture_data["metadata"] = dict(metadata)

    with open(fixture_path, "w", encoding="utf-8") as f:
        json.dump(
            fixture_data,
            f,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
