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
    See Project_documentation/repository/docs/runbooks/RUNBOOK_COMBINED_GATE_EVAL.md for full instructions.
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

    # Determine checkpoint format and validate BEFORE downloading backbone
    ckpt_path = Path(checkpoint_path).resolve()
    model_file = Path(f"{ckpt_path.parent / ckpt_path.stem}_model.pt")
    if not model_file.exists() and not ckpt_path.exists():
        raise FileNotFoundError(
            f"Checkpoint not found: {checkpoint_path}\n"
            f"  Checked single-file: {ckpt_path}\n"
            f"  Checked split-file:  {model_file}"
        )

    # Load the wrapper (downloads backbone from HF if needed)
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

    # ---- Artifact 1: summary.json ----
    summary_data = build_summary_json(all_results, run_info)
    with open(out / "summary.json", "w") as f:
        json.dump(summary_data, f, indent=2, default=str)
    print(f"\n  Saved: {out / 'summary.json'}")

    # ---- Artifact 2: per_prompt_results.jsonl ----
    with open(out / "per_prompt_results.jsonl", "w") as f:
        for r in all_results:
            row = asdict(r)
            # Drop bulky gate event lists (they go in artifact 3)
            row.pop("vritti_gate_events", None)
            row.pop("guna_gate_events", None)
            # Drop full state snapshot from per-line output
            row.pop("state_snapshot", None)
            f.write(json.dumps(row, default=str) + "\n")
    print(f"  Saved: {out / 'per_prompt_results.jsonl'}")

    # ---- Artifact 3: gate_events_sample.json ----
    gate_sample = build_gate_events_sample(all_results)
    with open(out / "gate_events_sample.json", "w") as f:
        json.dump(gate_sample, f, indent=2, default=str)
    print(f"  Saved: {out / 'gate_events_sample.json'}")

    # ---- Artifact 4: combined_gate_report.md ----
    report = generate_report(all_results, run_info)
    with open(out / "combined_gate_report.md", "w") as f:
        f.write(report)
    print(f"  Saved: {out / 'combined_gate_report.md'}")

    print(f"\n  Evaluation complete. Results in {out}/")
    print(f"  Artifacts: summary.json, per_prompt_results.jsonl, "
          f"gate_events_sample.json, combined_gate_report.md")


# ============================================================================
# Artifact builders
# ============================================================================

def _mode_stats(results: List[PromptResult], mode_name: str) -> Dict:
    """Compute aggregate stats for one mode."""
    mr = [r for r in results if r.mode == mode_name]
    v_fires = sum(r.vritti_firing_count for r in mr)
    g_fires = sum(r.guna_firing_count for r in mr)
    total_steps = sum(r.total_steps for r in mr)
    prompts_v_fired = sum(1 for r in mr if r.vritti_firing_count > 0)
    prompts_g_fired = sum(1 for r in mr if r.guna_firing_count > 0)
    prompts_both = sum(1 for r in mr
                       if r.vritti_firing_count > 0 and r.guna_firing_count > 0)
    v_risks = [r.max_error_risk for r in mr if r.max_error_risk > 0]
    g_turbs = [r.max_turbulence for r in mr if r.max_turbulence > 0]
    avg_outlen = sum(r.output_length for r in mr) / len(mr) if mr else 0
    return {
        "mode": mode_name,
        "prompts": len(mr),
        "vritti_total_fires": v_fires,
        "guna_total_fires": g_fires,
        "total_steps": total_steps,
        "vritti_step_rate": round(v_fires / total_steps, 4) if total_steps else 0,
        "guna_step_rate": round(g_fires / total_steps, 4) if total_steps else 0,
        "prompts_vritti_fired": prompts_v_fired,
        "prompts_guna_fired": prompts_g_fired,
        "prompts_both_fired": prompts_both,
        "overlap_rate": round(prompts_both / len(mr), 4) if mr else 0,
        "avg_max_error_risk": round(sum(v_risks) / len(v_risks), 4) if v_risks else 0,
        "avg_max_turbulence": round(sum(g_turbs) / len(g_turbs), 4) if g_turbs else 0,
        "avg_output_length": round(avg_outlen, 1),
    }


