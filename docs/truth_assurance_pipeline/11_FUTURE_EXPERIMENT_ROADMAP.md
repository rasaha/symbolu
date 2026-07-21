# TAP — Future Experiment Roadmap v0.1

**Future experiments only.** Each evaluates **exactly one layer**; no experiment
modifies more than one layer at a time. Architecture-only; nothing here is scheduled,
promised, or claimed to work.

> Boundary: `12_RESEARCH_BOUNDARIES.md`. These are *proposals*, contingent on corpora
> that largely do not yet exist.

---

## 1. One-layer-at-a-time rule

An experiment may implement/replace **one** layer and must hold all others fixed
(stub or frozen). This keeps failure attribution clean and preserves independent
replaceability.

## 2. Proposed experiments

| # | Experiment | Layer | Question | Prerequisite corpus | Status |
|---|---|---|---|---|---|
| E1 | Relationship Analysis Experiment | L1 | are proposed relationships supported by evidence? | relationship-truth corpus (gold labels + spans) | corpus does not exist |
| E2 | Governance Resolution Experiment | L2 | is applicability / operative source decided correctly? | governance-truth corpus (genuine + resolved conflicts) | corpus does not exist |
| E3 | Evidence Assembly Experiment | L3 | is the packet minimal **and** complete? | packet corpus (gold minimal sets) | corpus does not exist |
| E4 | Claim Validation Experiment | L4 | is each claim correctly statused? | claim-truth corpus | **synthetic prototype exists** (`relationship_claim_validation/`); a *real* corpus does not |
| E5 | Response Validation Experiment | L5 | is the whole answer faithful? | response-truth corpus | corpus does not exist |
| E6 | Cross-Layer Provenance Experiment | cross | is every assertion end-to-end traceable? | an end-to-end pipeline + labeled traces | pipeline does not exist |
| E7 | Cross-Layer Confidence Experiment | cross | are confidence dimensions calibrated? | labeled outcomes per dimension | data does not exist |

## 3. Sequencing logic (not a schedule)

1. **E4 first is already partly done** (synthetically). Turning it into a *real*
   experiment (real corpus, possibly LLM judges with measured inter-judge reliability)
   is the most concrete next step.
2. **E1 and E2 are independent** of each other and can proceed in either order once
   their corpora exist; E2 consumes E1's output type but is evaluated in isolation
   against gold applicability.
3. **E3 depends on E1+E2 outputs** conceptually but is evaluated against its own gold
   minimal-set corpus.
4. **E5 depends on E4** conceptually but is evaluated against its own faithful-answer
   corpus.
5. **E6/E7 are last** — they require a working end-to-end pipeline to measure across.

## 4. Per-experiment requirements (all must hold)

- Preregistration + hidden lock before results.
- One layer implemented/replaced; others frozen/stubbed.
- Negative + positive controls (`10_…`).
- Honest corpus provenance (synthetic vs real; self-authored ground truth flagged).
- Deterministic reproducibility, or declared non-determinism for LLM components.
- A verdict that separates *process validation* from *sufficiency* and states an
  interpretation boundary.

## 5. What is explicitly NOT on the roadmap

- Merging any two truth problems into one layer.
- Any experiment that modifies more than one layer.
- Any claim of hallucination elimination, production readiness, or certification.
- Fabricating a corpus or results to unblock an experiment.
