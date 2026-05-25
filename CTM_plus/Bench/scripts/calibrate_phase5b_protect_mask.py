#!/usr/bin/env python3
"""calibrate_phase5b_protect_mask.py — Phase 5B.0 acceptance.

Produces the per-MODEL static protect-K mask artifact required by all
subsequent Phase 5B/5C work. Replaces Phase 5A's per-sequence mask
(which can't be shared across sequences and breaks vLLM prefix
caching).

Strategy:
  1. Load Qwen2.5-7B via vLLM (stock, no install).
  2. Hook each leaf attention module's forward to capture K during
     PREFILL ONLY (T > 1).
  3. For each (layer, h_kv, d): accumulate max-abs of K across all
     calibration prompts.
  4. Per (layer, h_kv): select the top-`protect_fraction` channels by
     accumulated max-abs.
  5. Save the resulting mask as a `.pt` file with metadata header.

Lock from KERNEL_6C3C_PHASE5B5C_DESIGN.md Q1:
  - Per-model mask (not per-sequence).
  - Per-(layer, h_kv) granularity (not per-head-group).
  - max-of-maxes aggregation across prompts (matches Phase 5A
    convention for individual sequences).

Calibration corpus (v0):
  - ~60 hardcoded prompts, mix of short / medium / long, diverse
    topics (prose, code, dialogue, technical writing).
  - If quality re-acceptance (Phase 5B.5) shows degraded needle
    retrieval, upgrade to WikiText-103 sample. v0 corpus is cheap
    (~3 min runtime on A100).

Acceptance for Phase 5B.0:
  - Artifact exists at the configured output path.
  - Shape (num_layers, H_kv, D) int8.
  - Each (layer, h_kv) row has exactly n_protect = round(D *
    protect_fraction) ones.
  - Aggregate stats printed: % channels selected per layer (sanity:
    should be uniform ~protect_fraction).

Usage:
  /workspace/venv-vllm/bin/python3 calibrate_phase5b_protect_mask.py
    [--output PATH]
    [--protect-fraction 0.04]
    [--corpus-multiplier 1]
    [--max-model-len 2048]
"""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path("/workspace/symbolu/CTM_plus")
if str(ROOT / "KVPolicy") not in sys.path:
    sys.path.insert(0, str(ROOT / "KVPolicy"))

logger = logging.getLogger("calibrate_phase5b")

# ----------------------------------------------------------------------
# Calibration corpus — varied prompts to broaden per-channel coverage.
# ----------------------------------------------------------------------