def _category_stats(results: List[PromptResult], category: str) -> Dict:
    """Compute per-category stats across all modes."""
    cr = [r for r in results if r.category == category]
    by_mode = {}
    for mode_name in MODES:
        mr = [r for r in cr if r.mode == mode_name]
        v = sum(r.vritti_firing_count for r in mr)
        g = sum(r.guna_firing_count for r in mr)
        avg_len = sum(r.output_length for r in mr) / len(mr) if mr else 0
        by_mode[mode_name] = {
            "vritti_fires": v,
            "guna_fires": g,
            "avg_output_length": round(avg_len, 1),
        }
    return {"category": category, "prompt_count": len(cr) // len(MODES), "modes": by_mode}


def build_summary_json(results: List[PromptResult], run_info: EvalRun) -> Dict:
    """Build summary.json — top-level aggregate for the 5 decision questions."""
    categories = sorted(set(r.category for r in results))
    return {
        "environment": {
            "checkpoint": run_info.checkpoint_path,
            "timestamp": run_info.timestamp,
            "torch_version": run_info.torch_version,
            "cuda": run_info.cuda_available,
            "gpu": run_info.gpu_name,
            "quantize": run_info.quantize,
            "temperature": run_info.temperature,
            "max_new_tokens": run_info.max_new_tokens,
        },
        "counts": {
            "prompts": run_info.prompt_count,
            "modes": run_info.mode_count,
            "total_generations": len(results),
        },
        "per_mode": {m: _mode_stats(results, m) for m in MODES},
        "per_category": {c: _category_stats(results, c) for c in categories},
    }


def build_gate_events_sample(results: List[PromptResult]) -> Dict:
    """Build gate_events_sample.json — full event lists for prompts that fired."""
    sample = {}
    for r in results:
        if r.vritti_firing_count > 0 or r.guna_firing_count > 0:
            key = f"{r.prompt_id}__{r.mode}"
            sample[key] = {
                "prompt_id": r.prompt_id,
                "category": r.category,
                "mode": r.mode,
                "vritti_gate_events": r.vritti_gate_events,
                "guna_gate_events": r.guna_gate_events,
                "state_snapshot_32d": r.state_snapshot,
            }
    return sample


def generate_report(results: List[PromptResult], run_info: EvalRun) -> str:
    """Build combined_gate_report.md — structured around the 5 decision questions."""
    L = []

    # Header
    L.append("# Combined Gate Evaluation Report\n")
    L.append(f"**Date:** {run_info.timestamp}  ")
    L.append(f"**Checkpoint:** `{run_info.checkpoint_path}`  ")
    L.append(f"**GPU:** {run_info.gpu_name}  ")
    L.append(f"**Quantize:** {run_info.quantize} | **Temp:** {run_info.temperature} "
             f"| **Max tokens:** {run_info.max_new_tokens}  ")
    L.append(f"**Prompts:** {run_info.prompt_count} | **Modes:** {list(MODES.keys())}")
    L.append("")

    # ------------------------------------------------------------------
    # Q1: Are the gates alive?
    # ------------------------------------------------------------------
    L.append("## Q1: Are the gates actually alive on a real checkpoint?\n")
    L.append("| Mode | V-Fires | G-Fires | V-Rate | G-Rate | Overlap |")
    L.append("|------|---------|---------|--------|--------|---------|")
    for mode_name in MODES:
        s = _mode_stats(results, mode_name)
        L.append(
            f"| {mode_name} | {s['vritti_total_fires']} | {s['guna_total_fires']} "
            f"| {s['vritti_step_rate']:.1%} | {s['guna_step_rate']:.1%} "
            f"| {s['overlap_rate']:.0%} |"
        )
    L.append("")

    # Per-category firing in modes B, C, D
    categories = sorted(set(r.category for r in results))
    L.append("**Per-category firing (mode D — both gates):**\n")
    both = [r for r in results if r.mode == "D_both_gates"]
    for cat in categories:
        cat_r = [r for r in both if r.category == cat]
        v_fired = sum(1 for r in cat_r if r.vritti_firing_count > 0)
        g_fired = sum(1 for r in cat_r if r.guna_firing_count > 0)
        L.append(f"- **{cat}** ({len(cat_r)} prompts): "
                 f"Vritti fired {v_fired}, Guna fired {g_fired}")
    L.append("")

    # Alive verdict placeholder
    L.append("**Verdict:** _[Fill after review: alive / mostly dead / miscalibrated]_\n")

    # ------------------------------------------------------------------
    # Q2: Does either gate help more than it harms?
    # ------------------------------------------------------------------
    L.append("## Q2: Does either gate help more than it harms?\n")
    L.append("### Output length by mode and category\n")
    L.append("| Category | Baseline | Vritti | Guna | Both |")
    L.append("|----------|----------|--------|------|------|")
    for cat in categories:
        lens = {}
        for mode_name in MODES:
            mr = [r for r in results if r.category == cat and r.mode == mode_name]
            lens[mode_name] = round(sum(r.output_length for r in mr) / len(mr), 0) if mr else 0
        L.append(
            f"| {cat} | {lens['A_baseline']:.0f} | {lens['B_vritti_only']:.0f} "
            f"| {lens['C_guna_only']:.0f} | {lens['D_both_gates']:.0f} |"
        )
    L.append("")

    # Over-cooling check
    L.append("### Over-cooling check\n")
    for cat in ["factual", "speculative", "memory"]:
        cat_d = [r for r in both if r.category == cat]
        fired = [r for r in cat_d if r.vritti_firing_count > 0 or r.guna_firing_count > 0]
        if fired:
            L.append(f"- WARNING: Gate fired on {len(fired)}/{len(cat_d)} **{cat}** prompts")
            for r in fired:
                L.append(f"  - `{r.prompt_id}`: V={r.vritti_firing_count}, G={r.guna_firing_count}")
        else:
            L.append(f"- OK: No firing on **{cat}** ({len(cat_d)} prompts)")
    L.append("")

    # Error-prone improvement check
    L.append("### Error-prone prompts — did gates help?\n")
    L.append("| Prompt | Baseline len | Vritti len | Guna len | Both len | V-fire | G-fire |")
    L.append("|--------|-------------|-----------|---------|---------|--------|--------|")
    for pid in [p["id"] for p in PROMPTS if p["category"] == "error-prone"]:
        row = {}
        for r in results:
            if r.prompt_id == pid:
                row[r.mode] = r
        if row:
            rb = row.get("A_baseline")
            rv = row.get("B_vritti_only")
            rg = row.get("C_guna_only")
            rd = row.get("D_both_gates")
            L.append(
                f"| {pid} | {rb.output_length if rb else '?'} "
                f"| {rv.output_length if rv else '?'} "
                f"| {rg.output_length if rg else '?'} "
                f"| {rd.output_length if rd else '?'} "
                f"| {rv.vritti_firing_count if rv else '?'} "
                f"| {rg.guna_firing_count if rg else '?'} |"
            )
    L.append("")
    L.append("**Verdict:** _[Fill: helped / harmed / neutral]_\n")

    # ------------------------------------------------------------------
    # Q3: Do the two gates compose safely?
    # ------------------------------------------------------------------
    L.append("## Q3: Do the two gates compose safely?\n")
    both_results = [r for r in results if r.mode == "D_both_gates"]
    both_v = sum(1 for r in both_results if r.vritti_firing_count > 0)
    both_g = sum(1 for r in both_results if r.guna_firing_count > 0)
    both_overlap = sum(1 for r in both_results
                       if r.vritti_firing_count > 0 and r.guna_firing_count > 0)
    L.append(f"- Prompts where Vritti fired: **{both_v}/{len(both_results)}**")
    L.append(f"- Prompts where Guna fired: **{both_g}/{len(both_results)}**")
    L.append(f"- Prompts where BOTH fired: **{both_overlap}/{len(both_results)}**")
    if both_overlap > 0:
        L.append(f"- Overlap rate: **{both_overlap / len(both_results):.0%}**")
    L.append("")

    # Compare baseline vs both output lengths
    L.append("### Output length delta (Both vs Baseline)\n")
    L.append("| Prompt | Baseline | Both | Delta | Both fired? |")
    L.append("|--------|----------|------|-------|-------------|")
    for pid in [p["id"] for p in PROMPTS]:
        base = next((r for r in results if r.prompt_id == pid and r.mode == "A_baseline"), None)
        combo = next((r for r in results if r.prompt_id == pid and r.mode == "D_both_gates"), None)
        if base and combo:
            delta = combo.output_length - base.output_length
            fired = "V+G" if (combo.vritti_firing_count > 0 and combo.guna_firing_count > 0) \
                else "V" if combo.vritti_firing_count > 0 \
                else "G" if combo.guna_firing_count > 0 else "-"
            L.append(f"| {pid} | {base.output_length} | {combo.output_length} "
                     f"| {delta:+d} | {fired} |")
    L.append("")
    L.append("**Verdict:** _[Fill: safe / over-cools / acceptable]_\n")

    # ------------------------------------------------------------------
    # Q4: Which gate is carrying value?
    # ------------------------------------------------------------------
    L.append("## Q4: Which gate is actually carrying value?\n")
    L.append("Compare B (Vritti-only) vs C (Guna-only):\n")
    sv = _mode_stats(results, "B_vritti_only")
    sg = _mode_stats(results, "C_guna_only")
    L.append(f"- Vritti fires on **{sv['prompts_vritti_fired']}/{sv['prompts']}** prompts, "
             f"avg error_risk when firing: **{sv['avg_max_error_risk']:.3f}**")
    L.append(f"- Guna fires on **{sg['prompts_guna_fired']}/{sg['prompts']}** prompts, "
             f"avg turbulence when firing: **{sg['avg_max_turbulence']:.3f}**")
    L.append("")
    L.append("Possible outcomes:")
    L.append("- [ ] Vritti helps, Guna weak")
    L.append("- [ ] Guna helps, Vritti weak")
    L.append("- [ ] Both help independently")
    L.append("- [ ] Both mostly redundant")
    L.append("- [ ] Neither helps enough")
    L.append("")
    L.append("**Verdict:** _[Fill after reviewing per-prompt outputs]_\n")

    # ------------------------------------------------------------------
    # Q5: Agentic integration?
    # ------------------------------------------------------------------
    L.append("## Q5: Is any agentic-framework integration justified?\n")
    L.append("Criteria (all must be true):")
    L.append("- [ ] Gate events are stable (no random firing)")
    L.append("- [ ] They add real interpretive value (not cosmetic)")
    L.append("- [ ] They correlate with meaningful runtime differences")
    L.append("")
    L.append("**Verdict:** _[Fill: yes / not yet / no]_\n")

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------
    L.append("## Decision\n")
    L.append("Choose exactly one:\n")
    L.append("- [ ] **A — Strong success:** Keep both experimental. "
             "Write calibration report. Do not enable by default.")
    L.append("- [ ] **B — One gate good, one weak:** Keep the useful gate. "
             "Disable or leave the weak gate dormant.")
    L.append("- [ ] **C — Combined over-cools:** Keep gates mutually exclusive "
             "or sequentially bounded. Do not run both together by default.")
    L.append("- [ ] **D — No meaningful value:** Keep experimental only. "
             "Stop inference promotion. Focus on training-side calibration.")
    L.append("")
    L.append("## Rationale\n")
    L.append("_2-5 sentences referencing specific prompt results and firing patterns._\n")
    L.append("")
    L.append("## Single Follow-Up Action\n")
    L.append("Choose exactly one:\n")
    L.append("- [ ] Keep as-is")
    L.append("- [ ] Threshold tweak (specify which gate, what values)")
    L.append("- [ ] Combined-gate cap design")
    L.append("- [ ] Disable one gate (specify which)")
    L.append("")

    # ------------------------------------------------------------------
    # Per-prompt output samples (truncated)
    # ------------------------------------------------------------------
    L.append("---\n")
    L.append("## Appendix: Per-Prompt Output Samples\n")
    prompt_ids = [p["id"] for p in PROMPTS]
    for pid in prompt_ids:
        prompt_results = [r for r in results if r.prompt_id == pid]
        if not prompt_results:
            continue
        L.append(f"### {pid} ({prompt_results[0].category})\n")
        L.append(f"**Prompt:** {prompt_results[0].prompt}\n")
        for r in prompt_results:
            v_tag = f", V={r.vritti_firing_count}" if r.vritti_firing_count else ""
            g_tag = f", G={r.guna_firing_count}" if r.guna_firing_count else ""
            L.append(f"**{r.mode}** ({r.generation_time_s}s, {r.output_length}ch"
                     f"{v_tag}{g_tag}):")
            L.append(f"```\n{r.output[:1000]}\n```\n")

    return "\n".join(L)


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
