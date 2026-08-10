# TAP-E3 — Relationship Ontology (`tap-e3-ontology/1.0.0`)

A **compact, bounded, enterprise-relevant** set (49 types) — not an attempt to model
every semantic relation. Grouped into families; an `OTHER`/`UNMAPPED` fallback exists but
is not overused (co-occurrence baseline A uses `OTHER`).

## Families

- **Ownership & control:** OWNS, OWNED_BY, CONTROLLED_BY, MANAGES, OPERATES, ADMINISTERS
- **Commercial & legal:** LICENSES, DISTRIBUTES, SUPPLIES, PURCHASES_FROM,
  CONTRACTED_WITH, OBLIGATED_TO, AUTHORIZED_BY, PROHIBITED_FROM, PERMITTED_TO
- **Technical & structural:** DEPENDS_ON, DEPENDENCY_OF, CONNECTS_TO, CALLS, USES,
  IMPLEMENTS, EXTENDS, CONTAINS, PART_OF, HOSTED_ON, REPLACES, SUPERSEDES, SUPERSEDED_BY
- **Governance signals (representation only, NOT decisions):** APPLIES_TO, EXEMPTS,
  GOVERNS, REQUIRES, PROHIBITS, OVERRIDES, SUBORDINATE_TO
- **Informational:** REFERENCES, DESCRIBES, REPORTS, ATTRIBUTES_TO, RECOMMENDS, ALLEGES,
  CLAIMS
- **Temporal & causal:** PRECEDES, FOLLOWS, TRIGGERS, CAUSES, RESULTS_IN, VALID_FROM,
  VALID_UNTIL

## Inverses (applied ONLY where explicitly allowed; never auto-inferred)

`OWNS ↔ OWNED_BY` · `SUPERSEDES ↔ SUPERSEDED_BY` · `PART_OF ↔ CONTAINS` ·
`DEPENDS_ON ↔ DEPENDENCY_OF`. An inverse is used only on explicit request; the extractor
never invents one.

## Ontology-equivalence groups (lenient scoring)

A predicted predicate in the same group as gold counts as ontology-equivalent (not
exact): `REPLACES~SUPERSEDES`, `PROHIBITED_FROM~PROHIBITS`, `OBLIGATED_TO~REQUIRES`,
`PERMITTED_TO~AUTHORIZED_BY`, `OPERATES~MANAGES~ADMINISTERS`, `ALLEGES~CLAIMS`.

## Predicate lexicon

Surface phrases map to `(RelationshipType, Form)`; passive by-agent forms
("owned by", "operated by", "managed by", "superseded by") are matched before active
forms so direction can be resolved. The lexicon is deliberately bounded — out-of-lexicon
verbs yield no assertion rather than a guess.
