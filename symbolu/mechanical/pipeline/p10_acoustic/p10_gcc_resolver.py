"""
P10 GCC Resolver - Global Constraint Clamp Switch for Phase-10
===============================================================

This module implements the GCC (Global Constraint Clamp) switch logic for
Phase-10 consequence propagation.

Processing Rules:
    If gcc_mode == ENABLED:
        - Apply all existing GCC checks
        - Enforce consequence bounds
        - Enforce collapse thresholds
        - Block escalation
        - Behavior is BIT-IDENTICAL to current Phase-10

    If gcc_mode == DISABLED:
        - Skip GCC clamping logic ONLY
        - Still enforce: determinism, structural validity, ledger recording
        - Still enforce: ontological constraints
        - Consequences may propagate freely but remain structural
        - NO semantics, NO intent, NO interpretation

Hard Safety Boundaries (ALWAYS ENFORCED regardless of GCCMode):
    - NO mutation of Phase 1b-9 artifacts
    - NO new routing
    - NO new layer access
    - NO ABSOLVING access
    - NO generation
    - NO probabilistic logic
    - NO heuristics
    - NO inference

This switch ONLY affects consequence attenuation, NOT authority.

CRITICAL INVARIANTS:
    - Deterministic: same request + same gcc_mode -> identical output
    - Fail-closed: unknown gcc_mode -> HARD FAIL
    - No auto-downgrade or fallback behavior
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from symbolu.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)
from symbolu.mechanical.pipeline.p9_lexical.p9_lexical_schema import LexicalFrame
from symbolu.mechanical.pipeline.p10_acoustic.p10_acoustic_schema import (
    AcousticParameterFrame,
    AcousticRegime,
    EmphasisPolicy,
    PausePolicy,
    SPEECH_RATE_MIN,
    SPEECH_RATE_MAX,
    ENERGY_LEVEL_MIN,
    ENERGY_LEVEL_MAX,
    PITCH_MIN,
    PITCH_MAX,
    PAUSE_DURATION_MIN,
    PAUSE_DURATION_MAX,
    clamp_speech_rate,
    clamp_energy_level,
    clamp_pitch,
    clamp_pause_duration,
)
from symbolu.mechanical.pipeline.p10_acoustic.p10_acoustic_resolver import (
    P10AcousticResolver,
    REGIME_ACOUSTIC_MAP,
    SAFE_DEFAULT_CONFIG,
)
from symbolu.mechanical.pipeline.p10_acoustic.p10_gcc_mode import (
    GCCMode,
    Phase10Request,
    Phase10Response,
    validate_gcc_mode,
    is_gcc_enabled,
)


# =============================================================================
# Constants
# =============================================================================

# GCC Version identifier for ledger tracking
GCC_VERSION = "GCC1.0"


# =============================================================================
# GCC Ledger Entry
# =============================================================================


@dataclass(frozen=True)
class GCCLedgerEntry:
    """
    Ledger entry for Phase-10 GCC operations.

    This entry is recorded for EVERY Phase-10 execution, regardless of gcc_mode.
    The gcc_mode is hash-participating - replay with different gcc_mode produces
    different span IDs.

    Attributes:
        phase: Always "PHASE_10"
        gcc_mode: "ENABLED" or "DISABLED"
        artifact_hash: The artifact hash from the request
        span_id: Deterministically computed span ID
        timestamp: Always None (no timestamps in ledger)
        gcc_version: GCC version string
        clamping_applied: Whether GCC clamping was applied
    """
    phase: str
    gcc_mode: str
    artifact_hash: str
    span_id: str
    timestamp: None  # Always None - no timestamps
    gcc_version: str
    clamping_applied: bool

    def __post_init__(self) -> None:
        """Validate GCCLedgerEntry invariants (fail-closed)."""
        if self.phase != "PHASE_10":
            raise ValueError("GCCLedgerEntry.phase must be 'PHASE_10'")

        if self.gcc_mode not in ("ENABLED", "DISABLED"):
            raise ValueError(
                f"GCCLedgerEntry.gcc_mode must be 'ENABLED' or 'DISABLED', "
                f"got '{self.gcc_mode}'"
            )

        if not isinstance(self.artifact_hash, str) or len(self.artifact_hash) != 64:
            raise ValueError("GCCLedgerEntry.artifact_hash must be 64 hex chars")

        if not isinstance(self.span_id, str) or len(self.span_id) == 0:
            raise ValueError("GCCLedgerEntry.span_id must be non-empty string")

        if self.timestamp is not None:
            raise ValueError("GCCLedgerEntry.timestamp must be None")

        if not isinstance(self.gcc_version, str) or len(self.gcc_version) == 0:
            raise ValueError("GCCLedgerEntry.gcc_version must be non-empty string")

        if not isinstance(self.clamping_applied, bool):
            raise ValueError("GCCLedgerEntry.clamping_applied must be bool")

        # Invariant: clamping_applied IFF gcc_mode == "ENABLED"
        expected_clamping = (self.gcc_mode == "ENABLED")
        if self.clamping_applied != expected_clamping:
            raise ValueError(
                f"GCCLedgerEntry.clamping_applied must be {expected_clamping} "
                f"when gcc_mode is {self.gcc_mode}"
            )


# =============================================================================
# Span ID Computation
# =============================================================================


def compute_gcc_span_id(
    artifact_hash: str,
    gcc_mode: GCCMode,
    projected_layers_hash: str,
) -> str:
    """
    Compute deterministic span ID for Phase-10 GCC operation.

    The span ID is derived from:
        - artifact_hash
        - gcc_mode (hash-participating!)
        - projected_layers_hash

    This ensures that replay with different gcc_mode produces different span IDs.

    Args:
        artifact_hash: The artifact hash (64 hex chars).
        gcc_mode: The GCC mode (ENABLED or DISABLED).
        projected_layers_hash: Hash of projected layers.

    Returns:
        16-character hex span ID.
    """
    canonical_dict = {
        "artifact_hash": artifact_hash,
        "gcc_mode": gcc_mode.value,
        "phase": "PHASE_10",
        "projected_layers_hash": projected_layers_hash,
    }

    canonical_json = json.dumps(
        canonical_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    full_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return full_hash[:16]


def compute_layers_hash(layers: Tuple[Any, ...]) -> str:
    """
    Compute deterministic hash of projected layers.

    Args:
        layers: Tuple of OntologicalLayer enum values.

    Returns:
        16-character hex hash.
    """
    # Sort by layer value for determinism
    sorted_names = sorted(layer.name for layer in layers)
    canonical = json.dumps(sorted_names, sort_keys=True, separators=(",", ":"))
    full_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return full_hash[:16]


# =============================================================================
# P10 GCC Resolver
# =============================================================================


class P10GCCResolver:
    """
    Phase-10 GCC Resolver with Global Constraint Clamp switch.

    This resolver implements the GCC mode switch for Phase-10 consequence
    propagation. It wraps the existing P10AcousticResolver and applies
    GCC mode-dependent processing.

    Processing Rules:
        GCCMode.ENABLED:
            - Apply all GCC checks (consequence bounds, collapse thresholds)
            - Block escalation
            - Bit-identical to current Phase-10 behavior

        GCCMode.DISABLED:
            - Skip GCC clamping logic ONLY
            - Still enforce determinism and structural validity
            - Still enforce ontological constraints
            - Consequences propagate freely but remain structural

    CRITICAL: This resolver is DETERMINISTIC.
        - Same request + same gcc_mode -> identical output
        - No random, no timestamps, no side effects
    """

    def __init__(self) -> None:
        """Initialize the P10 GCC resolver."""
        self._acoustic_resolver = P10AcousticResolver()

    def resolve(
        self,
        *,
        request: Phase10Request,
        lexical_frame: Optional[LexicalFrame],
        discourse_envelope: Optional[DiscourseEnvelope],
        regime_envelope: Optional[RegimeEnvelope],
    ) -> Tuple[AcousticParameterFrame, GCCLedgerEntry]:
        """
        Resolve Phase-10 with GCC mode switch.

        Args:
            request: The Phase10Request containing gcc_mode.
            lexical_frame: The P9 LexicalFrame (for tracing).
            discourse_envelope: The P7 DiscourseEnvelope.
            regime_envelope: The P6 RegimeEnvelope.

        Returns:
            Tuple of (AcousticParameterFrame, GCCLedgerEntry).

        Raises:
            ValueError: If gcc_mode is invalid (fail-closed).

        Processing:
            1. Validate gcc_mode (HARD FAIL on unknown)
            2. Extract values for rule evaluation
            3. Apply GCC mode-dependent processing
            4. Generate ledger entry
            5. Return (frame, ledger_entry)
        """
        # Step 1: Validate gcc_mode - HARD FAIL on unknown
        validate_gcc_mode(request.gcc_mode)

        # Step 2: Extract values
        gcc_mode = request.gcc_mode

        # Step 3: Apply GCC mode-dependent processing
        if is_gcc_enabled(gcc_mode):
            # ENABLED: Apply all GCC checks (current behavior)
            frame = self._resolve_with_gcc_enabled(
                lexical_frame=lexical_frame,
                discourse_envelope=discourse_envelope,
                regime_envelope=regime_envelope,
            )
        else:
            # DISABLED: Skip GCC clamping, allow consequence flow
            frame = self._resolve_with_gcc_disabled(
                lexical_frame=lexical_frame,
                discourse_envelope=discourse_envelope,
                regime_envelope=regime_envelope,
            )

        # Step 4: Generate ledger entry
        layers_hash = compute_layers_hash(request.projected_layers)
        span_id = compute_gcc_span_id(
            artifact_hash=request.artifact_hash,
            gcc_mode=gcc_mode,
            projected_layers_hash=layers_hash,
        )

        ledger_entry = GCCLedgerEntry(
            phase="PHASE_10",
            gcc_mode=gcc_mode.value,
            artifact_hash=request.artifact_hash,
            span_id=span_id,
            timestamp=None,
            gcc_version=GCC_VERSION,
            clamping_applied=is_gcc_enabled(gcc_mode),
        )

        return frame, ledger_entry

    def _resolve_with_gcc_enabled(
        self,
        lexical_frame: Optional[LexicalFrame],
        discourse_envelope: Optional[DiscourseEnvelope],
        regime_envelope: Optional[RegimeEnvelope],
    ) -> AcousticParameterFrame:
        """
        Resolve with GCC ENABLED - apply all consequence bounds.

        This is BIT-IDENTICAL to the existing P10AcousticResolver behavior.
        All clamping functions are applied:
            - clamp_speech_rate()
            - clamp_energy_level()
            - clamp_pitch()
            - clamp_pause_duration()

        Args:
            lexical_frame: The P9 LexicalFrame.
            discourse_envelope: The P7 DiscourseEnvelope.
            regime_envelope: The P6 RegimeEnvelope.

        Returns:
            AcousticParameterFrame with all GCC bounds enforced.
        """
        # Delegate to existing resolver - applies all clamping
        return self._acoustic_resolver.resolve(
            lexical_frame=lexical_frame,
            discourse_envelope=discourse_envelope,
            regime_envelope=regime_envelope,
        )

    def _resolve_with_gcc_disabled(
        self,
        lexical_frame: Optional[LexicalFrame],
        discourse_envelope: Optional[DiscourseEnvelope],
        regime_envelope: Optional[RegimeEnvelope],
    ) -> AcousticParameterFrame:
        """
        Resolve with GCC DISABLED - skip consequence clamping.

        Skip GCC clamping logic ONLY. Still enforce:
            - Determinism
            - Structural validity (frozen dataclass)
            - Ontological constraints

        Consequences may propagate freely but remain structural.
        NO semantics, NO intent, NO interpretation.

        Args:
            lexical_frame: The P9 LexicalFrame.
            discourse_envelope: The P7 DiscourseEnvelope.
            regime_envelope: The P6 RegimeEnvelope.

        Returns:
            AcousticParameterFrame WITHOUT GCC bounds enforcement.
        """
        # Validate inputs - SAFE_DEFAULT on missing (fail-safe structural)
        if regime_envelope is None or discourse_envelope is None:
            return self._build_unclamped_safe_default(
                regime_envelope=regime_envelope,
                discourse_envelope=discourse_envelope,
            )

        # Extract values for rule evaluation
        regime = regime_envelope.regime
        discourse_act = discourse_envelope.act

        # Get base acoustic config from regime mapping (deterministic)
        base_config = REGIME_ACOUSTIC_MAP.get(regime, SAFE_DEFAULT_CONFIG).copy()

        # Apply discourse act overrides (deterministic, structural)
        config = self._apply_discourse_overrides_unclamped(
            base_config=base_config,
            discourse_act=discourse_act,
            regime=regime,
        )

        # Build frame WITHOUT clamping (allow values to flow through)
        return self._build_frame_unclamped(
            config=config,
            regime=regime,
            discourse_act=discourse_act,
            lexical_frame=lexical_frame,
        )

    def _apply_discourse_overrides_unclamped(
        self,
        base_config: Dict[str, Any],
        discourse_act: DiscourseAct,
        regime: OperationalRegime,
    ) -> Dict[str, Any]:
        """
        Apply discourse act overrides WITHOUT clamping.

        Same logic as GCC ENABLED, but no bound enforcement.
        Structural overrides are still applied (deterministic).

        Args:
            base_config: The base acoustic configuration.
            discourse_act: The discourse act from P7.
            regime: The operational regime from P6.

        Returns:
            Modified acoustic configuration (unclamped).
        """
        config = base_config.copy()

        # REFLECTION: Force max_stressed_tokens = 0 (structural)
        if discourse_act == DiscourseAct.REFLECTION:
            config["max_stressed_tokens"] = 0
            config["emphasis_policy"] = EmphasisPolicy.NONE

        # DEFERRAL: Force suppress_certainty = True (structural)
        if discourse_act == DiscourseAct.DEFERRAL:
            config["suppress_certainty"] = True

        # QUESTION: No emphasis under careful regimes (structural)
        if discourse_act == DiscourseAct.QUESTION:
            if regime in {
                OperationalRegime.HOLD,
                OperationalRegime.STABILIZE,
                OperationalRegime.DE_ESCALATE,
            }:
                config["max_stressed_tokens"] = 0
                config["emphasis_policy"] = EmphasisPolicy.NONE

        # EXPLANATION: Only allow emphasis if regime permits (structural)
        if discourse_act == DiscourseAct.EXPLANATION:
            if regime in {
                OperationalRegime.HOLD,
                OperationalRegime.STABILIZE,
                OperationalRegime.DE_ESCALATE,
            }:
                config["max_stressed_tokens"] = 0
                config["emphasis_policy"] = EmphasisPolicy.NONE

        # ACKNOWLEDGMENT: No emphasis (structural)
        if discourse_act == DiscourseAct.ACKNOWLEDGMENT:
            config["max_stressed_tokens"] = 0
            config["emphasis_policy"] = EmphasisPolicy.NONE

        # INSTRUCTION: Only allow emphasis under INFORM/CLARIFY (structural)
        if discourse_act == DiscourseAct.INSTRUCTION:
            if regime not in {OperationalRegime.INFORM, OperationalRegime.CLARIFY}:
                config["max_stressed_tokens"] = 0
                config["emphasis_policy"] = EmphasisPolicy.NONE

        return config

    def _build_frame_unclamped(
        self,
        config: Dict[str, Any],
        regime: OperationalRegime,
        discourse_act: DiscourseAct,
        lexical_frame: Optional[LexicalFrame],
    ) -> AcousticParameterFrame:
        """
        Build AcousticParameterFrame WITHOUT clamping.

        Values flow through without bound enforcement.
        HOWEVER: The dataclass __post_init__ still validates bounds,
        so we must stay within valid ranges to maintain structural validity.

        For GCC DISABLED, we use the MAXIMUM allowed values in the
        direction of "more expressive" while staying structurally valid.

        Args:
            config: The acoustic configuration dictionary.
            regime: The operational regime.
            discourse_act: The discourse act.
            lexical_frame: The P9 lexical frame.

        Returns:
            AcousticParameterFrame with unclamped (but structurally valid) params.
        """
        # For GCC DISABLED: Use values at the MORE EXPRESSIVE end of bounds
        # This allows consequence flow without violating structural validity

        # Speech rate: use configured value without clamping toward minimum
        speech_rate = config["speech_rate"]
        # Still must be structurally valid (dataclass validates)
        if speech_rate < SPEECH_RATE_MIN:
            speech_rate = SPEECH_RATE_MIN
        if speech_rate > SPEECH_RATE_MAX:
            speech_rate = SPEECH_RATE_MAX

        # Energy level: use configured value
        energy_level = config["energy_level"]
        if energy_level < ENERGY_LEVEL_MIN:
            energy_level = ENERGY_LEVEL_MIN
        if energy_level > ENERGY_LEVEL_MAX:
            energy_level = ENERGY_LEVEL_MAX

        # Pitch range: use configured values
        pitch_low, pitch_high = config["pitch_range"]
        if pitch_low < PITCH_MIN:
            pitch_low = PITCH_MIN
        if pitch_low > PITCH_MAX:
            pitch_low = PITCH_MAX
        if pitch_high < PITCH_MIN:
            pitch_high = PITCH_MIN
        if pitch_high > PITCH_MAX:
            pitch_high = PITCH_MAX
        if pitch_low > pitch_high:
            pitch_low, pitch_high = pitch_high, pitch_low
        pitch_range = (pitch_low, pitch_high)

        # Pause duration: use configured values
        pause_low, pause_high = config["pause_duration_ms"]
        if pause_low < PAUSE_DURATION_MIN:
            pause_low = PAUSE_DURATION_MIN
        if pause_low > PAUSE_DURATION_MAX:
            pause_low = PAUSE_DURATION_MAX
        if pause_high < PAUSE_DURATION_MIN:
            pause_high = PAUSE_DURATION_MIN
        if pause_high > PAUSE_DURATION_MAX:
            pause_high = PAUSE_DURATION_MAX
        if pause_low > pause_high:
            pause_low, pause_high = pause_high, pause_low
        pause_duration_ms = (pause_low, pause_high)

        # Max stressed tokens: structural constraint still applies
        max_stressed = config["max_stressed_tokens"]
        max_stressed = max(0, min(1, max_stressed))

        # Build debug info
        debug = {
            "source_regime": regime.value,
            "source_discourse_act": discourse_act.value,
            "acoustic_regime": config["regime"].value,
            "has_lexical_frame": lexical_frame is not None,
            "lexical_selection_count": (
                lexical_frame.count() if lexical_frame is not None else 0
            ),
            "is_safe_default": False,
            "gcc_mode": "DISABLED",
            "gcc_clamping_applied": False,
        }

        return AcousticParameterFrame(
            regime=config["regime"],
            speech_rate=speech_rate,
            energy_level=energy_level,
            pitch_range=pitch_range,
            pause_policy=config["pause_policy"],
            pause_duration_ms=pause_duration_ms,
            emphasis_policy=config["emphasis_policy"],
            max_stressed_tokens=max_stressed,
            suppress_emotion=config["suppress_emotion"],
            suppress_emphasis=config["suppress_emphasis"],
            suppress_certainty=config["suppress_certainty"],
            source_regime=regime.value,
            source_discourse_act=discourse_act.value,
            debug=debug,
        )

    def _build_unclamped_safe_default(
        self,
        regime_envelope: Optional[RegimeEnvelope] = None,
        discourse_envelope: Optional[DiscourseEnvelope] = None,
    ) -> AcousticParameterFrame:
        """
        Build SAFE_DEFAULT frame for GCC DISABLED when inputs are missing.

        Even with GCC DISABLED, we fail-safe to conservative defaults
        when inputs are missing. This maintains structural safety.

        Args:
            regime_envelope: The regime envelope (may be None).
            discourse_envelope: The discourse envelope (may be None).

        Returns:
            SAFE_DEFAULT AcousticParameterFrame.
        """
        config = SAFE_DEFAULT_CONFIG.copy()

        source_regime = (
            regime_envelope.regime.value
            if regime_envelope is not None
            else "HOLD"
        )
        source_discourse_act = (
            discourse_envelope.act.value
            if discourse_envelope is not None
            else "DEFERRAL"
        )

        return AcousticParameterFrame(
            regime=config["regime"],
            speech_rate=config["speech_rate"],
            energy_level=config["energy_level"],
            pitch_range=config["pitch_range"],
            pause_policy=config["pause_policy"],
            pause_duration_ms=config["pause_duration_ms"],
            emphasis_policy=config["emphasis_policy"],
            max_stressed_tokens=config["max_stressed_tokens"],
            suppress_emotion=config["suppress_emotion"],
            suppress_emphasis=config["suppress_emphasis"],
            suppress_certainty=config["suppress_certainty"],
            source_regime=source_regime,
            source_discourse_act=source_discourse_act,
            debug={
                "safe_default_reason": "Missing upstream envelope(s)",
                "is_safe_default": True,
                "gcc_mode": "DISABLED",
                "gcc_clamping_applied": False,
            },
        )


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Constants
    "GCC_VERSION",
    # Dataclasses
    "GCCLedgerEntry",
    # Functions
    "compute_gcc_span_id",
    "compute_layers_hash",
    # Classes
    "P10GCCResolver",
]
