# Capability Requirements

`CapabilityRequirement` records a role-relevant capability a node requires, with
deterministic provenance. Fields: `capability_id`, `requirement_level`
(REQUIRED/OPTIONAL), `source`, `source_ref`, `resolution`, `authority_context`,
`provenance`, `fingerprint`.

## Sources (never natural-language inference)

- `EXPLICIT_POLICY` — declared by the source policy (when a source construct exists).
- `NODE_KIND_MAPPING` — a registered compiler mapping from node kind to a functional
  capability. The one shipped mapping: `EVIDENCE_REQUIREMENT → evidence_extraction`.
- `CAPABILITY_OWNER_MAPPING` — governance/authority nodes carry their owning
  capability id (e.g. `DECISION_AUTHORITY`, `ACTION_GATE`) as a requirement.
- `CONTRACT_DERIVATION` — reserved for capabilities derived from typed contracts.
- `UNRESOLVED` — nothing could be resolved (never a fabricated capability).

## Rules

- Every emitted capability has provenance (`compiler_rule` + `derivation_class`).
- Duplicate requirements canonicalize; the release validator rejects duplicates.
- No substring/keyword/LLM guessing. Structural nodes with no functional capability
  emit an empty set, not a guess.
