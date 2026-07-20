# Claim Schema (v0.1)

Defines the `RelationshipClaim` (a proposed relationship treated as a factual
hypothesis) and the executable/public projection. Source: `model.py`.

> Scope: self-contained synthetic experiment; no external pipeline. See
> `CLAIM_VALIDATION_PREREGISTRATION.md` §Scope boundary.

---

## 1. RelationshipClaim

| Field | Type | Meaning |
|---|---|---|
| `relationship_id` | str | stable id |
| `relationship_type` | str | one of the legal types (§3) |
| `source_node` | str | subject entity |
| `target_node` | str | object entity |
| `cited_document_ids` | tuple[str] | documents the proposer cites |
| `cited_span_ids` | tuple[str] | evidence spans the proposer cites |
| `claimed_scope` | str \| None | scope the claim asserts (None = unscoped) |
| `claimed_temporal` | (int\|None, int\|None) \| None | claimed applicability window |
| `claimed_authority` | str \| None | authority domain claimed |

Each proposed relationship becomes an explicit claim, e.g. `PolicyA SUPERSEDES
PolicyB`, and must be grounded in cited document evidence before being retained.

## 2. Documents & spans

`Document(doc_id, spans)`; `Span(span_id, text, assertions)`. `assertions` is a
small structured description the judges reason over (never gold). Recognized keys:
`source`, `target`, `relation`, `negates` (bool), `contradicts` (a relation type),
`exclusive_direction` (bool), `scope`, `temporal={"from","to"}`, `authority`.

## 3. Legal relationship types (schema/legality gate)

`SUPERSEDES`, `EXEMPTS`, `REQUIRES`, `RESTRICTS`, `REFERENCES`, `AMENDS`,
`PRECEDES`, `DELEGATES_TO`. Any other type fails the deterministic legality check
and is removed (`DETERMINISTIC_VALIDATION.md`).

## 4. Public projection (leakage control)

`corpus.public_claims()` / `loader.public_claims()` expose only the fields in §1.
Gold status, difficulty, family, and authoring rationale are **never** in the
public projection — asserted by `test_public_projection_has_no_leakage`.
