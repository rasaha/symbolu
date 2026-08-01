"""Minimal-completion analysis (§8) — a deterministic, advisory extension.

For a partially-matched recipe, this reports which capability fragments would
complete the recipe if they appeared next, and whether structural constraints
already make completion impossible. It is a lookahead over *known encoded*
recipes — nothing more.

Explicitly:

* This does **not** predict attacker intent.
* This is **not** claimed to be novel or patentable (attack-path reachability and
  multi-stage attack reconstruction have substantial prior art — see
  ``docs/architecture/COMPOSITE_THREAT_DETECTION_SPEC.md`` §14).
* The output is advisory evidence, exactly like the rest of the analyzer.

Phrasing used everywhere: *"the analyzer identifies which capability fragments
would complete a known recipe if they appeared next."*
"""

from __future__ import annotations

from dataclasses import dataclass

from .matcher import MatchResult


@dataclass
class CompletionAnalysis:
    remaining_required: list[str]     # fragments still needed
    remaining_distance: int           # count of required fragments still missing
    completing_fragments: list[str]   # which next-fragments would reduce distance
    completion_possible: bool
    impossible_reason: str


def analyze(result: MatchResult) -> CompletionAnalysis:
    """Deterministic minimal-completion for one recipe match."""
    remaining = list(result.missing_required)
    if result.impossible:
        return CompletionAnalysis(
            remaining_required=remaining,
            remaining_distance=len(remaining),
            completing_fragments=[],
            completion_possible=False,
            impossible_reason=result.impossible_reason or "recipe constraints unsatisfiable",
        )
    # The fragments that, if observed next, would materially reduce the distance
    # to completion are exactly the still-missing required fragments (plus any
    # required corroboration not yet present).
    completing = sorted(set(remaining) | (
        result.recipe.required_corroboration
        - set(result.present_required) - set(result.present_optional)))
    return CompletionAnalysis(
        remaining_required=remaining,
        remaining_distance=len(remaining),
        completing_fragments=completing,
        completion_possible=True,
        impossible_reason="",
    )
