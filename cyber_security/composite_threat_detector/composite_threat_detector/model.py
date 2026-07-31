"""Core data types for the composite-threat detector.

The engine is deterministic and *domain-agnostic*: it knows nothing about guns,
databases, or IAM. All domain knowledge lives in an :class:`Ontology` — a set of
capability :class:`Fragment` definitions, a set of composite-threat
:class:`Recipe` definitions, and a pure ``extract`` function that maps one event
to the fragments it contributes. Swapping the ontology retargets the same engine
from the "assemble a firearm from innocuous parts" illustration to the digital
"assemble data-exfiltration from individually-admissible actions" case.

Nothing here decides admissibility. A detector output is *advisory evidence*: its
strongest possible effect is to recommend escalation to a human (see
``signals.py`` and ``COMPOSITE_THREAT_DETECTION_SPEC.md`` §2). It can never admit,
deny, or satisfy a hard requirement in the underlying Action Gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Fragment:
    """One reusable capability fragment — a "part" that, on its own, is benign.

    ``physical_analogue`` documents the metaphor mapping (e.g. a firearm barrel)
    so the digital ontology and the illustrative physical ontology stay legible
    as two projections of the same idea.
    """

    fragment_id: str
    title: str
    description: str
    physical_analogue: str = ""


@dataclass(frozen=True)
class Recipe:
    """A named composite capability assembled from fragments — the "crime story".

    ``required``  : every fragment here must be present for a *complete* assembly.
    ``optional``  : fragments that corroborate/aggravate but are not load-bearing.
    ``narrative`` : a human-readable template describing the assembled capability.

    Completeness is ``|present ∩ required| / |required|`` — a monotone,
    order-independent score. The engine never treats a partial score as proof;
    it uses it only to decide between *observe* and *escalate* (both advisory).
    """

    recipe_id: str
    name: str
    narrative: str
    required: frozenset[str]
    optional: frozenset[str] = field(default_factory=frozenset)
    physical_analogue: str = ""

    def __post_init__(self) -> None:
        if not self.required:
            raise ValueError(f"recipe {self.recipe_id!r} must have >=1 required fragment")
        overlap = self.required & self.optional
        if overlap:
            raise ValueError(
                f"recipe {self.recipe_id!r}: fragments both required and optional: "
                f"{sorted(overlap)}"
            )


@dataclass(frozen=True)
class FragmentInstance:
    """A concrete observation that a specific event contributed a fragment.

    Carries the provenance needed to reconstruct the story: which admissible
    step, in which position, and a short human-readable note of *why* this event
    counts as this fragment.
    """

    fragment_id: str
    correlation_id: str
    sequence_id: str
    action_id: str
    operation: str
    note: str
    position: int  # deterministic arrival order within the correlation


@dataclass(frozen=True)
class Ontology:
    """A domain binding: fragments + recipes + a pure per-event extractor."""

    ontology_id: str
    version: str
    fragments: dict[str, Fragment]
    recipes: tuple[Recipe, ...]
    extract: Callable[[dict, str, int], list[FragmentInstance]]

    def __post_init__(self) -> None:
        known = set(self.fragments)
        for r in self.recipes:
            unknown = (r.required | r.optional) - known
            if unknown:
                raise ValueError(
                    f"recipe {r.recipe_id!r} references unknown fragments: "
                    f"{sorted(unknown)}"
                )
