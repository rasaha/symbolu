# GOVERNANCE_SEMANTICS_PREREGISTRATION — Governance Semantics Experiment v0.1

**Written and frozen BEFORE any hidden evaluation of v0.4.** Hashed at lock time
(GOVERNANCE_SEMANTICS_HIDDEN_LOCK.md). Not modified after the lock.

Resolver under test: **HybridRelationshipResolver Experimental v0.4**.

## Frozen — nothing below may change
SEEB v1.0.0; retrieval benchmarks/extractors; Relationship Measurement Specification
v1.0; Relationship Corpus Curation Specification v1.0; Hidden Relationship Corpus Pilot
v0.2 + annotations; the parser; relationship proposal generation; the Proposal
Validation Layer; GraphTraversalResolver; HybridRelationshipResolver v0.1 / v0.2; the
Edge Prioritization Experiment v0.1; the existing governance implementation; the
existing packet implementation; frozen metrics; the hidden-evaluation protocol; and all
prior experiment outputs, locks, reports, and tests. All prior versions remain
byte-for-byte unchanged. Frozen governance is not silently promoted or replaced; the new
behavior lives only in this additive package.

## Research question
Given a validated relationship graph, can a deterministic Governance Semantics Layer
distinguish (1) replacement/supersession, (2) amendment, (3) exception, (4) parallel
applicability, (5) cumulative requirements, (6) conflicting-but-simultaneously-relevant
authorities — and then identify the evidence carrying the operative term required for
the final decision?

## Hypotheses
- **Primary hypothesis.** Frozen governance loses information because it globally
  discards edge destinations and relies on node ordering to pick the primary source. An
  explicit semantic applicability analysis may improve full-pipeline selective accuracy
  by deciding which clauses are applicable/displaced/cumulative, which clause carries the
  operative term, and when to abstain.
- **Null.** Explicit governance semantics will not improve selective accuracy over v0.2
  and may merely swap one brittle heuristic for another.
- **Alternative.** A deterministic Governance Semantics Layer improves selective accuracy
  while preserving discovery, classification, validation, packet Mode P, coverage within
  margin, and unsafe-answer count.

## Architecture
`proposal (v0.1) → validation (v0.2) → validated graph → Governance Semantics Layer →
adapter → frozen packet`. See GOVERNANCE_SEMANTICS_ARCHITECTURE.md.

## Resolver inputs / outputs
Inputs identical to every resolver: `(question, evidence)`. Never receives gold answer,
gold governing nodes, capability/difficulty labels, hidden annotations, author
rationale, or case-identifier semantics. Output: `ResolutionResult` plus an explicit
machine-readable GovernanceResult (statuses, role sets, decision trace, evidence
vectors).

## Owner boundary
The layer owns ONLY: clause applicability, displacement, cumulative applicability,
operative-source selection, governance ambiguity, governance-stage abstention. It does
NOT own discovery, classification, parsing, proposal validation, packet rendering,
non-governance answer extraction, or SafetyGate.

## Design decision that preserves the protected stages (frozen)
The layer reports the **frozen governing set** (frozen governance is reused to compute
it), so governance Mode G is bit-identical to the G0 control by construction. The
behavioral change is confined to (a) **operative-source selection** — which governing
node the frozen packet reads the answer from — and (b) **governance-stage abstention**.
These affect only the full-pipeline answer (selective accuracy / coverage), never
discovery, classification, validation, or Mode P.

## Semantic categories & rule precedence (frozen)
See GOVERNANCE_STATUS_MODEL.md and GOVERNANCE_RULEBOOK.md. Precedence for the operative
decision: frozen abstention inherited → conflicting operative terms (abstain) →
prohibition present → permission present → other operative-term carrier (latest) →
no operative term (abstain if enabled, else frozen primary).

## Operative-source rules (frozen)
Authority source, operative source, and supporting source are distinguished; the
operative source is the governing node carrying the decisive termination-for-convenience
term (prohibition/permission), NOT necessarily the highest-authority node. See
OPERATIVE_SOURCE_SPEC.md.

## Abstention rules (frozen)
Governance-stage abstention when: two conflicting operative outcomes are equally
supported; the authority node is known but the operative term cannot be located; or
frozen abstention is inherited. See GOVERNANCE_ABSTENTION_SPEC.md.

## Adapter behavior (frozen)
Orders the operative node first and hides competing governance-source edges from the
packet-input graph so the frozen packet's own `primary` rule lands on the operative
node. It does not infer relationships, edit evidence, add answer text, add policy rules,
or select the final answer. Documented information loss: the frozen contract cannot
natively express "operative ≠ authority" or multiple cumulative operatives.

