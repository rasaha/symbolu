# Internal Policy Controller v3 — Report

v3 implements the fixes from `V2_AUDIT_AND_V3_PLAN.md`. v2 is kept intact as the
audited-defective record (nothing deleted). Code: `v3/`. No API key in this sandbox,
so the **quality verdict still cannot run here**; the mock backend is plumbing-only
and the pilot refuses a verdict.

## What was fixed from v2 (each defect → resolution, verified)

| v2 defect | v3 resolution | verification |
|---|---|---|
| **D1** 6/8 state fields inert | every **policy-driving** variable maps to a **distinct** axis; a **field-influence self-check** fails if any is inert | `cli check` → all 6 OK; `test_every_policy_driving_var_influences_policy` |
| **D2** Aspect never computed | `aspect_balance` computed via `varna_lens → phase4a.lookup` | `test_full_state_includes_aspect` |
| **D3** sattva unreachable | Vritti→Guna remap (sattva ← RELEASE+OSCILLATION); all 3 reachable | `test_sattva_is_reachable`, `test_tone_all_three_reachable` |
| **D4** dead branches (resonance `<0.5`, constant clarity) | resonance threshold recalibrated to real range; caution thresholds calibrated to the aspect_balance range; clarity declared a **fixed default, not claimed state-driven** | `test_no_dead_caution_branch` |
| **D6** structural used prompt-states, quality used draft-states | quality path uses **draft-states**; structural note documents prompt-state stand-in | code `run_quality` |
| **D7** silent fallbacks | `_valence`/`_aspect` failures are **counted in `state.warnings`**; judge-zero responses counted as `judge_failures` | `test_state_warnings_surface_not_silent` |
| **D8** relabel permuted only guna | relabel permutes **guna + kosha + valence** (every consumed category) | `test_relabel_permutes_all_consumed_categories` |

Policy wiring (each Symbol-U variable → one axis): `guna→tone`, `vritti→directness`,
`kosha→reasoning_style`, `aspect_balance→caution`, `guna_resonance→uncertainty`,
`valence→speculation_reduction`. `pse_meaning/pse_resonance/kosha_resonance/
valence_sign` are explicitly **diagnostic-only** (kept in state, not claimed to
drive policy) — honesty about claim-vs-wiring, the central v2 failure.

## Structural results (real, offline)

- **Field-influence self-check: ALL 6 PASS.**
- **Distinct Symbol-U policies: 11/12** (v2 produced only 4).
- Tone, directness, reasoning_style, caution, uncertainty, speculation all reachable
  across prompts (no dead axis).
- Policy divergence vs the real Symbol-U policy: `relabeled 0.333`, `shuffled 0.536`,
  `sentiment 0.524`, `random 0.571`, `nl 0.643` — relabel `> 0` confirms the
  **specific ontology labels** now change the policy (and across guna+kosha+valence).

## What is still limited

- **No quality verdict in-sandbox** (no API key) — the headline question
  (does Symbol-U beat the controls?) is **untested**.
- **Guna/Kosha are derived from Vritti** (no canonical text→guna/kosha exists), so
  they are re-expressions of the vritti distribution, not independent measurements —
  but they now map to *different* axes via *different* label sets, and the
  relabel/shuffle controls test whether the specific assignment matters.
- **aspect_balance is weakly discriminative** (empirical range 0.79–1.0); its caution
  thresholds are calibrated to that range and are the most tuning-sensitive part.
- Translation is hand-authored (as any policy layer is); `relabeled`/`shuffled`/
  `random` exist precisely to test whether the *specific* ontology, not just *a*
  policy, drives any quality gain.
- Single model / single seed when run; hardening (≥2 models, ≥3 seeds, human
  spot-check) listed below.

## Commands for the real run (RunPod / any host with API access)

```bash
export PYTHONPATH=$(pwd)
python -m symbolu_neural.internal_policy_controller.v3.cli check    # gate: must all pass
python -m symbolu_neural.internal_policy_controller.v3.cli state    # inspect state+policy
export ANTHROPIC_API_KEY=...    # or MISTRAL_API_KEY

# statistically valid run: 36 prompts × 3 seeds = n≈108/arm, with 95% CIs +
# paired symbolu−control differences (SIG = CI excludes 0)
python -m symbolu_neural.internal_policy_controller.v3.cli run --backend anthropic --seeds 3
python symbolu_neural/internal_policy_controller/v3/tests/test_v3.py
```

**Sample size:** the prompt set is **36** (6 categories × 6, each with a
paraphrase); `--seeds N` pools `0..N-1` so `--seeds 3 ⇒ n ≈ 108 per arm`. Cost ≈
36×16 = 576 LLM calls/seed (~$1–3 on a small model), ~1,700 calls for 3 seeds.

**Pre-registered pass condition (now CI-based):** the **paired** difference
`symbolu − control` must have a 95% CI **strictly above 0** (SIG) for *every*
control — `generic_refine`, `nl_policy`, `sentiment_critic`, `random_policy`,
`shuffled_symbolu`, AND `relabeled_symbolu`. A significant win over all controls
*except* `relabeled` ⇒ the controller helps but the **specific ontology** does not.
**Signal-coverage audit** (`cli coverage`, offline): all 6 policy-driving variables
are wired & influence the policy; value-coverage on the 36 prompt-states is **full
for guna(3/3), valence(3/3)** and for the **tone/directness/caution/speculation**
axes, with continuous `guna_resonance` spanning 0.41–1.0 and `aspect_balance`
0.79–1.0. The **only** gap: `vritti_top` and `kosha_top` are **4/5** — the
`RELEASE`→`anandamaya`→"holistic" reasoning_style value is **structurally
near-unreachable** on natural text (probe: even vowel-saturated strings don't make
RELEASE the argmax). This is a property of the phonological vritti mapper, **not a
wiring defect** (the field-influence self-check passes for all 6), and forcing it
via prompt selection or a re-map would be dishonest. The quality run uses
**draft**-states × seeds, which broadens coverage beyond this prompt-state proxy.
A regression test (`test_signal_coverage_audit`) pins this audited coverage.

## Final answer

The experiment is now **structurally sound** — the wiring faithfully implements
draft → full Symbol-U analysis → ontology-driven policy → LLM rewrite → independent
judge, and every claimed Symbol-U variable provably influences the policy (the exact
thing v2 failed). **But the hypothesis remains UNTESTED for answer quality** because
no LLM API is available here. v3 is the version worth spending API credits on; run
the commands above on a host with a key to get the honest verdict. Given all prior
evidence my pre-registered expectation is that `symbolu` ties `generic_refine`/
`nl_policy` and does not beat `relabeled_symbolu` — but that is now a real empirical
question this harness can answer.
