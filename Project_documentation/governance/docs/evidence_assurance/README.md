# EvidenceAssurance — Completion Report

*Isolated research track investigating whether provenance-aware, independence-aware evidence
verification can detect correlated grounding+entailment failures that downstream signal composition
cannot. 24 phases across 16 milestones (M1–M16). Deterministic, stdlib-only, no live calls, enforcement
off. Prior AGE + AssertionGate work untouched throughout.*

## The question

A claim can be **grounded** (the passage says it) and **entailed** (NLI agrees) and still be **wrong** —
when both evaluate against the same wrong evidence. Grounding and entailment then fail *together*, and
no downstream combination of them can detect it. Can a verification layer that reasons about
**provenance and independence** catch what signal composition cannot?

## The answer (bounded)

**Yes, for correlated failures that leave an observable tell — and no otherwise.**

- On the frozen corpus, the reference component reaches **correlated-failure escape = 0.000** and
  **overall escape = 0.000** at a **false-block of 0.114 that is entirely NLI-proxy noise** (15/132).
- Every signal-only baseline — and a learned comparator over those signals — escapes **0.667–1.000**.
  The deficiency is in the *inputs* (no independence/provenance information), not model capacity.
- **Ceiling:** a no-tell correlated failure (false claim, aligned passage, no counterevidence,
  fabricated provenance) escapes **100%**. No metadata-based method can catch a failure that leaves no
  metadata trace. That residual needs external/human verification.
- **Complexity:** on this benign corpus the primary endpoint is reachable by **independence alone**
  (2 probes of 18), because every trap case carries multiple tells. The full stack earns its cost under
  **adversarial provenance fabrication** (independence-alone escapes 0.500; full stack 0.000) and by
  covering **non-correlated** failure states.

## Decision

Adopt as an **upstream, high-risk-gated evidence-verification stage feeding a thin AssertionGate** — in
shadow mode, with the bounded claim, abstention-as-data-quality-alarm, full stack for high-risk /
independence-first elsewhere, and the no-tell residual routed to external verification. **Not** a
product, **not** an 11th canonical module, **not** a merge into AssertionGate. (`ARCHITECTURAL_DECISION.md`.)

## Falsification scorecard

13 of 15 preregistered nulls **rejected**; H0-4 rejected in the bounded/adversarial sense; **H0-12
(no-tell / model-consensus failure) not rejected** and owned as the fundamental limit.
(`LIMITATIONS_AND_FALSIFICATION.md`.)

## Milestones

| M | Phase(s) | Deliverable | Commit |
|---|---|---|---|
| M1 | 1–2 | prior-result freeze + evidence model | `ce9ccdb` |
| M2 | 3–4 | correlated-failure taxonomy (30) + falsification plan (15 H0) | `ee6fae3` |
| M3 | 5–7 | ground-truth protocol + provenance corpus | `cbb3b66` |
| M4 | — | provenance graph + source identity + duplicate detection | `2fbd32b` |
| M5 | 8–9 | alignment + independence + observed downstream signals | `429b39d` |
| M6 | 10–11 | counterevidence search + frozen disposition vocabulary | `c54d593` |
| M7 | 12 | baselines A–T **+ corpus v1_1 gold-gate correction** | `e10714f` |
| M8 | 13 | reference component (layered disposition) | `2c3352b` |
| M9 | 14 | AssertionGate adapter + contract + thin-gate tests | `2d996ca` |
| M10 | 15–16 | correlated-failure scenarios + missing-metadata study | `18beeb9` |
| M11 | 17–19 | ablation + cost proxy + defense-in-depth | `2dc2586` |
| M12 | 20 | test suite + prior suites re-run unchanged | `328780b` |
| M13 | 21 | evaluation protocol freeze | `33b7805` |
| M14 | 22 | final evaluation report | `e2212e1` |
| M15 | 23–24 | limitations/falsification + architectural decision | `4ba4547` |
| M16 | — | this completion report | — |

## Reproduce

```bash
# regenerate everything (deterministic)
python -m evidence_assurance.eval_baselines
python -m evidence_assurance.eval_assurance
python -m evidence_assurance.experiments
python -m evidence_assurance.eval_ablation
python -c "from evidence_assurance import dataset; dataset.dump_json('evidence_assurance/data/ea_corpus_v1_1.json')"

# verify frozen artifacts (this track's outputs, and the prior AGE/AGR artifacts)
python -m evidence_assurance.verify_frozen
python evidence_assurance/verify_prior_artifacts.py

# tests: EA + prior AGE + AssertionGate-robustness + model-selection, all unchanged
python -m pytest evidence_assurance/tests assertion_governance/tests \
  assertion_gate_robustness/tests model_selection_reconciliation/tests -q
# -> 66 passed
```

## Integrity notes

- **Anti-circularity:** gold is derived from TRUE latent state by two independent annotator rubrics +
  conservative adjudication; methods see only OBSERVED (possibly misleading) metadata.
- **Honest corpus correction:** M7 surfaced a gold-labeling bug (a high-risk gate compared a severity
  string against a domain-name set, making `AUTHORITY_MISMATCH` unreachable). It was fixed in the open,
  versioned v1 → v1_1, and documented (`CORPUS_CHANGELOG.md`) — not silently reconciled.
- **No masking:** the prior AGE + AssertionGate suites were re-run unmodified (32 passed); the four
  guarded prior artifacts are byte-identical throughout.
- **Bounds stated as prominently as results:** the no-tell ceiling and the benign-corpus redundancy are
  in the headline of every summary, not buried.

## Document index

Scope & model: `PRIOR_RESULTS_AND_SCOPE.md`, `EVIDENCE_MODEL.md`, `VOCABULARY_V1.md` ·
Design: `CORRELATED_FAILURE_TAXONOMY.md`, `GROUND_TRUTH_PROTOCOL.md`, `INDEPENDENCE_MODEL.md`,
`ALIGNMENT_PROTOCOL.md`, `CORPUS_CHANGELOG.md` · Methods: `BASELINES.md`, `COMPONENT.md`,
`ASSERTIONGATE_CONTRACT.md` · Experiments: `EXPERIMENTS.md`, `ABLATION_AND_COST.md`, `TEST_SUITE.md` ·
Freeze & conclusions: `FALSIFICATION_PLAN.md`, `EVALUATION_PROTOCOL.md`, `EVALUATION_REPORT.md`,
`LIMITATIONS_AND_FALSIFICATION.md`, `ARCHITECTURAL_DECISION.md`.
