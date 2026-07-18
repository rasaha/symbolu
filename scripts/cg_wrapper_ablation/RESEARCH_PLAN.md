# CG Wrapper — Generation-Quality Ablation (Research Plan, PRE-REGISTERED)

> **Track scope.** This evaluates the CG wrapper *purely as an LLM generation-quality
> modifier*. It is **not** about governance. The Trust Observable Architecture has replaced
> CG as a governance signal; this track does **not** touch trust observables, JEPA
> governance, Vritti/Guna/Kosha *governance* signals, the shadow/parity machinery, the VC
> brief, or any Phase-2 governance work. No new governance code is introduced.

> **Falsification-first.** This document is pre-registered. The eval sets, seeds, metrics, and
> kill criteria below are fixed **before** any GPU run. "No measurable benefit" / "inert" are
> valid, expected outcomes and will be reported honestly. We do not select metrics post hoc and
> do not claim success on subjective grounds.

---

## 1. Core question

Does the CG wrapper — `Bhava → ΔBhava → intent_phase → phase_adapter → gated residual on the
last hidden state → LM head` — improve generation **quality, coherence, controllability, or
task accuracy** versus the base open model, measured by **objective** metrics?

The mechanism (audited in `TASK1_AUDIT_FINDINGS.md`) is:

```
hidden            = backbone(input).hidden_states[-1]          # [B,T,D]
state             = state_projector(mean_pool(hidden))         # 32D Sovereign State
delta_bhava       = bhava_t - bhava_{t-1}                      # 12D
intent_phase      = intent_projector(delta_bhava)              # [B,H]
adapter_output    = RMSNorm(phase_adapter(intent_phase))       # [B,T,D]
adapted_hidden    = hidden + sigmoid(adapter_gate) * adapter_output
logits            = lm_head(adapted_hidden)                    # <-- generation hooks HERE
```

The wrapper changes **logits at generation time** via `adapted_hidden`. The effect size is
governed by `sigmoid(adapter_gate)` (init `sigmoid(-2) ≈ 0.12`) and the trained
`phase_adapter` output norm. If the head is untrained (zero-init final layer), the correction
is identically zero and the wrapper is inert by construction.

---

## 2. Arms (each a clean, reproducible config)

| Arm | Description | Config (`AttentionAblationConfig`) | Pre-registered expectation |
|-----|-------------|------------------------------------|----------------------------|
| **A** | Base model, no wrapper | `lm_head(hidden)` directly (`ablation = all_off` is logit-equivalent) | Reference |
| **B** | Base + CG wrapper (full) | `ablation = None` (baseline: phase+vritti+guna on) | The only arm that can show benefit |
| **C** | Wrapper, phase_adapter input disabled | `use_phase_sync=False` (intent_phase forced 0) | **May differ from A** — see note |
| **D** | Wrapper, adapter_gate forced 0 | `use_guna_bias=False` (gate ≡ 0) | **Must be logit-identical to A** |
| **E** | CSR ON vs OFF (only if CSR is in the path) | — | **N/A — CSR is not in the wrapper generation path** (see audit) |

**Pre-registered structural predictions (sanity checks, not hypotheses about benefit):**

- **D ≡ A** to within `atol=1e-4, rtol=1e-3` on logits. With `gate=0`,
  `adapted_hidden == hidden`, so `lm_head(adapted_hidden) == lm_head(hidden)`. If D ≠ A, that
  is a **hidden-coupling finding** (something other than the gated residual is moving logits).
- **C is *not* guaranteed to equal A — and under Active-CG it is the key reference.**
  `use_phase_sync=False` only zeroes the *input* to `phase_adapter`; the adapter still emits
  `phase_adapter(0)` (a trained constant/bias term) scaled by `sigmoid(gate)`. So C is the
  **static-offset arm**: the wrapper with its constant correction but no phase/Bhava dynamics.
  **B vs C is therefore the decisive comparison** — it isolates the CG-dynamic component from the
  static offset. (The 600-step activation check showed the state-projector grad collapsing, so a
  largely-static offset is a live possibility; `STATIC_OFFSET_NO_CG_DYNAMIC` is a pre-registered
  outcome, not a surprise.) We report C−A (offset size) and B−C (dynamic component) every run.
