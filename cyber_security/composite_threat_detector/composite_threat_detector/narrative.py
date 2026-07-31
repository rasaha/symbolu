"""Deterministic reconstruction of the 'story' from matched fragments.

Given a recipe and the fragment instances observed for one correlation, build a
stable, human-readable account: what capability is being assembled, which
admissible steps contributed which part, and — the operationally useful bit —
which part is still missing (the step to watch for next).
"""

from __future__ import annotations

from .model import FragmentInstance, Ontology, Recipe


def build_story(
    ontology: Ontology,
    recipe: Recipe,
    instances: list[FragmentInstance],
) -> dict:
    """Return a structured, deterministic narrative for one recipe match.

    ``instances`` is every fragment observed for the correlation (the caller need
    not pre-filter); this function selects the ones relevant to ``recipe`` and
    orders the reconstructed steps by their arrival ``position`` (then sequence
    id), so the story reads in the order the assembly actually happened.
    """
    relevant_ids = recipe.required | recipe.optional
    relevant = [i for i in instances if i.fragment_id in relevant_ids]
    relevant.sort(key=lambda i: (i.position, i.sequence_id, i.fragment_id))

    present = {i.fragment_id for i in relevant}
    present_required = sorted(recipe.required & present)
    missing_required = sorted(recipe.required - present)
    present_optional = sorted(recipe.optional & present)

    steps = [
        {
            "position": i.position,
            "sequence_id": i.sequence_id,
            "action_id": i.action_id,
            "operation": i.operation,
            "fragment_id": i.fragment_id,
            "fragment_title": ontology.fragments[i.fragment_id].title,
            "note": i.note,
        }
        for i in relevant
    ]

    headline = (
        f"Correlation is assembling '{recipe.name}': {recipe.narrative}."
        if not missing_required
        else (
            f"Correlation is partially assembling '{recipe.name}' "
            f"({len(present_required)}/{len(recipe.required)} required parts). "
            f"Still missing: {', '.join(missing_required)}."
        )
    )

    return {
        "recipe_id": recipe.recipe_id,
        "recipe_name": recipe.name,
        "headline": headline,
        "physical_analogue": recipe.physical_analogue,
        "present_required": present_required,
        "missing_required": missing_required,
        "present_optional": present_optional,
        "steps": steps,
    }
