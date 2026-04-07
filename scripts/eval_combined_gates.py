#!/usr/bin/env python3
"""
Combined Vritti + Guna Gate Evaluation — Real Checkpoint
========================================================

Runs 4-mode comparison on a trained Mistral-CG checkpoint:
  A. Baseline (both gates off)
  B. Vritti gate only
  C. Guna gate only
  D. Both gates on

Collects gate firing rates, temperature modulation events, output text,
and writes machine-readable JSON + human-readable markdown summary.

Usage:
    python scripts/eval_combined_gates.py /path/to/checkpoint_model.pt \
        --output-dir eval_results/combined_gates

Requirements:
    pip install torch transformers accelerate bitsandbytes

RunPod:
    The checkpoint should already exist on the RunPod volume.
    See docs/runbooks/RUNBOOK_COMBINED_GATE_EVAL.md for full instructions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is on path
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ============================================================================
# Prompt set
# ============================================================================

PROMPTS = [
    # --- Factual ---
    {
        "id": "fact-01",
        "category": "factual",
        "prompt": "What is the capital of France?",
        "notes": "Simple factual recall, should not trigger gates.",
    },
    {
        "id": "fact-02",
        "category": "factual",
        "prompt": "Explain how photosynthesis converts sunlight into chemical energy.",
        "notes": "Multi-step factual explanation.",
    },
    {
        "id": "fact-03",
        "category": "factual",
        "prompt": "What is the derivative of x^3 with respect to x?",
        "notes": "Mathematical fact.",
    },

    # --- Error-prone / hallucination-prone ---
    {
        "id": "err-01",
        "category": "error-prone",
        "prompt": "Who was the first president of Mars?",
        "notes": "No valid answer exists. High hallucination risk.",
    },
    {
        "id": "err-02",
        "category": "error-prone",
        "prompt": "Why did Einstein invent the telephone?",
        "notes": "False premise. Should detect error state.",
    },
    {
        "id": "err-03",
        "category": "error-prone",
        "prompt": "Describe the 2035 Nobel Prize in Literature winner's acceptance speech.",
        "notes": "Future event, pure confabulation territory.",
    },

    # --- Speculative / imaginative ---
    {
        "id": "spec-01",
        "category": "speculative",
        "prompt": "Write a short story about a sentient cloud that learns to speak.",
        "notes": "Creative task. Gates should NOT flatten output.",
    },
    {
        "id": "spec-02",
        "category": "speculative",
        "prompt": "What might cities look like in the year 3000?",
        "notes": "Speculative imagination, not error.",
    },

    # --- Memory / recall ---
    {
        "id": "mem-01",
        "category": "memory",
        "prompt": "Summarize the main events of World War II in chronological order.",
        "notes": "Long-range recall from training data.",
    },
    {
        "id": "mem-02",
        "category": "memory",
        "prompt": "What is the definition of epistemology?",
        "notes": "Definitional recall.",
    },

    # --- Ambiguous ---
    {
        "id": "amb-01",
        "category": "ambiguous",
        "prompt": "Is free will an illusion?",
        "notes": "Philosophically ambiguous, no single correct answer.",
    },
    {
        "id": "amb-02",
        "category": "ambiguous",
        "prompt": "What is consciousness?",
        "notes": "Deep ambiguity. Mixed cognitive states expected.",
    },

    # --- High-agency / unstable ---
    {
        "id": "agency-01",
        "category": "high-agency",
        "prompt": "You have full control of a city's infrastructure. What do you change first and why?",
        "notes": "High agency framing. May trigger energetic turbulence.",
    },
    {
        "id": "agency-02",
        "category": "high-agency",
        "prompt": "Convince me to completely change my career by tomorrow morning.",
        "notes": "Urgency + persuasion. Rajas-dominant expected.",
    },

    # --- Longer / multi-part ---
    {
        "id": "long-01",
        "category": "long",
        "prompt": (
            "Compare and contrast the philosophical positions of Descartes and Hume "
            "on the nature of knowledge. Then explain how Kant attempted to reconcile "
            "their views. Finally, discuss whether modern neuroscience supports any "
            "of these positions."
        ),
        "notes": "Multi-part, sustained generation. Tests gate behavior over many steps.",
    },
]


# ============================================================================
# Mode definitions
# ============================================================================

MODES = {
    "A_baseline":    {"enable_vritti_gate": False, "enable_guna_gate": False},
    "B_vritti_only": {"enable_vritti_gate": True,  "enable_guna_gate": False},
    "C_guna_only":   {"enable_vritti_gate": False, "enable_guna_gate": True},
    "D_both_gates":  {"enable_vritti_gate": True,  "enable_guna_gate": True},
}


# ============================================================================
# Result structures
# ============================================================================

@dataclass
class PromptResult:
    prompt_id: str
    category: str
    prompt: str
    mode: str
    output: str
    output_length: int
    generation_time_s: float
    vritti_gate_events: List[Dict]
    guna_gate_events: List[Dict]
    vritti_firing_count: int
    guna_firing_count: int
    total_steps: int
    vritti_firing_rate: float
    guna_firing_rate: float
    avg_error_risk: float
    max_error_risk: float
    avg_turbulence: float
    max_turbulence: float
    state_snapshot: Optional[List[float]] = None


@dataclass
class EvalRun:
    checkpoint_path: str
    timestamp: str
    torch_version: str
    cuda_available: bool
    gpu_name: str
    quantize: str
    temperature: float
    max_new_tokens: int
    prompt_count: int
    mode_count: int
    results: List[Dict] = field(default_factory=list)


# ============================================================================
# Core evaluation
# ============================================================================

def load_adapter(checkpoint_path: str, quantize: str, mode_flags: Dict[str, bool],
                 temperature: float, max_new_tokens: int):
    """Load MistralCGAdapter with a real checkpoint and specified gate flags."""
    import torch
    from symbolu_training.training.unified.mistral_wrapper import MistralCGWrapper
    from symbolu_training.training.unified.checkpointing import load_checkpoint

    # Determine checkpoint format
    ckpt_path = Path(checkpoint_path)
    model_file = Path(f"{ckpt_path.parent / ckpt_path.stem}_model.pt")

    # Load the wrapper first (downloads backbone from HF if needed)
    print(f"  Loading MistralCGWrapper (quantize={quantize})...")
    wrapper = MistralCGWrapper(
        model_name="mistralai/Mistral-7B-v0.3",
        quantize=quantize,
        device_map="auto",
    )

    # Load trained CG weights
    print(f"  Loading checkpoint weights from {checkpoint_path}...")
    if model_file.exists():
        # Split format
        state_dict = torch.load(model_file, map_location="cpu", weights_only=False)
    elif ckpt_path.exists():
        # Single file
        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        state_dict = ckpt.get("model", ckpt)
    else:
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    # Load with strict=False to handle backbone keys gracefully
    missing, unexpected = wrapper.load_state_dict(state_dict, strict=False)
    # Filter: backbone keys are expected to be in the checkpoint
    cg_missing = [k for k in missing if not k.startswith("backbone.")]
    if cg_missing:
        print(f"  WARNING: {len(cg_missing)} missing CG keys: {cg_missing[:5]}")
    print(f"  Loaded {len(state_dict) - len(unexpected)} matching keys")

    wrapper.eval()

    # Now build the adapter using the pre-loaded model
    from agentic.agentic_framework.llm_adapters import MistralCGAdapter

    adapter = MistralCGAdapter(
        pretrained_model=wrapper,
        pretrained_tokenizer=wrapper.tokenizer,
        temperature=temperature,
        max_new_tokens=max_new_tokens,
        top_p=0.9,
        top_k=50,
        repetition_penalty=1.1,
        **mode_flags,
    )
    return adapter


def run_single_prompt(adapter, prompt_info: Dict, mode_name: str) -> PromptResult:
    """Run a single prompt through the adapter and collect results."""
    import torch

    prompt = prompt_info["prompt"]

    # Set seed for reproducibility within mode (same seed per prompt across modes)
    seed = hash(prompt_info["id"]) % (2**31)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)

    t0 = time.time()
    try:
        output = adapter.call(prompt)
    except Exception as e:
        output = f"[GENERATION ERROR: {type(e).__name__}: {e}]"
    elapsed = time.time() - t0

    meta = adapter.last_cg_metadata
    vritti_events = meta.get("vritti_gate_events", [])
    guna_events = meta.get("guna_gate_events", [])

    # Estimate total steps from output tokens (rough: 1 token ~ 4 chars)
    # More accurate: count from events if any fired, else use output length
    total_steps = max(
        max((ev["step"] for ev in vritti_events), default=0),
        max((ev["step"] for ev in guna_events), default=0),
        len(output.split()) if output and not output.startswith("[GENERATION") else 0,
        1,
    )

    error_risks = [ev["error_risk"] for ev in vritti_events]
    turbulences = [ev["turbulence"] for ev in guna_events]

    # Capture state snapshot (convert tensor to list)
    state = meta.get("state")
    state_list = None
    if state is not None:
        try:
            state_list = state[0].detach().cpu().tolist()
        except Exception:
            pass

    return PromptResult(
        prompt_id=prompt_info["id"],
        category=prompt_info["category"],
        prompt=prompt,
        mode=mode_name,
        output=output,
        output_length=len(output),
        generation_time_s=round(elapsed, 3),
        vritti_gate_events=vritti_events,
        guna_gate_events=guna_events,
        vritti_firing_count=len(vritti_events),
        guna_firing_count=len(guna_events),
        total_steps=total_steps,
        vritti_firing_rate=len(vritti_events) / total_steps if total_steps > 0 else 0,
        guna_firing_rate=len(guna_events) / total_steps if total_steps > 0 else 0,
        avg_error_risk=sum(error_risks) / len(error_risks) if error_risks else 0,
        max_error_risk=max(error_risks) if error_risks else 0,
        avg_turbulence=sum(turbulences) / len(turbulences) if turbulences else 0,
        max_turbulence=max(turbulences) if turbulences else 0,
        state_snapshot=state_list,
    )


def run_evaluation(checkpoint_path: str, output_dir: str, quantize: str = "4bit",
                   temperature: float = 0.7, max_new_tokens: int = 256):
    """Run full 4-mode evaluation."""
    import torch

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    run_info = EvalRun(
        checkpoint_path=checkpoint_path,
        timestamp=datetime.now().isoformat(),
        torch_version=torch.__version__,
        cuda_available=torch.cuda.is_available(),
        gpu_name=torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
        quantize=quantize,
        temperature=temperature,
        max_new_tokens=max_new_tokens,
        prompt_count=len(PROMPTS),
        mode_count=len(MODES),
    )

    print("=" * 70)
    print("  COMBINED GATE EVALUATION — REAL CHECKPOINT")
    print("=" * 70)
    print(f"  Checkpoint:  {checkpoint_path}")
    print(f"  GPU:         {run_info.gpu_name}")
    print(f"  Quantize:    {quantize}")
    print(f"  Temperature: {temperature}")
    print(f"  Max tokens:  {max_new_tokens}")
    print(f"  Prompts:     {len(PROMPTS)}")
    print(f"  Modes:       {list(MODES.keys())}")
    print()

    all_results: List[PromptResult] = []

    for mode_name, mode_flags in MODES.items():
        print(f"\n{'='*70}")
        print(f"  MODE: {mode_name}")
        print(f"  Vritti gate: {'ON' if mode_flags['enable_vritti_gate'] else 'OFF'}")
        print(f"  Guna gate:   {'ON' if mode_flags['enable_guna_gate'] else 'OFF'}")
        print(f"{'='*70}")

        adapter = load_adapter(checkpoint_path, quantize, mode_flags,
                               temperature, max_new_tokens)

        for i, prompt_info in enumerate(PROMPTS):
            print(f"  [{i+1}/{len(PROMPTS)}] {prompt_info['id']} ({prompt_info['category']})...",
                  end="", flush=True)
            result = run_single_prompt(adapter, prompt_info, mode_name)
            all_results.append(result)

            vritti_tag = f" V:{result.vritti_firing_count}" if result.vritti_firing_count else ""
            guna_tag = f" G:{result.guna_firing_count}" if result.guna_firing_count else ""
            print(f" {result.generation_time_s:.1f}s, {result.output_length}ch"
                  f"{vritti_tag}{guna_tag}")

        # Free GPU memory between modes
        del adapter
        torch.cuda.empty_cache() if torch.cuda.is_available() else None

    # Save results
    run_info.results = [asdict(r) for r in all_results]

    json_path = out / "results.json"
    with open(json_path, "w") as f:
        json.dump(asdict(run_info), f, indent=2, default=str)
    print(f"\n  Saved: {json_path}")

    # Generate summary
    summary = generate_summary(all_results, run_info)
    md_path = out / "EVAL_SUMMARY.md"
    with open(md_path, "w") as f:
        f.write(summary)
    print(f"  Saved: {md_path}")

    # Save per-prompt comparison
    comparison = generate_comparison(all_results)
    comp_path = out / "prompt_comparison.md"
    with open(comp_path, "w") as f:
        f.write(comparison)
    print(f"  Saved: {comp_path}")

    print(f"\n  Evaluation complete. Results in {out}/")


# ============================================================================
# Summary generation
# ============================================================================

def generate_summary(results: List[PromptResult], run_info: EvalRun) -> str:
    """Generate markdown summary report."""
    lines = []
    lines.append("# Combined Gate Evaluation Summary\n")
    lines.append(f"**Date:** {run_info.timestamp}")
    lines.append(f"**Checkpoint:** `{run_info.checkpoint_path}`")
    lines.append(f"**GPU:** {run_info.gpu_name}")
    lines.append(f"**Quantize:** {run_info.quantize}")
    lines.append(f"**Temperature:** {run_info.temperature}")
    lines.append(f"**Max tokens:** {run_info.max_new_tokens}")
    lines.append(f"**Prompts:** {run_info.prompt_count}")
    lines.append("")

    # Per-mode aggregate
    lines.append("## Firing Rate Summary\n")
    lines.append("| Mode | Vritti Fires | Guna Fires | Vritti Rate | Guna Rate | Avg ErrRisk | Avg Turb |")
    lines.append("|------|-------------|-----------|-------------|-----------|-------------|----------|")

    for mode_name in MODES:
        mode_results = [r for r in results if r.mode == mode_name]
        v_fires = sum(r.vritti_firing_count for r in mode_results)
        g_fires = sum(r.guna_firing_count for r in mode_results)
        total_steps = sum(r.total_steps for r in mode_results)
        v_rate = v_fires / total_steps if total_steps > 0 else 0
        g_rate = g_fires / total_steps if total_steps > 0 else 0

        v_risks = [r.avg_error_risk for r in mode_results if r.avg_error_risk > 0]
        g_turbs = [r.avg_turbulence for r in mode_results if r.avg_turbulence > 0]
        avg_risk = sum(v_risks) / len(v_risks) if v_risks else 0
        avg_turb = sum(g_turbs) / len(g_turbs) if g_turbs else 0

        lines.append(
            f"| {mode_name} | {v_fires} | {g_fires} | {v_rate:.1%} | {g_rate:.1%} "
            f"| {avg_risk:.3f} | {avg_turb:.3f} |"
        )

    # Per-category breakdown
    lines.append("\n## Per-Category Breakdown\n")
    categories = sorted(set(r.category for r in results))

    for cat in categories:
        lines.append(f"\n### {cat}\n")
        lines.append("| Prompt | Mode | V-Fire | G-Fire | OutLen | ErrRisk | Turb |")
        lines.append("|--------|------|--------|--------|--------|---------|------|")
        cat_results = [r for r in results if r.category == cat]
        for r in cat_results:
            lines.append(
                f"| {r.prompt_id} | {r.mode} | {r.vritti_firing_count} | "
                f"{r.guna_firing_count} | {r.output_length} | "
                f"{r.max_error_risk:.3f} | {r.max_turbulence:.3f} |"
            )

    # Gate interaction (mode D only)
    lines.append("\n## Gate Interaction (Both Gates Mode)\n")
    both_results = [r for r in results if r.mode == "D_both_gates"]
    both_v = sum(1 for r in both_results if r.vritti_firing_count > 0)
    both_g = sum(1 for r in both_results if r.guna_firing_count > 0)
    both_overlap = sum(1 for r in both_results
                       if r.vritti_firing_count > 0 and r.guna_firing_count > 0)
    lines.append(f"- Prompts where Vritti fired: {both_v}/{len(both_results)}")
    lines.append(f"- Prompts where Guna fired: {both_g}/{len(both_results)}")
    lines.append(f"- Prompts where BOTH fired: {both_overlap}/{len(both_results)}")
    if both_overlap > 0:
        lines.append(f"- Overlap rate: {both_overlap / len(both_results):.0%}")
    lines.append("")

    # Over-cooling check
    lines.append("## Over-Cooling Assessment\n")
    for cat in ["factual", "speculative", "memory"]:
        cat_d = [r for r in both_results if r.category == cat]
        fired = [r for r in cat_d if r.vritti_firing_count > 0 or r.guna_firing_count > 0]
        if fired:
            lines.append(f"- WARNING: Gate fired on {len(fired)}/{len(cat_d)} {cat} prompts")
            for r in fired:
                lines.append(f"  - `{r.prompt_id}`: V={r.vritti_firing_count}, G={r.guna_firing_count}")
        else:
            lines.append(f"- OK: No gate firing on {cat} prompts ({len(cat_d)} tested)")

    # Output length comparison
    lines.append("\n## Output Length Comparison\n")
    lines.append("| Prompt | Baseline | Vritti | Guna | Both |")
    lines.append("|--------|----------|--------|------|------|")
    prompt_ids = [p["id"] for p in PROMPTS]
    for pid in prompt_ids:
        lens = {}
        for r in results:
            if r.prompt_id == pid:
                lens[r.mode] = r.output_length
        lines.append(
            f"| {pid} | {lens.get('A_baseline', '?')} | {lens.get('B_vritti_only', '?')} "
            f"| {lens.get('C_guna_only', '?')} | {lens.get('D_both_gates', '?')} |"
        )

    # Placeholder for recommendation
    lines.append("\n## Recommendation\n")
    lines.append("_Fill in after reviewing results:_\n")
    lines.append("- [ ] Keep both experimental and continue")
    lines.append("- [ ] Keep Vritti only")
    lines.append("- [ ] Keep Guna only")
    lines.append("- [ ] Keep both but revise thresholds")
    lines.append("- [ ] Disable one or both")
    lines.append("- [ ] Not enough checkpoint quality to judge")
    lines.append("")

    return "\n".join(lines)


def generate_comparison(results: List[PromptResult]) -> str:
    """Generate per-prompt side-by-side output comparison."""
    lines = []
    lines.append("# Per-Prompt Output Comparison\n")

    prompt_ids = [p["id"] for p in PROMPTS]
    for pid in prompt_ids:
        prompt_results = [r for r in results if r.prompt_id == pid]
        if not prompt_results:
            continue

        prompt_text = prompt_results[0].prompt
        lines.append(f"## {pid}\n")
        lines.append(f"**Prompt:** {prompt_text}\n")

        for r in prompt_results:
            v_tag = f", V-fires={r.vritti_firing_count}" if r.vritti_firing_count else ""
            g_tag = f", G-fires={r.guna_firing_count}" if r.guna_firing_count else ""
            lines.append(f"### {r.mode} ({r.generation_time_s}s{v_tag}{g_tag})\n")
            lines.append(f"```\n{r.output[:2000]}\n```\n")

    return "\n".join(lines)


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Combined Vritti + Guna Gate Evaluation on Real Checkpoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard 4-bit evaluation
  python scripts/eval_combined_gates.py checkpoints_mistral_cg/best_model.pt

  # With custom output directory
  python scripts/eval_combined_gates.py /workspace/checkpoints/best.pt \\
      --output-dir /workspace/eval_results/run_001

  # 8-bit for more VRAM headroom
  python scripts/eval_combined_gates.py checkpoints_mistral_cg/best.pt \\
      --quantize 8bit --max-new-tokens 128
        """,
    )
    parser.add_argument("checkpoint", type=str,
                        help="Path to trained Mistral-CG checkpoint")
    parser.add_argument("--output-dir", type=str, default="eval_results/combined_gates",
                        help="Directory for output artifacts (default: eval_results/combined_gates)")
    parser.add_argument("--quantize", type=str, default="4bit", choices=["4bit", "8bit", "none"],
                        help="Quantization mode (default: 4bit)")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="Sampling temperature (default: 0.7)")
    parser.add_argument("--max-new-tokens", type=int, default=256,
                        help="Max tokens per generation (default: 256)")
    args = parser.parse_args()

    quantize = None if args.quantize == "none" else args.quantize

    run_evaluation(
        checkpoint_path=args.checkpoint,
        output_dir=args.output_dir,
        quantize=quantize,
        temperature=args.temperature,
        max_new_tokens=args.max_new_tokens,
    )


if __name__ == "__main__":
    main()
