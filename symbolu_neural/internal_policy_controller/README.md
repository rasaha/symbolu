# Internal Draft→Policy→Final-Answer Symbol-U Controller (experimental / isolated)

**Status: EXPERIMENTAL, SMOKE-LEVEL.** A critique-and-revise / self-refinement loop
whose critic is **Symbol-U/PSE** instead of the LLM itself. No weights changed, no
Transformer trained, no decoder built.

Read the full write-up in **`INTERNAL_POLICY_CONTROLLER_REPORT.md`**.

## Idea

```
user prompt → initial draft → Symbol-U/PSE critic diagnoses the draft
            → revision policy → shared reviser → final answer
```
Like Self-Refine / Reflexion / Constitutional AI, but the critic is Symbol-U.

## Why this is testable offline

The new component is the **critic**. We generate drafts with KNOWN flaws
(speculative / escalated / verbose / vague / none) and measure each critic's
**diagnostic accuracy** (ground-truth labels, held-out) — assumption-light, no LLM
needed. A shared rule-based reviser then applies whatever policy the critic emits,
so final-answer differences trace to critic quality.

## Arms

`base` · `generic_refine` (content critic ≈ LLM self-critique) · `sentiment` ·
`random` · `shuffled_symbolu` · `relabeled_symbolu` · `symbolu`.

## Result (smoke-only)

Symbol-U critic diagnostic accuracy **0.333** (chance 0.200) — barely above
chance, **below** the content critic (0.533) and **far below** the sentiment
critic (1.000); **ontology irrelevant** (relabeled = symbolu). Final-answer
improvement: symbolu 0.054 **< generic self-refine 0.071 < sentiment 0.101**.
→ **The Symbol-U controller does not beat generic self-refinement.**

## Commands

```bash
export PYTHONPATH=$(pwd)
python -m symbolu_neural.internal_policy_controller.cli run       # the pilot
python -m symbolu_neural.internal_policy_controller.cli drafts    # example flawed drafts
python symbolu_neural/internal_policy_controller/tests/test_controller.py
```
Hardened run (needs a real LLM / API key; not available in this sandbox): swap in
`reviser.LLMReviser` + an LLM judge — see report §8.

## Limitations

No pretrained LLM / API offline → rule-based reviser + proxy evaluators, small N,
single seed. The **diagnostic-accuracy** finding is the trustworthy, decisive part;
a real LLM would only strengthen the generic-self-refinement baseline Symbol-U
already loses to.

## Isolation

Separate from `clean_softmax`, `complementarity_probe`, `controllability_pilot`,
`api_control_protocol`, and Hybrid-Phase/Sovereign/JEPA. Reuses only
`complementarity_probe.backends` to compute a draft's Symbol-U state. Nothing
deleted.
