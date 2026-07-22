"""
TAP-E3 relationship ontology (compact, explicit, versioned).

A BOUNDED enterprise-relevant set of relationship types — not an attempt to model every
possible semantic relation. Grouped into families, with documented inverses. Inverses
are only applied where this module explicitly allows them (``INVERSES``); the extractor
never invents an inverse otherwise.

The predicate lexicon maps surface phrases to (RelationshipType, form). ``form`` marks
active vs passive so direction resolution can flip subject/object for passives.

HONESTY: this is a deterministic, pattern-based lexicon over synthetic enterprise
sentences authored to be parseable. It does not claim general natural-language
understanding.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Mapping, Tuple

ONTOLOGY_VERSION = "tap-e3-ontology/1.0.0"


class RelationshipType(str, Enum):
    # 6.1 ownership & control
    OWNS = "OWNS"
    OWNED_BY = "OWNED_BY"
    CONTROLLED_BY = "CONTROLLED_BY"
    MANAGES = "MANAGES"
    OPERATES = "OPERATES"
    ADMINISTERS = "ADMINISTERS"
    # 6.2 commercial & legal
    LICENSES = "LICENSES"
    DISTRIBUTES = "DISTRIBUTES"
    SUPPLIES = "SUPPLIES"
    PURCHASES_FROM = "PURCHASES_FROM"
    CONTRACTED_WITH = "CONTRACTED_WITH"
    OBLIGATED_TO = "OBLIGATED_TO"
    AUTHORIZED_BY = "AUTHORIZED_BY"
    PROHIBITED_FROM = "PROHIBITED_FROM"
    PERMITTED_TO = "PERMITTED_TO"
    # 6.3 technical & structural
    DEPENDS_ON = "DEPENDS_ON"
    DEPENDENCY_OF = "DEPENDENCY_OF"
    CONNECTS_TO = "CONNECTS_TO"
    CALLS = "CALLS"
    USES = "USES"
    IMPLEMENTS = "IMPLEMENTS"
    EXTENDS = "EXTENDS"
    CONTAINS = "CONTAINS"
    PART_OF = "PART_OF"
    HOSTED_ON = "HOSTED_ON"
    REPLACES = "REPLACES"
    SUPERSEDES = "SUPERSEDES"
    SUPERSEDED_BY = "SUPERSEDED_BY"
    # 6.4 governance & applicability signals (representation only)
    APPLIES_TO = "APPLIES_TO"
    EXEMPTS = "EXEMPTS"
    GOVERNS = "GOVERNS"
    REQUIRES = "REQUIRES"
    PROHIBITS = "PROHIBITS"
    OVERRIDES = "OVERRIDES"
    SUBORDINATE_TO = "SUBORDINATE_TO"
    # 6.5 informational
    REFERENCES = "REFERENCES"
    DESCRIBES = "DESCRIBES"
    REPORTS = "REPORTS"
    ATTRIBUTES_TO = "ATTRIBUTES_TO"
    RECOMMENDS = "RECOMMENDS"
    ALLEGES = "ALLEGES"
    CLAIMS = "CLAIMS"
    # 6.6 temporal & causal
    PRECEDES = "PRECEDES"
    FOLLOWS = "FOLLOWS"
    TRIGGERS = "TRIGGERS"
    CAUSES = "CAUSES"
    RESULTS_IN = "RESULTS_IN"
    VALID_FROM = "VALID_FROM"
    VALID_UNTIL = "VALID_UNTIL"
    # fallback
    OTHER = "OTHER"
    UNMAPPED = "UNMAPPED"


FAMILIES: Mapping[str, Tuple[RelationshipType, ...]] = {
    "ownership_control": (RelationshipType.OWNS, RelationshipType.OWNED_BY,
                          RelationshipType.CONTROLLED_BY, RelationshipType.MANAGES,
                          RelationshipType.OPERATES, RelationshipType.ADMINISTERS),
    "commercial_legal": (RelationshipType.LICENSES, RelationshipType.DISTRIBUTES,
                         RelationshipType.SUPPLIES, RelationshipType.PURCHASES_FROM,
                         RelationshipType.CONTRACTED_WITH, RelationshipType.OBLIGATED_TO,
                         RelationshipType.AUTHORIZED_BY, RelationshipType.PROHIBITED_FROM,
                         RelationshipType.PERMITTED_TO),
    "technical_structural": (RelationshipType.DEPENDS_ON, RelationshipType.DEPENDENCY_OF,
                             RelationshipType.CONNECTS_TO, RelationshipType.CALLS,
                             RelationshipType.USES, RelationshipType.IMPLEMENTS,
                             RelationshipType.EXTENDS, RelationshipType.CONTAINS,
                             RelationshipType.PART_OF, RelationshipType.HOSTED_ON,
                             RelationshipType.REPLACES, RelationshipType.SUPERSEDES,
                             RelationshipType.SUPERSEDED_BY),
    "governance_signal": (RelationshipType.APPLIES_TO, RelationshipType.EXEMPTS,
                          RelationshipType.GOVERNS, RelationshipType.REQUIRES,
                          RelationshipType.PROHIBITS, RelationshipType.OVERRIDES,
                          RelationshipType.SUBORDINATE_TO),
    "informational": (RelationshipType.REFERENCES, RelationshipType.DESCRIBES,
                      RelationshipType.REPORTS, RelationshipType.ATTRIBUTES_TO,
                      RelationshipType.RECOMMENDS, RelationshipType.ALLEGES,
                      RelationshipType.CLAIMS),
    "temporal_causal": (RelationshipType.PRECEDES, RelationshipType.FOLLOWS,
                        RelationshipType.TRIGGERS, RelationshipType.CAUSES,
                        RelationshipType.RESULTS_IN, RelationshipType.VALID_FROM,
                        RelationshipType.VALID_UNTIL),
}

# Documented inverses (applied ONLY when explicitly requested; never auto-inferred).
INVERSES: Mapping[RelationshipType, RelationshipType] = {
    RelationshipType.OWNS: RelationshipType.OWNED_BY,
    RelationshipType.OWNED_BY: RelationshipType.OWNS,
    RelationshipType.SUPERSEDES: RelationshipType.SUPERSEDED_BY,
    RelationshipType.SUPERSEDED_BY: RelationshipType.SUPERSEDES,
    RelationshipType.PART_OF: RelationshipType.CONTAINS,
    RelationshipType.CONTAINS: RelationshipType.PART_OF,
    RelationshipType.DEPENDS_ON: RelationshipType.DEPENDENCY_OF,
    RelationshipType.DEPENDENCY_OF: RelationshipType.DEPENDS_ON,
}

# Ontology-equivalent groupings for lenient scoring (a prediction in the same group as
# the gold predicate counts as ontology-equivalent, though not exact).
EQUIVALENCE_GROUPS: Tuple[Tuple[RelationshipType, ...], ...] = (
    (RelationshipType.REPLACES, RelationshipType.SUPERSEDES),
    (RelationshipType.PROHIBITED_FROM, RelationshipType.PROHIBITS),
    (RelationshipType.OBLIGATED_TO, RelationshipType.REQUIRES),
    (RelationshipType.PERMITTED_TO, RelationshipType.AUTHORIZED_BY),
    (RelationshipType.OPERATES, RelationshipType.MANAGES, RelationshipType.ADMINISTERS),
    (RelationshipType.ALLEGES, RelationshipType.CLAIMS),
)


class Form(str, Enum):
    ACTIVE = "active"
    PASSIVE = "passive"


# Predicate lexicon: (regex-ready phrase, RelationshipType, Form). Longer/more specific
# phrases must be listed before shorter ones (the extractor tries them in order).
PREDICATE_LEXICON: Tuple[Tuple[str, RelationshipType, Form], ...] = (
    # passive / by-agent forms first
    ("is owned by", RelationshipType.OWNS, Form.PASSIVE),
    ("are owned by", RelationshipType.OWNS, Form.PASSIVE),
    ("owned by", RelationshipType.OWNS, Form.PASSIVE),
    ("is operated by", RelationshipType.OPERATES, Form.PASSIVE),
    ("are operated by", RelationshipType.OPERATES, Form.PASSIVE),
    ("operated by", RelationshipType.OPERATES, Form.PASSIVE),
    ("is managed by", RelationshipType.MANAGES, Form.PASSIVE),
    ("managed by", RelationshipType.MANAGES, Form.PASSIVE),
    ("is controlled by", RelationshipType.CONTROLLED_BY, Form.ACTIVE),
    ("controlled by", RelationshipType.CONTROLLED_BY, Form.ACTIVE),
    ("is administered by", RelationshipType.ADMINISTERS, Form.PASSIVE),
    ("administered by", RelationshipType.ADMINISTERS, Form.PASSIVE),
    ("is hosted on", RelationshipType.HOSTED_ON, Form.ACTIVE),
    ("hosted on", RelationshipType.HOSTED_ON, Form.ACTIVE),
    ("is supplied by", RelationshipType.SUPPLIES, Form.PASSIVE),
    ("supplied by", RelationshipType.SUPPLIES, Form.PASSIVE),
    ("is superseded by", RelationshipType.SUPERSEDES, Form.PASSIVE),
    ("superseded by", RelationshipType.SUPERSEDES, Form.PASSIVE),
    # attribution / informational (checked before generic verbs)
    ("alleges that", RelationshipType.ALLEGES, Form.ACTIVE),
    ("alleges", RelationshipType.ALLEGES, Form.ACTIVE),
    ("claims that", RelationshipType.CLAIMS, Form.ACTIVE),
    ("claims", RelationshipType.CLAIMS, Form.ACTIVE),
    ("reports that", RelationshipType.REPORTS, Form.ACTIVE),
    ("recommends", RelationshipType.RECOMMENDS, Form.ACTIVE),
    ("references", RelationshipType.REFERENCES, Form.ACTIVE),
    ("refers to", RelationshipType.REFERENCES, Form.ACTIVE),
    ("describes", RelationshipType.DESCRIBES, Form.ACTIVE),
    # authorization / permission / prohibition
    ("is not authorized to", RelationshipType.PERMITTED_TO, Form.ACTIVE),
    ("are not authorized to", RelationshipType.PERMITTED_TO, Form.ACTIVE),
    ("not authorized to", RelationshipType.PERMITTED_TO, Form.ACTIVE),
    ("is not permitted to", RelationshipType.PERMITTED_TO, Form.ACTIVE),
    ("are not permitted to", RelationshipType.PERMITTED_TO, Form.ACTIVE),
    ("not permitted to", RelationshipType.PERMITTED_TO, Form.ACTIVE),
    ("prohibited from", RelationshipType.PROHIBITED_FROM, Form.ACTIVE),
    ("authorizes", RelationshipType.AUTHORIZED_BY, Form.ACTIVE),
    ("authorized to", RelationshipType.PERMITTED_TO, Form.ACTIVE),
    ("permitted to", RelationshipType.PERMITTED_TO, Form.ACTIVE),
    ("obligated to", RelationshipType.OBLIGATED_TO, Form.ACTIVE),
    ("required to", RelationshipType.OBLIGATED_TO, Form.ACTIVE),
    # governance signals
    ("applies to", RelationshipType.APPLIES_TO, Form.ACTIVE),
    ("apply to", RelationshipType.APPLIES_TO, Form.ACTIVE),
    ("exempts", RelationshipType.EXEMPTS, Form.ACTIVE),
    ("governs", RelationshipType.GOVERNS, Form.ACTIVE),
    ("overrides", RelationshipType.OVERRIDES, Form.ACTIVE),
    ("subordinate to", RelationshipType.SUBORDINATE_TO, Form.ACTIVE),
    ("prohibits", RelationshipType.PROHIBITS, Form.ACTIVE),
    ("requires", RelationshipType.REQUIRES, Form.ACTIVE),
    # technical / structural
    ("depends on", RelationshipType.DEPENDS_ON, Form.ACTIVE),
    ("depended on", RelationshipType.DEPENDS_ON, Form.ACTIVE),
    ("depend on", RelationshipType.DEPENDS_ON, Form.ACTIVE),
    ("connects to", RelationshipType.CONNECTS_TO, Form.ACTIVE),
    ("connect to", RelationshipType.CONNECTS_TO, Form.ACTIVE),
    ("calls", RelationshipType.CALLS, Form.ACTIVE),
    ("implements", RelationshipType.IMPLEMENTS, Form.ACTIVE),
    ("extends", RelationshipType.EXTENDS, Form.ACTIVE),
    ("contains", RelationshipType.CONTAINS, Form.ACTIVE),
    ("part of", RelationshipType.PART_OF, Form.ACTIVE),
    ("uses", RelationshipType.USES, Form.ACTIVE),
    ("use", RelationshipType.USES, Form.ACTIVE),
    # commercial / legal
    ("licenses", RelationshipType.LICENSES, Form.ACTIVE),
    ("distributes", RelationshipType.DISTRIBUTES, Form.ACTIVE),
    ("supplies", RelationshipType.SUPPLIES, Form.ACTIVE),
    ("purchases from", RelationshipType.PURCHASES_FROM, Form.ACTIVE),
    ("contracted with", RelationshipType.CONTRACTED_WITH, Form.ACTIVE),
    # ownership / control active
    ("owns", RelationshipType.OWNS, Form.ACTIVE),
    ("manages", RelationshipType.MANAGES, Form.ACTIVE),
    ("operates", RelationshipType.OPERATES, Form.ACTIVE),
    ("administers", RelationshipType.ADMINISTERS, Form.ACTIVE),
    # temporal / causal
    ("supersedes", RelationshipType.SUPERSEDES, Form.ACTIVE),
    ("replaces", RelationshipType.REPLACES, Form.ACTIVE),
    ("precedes", RelationshipType.PRECEDES, Form.ACTIVE),
    ("follows", RelationshipType.FOLLOWS, Form.ACTIVE),
    ("triggers", RelationshipType.TRIGGERS, Form.ACTIVE),
    ("causes", RelationshipType.CAUSES, Form.ACTIVE),
    ("caused", RelationshipType.CAUSES, Form.ACTIVE),
    ("results in", RelationshipType.RESULTS_IN, Form.ACTIVE),
    ("notify", RelationshipType.OBLIGATED_TO, Form.ACTIVE),
    ("escalate", RelationshipType.OBLIGATED_TO, Form.ACTIVE),
    ("access", RelationshipType.PERMITTED_TO, Form.ACTIVE),
)


def predicates_in_ontology() -> int:
    return len([r for r in RelationshipType if r not in
                (RelationshipType.OTHER, RelationshipType.UNMAPPED)])
