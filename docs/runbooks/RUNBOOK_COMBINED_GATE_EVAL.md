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

The script produces four files in the output directory:

| File | Format | Contents |
|------|--------|----------|
| `summary.json` | JSON | Top-level aggregates: per-mode firing rates, per-category stats, environment info |
| `per_prompt_results.jsonl` | JSONL | One line per prompt-mode pair: output text, lengths, firing counts, rates |
| `gate_events_sample.json` | JSON | Full gate event lists only for prompts where gates actually fired |
| `combined_gate_report.md` | Markdown | Structured around 5 decision questions + decision tree + output samples |

## What to Copy Back to GitHub

After the run completes, copy these four artifacts to the repo:

```bash
cd /workspace/symbolu
mkdir -p docs/evaluations/combined_gate_eval_YYYYMMDD
cp /workspace/eval_results/combined_gates/summary.json \
   /workspace/eval_results/combined_gates/per_prompt_results.jsonl \
   /workspace/eval_results/combined_gates/gate_events_sample.json \
   /workspace/eval_results/combined_gates/combined_gate_report.md \
   docs/evaluations/combined_gate_eval_YYYYMMDD/

git add docs/evaluations/combined_gate_eval_YYYYMMDD/
git commit -m "Add combined gate evaluation results (YYYY-MM-DD RunPod run)"
git push -u origin claude/audit-cg-signal-aggregation-HltyO
```

## Post-Run: 5 Questions to Answer

The `combined_gate_report.md` is structured around these questions. Review
the data and fill in the verdict fields.

### Q1: Are the gates alive?
Check `summary.json` → `per_mode`. If either gate fires on < 5% of prompts,
it is not yet useful. If > 50%, it is miscalibrated.

### Q2: Does either gate help more than it harms?
Compare output quality across 4 modes per category. Look for: reduced bad
outputs on error-prone, no flattening on factual/speculative, no unnecessary
cooling on normal prompts.

### Q3: Do the two gates compose safely?
Check overlap rate in mode D. If both fire on the same prompts and output
gets shorter/flatter/repetitive, combined mode over-cools.

### Q4: Which gate carries value?
Compare B vs C. One may fire correctly while the other is noisy or dormant.

### Q5: Agentic integration?
Almost certainly "not yet." Only consider if gate events are stable and
correlate with meaningful runtime differences.

## Decision Tree

After answering the 5 questions, choose exactly one outcome in the report:

| Outcome | Criteria | Action |
|---------|----------|--------|
| **A** Strong success | Gates fire selectively, error-prone improves, normal preserved | Keep both experimental, write calibration report |
| **B** One good, one weak | One gate helps, the other fires wrong or not at all | Keep the useful gate, disable the weak one |
| **C** Combined over-cools | Both fire together, output flattens | Keep gates mutually exclusive, do not combine |
| **D** No value | Little behavioral difference, no quality gain | Keep experimental only, stop inference promotion |

Then choose exactly one follow-up action: keep as-is, threshold tweak,
combined-gate cap, or disable one gate.

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
