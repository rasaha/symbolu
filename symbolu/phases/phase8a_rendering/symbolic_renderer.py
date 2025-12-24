"""
Phase-8A Rendering Layer - Symbolic Renderer

Transforms Phase-7 outputs into abstract symbol sequences.
Deterministic mapping from tokens/trajectories to symbols.

Contract: docs/contracts/PHASE_8A_RENDERING_CONTRACT.md Section 7
"""

from typing import FrozenSet

from symbolu.phases.phase8a_rendering.types import (
    RenderInput,
    RenderModality,
    RendererConfig,
    SymbolicArtifact,
)
from symbolu.phases.phase8a_rendering.renderer import Renderer


# Deterministic token → symbol mapping (from contract Section 7)
TOKEN_TO_SYMBOL: dict[str, str] = {
    "ka": "\u25c6",  # ◆
    "ga": "\u25c7",  # ◇
    "ta": "\u25b2",  # ▲
    "da": "\u25b3",  # △
    "pa": "\u25cf",  # ●
    "ba": "\u25cb",  # ○
    "a": "\u2500",   # ─
    "i": "\u2502",   # │
    "u": "\u253c",   # ┼
}

# Default symbol for unknown tokens (deterministic fallback)
DEFAULT_SYMBOL = "\u25a1"  # □


class SymbolicRenderer(Renderer):
    """
    Renderer that transforms sequences into abstract symbol sequences.

    Properties:
      - Deterministic: same input always produces same output
      - Stateless: no state between render() calls
      - Non-selective: does not access score/rank fields

    Derivation rules (from contract):
      - Symbol: deterministic mapping from token
      - Grouping: reset events start new groups
      - Connector: based on magnitude delta between groups
    """

    def __init__(self):
        super().__init__(
            renderer_id="symbolic_v1",
            modality=RenderModality.SYMBOLIC,
        )

    @property
    def supported_formats(self) -> FrozenSet[str]:
        """Supported output formats."""
        return frozenset({"default", "unicode", "ascii"})

    def _do_render(
        self, render_input: RenderInput, config: RendererConfig
    ) -> SymbolicArtifact:
        """
        Render sequence to symbolic artifact.

        Accesses only trajectory data (per INV-6):
          - trajectory.sequence (tokens)
          - trajectory.steps[i].event (for grouping)
          - trajectory.steps[i].magnitude (for connectors)

        Selection fields (INV-6 forbidden) are never read here.
        """
        trajectory = render_input.ranked_result.trajectory
        sequence = trajectory.sequence
        steps = trajectory.steps

        # Map tokens to symbols (deterministic)
        symbols = tuple(
            self._token_to_symbol(token, config.output_format)
            for token in sequence
        )

        # Compute groupings from events (reset starts new group)
        groupings = self._compute_groupings(steps)

        # Compute connectors from magnitude deltas
        connectors = self._compute_connectors(steps, groupings)

        return SymbolicArtifact(
            symbols=symbols,
            groupings=groupings,
            connectors=connectors,
        )

    def _token_to_symbol(self, token: str, output_format: str) -> str:
        """
        Map token to symbol deterministically.

        Args:
            token: Varna token
            output_format: Output format (unicode or ascii)

        Returns:
            Symbol string
        """
        if output_format == "ascii":
            # ASCII fallback mapping
            ascii_map = {
                "ka": "K", "ga": "G", "ta": "T",
                "da": "D", "pa": "P", "ba": "B",
                "a": "-", "i": "|", "u": "+",
            }
            return ascii_map.get(token, "?")

        # Default unicode mapping
        return TOKEN_TO_SYMBOL.get(token, DEFAULT_SYMBOL)

    def _compute_groupings(
        self, steps: tuple
    ) -> tuple[tuple[int, ...], ...]:
        """
        Compute symbol groupings from events.

        Reset events start new groups.
        Each group is a tuple of indices.
        """
        if not steps:
            return ()

        groups = []
        current_group = []

        for i, step in enumerate(steps):
            if step.event == "reset" and current_group:
                # Save previous group and start new one
                groups.append(tuple(current_group))
                current_group = [i]
            else:
                current_group.append(i)

        # Add final group
        if current_group:
            groups.append(tuple(current_group))

        return tuple(groups)

    def _compute_connectors(
        self, steps: tuple, groupings: tuple[tuple[int, ...], ...]
    ) -> tuple[str, ...]:
        """
        Compute connectors between groups based on magnitude delta.

        Connector rules (from contract):
          - delta > 0.3  → "→" (rising)
          - delta < -0.3 → "←" (falling)
          - otherwise    → "·" (stable)
        """
        if len(groupings) <= 1:
            return ()

        connectors = []
        for i in range(len(groupings) - 1):
            # Get last magnitude of current group
            current_last_idx = groupings[i][-1]
            current_mag = steps[current_last_idx].magnitude

            # Get first magnitude of next group
            next_first_idx = groupings[i + 1][0]
            next_mag = steps[next_first_idx].magnitude

            # Compute delta and determine connector
            delta = next_mag - current_mag
            if delta > 0.3:
                connectors.append("\u2192")  # → rising
            elif delta < -0.3:
                connectors.append("\u2190")  # ← falling
            else:
                connectors.append("\u00b7")  # · stable

        return tuple(connectors)
