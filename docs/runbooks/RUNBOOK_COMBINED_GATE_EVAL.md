# Runbook: Combined Vritti + Guna Gate Evaluation

## Purpose

Run the 4-mode gate comparison on a **real trained Mistral-CG checkpoint** to
determine whether the Vritti and Guna sampling gates produce useful behavior
on real inference.

## Prerequisites

### Hardware
- RunPod GPU pod with >= 16GB VRAM (A10, A100, or L40S recommended)
- 4-bit quantization requires ~5GB VRAM; 8-bit requires ~8GB

### Software
```bash
pip install torch transformers accelerate bitsandbytes
```

### Checkpoint
A trained Mistral-CG checkpoint must exist on the pod. Expected paths:
```
/workspace/checkpoints_mistral_cg/best_model.pt    # split format
/workspace/checkpoints_mistral_cg/best.pt           # single file
```

The checkpoint must contain trained CG module weights (state_projector,
phase_adapter, conscious_gen.*). The Mistral-7B backbone is loaded from
HuggingFace automatically.

### Repository
```bash
cd /workspace
git clone <repo-url> symbolu
cd symbolu
git checkout claude/audit-cg-signal-aggregation-HltyO
```

## Running the Evaluation

### Standard run (4-bit, default settings)
```bash
cd /workspace/symbolu
python scripts/eval_combined_gates.py \
    /workspace/checkpoints_mistral_cg/best_model.pt \
    --output-dir /workspace/eval_results/combined_gates
```

### With options
```bash
# 8-bit quantization, shorter generation
python scripts/eval_combined_gates.py \
    /workspace/checkpoints_mistral_cg/best_model.pt \
    --output-dir /workspace/eval_results/combined_gates \
    --quantize 8bit \
    --max-new-tokens 128

# Full precision (requires ~28GB VRAM)
python scripts/eval_combined_gates.py \
    /workspace/checkpoints_mistral_cg/best.pt \
    --quantize none \
    --max-new-tokens 256
```

### Expected runtime
- 15 prompts x 4 modes = 60 generations
- ~1-3 minutes per generation at 256 tokens
- Total: ~30-90 minutes depending on GPU

## Output Artifacts

The script produces three files in the output directory:

| File | Format | Contents |
|------|--------|----------|
| `results.json` | JSON | Machine-readable full results (all events, states, outputs) |
| `EVAL_SUMMARY.md` | Markdown | Firing rates, per-category breakdown, gate interaction, over-cooling check |
| `prompt_comparison.md` | Markdown | Side-by-side output text for each prompt across all 4 modes |

## What to Copy Back to GitHub

After the run completes, copy these artifacts to the repo:

```bash
# Copy results into the repo
cp -r /workspace/eval_results/combined_gates \
    /workspace/symbolu/docs/evaluations/combined_gate_eval_YYYYMMDD/

# Commit and push
cd /workspace/symbolu
git add docs/evaluations/combined_gate_eval_YYYYMMDD/
git commit -m "Add combined gate evaluation results (YYYY-MM-DD RunPod run)"
git push -u origin claude/audit-cg-signal-aggregation-HltyO
```

## What to Look For

### Good signs
- Gates fire on error-prone / high-agency prompts but NOT on factual / memory
- Vritti and Guna fire on different prompts (complementary, not redundant)
- Output quality improves on error-prone prompts with gates on
- Output length / diversity is preserved on factual / creative prompts

### Bad signs
- Gates fire on > 30% of all steps (over-cooling)
- Gates fire on factual or creative prompts (false positives)
- Both gates always fire together (redundant)
- Output becomes repetitive or degenerate with gates on
- Guna turbulence values are always near 0 or always near 1 (uninformative)

### Decision guide
After reviewing results, check one box in the EVAL_SUMMARY.md recommendation section:
- **Keep both experimental** — if gates fire selectively and improve error-prone cases
- **Keep Vritti only** — if Guna adds noise or is redundant
- **Keep Guna only** — if Vritti is too aggressive or Guna is more selective
- **Revise thresholds** — if gate logic is sound but fires too much / too little
- **Disable** — if checkpoint quality is too low for gates to add value
- **Insufficient quality** — if the 32D state is near-random (untrained projector)

## Troubleshooting

### `ImportError: symbolu_training`
Ensure you're running from the repo root and it's on PYTHONPATH:
```bash
cd /workspace/symbolu
export PYTHONPATH=/workspace/symbolu:$PYTHONPATH
```

### `FileNotFoundError: Checkpoint not found`
The script tries both split format (`*_model.pt`) and single file. Check:
```bash
ls -la /workspace/checkpoints_mistral_cg/
```

### `OutOfMemoryError`
Use `--quantize 4bit` (default) or reduce `--max-new-tokens 64`.

### `RuntimeError: size mismatch`
The checkpoint may be from a different model version. Run the checkpoint
validator first:
```bash
python scripts/validate_cg_checkpoint.py /workspace/checkpoints_mistral_cg/best_model.pt --verbose
```
