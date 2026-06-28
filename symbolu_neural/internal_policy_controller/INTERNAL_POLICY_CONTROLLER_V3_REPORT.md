# Internal Policy Controller v3 — Report

v3 implements the fixes from `V2_AUDIT_AND_V3_PLAN.md`. v2 is kept intact as the
audited-defective record (nothing deleted). Code: `v3/`. No API key in this sandbox,
so the **quality verdict still cannot run here**; the mock backend is plumbing-only
and the pilot refuses a verdict.

## Latest refactor: classical Vritti is now a SENTENCE-LEVEL COGNITIVE evaluator

Two earlier steps led here. (1) v3 first **conflated** the 5-state **dynamic/motion**
system (inertia/activation/oscillation/tension/release) with the name "vritti" — those
are **not** the classical Patañjali vrittis. (2) The two were then split, but
`classical_vritti` was still a **phonological `derived_bridge`** (bridged from
dynamic_state + valence + aspect). That was *unfaithful*: classical vrittis are **modes
of cognition**, so they must be read from what the sentence **asserts**, not from its
sound. This refactor makes `classical_vritti` a **sentence-level cognitive evaluation
of the draft answer's meaning** (`cognitive_evaluator.py`). The two fields now come
from **two genuinely different sources**:

| field | values | source | policy family | axis |
|---|---|---|---|---|
| `dynamic_state` | inertia/activation/oscillation/tension/release | **canonical** `vritti_mapper.VrittiType`, **phoneme/PSE-driven** | **delivery/energy** | `delivery_pace` |
| `classical_vritti.primary` | pramana / viparyaya / vikalpa | **sentence-level rule** (`sentence_semantic_rule_v1`) on the draft's **meaning** | **cognitive/epistemic** | `epistemic_stance` |
| `classical_vritti.nidra` | `bool` | same evaluator — low-info / evasive | **cognitive** | `clarification_policy` |
| `classical_vritti.smrti` | `bool` | same evaluator — memory/prior-context reference | **cognitive** | `memory_policy` |

The 3+2 representation (`primary` + the `nidra`/`smrti` flags) uses the **canonical
schema names** `presentation.signals.VrittiDistribution`
(pramana/viparyaya/vikalpa/smrti/nidra), pinned by `test_classical_uses_canonical_schema_names`.

**Provenance honesty:** provenance is now **`sentence_semantic_rule_v1`** (a rule-based
reading of the draft), **not** `phonological_bridge` and **not** `canonical` — we do not
pretend a rule evaluator is the neural Sovereign `chitta_vritti` computation. If an LLM
later does this evaluation, the provenance becomes `llm_judge_vritti`. The
`shuffled`/`relabeled` controls still test whether the *specific* cognitive labels add
anything. **Only the API quality run can decide whether the cognitive signal improves
final answers.**

Proof (offline): `cli check` → all **9** policy-driving fields wired;
`field_influence_by_family` proves the **four headline signals hit their distinct
axes** — `classical_primary → epistemic_stance`, `nidra_flag → clarification_policy`,
`smrti_flag → memory_policy` (all cognitive), and `dynamic_state → delivery_pace`
(delivery). Because the benchmark prompts are **questions**, the evaluator reads
mostly `pramana`/`nidra` on them and rarely `smrti`; reachability of **every**
cognitive state (primary 3/3, nidra T/F, smrti T/F) is proven on crafted **ANSWER
probes** (`evaluator_reachability`), surfaced by `cli coverage`. Regression tests pin
the separation (`test_classical_vritti_is_sentence_level_not_phonological`,
`test_evaluator_detects_each_cognitive_state`,
`test_three_cognitive_signals_hit_their_axes_and_dynamic_hits_delivery`,
`test_classical_uses_canonical_schema_names`).

## First real run (Mistral) + measurement-validity fix

The first real run (`mistral-small`, seed 0, n=36) produced a **preliminary negative
result and exposed a measurement defect**:

