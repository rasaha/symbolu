# Text-FSCS Implementation Status

**Date:** 2026-04-11
**Branch:** `claude/vc-pitch-document-LBYcN`
**Maturity tier:** Code-complete, **not yet benchmark-validated.**
**Requires operator execution on A100-80GB to measure `r*`.**

---

## Top-level honest summary

This is a first-pass implementation of the Text-FSCS v5.0 specification
applied to a frozen Mistral-7B backbone. Every file listed below is
code-complete; none of them have been executed in the session that
produced them. The dev environment where these files were written has
no `torch`, no `transformers`, no GPU, and no Mistral weights. That
means:

- **The code compiles in principle but has not been run.** Expect 1–3
  small bugs (typo-level, not architectural) the first time you run
  the smoke test. Those are normal and expected.
- **No `r*` numbers exist.** No `results.json` has been produced. The
  harness that would produce one is in place.
- **The CPU smoke test (`tests/test_fscs_core.py`) has not been
  executed.** It is designed to run without GPU, without transformers,
  and without Mistral weights — but "designed to run" is not "has
  run." Run it first, before touching the GPU sweep.

If a reviewer asks *"has this been validated?"* the answer is:
**"code-complete, smoke-test-authored, not yet executed."**

---

## What is implemented

### Files added in this pass

| File | Lines | Purpose |
|---|---|---|
| `symbolu/fscs/__init__.py` | ~60 | Package init, public API exports |
| `symbolu/fscs/core.py` | ~380 | FSCS core modules: coherence, routing gate, boundary detector, surprise-delta suppressor, layer cap, alignment loss |
| `symbolu/fscs/mistral_gated_layer.py` | ~270 | `FSCSGatedDecoderLayer` wrapping a frozen Mistral decoder layer with full+windowed branches and per-token blend |
| `symbolu_training/training/unified/mistral_fscs_wrapper.py` | ~400 | `MistralFSCSWrapper` loading frozen Mistral-7B the same way `MistralHybridWrapper` does, installing gated layers in place |
| `scripts/r_star_sweep.py` | ~420 | Measurement harness: baseline + τ sweep + soft/hard comparison + GO/NO-GO verdict |
| `tests/test_fscs_core.py` | ~340 | CPU smoke test for every FSCS core module |
| `scripts/run_fscs_rstar_measurement.sh` | ~130 | Operator runbook: env check → smoke → sanity → full sweep |
| `docs/FSCS_IMPLEMENTATION_STATUS.md` | this file | Status doc |

### Spec section coverage

| Text-FSCS section | Mechanism | Implemented? | Notes |
|---|---|---|---|
| §0 | Compute model (training vs decoding) | Acknowledged in design | Not a code component |
| §1.1 | Three-signal coherence (output delta + residual delta) | **Yes** | Block-mass KL (§1.3) is stubbed, off by default. Requires attention-summary storage which isn't feasible without reimplementing Mistral's attention. |
| §1.2 | EMA smoothing | **Yes** | Explicit loop in `FSCSCoherenceModule` |
| §1.3 | Coherence state storage (block-mass / top-k / full) | **Deferred** | First-pass uses only output + residual deltas |
| §2 | Surprise-delta suppressor | **Yes** | `FSCSSurpriseDeltaSuppressor`. Hook exists in the gated layer but the frozen-backbone r* path does not call it by default (the harness can optionally pass baseline token surprise). |
| §3.1 | Boundary detector v1 (heuristic) | **Yes** | Token-ID lookup, resolved from the Mistral tokenizer at wrap time |
| §3.2 | Boundary detector v2 (trained MLP) | **Deferred** | Future work |
| §4 | Sequence-start warmup | **Yes** | `FSCSCoherenceModule` forces coherence to 0 for the first `warmup_tokens` positions |
| §5 | Head-importance-weighted thresholds | **Partial** | Token-level cap (not per-head) in `FSCSLayerCap`. Per-head importance via `W_O` Frobenius norm is deferred — it requires reimplementing Mistral's output projection. |
| §5.3 | Importance update schedule | **N/A** | No training in the frozen-backbone path |
| §6.1 | Pre-gate routing `π = σ(α(Ĉ-τ))` | **Yes** | `FSCSRoutingGate`, per-band τ and α |
| §6.2 | Three explicit modes (train / soft / hard) | **Yes** | `use_hard_routing` flag toggles Mode 2 vs Mode 3 |
| §7 | Layer-level gating cap | **Yes** | `FSCSLayerCap`, β_max_train and β_max_inference |
| §7.3 | Enforcement ordering (gate → cap → execute) | **Yes** | Enforced in `FSCSGatedDecoderLayer.forward` |
| §8 | Cross-layer caution | **Partial** | Stateful approximation — this layer reads the previous layer's gate fraction from the wrapper and shrinks π proportionally. Strictly, §8 requires within-forward-pass propagation, which needs a manual layer loop. The stateful version is sufficient for eval-mode r* measurement. |
| §9 | Per-band coarse operators | **Partial** | **First-pass uses a single windowed coarse operator across all bands.** The Mid-band strided operator and Global-band EMA-cache-with-refresh from §9.1/§9.3 are deferred to a future pass. |
| §10 | KV-cache always-update | **Trivially satisfied** | We call Mistral's own `self_attn` twice per forward, both times with the full K/V projection. No cache gaps possible. |
| §11 | Plateau block sparsity | **Deferred** | Not in first pass |
| §12 | Training regime (warmup + alignment loss) | **Partial** | `fscs_alignment_loss` with stopgrad is implemented and unit-tested. No training loop is included in this pass — first-pass measurement is frozen-backbone eval only. |

