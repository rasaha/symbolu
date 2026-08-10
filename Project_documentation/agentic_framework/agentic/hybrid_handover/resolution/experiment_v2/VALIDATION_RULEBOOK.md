# VALIDATION_RULEBOOK — Proposal Validation Experiment v0.1

The complete, frozen set of deterministic rules the Proposal Validator applies to
each proposed edge, in evaluation order. Every rule is a pure function of the parsed
nodes and the v0.1 proposal output (edge, lexical confidence, provenance needle). No
learned parameters; no randomness; no hidden data used to author any rule.

Notation: an edge is `(src) --type--> (dst)`; `order` is the parsed document order
(0 = base clause; amendments increase). "Real node" = the endpoint key is a parsed
node; "dangling" = it is not.

## Gate order and rejection categories

| # | gate | condition to REJECT | category |
|---|------|---------------------|----------|
| 1 | duplicate suppression | triple already accepted | `duplicate_edge` |
| 2a | source evidence | provenance needle missing/empty | `missing_source_evidence` |
| 2b | destination evidence | type ∈ dest-required and structural < 0.5 | `missing_destination_evidence` |
| 2c | reference resolution | reference/alias target unresolved (reference < 0.5) | `unsupported_wording` |
| 3 | authority / temporal | type ∈ order-sensitive and not(src.order > dst.order) | `authority_mismatch` / `temporal_mismatch` |
| 4a | conflict validity | `conflicts_with` with no differing operative attr and no shared definition term | `type_conflict` |
| 4b | alias validity | `same_as` (real dst) with no shared version_base and no matching normalized section | `relationship_ambiguity` |
| 5 | exclusivity / contradiction | `supersedes`⊕`amends` on a pair; or same-type order-sensitive cycle | `graph_contradiction` |
| 6 | minimum confidence | lexical < FLOOR_LEXICAL (0.6) | `low_evidence` |

An edge that passes every enabled gate is **accepted** into the validated graph.
Ablations enable subsets of the gates (see VALIDATION_ABLATIONS.md).

## Sets (frozen)

- **order-sensitive types** (source must be strictly later): `supersedes`, `amends`,
  `effective_after`.
- **destination-required types** (dangling destination invalid): `supersedes`,
  `amends`, `overrides`, `governs_over`, `exception_to`, `conflicts_with`,
  `effective_after`. (`references` and `same_as` may name a not-yet-present target.)
- **mutually-exclusive family** on one (src,dst) pair: `supersedes` ⊕ `amends`.

## Rule rationale (general legal reasoning, not corpus-specific)

- **Authority/temporal.** A superseding or amending instrument is, by construction,
  enacted *after* what it changes; an `effective_after` edge asserts a later
  effective date. A proposal that runs the other way is structurally impossible and
  is almost always a lexical false-positive (a cue word matched in the wrong node).
- **Destination evidence.** A governance-bearing relationship (supersession,
  override, governance, exception) must point at an actual clause; a dangling target
  is an unresolved reference, not a governance edge.
- **Conflict validity.** Two clauses "conflict" only if they actually prescribe
  different operative outcomes; identical clauses cited together are not a conflict.
- **Alias validity.** `same_as` asserts identity; it needs a shared version lineage
  or a section-number identity (modulo formatting, e.g. 7.01 ≡ 7.1), otherwise it is
  an ambiguous guess.
- **Exclusivity.** A single instrument either replaces (`supersedes`) or modifies
  (`amends`) a given clause, not both; and A cannot supersede B while B supersedes A.

## Why these preserve genuine discovery
On the visible corpus every v0.1 edge is correct, and V4 rejects none of them
(discovery precision and recall stay 1.0/1.0). The gates only fire on structurally
unsupported edges — the intended behaviour is to leave real relationships untouched
and remove only proposals that violate a hard structural/temporal/type constraint.
