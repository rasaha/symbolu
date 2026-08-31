# EXPERIMENT_PREREGISTRATION — Exploratory Resolver Study v0.1

**Written and frozen BEFORE any hidden evaluation.** Hashed at lock time
(HIDDEN_EVALUATION_LOCK.md). Not modified after hidden evaluation begins.

Frozen and untouched: SEEB v1.0.0, Hybrid Handover, retrieval benchmarks, baseline
extractors, Relationship Resolution Measurement Spec v1.0, Relationship Corpus
Curation Spec v1.0, the visible development corpus, the 22 hidden seed cases, the
38 hidden pilot cases, hidden annotations, lifecycle records, and the existing
deterministic resolvers. No resolver performance from the hidden set is inspected
before all preregistered runs complete. All data synthetic.

## Research question
Does a structured hybrid resolver produce a measurable capability signal beyond
deterministic graph traversal on the visible corpus and the frozen 60-case Hidden
Relationship Corpus Pilot v0.2 — without sacrificing precision, governance,
packet realization, abstention quality, determinism, or fail-closed behaviour?

## Hypotheses
- **H0 (null):** HybridRelationshipResolver does not meaningfully improve over
  GraphTraversalResolver after accounting for variance, abstention, parser
  behaviour, difficulty, capability distribution, and multiple comparisons.
- **H1 (alt):** It improves ≥1 preregistered owner-clean capability metric on the
  hidden pilot without materially degrading the others, without increasing
  unsafe/overconfident answers, without hidden-specific tuning, and across >1
  wording/structural family.

## Resolver
- **HybridRelationshipResolver** = a richer RELATIONSHIP-PROPOSAL layer feeding
  the FROZEN GraphTraversalResolver governance + packet builder (reused by
  composition, not modified). This isolates any gain to relationship discovery.
- Inputs (identical to every resolver): `(question, evidence: list[EvidenceSpan])`.
  Never receives ids-with-meaning, capability, difficulty, gold graphs, gold
  governance, packet expectations, ambiguity labels, rationales, confidences, or
  abstention reasons.
- Outputs: `ResolutionResult` (graph, governance, tfc/notice/penalty) plus a
  machine-readable, deterministic intermediate-artifact dict (proposed nodes/edges,
  edge confidence, type, direction, provenance, governance, excluded evidence,
  packet, abstention decision+rationale, confidence).
- **Deterministic. No training. No LLM/prompt.** (Stated explicitly per DATA and
  PROMPT boundary docs.)

## Datasets
- Visible development corpus (16 SEEB relationship cases via the frozen measurement
  package) — debugging, interface validation, threshold selection ONLY.
- Hidden Relationship Corpus Pilot v0.2 (22 seed + 38 pilot = 60) — FINAL
  preregistered evaluation only; not inspected per-case before evaluation.

## Metrics (owner-clean, frozen definitions)
Discovery precision/recall/F1; classification accuracy; edge-type & direction
accuracy; governance accuracy (Mode G); packet-realization accuracy (Mode P);
abstention precision/recall, false-abstention rate, missed-abstention rate, answer
coverage, selective accuracy. Parser (negation, type) and SafetyGate (coverage
abstention) reported SEPARATELY and never in the resolver score.

## Primary endpoint (singular)
**Hidden owner-clean macro** = unweighted mean of exactly five metrics on the
hidden pilot:
`(discovery_F1 + classification_accuracy + governance_accuracy_modeG +
 packet_realization_accuracy_modeP + selective_accuracy) / 5`.
Excludes parser/SafetyGate metrics and answer_coverage (coverage is a separate
constraint). Practical-significance threshold: **macro improvement ≥ 0.03**
absolute over GraphTraversalResolver.

## Non-inferiority constraints (vs GraphTraversalResolver) — FROZEN margins
An apparent macro gain is NOT successful if any occurs:
- discovery precision decreases > 0.05;
- governance accuracy (Mode G) decreases > 0.03;
- packet realization (Mode P) decreases > 0.03;
- selective accuracy decreases > 0.03;
- false-abstention rate increases > 0.05;
- missed-abstention rate increases > 0.05;
- answer coverage decreases > 0.10;
- unsafe/overconfident answer count increases (a wrong non-abstained answer where
  gold abstains, i.e. a missed-abstention producing a confident wrong answer);
- determinism fails.

## Secondary endpoints
All metrics listed above, reported per the frozen owner separation.

## Comparators (same framework, unaltered)
Null; Always-abstain; FrozenResolver; RuleResolver; GraphTraversalResolver;
HybridRelationshipResolver.

## Abstention policy (deterministic; thresholds from VISIBLE only)
Abstain when: a required reference is unresolved (dangling/cycle); ≥2 governing
outcomes remain equally supported (version conflict); unresolved graph
contradiction; provenance missing for a decisive edge; edge confidence below the
preregistered threshold **τ = 0.5**; governing evidence not uniquely identifiable.
τ and any thresholds are selected on the visible corpus and frozen before hidden
evaluation.

## Ablations (preregistered)
A0 full; A1 no semantic proposal (falls back to the narrow cue set); A2 no
governance traversal (proposal only); A3 no governance rule layer; A4 no
confidence abstention; A5 no provenance requirement; A6 discovery only; A7 Mode G
(gold graph); A8 Mode P (gold governance).

## Run protocol
Fully deterministic → **2 complete repetitions, byte-identical outputs required**.
No stochastic component → no seeds (stated explicitly). Run order fixed
(comparator list order), recorded in the manifest.

## Statistics
Paired case-level. Binary per-case correctness: **exact McNemar** (Hybrid vs
GraphTraversal). Composite per-case macro: **paired bootstrap 95% CI** (fixed
resample seed recorded). Multiple-comparison correction across secondary
endpoints: **Holm**. Primary endpoint remains singular. Report absolute diff,
relative diff, CI, n, p, effect size. Significance ≠ practical significance.

## Failure attribution
Each incorrect case → exactly one primary stage: evidence acquisition; semantic
parsing; relationship discovery; relationship classification; graph construction;
governance application; packet realization; abstention decision; SafetyGate;
infrastructure. Secondary contributing stage recorded separately.

## Allowed implementation corrections
Only objective execution bugs (crashes, wrong wiring) may be fixed. Any fix after
hidden lock invalidates prior hidden runs, bumps the lock version, and reruns all
resolvers from scratch (disclosed).

## Prohibited post-hoc changes
No threshold/prompt/rule change from hidden results; no lexical rule from hidden
wording; no case removal; no abstention-threshold change post hoc; no selective
reruns; no ablation added after hidden results.

## Reporting format
The 14 deliverable docs + 12 tables named in the task, plus a single final verdict:
PROMISING SIGNAL / NO CLEAR SIGNAL / FALSIFIED IN CURRENT FORM, and the six
required questions. Q6 (broad generalization) is answered NO a priori — 60 cases
is not a certification corpus.
