# COMPETING_OPERATIVE_PREREGISTRATION — Competing Operative Resolution Experiment v0.1

**Written and frozen BEFORE any hidden evaluation of v0.5.** Hashed at lock time
(COMPETING_OPERATIVE_HIDDEN_LOCK.md). Not modified after the lock.

Resolver under test: **HybridRelationshipResolver Experimental v0.5**.

## Frozen — nothing below may change
SEEB v1.0.0; retrieval benchmarks/extractors; Relationship Measurement Specification
v1.0; Corpus Curation Specification v1.0; Hidden Relationship Corpus Pilot v0.2 +
annotations; the parser; relationship proposal generation; the Proposal Validation
Layer; GraphTraversalResolver; HybridRelationshipResolver v0.1 / v0.2; the Edge
Prioritization Experiment v0.1; the Governance Semantics Experiment v0.1; frozen
governance; the frozen packet builder and Mode P; frozen metrics; and all prior
evaluation outputs, preregistrations, locks, reports, and tests. All five prior
architectural stages and all four previous experiment packages remain byte-for-byte
unchanged. Implemented as a new additive package.

## Baseline (principal control)
**C0 = Governance Semantics G3** — successful operative-source selection, WITHOUT the
failed coarse G4 abstention. The control reproduces G3 bit-for-bit. Historical G4 is a
diagnostic comparator only, never the principal control.

## Research question
Can a deterministic Competing Operative Resolution Layer distinguish (1) genuine
unresolved operative conflict, (2) scoped override, (3) exception, (4) parallel
applicability, (5) cumulative requirements, and (6) non-conflicting permission/
prohibition co-occurrence — and abstain only when the final operative outcome is
genuinely unresolved?

## Hypotheses
- **Primary.** The G4 abstention failure was caused by an insufficient representation of
  competing operatives. A typed operative-set representation with explicit scope,
  polarity, applicability, and conflict status should retain the five G3 fixes, preserve
  coverage, reduce false abstention, identify genuinely unresolved conflicts, and improve
  or preserve selective accuracy without unsafe regressions.
- **Null.** A richer representation will not improve full-pipeline decisions beyond G3 and
  may add brittle conflict rules.
- **Alternative.** The full layer outperforms G3 on selective accuracy or correct
  abstention while satisfying all non-inferiority and safety constraints.

## Architecture
`proposal (v0.1) → validation (v0.2) → frozen governing set → G3 operative source →
Competing Operative Resolution Layer → governance decision / precise abstention → frozen
packet via the v0.4 adapter`. Only the Competing Operative Resolution Layer varies.
See COMPETING_OPERATIVE_ARCHITECTURE.md.

## Core principle (frozen)
A conflict exists only when two candidates are simultaneously applicable to the same
subject/action/object/condition/scope/time/authority-domain AND prescribe incompatible
outcomes AND no graph relationship resolves it. Co-occurrence of permission and
prohibition language is NOT sufficient. A value that cannot be derived is UNKNOWN and
implies neither overlap nor non-overlap; genuine conflict requires overlap to be
POSITIVELY established.

## Schemas, categories, predicates, rules, abstention
See OPERATIVE_CANDIDATE_SCHEMA.md, OPERATIVE_SCOPE_SPEC.md, CONFLICT_PREDICATE_SPEC.md,
CONFLICT_CLASSIFICATION_RULEBOOK.md, PRECISE_ABSTENTION_SPEC.md,
PACKET_CARDINALITY_BOUNDARY.md. Rule precedence for the abstention decision: genuine
unresolved conflict → (else) operative term not located → (else) answer with the G3
operative. Abstention reasons are exactly: GENUINE_UNRESOLVED_CONFLICT,
INSUFFICIENT_SCOPE_EVIDENCE, OPERATIVE_TERM_NOT_LOCATED,
MULTIPLE_INCOMPATIBLE_OPERATIVE_TERMS, FROZEN_PACKET_CARDINALITY_LIMIT,
MISSING_DECISIVE_PROVENANCE. No catch-all low-confidence abstention.

## Ablations (exactly these)
- **C0** — G3 control (no competing-operative analysis).
- **C1** — operative extraction only (typed candidates; decision unchanged).
- **C2** — scope + applicability (subject/action/object/temporal/authority/condition).
- **C3** — conflict classification (predicates + categories; abstention NOT yet active).
- **C4** — full resolution + restricted abstention.

## Primary endpoint
Full-pipeline **selective accuracy**, C4 vs C0, paired. Practical success: absolute
improvement ≥ 0.03; OR, if selective is unchanged, correct-abstention recall improves
≥ 0.10 with no false-abstention increase and no safety regression. A selective gain
caused primarily by coverage reduction is NOT success; the interpretation must account
for coverage.

## Critical retention requirement
C4 must retain the five established G3 fixes (`HX59d7a3eb1c`, `HP059f01c294`,
`HP7d8d12efac`, `HPb3463204c9`, `HPebe6e8abf0`). If any is lost, the mechanism cannot
receive a promising verdict.

## Non-inferiority constraints (vs C0)
Identical: discovery precision/recall/F1, classification, proposal-validation records,
governing-set output, packet Mode P. Bounded: coverage decrease ≤ 0.05; false-abstention
increase ≤ 0.03; missed-abstention increase ≤ 0.03; operative-source accuracy no decline;
unsafe not increased; determinism holds.

## Secondary endpoints & measurability
Full metric list per the task. Gold labels for operative polarity, scope overlap, and
conflict category do not exist in the frozen annotations; those are reported as DERIVED
DIAGNOSTIC or UNAVAILABLE, never as authoritative ground truth, in an additive namespace.
The frozen specification is not altered.

## Calibration gates (C0–C9)
Control identity; discovery identity; classification identity; validation identity;
governing-set identity; G3 operative identity; Mode P identity; visible non-degradation;
co-occurrence safety (co-occurrence alone must not abstain); genuine-conflict activation
(a synthetic genuine conflict must abstain). All must pass before hidden evaluation.

## Visible-corpus use & synthetic fixtures
Visible use limited to interface validation, crash repair, control reproduction,
protected-stage identity, no-degradation checks, and co-occurrence safety. Because the
visible corpus contains no genuine competing operatives, synthetic fixtures (invented
neutral names; NOT derived from hidden text) exercise scoped non-conflict, temporal
non-overlap, exception, override, compatible/cumulative, parallel authority, and a
genuine unresolved conflict. All pre-lock corrections documented.

## Statistics
Paired case-level; exact McNemar for binary correctness; paired bootstrap for selective
(seed 20240601). Compare C4 vs C0 (primary), C4 vs historical G4 (diagnostic), C0 vs
frozen v0.2 (diagnostic). With ~60 synthetic cases, emphasize effect size and case-level
mechanism.

## Run protocol / determinism
Two byte-identical runs required (operative artifacts, conflict classifications,
abstention records, final outputs, aggregate reports). No run discarded.

## Prohibited post-lock changes
No rule/threshold/schema/adapter/code/case change; no hidden-specific correction; no
selective reruns. An objective execution defect requires invalidating affected outputs, a
new lock version, and a full rerun.

## Verdict criteria & interpretation boundary
PROMISING / NO CLEAR SIGNAL / FALSIFIED per the task. Questions 11 (promote) and 12
(broad generalization) are answered NO; question 10 (packet the active bottleneck) is
answered strictly by the evidence. Even a positive result supports only: a deterministic
competing-operative model improved governance behavior on the 60-case Hidden
Relationship Corpus Pilot v0.2 while preserving the G3 mechanism — not generalization,
enterprise readiness, legal correctness, production safety, certification, or RRB v1.0.
