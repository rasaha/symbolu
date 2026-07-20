# EDGE_PRIORITIZATION_PREREGISTRATION — Edge Prioritization Experiment v0.1

**Written and frozen BEFORE any hidden evaluation of v0.3.** Hashed at lock time
(HIDDEN_EVALUATION_LOCK_V3.md). Not modified after hidden evaluation begins.

Resolver under test: **HybridRelationshipResolver Experimental v0.3**.

## Frozen — nothing below may change
SEEB; Measurement Specification v1.0; Corpus Curation Specification v1.0; Hidden
Corpus Pilot v0.2 and annotations; **HybridRelationshipResolver v0.2**; the Proposal
Validation Layer; the frozen governance; the frozen packet builder; the hidden
evaluation protocol; the metrics; the parser. Proposal generation is bit-identical to
v0.2, and proposal validation is bit-identical to v0.2 (both reused by composition).

## Scientific question
Given multiple VALID relationship proposals, can a deterministic prioritization layer
identify which relationships should DOMINATE governance — improving downstream
decisions without changing proposal generation or validation?

## Architecture (only the prioritization box is new)
`proposal → validation → Edge Prioritization → frozen governance → frozen packet`

## Mechanism (and why the boundary holds structurally)
The frozen packet selects its `primary` as the first governing node, in graph-node
order, that is a source of supersedes / overrides / governs_over. When two or more
such **governance sources** compete, node order decides which one drives the answer.
The prioritization layer reorders the nodes of the graph handed to the frozen
governance in the **full `resolve()` pipeline** so the dominant source is primary. It
never adds, removes, or retypes an edge.

Consequences (structural, not merely intended):
- `resolve_relationships` is delegated to v0.2 verbatim → **discovery precision /
  recall / classification are bit-identical to v0.2**.
- `resolve_governance` (Mode G, gold graph) and `_derive` (Mode P, gold governance)
  delegate straight to the frozen code with **no prioritization** → **Mode G and Mode
  P are unchanged**.
- Prioritization runs only in the full pipeline, where fewer than two competing
  governance sources means the order — and the outcome — is unchanged. With P0 the
  resolver reproduces v0.2 exactly.

## Priority vector (frozen; never collapsed into one scalar)
Per governance-source node: `{authority, temporal, specificity, reference,
structural, confidence, support}`, each in [0,1]. Competing sources are ranked
**lexicographically** over the enabled components in the fixed order
`authority > temporal > specificity > reference > structural > confidence > support`;
the winner is explainable by the first component on which it beats the competitor.
See PRIORITY_VECTOR_SPEC.md and EDGE_PRIORITY_RULEBOOK.md.

## Ablations (exactly these)
- **P0** — no prioritization (v0.2).
- **P1** — authority only.
- **P2** — authority + temporal.
- **P3** — authority + temporal + specificity.
- **P4** — full prioritization (all seven components).

## Primary endpoint
**Selective accuracy** on the hidden pilot, subject to **no degradation** of:
discovery precision, discovery recall, classification, governance Mode G, packet Mode
P, unsafe answers. (These are structurally guaranteed unchanged by the mechanism;
the run confirms it empirically.)

## Success criteria
- **PROMISING PRIORITIZATION** — selective accuracy improves; discovery unchanged;
  precision unchanged; recall unchanged; unsafe unchanged.

## Failure criteria
- **NO CLEAR SIGNAL** — prioritization merely reshuffles edges without improving
  downstream decisions (selective accuracy unchanged).
- **FALSIFIED** — prioritization harms discovery or governance.

## Required outputs (per competing edge)
priority vector; retained / rejected; reason; competing edge; winner.

## Calibration & thresholds
No thresholds beyond the fixed lexicographic component order. Calibrated on the
visible corpus: P0 reproduces v0.2, and P1–P4 leave every visible metric unchanged
(visible contains no multi-governance-source competition), so no correct visible
decision is altered.

## Run protocol
Fully deterministic → two byte-identical repetitions required. Fixed ablation order
P0→P4, recorded in the manifest. Statistics reuse the v0.1 `stats.py` unchanged.

## Prohibited post-hoc changes
No component, order, or rule change from hidden results; no rule keyed to a hidden
case; no case removal; no ablation added post hoc. Any post-lock fix (crash/wiring
only) bumps the lock version and reruns all ablations.

## Final questions (answered in FINAL_VERDICT.md)
How many competing edges were reprioritized? How many governance decisions changed?
Did selective accuracy improve? Was any discovery performance lost? Is prioritization
now the dominant remaining bottleneck? Should Edge Prioritization become part of the
frozen resolver architecture? (It is NOT promoted regardless of outcome.)