CALIBRATION_CORPUS: List[str] = [
    # ----- short prose -----
    "The cat sat on the mat.",
    "She walked across the bridge as the sun set.",
    "Open the door and step into the garden.",
    "The river flowed quietly past the old mill.",
    "He wrote a letter and sealed it with wax.",
    # ----- medium prose -----
    "In the heart of the bustling city, a small bookshop stood quietly between "
    "two towering skyscrapers, its windows fogged with the warmth of stories "
    "inside.",
    "The conference began at nine sharp, with delegates from twelve countries "
    "gathering around the long oak table to discuss the upcoming treaty on "
    "renewable energy.",
    "Years had passed since she last visited the coast, but the smell of salt "
    "and the cry of gulls brought back every memory of her childhood summers.",
    "Through the heavy snowfall, the climbers could just make out the outline "
    "of the cabin, a small dark shape promising warmth and rest after a "
    "long day's ascent.",
    "He stared at the manuscript for what felt like hours, searching for the "
    "single word that would finally bring his protagonist to life.",
    # ----- technical prose -----
    "Quantum entanglement remains one of the most counterintuitive predictions "
    "of quantum mechanics, with two particles maintaining correlated states "
    "regardless of the distance separating them.",
    "Transformer architectures revolutionized natural language processing by "
    "replacing recurrent connections with attention mechanisms that can "
    "process sequences in parallel across all positions.",
    "The CRISPR-Cas9 system enables precise gene editing by directing a "
    "nuclease to specific DNA sequences via a guide RNA, allowing targeted "
    "insertions or deletions in the genome.",
    "Memory hierarchies in modern processors typically include three levels "
    "of cache, with L1 closest to the cores at single-digit nanosecond "
    "latencies, L2 in the tens of nanoseconds, and L3 shared across cores.",
    "Convex optimization problems admit efficient global solutions because "
    "any local minimum is necessarily a global minimum, enabling the use of "
    "gradient descent and its variants with provable convergence guarantees.",
    # ----- code -----
    "def fibonacci(n):\n    if n < 2:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
    "class Stack:\n    def __init__(self): self.items = []\n    def push(self, x): self.items.append(x)\n    def pop(self): return self.items.pop()",
    "SELECT user_id, COUNT(*) AS event_count FROM events WHERE created_at >= NOW() - INTERVAL '7 days' GROUP BY user_id ORDER BY event_count DESC LIMIT 100;",
    "function debounce(fn, delay) {\n  let timer;\n  return function(...args) {\n    clearTimeout(timer);\n    timer = setTimeout(() => fn(...args), delay);\n  };\n}",
    "#include <stdio.h>\nint main(void) {\n    for (int i = 1; i <= 100; i++) {\n        if (i % 15 == 0) printf(\"FizzBuzz\\n\");\n        else if (i % 3 == 0) printf(\"Fizz\\n\");\n        else if (i % 5 == 0) printf(\"Buzz\\n\");\n        else printf(\"%d\\n\", i);\n    }\n}",
    # ----- dialogue -----
    "Alice: Have you finished the report?\nBob: Almost — I just need to add the budget summary at the end.",
    "Doctor: How long have you been feeling this way?\nPatient: About three weeks now, mostly in the mornings.\nDoctor: Any changes in diet or sleep?",
    "Teacher: Can anyone tell me what photosynthesis converts?\nStudent: Sunlight into chemical energy?\nTeacher: Right — and what byproduct does it release?",
    "Detective: Where were you on the night of the fifteenth?\nSuspect: At home, asleep.\nDetective: Can anyone confirm that?",
    # ----- instructions / lists -----
    "To bake bread you will need flour, water, yeast, salt, and time. Mix the "
    "ingredients, knead for ten minutes, let rise for two hours, shape, rise "
    "again, then bake at 220°C.",
    "Step 1: Open the terminal. Step 2: Navigate to the project directory. "
    "Step 3: Run `git status` to check your working tree. Step 4: Stage your "
    "changes with `git add`. Step 5: Commit with a descriptive message.",
    "The five pillars of effective writing are clarity, brevity, accuracy, "
    "structure, and tone. Master each one before attempting longer works.",
    "When troubleshooting a connection failure, first check the physical "
    "cable, then the link lights on both ends, then the IP configuration, "
    "then the firewall rules, then the routing table.",
    # ----- questions / Q&A -----
    "What is the largest moon of Jupiter? Ganymede, which is also the largest "
    "moon in the solar system and is larger than the planet Mercury.",
    "How do I improve my running endurance? Start with a base of three runs "
    "per week, gradually increase distance by no more than 10% weekly, and "
    "include one long run for endurance and one tempo run for speed.",
    "Why does the moon appear larger near the horizon? It is an optical "
    "illusion caused by the brain's interpretation of nearby reference "
    "objects; the moon's angular size is actually the same throughout its arc.",
    "What is the difference between TCP and UDP? TCP is connection-oriented "
    "with guaranteed delivery and ordering, while UDP is connectionless and "
    "faster but provides no delivery or ordering guarantees.",
    # ----- math / reasoning -----
    "If a train travels 60 miles per hour for 2.5 hours, then 80 miles per "
    "hour for 1.5 hours, the total distance covered is 150 + 120 = 270 miles.",
    "The integral of x squared from 0 to 1 is computed as the antiderivative "
    "x cubed over 3, evaluated at the bounds: 1/3 - 0 = 1/3.",
    "To prove that the square root of two is irrational, assume it can be "
    "written as p/q in lowest terms, square both sides, and derive a "
    "contradiction showing both p and q must be even.",
    "A polynomial of degree n has at most n real roots, by the fundamental "
    "theorem of algebra extended to the complex numbers.",
    # ----- narrative / story -----
    "The lighthouse keeper had not seen a ship for sixty-three days. On the "
    "morning of the sixty-fourth, a small fishing boat appeared on the "
    "horizon, and he climbed the spiral stairs to ring the brass bell.",
    "Long ago, in a village at the edge of an ancient forest, there lived a "
    "young woodcarver whose creations were said to come alive at midnight, "
    "though no one had ever caught one in the act.",
    "The astronaut adjusted her helmet visor and stepped out onto the dusty "
    "surface. Behind her, the lander hissed softly as its cooling systems "
    "vented into the thin Martian atmosphere.",
    "Detective Chen examined the lock for the third time. There were no "
    "signs of forced entry, yet the safe — bolted to the floor of the "
    "study — had been emptied of its contents during the dinner party.",
    # ----- philosophical / abstract -----
    "Consciousness remains the hard problem of philosophy: why subjective "
    "experience accompanies physical processes at all is a question that "
    "scientific reductionism alone seems unable to answer.",
    "Free will and determinism appear in tension only if we insist that "
    "freedom requires uncaused action; a compatibilist sees freedom as "
    "acting in accordance with one's own desires regardless of their cause.",
    "The trolley problem is less about ethics than about how we reason "
    "under impossible constraints: it reveals the structure of our moral "
    "intuitions rather than prescribing any particular action.",
    # ----- business / formal -----
    "Q3 revenue increased 18% year-over-year, driven primarily by strong "
    "performance in the enterprise segment, where average contract values "
    "rose 24% as customers upgraded to our higher tiers.",
    "We propose a two-phase rollout: pilot in Region 1 for 60 days with "
    "five anchor customers, gather feedback and metrics, then expand to "
    "the remaining regions over the following quarter.",
    "The board has approved the strategic pivot toward AI-native products. "
    "Effective Q1, all new feature work should evaluate AI integration "
    "during the design phase, not as an afterthought.",
    # ----- repetitive / structured -----
    "AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH IIII JJJJ KKKK LLLL",
    "The first item is A. The second item is B. The third item is C. The "
    "fourth item is D. The fifth item is E.",
    "1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20",
    # ----- mixed language / multilingual cues -----
    "Bonjour, comment allez-vous? — I'm doing well, thank you. Et vous?",
    "The Japanese word 'omotenashi' captures a philosophy of hospitality "
    "that goes beyond service into wholehearted anticipation of needs.",
    "Hola, mi nombre es Carlos. ¿Cómo te llamas? — My name is Maria, "
    "nice to meet you.",
    # ----- long-context examples -----
    "Once upon a time, in a kingdom by the sea, there lived a clockmaker "
    "whose timepieces were said to never lose a second. Travelers came from "
    "across the realm to commission his work, paying in gold and rare gems. "
    "But the clockmaker had a secret: each clock contained a tiny spring "
    "made from the wing of a hummingbird, captured at dawn on the summer "
    "solstice, and this was the source of their unerring accuracy. When the "
    "kingdom's prince asked for a clock that would tell not just the time "
    "but also the future, the clockmaker faced his greatest challenge.",
    "In the field of computational complexity, the question of whether P "
    "equals NP remains the most important open problem. P is the class of "
    "decision problems solvable in polynomial time by a deterministic "
    "Turing machine, while NP is the class verifiable in polynomial time. "
    "The Cook-Levin theorem established that SAT is NP-complete, meaning "
    "every problem in NP can be reduced to it in polynomial time. If a "
    "polynomial-time algorithm for SAT existed, every NP problem would be "
    "in P. The conventional wisdom holds that P does not equal NP, but no "
    "proof has been found despite five decades of effort.",
    "The migration patterns of the Arctic tern are among the most "
    "remarkable in the animal kingdom. These small seabirds breed in the "
    "Arctic during the northern summer and then fly to the Antarctic for "
    "the southern summer, covering a round-trip distance of roughly 70,000 "
    "kilometers each year. Over a typical 30-year lifespan, an individual "
    "tern may fly more than two million kilometers, equivalent to three "
    "round trips to the moon. Their navigation appears to rely on a "
    "combination of celestial cues, the Earth's magnetic field, and "
    "polarized light patterns in the sky.",
]


