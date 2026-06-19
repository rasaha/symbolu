# Task 1 — CG Wrapper Path Audit (findings)

**Scope:** the CG wrapper as a *generation-quality* modifier only. Governance paths
(trust observables, JEPA governance, Vritti/Guna/Kosha *governance*, shadow/parity) are out of
scope and were not modified. This is a read-only audit of the code paths that produce logits.

**Files audited**

- `symbolu_training/training/unified/mistral_wrapper.py` — `MistralCGWrapper` (the wrapper).
- `symbolu/agentic_framework/llm_adapters.py` — `MistralCGAdapter.call()` (the generation loop).
- `symbolu_core/phase_transformer.py` — `IntentPhaseProjector` (ΔBhava → phase).
- `symbolu_training/jepa/state_projector.py` — `SovereignStateProjector` (hidden → 32D state).
- `experiments/signal_gov/cg_checkpoint.py` — checkpoint load + fail-closed verification.
- `symbolu_training/training/conscious_generation/ablation/config.py` — `AttentionAblationConfig`.

---

## Stage → tensor it touches → load-bearing?

| Stage | Code | Input → Output tensor | Load-bearing at generation? |
|-------|------|----------------------|------------------------------|
| Backbone (frozen) | `mistral_wrapper.py:370-378` | `input_ids → hidden = hidden_states[-1]` `[B,T,D]` | Yes (base signal) |
| State projector | `compute_state_delta` `:291-334`, `state_projector(:103)` | `mean_pool(hidden)[B,D] → state[B,32]` | Indirect — feeds ΔBhava only |
| ΔBhava | `:320-332` | `bhava_t − bhava_{t-1} → delta_bhava[B,12]` | Indirect — drives intent_phase |
| Intent phase projector | `IntentPhaseProjector.forward` `phase_transformer.py:1868` | `delta_bhava[B,12] → intent_phase[B,H]`, `tanh·π` | Indirect — adapter input |
| phase_adapter | `mistral_wrapper.py:126-133, 411` | `intent_phase[B,T,H] → adapter_output[B,T,D]` | **Yes — the correction** |
| adapter_output_norm | RMSNorm `:138, 416` | `adapter_output → unit-RMS adapter_output` | Yes — scales correction |
| adapter_gate | `:144, 419-424` | scalar `sigmoid(adapter_gate) ∈ (0,1)` | **Yes — the multiplier** |
| Gated residual | `:424` | `adapted_hidden = hidden + gate·adapter_output` | **Yes — where logits change** |
| LM head (frozen) | `:447-448` | `lm_head(adapted_hidden) → logits[B,T,V]` | **Yes — generation hook** |
| Perspective synthesizer | `:428-443` | optional `_perspective_synthesizer`, **not attached by default** | Only if externally set |
| CSR / Varna | — | **absent from the wrapper logit path** | **No (not wired)** |

---

## The three questions, answered explicitly

### Q1. Does the wrapper ACTUALLY change logits at generation time? Where, exactly?

**Yes — at the LM head, via the last hidden state.** `mistral_wrapper.py:424` computes
`adapted_hidden = hidden + sigmoid(adapter_gate) * adapter_output_norm(phase_adapter(intent_phase))`
and `:448` feeds `adapted_hidden` (not the raw `hidden`) into the frozen `lm_head`. The
generation loop (`llm_adapters.py:459-466`) re-runs the **full wrapper forward** each step and
samples from `outputs['logits'][:, -1, :]` — so every generated token sees the CG-adapted
logits. The hook point is **logits, computed from the last-layer hidden state** (single layer,
the final one).

**Magnitude is conditional.** The correction is `sigmoid(adapter_gate) · ‖adapter_output‖`.
- `adapter_gate` is initialized to `-2.0 → sigmoid ≈ 0.12`.
- `phase_adapter`'s final `Linear` is **zero-initialized** (`:132-133`). **If the loaded head
  is untrained, `adapter_output ≡ 0` and the wrapper is logit-identical to base** (inert by
  construction). This is exactly what `cg_checkpoint.verify_cg_state_dict` guards: it refuses to
  run a checkpoint whose `phase_adapter` output weight L2 ≈ 0 unless `--allow-untrained-cg-head`
  is passed. So a real effect at generation time requires a **trained** head.

> Generation caveat (not a bug, but noted): the adapter loop in `llm_adapters.py` re-runs the
> whole forward on the growing sequence with **no KV cache** (`O(n²)`), and `reset_state` is
> only passed on the initial metadata pass — during the loop `prev_state` updates each step, so
> `ΔBhava` is the *step-to-step* change of the mean-pooled state over the growing prefix. This
> is the behaviour the ablation measures; the harness records `ΔBhava` norm per step.

### Q2. Does `reset_state()` make ΔBhava zero (clean "inert" baseline)?

**Partly — it zeroes ΔBhava, but that does NOT make the correction zero.**
`compute_state_delta(..., reset_state=True)` (`:315-328`) sets `delta_S` and `delta_bhava` to
`torch.zeros_like(...)`. So **ΔBhava norm == 0** after a reset. ✔ (verified by CPU test.)

