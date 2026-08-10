# Evaluation Protocol (Phase 25 — FROZEN)

*Frozen before the final report (Phase 26). Endpoints, corpus, methods, and decision rules are fixed
here so the report cannot be metric-shopped. Corpus and result artifacts are hash-pinned in
`claim_integrity/verify_frozen.py`; the prior-track artifacts remain guarded by
`claim_integrity/verify_prior_artifacts.py`.*

## Frozen artifacts

| Artifact | SHA-256 (16) |
|---|---|
| `data/v1/corpus.json` | `1fe856cc10de9d47` |
| `eval_results/baselines.json` | `d4276b3b460c6ca5` |
| `eval_results/adversarial.json` | `f22e830d0d1a6f6b` |
| `eval_results/downstream.json` | `d459c26ab5ef3af3` |
| `eval_results/ablation.json` | `7af3acd437ab68d5` |

All results confirmed deterministic across repeated runs before pinning.

## Endpoints (fixed — no post-hoc substitution)

**Primary safety endpoint — unsafe downstream delivery.** A decomposition that causes a claim which
should be withheld to be delivered-as-supported by the thin AssertionGate (Phase 18). Lower is better.

**Co-primary — material semantic-drift rate.** Fraction of gold claims whose aligned produced claim is
not materially preserved (per the per-dimension check, Phase 11). Lower is better.

**Key secondary (reported, not decisive):** evidence-query alteration (dangling-reference), false
rejection, omitted/invented-claim rates, over/under split, per-dimension preservation vector, cost in
probes.

## Methods

17 baselines A–R (preserve-whole, sentence/clause split, dependency/SRL/OpenIE/SPO — the last four
deterministic local approximations of unavailable parsers/LLMs, labelled `SIMULATED`), the reference
component P, oracle Q, and three simple complexity comparators (SC1–SC3). Simulated methods make **zero
model calls**; the report states this everywhere they appear.

## Analysis plan

1. Rank methods by the primary endpoint (unsafe delivery), then co-primary (material drift).
2. Report the component vs sentence-splitting explicitly on both endpoints and on evidence-query.
3. Report the error-propagation matrix (which drift types reach unsafe delivery; whether downstream
   catches them).
4. Report the ablation (which mechanism is load-bearing) and the complexity comparators (does the full
   stack beat a 2-probe splitter).
5. Stratify by partition, domain, risk tier, claim type, and semantic-failure type.

## Decision rules (fixed before writing the report)

The architectural decision (Phase 28) is driven by these, decided in advance:

- **A distinct heavyweight ClaimIntegrity layer is justified** only if the component materially beats
  sentence-splitting on the **primary** endpoint (unsafe delivery), not merely on a secondary one.
- **Triple/parser extraction is to be recommended against** if it materially raises unsafe delivery
  over sentence-splitting (a robustness claim, not a component claim).
- **The recommendation reduces to the minimal sufficient configuration** if a simple comparator
  (≤ a few probes) reproduces the component's primary-endpoint result.
- **No claim of production readiness.** The corpus is deterministic and self-built; only mechanism and
  ordering transfer, not rates.

## What would falsify the study's core hypothesis

H1: *a material share of downstream governance failures originate in claim decomposition, before
evidence evaluation.* Falsified if, on the frozen corpus, decomposition drift did not propagate to
unsafe delivery, or downstream layers absorbed it. Result: **not falsified** — every dimension-dropping
perturbation reaches unsafe delivery (0.09–0.21) and none is caught downstream.

The **null that survives** is H0-1 on the primary endpoint: sentence splitting ties the component on
unsafe delivery. The study reports this as its central honest finding, not as a failure to be
explained away — the component's measured value is confined to reference resolution (a secondary
endpoint), and the report and decision are written around that.

## Pre-committed shape of the conclusion

- **Robust positive:** decomposition *method* matters enormously — triple extraction is dangerous
  (0.86 unsafe); preservation-first (never-strip) is essential.
- **Honest negative:** the heavyweight component does not beat a cheap preservation-first splitter on
  the primary endpoint; its distinct value is reference resolution.
- **Direction:** toward a reduction (minimal splitter + reference resolution + per-dimension checkers
  as an *audit* of untrusted extractors), not a large distinct stage — subject to the Phase-27/28
  write-up, which may not move these numbers.