- **Negative direction:** on the absolute 1-5 rubric, `symbolu` (mean 4.809) was the
  **lowest of all refinement arms** and beat **none** of the controls — including
  `generic_refine` (4.827), `nl_policy` (4.830), and crucially `relabeled_symbolu`
  (4.827, i.e. random label scrambles scored *higher*). This matches the
  pre-registered expectation that the specific ontology adds nothing.
- **But the measurement was invalid:** every arm scored 4.68-4.86/5 and
  `prefer_final ≈ 1.0` everywhere — a **ceiling effect**. A judge that rates
  everything ~4.8 cannot detect a small effect in *either* direction, so the rubric
  result cannot even confidently establish a *tie*, only rule out a *large* win.

**Fix — pairwise A/B eval** (`cli pairwise`, `judge.judge_pairwise`): forced choice
between `symbolu` and each control on the same prompt, **position-debiased** (both
orders judged and averaged so order bias cancels), reported as a preference margin in
[-1,+1] with 95% CIs and W/L/T counts. A **judge validity gate**
(`judge_discriminates`) requires the judge to prefer a correct answer over an evasive
one (margin > 0.5); if it fails, the verdict is declared **invalid** rather than
reported. Position-debias and gate are pinned by tests
(`test_pairwise_judge_cancels_position_bias`,
`test_pairwise_validity_gate_detects_content_aware_judge`). **The pairwise verdict
supersedes the rubric verdict**; the rubric path is kept as a (saturated) diagnostic.

## Gate-valid verdict (Mistral generates, Anthropic judges, n=36)

With the independent Anthropic judge the **validity gate PASSED (margin +1.00)** — so
these numbers are trustworthy (unlike the saturated rubric, which crushed every arm to
~4.8/5 *even with Anthropic as the rubric judge*, confirming the ceiling is intrinsic
to absolute scoring). Position-debiased pairwise preference margins in [-1,+1]:

| symbolu vs | margin ±95% CI | W/L/T | verdict |
|---|---|---|---|
| draft_only | +0.181 ±0.244 | 15/8/13 | tie (ns) |
| generic_refine | −0.083 ±0.263 | 12/17/7 | tie (ns) |
| nl_policy | +0.042 ±0.263 | 13/12/11 | tie (ns) |
| sentiment_critic | +0.028 ±0.273 | 14/15/7 | tie (ns) |
| random_policy | +0.125 ±0.274 | 15/11/10 | tie (ns) |
| shuffled_symbolu | −0.069 ±0.244 | 11/14/11 | tie (ns) |
| **relabeled_symbolu** | **+0.111 ±0.207** | 12/7/17 | **tie (ns) — ontology not shown to matter** |

`symbolu` beats **no** control; every CI includes 0. It is not reliably better than
even the **raw draft**, is if anything slightly worse than plain `generic_refine`, and
ties its own **label-scrambled** version — the decisive ontology test.

## BUT the null is confounded: the translator destroys the ontology (offline audit)

Before concluding "Symbol-U has no merit," we audited whether the experiment actually
*preserved* the ontology's information, or whether `translate()` collapsed it into a
few generic English instructions. The audit (`cli bottleneck`,
`pilot.bottleneck_report`, pinned by `test_bottleneck_audit_quantifies_information_collapse`)
is decisive — **it collapsed it**:

| measure | value | meaning |
|---|---|---|
| distinct full states → distinct policies | 36 → **24** | a third of prompts yield an identical policy |
| total policy entropy | **4.38 bits** (max 5.17) | the whole ontology compressed to <4.4 bits of canned English |
| `memory_policy`, `clarity` entropy | **0 bits** | constant — carry no information at all |
| argmax top1–top2 gap (dynamic, kosha) | **0.10** | `translate()` keeps only the argmax of each distribution, dropping near-ties — the distribution *shape* (the actual content of a vritti/guna/kosha vector) never reaches the prompt |
| relabel axis-change fraction | **0.34** | scrambling the ontology labels changes only 34% of axes → **66% of every prompt is byte-identical to its label-scrambled version** |
| overlap with a FIXED generic policy | **0.54** | >half of every "Symbol-U" prompt matches a hand-written generic policy that uses no ontology |

