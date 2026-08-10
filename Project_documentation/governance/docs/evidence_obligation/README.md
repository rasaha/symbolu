# Contextual Evidence Obligation and Utility Calibration Study — Completion Report

*A falsification-first calibration track. Begins from the completed Bounded Governed Inference
Natural-Artifact Shadow Pilot, which found the runtime **safe but operationally low-value** on natural
artifacts (0% clean allow, 85.5% over-qualification), caused by applying a **uniform** evidence burden.
This study asks whether a **contextual** evidence-obligation policy can restore utility without weakening
safety. Consumes all prior components **read-only**; shadow-only, non-enforcing, no external actions.*

## Answer

> **The concept works; the rich component does not earn its complexity.** Contextual evidence obligation
> converts the natural-artifact failure into **29.6% safe clean-allow (oracle) / 58.4% (reference)** with
> over-qualification down from **85.5% to 2%** — but a **3-rule risk-only policy reaches higher safe
> clean-allow (66.8%)** than the 90-rule reference component, and the reference classifier **leaks 10
> adversarial disguise cases**. Decision: **reduce to a claim-type + source-role policy** and **fix the
> obligation classifier's adversarial safety before any pilot.**

## The central mechanism

An `EvidenceObligation` stage upstream of Evidence binding assigns each claim one of **14 obligation
types** (never a binary flag), then a contract maps a *met* low-burden standard to an **obligation-
relative `VERIFIED`** — "standard met by context/implementation; factual truth not independently
established" — never to "claim is true." A high-external-burden obligation without external evidence
stays `INSUFFICIENT`. That single asymmetry is what lifts utility while holding safety.

## Findings by dimension (each on its own evidence)

| Dimension | Finding |
|---|---|
| **Utility** | large gain — 0% → 29.6% (safe oracle) / 58.4% (reference); over-qual 85.5% → 2% |
| **Concept safety** | oracle 0 unsafe on held-out AND adversarial |
| **Reference-classifier safety** | held-out high-risk unsafe 0; **adversarial disguise leaks 10** (model self-verification) |
| **Complexity** | risk-only (3 rules) **dominates** the reference (90 rules): 0.668 vs 0.584 clean, 0 vs 10 adversarial unsafe |
| **Load-bearing features** | `risk` (safety), `source_role` (utility, −27pp if removed); authority-guard/risk-escalation/floors inert on this data |
| **Reviewer stability** | simulated agreement 0.316; overrides skew stricter — real study required |
| **Latency / cost** | sub-ms, stdlib-only, deterministic |

## Falsification (18 nulls: 12 rejected / 6 retained)

Rejected (concept validated): H0-1, H0-3, H0-4, H0-5, H0-6, H0-7, H0-8, H0-9, H0-10, H0-12, H0-15, H0-16.
Retained (honest negatives): **H0-2** (risk-tier alone as good), **H0-11** (reference weakens high-risk
safety), **H0-13** (simple comparator matches), **H0-14** (reviewers disagree), **H0-17** (distinct stage
unnecessary), **H0-18** (readiness still blocked). Frozen success criteria: **7/9 pass** — the 2 failures
(no-adversarial-unsafe, improves-over-risk-only) are the exact signals the frozen criteria were designed
to catch.

## Decisions

- **Architectural (1 of 10): Option 3 — REDUCE TO CLAIM-TYPE + SOURCE-ROLE POLICY.** The concept is
  needed (uniform/global fail) but the 90-rule stage is not justified over a 3-rule risk / claim+source
  policy. Documented alternatives: Option 4 (risk-tier only, highest safe clean-allow) and Option 2
  (high-risk domains only).
- **Pilot (A–H): D — FIX EVIDENCE OBLIGATION FIRST.** Fix the adversarial self-verification leak and
  simplify; then an **internal single-tenant pilot (B) with a real review study** before any external
  exposure.

## Milestones

| M | Deliverable | Phases | Commit |
|---|---|---|---|
| M1 | freeze + prior results + utility-failure analysis | 1 | `586d67e` |
| M2 | obligation model + claim-to-obligation taxonomy | 2–3 | `bf5db01` |
| M3 | source-role + authority model | 4 | `27f959f` |
| M4 | falsification plan (18 nulls) | 5 | `85a33ec` |
| M5 | dataset + ground-truth protocol | 6–7 | `3a9e673` |
| M7 | reference EvidenceObligation component | 9 | `a52a533` |
| M6 | baselines A–S | 8 | `d1c65df` |
| M8 | obligation → EvidenceAssurance contract | 10 | `c5681f5` |
| M9 | contextual authority + implementation evidence | 11–12 | `1c3c309` |
| M10 | no-evidence-required + risk escalation | 13–14 | `4a0ccdc` |
| M11 | downstream utility evaluation (pivotal) | 15 | `d4441e8` |
| M12 | error propagation + calibration frontier | 16–17 | `8cdd0df` |
| M13 | ablation + complexity challenge | 18–19 | `4d5706b` |
| M14 | human-review study (simulated) | 20 | `7449f39` |
| M15 | consolidated test suite | 21 | `3f178fd` |
| M16 | evaluation protocol freeze | 22 | `38ca8d1` |
| M17 | final evaluation | 23 | `d8087e7` |
| M18 | falsification + architectural decision | 24–25 | `a2f54b1` |
| M19 | this completion report | — | — |

