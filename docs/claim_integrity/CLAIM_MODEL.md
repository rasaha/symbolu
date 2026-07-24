# Formal Claim Model (Phase 2)

*The canonical claim unit and the four preservation properties. Implemented in
`claim_integrity/schema.py`. The unit is deliberately rich: each field is a semantic dimension that a
decomposition step can silently corrupt (Phase 4), and the study measures preservation per dimension —
never as one collapsed score.*

## The canonical claim unit (`ClaimUnit`)

| Field | Meaning |
|---|---|
| `claim_id` | stable id within the source output |
| `source_output_id` | the model output this claim was extracted from |
| `source_span` | character span in the original text (provenance to the exact words) |
| `normalized_text` | the claim in normalized form (semantic normalization only, no rewriting) |
| `claim_type` | one of the 30 taxonomy types (Phase 3) |
| `subject` / `predicate` / `object` | the proposition's core triple |
| `polarity` | affirmative / negated / partially-negated |
| `quantifier` | none / universal / existential / proportional (+ scope) |
| `modality` | none / possibility / necessity / obligation / permission / prohibition |
| `uncertainty` | none / hedged / probabilistic / attributed-uncertainty |
| `confidence_expression` | the surface phrase carrying uncertainty ("may", "likely", "35%") |
| `temporal_scope` | timeframe the claim applies to (as-of, window, tense) |
| `spatial_scope` | geography the claim applies to |
| `jurisdiction` | legal/regulatory jurisdiction, if any |
| `population` | entity/cohort/individual the claim applies to |
| `conditions` | "only if" / "unless" clauses gating the claim |
| `exceptions` | carve-outs that narrow the claim |
| `causal_direction` | none / causal(A→B) / correlational / reverse |
| `comparative_reference` | the baseline a comparative claim is measured against |
| `numerical_values` | values asserted |
| `units` | units attached to values |
| `ranges` | ranges / bounds / intervals |
| `attribution` | direct (author) vs attributed (source X says) |
| `evidence_status_language` | "no evidence", "not approved", "not established" |
| `citation_references` | citations/links and which clause they attach to |
| `reference_links` | pronoun/entity antecedents resolved within context |
| `depends_on` | other claim_ids this claim requires to be evaluable |
| `conjunction_structure` | how ANDed sub-claims relate |
| `disjunction_structure` | how ORed alternatives relate |
| `rhetorical_status` | assertive vs non-assertive (question, aside) |
| `normative_status` | descriptive vs normative |
| `decomposition_confidence` | the component's confidence in this unit |
| `unresolved_ambiguity` | recorded ambiguity that was NOT forced to a decision |

A claim unit records **provenance to the original words** (`source_span`) so that any downstream check
— or any audit — can compare the governed proposition against the text that produced it.

## The four preservation properties (kept separate)

Decomposition quality is not one number. Four distinct properties can fail independently, and the study
measures each:

1. **Atomicity** — does the unit contain exactly one *independently evaluable* proposition? Too coarse
   (multiple claims in one unit) and evidence evaluation conflates them; too fine (one claim shattered
   across units) and qualifiers/dependencies detach.
2. **Completeness** — were all materially relevant assertions extracted? A dropped claim is never
   evaluated; an invented claim is evaluated but was never made.
3. **Semantic preservation** — does the extracted claim retain the original *meaning*? This is the
   headline property: polarity, modality, uncertainty, causal direction, evidentiary status, numerics.
4. **Scope preservation** — do qualifiers, quantifiers, conditions, exceptions, temporal/spatial/
   jurisdiction/population limits remain attached to the *correct* claim? Scope can survive as text yet
   attach to the wrong unit (qualifier reassignment) — a distinct failure from scope deletion.
5. **Reference preservation** — do entities, pronouns, citations, and cross-sentence dependencies
   remain correct? "Source X claims Y" must not become "Y", and a citation on clause 2 must not migrate
   to clause 1.

These are **not** collapsed into a single score in this study. A method can preserve semantics while
destroying atomicity, or preserve atomicity while reassigning scope; conflating them would hide exactly
the trade-offs the study exists to expose. The final report (Phase 26) stratifies by all five.

## Why the richness is load-bearing, not decoration

Each field maps to at least one semantic-failure type (Phase 4) and at least one downstream governance
consequence (Phase 18). A minimal `{subject, predicate, object}` triple — the OpenIE-style baseline —
*cannot represent* polarity, modality, uncertainty, conditions, exceptions, attribution, or evidentiary
status, so a pipeline built on it discards those dimensions structurally, before any error is even
possible. Part of the study is measuring exactly how much that structural discarding costs downstream
(H0-3). The rich unit is the instrument that makes the cost visible; whether the *component* that
populates it is justified is the open question, not an assumption.
