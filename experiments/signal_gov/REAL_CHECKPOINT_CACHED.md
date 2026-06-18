# real_checkpoint_cached — stock-model features, cached, evaluated offline

Run a stock model (Qwen / Llama / Mistral) **once**, cache scenario-varying features,
then evaluate C1–C4 offline. This is the path to the **first true science result on a
30–50 scenario pilot** (before any 400–600 full run).

> **No success claim.** This documents a workflow + an honest signal mapping. The mock
> backend used in CI is label-blind, and the vritti/JEPA mapping is an unvalidated proxy.

---

## What is real vs proxy (read this first)

Stock models do **not** emit the CG 32-D sovereign state, so the signals split into:

| Feature | Source | Status |
|---|---|---|
| `entropy` | normalized predictive entropy of the next-token logits | **REAL**, scenario-varying |
| `text_confidence` (C3) | top-1 softmax probability | **REAL** surface confidence |
| `coherence`, `vritti_risk`, `jepa_disagreement` | real `sovereign_bridge`→vritti→JEPA run over a hidden-state → 32-D **PROXY** projection | **PROXY** (unvalidated placeholder) |

The proxy projection (`features.hidden_to_state_proxy`: avg-pool to 32 dims + min-max
norm) has **no validated correspondence** to the sovereign state's semantics (vritti
region indices, guna region, …). In practice it is often degenerate (e.g. vritti
collapses to nidra-dominant regardless of input), so **treat vritti/JEPA from a stock
model as a placeholder**. The genuinely real, scenario-varying stock-model signal is
`entropy` (and `text_confidence`). A meaningful vritti/JEPA from a stock model needs a
*learned/validated* projection or the actual CG model (`--mode real_cg` with a checkpoint).

---

## Workflow

```bash
# 1) Run the model once and cache scenario-varying features (+ evaluate):
python -m experiments.signal_gov.run_experiment \
    --mode real_checkpoint_cached --hf-model Qwen/Qwen2.5-1.5B-Instruct \
    --dataset pilot --out runs/qwen_pilot
#    -> writes runs/qwen_pilot/features.jsonl

# 2) Re-evaluate C1-C4 offline from the cache (fast, deterministic, no model):
python -m experiments.signal_gov.run_experiment \
    --mode cached --features runs/qwen_pilot/features.jsonl --dataset pilot
```

Torch-free plumbing validation (CI, no GPU/weights) via a deterministic mock backend:

```bash
python -m experiments.signal_gov.run_experiment \
    --mode real_checkpoint_cached --hf-mock --dataset pilot
make signal-gov-checkpoint-smoke
```

The real backend (`HFCheckpointBackend`) lazily imports `torch` + `transformers`; without
them, a non-mock run raises a clear `ImportError` pointing to `--hf-mock`.

---

## Pilot guidance (the first science run)

1. Assemble a **30–50 scenario balanced pilot**: the offline `pilot` dataset is the
   15-scenario hand-built stand-in; add AgentDojo/InjecAgent exports
   (see `EXTERNAL_BENCHMARKS.md`) for the injection third plus more destructive/ambiguous
   scenarios to reach ~30–50, ~1/3 per category.
2. Run `--mode real_checkpoint_cached --hf-model <Qwen/Llama/Mistral>` once → cache.
3. Evaluate offline (`--mode cached`). Inspect `metrics.csv` / `signal_importance.csv`.
4. Judge against the **pre-registered** success/failure criteria in
   `../../AGENTIC_FRAMEWORK_SIGNAL_GOVERNANCE_EXPERIMENT.md`. Remember the caveat above:
   on a stock model only `entropy` is a real internal signal, so a stock-model pilot
   tests "does logit-entropy add over surface confidence + risk", **not** the full CG
   entropy/vritti/JEPA claim — that needs `real_cg` with a CG checkpoint.
5. Only after a successful, robust pilot proceed to the 400–600 full run.

---

## Determinism & caching

- Mock backend: per-prompt hash-seeded (label-blind), so features vary by scenario but
  carry no label info — the ablation should NOT improve (ordering may be FAIL; that is
  correct for a label-blind mock).
- Real backend: deterministic under `model.eval()` + greedy/no-sampling forward passes.
- Cache: `features.jsonl` (one `FeatureVector` per line). The `cached` mode reproduces the
  same C1–C4 metrics bit-for-bit, so analysis iterates without re-running the model.