`translate()` reads only argmaxes + two thresholds and renders generic phrases from
lookups of size ≤5. Under that bottleneck, a tie vs `relabeled_symbolu` and `nl_policy`
is **near-inevitable by construction** — there is barely any ontology-specific signal
left in the prompt for *any* judge to detect.

## Corrected conclusion

**This experiment is not yet a fair test of Symbol-U.** The trustworthy (gate-valid)
finding is about the **translator**, not the ontology: the `state → policy` step
discards most of the Symbol-U information (distributions → argmax, continuous →
2–3 buckets, everything → generic English) before the LLM sees it, so the controller's
prompts are mostly indistinguishable from generic / label-scrambled ones, and they
tie. We can say the *current controller* adds nothing over generic self-refinement; we
**cannot** say the *ontology* is meritless — the design lacks the fidelity to test that
claim. A genuine test requires a higher-fidelity translator (v4) that verbalizes the
full distributions and continuous signals so that scrambling labels would change far
more than 34% of the prompt.

## What was fixed from v2 (each defect → resolution, verified)

| v2 defect | v3 resolution | verification |
|---|---|---|
| **D1** 6/8 state fields inert | every **policy-driving** variable maps to a **distinct** axis; a **field-influence self-check** fails if any is inert | `cli check` → all **9** OK; `test_every_policy_driving_var_influences_policy` |
| **D2** Aspect never computed | `aspect_balance` computed via `varna_lens → phase4a.lookup` | `test_full_state_includes_aspect` |
| **D3** sattva unreachable | Vritti→Guna remap (sattva ← RELEASE+OSCILLATION); all 3 reachable | `test_sattva_is_reachable`, `test_tone_all_three_reachable` |
| **D4** dead branches (resonance `<0.5`, constant clarity) | resonance threshold recalibrated to real range; caution thresholds calibrated to the aspect_balance range; clarity declared a **fixed default, not claimed state-driven** | `test_no_dead_caution_branch` |
| **D6** structural used prompt-states, quality used draft-states | quality path uses **draft-states**; structural note documents prompt-state stand-in | code `run_quality` |
| **D7** silent fallbacks | `_valence`/`_aspect` failures are **counted in `state.warnings`**; judge-zero responses counted as `judge_failures` | `test_state_warnings_surface_not_silent` |
| **D8** relabel permuted only guna | relabel permutes **guna + kosha + valence** (every consumed category) | `test_relabel_permutes_all_consumed_categories` |

Policy wiring (each Symbol-U variable → one axis): `guna→tone`,
`dynamic_state→delivery_pace`, `classical_primary→epistemic_stance`,
`nidra_flag→clarification_policy`, `smrti_flag→memory_policy`,
`kosha→reasoning_style`, `aspect_balance→caution`, `guna_resonance→uncertainty`,
`valence→speculation_reduction` — **9 policy-driving signals** (the classical
evaluator now contributes **three** independent cognitive axes). `pse_meaning/
pse_resonance/kosha_resonance/valence_sign` are explicitly **diagnostic-only** (kept
in state, not claimed to drive policy) — honesty about claim-vs-wiring, the central
v2 failure.

## Structural results (real, offline)

- **Field-influence self-check: ALL 9 PASS** (incl. the 3 cognitive signals + dynamic).
- **By-family separation PASS:** primary→epistemic_stance, nidra→clarification_policy,
  smrti→memory_policy, dynamic→delivery_pace.
- **Distinct Symbol-U policies: ≥6** across the 36 prompts (v2 produced only 4).
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
python -m symbolu_neural.internal_policy_controller.v3.cli check      # gate: all 9 must pass
python -m symbolu_neural.internal_policy_controller.v3.cli coverage   # signals/axes + evaluator reachability
python -m symbolu_neural.internal_policy_controller.v3.cli bottleneck # translator info-preservation audit
python -m symbolu_neural.internal_policy_controller.v3.cli state      # inspect state+policy
export MISTRAL_API_KEY=...    # generator;  export ANTHROPIC_API_KEY=... for an independent judge

