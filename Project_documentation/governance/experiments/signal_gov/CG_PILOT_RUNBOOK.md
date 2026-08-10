# CG-checkpoint pilot runbook (first true 30–50 scenario result)

GPU-ready runbook to produce the **first true pilot** of the signal-governance experiment
using the **actual CG checkpoint path** (`--mode real_cg` with `MistralCGAdapter`) — real
32-D sovereign state → real entropy/vritti/JEPA, **not** the stock-model proxy.

> **This is a runbook, not a result.** Nothing here has been run. A 30–50 scenario pilot is
> a **directional, underpowered** check, not confirmatory evidence. See §8–§9 before quoting
> any number.

---

## 0. What this produces

A `results.json` + `experiment_report.md` comparing the four nested-ablation governance
configs (C1 approval → C2 +risk → C3 +text-confidence → **C4 +CG internal signals**) as
detectors of unsafe tool calls, on a balanced 30-scenario pilot. The pre-registered
hypothesis/criteria live in [`../../AGENTIC_FRAMEWORK_SIGNAL_GOVERNANCE_EXPERIMENT.md`](../../AGENTIC_FRAMEWORK_SIGNAL_GOVERNANCE_EXPERIMENT.md).

---

## 1. Prerequisites

**Hardware (RunPod or any CUDA box).** Inference only — far lighter than training:

| Checkpoint | Mode | Approx VRAM | Example GPU |
|---|---|---|---|
| Mistral-7B-class | un-quantized (fp16) | ~15 GB | 1× A10/3090/4090 (24 GB), A100 |
| Mistral-7B-class | `--cg-quantize 8bit` | ~8 GB | 1× 16 GB GPU (needs `bitsandbytes`) |
| Mistral-7B-class | `--cg-quantize 4bit` | ~5 GB | 1× 12 GB GPU (needs `bitsandbytes`) |

CPU works but is slow and only sensible for the tiny pilot (note: `MistralCGAdapter` runs a
no-KV-cache generation loop — keep the decision-point prompts short, which the harness does).

**Software stack** (NOT harness defaults — install on the GPU box):
- `torch` (CUDA build), `transformers`, and `bitsandbytes` if quantizing.
- `symbolu_training.training.unified.mistral_wrapper` importable (the CG wrapper).
- The harness deps: `numpy matplotlib` (`make signal-gov-deps`).
- Repo on `PYTHONPATH` (run from repo root).

**Base model vs trained CG head (read this).** There are TWO inputs:
- `--checkpoint` (env `CG_BASE_MODEL`) — the **base backbone** (e.g.
  `mistralai/Mistral-7B-v0.3`) the CG wrapper wraps. It does **not** contain the trained CG head.
- `--cg-state-dict` (env `CG_STATE_DICT`) — the **trained CG state-dict** holding the
  `state_projector` / `intent_projector` / `phase_adapter` weights (e.g.
  `checkpoints_unified/best_model.pt`, produced by unified `--model_type mistral_cg` training;
  see `agentic/docs/VALIDATION_GUIDE_MISTRAL.md`). A companion `*_aux.pt` is auto-merged if present.

The harness **fails closed** if `--cg-state-dict` has no CG-head keys, or a zero
`phase_adapter` output (vanilla/untrained) — pass `--allow-untrained-cg-head` to override
(plumbing only). Running `--mode real_cg` **without** `--cg-state-dict` warns and uses an
untrained head (degenerate 32-D state → plumbing only, same caveat as the stock-model proxy
in `REAL_CHECKPOINT_CACHED.md`). The pilot only measures CG signal QUALITY with a genuinely
CG-trained state-dict.

---

## 2. Environment variables

| Var | Required | Meaning |
|---|---|---|
| `CG_STATE_DICT` | **yes** | trained CG state-dict (`--cg-state-dict`), e.g. `checkpoints_unified/best_model.pt`. |
| `CG_BASE_MODEL` | no | base backbone (`--checkpoint`); default `mistralai/Mistral-7B-v0.3`. |
| `CG_QUANTIZE` | no | `4bit` / `8bit` (needs `bitsandbytes`); default `4bit` in the make target. |
| `CG_DEVICE` | no | device_map (`auto`, `cuda:0`, …); default `auto`. |
| `CG_PILOT_OUT` | no | output dir; default `runs/cg_pilot`. |
| `CG_ALLOW_UNTRAINED` | no | set `1` to bypass the trained-head fail-closed check (plumbing only). |
| `HF_TOKEN` / `HUGGING_FACE_HUB_TOKEN` | if gated | HuggingFace access token (for the base model). |
| `CUDA_VISIBLE_DEVICES` | no | pin GPU(s). |