## Control & ablations (exactly these)
- **G0** — frozen governance control (v0.2; no experimental semantics).
- **G1** — supersession + amendment scope only.
- **G2** — G1 + parallel applicability.
- **G3** — G2 + operative-source selection.
- **G4** — full Governance Semantics Layer (+ exception handling, cumulative,
  governance-stage abstention).

## Primary endpoint
Full-pipeline **selective accuracy** on the hidden pilot, G4 vs G0, paired case-level.
Practical-success threshold: absolute improvement **≥ 0.03**.

## Non-inferiority constraints (vs G0) — frozen
G4 is not successful if any occurs: discovery precision/recall/F1 changes; classification
changes; proposal-validation rejection behavior changes; governance Mode G decreases
> 0.03; packet Mode P changes; coverage decreases > 0.05; false-abstention rate increases
> 0.05; missed-abstention rate increases > 0.05; unsafe-answer count increases;
determinism fails. Discovery and validation must be exactly identical, not merely
non-inferior.

## Secondary endpoints
Full-pipeline accuracy; selective accuracy; coverage; abstention precision/recall;
false/missed-abstention rate; unsafe count; governing-set accuracy; packet Mode P;
discovery/classification identity checks. Governance-status accuracies (operative,
displaced, cumulative, parallel, ambiguity) require gold status labels that the frozen
annotations do not provide; they are reported as NOT EVALUABLE rather than fabricated,
in an additive experimental namespace. The frozen specification is not altered.

## Diagnostic categories (post-lock, diagnostic only)
supersession; amendment; override; governs-over; exception; parallel authority;
cumulative obligation; conflicting authority; operative-term separation; single/multiple
governing sources; ambiguity; required abstention; difficulty; reasoning depth;
seed-vs-pilot. No implementation change from subgroup results.

## Statistical methods
Paired case-level. Binary full-pipeline correctness → exact McNemar. Per-case selective
→ paired bootstrap 95% CI (fixed seed 20240601, reused from v0.1 `stats.py`). Report
fixes/breaks/unchanged, absolute diff, CI, p, effect size, n. With only 60 synthetic
cases, emphasize effect size and case-level mechanism over significance.

## Run protocol / determinism
Deterministic. Two complete runs; byte-identical governance artifacts, final outputs,
and aggregate reports required. No run discarded.

## Allowed pre-lock corrections
Only interface validation, crash correction, deterministic rule debugging, verifying
protected-stage identity, checking no correct visible decision is degraded, and selecting
preregistered thresholds. No rule derived from hidden-case wording. All visible
corrections documented (see below).

### Visible-corpus corrections made before lock
The first layer design changed the governing set (parallel applicability) and abstained,
which dropped visible Mode G (1.0→0.60) and visible selective (0.82→0.60). Correction:
the governing SET was pinned to the frozen set (Mode G preserved) and the improvement
confined to operative-source selection + abstention. After the fix, G0–G4 leave every
visible metric unchanged. No hidden data was used.

## Prohibited post-lock changes
No rule, threshold, adapter, code, or case change; no selective reruns; no
hidden-specific corrections. An objective execution defect requires invalidating affected
runs, documenting the defect, a new lock version, and rerunning every condition.

## Success classification (choose exactly one)
- **PROMISING GOVERNANCE SEMANTICS** — G4 improves selective ≥ 0.03; more fixes than
  breaks; all non-inferiority passes; unsafe not increased; improvement not confined to
  one case; ≥1 preregistered mechanism causally supported by the ablations.
- **NO CLEAR SIGNAL** — decisions change but net selective does not improve materially;
  fixes/breaks largely cancel; gains too narrow; CI inconclusive; or gains driven mainly
  by abstention/coverage reduction.
- **FALSIFIED IN CURRENT FORM** — G4 materially reduces selective; increases unsafe;
  violates protected-stage identity; harms governance across families; or its semantics
  do not outperform frozen governance.

## Final questions & interpretation boundary
Answered in FINAL_VERDICT.md. Questions 9 (promote into frozen architecture) and 10
(broad generalization) must remain **NO**. Even a positive result supports only: a
deterministic governance-semantics layer improved performance on the 60-case Hidden
Relationship Corpus Pilot v0.2 — not enterprise readiness, generalization, production
safety, real-document correctness, certification, or RRB v1.0.
