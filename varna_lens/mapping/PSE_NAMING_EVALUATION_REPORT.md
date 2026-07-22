# PSE Symbolic Profile — Naming Capability Evaluation

## 1. Executive summary — does PSE improve naming?

**Not demonstrated. On the measured data, there is _no measurable evidence_ of a production naming
benefit — and a real, measured cost.**

The research question ("does the canonical Symbolic Profile improve naming quality?") can only be
answered by generating candidate names per arm and blind-judging their quality. Both steps require a
live LLM. **No API key or model is reachable in this environment**, so the outcome metrics (candidate
quality, explanation quality, portfolio consistency of generated names) were **not run and were not
fabricated**. What *is* measurable deterministically was measured in full:

* Injecting the Symbolic Profile (Arm B) **multiplies prompt size ~6.8×** vs the baseline (72 → 492
  tokens mean; +420 tokens/prompt, 95% CI [385, 456]). This is a definite recurring cost.
* The profile is **fully deterministic** and its injected payload is **symbolically honest** (0
  decode-claim phrases, 0 raw decode tokens) — genuine properties, but neither is a naming-quality
  benefit.
* A minimal summary (Arm D) delivers the varṇa identity + dominant poles at **~2.5× baseline (183
  tokens)** — 63% cheaper than the full profile — so *if* symbolic conditioning ever proves useful,
  most of the full profile's token cost (the binding + liberating pole prose, ~318 of ~420 tokens)
  is not obviously necessary.

Under the task's stated standard — *assume no benefit until evidence demonstrates otherwise; the burden
of proof is on PSE* — the burden is **unmet**: PSE adds cost with no demonstrated quality improvement.
The evaluation harness (corpus, four arms, ablations, blinded LLM judging adapter) is delivered and will
produce the outcome evidence the moment a model is available; the verdict should be revisited then.

## 2. Methodology

* **Dataset** (`tools/naming_eval/corpus.py`, 26 frozen items): 10 brand industries (AI, pharma,
  fintech, consumer electronics, education, enterprise, healthcare, automotive, gaming, industrial);
  3 product tasks (premium/short/multilingual/required-suffix); 4 agent names (support, finance,
  medical, coding); 2 portfolio tasks (rename siblings, name a family); 7 difficult cases
  (similar-sounding, multilingual ambiguity, **Sanskrit-origin** `śānti`, **conjunct-kṣ** `kṣamā`/`rakṣā`,
  invented, competing feelings). Each item carries a brief, constraints, and a `seed_concept` a Symbolic
  Profile is built from.
* **Arms** (`tools/naming_eval/arms.py`) — identical wrapper/brief/constraints; only the conditioning
  slot differs (parity):
  * **A Baseline** — brief + constraints only.
  * **B Symbolic Profile** — A + the canonical profile (varṇa decomposition, binding & liberating pole
    text, trajectory, provenance), deterministic data, no explanation.
  * **C Random symbolic control** — A + a **real profile from a _different_ seed**, deterministically
    chosen for the closest block length (isolates "structured text of similar size" from real content).
  * **D Simplified** — A + varṇas + dominant poles only (no trajectory, no structure).
* **Judges** — none available (no human panel; no reachable LLM). A pluggable, multi-model, **blinded**
  judging adapter (`tools/naming_eval/judge.py`) is provided; it returns an explicit `LLM_UNAVAILABLE`
  sentinel rather than inventing scores.
* **Metrics** — deterministic (token cost, determinism, injected honesty, arm distinctness, random-
  control parity, ablation field costs) run now; outcome metrics gated on an LLM.
* **Randomization** — `blind_shuffle` maps each arm's output to opaque `opt_N` labels in a salt-derived
  order so judges never see arm identity or whether symbolic info was used.

## 3. Results table

| Metric | A Baseline | B Profile | C Random | D Minimal |
|---|--:|--:|--:|--:|
| Prompt tokens (mean) | 72 | **492** | 495 | 183 |
| Prompt tokens (stdev / range) | 5 / 66–89 | 92 / 319–676 | 90 / 359–669 | 12 / 160–212 |
| Prompt growth over A (mean tok) | — | **+420** | +423 | +111 |
| Determinism (same input→same output) | ✓ | ✓ | ✓ | ✓ |
| Injected decode-claim phrases (total) | 0 | **0** | 0 | 0 |
| Distinct from other arms | ✓ | ✓ | ✓ | ✓ |
| Candidate quality (memorability, fit, …) | — | — | — | — |
| Explanation quality | — | — | — | — |
| Portfolio consistency | — | — | — | — |

