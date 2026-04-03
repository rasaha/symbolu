"""
Symbol-U Pipeline Router (v3.0 - Option C)

Future-proof router abstraction for the hybrid pipeline.

v3.0 Implementation:
    - Always returns "linear" mode (simple sequential execution)
    - Provides clean extension points for v3.1+ adaptive flows

Future Modes (v3.1+):
    - "dha_first": Run DHA early for high-resistance detection
    - "dual_branch": Parallel symbolic + practical paths
    - "resistance_loop": Iterative adaptation cycle
    - "entropy_priority": Dynamic ordering based on entropy metrics

The router inspects PipelineContext and decides which execution path
to take. In v3.0, all paths resolve to linear for production safety.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .models import PipelineContext


class PipelineRouter:
    """
    Pipeline routing decision engine.

    Option C Router Design:
    - v3.0: Always linear (production-safe baseline)
    - v3.1+: Inspect context for adaptive decisions

    The router is called early in the pipeline (typically after Persona
    or MLCR) to determine execution strategy. Results are stored in
    ctx.router_mode for downstream stages to consume.

    Example Usage:
        router = PipelineRouter()
        ctx.router_mode = router.decide(ctx)
        # ctx.router_mode == "linear" in v3.0
    """

    # Valid routing modes (for validation and documentation)
    VALID_MODES = frozenset({
        "linear",           # v3.0: Sequential Persona -> MLCR -> Fusion -> DHA -> Render
        "dha_first",        # v3.1: Run DHA analysis before Fusion for early adaptation
        "dual_branch",      # v3.1: Parallel symbolic and practical reasoning branches
        "resistance_loop",  # v3.1: Iterative DHA cycles for high-resistance cases
        "entropy_priority", # v3.1: Dynamic stage ordering based on entropy metrics
    })

    def __init__(self, force_mode: Optional[str] = None) -> None:
        """
        Initialize the router.

        Args:
            force_mode: Optional mode override for testing. Must be in VALID_MODES.
        """
        if force_mode is not None and force_mode not in self.VALID_MODES:
            raise ValueError(f"Invalid force_mode '{force_mode}'. Must be one of {self.VALID_MODES}")
        self._force_mode = force_mode

    def decide(self, ctx: "PipelineContext") -> str:
        """
        Decide which pipeline routing mode to use.

        v3.0 Implementation:
            Always returns "linear" - the safe production default.

        v3.1+ Roadmap (TODO):
            Inspect ctx for signals that warrant adaptive routing:

            1. "dha_first" - High resistance early detection:
                - ctx.request.metadata.get("resistance_hint") == "high"
                - Previous session showed resistance patterns
                - Domain is known to be emotionally charged

            2. "dual_branch" - Complex multi-perspective queries:
                - MLCR entropy (H_D, H_G, H_K) all above threshold
                - Intent classification is ambiguous
                - Query contains both "why" and "how" signals

            3. "resistance_loop" - Adaptive iteration:
                - DHA readiness_level == "LOW"
                - Multiple resistance_flags detected
                - User feedback indicates non-receptivity

            4. "entropy_priority" - Dynamic ordering:
                - Very high H_D (domain uncertainty) -> prioritize domain resolution
                - Very high H_G (goal uncertainty) -> prioritize intent clarification
                - Very high H_K (knowledge uncertainty) -> prioritize RAG augmentation

        Args:
            ctx: Current PipelineContext with accumulated stage results.

        Returns:
            Routing mode string. Always "linear" in v3.0.
        """
        # Allow test override
        if self._force_mode is not None:
            return self._force_mode

        # ============================================================
        # v3.0: ALWAYS LINEAR
        # This is the production-safe baseline. All adaptive logic
        # is documented but disabled until v3.1 validation.
        # ============================================================

        # TODO v3.1: Check for dha_first conditions
        # if self._should_dha_first(ctx):
        #     return "dha_first"

        # TODO v3.1: Check for dual_branch conditions
        # if self._should_dual_branch(ctx):
        #     return "dual_branch"

        # TODO v3.1: Check for resistance_loop conditions
        # if self._should_resistance_loop(ctx):
        #     return "resistance_loop"

        # TODO v3.1: Check for entropy_priority conditions
        # if self._should_entropy_priority(ctx):
        #     return "entropy_priority"

        return "linear"

    def _should_dha_first(self, ctx: "PipelineContext") -> bool:
        """
        TODO v3.1: Determine if DHA should run before Fusion.

        Conditions to check:
        - Request metadata hints at high resistance
        - Domain is emotionally sensitive (relationships, health, finance)
        - Previous session context shows defensive patterns

        Args:
            ctx: Pipeline context.

        Returns:
            True if dha_first mode is recommended.
        """
        # v3.0: Always False
        return False

    def _should_dual_branch(self, ctx: "PipelineContext") -> bool:
        """
        TODO v3.1: Determine if parallel symbolic/practical branches needed.

        Conditions to check:
        - High entropy across all H_D, H_G, H_K dimensions
        - Ambiguous intent (multiple categories scoring similarly)
        - Query explicitly requests multiple perspectives

        Args:
            ctx: Pipeline context.

        Returns:
            True if dual_branch mode is recommended.
        """
        # v3.0: Always False
        return False

    def _should_resistance_loop(self, ctx: "PipelineContext") -> bool:
        """
        TODO v3.1: Determine if iterative adaptation is needed.

        Conditions to check:
        - DHA readiness_level is LOW
        - Multiple resistance flags detected
        - Ego state indicates defensiveness

        Args:
            ctx: Pipeline context (requires DHA to have run once).

        Returns:
            True if resistance_loop mode is recommended.
        """
        # v3.0: Always False
        return False

    def _should_entropy_priority(self, ctx: "PipelineContext") -> bool:
        """
        TODO v3.1: Determine if dynamic entropy-based ordering needed.

        Conditions to check:
        - Extreme entropy in one dimension (H_D > 0.9 or similar)
        - Large variance between entropy dimensions
        - Known domain uncertainty for this query type

        Args:
            ctx: Pipeline context.

        Returns:
            True if entropy_priority mode is recommended.
        """
        # v3.0: Always False
        return False

    def explain(self, mode: str) -> str:
        """
        Get a human-readable explanation of a routing mode.

        Args:
            mode: Routing mode string.

        Returns:
            Description of what the mode does.
        """
        explanations = {
            "linear": (
                "Sequential pipeline: Persona -> MLCR -> Fusion -> DHA -> Render. "
                "Safe, deterministic, production-ready."
            ),
            "dha_first": (
                "Run DHA analysis early (before Fusion) to detect resistance patterns. "
                "Enables pre-emptive tone adjustment."
            ),
            "dual_branch": (
                "Parallel execution of symbolic and practical reasoning branches. "
                "Merges results for complex multi-perspective queries."
            ),
            "resistance_loop": (
                "Iterative adaptation cycle when initial delivery fails. "
                "Re-runs DHA and rendering with progressively softer approaches."
            ),
            "entropy_priority": (
                "Dynamic stage ordering based on entropy metrics. "
                "Prioritizes uncertainty reduction in the highest-entropy dimension."
            ),
        }
        return explanations.get(mode, f"Unknown mode: {mode}")


def get_default_router() -> PipelineRouter:
    """
    Factory function to get the default pipeline router.

    Returns:
        A PipelineRouter instance with default (linear) behavior.
    """
    return PipelineRouter()


# Public exports
__all__ = [
    "PipelineRouter",
    "get_default_router",
]