def _looks_like_attention(module: Any) -> bool:
    """Same leaf-attention heuristic as Phase 5A."""
    cls_name = type(module).__name__
    if not cls_name.endswith("Attention"):
        return False
    if not callable(getattr(module, "forward", None)):
        return False
    for sub in module.modules():
        if sub is module:
            continue
        sub_cls = type(sub).__name__
        if sub_cls.endswith("Attention") and callable(getattr(sub, "forward", None)):
            return False
    return True


def _reshape_kv_2d_to_3d(kv, num_kv_heads):
    if kv.ndim != 2:
        return None
    T, hd = kv.shape
    if hd % num_kv_heads != 0:
        return None
    D = hd // num_kv_heads
    return kv.reshape(T, num_kv_heads, D)


def _detect_num_kv_heads(model: Any) -> Optional[int]:
    cfg = getattr(model, "config", None)
    if cfg is not None:
        for name in ("num_key_value_heads", "num_kv_heads"):
            v = getattr(cfg, name, None)
            if isinstance(v, int) and v > 0:
                return v
    return None


def _find_inner_model(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.workers[0].model_runner.model,
    ]
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError):
            pass
    raise RuntimeError("Could not locate inner nn.Module on the vLLM LLM.")


class CalibrationAccumulator:
    """Per-(layer, h_kv, d) max-abs accumulator across all prompts."""
    def __init__(self) -> None:
        # layer_name -> (H_kv, D) float tensor on CUDA
        self.layer_maxabs: Dict[str, "torch.Tensor"] = {}
        # Stable ordered list of layer names (insertion order from
        # named_modules walk → corresponds to model layer order).
        self.layer_order: List[str] = []
        self.prompts_seen: int = 0
        # Per-call counters for sanity reporting.
        self.prefill_hooks = 0
        self.decode_hooks = 0
        self.bail_outs = 0

    def update(self, layer_name: str, k_3d) -> None:
        """k_3d is (T, H_kv, D). Take per-channel max-abs across T,
        merge into the layer's accumulator with elementwise maximum."""
        import torch
        mag = k_3d.float().abs().amax(dim=0)  # (H_kv, D)
        if layer_name not in self.layer_maxabs:
            self.layer_maxabs[layer_name] = mag.clone()
            self.layer_order.append(layer_name)
        else:
            self.layer_maxabs[layer_name] = torch.maximum(
                self.layer_maxabs[layer_name], mag,
            )


