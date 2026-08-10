# ClaimIntegrity — Completion Report

*Isolated, falsification-first research track investigating whether model outputs can be decomposed
into atomic governable claims without altering meaning — and whether a dedicated claim-integrity stage
is justified. 28 phases across 18 milestones (M1–M18). Deterministic, stdlib-only, no live calls,
enforcement off. AGE, AssertionGate, and EvidenceAssurance artifacts untouched throughout.*

## The question

Every downstream governance layer — EvidenceAssurance, AssertionGate — evaluates *a claim*.
EvidenceAssurance's own conclusion states it **assumes the correct claim has already been extracted**.
If decomposition silently changed the proposition (dropped a qualifier, inverted a negation, broadened
a population, detached a citation), every downstream decision is computed against the wrong claim. This
track asks whether that upstream assumption holds and whether it needs a component of its own.

## The answer

**Decomposition method dominates downstream safety — but a dedicated heavyweight component is not
justified.**

- **Decomposition drift is a real, downstream-invisible failure surface.** Every dimension-dropping
  error propagates to unsafe delivery (0.09–0.21) and **none is caught downstream** — the gate
  evaluates the altered claim faithfully because it cannot see the original. (H1 supported.)
- **How you decompose matters enormously.** Triple/parser extraction (OpenIE/SPO) causes **0.864**
  unsafe delivery by stripping negation/modality/qualifier/scope; a preservation-first splitter causes
  **0.068**. (H0-3, H0-9, H0-17 rejected.)
- **The heavyweight component does not beat sentence splitting** on the primary endpoint (both 0.068,
  in every partition and every risk tier). Its only distinct benefit is reference resolution
  (evidence-query 0.091 → 0.000), a secondary endpoint. A 2-probe sentence splitter ties the 15-probe
  component. (H0-1, H0-14, H0-18 survive.)

## Decision