# PRIMARY measure — pairwise A/B, gate-validated, independent judge:
python -m symbolu_neural.internal_policy_controller.v3.cli pairwise \
    --backend mistral --judge-backend anthropic --seeds 1
# rubric path (kept as a SATURATED diagnostic only — do not use for the verdict):
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
**Signal-coverage audit** (`cli coverage`, offline): all **9** policy-driving variables
are wired & influence the policy; value-coverage on the 36 prompt-states is **full
for guna(3/3), valence(3/3)**, the **primary cognitive mode (3/3)** and the
**nidra flag (T/F)**, plus the **tone/caution/speculation** axes, with continuous
`guna_resonance` spanning 0.41–1.0 and `aspect_balance` 0.79–1.0. Gaps and how they
are handled honestly: `dynamic_state_top` and `kosha_top` are **4/5** — the
`RELEASE`→`anandamaya`→"holistic" value is **structurally near-unreachable** on natural
text (a property of the phonological vritti mapper, **not** a wiring defect). The
`smrti` flag and `memory_policy` axis read only **False** on the prompt set **because
the prompts are questions, not memory-referencing answers** — so reachability of
`smrti=True` (and every cognitive state) is proven on crafted **ANSWER probes**,
reported as `evaluator_reachability` (primary={pramana,viparyaya,vikalpa},
nidra={T,F}, smrti={T,F}). Forcing these via prompt selection would be dishonest; the
real quality run uses **draft**-answer states × seeds, which broadens coverage beyond
this question-prompt proxy. A regression test (`test_signal_coverage_audit`) pins this
audited coverage and the evaluator reachability.

## Final answer (corrected after the gate-valid run + bottleneck audit)

1. **The gate-passing null result is valid — for the v3 translator.** With an
   independent Anthropic judge that passed the validity gate (+1.00), the v3
   controller ties every control (all 95% CIs include 0), including its own
   label-scrambled version. As a statement about *this controller*, that is trustworthy:
   the v3 `state → policy` translator produces no measurable answer-quality gain over
   generic self-refinement or a random-relabeled baseline.
2. **It does not refute Symbol-U itself.** The offline `bottleneck` audit shows the
   translator compresses the rich ontology into **4.38 bits** of generic English
   (distributions → argmax, continuous → 2–3 buckets), so **66%** of every Symbol-U
   prompt is identical to its label-scrambled version and **54%** matches a fixed
   generic policy. With so little ontology-specific signal in the prompt, a tie vs
   `relabeled`/`nl_policy` is near-inevitable by construction — the result is about
   the encoding, not the ontology.
3. **The translator bottleneck is the main limitation**, and the next research move is
   **v4: test Symbol-U with less compression** — a high-fidelity translator that
   preserves the full distributions, top-2/3 state probabilities, and continuous
   resonance/aspect values, producing richer ontology-specific policy such that
   scrambling labels changes far more than 34% of the prompt. Only then does a
   win-or-lose verdict speak to Symbol-U's merit rather than to a lossy encoding of it.

**v4 is now built** (`v4/`, see `v4/README.md`). It preserves the full distributions
(top-k components with probabilities + raw names) and continuous resonance/aspect/sign
values. Offline fidelity audit (`cli_v4 bottleneck`): distinct prompts 24→**36**,
divergence-from-generic 12%→**60%** (~5× less generic — the bottleneck loosening),
relabel field-divergence 34%→**43%**, relabel token-divergence 10%→**21%**. Relabel
divergence is honestly capped (~30% of the policy is continuous-magnitude-driven and
correctly label-invariant). Re-run the gate-valid pairwise test with
`v4.cli_v4 pairwise --backend mistral --judge-backend anthropic` for a verdict that
speaks to the ontology rather than to its encoding.
