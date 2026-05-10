"""Phase 4 Q-center calibration driver for vLLM-loaded models.

Loads a model via vLLM's ``LLM`` (so the same server config the
streaming runner will use is exercised), walks to the underlying
torch model, registers Q-center calibration hooks via
``kv_policy.triattention.calibrate_q_centers``, drives a few
forward passes via ``llm.generate(...)``, and writes the resulting
QCenterStats JSON to ``--output``.

Usage:

    python -m ctm_bench.scripts.calibrate_qcenters_vllm \\
        --model /workspace/.hf_cache_phase4/qwen2.5-7b \\
        --model-name Qwen/Qwen2.5-7B-Instruct \\
        --output /workspace/.calibration/qwen2.5-7b.qcenters.json \\
        --gpu-memory-utilization 0.30 \\
        --max-model-len 8192 \\
        --max-tokens 100000

Honest scope: this script is "drive the model with a generic
calibration corpus". Partner runs may want to swap the corpus for
prompts representative of the partner's traffic; pass
``--prompts-file <path>`` to provide one prompt per line.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List


def _add_kv_policy_to_path() -> None:
    here = Path(__file__).resolve()
    kv_policy_root = here.parents[3] / "KVPolicy"
    if kv_policy_root.exists():
        sys.path.insert(0, str(kv_policy_root))


_DEFAULT_PROMPTS: List[str] = [
    "The capital of France is Paris, which is famous for the Eiffel Tower built in 1889.",
    "Quantum computing exploits superposition and entanglement to solve certain problems.",
    "Photosynthesis converts light energy into chemical energy stored in glucose molecules.",
    "The mitochondria is the powerhouse of the cell, generating most of its ATP supply.",
    "In machine learning, gradient descent minimises a loss function by iterative updates.",
    "The Roman Empire fell in 476 CE when Odoacer deposed the last western emperor.",
    "DNA is structured as a double helix with adenine pairing to thymine and guanine to cytosine.",
    "Black holes form when massive stars collapse under their own gravitational pull.",
    "The theory of relativity unifies space and time into a four-dimensional spacetime fabric.",
    "Neural networks learn representations through stacked layers of nonlinear transformations.",
]


def _walk_to_torch_model(llm_engine):
    candidate_paths = (
        ("model_executor", "driver_worker", "worker", "model_runner", "model"),
        ("model_executor", "model_runner", "model"),
        ("model_runner", "model"),
    )
    for path in candidate_paths:
        cur = llm_engine
        for attr in path:
            cur = getattr(cur, attr, None)
            if cur is None:
                break
        if cur is not None:
            return cur
    raise RuntimeError(
        "Could not walk vLLM engine to the underlying torch model; "
        "tried paths: " + repr(candidate_paths)
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Path or HF id for vLLM to load.")
    parser.add_argument("--model-name", required=True, help="Identifier saved into the QCenterStats JSON.")
    parser.add_argument("--output", required=True, help="Path to write the QCenterStats JSON.")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.30)
    parser.add_argument("--max-model-len", type=int, default=8192)
    parser.add_argument("--max-tokens", type=int, default=100_000,
                        help="Stop calibration after this many tokens are observed.")
    parser.add_argument("--prompts-file", default=None,
                        help="Optional path to a file of one calibration prompt per line.")
    parser.add_argument("--prompts-multiplier", type=int, default=16,
                        help="Repeat the prompt list this many times to give max_tokens enough work.")
    parser.add_argument("--per-prompt-decode-tokens", type=int, default=64,
                        help="Decode tokens per prompt during calibration drives.")
    parser.add_argument("--corpus-label", default="phase4_calibration",
                        help="Free-form label saved with the stats.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    _add_kv_policy_to_path()

    from vllm import LLM, SamplingParams
    from kv_policy.triattention import calibrate_q_centers

    if args.prompts_file:
        prompts_path = Path(args.prompts_file)
        prompts = [
            line.strip()
            for line in prompts_path.read_text().splitlines()
            if line.strip()
        ]
        if not prompts:
            raise ValueError(f"No prompts in {prompts_path}")
    else:
        prompts = list(_DEFAULT_PROMPTS)
    prompts = prompts * max(1, args.prompts_multiplier)

    llm = LLM(
        model=args.model,
        gpu_memory_utilization=args.gpu_memory_utilization,
        swap_space=4,
        enforce_eager=True,
        max_model_len=args.max_model_len,
        enable_prefix_caching=True,
        seed=args.seed,
    )

    torch_model = _walk_to_torch_model(llm.llm_engine)
    config = torch_model.config
    num_heads = int(config.num_attention_heads)
    num_kv_heads = int(getattr(config, "num_key_value_heads", num_heads))
    head_dim = getattr(config, "head_dim", None)
    if head_dim is None:
        head_dim = int(config.hidden_size) // num_heads
    head_dim = int(head_dim)
    rope_theta = float(getattr(config, "rope_theta", 10000.0))
    # vLLM's Qwen2 / Llama / Mistral models share ONE RotaryEmbedding
    # instance across all transformer layers. The calibrator's
    # default per-module layer indexing therefore pools all 28 layers'
    # Q distributions into one — yielding low MRL (the May 2026 GPU
    # run measured 0.221, below the paper's 0.3 healthy bar). Pass
    # the model's actual layer count so the calibrator uses
    # call-counter indexing and produces per-layer stats.
    num_hidden_layers = int(
        getattr(
            config, "num_hidden_layers",
            getattr(config, "n_layers", num_heads),
        )
    )

    sampling = SamplingParams(
        temperature=0.0,
        max_tokens=args.per_prompt_decode_tokens,
        seed=args.seed,
    )

    def forward_callable(_model):
        llm.generate(prompts, sampling, use_tqdm=False)

    stats = calibrate_q_centers(
        model=torch_model,
        forward_callable=forward_callable,
        model_name=args.model_name,
        num_heads=num_heads,
        num_kv_heads=num_kv_heads,
        head_dim=head_dim,
        num_layers=num_hidden_layers,
        rope_theta=rope_theta,
        corpus_label=args.corpus_label,
        max_tokens=args.max_tokens,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    stats.save(out_path)
    print(
        f"Wrote {out_path} | layers={stats.num_layers} "
        f"kv_heads={stats.num_kv_heads} bands={stats.num_bands} "
        f"tokens={stats.calibration_token_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
