# Internal Policy Controller v2 — Faithful Redo

**Final question:** *When implemented properly, does Symbol-U draft→policy→final
control outperform generic self-refinement, sentiment/style critique, and the
random/shuffled/relabeled controls?*

**Answer: UNTESTED — and stated honestly as untested.** The decisive comparison
requires a real LLM (draft generation, policy-conditioned rewrite, independent
judge). **No LLM API key is available in this sandbox** (`api.anthropic.com` /
`api.mistral.ai` need keys that are absent; the session token is not repurposable),
so the quality verdict **cannot be produced here.** What v2 *does* deliver, and
what v1 did not: a faithful, runnable harness, plus a **real offline structural
result** — the controller now computes the full Symbol-U state and produces
genuine, ontology-label-dependent policies (v1's relabel control was a tautology;
v2's is not). No scientific quality claim is made from the mock run.

Code: `symbolu_neural/internal_policy_controller/v2/` (v1 left intact, not deleted).

---

## 1. What was fixed from v1 (mapped to the forensic audit)

| v1 defect (from `IMPLEMENTATION_FORENSIC_REVIEW.md`) | v2 fix |
|---|---|
| Symbol-U = one phonological backend; **Guna/Kosha/Aspect/Resonance never computed** | `symbolu_state.py` computes the **full available state**: Vritti (canonical), Resonance/valence (canonical `varna_lens`), PSE (canonical-wrapped), Guna & Kosha **derived from Vritti by a documented mapping**, guna/kosha-resonance via the **canonical** functions. Every field carries a **provenance** tag. |
| "Policy reasoning" was a **learned 5-label classifier** | `policy.py` `translate()` is an **explicit, label-semantic** mapping state→policy over 6 axes (tone, caution, directness, clarity, uncertainty, speculation-reduction). No classifier. |
| Translation **hard-coded**, ontology semantics unused | The translation **reads the ontology labels** (guna_top, valence, resonance) and the patent-style mappings (sattva→calm/clear, rajas→direct, tamas→cautious/grounded). |
| Final answer = **regex deletion**, no LLM | `llm.py` real `anthropic`/`mistral` clients; the rewrite is an **LLM revision under the rendered policy**. (Mock only for plumbing.) |
| **Circular eval** (injector=reviser=evaluator=sentiment lexicon) | `judge.py` is an **independent LLM judge** on a 1-5 rubric + draft-vs-final preference. No keyword markers, no regex, no oracle lexicon. |
| **Oracle sentiment critic** handed the answer key | `sentiment_critic` derives a policy from valence only and is judged by the same independent judge as every arm. |
| **`relabeled == symbolu` was a linear tautology** | v2 relabel permutes the **ontology labels before translation**, which changes the policy. Measured divergence **0.583 ≠ 0** (§3). |
| Flaws were **keyword-injected**; task rigged lexical | Drafts are **LLM-written** to real prompts; problems (escalation, speculation, over/under-caution) are not keyword-detectable. |

## 2. Arms (all 8 required)

`draft_only` · `generic_refine` (LLM critiques its own draft) · `nl_policy` (fixed
style guide) · `sentiment_critic` (valence-only policy) · `random_policy` ·
`shuffled_symbolu` (policy from a *different* draft's state) · `relabeled_symbolu`
(ontology labels permuted) · `symbolu` (real translation).

## 3. Results

### 3.1 STRUCTURAL — real, offline, trustworthy

Full Symbol-U state is computed canonically for every prompt; the controller emits a
real policy. Example (prompt "explain how a transformer works"): state
`{vritti_top: OSCILLATION, guna_top: rajas, kosha_top: manomaya, guna_resonance:
0.73, valence: mixed}` → policy `{tone: direct and energetic, caution: medium,
directness: high, speculation_reduction: medium}`.

**Policy divergence vs the real Symbol-U policy** (fraction of 6 axes differing,
mean over 12 prompts):

| arm | divergence from symbolu policy |
|---|---|
| symbolu | 0.000 |
| shuffled_symbolu | 0.389 |
| sentiment_critic | 0.417 |
| relabeled_symbolu | **0.583** |
| nl_policy | 0.597 |
| random_policy | 0.681 |

**Key structural finding:** `relabeled_symbolu` diverges **0.583 > 0** — permuting
the ontology labels changes the policy on ~58% of axes. **v1's relabel was 0.000
(a basis-permutation no-op); v2's is a genuine ontology-sensitivity control.** So
the harness can now actually answer "does the specific ontology matter?" — once the
quality judge runs.

### 3.2 QUALITY — requires a real LLM (NOT run here)

With the `mock` backend the pilot **refuses to emit a verdict** ("NO QUALITY
VERDICT. Plumbing only."). The rubric metrics (clarity, directness, usefulness,
caution appropriateness, speculation reduction, escalation reduction, completeness,
meaning preservation, fluency, judge preference) are wired and produce per-arm
means + `prefer_final` rates **only on a real backend.**

## 4. What is still limited

- **No quality result in-sandbox** (no API key) — the headline question is untested.
- **Guna/Kosha are derived from Vritti**, not canonical text→guna/kosha (none exist
  in the repo). The derivation is documented and honest, but it means the "Guna"
  signal is a re-expression of Vritti, not an independent measurement. **Aspect**
  (phase4a lookup) is available but not yet pooled into the policy — a noted TODO.
- **Single LLM family / single seed** when run; the plan calls for ≥2 models and
  ≥3 seeds with CIs.
- The translation table is **hand-authored** (as any policy layer is); the
  `relabeled`/`shuffled`/`random` controls exist precisely to test whether the
  *specific* ontology, not just *a* policy, drives any quality gain.

## 5. Exact commands for the real run (RunPod / any host with API access)

```bash
export PYTHONPATH=$(pwd)

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python -m symbolu_neural.internal_policy_controller.v2.cli run --backend anthropic

# Mistral (or any OpenAI-compatible endpoint via MISTRAL_BASE_URL)
export MISTRAL_API_KEY=...
python -m symbolu_neural.internal_policy_controller.v2.cli run --backend mistral --model mistral-small-latest

# offline structural view (runs anywhere) + machinery tests
python -m symbolu_neural.internal_policy_controller.v2.cli state
python symbolu_neural/internal_policy_controller/v2/tests/test_v2.py
```

Recommended hardening for a publishable result: use a **different** model as judge
than as generator; run ≥3 seeds; add a human spot-check on ~30 (prompt, draft,
final) triples; report CIs.

**Pre-registered pass condition:** `symbolu` must beat `generic_refine` AND
`sentiment_critic` AND `nl_policy` on the judge's rubric mean / preference, AND beat
`random_policy`/`shuffled_symbolu`, AND **beat `relabeled_symbolu`** (the specific
ontology must matter). Failing any ⇒ Symbol-U adds nothing over ordinary
self-refinement / a generic policy.

## 6. Final answer

**The hypothesis remains UNTESTED for answer quality** (no API access here), and I
am not claiming a result from the mock run. v2's contribution is to make the test
**faithful and ready**: it computes the full Symbol-U state, performs an explicit
ontology-driven policy translation, rewrites with a real LLM, and judges
independently — fixing every defect the forensic audit found. The one genuine,
trustworthy result available offline is structural: **the controller now produces
real, ontology-label-dependent policies (relabel divergence 0.583), so the
ontology-sensitivity question is finally well-posed.** Run §5 on a host with an API
key to get the honest quality verdict; given all prior evidence, my pre-registered
expectation is that `symbolu` ties `generic_refine`/`nl_policy` and does **not**
beat `relabeled_symbolu` — but that is now an empirical question this harness can
actually answer, rather than one a rigged proxy pre-decided.