def _install_calibration_hooks(
    model: Any,
    accumulator: CalibrationAccumulator,
    num_kv_heads: int,
    key_arg_index: int = 1,
) -> List[Callable[[], None]]:
    """Install a capture hook on each leaf attention module. Returns
    a list of teardown callables."""
    import torch
    teardown_list: List[Callable[[], None]] = []
    n_wrapped = 0
    for name, sub in model.named_modules():
        if not _looks_like_attention(sub):
            continue
        original_forward = sub.forward
        # Capture name + module in the closure.
        layer_name = name
        module_ref = sub

        def _make_wrapper(orig, lname, mref):
            def wrapped(*args, **kwargs):
                if (key_arg_index >= len(args)
                        or not isinstance(args[key_arg_index], torch.Tensor)):
                    accumulator.bail_outs += 1
                    return orig(*args, **kwargs)
                key = args[key_arg_index]
                if key.ndim == 2:
                    k_3d = _reshape_kv_2d_to_3d(key, num_kv_heads)
                    if k_3d is None:
                        accumulator.bail_outs += 1
                        return orig(*args, **kwargs)
                elif key.ndim == 3:
                    k_3d = key
                else:
                    accumulator.bail_outs += 1
                    return orig(*args, **kwargs)
                T = k_3d.shape[0]
                if T > 1:
                    # Prefill — collect K stats.
                    accumulator.update(lname, k_3d.detach())
                    accumulator.prefill_hooks += 1
                else:
                    accumulator.decode_hooks += 1
                return orig(*args, **kwargs)
            return wrapped

        sub.forward = _make_wrapper(original_forward, layer_name, module_ref)
        teardown_list.append(
            (lambda m=module_ref, of=original_forward: setattr(m, "forward", of))
        )
        n_wrapped += 1
    logger.info("Installed calibration hooks on %d leaf attention modules", n_wrapped)
    return teardown_list