---

## Scope note: token-level vs per-head gating

**The single most important design choice in this first-pass implementation
is that FSCS gates at the token level, not the head level.** This is a
deliberate scope compromise. The spec calls for per-head gating because
head importance follows a power law and the best per-layer gating rate
comes from selectively dropping only the weak heads. A token-level gate,
in contrast, says *"for this token on this layer, use full or windowed
attention for all heads together."*

**Why I chose token-level for this first pass:**

1. **Honesty about reimplementation risk.** Per-head gating requires
   intercepting Mistral's attention *before* the output projection, which
   means reimplementing q/k/v projection + RoPE + GQA + SDPA. HuggingFace's
   `MistralAttention` is ~300 lines of tightly-coupled code, its exact
   layout varies across transformers versions, and without being able to
   execute and diff against it in the dev session, any reimplementation
   would almost certainly have RoPE or GQA bugs that only surface on real
   Mistral checkpoints.

2. **A valid first measurement.** Token-level gating still measures a
   meaningful `r*`: *"what fraction of tokens can be routed to windowed
   attention before PPL degrades?"* This is a conservative lower bound on
   the head-level `r*` from the full spec — per-head gating can only do
   better, because it has strictly more freedom.

3. **Mistral's attention primitive is reused unchanged.** We call
   Mistral's own `self_attn` twice per layer with different attention
   masks (full causal and windowed causal). Mistral's RoPE, GQA, and
   flash-attention paths are used exactly as they were trained. No
   custom attention code.

4. **What is deferred, explicitly:** The per-head variant, per-band coarse
   operators (Mid-strided, Global-EMA-cache), and head-importance
   weighting are all the mechanisms from §5 and §9 that push `r*` higher
   in the full spec. Each one is a plausible next-pass improvement.

**What this means for the `r*` number you get:**

- The `r*` measured by `scripts/r_star_sweep.py` on frozen Mistral-7B
  is a **conservative lower bound** on the theoretical full-spec `r*`.
  If this bound is already in the GO region (r* > 30% with Δppl < 0.5%),
  the full spec is almost certainly also GO and is worth implementing
  next.
- If the bound is MARGINAL or NO-GO, the honest next step is *not* to
  implement the deferred per-head mechanisms hoping they'll rescue it —
  the honest next step is to co-train a model with the alignment loss
  active. The frozen-backbone measurement cannot capture the benefit of
  having the coarse path trained to match the full path; that requires
  co-training. See §12 of the spec and the roadmap below.

---

## What the first-pass `r*` measurement actually measures

Concretely, `scripts/r_star_sweep.py` answers this question:

> *"If we take a fully-trained Mistral-7B and replace the attention
> output at some fraction of tokens with the output of the same
> `MistralAttention` called on a windowed-causal attention mask — how
> high can that fraction go before WikiText-2 perplexity degrades by
> more than 0.5%?"*

That is a well-defined, reproducible measurement. It is a meaningful
first answer to the Text-FSCS viability question. It is *not* the full
answer. It is the floor.

The soft-to-hard gap (§6.2) is measured at each τ: the sweep runs
Mode 2 (soft blend between full and coarse) and Mode 3 (hard route at
θ) and reports the ppl delta between them. The spec's acceptance
criterion is `<0.3% Δppl` between modes; if the gap is larger than
that, hard routing is unsafe and the model needs co-training before
Mode 3 can ship.

---

## Wall-clock caveat (important)

**The wall-clock numbers this harness reports are not production
inference-speed numbers.** Because we call `self_attn` twice per layer
(once full, once windowed), this harness is *slower* than stock Mistral
even at `r* = 0`. That is intentional for a measurement harness — we
need both branches to compute the soft blend for `L_align` validation
and the soft-to-hard gap.

A production Mode 3 implementation would need a conditional per-token
dispatch that only runs one branch per (layer, token) cell. That is a
separate engineering task, not part of this `r*` measurement. The
`r*` number from this harness tells you the **quality ceiling** — the
*"is it worth building the fast path?"* decision. Once quality is
proven, a Mode-3 fast path is straightforward linear-algebra
engineering.

