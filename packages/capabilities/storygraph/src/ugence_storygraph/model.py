"""Core data types for the Composite Capability & Sequence-Risk Analyzer.

The engine is deterministic and *domain-agnostic*: it knows nothing about guns,
databases, or IAM. All domain knowledge lives in an :class:`Ontology` — a set of
capability :class:`Fragment` definitions, a set of :class:`Recipe` definitions,
and a pure ``extract`` function that maps one event to the fragments it
contributes. Swapping the ontology retargets the same engine from the synthetic
"assemble a firearm from innocuous parts" illustration to the product target:
enterprise AI-agent and infrastructure workflows.

Nothing here decides admissibility. The analyzer produces *advisory evidence*:
its strongest output is a recommendation to escalate a case to a human (see
``signals.py`` and ``docs/architecture/COMPOSITE_THREAT_DETECTION_SPEC.md`` §2). It can never
admit, deny, authorize, block, or satisfy a hard requirement in the underlying
ActionGate. An ActionGate/workflow policy — not this analyzer — owns any binding
consequence (``policy.py``).

Scope of this version: deterministic, recipe- and ontology-driven, advisory,
limited to *encoded* capability patterns. It is **not** a general
intent-understanding system and **not** a learned anomaly detector.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

# Fragment decay classes (see ledger.py). PERSISTENT capability survives in the
# capability ledger until explicitly revoked; TRANSIENT evidence decays.
PERSISTENT = "PERSISTENT"
TRANSIENT = "TRANSIENT"
DECAY_CLASSES = frozenset({PERSISTENT, TRANSIENT})

ACTOR_SCOPES = frozenset({"ANY_ACTOR", "SAME_ACTOR", "REQUIRE_MULTI_ACTOR"})
RESOURCE_SCOPES = frozenset({"ANY", "SAME_TARGET_FAMILY"})
SEVERITIES = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})


@dataclass(frozen=True)
class Fragment:
    """One reusable capability fragment — a "part" that, on its own, is benign.

    ``decay_class`` decides how the fragment ages in the capability ledger:
    PERSISTENT (a credential obtained, a privilege granted, a foothold — durable
    until revoked) vs TRANSIENT (a one-off discovery read — decays). This is what
    lets a *long-and-slow* assembly still be detected: durable parts do not fall
    out of a short event window.

    ``physical_analogue`` documents the metaphor mapping so the digital ontology
    and the synthetic physical ontology stay legible as two projections.
    """

    fragment_id: str
    title: str
    description: str
    decay_class: str = TRANSIENT
    physical_analogue: str = ""

    def __post_init__(self) -> None:
        if self.decay_class not in DECAY_CLASSES:
            raise ValueError(f"fragment {self.fragment_id!r}: bad decay_class "
                             f"{self.decay_class!r}")


@dataclass(frozen=True)
class Recipe:
    """A named composite capability assembled from fragments (§6).

    Matching is deliberately *not* pure fragment-count. A sequence must not be
    escalated merely because it contains the same nouns as a prohibited
    capability; the structural constraints below must also hold.

    Fields
    ------
    required / optional      : load-bearing vs corroborating fragments.
    mutually_exclusive       : tuple of fragment-id sets; two members of one set
                               present ⇒ the assembly is *impossible* under this
                               recipe (used by completion analysis).
    ordering                 : (before_id, after_id) pairs; ``before`` must occur
                               at an earlier position than ``after``.
    max_assembly_gap         : max span (timescale units) between the first and
                               last contributing required fragment, or None.
    pair_gaps                : {(a,b): (min_gap, max_gap)} temporal bounds, units
                               as the active timescale; None entries are open.
    actor_scope              : ANY_ACTOR / SAME_ACTOR / REQUIRE_MULTI_ACTOR.
    resource_scope           : ANY / SAME_TARGET_FAMILY.
    completion_threshold     : fraction of ``required`` present to be "complete".
    escalation_threshold     : fraction of ``required`` present to escalate.
    observe_threshold        : fraction to raise the OBSERVE watch signal.
    required_corroboration   : fragment ids that must ALSO be present to escalate
                               (beyond the required set).
    min_optional_for_escalation : minimum count of ``optional`` fragments present
                               required before escalation (0 = none).
    benign_exclusions        : benign-context tags that can qualify/downgrade an
                               escalation *when scope-matched* (see benign.py).
    severity                 : LOW / MEDIUM / HIGH / CRITICAL.
    recommended_consequence  : advisory recommendation to policy (non-binding).
    explanation_template     : concise, non-dramatic finding text with {slots}.
    """

    recipe_id: str
    version: str
    name: str
    required: frozenset[str]
    optional: frozenset[str] = field(default_factory=frozenset)
    mutually_exclusive: tuple[frozenset[str], ...] = ()
    ordering: tuple[tuple[str, str], ...] = ()
    max_assembly_gap: float | None = None
    pair_gaps: dict[tuple[str, str], tuple[float | None, float | None]] = field(
        default_factory=dict)
    actor_scope: str = "ANY_ACTOR"
    resource_scope: str = "ANY"
    completion_threshold: float = 1.0
    escalation_threshold: float = 1.0
    observe_threshold: float = 0.5
    required_corroboration: frozenset[str] = field(default_factory=frozenset)
    min_optional_for_escalation: int = 0
    benign_exclusions: frozenset[str] = field(default_factory=frozenset)
    severity: str = "HIGH"
    recommended_consequence: str = "HOLD_FOR_REVIEW"
    # When the recipe declares ordering constraints, ambiguous/conflicting event
    # order does NOT satisfy them unless this is explicitly set (§6). Default is
    # fail-safe: unresolved order caps the signal at OBSERVE.
    permit_ambiguous_ordering: bool = False
    physical_analogue: str = ""
    explanation_template: str = ""

    def __post_init__(self) -> None:
        if not self.required:
            raise ValueError(f"recipe {self.recipe_id!r} must have >=1 required fragment")
        overlap = self.required & self.optional
        if overlap:
            raise ValueError(
                f"recipe {self.recipe_id!r}: fragments both required and optional: "
                f"{sorted(overlap)}")
        if self.actor_scope not in ACTOR_SCOPES:
            raise ValueError(f"recipe {self.recipe_id!r}: bad actor_scope "
                             f"{self.actor_scope!r}")
        if self.resource_scope not in RESOURCE_SCOPES:
            raise ValueError(f"recipe {self.recipe_id!r}: bad resource_scope "
                             f"{self.resource_scope!r}")
        if self.severity not in SEVERITIES:
            raise ValueError(f"recipe {self.recipe_id!r}: bad severity {self.severity!r}")
        if not 0.0 < self.observe_threshold <= self.escalation_threshold <= 1.0:
            raise ValueError(f"recipe {self.recipe_id!r}: thresholds must satisfy "
                             f"0 < observe <= escalate <= 1")
        if not 0.0 < self.completion_threshold <= 1.0:
            raise ValueError(f"recipe {self.recipe_id!r}: bad completion_threshold")
        allknown = self.required | self.optional
        for a, b in self.ordering:
            if a not in allknown or b not in allknown:
                raise ValueError(f"recipe {self.recipe_id!r}: ordering references "
                                 f"unknown fragment(s): {(a, b)}")
        for cor in self.required_corroboration:
            if cor not in allknown:
                raise ValueError(f"recipe {self.recipe_id!r}: corroboration references "
                                 f"unknown fragment {cor!r}")

    @property
    def ref(self) -> str:
        return f"{self.recipe_id}@{self.version}"


@dataclass(frozen=True)
class FragmentInstance:
    """A concrete observation that a specific event contributed a fragment.

    Carries the provenance needed to reconstruct the assembly deterministically:
    the tenant, the linked entities, the ordering position, an optional event
    time (supplied as data — never wall-clock), and dedup keys.
    """

    fragment_id: str
    decay_class: str
    tenant_id: str
    correlation_id: str
    sequence_id: str
    event_id: str
    idempotency_key: str
    operation: str
    actor: str
    entities: dict[str, str]
    note: str
    position: int          # deterministic arrival order within the assembly
    at_epoch: float | None  # event time in seconds if a timestamp was supplied


@dataclass(frozen=True)
class Ontology:
    """A domain binding: fragments + recipes + a pure per-event extractor.

    ``extract(event, ctx) -> [FragmentInstance]`` where ``ctx`` supplies the
    resolved tenant/assembly/position/epoch so the extractor stays a pure
    function of its inputs (see ``fragments.py``).
    """

    ontology_id: str
    version: str
    fragments: dict[str, Fragment]
    recipes: tuple[Recipe, ...]
    extract: Callable[[dict, "ExtractContext"], list[FragmentInstance]]

    def __post_init__(self) -> None:
        known = set(self.fragments)
        for r in self.recipes:
            unknown = (r.required | r.optional) - known
            if unknown:
                raise ValueError(
                    f"recipe {r.recipe_id!r} references unknown fragments: "
                    f"{sorted(unknown)}")
            for group in r.mutually_exclusive:
                bad = group - known
                if bad:
                    raise ValueError(f"recipe {r.recipe_id!r}: mutually_exclusive "
                                     f"references unknown fragments: {sorted(bad)}")


@dataclass(frozen=True)
class ExtractContext:
    """Resolved, deterministic context handed to an ontology extractor."""

    tenant_id: str
    correlation_id: str
    sequence_id: str
    event_id: str
    idempotency_key: str
    position: int
    at_epoch: float | None
    entities: dict[str, str]