def _build_mask_from_accumulator(
    accumulator: CalibrationAccumulator,
    protect_fraction: float,
):
    """Convert per-layer max-abs accumulator -> (num_layers, H_kv, D) int8
    mask via top-k channel selection per (layer, h_kv).
    """
    import torch
    if not accumulator.layer_order:
        raise RuntimeError(
            "No layers in accumulator — calibration hooks didn't fire. "
            "Verify the model architecture matches expectations."
        )
    # All layers should have the same (H_kv, D) shape.
    first_shape = accumulator.layer_maxabs[accumulator.layer_order[0]].shape
    H_kv, D = first_shape
    n_protect = max(1, int(round(D * protect_fraction)))

    num_layers = len(accumulator.layer_order)
    mask = torch.zeros((num_layers, H_kv, D), dtype=torch.int8)

    for layer_idx, name in enumerate(accumulator.layer_order):
        mag = accumulator.layer_maxabs[name]  # (H_kv, D)
        if mag.shape != first_shape:
            raise RuntimeError(
                f"Inconsistent shape at layer {name}: "
                f"{tuple(mag.shape)} != {tuple(first_shape)}"
            )
        # Top-k indices along D, per h_kv.
        _, topk_idx = mag.topk(n_protect, dim=-1)  # (H_kv, n_protect)
        mask[layer_idx].scatter_(-1, topk_idx.cpu(), 1)
    return mask, n_protect


def _print_summary(mask, accumulator: CalibrationAccumulator, n_protect: int) -> None:
    """Sanity report: per-layer channel selection counts."""
    import torch
    num_layers, H_kv, D = mask.shape
    per_layer_counts = mask.view(num_layers, -1).sum(dim=-1)
    expected = H_kv * n_protect
    print(f"  Mask shape:       ({num_layers}, {H_kv}, {D}) int8")
    print(f"  n_protect:        {n_protect} channels per (layer, h_kv)")
    print(f"  Expected sum per layer: {expected}")
    print(f"  Observed (min/max/mean): {per_layer_counts.min().item()}/"
          f"{per_layer_counts.max().item()}/{per_layer_counts.float().mean().item():.1f}")
    assert (per_layer_counts == expected).all(), \
        f"Layer mask sums inconsistent: {per_layer_counts.tolist()}"
    # Per-layer overlap stats — how much does layer 0 share with layer 1?
    if num_layers >= 2:
        l0 = mask[0].bool()
        l1 = mask[1].bool()
        overlap = (l0 & l1).sum().item()
        union   = (l0 | l1).sum().item()
        print(f"  Layer-0 vs Layer-1 channel overlap: {overlap}/{union} "
              f"({overlap / max(1, union) * 100:.1f}% IoU)")
    print(f"  Stats: prefill_hooks={accumulator.prefill_hooks}, "
          f"decode_hooks={accumulator.decode_hooks}, "
          f"bail_outs={accumulator.bail_outs}, "
          f"prompts_seen={accumulator.prompts_seen}")