## Final tallies

- **Files:** 27 Python modules under `evidence_obligation/`, 22 docs under `docs/evidence_obligation/`,
  9 eval artifacts + 4 dataset files.
- **Prior artifacts verified unchanged:** 32 (17 research-track + 4 GIP + 1 CSR + 10 bounded_shadow_pilot),
  byte-identical; no frozen logic touched.
- **Dataset:** 500 items — DEVELOPMENT 150, HELD_OUT_NATURAL 250, ADVERSARIAL_OBLIGATION 100; 786 new
  natural artifacts available (SUFFICIENT). Obligation vocab `evidence_obligation_vocab_v1`; 14 obligation
  types; 31 claim families; 15 source roles; 19 baselines (A–S).
- **Tests:** 82 evidence_obligation + 193 prior = **275 passed**; prior suites unchanged.
- **Obligation accuracy (held-out):** exact 0.560, acceptable 0.736; **adversarial unsafe assignments 0**.
- **Authority accuracy:** 1.0 (canonical 16-case set). **Implementation-evidence matrix:** 1.0.
- **Downstream (reference, held-out):** clean-allow 0.584, over-qualification 0.020, false-withholding
  0.192, high-risk unsafe-allow 0, unsafe action-allow 0, **adversarial unsafe-allow 10**.
- **Reviewer agreement (simulated):** 0.316.
- **Calibration frontier:** safe-and-useful = risk-only (0.668), learned (0.332), oracle (0.296),
  simple-contextual (0.264); reference (0.584) is off the safe frontier.
- **Complexity comparator:** risk-only (3 rules) dominates the reference (90 rules).

## Unresolved blockers (before any external pilot)

1. Reference classifier's adversarial self-verification leak (10 cases).
2. Real (non-simulated) human-review study; simulated agreement is only 0.316.
3. Real evidence sources / real traffic — the safe utility ceiling (oracle 29.6%) is conditioned on a
   modelled available-evidence set.

**Not production-ready.** Shadow-only, read-only, de-identified, single execution window.

## Reproduce

```bash
python -m evidence_obligation.verify_prior_artifacts       # 32 prior artifacts intact
python -m evidence_obligation.dataset                      # 500-item dataset
python -m evidence_obligation.baselines                    # A-S obligation accuracy
python -m evidence_obligation.downstream                   # utility via frozen EA (pivotal)
python -m evidence_obligation.calibration_frontier         # safety-utility frontier
python -m evidence_obligation.ablation                     # feature ablation + complexity
python -m evidence_obligation.verify_evaluation_freeze     # freeze the evaluation
python -m evidence_obligation.final_evaluation             # 7/9 frozen criteria
python -m evidence_obligation.architectural_decision       # 18 nulls + decision
python -m pytest evidence_obligation/tests -q              # 82 passed
```

## Document index

`PRIOR_RESULTS_AND_SCOPE.md` · `UTILITY_FAILURE_ANALYSIS.md` · `EVIDENCE_OBLIGATION_MODEL.md` ·
`CLAIM_TO_OBLIGATION_TAXONOMY.md` · `SOURCE_ROLE_MODEL.md` · `FALSIFICATION_PLAN.md` ·
`GROUND_TRUTH_PROTOCOL.md` · `BASELINES.md` · `REFERENCE_COMPONENT.md` · `EVIDENCEASSURANCE_CONTRACT.md` ·
`CONTEXTUAL_AUTHORITY_PROTOCOL.md` · `NO_EVIDENCE_REQUIRED_POLICY.md` · `DOWNSTREAM_UTILITY.md` ·
`ERROR_PROPAGATION_REPORT.md` · `CALIBRATION_FRONTIER.md` · `ABLATION_AND_COMPLEXITY.md` ·
`REVIEW_PROTOCOL.md` · `EVALUATION_PROTOCOL.md` · `EVALUATION_REPORT.md` ·
`LIMITATIONS_AND_FALSIFICATION.md` · `ARCHITECTURAL_DECISION.md`.
