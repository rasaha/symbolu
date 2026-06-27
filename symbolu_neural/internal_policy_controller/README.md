# Internal Draft→Policy→Final-Answer Symbol-U Controller

> ## ⚠️ CANONICAL VERSION IS **v3** → [`v3/`](v3/)
> - **v3/** — current canonical implementation. Use this. See
>   [`INTERNAL_POLICY_CONTROLLER_V3_REPORT.md`](INTERNAL_POLICY_CONTROLLER_V3_REPORT.md)
>   and [`VERSION_CLEANUP_PLAN.md`](VERSION_CLEANUP_PLAN.md).
> - **v1** (these top-level files) and **v2/** are retained **only for audit /
>   history**. They are **superseded and defective** — do **NOT** run them for any
>   scientific conclusion.
>   - v1 was an invalid prototype (proxy classifier, regex revision, no real Symbol-U
>     state) — see `IMPLEMENTATION_FORENSIC_REVIEW.md`.
>   - v2 had wiring defects (only Guna+Valence reached policy, Aspect missing,
>     dead branches) — see `V2_WIRING_AUDIT.md` / `V2_AUDIT_AND_V3_PLAN.md`.
> - Note: v3 currently reuses v2's `data.py`, `llm.py`, `judge.py` as **shared
>   helpers** (live dependencies — do not delete v2 wholesale; see cleanup plan).

---

## v1 (DEPRECATED — audit history only)

**Status: SUPERSEDED by v3. Invalid prototype.** A critique-and-revise loop whose
critic is **Symbol-U/PSE**. Kept only as the documented record of what not to do.

Read the v1 write-up in **`INTERNAL_POLICY_CONTROLLER_REPORT.md`** and why it is
invalid in **`IMPLEMENTATION_FORENSIC_REVIEW.md`**.

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