**Reduce to semantic validation after simple splitting** (Option 4 of 9). Use a cheap preservation-
first splitter (never strip, resolve references, skip non-assertive text, ~4 probes); run the
per-dimension checkers as a **validator/audit of untrusted extractors** and a high-risk delivery gate
(their real value — catching a *different* system's drift, e.g. OpenIE at 0.864); preserve ambiguity
over false precision; send the residual to human review. Placed upstream of EvidenceAssurance as a
validation gate — **not** a heavyweight layer, not high-risk-only, not merged into EA, not
preserve-whole, not rejected. (`ARCHITECTURAL_DECISION.md`.)

## Falsification scorecard

Method-quality nulls (2, 3, 9, 17) **rejected**; distinct-component nulls (1, 14, 18) **survive**;
H1 (decomposition is a pre-evidence failure surface) **not falsified**; H0-15 (gold stability)
**rejected** (0.934 agreement, disagreement only on atomicity granularity). (`LIMITATIONS_AND_
FALSIFICATION.md`.)

## Milestones

| M | Phase(s) | Deliverable | Commit |
|---|---|---|---|
| M1 | 1–2 | prior-result freeze + claim model | `e3003c8` |
| M2 | 3–4 | claim taxonomy (30) + semantic-failure taxonomy (50) | `423f958` |
| M3 | 5 | falsification plan (18 H0) | `789f970` |
| M4 | 6–7 | ground-truth protocol + corpus (ci_corpus_v1, 832) | `a03622c` |
| M5 | 8 | baselines A–R + characterization | `2de56fd` |
| M6 | 9 | reference component (dependency-preserving) | `75edfc7` |
| M7 | 10–11 | vocabulary freeze + semantic-preservation machinery | `6feece2` |
| M8 | 12–14 | atomicity + qualifier/scope/negation/modality/uncertainty | `20f6255` |
| M9 | 15–16 | numeric/temporal/attribution + validation/audit | `58fdcd2` |
| M10 | 17 | adversarial decomposition study (25 traps) | `319ecae` |
| M11 | 18–19 | downstream impact + error propagation (primary) | `4231404` |
| M12 | 20 | ambiguity policy | `5710c87` |
| M13 | 21–23 | cost + ablation + complexity challenge | `ce4f304` |
| M14 | 24 | test suite + prior suites unchanged | `ef14933` |
| M15 | 25 | evaluation protocol freeze | `67f9229` |
| M16 | 26 | final evaluation report | `37228d9` |
| M17 | 27–28 | limitations/falsification + architectural decision | `7526a22` |
| M18 | — | this completion report | — |

## Final tallies

- **Files:** 30 Python modules under `claim_integrity/`, 18 docs under `docs/claim_integrity/`.
- **Dataset:** `ci_corpus_v1`, 832 examples, 5 partitions, 13 domains, 1144 gold claims, 806
  unsafe-allow; claim taxonomy 30 types; semantic-failure taxonomy 50 classes; vocabulary 17
  dispositions; 17 baselines.
- **Tests:** 26 ClaimIntegrity + 25 EvidenceAssurance + 32 AGE/AGR + 9 model-selection = **92 passed**,
  prior suites unchanged.
- **Key rates:** material drift — oracle 0.000, component/sentence-split 0.136, preserve-whole 0.545,
  OpenIE 0.705. Unsafe delivery — oracle 0.000, component/sentence-split 0.068, preserve-whole 0.454,
  OpenIE 0.864. Per-dimension preservation, invented/omitted, over/under-split all reported separately.

## Reproduce

```bash
python -c "from claim_integrity import dataset; dataset.dump_json('claim_integrity/data/v1/corpus.json')"
python -m claim_integrity.eval_baselines
python -m claim_integrity.eval_adversarial
python -m claim_integrity.eval_downstream
python -m claim_integrity.eval_ablation
python -m claim_integrity.verify_frozen          # this track's frozen artifacts
python -m claim_integrity.verify_prior_artifacts # AGE + AssertionGate + EvidenceAssurance, unchanged
python -m pytest claim_integrity/tests evidence_assurance/tests assertion_governance/tests \
  assertion_gate_robustness/tests model_selection_reconciliation/tests -q   # 92 passed
```

## Integrity notes

- **Anti-circularity:** gold is annotator-derived from a TRUE latent decomposition; methods see only
  observed text.
- **Two honest corrections made in the open:** an adversarial gold-construction bug (two 2-claim cases
  listed only one gold, falsely flagging the component) and a taxonomy-mandated non-assertive filter
  the adversarial study exposed — both documented, neither silently reconciled.
- **No masking:** prior AGE + AssertionGate + EvidenceAssurance suites re-run unmodified; all nine
  guarded prior artifacts byte-identical throughout.
- **Bounds stated as prominently as results:** the P≈B tie on the primary endpoint, the simulated
  nature of the parser/LLM baselines, and the deterministic-corpus limit are in the headline of every
  summary.

## Document index

Scope & model: `PRIOR_RESULTS_AND_SCOPE.md`, `CLAIM_MODEL.md`, `VOCABULARY_V1.md` ·
Taxonomies: `CLAIM_TAXONOMY.md`, `SEMANTIC_FAILURE_TAXONOMY.md` ·
Protocols: `FALSIFICATION_PLAN.md`, `GROUND_TRUTH_PROTOCOL.md`, `SEMANTIC_PRESERVATION_PROTOCOL.md`,
`ATOMICITY_PROTOCOL.md`, `AMBIGUITY_POLICY.md` ·
Experiments: `ADVERSARIAL_DECOMPOSITION_STUDY.md`, `DOWNSTREAM_IMPACT.md`, `ERROR_PROPAGATION_MATRIX.md`,
`COST_ABLATION_COMPLEXITY.md` ·
Freeze & conclusions: `EVALUATION_PROTOCOL.md`, `EVALUATION_REPORT.md`, `LIMITATIONS_AND_FALSIFICATION.md`,
`ARCHITECTURAL_DECISION.md`.