**But** `reset_state` is *not* a clean inert baseline for logits, because:
`intent_phase = intent_projector(delta_bhava=0)` is **not 0** after training — `IntentPhaseProjector`
runs `Linear→GELU→Linear` then `tanh·π`; with a zero input the first layer's bias propagates, so
`intent_projector(0)` is a trained constant. Then `phase_adapter(const)` is a trained constant
correction. Therefore `reset_state=True` still injects a (constant) logit perturbation whenever
the head is trained and the gate > 0.

**The only true inert baseline is `gate == 0`** (see Q3), which forces `adapted_hidden == hidden`
exactly. Note there is no public `reset_state()` *method*; `reset_state` is a forward kwarg.

### Q3. Is there a supported way to disable phase_adapter and to force adapter_gate = 0?

**Yes — via `set_ablation_config(AttentionAblationConfig(...))`** (`:186-196`, applied in
`forward` at `:380-424`):

- **Force `adapter_gate = 0`** → `use_guna_bias=False`. `forward` then sets
  `gate = zeros(1)` (`:421-423`), so `adapted_hidden = hidden + 0 = hidden` and
  `logits = lm_head(hidden)` — **logit-identical to base**. This is arm **D** and the true
  inert switch.
- **Disable the phase signal into the adapter** → `use_phase_sync=False` → `intent_phase = 0`
  (`:401-402`). This is arm **C**. ⚠ **It is NOT a full disable of the adapter:** the adapter
  still emits `phase_adapter(0)` (trained constant), scaled by `sigmoid(gate)`. So C is expected
  to differ from A unless that constant is ~0. We measure the C−A gap as a finding.
- **Bypass the state projector** → `use_vritti_modulation=False` → `state`, `delta_S`,
  `delta_bhava` all forced to zero (`:391-395`). Combined with `use_phase_sync` this is another
  way to zero the phase signal (but again not the adapter constant).
- **All off** (`AttentionAblationConfig.all_off()`): pure base logits.

There is **no per-call kwarg** to disable just the `phase_adapter` module; control is exclusively
through `set_ablation_config`. `use_guna_bias=False` is the load-bearing "off" switch.

---

## Checkpoint loading path (weights / where / dtype / device)

- **Backbone**: loaded fresh from `model_name` (default `mistralai/Mistral-7B-v0.3`) via
  `AutoModelForCausalLM.from_pretrained`, `dtype=bfloat16`, `device_map="auto"`,
  `output_hidden_states=True`, attn = flash-attn-2 if available else sdpa; optional 4/8-bit
  bitsandbytes (`mistral_wrapper.py:198-272`). Backbone is **frozen** (`:88-89`).
- **CG head**: a *separate* state-dict (e.g. `checkpoints_unified/best_model.pt`) loaded by
  `cg_checkpoint.load_cg_adapter` → `_load_into_wrapper` which **filters out `backbone.*` keys**
  and loads only `state_projector / intent_projector / phase_adapter / adapter_gate /
  adapter_output_norm` with `strict=False` (`cg_checkpoint.py:168-181`). An optional companion
  `*_aux.pt` is best-effort merged.
- **Fail-closed verification**: `verify_cg_state_dict` checks for CG-head keys and that the
  `phase_adapter` output weight L2 `> 1e-6`; an untrained (zero-init) head is **refused** unless
  `allow_untrained=True` (`cg_checkpoint.py:76-114`). This is the guard that stops an untrained
  head from silently producing an inert run.
- **Device/dtype sync**: `_sync_cg_device` (`:161-178`) moves all non-backbone params/buffers to
  the backbone's device+dtype; re-run after `load_state_dict`.

## CSR / Varna

`csr_phoneme_provider.py`, `varna_mapping.py`, and `crs_combined_scorer.py` exist in the repo,
but **none are referenced by `MistralCGWrapper.forward` or `MistralCGAdapter.call`** (grep of
both files for `csr|varna|crs` returns nothing). **CSR is not in the generation logit path**, so
ablation **arm E is N/A**. `run_ablation.py` verifies this with a grep guard and records the
result; arm E activates only if a CSR stage is ever wired into the forward.

---

## Implications for the experiment

1. The wrapper **does** change generation logits (arm B), *provided the head is trained*; the
   effect scales with `sigmoid(adapter_gate)` and the trained `phase_adapter` norm.
2. **Arm D (`use_guna_bias=False`) is the rigorous base-equivalent** and must match base logits
   to `atol=1e-4` — pre-registered sanity check K0.
3. **Arm C (`use_phase_sync=False`) is expected to differ from base** by the adapter's constant
   (zero-phase) output — a real finding about whether the wrapper's effect is phase-driven or
   just a learned constant bias.
4. The honest default expectation is **inert or no-measurable-effect** unless a trained head with
   a non-trivial gate is supplied; the kill criteria (K1/K2) are designed to catch that.
