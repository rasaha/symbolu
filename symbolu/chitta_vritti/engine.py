"""Chitta-Vṛtti computation engine.

Main orchestrator that combines all components:
- Coherence computation
- Vṛtti distribution
- Score composition
- Explainability

Implements fast-path optimization for low-entropy cases with
viparyaya safety gate.
"""

import time
import logging
from typing import Optional

from symbolu.chitta_vritti.types import (
    ChittaVrittiInputs,
    ChittaVrittiResult,
    OptimizedConfig,
    SessionState,
    CONSUMER_CONFIG,
)
from symbolu.chitta_vritti.coherence import (
    CoherenceComputer,
    quick_opposition_check,
)
from symbolu.chitta_vritti.vritti import VrittiComputer, get_dominant_vritti
from symbolu.chitta_vritti.score import compute_score
from symbolu.chitta_vritti.explain import generate_brief_explanation


logger = logging.getLogger(__name__)


class ChittaVrittiEngine:
    """Main computation engine for Chitta-Vṛtti analysis.

    Orchestrates the full computation pipeline:
    1. Fast-path check (with viparyaya safety gate)
    2. Coherence computation
    3. Vṛtti distribution
    4. Score composition
    5. Result assembly

    Maintains session state for smṛti (memory persistence) tracking.
    """

    def __init__(
        self,
        config: Optional[OptimizedConfig] = None,
        enable_timing: bool = False
    ) -> None:
        """Initialize engine.

        Args:
            config: Configuration (defaults to CONSUMER_CONFIG)
            enable_timing: Whether to log timing information
        """
        self._config = config or CONSUMER_CONFIG
        self._enable_timing = enable_timing

        # Initialize sub-components
        self._coherence_computer = CoherenceComputer(self._config.projection_dim)
        self._vritti_computer = VrittiComputer(self._config)

        # Session state for smṛti tracking
        self._session_state = SessionState()

    @property
    def config(self) -> OptimizedConfig:
        """Get current configuration."""
        return self._config

    def reset_session(self) -> None:
        """Reset session state (clears smṛti accumulation)."""
        self._session_state = SessionState()

    def compute(self, inputs: ChittaVrittiInputs) -> ChittaVrittiResult:
        """Compute Chitta-Vṛtti result for given inputs.

        Args:
            inputs: Input representations and signals

        Returns:
            Complete Chitta-Vṛtti result
        """
        start_time = time.perf_counter_ns() if self._enable_timing else 0

        # Check fast-path eligibility
        if self._can_use_fast_path(inputs):
            result = self._fast_path_pramana(inputs)
        elif inputs.count_missing_layers() >= 3:
            result = self._fast_path_nidra(inputs)
        else:
            result = self._full_computation(inputs)

        # Update session state
        self._session_state.update(inputs, result.vritti.get("smrti", 0.0))

        # Log timing if enabled
        if self._enable_timing:
            elapsed_us = (time.perf_counter_ns() - start_time) / 1000
            if elapsed_us > 100:
                logger.warning(
                    f"Chitta-Vṛtti exceeded 100μs: {elapsed_us:.1f}μs"
                )
            else:
                logger.debug(f"Chitta-Vṛtti completed in {elapsed_us:.1f}μs")

        return result

    def _can_use_fast_path(self, inputs: ChittaVrittiInputs) -> bool:
        """Check if fast-path optimization can be used.

        Fast-path requires:
        1. All layers present
        2. Low entropy
        3. No viparyaya signal (safety gate)

        Args:
            inputs: Input representations

        Returns:
            True if fast-path can be used
        """
        # Check basic conditions
        if not inputs.all_layers_present():
            return False

        if inputs.entropy >= self._config.fast_path_entropy_threshold:
            return False

        # Safety gate: check for viparyaya
        estimated_viparyaya = quick_opposition_check(inputs)
        if estimated_viparyaya >= self._config.fast_path_viparyaya_ceiling:
            return False

        return True

    def _fast_path_pramana(self, inputs: ChittaVrittiInputs) -> ChittaVrittiResult:
        """Fast-path for stable, coherent state.

        Used when all conditions indicate high pramāṇa.

        Args:
            inputs: Input representations

        Returns:
            Pre-computed high-pramāṇa result
        """
        return ChittaVrittiResult(
            coherence=0.95,
            fractures={},  # Skip detailed fracture analysis
            vritti={
                "pramana": 0.85,
                "viparyaya": 0.03,
                "vikalpa": 0.04,
                "smrti": 0.04,
                "nidra": 0.04,
            },
            score=0.90,
            dominant_vritti="pramana",
            primary_fracture=None,
            explanation="Fast path: low entropy, all layers present, no opposition",
            fast_path_used=True,
        )

    def _fast_path_nidra(self, inputs: ChittaVrittiInputs) -> ChittaVrittiResult:
        """Fast-path for dormant state (most layers missing).

        Args:
            inputs: Input representations

        Returns:
            Pre-computed high-nidrā result
        """
        missing = inputs.count_missing_layers()
        nidra_value = missing / 4.0

        # Distribute remaining probability
        remaining = 1.0 - nidra_value
        other_share = remaining / 4.0

        return ChittaVrittiResult(
            coherence=0.5,  # Unknown coherence
            fractures={},
            vritti={
                "pramana": other_share,
                "viparyaya": other_share,
                "vikalpa": other_share,
                "smrti": other_share,
                "nidra": nidra_value,
            },
            score=max(0.0, 0.5 - nidra_value * self._config.penalty_nidra),
            dominant_vritti="nidra",
            primary_fracture=None,
            explanation=f"Fast path: {missing}/4 layers missing, nidrā dominant",
            fast_path_used=True,
        )

    def _full_computation(self, inputs: ChittaVrittiInputs) -> ChittaVrittiResult:
        """Full computation path.

        Args:
            inputs: Input representations

        Returns:
            Complete Chitta-Vṛtti result
        """
        # Step 1: Compute coherence and fractures
        coherence, fractures, primary_fracture = self._coherence_computer.compute(
            inputs
        )

        # Step 2: Compute vṛtti distribution
        vritti, new_smrti = self._vritti_computer.compute(
            inputs=inputs,
            coherence=coherence,
            fractures=fractures,
            previous_inputs=self._session_state.previous_inputs,
            accumulated_smrti=self._session_state.accumulated_smrti,
        )

        # Step 3: Compute score
        score = compute_score(coherence, vritti, self._config)

        # Step 4: Determine dominant vṛtti
        dominant = get_dominant_vritti(vritti)

        # Step 5: Generate explanation
        explanation = self._generate_explanation(
            coherence, fractures, vritti, dominant, primary_fracture
        )

        return ChittaVrittiResult(
            coherence=coherence,
            fractures=fractures,
            vritti=vritti,
            score=score,
            dominant_vritti=dominant,
            primary_fracture=primary_fracture,
            explanation=explanation,
            fast_path_used=False,
        )

    def _generate_explanation(
        self,
        coherence: float,
        fractures: dict[tuple[str, str], float],
        vritti: dict[str, float],
        dominant: str,
        primary_fracture: Optional[tuple[str, str]]
    ) -> str:
        """Generate brief explanation for result.

        Args:
            coherence: Aggregate coherence
            fractures: Pairwise fractures
            vritti: Vṛtti distribution
            dominant: Dominant mode
            primary_fracture: Layer pair with highest fracture

        Returns:
            Brief explanation string
        """
        parts = []

        # Coherence assessment
        if coherence >= 0.8:
            parts.append("High coherence")
        elif coherence >= 0.5:
            parts.append("Moderate coherence")
        else:
            parts.append("Low coherence")

        # Dominant mode
        parts.append(f"{dominant} dominant")

        # Primary fracture
        if primary_fracture and fractures.get(primary_fracture, 0) > 0.4:
            parts.append(
                f"{primary_fracture[0]}-{primary_fracture[1]} disagree"
            )

        return "; ".join(parts)


def create_engine(
    tier: str = "consumer",
    enable_timing: bool = False
) -> ChittaVrittiEngine:
    """Factory function to create engine with tier-specific config.

    Args:
        tier: "consumer" or "enterprise"
        enable_timing: Whether to log timing

    Returns:
        Configured engine
    """
    from symbolu.chitta_vritti.types import CONSUMER_CONFIG, ENTERPRISE_CONFIG

    if tier == "enterprise":
        config = ENTERPRISE_CONFIG
    else:
        config = CONSUMER_CONFIG

    return ChittaVrittiEngine(config=config, enable_timing=enable_timing)