def main(argv) -> int:
    logging.basicConfig(
        level=logging.INFO, format="[%(name)s] %(message)s",
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None,
                        help="Output .pt path. Default: derived from --model "
                             "as /workspace/dev/build-logs/"
                             "<slug>_protect_mask_<pct>pct.pt")
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--protect-fraction", type=float, default=0.04)
    parser.add_argument("--max-model-len", type=int, default=2048,
                        help="vLLM max_model_len. Keep small for calibration "
                             "memory (we only need prefill K, not long decode).")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    parser.add_argument("--corpus-multiplier", type=int, default=1,
                        help="Run the corpus this many times (each prompt seen "
                             "N times). Default 1.")
    args = parser.parse_args(argv)

    if args.output is None:
        # Phase 7: derive output path from model id so calibration for any
        # model lands in a predictable location. e.g.
        #   Qwen/Qwen2.5-7B-Instruct        -> qwen2_5_7b_instruct
        #   mistralai/Mistral-7B-Instruct-v0.3 -> mistral_7b_instruct_v0_3
        #   meta-llama/Llama-3.1-8B-Instruct -> llama_3_1_8b_instruct
        # Lowercased, strip vendor prefix, normalize separators.
        slug = args.model.split("/")[-1].lower()
        for ch in (".", "-"):
            slug = slug.replace(ch, "_")
        pct = int(round(args.protect_fraction * 100))
        args.output = f"/workspace/dev/build-logs/{slug}_protect_mask_{pct}pct.pt"

    try:
        import torch  # noqa: F401
        from vllm import LLM, SamplingParams
    except ImportError as e:
        print(f"FAIL: import error ({e}). Run inside venv-vllm.")
        return 1

    print(f"Phase 5B.0 — per-model protect mask calibration")
    print(f"  model:             {args.model}")
    print(f"  protect_fraction:  {args.protect_fraction}")
    print(f"  max_model_len:     {args.max_model_len}")
    print(f"  corpus size:       {len(CALIBRATION_CORPUS)} prompts "
          f"× {args.corpus_multiplier} = {len(CALIBRATION_CORPUS) * args.corpus_multiplier}")
    print(f"  output:            {args.output}")
    print()

    # ---- Load model ----------------------------------------------
    print("Loading model...")
    llm = LLM(
        model=args.model, max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
        enforce_eager=True,
    )
    model = _find_inner_model(llm)
    num_kv_heads = _detect_num_kv_heads(model)
    if num_kv_heads is None:
        print("FAIL: could not detect num_kv_heads from model.config")
        return 1
    print(f"  located: {type(model).__name__}, num_kv_heads={num_kv_heads}")

    # ---- Install hooks ------------------------------------------
    accumulator = CalibrationAccumulator()
    teardown_list = _install_calibration_hooks(
        model, accumulator, num_kv_heads=num_kv_heads,
    )

    # ---- Run calibration prompts --------------------------------
    # max_tokens=1 so only one decode step runs per prompt (we just need
    # prefill K). vLLM doesn't allow max_tokens=0.
    sampling = SamplingParams(temperature=0.0, max_tokens=1)

    full_corpus = CALIBRATION_CORPUS * args.corpus_multiplier
    print(f"Running calibration over {len(full_corpus)} prompts...")
    # Batch the LLM.generate call internally — vLLM handles sequential.
    out = llm.generate(full_corpus, sampling)
    accumulator.prompts_seen = len(full_corpus)
    print(f"  generate done. {len(out)} outputs.")

    # Teardown hooks before potentially-failing mask construction.
    for fn in reversed(teardown_list):
        fn()

    # ---- Build mask ---------------------------------------------
    print("Building mask from accumulator...")
    mask, n_protect = _build_mask_from_accumulator(accumulator, args.protect_fraction)
    print(f"  mask built: {tuple(mask.shape)} int8")

    # ---- Print summary ------------------------------------------
    print()
    print("Summary:")
    _print_summary(mask, accumulator, n_protect)

    # ---- Save artifact ------------------------------------------
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "mask":                 mask,
        "protect_fraction":     args.protect_fraction,
        "n_protect":            n_protect,
        "num_layers":           mask.shape[0],
        "num_kv_heads":         int(mask.shape[1]),
        "head_dim":             int(mask.shape[2]),
        "model":                args.model,
        "calibration_prompts":  len(full_corpus),
        "calibration_corpus_size": len(CALIBRATION_CORPUS),
        "corpus_multiplier":    args.corpus_multiplier,
        "phase":                "5B.0",
        # Layer name ordering preserved so consumers can verify.
        "layer_order":          accumulator.layer_order,
    }
    import torch
    torch.save(artifact, output_path)
    print()
    print(f"Phase 5B.0 GREEN")
    print(f"  artifact saved: {output_path}")
    print(f"  size:           {output_path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