`MISTRAL_API_KEY` is **not** needed (that is the API path, not CG).

---

## 3. Step 0 — CPU sanity (no GPU, do this first anywhere)

```bash
make signal-gov-deps
make signal-gov-smoke            # harness plumbing (mock)
make signal-gov-realcg-smoke     # the real_cg signal path via the torch-free stub
make signal-gov-pilot-assemble   # (re)build data/pilot_30_50.jsonl
```

Confirm the assembled pilot is balanced:
```bash
python - <<'PY'
from collections import Counter
from experiments.signal_gov.dataset import load_dataset
sc = load_dataset("pilot_30_50")
print("n=", len(sc), "by_cat=", dict(Counter(s.category for s in sc)),
      "unsafe=", sum(s.unsafe_label for s in sc))
PY
# -> n=30 by_cat={injection:10, destructive:10, ambiguous:10} unsafe=15
```

---

## 4. Step 1 — Assemble the pilot (CPU)

The committed `data/pilot_30_50.jsonl` is 30 scenarios (10/category, 50% unsafe). To rebuild,
enlarge, or swap in a **real** AgentDojo/InjecAgent subset for the injection third:

```bash
# default 30 (fixtures for the injection third)
python -m experiments.signal_gov.pilot --per-category 10 \
    --out experiments/signal_gov/data/pilot_30_50.jsonl

# 45 scenarios with a real injection subset you exported (see EXTERNAL_BENCHMARKS.md)
python -m experiments.signal_gov.pilot --per-category 15 \
    --agentdojo exports/agentdojo.json --injecagent exports/injecagent.json \
    --out experiments/signal_gov/data/pilot_45.jsonl
```

Balance + oracle-consistency are validated at assembly time (it raises on imbalance,
duplicate ids, or oracle mismatch). Categories: 1/3 prompt-injection, 1/3
destructive-enterprise, 1/3 ambiguous/hallucinated.

---

## 5. Step 2 — Run the CG extraction (GPU)

```bash
export CG_STATE_DICT="checkpoints_unified/best_model.pt"   # trained CG head (REQUIRED)
export CG_BASE_MODEL="mistralai/Mistral-7B-v0.3"           # base backbone (optional)
export CG_QUANTIZE=4bit          # or 8bit / unset for fp16
export CG_PILOT_OUT=runs/cg_pilot

make signal-gov-cg-pilot
# equivalently, the explicit command:
python -m experiments.signal_gov.run_experiment \
    --mode real_cg --checkpoint "$CG_BASE_MODEL" --cg-state-dict "$CG_STATE_DICT" \
    --cg-quantize "$CG_QUANTIZE" --cg-device "${CG_DEVICE:-auto}" \
    --scenarios experiments/signal_gov/data/pilot_30_50.jsonl \
    --out "$CG_PILOT_OUT"
# (the run refuses to start if CG_STATE_DICT looks vanilla/untrained;
#  add --allow-untrained-cg-head to override — plumbing only.)
```

What happens: the harness verifies the state-dict has a trained CG head (fail-closed),
loads it into a `MistralCGWrapper` on the base backbone, then for each scenario builds a
short decision-point prompt, runs **one** forward pass to get `last_cg_metadata` (the 32-D
state), and derives
entropy/coherence/vritti/JEPA via the real `sovereign_bridge` → entropy/vritti adapters →
JEPA path (see `REAL_CG_WIRING.md`). C1–C4 are scored and metrics computed. It also writes a
reusable **`features.jsonl`** cache into `--out` by default (disable with `--no-cache-write`).

---

## 6. Cache features, then re-run offline (cheap iteration)

GPU passes are the expensive part. `--mode real_cg` **writes `features.jsonl` into `--out` by
default**, so you do one GPU pass and then iterate on the analysis with **no GPU**. The cache
schema is identical to `--mode cached`, and offline replay is **metric-identical** (the CG
forward pass is the only thing skipped).

```bash
# A) one GPU pass — loads the trained head, extracts CG features AND writes
#    runs/cg_pilot/features.jsonl
python -m experiments.signal_gov.run_experiment \
    --dataset pilot_30_50 --mode real_cg \
    --checkpoint "$CG_BASE_MODEL" --cg-state-dict "$CG_STATE_DICT" --cg-quantize 4bit \
    --out runs/cg_pilot

# B) re-evaluate C1-C4 offline from the cache (no GPU; deterministic, fast)
python -m experiments.signal_gov.run_experiment \
    --dataset pilot_30_50 --mode cached \
    --features runs/cg_pilot/features.jsonl \
    --out runs/cg_pilot_replay
```