`—` in the bottom three rows = **LLM_UNAVAILABLE** (requires generation + blinded judging; not measured,
not fabricated). Random-control length parity is tight (mean |B−C| = 35 chars over ~2 000-char blocks),
so Arm C is a valid "same-size structured text" control.

## 4. Statistical analysis (deterministic metrics only)

* **Prompt growth B over A:** mean **+420.5 tokens**, stdev 39, 95% CI **[385.1, 455.9]**, range
  [250, 592]. A large, consistent cost across all 26 items.
* **Prompt growth D over A:** mean **+111.1 tokens** — the minimal summary carries the varṇa identity at
  ~26% of the full profile's added cost.
* **Effect sizes / paired comparisons / variance on _quality_:** not computable — the outcome variable
  requires an LLM. The harness computes per-arm rubric means, paired B−A / B−C / B−D deltas, and effect
  sizes automatically once a model is present.

## 5. Ablation report — which profile components cost what

Mean token cost of removing each field from Arm B (`tools/naming_eval/naming_eval_results.json`):

| Removed field | Mean tokens saved | Share of profile payload |
|---|--:|--:|
| liberating poles | 165.3 | ~39% |
| binding poles | 152.7 | ~36% |
| trajectory | 45.3 | ~11% |
| provenance | 30.7 | ~7% |
| symbolic ordering (reversed) | 0 | 0% (reordering changes no tokens) |

**The two pole lists dominate the payload (~75%).** Which fields contribute *value* cannot be
determined without the LLM outcome pass — but the ablation arms are wired and will isolate it. Note that
"symbolic ordering" has zero token cost, so any value it carries (if any) would show only in the quality
metrics.

## 6. Failure analysis

Help / hurt / no-effect on *naming outcomes* cannot be attributed without generation + judging. What the
deterministic pass shows: the **random-symbolic control (C) is nearly identical in size to the real
profile (B)** — so the design can cleanly separate "real symbolic content helped" from "adding ~420
tokens of structured text helped." If, when judged, B ≈ C, any apparent benefit is *structured-text
padding*, not the symbolic content. The Sanskrit-origin / conjunct-kṣ items (`śānti`, `kṣamā`, `rakṣā`)
build valid profiles (parser + B1.12 mapping exercised end-to-end), so no case failed to produce an arm.

## 7. Honest limitations

* **No LLM in this environment** → the core outcome question is unanswered by measured data; only
  cost/determinism/payload-honesty are measured.
* **No human judges**; the provided judging is LLM-based and, when run, must report cross-model
  disagreement and must **never** be claimed to equal human validation.
* **Token counts are heuristic** (~4 chars/token); absolute counts may shift with a real tokenizer, but
  the ~6.8× B/A ratio and B≈C parity are robust to that.
* **Single seed per item**; a fuller study would vary seeds and briefs and run multiple judges/models
  for confidence intervals on quality.
* **Injected-honesty is measured on the _input_ payload** (0 decode-claims), not on generated
  explanations — output honesty needs the LLM pass.

## 8. Final verdict

**No measurable evidence** for production benefit (from this environment).

Justification, entirely from measured data: the only quantities measurable without an LLM are cost
(Arm B ≈ 6.8× baseline prompt tokens, +420 tok mean), determinism (holds), and injected-payload honesty
(clean). None of these is a naming-quality improvement; the quality outcome was not measurable here and
was not fabricated. Per the burden-of-proof standard, an undemonstrated benefit against a definite cost
yields **no measurable evidence** of value. This is **not** a claim that PSE has no value — it is that
value was not demonstrated. The smallest justified next step, when an LLM is available, is to run the
delivered harness (Arms A–D + ablations, blinded multi-model judging) and re-decide; the ablation
already flags that the ~318-token pole payload is where the cost concentrates, and Arm D shows a 63%-
cheaper alternative to test first.

### Deliverables
`tools/naming_eval/`: `corpus.py` (26-item frozen corpus), `arms.py` (A/B/C/D + 5 ablations, frozen
runtime, read-only), `judge.py` (blinded multi-model adapter; UNAVAILABLE-safe), `run_eval.py`
(deterministic metrics + gated outcome pipeline), `test_naming_eval.py` (9/9), `naming_eval_results.json`
(measured data), and this report. No production runtime was modified.
