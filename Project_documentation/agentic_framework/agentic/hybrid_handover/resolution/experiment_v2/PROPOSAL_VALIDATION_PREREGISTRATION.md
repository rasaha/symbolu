# PROPOSAL_VALIDATION_PREREGISTRATION — Proposal Validation Experiment v0.1

**Written and frozen BEFORE any hidden evaluation of v0.2.** Hashed at lock time
(HIDDEN_EVALUATION_LOCK_V2.md). Not modified after hidden evaluation begins.

Resolver under test: **HybridRelationshipResolver Experimental v0.2**.

## What is NOT touched (verified byte-identical at lock)
SEEB v1.0.0; the retrieval benchmark; the Relationship Measurement Specification
v1.0; the Relationship Corpus Curation Specification v1.0; the Hidden Relationship
Corpus Pilot v0.2 and its annotations; the existing deterministic resolvers; the
frozen GraphTraversal governance; the frozen packet construction; the frozen parser;
the frozen metrics; the frozen evaluation harness; the hidden evaluation protocol;
**and the entire v0.1 experiment (`experiment/`), which is left exactly as committed.**
Proposal generation is the v0.1 generator, reused unchanged. Only the Proposal
Validation Layer is new.

## Scientific question
Can unsupported relationship proposals be rejected before graph construction, by a
deterministic validator, **without materially reducing genuine discovery**?

## Architecture (only the middle box is new)
`v0.1 proposal → Proposal Validation → validated graph → frozen governance → frozen packet`

With validation disabled (V0) the resolver reproduces Hybrid v0.1 bit-for-bit.

## Proposal Validator — frozen rules
Each proposed edge is validated INDEPENDENTLY. Gates (in evaluation order):

1. **duplicate suppression** — a repeated triple is dropped (`duplicate_edge`).
2. **evidence consistency** —
   - provenance needle present, else `missing_source_evidence`;
   - for destination-required types (supersedes, amends, overrides, governs_over,
     exception_to, conflicts_with, effective_after) the destination must be a real
     node (structural ≥ 0.5), else `missing_destination_evidence`;
   - a named reference/alias whose target does not resolve at all → `unsupported_wording`.
3. **authority / temporal** — for order-sensitive types (supersedes, amends,
   effective_after) the source instrument must be strictly later than the
   destination by parsed `order`; violation → `authority_mismatch`
   (`temporal_mismatch` for effective_after).
4. **type-specific constraints** —
   - `conflicts_with` requires a genuinely differing operative attribute
     (allows / negation / notice_days / penalty_months) or a shared definition
     term, else `type_conflict`;
   - `same_as` requires a shared `version_base` or a matching normalized section
     number (7.01 ≡ 7.1) when the destination is a real node, else
     `relationship_ambiguity`.
5. **relationship exclusivity / graph contradiction** — `supersedes` and `amends`
   are mutually exclusive on one (src,dst) pair; a same-type order-sensitive cycle
   (A→B and B→A) is contradictory → `graph_contradiction`.
6. **minimum confidence** — lexical component below the floor → `low_evidence`.

## Confidence vector (frozen; never collapsed into one score)
Per edge: `{lexical, structural, authority, reference}`.
- **lexical** = the v0.1 cue-strength confidence for the triggering needle.
- **structural** = 1.0 if the destination is a real node; 0.5 if it is a named but
  unresolved reference/alias target; 0.0 otherwise.
- **authority** = 1.0 if the edge is order/temporal-consistent for its type (or the
  type is order-agnostic); 0.0 if it violates ordering.
- **reference** = for references/same_as, 1.0 if the destination resolves, 0.5 if
  named-but-dangling, 0.0 otherwise; 1.0 (n/a) for other types.
Decisions use component-wise gates and floors, so every rejection cites a specific
component, never an opaque threshold.

## Frozen thresholds (selected on the VISIBLE corpus only)
`FLOOR_LEXICAL = 0.6`, `FLOOR_STRUCTURAL = 0.5`. Calibration criterion: the full
validator (V4) must reject **zero** correct edges on the visible corpus (verified:
visible discovery precision and recall are unchanged at 1.0/1.0 under V4). No hidden
data was used to set any threshold or rule.

## Ablations (exactly these, no others)
- **V0** — no validation (Hybrid v0.1).
- **V1** — duplicate suppression only.
- **V2** — evidence consistency only (+ min confidence).
- **V3** — authority + temporal validation (+ type-specific).
- **V4** — full Proposal Validator.

## Primary endpoint
**Recovery of discovery precision** on the hidden pilot, subject to **no more than
0.03 loss of discovery recall relative to Hybrid v0.1 (= V0)**.

## Secondary endpoints
Discovery precision, discovery recall, discovery F1, classification, governance
Mode G, packet Mode P, selective accuracy, false abstention, missed abstention,
coverage, unsafe answers.

## Success / failure criteria
- **PROMISING VALIDATION LAYER** — discovery precision improves; recall loss ≤ 0.03;
  selective accuracy improves; unsafe answers do not increase; governance unchanged;
  packet unchanged.
- **NO CLEAR SIGNAL** — precision improves only by sacrificing recall (loss > 0.03).
- **FALSIFIED** — validation removes most genuine discoveries.

## Required outputs (per proposed edge)
proposal source; proposal destination; relationship type; proposal evidence;
validation evidence; validation decision; rejection reason; confidence vector.

## Failure taxonomy (frequencies reported)
unsupported_wording; authority_mismatch; temporal_mismatch;
missing_destination_evidence; missing_source_evidence; graph_contradiction;
duplicate_edge; relationship_ambiguity; low_evidence; type_conflict.

## Run protocol
Fully deterministic → two byte-identical repetitions required. Fixed ablation order
V0→V4, recorded in the manifest. Statistics reuse the v0.1 `stats.py` (exact
McNemar, seeded paired bootstrap, Holm) unchanged.

## Prohibited post-hoc changes
No rule, floor, or threshold change from hidden results; no rule keyed to a specific
hidden case; no case removal; no ablation added after hidden results. Any post-lock
fix (crash/wiring only) bumps the lock version and reruns all ablations.

## Final questions (answered in VALIDATION_RESULTS.md)
How many incorrect proposals were removed? How many correct proposals mistakenly
rejected? Was the precision gain worth the recall loss? Did selective accuracy
recover? Is Proposal Validation the preferred architecture? Should it become part of
the frozen resolver architecture? (The frozen architecture is NOT changed regardless
of outcome.)