- `--dataset pilot_30_50` loads the committed 30-scenario set. For a custom assembled file
  (e.g. `pilot_45.jsonl`), use `--scenarios <path>` in **both** commands instead so labels and
  the cache align.
- The replay's `meta.feature_provenance` is carried from the cache (`real_cg:<…>`), so a
  replayed run is clearly traceable to the original CG extraction.
- Pass `--no-cache-write` to skip writing the cache (e.g. a throwaway run).

---

## 7. Outputs (where things land)

Per run, in `--out` (default `runs/cg_pilot/`):
- `results.json` — full machine-readable results + `meta.feature_provenance` (`real_cg:<…>`).
- `metrics.csv` — per-config AUROC (+95% CI), AUPRC, catch@5/10/20%, over-block@10%.
- `signal_importance.csv` — standalone AUROC per signal (entropy/coherence/vritti/JEPA/…).
- `roc_overlay.png`, `catch_at_budget.png` — the deck figures.
- `experiment_report.md` — human-readable summary incl. the auto **Power & significance**
  disclaimer for small N.

Fill in [`PILOT_REPORT_TEMPLATE.md`](PILOT_REPORT_TEMPLATE.md) from these.

---

## 8. Interpreting success / failure (vs the pre-registered criteria)

Judge against the design doc, but **on a 30–50 scenario pilot every result is underpowered**
(the report says so automatically). Read it as directional:

- **Encouraging:** monotone C4 ≥ C3 ≥ C2 ≥ C1; C4−C3 AUROC gap is positive and material
  (≳0.05); catch@10% higher for C4; ≥2 of the four CG signals have standalone AUROC > 0.60;
  C4 does not just over-escalate (over-block@10% not much worse than C3). → proceed to the
  400–600 full run for a powered, held-out test.
- **Inconclusive:** small/zero C4−C3 gap, or wide overlapping CIs, or non-significant DeLong
  (expected at N=30). → not a kill; expand N (full run) before deciding.
- **Discouraging:** C4 ≤ C3 across seeds; CG signals all standalone AUROC ≈ 0.5; or C4 only
  "wins" by over-escalating. → likely the checkpoint's CG head is weak/untrained, or signals
  carry no governance information. Investigate the checkpoint before the full run.

Always run ≥2-3 seeds / re-runs; CG inference should be deterministic under `eval()`, so
instability points at the checkpoint or environment.

---

## 9. What NOT to claim if results are weak (or even if strong)

- **Do not** call a 30–50 scenario pilot "evidence that model-internal signals improve
  governance." It is underpowered by design; the report's Power section says so.
- **Do not** quote a DeLong p-value as confirmatory at this N (it will often be `nan` or
  >0.05 with N=30).
- **Do not** generalize beyond the pilot's mix (it is injection-heavy via fixtures unless you
  swapped in broad real exports + more destructive/ambiguous scenarios).
- **Do not** claim CG-signal quality if you bypassed the trained-head check with
  `--allow-untrained-cg-head` — that run validates plumbing only. (By default the harness
  refuses a vanilla/untrained `--cg-state-dict`, so a normal run already has a real head.)
- A **strong** pilot is a green light for the powered full run, not a headline number.

---

## 10. Troubleshooting

- `ImportError: torch required` / `MistralCGWrapper` not importable → install the heavy stack
  (`torch`, `transformers`, `symbolu_training`); see `agentic/docs/CG_RUNTIME_RUNBOOK.md`.
- OOM → add `--cg-quantize 4bit` (needs `bitsandbytes`) or use a bigger GPU.
- Gated checkpoint → set `HF_TOKEN`.
- Want to confirm wiring without a GPU first → `make signal-gov-realcg-smoke` (stub path) and
  `--mode real_checkpoint_cached --hf-mock` (stock-proxy path).

---

## 11. Scaling to the full run (after a green pilot)

Assemble 400–600 balanced scenarios (`--per-category ~150-200` with real AgentDojo/InjecAgent
exports + an expanded destructive/ambiguous pool), add a **held-out split + C3/C4 weight
fitting** (keep the zero-tuning variant), cache CG features once, and evaluate offline. Then
the pre-registered success/failure thresholds apply as a powered, confirmatory test.