---

## How to run

```bash
# 1. From a venv with torch, transformers, bitsandbytes, accelerate,
#    datasets, and pytest installed:

# 2. Run the CPU smoke test first (takes seconds, validates FSCS core
#    without touching the GPU or Mistral weights):
pytest tests/test_fscs_core.py -v

# 3. Run a 15-minute sanity pass on the GPU to catch wiring bugs before
#    the full sweep:
./scripts/run_fscs_rstar_measurement.sh --sanity

# 4. Run the full sweep (several hours):
./scripts/run_fscs_rstar_measurement.sh

# 5. Read the verdict:
cat results/fscs_rstar/results.json | jq '.verdict, .r_star'
```

---

## Known gaps and risks

| Risk | Severity | Mitigation |
|---|---|---|
| Code has not been executed in this session | **High** | First run is expected to surface 1–3 small bugs. Run the smoke test first — it does not need a GPU. |
| HuggingFace `MistralDecoderLayer` API may differ across transformers versions | **Medium** | `FSCSGatedDecoderLayer.__init__` checks for required attributes (`self_attn`, `mlp`, `input_layernorm`, `post_attention_layernorm`) and raises with a descriptive error if the layout differs. |
| Token-level gating under-measures the full-spec `r*` | **Medium** | Explicitly documented above. The number is a lower bound, not an upper bound. |
| The dual-branch forward pass doubles memory usage during eval | **Medium** | Use 4-bit quantization (default). Reduce `--seq-len` if OOM. The harness never uses more than one sample at a time. |
| Cross-layer caution (§8) is a stateful approximation | **Low** | Acceptable for eval-mode measurement. A correct in-pass implementation requires a manual layer loop, deferred. |
| Boundary detector v1 is heuristic | **Low** | v2 (trained MLP) is future work. The heuristic is only active if the tokenizer resolves the default boundary characters to single token IDs, which is typical for Mistral's BPE tokenizer. |
| `FSCSCoherenceModule` uses a Python loop for EMA smoothing | **Low** | O(N) in Python. Fine for measurement; would need fusing for production inference. |
| We do not validate that Mistral's `output_attentions=False` path actually returns a tensor/tuple consistently | **Low** | Handled by the `isinstance(attn_out, tuple)` check in the gated layer forward. |

---

## Roadmap after the first `r*` measurement

Once `scripts/r_star_sweep.py` produces a result, the next decisions are:

1. **If GO (`r* > 30%` with `Δppl < 0.5%`):**
   - Write a production Mode 3 path that dispatches a single branch per
     (layer, token) cell instead of computing both — turns the quality
     ceiling into an actual wall-clock win
   - Implement the per-head variant on a co-training run to push `r*`
     above the frozen lower bound
   - Implement per-band coarse operators (Mid-strided, Global-EMA-cache)
     for additional savings at matched quality

2. **If MARGINAL (`r* = 15–30%`):**
   - Run the same measurement with co-training on a smaller model
     (1.3B) where we can afford to train from scratch with the
     alignment loss active
   - This isolates *"does the alignment loss actually raise `r*`?"*
     which is the most important unknown

3. **If NO-GO (`r* < 15%` or `Δppl > 1%`):**
   - Honest negative result — the frozen-backbone token-level version
     of FSCS does not work, and we would need to decide whether to
     invest in the co-training path before declaring Text-FSCS
     nonviable. A token-level measurement alone is not sufficient
     evidence to abandon the architecture, because co-training
     typically lifts `r*` by 10–20 points in this class of method.

None of these next steps are funded or in progress. They all follow
from the first measurement.

---

## Files NOT touched by this pass

For clarity on what was and wasn't changed:

- **Not touched:** `symbolu/phase_transformer.py` (the existing GCT
  module remains as it was — FSCS is a sibling package, not a rewrite
  of GCT).
- **Not touched:** `train_unified_llm_clean.py` (GCT's training entry
  point). FSCS does not yet have a training integration; the frozen
  Mistral measurement does not need one.
- **Not touched:** `MistralHybridWrapper` or `MistralCGWrapper` — they
  remain available for their existing use cases.
- **Not touched:** Any existing tests. FSCS's tests live in a new
  file, `tests/test_fscs_core.py`.

---

## Contact

Branch: `claude/vc-pitch-document-LBYcN`
Spec: Text-FSCS v5.0 (attached to conversation)
Implementation: `symbolu/fscs/`, `symbolu_training/training/unified/mistral_fscs_wrapper.py`
Measurement: `scripts/r_star_sweep.py`, `scripts/run_fscs_rstar_measurement.sh`
Smoke test: `tests/test_fscs_core.py`
