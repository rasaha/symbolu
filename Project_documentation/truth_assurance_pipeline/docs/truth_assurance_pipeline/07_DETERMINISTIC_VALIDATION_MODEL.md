# TAP — Deterministic Validation Model v0.1

Specifies **where deterministic validation belongs** and why it is authoritative.
Architecture-only.

> Boundary: `12_RESEARCH_BOUNDARIES.md`.

---

## 1. Principle

Anything a rule, schema, computation, or lookup can decide **must** be decided
deterministically, and that decision is **authoritative** — judges (LLM or rule)
never override it. Deterministic validation is the backbone; judges handle only the
residual semantic uncertainty.

## 2. Deterministic check families and where they belong

| Check family | Belongs to | Example |
|---|---|---|
| schema | every layer's input boundary | claim/relationship well-formedness |
| IDs | Retrieval, Layer 1, Layer 4 | referenced doc/span id exists |
| dates / temporal | Layer 2, Layer 4 | temporal validity, temporal leakage |
| citations | Layer 4, Layer 5 | cited span exists and is quoted faithfully |
| business rules | Layer 2 | authority/scope/supersession rules |
| policy constraints | Safety/Policy (out of TAP scope) | hard prohibitions |
| math | Layer 4, Layer 5 | numeric consistency of a claim |
| code execution | Layer 4 | executable check of a computable claim |
| database lookups | Retrieval, Layer 4 | ground a claim against a system of record |

## 3. Ordering rule

Within any layer: **deterministic checks run first.** A hard deterministic failure
resolves the item (remove / abstain) and it never reaches the judges. Only items that
pass deterministic checks — and still carry semantic uncertainty — proceed to
advocate/challenger/adjudicator.

## 4. Authority rule

- `deterministic_certainty = 1` for a settled check ⇒ that outcome stands.
- A judge may *raise* scrutiny (add a concern) but may not *lower* a deterministic
  denial or *manufacture* support a deterministic check refuted.
- Deterministic and judge signals are separate `ConfidenceVector` dimensions
  (`05_…`); they are never averaged into one number that could let a judge dilute a
  deterministic result.

## 5. Reference instantiation (existing, synthetic, Layer 4)

The `relationship_claim_validation/` prototype runs deterministic pre-judge checks
(legality, schema, duplicate, direction, document existence, citation validity)
before any judge; in its measured run, **6 of 48** claims were resolved
deterministically before adjudication. See its
`Project_documentation/governance/docs/relationship_claim_validation/DETERMINISTIC_VALIDATION.md`. This validates the
*ordering and authority* pattern on synthetic data only.

## 6. Boundary

Deterministic validation reduces — it does not eliminate — the need for judges: many
truth questions (paraphrase, implication, over-generalization) are not decidable by
rule. TAP's stance is to *maximize* the deterministic surface and *scope* judges to
the irreducible remainder.
