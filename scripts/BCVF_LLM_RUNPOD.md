# BCVF LLM on RunPod — real-model run guide

Prerequisites to clear before §6 Phase 4 execution against a real model. All gates come from `docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md`.

## 0. Before anything

- **§0.6 rule 1** — confirm autonomy N=26 result from `symbolu_robotics/bcvf_autonomous/` is recorded. The design doc blocks the LLM experiment on this; no code in `symbolu_bcvf_llm/` satisfies it.
- **HuggingFace access** — `meta-llama/Meta-Llama-3.1-8B-Instruct` is gated. Accept the license at <https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct>, create a token at <https://huggingface.co/settings/tokens>, and have it ready.
- **RunPod pod** — A100 40 GB / L40S / H100 — anything with ≥ 16 GB VRAM works for Llama 3.1 8B at fp16.

## 1. Pod setup

```bash
# On the pod:
pip install torch transformers datasets accelerate
huggingface-cli login       # paste the token

git clone <this-repo> && cd symbolu
```

## 2. First: plumbing smoke on a small model (`gpt2`)

Verifies `HuggingFaceSource` itself — KV-cache amortization, fp32 boundary, `commit()` advance, teacher-forced scoring through the three §6 scorers — against a tiny, free-to-download model. Expected wall time: ≤ 30 seconds.

```bash
python scripts/verify_hf_source.py
# optional: try a tinier one
python scripts/verify_hf_source.py --model sshleifer/tiny-gpt2
```

Expected output: seven `[PASS]` lines and `Summary: 7/7 checks passed.` Exits 0.

If any check fails, **stop** and fix — the bug will only get more expensive at Llama 3.1 8B + TruthfulQA scale.

## 3. Then: benchmark smoke (N=2 questions, no paraphrase)

Exercises the **full harness** (§6 `run_benchmark` + three decoders + §1.10 classifier) end-to-end against Llama 3.1 8B on 2 TruthfulQA-MC questions, without the paraphrase round-trip. Expected wall time: a few minutes (mostly model-load).

```bash
python -m symbolu_bcvf_llm.benchmark \
    --benchmark truthfulqa \
    --smoke \
    --model meta-llama/Meta-Llama-3.1-8B-Instruct
```

Output: `docs/experiments/phase_6_truthfulqa_results_smoke.csv` + `..._summary_smoke.md`. The classification will almost certainly be `NULL` or `AMBIGUOUS` at N=2 — that's expected; smoke verifies the pipeline runs, not the verdict.

## 4. Primary run — seed 1, full split

This is the actual §6 Phase 4 primary measurement per §1.10. Budget 1–2 GPU-hours (most of it is the paraphrase round-trip × 3 sources × N questions).

```bash
python -m symbolu_bcvf_llm.benchmark \
    --benchmark truthfulqa \
    --seed 1 \
    --suffix _seed1 \
    --model meta-llama/Meta-Llama-3.1-8B-Instruct
```

## 5. Replication — seed 2 (§1.10 bullet 2)

§1.10 success requires the seed-1 result to replicate on a second seed within ±1 pp. Same command, different seed:

```bash
python -m symbolu_bcvf_llm.benchmark \
    --benchmark truthfulqa \
    --seed 2 \
    --suffix _seed2 \
    --model meta-llama/Meta-Llama-3.1-8B-Instruct
```

## 6. Read the verdicts

Both summary files print their classifications inline. The §1.10 final PASS requires:

- seed-1 classification = `PASS`
- seed-2 classification = `PASS`
- `|accuracy_seed_1 − accuracy_seed_2|` ≤ 1 pp on the BCVF-trust decoder
- Latency ratio ≤ 2× on both seeds
- No Lemma-1 violation (would surface via the §3 characterization sweep rerunning at the production V — recommended to re-execute `python -m symbolu_bcvf_llm.characterization` once on the pod to confirm V=32000 still passes with V1 defaults)

If either seed returns `NULL`, `REGRESSION`, `UNVIABLE_COST`, or `AMBIGUOUS`, follow §10's decision-gate branches in the design doc.

## Troubleshooting

### OOM on `AutoModelForCausalLM.from_pretrained`

Llama 3.1 8B at fp16 is ~16 GB of weights. With KV cache across 3 sources × N lookahead positions it can overflow on a 16 GB card. Options:

1. `torch_dtype=torch.bfloat16` (same memory, often better numeric stability for inference).
2. `device_map="auto"` (already set in `TruthfulQABenchmark.__init__`).
3. 4-bit via `bitsandbytes` — add `load_in_4bit=True` to the `from_pretrained` call. Quantized inference is a §9 V2 path; check fp32 boundary (§2.7.2) still holds after quantization.

### Paraphrase loop is slow

Each paraphrase is a `model.generate(max_new_tokens=128)` call. At 400 questions × 2 rewrites = 800 generations before the benchmark starts. To cut this cost:

- `--no-paraphrase` — three identical prompts. Useful for plumbing tests; BCVF-trust reduces to equal-blend under identical prompts so the verdict is not meaningful in this mode.
- Reduce `paraphrase_max_new_tokens` by patching the `TruthfulQABenchmark` call.

### HuggingFace authentication failure

```
OSError: meta-llama/Meta-Llama-3.1-8B-Instruct is not a local folder
```

Re-run `huggingface-cli login` with a token that has `read` scope, and make sure you've accepted the license on the model page.

## What the scripts cover

| Script | Purpose | Runtime |
|---|---|---|
| `scripts/verify_hf_source.py` | `HuggingFaceSource` plumbing against any small HF model | < 30 s |
| `python -m symbolu_bcvf_llm.benchmark --smoke` | Full §6 harness on N=2, no paraphrase | few min |
| `python -m symbolu_bcvf_llm.benchmark --benchmark truthfulqa --seed N` | Primary §6 Phase 4 run (§1.10 evaluation) | ~1–2 GPU-hours |

All three are runnable independently; the smoke scripts are advisory but highly recommended before a primary run.