- **E is excluded.** A grep of the generation path (`mistral_wrapper.py`, `llm_adapters.py`)
  finds no CSR / Varna stage feeding logits. The script verifies this programmatically and
  records the result; if a CSR stage is ever wired in, arm E activates automatically.

---

## 3. Primary metrics (OBJECTIVE ONLY)

All metrics are objective and computed from raw generations / raw logits. No standalone
subjective "coherence" score is used; any coherence-style proxy must be paired with an
objective score and is reported only alongside it.

**Task / format metrics (per arm, aggregated over the eval set × seeds):**

1. **Exact-match accuracy** — GSM8K-style multi-step arithmetic, final-number match.
2. **Constraint satisfaction** — instruction-following / format constraints (e.g. "answer in
   one word", "list exactly 3 items", "end with DONE"): fraction of constraints satisfied.
3. **JSON validity / format adherence** — parse rate of responses required to be valid JSON
   matching a requested shape.
4. **Multi-step reasoning correctness** — same GSM8K-style set scored on the final answer
   (the multi-step subset is tagged so reasoning-only accuracy can be reported separately).
5. **Answer consistency across seeds** — mean pairwise agreement of the extracted answer over
   `N` seeds (stability of the arm).

**Logit-level diagnostics (base vs wrapper, the inert/effect discriminators):**

6. **Per-token logit KL divergence** `KL(softmax(base) || softmax(wrapper))`, averaged over
   tokens and examples (nats).
7. **Top-1 token flip rate** — fraction of positions where `argmax` differs between base and
   wrapper.

**Statistics:**

- Paired **McNemar exact test** for exact-match / constraint / JSON pass rates (paired binary
  outcomes per example, base vs wrapper).
- Paired **bootstrap 95% CI** (10,000 resamples, seed `12345`) for continuous metrics and for
  the accuracy delta point estimate.
- Significance threshold `α = 0.05`.

---

## 4. Eval sets (PRE-REGISTERED, in-repo, no download)

Embedded under `eval_sets/` so the run is fully reproducible offline. These are small,
deterministic, hand-checked sets — chosen for objective scorability, not size. They are fixed
as of this commit; no examples are added/removed after results are seen.

| File | Task | N | Scorer |
|------|------|---|--------|
| `eval_sets/gsm8k_style.jsonl` | multi-step arithmetic word problems | 30 | exact-match on final integer |
| `eval_sets/format_constraints.jsonl` | instruction-following / format | 24 | per-example constraint predicate |
| `eval_sets/json_format.jsonl` | "respond with JSON of shape X" | 16 | JSON parse + required-keys check |

**Seeds:** `[0, 1, 2, 3, 4]` (5 seeds). **Decoding:** greedy for accuracy/format/JSON
(`temperature=0`); seeds drive any tie-breaking + the cross-seed consistency metric uses
`temperature=0.7, top_p=0.9, top_k=50` (the adapter's default sampler) so agreement is
measured under stochastic decoding. Both decoding configs are fixed here.

`N_SAMPLES` (examples per set) and `SEEDS` are overridable via env for a quick smoke, but the
**reported verdict uses the full pre-registered sets and all 5 seeds**.

---

## 5. Diagnostics logged every run (Task 6)

Per arm, per example (and aggregated):

- `adapter_gate` value (and distribution if it varies across steps).
- `phase_adapter` output norm (`adapter_output_norm`).
- correction norm `‖gate·adapter_output‖`, hidden-state norm `‖hidden‖`, and their **ratio**.
- `ΔBhava` norm during generation.
- logit KL (base vs wrapper) and top-1 flip rate.
- side-by-side base vs wrapper generations (raw text, saved verbatim).

All artifacts are saved under `runs/cg_wrapper_ablation/<timestamp>/`:
`config.json`, `raw_generations.jsonl`, `per_example_scores.jsonl`, `diagnostics.jsonl`,
`summary.json`, plus the resolved `RESEARCH_PLAN` snapshot.

---

## 6. Kill criteria + decision categories (PRE-REGISTERED, numeric thresholds)

> **Update (post Active-CG).** The ORIGINAL wrapper is **structurally inert** — it cannot bootstrap
> an active gate under an LM objective on a frozen backbone (proof + math: `BOOTSTRAP_ANALYSIS.md`).
> The ablation is therefore run on a **trained Active-CG** head (gate −1.0 + N(0,1e-3) adapter,
> `--cg_bootstrap_mode active`), which *is* active. Because the wrapper is now active, the decisive
> question shifts from "does it change logits" (B vs A) to **"is any effect CG-DYNAMIC or just a
> static adapter offset"** — i.e. **B vs C**. Active ≠ useful.

**Significance** = paired McNemar exact `p < 0.05` **AND** the 95% paired-bootstrap CI of the
rate difference excludes 0. Comparisons computed every run: **B vs A**, **B vs C**, **C vs A**,
plus the B-vs-C logit separation `KL(B‖C)` / top-1 flip.

Checks (evaluated in order → one `DECISION`):

**K0 — Sanity / hidden coupling.** `max|logit_D − logit_A| > 1e-4` ⇒ gate=0 ≠ base ⇒
`INVESTIGATE_K0_HIDDEN_COUPLING`. Fix before trusting anything else.

**K1 — Inert.** For B vs A: `KL < 1e-3` **AND** `flip < 0.5%` **AND** `corr/hidden < 1e-2`
⇒ `INERT`. Expected for ORIGINAL; for a trained Active-CG head this firing means the checkpoint is
untrained/mis-loaded.

**Decision categories** (active head, K0 ok, not inert):

| Decision | Condition | Meaning / action |
|----------|-----------|------------------|
| `REGRESSION` | B **<** A significant on any task metric | wrapper **hurts** → KILL / flag retrain |
| `CG_DYNAMIC_SIGNAL` | B **>** A significant **AND** B **>** C significant | gain needs the phase/Bhava dynamics → **continue** CG research |
| `STATIC_OFFSET_NO_CG_DYNAMIC` | B moves metrics vs A (or C does) **AND** B ≈ C (not distinguishable, `KL(B‖C)`≈0) | effect is a **constant adapter offset**, not CG dynamics → park CG-dynamics claim |
| `WEAK_OBJECTIVE_GAIN` | B **>** A significant, but B-vs-C ambiguous (distinguishable yet not B>C) | weak/uncertain → more data before any claim |
| `ACTIVE_NO_EFFECT` | active, no significant task movement anywhere | logits move, metrics don't → DEPRIORITIZE |

Rules: a benefit is recorded **only** for `CG_DYNAMIC_SIGNAL` (objective, B>A and B>C). A
`STATIC_OFFSET_NO_CG_DYNAMIC` is **not** evidence for the CG mechanism even if B>A. Subjective /
coherence-only impressions never count. Any `REGRESSION` is reported with metric + effect size.

---

## 7. What requires GPU / RunPod

The CPU portion (this repo, here) covers: the audit, the pure-Python metric/stat functions,
the stub-backend equivalence + ΔBhava tests, and all plumbing. It does **not** load Mistral-7B
or a real CG checkpoint.

The **verdict requires a GPU run on RunPod** with a real base model + a *trained* CG
state-dict (the loader fails closed on untrained heads). The scripts in this directory
(`setup.sh`, `smoke_generate.py`, `run_ablation.py`, `metrics_report.py`) drive that run and
write `summary.json`, which is then transcribed into `RESULTS_TEMPLATE.md`.

---

## 8. Reproducibility

- Seeds pinned (`[0..4]`, bootstrap seed `12345`).
- Full config + plan snapshot saved per run.
- Raw generations, per-example scores, and diagnostics saved verbatim.
- Arms differ **only** by `AttentionAblationConfig`; the backbone + checkpoint are identical
  across arms within a run.
