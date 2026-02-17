#!/usr/bin/env python3
"""
BCVF Benchmark CLI — Thin Wrapper for Deployment-Realistic Evaluation
======================================================================

**Architecture**: This CLI is a thin wrapper that:
    1. Parses arguments
    2. Builds config + loads data via DatasetAdapter
    3. Calls BenchmarkRunner / BenchmarkSuite
    4. Prints summary

It contains **zero** decoding logic, metric logic, or benchmark logic.
All of that lives in ``bcvf_benchmarks.py``, ``bcvf_experiments.py``,
and ``bcvf_decoding.py``.

Modes
-----
``wikitext``
    Next-token prediction on WikiText-103 (or fallback texts).
    Goal strategies: lookahead, prompt_mean, random.

``humaneval``
    Code generation on HumanEval (OpenAI).
    Goal: encoded problem description (``code_problem_only``).

``instruction``
    Instruction-following on Alpaca-style data.
    Goal: encoded instruction (``instruction_only``).

``retrieval``
    Retrieval-augmented generation.
    Goal: encoded retrieved context (``retrieval_context``).

``all``
    Run all available benchmarks and produce a unified comparison.

``dry-run``
    Tiny random-weight model, no network.  Verifies the full pipeline
    end-to-end in seconds.

Usage::

    # Quick dry-run (no network, no GPU)
    python scripts/run_bcvf_benchmarks.py --dry-run

    # WikiText with GPT-2 (sanity check)
    python scripts/run_bcvf_benchmarks.py --mode wikitext --model gpt2 --samples 100

    # HumanEval code generation
    python scripts/run_bcvf_benchmarks.py --mode humaneval --model phi3 --samples 164

    # Full suite on a 3B model
    python scripts/run_bcvf_benchmarks.py --mode all --model phi3 --samples 500

    # Sweep goal strategies on wikitext
    python scripts/run_bcvf_benchmarks.py --mode wikitext --model gpt2 \\
        --goal-strategy lookahead prompt_mean random --samples 200

    # Custom BCVF parameters
    python scripts/run_bcvf_benchmarks.py --mode wikitext --model gpt2 \\
        --beta 0.3 --top-m 200 --lambda-c 0.5

    # List supported models
    python scripts/run_bcvf_benchmarks.py --list-models
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import torch

from symbolu.ontological.bcvf_decoding import BCVFDecoder, DecodingConfig
from symbolu.ontological.bcvf_experiments import (
    ExperimentResult,
    ExperimentRunner,
    StepLogger,
    evaluate_energy_stop_conditions,
)
from symbolu.ontological.bcvf_benchmarks import (
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkSuite,
    ComparisonReport,
    bootstrap_pass_at_1_delta,
    bootstrap_spearman,
    compute_verdict,
    print_energy_comparison,
    print_extended_summary,
)
from symbolu.ontological.bcvf_goal_embeddings import GoalEmbeddingFactory
from symbolu.ontological.goal_dirnet import (
    GoalDirNetConfig,
    GoalDirFeatureBuilder,
    GoalDirNet,
    collect_from_dataset_adapter,
    train_goal_dirnet,
    evaluate_goal_dirnet,
    run_alpha_sweep,
    run_goal_dirnet_pipeline,
    print_goal_dirnet_report,
    GoalDirEvalResult,
)
from symbolu.ontological.contrastive_token_ranking import (
    CTRConfig,
    run_ctr_pipeline,
    print_ctr_report,
    CTREvalResult,
)
from symbolu.ontological.bilinear_bcvf import (
    BilinearConfig,
    BilinearScorer,
    run_bilinear_pipeline,
    print_bilinear_report,
    BilinearEvalResult,
)


# =========================================================================
# Model Aliases (reused from validate_bcvf_signal.py)
# =========================================================================

RECOMMENDED_MODELS = {
    "gpt2": "gpt2 (124M — sanity check, fast)",
    "phi2": "microsoft/phi-2 (2.7B — fast iteration)",
    "phi3": "microsoft/phi-3.5-mini-instruct (3.8B — best quality)",
    "stablelm": "stabilityai/stablelm-zephyr-3b (3B — good baseline)",
    "openllama3b": "openlm-research/open_llama_3b_v2 (3B — llama arch)",
}

MODEL_ALIASES = {
    "gpt2": "gpt2",
    "phi2": "microsoft/phi-2",
    "phi-2": "microsoft/phi-2",
    "phi3": "microsoft/phi-3.5-mini-instruct",
    "phi-3": "microsoft/phi-3.5-mini-instruct",
    "phi3.5": "microsoft/phi-3.5-mini-instruct",
    "stablelm": "stabilityai/stablelm-zephyr-3b",
    "stablelm3b": "stabilityai/stablelm-zephyr-3b",
    "openllama": "openlm-research/open_llama_3b_v2",
    "openllama3b": "openlm-research/open_llama_3b_v2",
}


def resolve_model_name(name: str) -> str:
    """Resolve aliases to full HuggingFace model identifiers."""
    return MODEL_ALIASES.get(
        name.lower().replace("-", "").replace("_", ""), name
    )


# =========================================================================
# DatasetAdapter — uniform interface for all benchmark modes
# =========================================================================


class DatasetAdapter:
    """
    Uniform interface: each adapter returns a list of dicts compatible
    with ``ExperimentRunner.run_single_experiment``.

    Required keys per sample:
        hidden_state:   [1, D] float32 tensor
        goal_embedding: [1, D] float32 tensor
        logits:         [1, V] float32 tensor
        ground_truth:   int token id

    Optional metadata keys (for reporting):
        prompt, instruction, context, task_id
    """

    @staticmethod
    def from_wikitext(
        model: Any,
        tokenizer: Any,
        texts: List[str],
        strategy: str,
        n_samples: int,
        device: str = "cpu",
        max_seq_len: int = 512,
    ) -> List[Dict[str, Any]]:
        """
        Collect next-token prediction dataset from text passages.

        Runs the model forward once per passage, extracts per-position
        (hidden_state, logits, ground_truth) tuples, and computes goal
        embeddings with the specified strategy.
        """
        dataset: List[Dict[str, Any]] = []

        for text_idx, text in enumerate(texts):
            if len(dataset) >= n_samples:
                break

            tokens = tokenizer.encode(
                text, return_tensors="pt", truncation=True,
                max_length=max_seq_len,
            ).to(device)

            if tokens.shape[1] < 10:
                continue

            with torch.no_grad():
                outputs = model(
                    tokens, output_hidden_states=True, use_cache=False
                )
                logits_all = outputs.logits           # [1, T, V]
                hidden_all = outputs.hidden_states[-1] # [1, T, D]

            T = tokens.shape[1]
            ground_truth = tokens[0, 1:]  # [T-1]

            # Goal embeddings per position
            goals = _compute_goal_embeddings(
                hidden_all, strategy, prompt_length=T // 4,
            )

            positions = min(T - 1, n_samples - len(dataset))
            for t in range(positions):
                dataset.append({
                    "hidden_state": hidden_all[:, t, :].float(),
                    "goal_embedding": goals[t].unsqueeze(0).float(),
                    "logits": logits_all[:, t, :].float(),
                    "ground_truth": int(ground_truth[t].item()),
                })

            if (text_idx + 1) % 5 == 0:
                print(
                    f"  [{strategy}] Collected "
                    f"{len(dataset)}/{n_samples} positions"
                )

        print(f"  [{strategy}] Total: {len(dataset)} positions")
        return dataset

    @staticmethod
    def from_humaneval(
        model: Any,
        tokenizer: Any,
        n_samples: int,
        device: str = "cpu",
        max_seq_len: int = 512,
        humaneval_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build dataset from HumanEval problems.

        For each problem, tokenises the prompt and collects per-position
        hidden states.  The goal embedding is mean-pooled from the full
        prompt (``code_problem_only`` strategy — the docstring + signature
        IS the goal, no answer leakage).
        """
        problems = _load_humaneval_problems(humaneval_path)
        if not problems:
            print("  WARNING: No HumanEval problems loaded. "
                  "Install: pip install datasets")
            return []

        dataset: List[Dict[str, Any]] = []
        factory = GoalEmbeddingFactory(model=model, tokenizer=tokenizer,
                                       device=device)

        for prob in problems:
            if len(dataset) >= n_samples:
                break

            tokens = tokenizer.encode(
                prob["prompt"], return_tensors="pt", truncation=True,
                max_length=max_seq_len,
            ).to(device)

            if tokens.shape[1] < 5:
                continue

            with torch.no_grad():
                outputs = model(
                    tokens, output_hidden_states=True, use_cache=False
                )
                logits_all = outputs.logits
                hidden_all = outputs.hidden_states[-1]

            T = tokens.shape[1]
            ground_truth = tokens[0, 1:]

            # Goal = mean-pooled prompt hidden states (the problem IS the goal)
            prompt_goal = hidden_all[0].mean(dim=0).unsqueeze(0).float()

            positions = min(T - 1, n_samples - len(dataset))
            for t in range(positions):
                dataset.append({
                    "hidden_state": hidden_all[:, t, :].float(),
                    "goal_embedding": prompt_goal,
                    "logits": logits_all[:, t, :].float(),
                    "ground_truth": int(ground_truth[t].item()),
                    "prompt": prob["prompt"],
                    "task_id": prob.get("task_id", ""),
                })

        print(f"  [humaneval] Total: {len(dataset)} positions "
              f"from {len(problems)} problems")
        return dataset

    @staticmethod
    def from_instruction(
        model: Any,
        tokenizer: Any,
        pairs: List[Dict[str, str]],
        n_samples: int,
        device: str = "cpu",
        max_seq_len: int = 512,
    ) -> List[Dict[str, Any]]:
        """
        Build dataset from instruction-response pairs.

        Goal embedding = mean-pooled hidden states of the instruction
        only (no answer leakage).

        Each pair dict should have ``instruction`` and ``response`` keys.
        """
        dataset: List[Dict[str, Any]] = []

        for pair in pairs:
            if len(dataset) >= n_samples:
                break

            instruction = pair["instruction"]
            response = pair.get("response", "")
            full_text = instruction + " " + response

            tokens = tokenizer.encode(
                full_text, return_tensors="pt", truncation=True,
                max_length=max_seq_len,
            ).to(device)

            if tokens.shape[1] < 10:
                continue

            # Determine instruction boundary
            instr_tokens = tokenizer.encode(
                instruction, return_tensors="pt", truncation=True,
                max_length=max_seq_len,
            )
            instr_len = instr_tokens.shape[1]

            with torch.no_grad():
                outputs = model(
                    tokens, output_hidden_states=True, use_cache=False
                )
                logits_all = outputs.logits
                hidden_all = outputs.hidden_states[-1]

            T = tokens.shape[1]
            ground_truth = tokens[0, 1:]

            # Goal = mean-pooled instruction-only hidden states
            instr_end = min(instr_len, T)
            instr_goal = (
                hidden_all[0, :instr_end].mean(dim=0).unsqueeze(0).float()
            )

            # Collect positions from the response part only
            start_pos = max(instr_end - 1, 0)
            positions = min(T - 1 - start_pos, n_samples - len(dataset))
            for t in range(start_pos, start_pos + positions):
                dataset.append({
                    "hidden_state": hidden_all[:, t, :].float(),
                    "goal_embedding": instr_goal,
                    "logits": logits_all[:, t, :].float(),
                    "ground_truth": int(ground_truth[t].item()),
                    "instruction": instruction,
                })

        print(f"  [instruction] Total: {len(dataset)} positions")
        return dataset

    @staticmethod
    def from_retrieval(
        model: Any,
        tokenizer: Any,
        queries: List[Dict[str, str]],
        corpus: List[str],
        n_samples: int,
        device: str = "cpu",
        max_seq_len: int = 512,
    ) -> List[Dict[str, Any]]:
        """
        Build dataset for retrieval-augmented generation.

        For each query, retrieves the best matching corpus passage by
        cosine similarity and uses it as the goal embedding.

        Query dicts should have ``query`` and ``answer`` keys.
        """
        from symbolu.ontological.bcvf_goal_embeddings import SimpleRetriever

        dataset: List[Dict[str, Any]] = []

        # Build corpus embeddings
        print("  [retrieval] Encoding corpus...")
        corpus_embs = []
        for text in corpus:
            toks = tokenizer.encode(
                text, return_tensors="pt", truncation=True,
                max_length=max_seq_len,
            ).to(device)
            with torch.no_grad():
                out = model(toks, output_hidden_states=True, use_cache=False)
                emb = out.hidden_states[-1][0].mean(dim=0)
                corpus_embs.append(emb)
        corpus_emb_tensor = torch.stack(corpus_embs)  # [N, D]

        retriever = SimpleRetriever(device=device)
        retriever.index_from_embeddings(corpus, corpus_emb_tensor)

        for q in queries:
            if len(dataset) >= n_samples:
                break

            query_text = q["query"]
            answer_text = q.get("answer", "")
            full_text = query_text + " " + answer_text

            tokens = tokenizer.encode(
                full_text, return_tensors="pt", truncation=True,
                max_length=max_seq_len,
            ).to(device)

            if tokens.shape[1] < 10:
                continue

            with torch.no_grad():
                outputs = model(
                    tokens, output_hidden_states=True, use_cache=False
                )
                logits_all = outputs.logits
                hidden_all = outputs.hidden_states[-1]

            T = tokens.shape[1]
            ground_truth = tokens[0, 1:]

            # Retrieve context and use its embedding as goal
            query_emb = hidden_all[0].mean(dim=0).unsqueeze(0)
            hits = retriever.retrieve(query_emb, top_k=1)
            if hits:
                context_text = hits[0]["text"]
                # Encode context for goal embedding
                ctx_toks = tokenizer.encode(
                    context_text, return_tensors="pt", truncation=True,
                    max_length=max_seq_len,
                ).to(device)
                with torch.no_grad():
                    ctx_out = model(
                        ctx_toks, output_hidden_states=True, use_cache=False
                    )
                    ctx_goal = (
                        ctx_out.hidden_states[-1][0]
                        .mean(dim=0).unsqueeze(0).float()
                    )
            else:
                ctx_goal = hidden_all[0].mean(dim=0).unsqueeze(0).float()
                context_text = ""

            positions = min(T - 1, n_samples - len(dataset))
            for t in range(positions):
                dataset.append({
                    "hidden_state": hidden_all[:, t, :].float(),
                    "goal_embedding": ctx_goal,
                    "logits": logits_all[:, t, :].float(),
                    "ground_truth": int(ground_truth[t].item()),
                    "context": context_text,
                })

        print(f"  [retrieval] Total: {len(dataset)} positions")
        return dataset

    @staticmethod
    def from_dry_run(
        n_samples: int = 100,
        hidden_dim: int = 64,
        vocab_size: int = 50,
        strategy: str = "lookahead",
    ) -> List[Dict[str, Any]]:
        """
        Generate a synthetic dataset with random tensors.
        No model, no network, no GPU required.
        """
        torch.manual_seed(42)
        dataset: List[Dict[str, Any]] = []

        for i in range(n_samples):
            h = torch.randn(1, hidden_dim)
            v = torch.randn(vocab_size, hidden_dim)
            logits = h @ v.T
            gt = torch.argmax(logits, dim=-1).item()

            if strategy == "random":
                goal = torch.randn(1, hidden_dim)
            else:
                # lookahead-like: slightly perturbed hidden state
                goal = h + 0.1 * torch.randn(1, hidden_dim)

            dataset.append({
                "hidden_state": h,
                "goal_embedding": goal,
                "logits": logits,
                "ground_truth": gt,
                "prompt": f"dry_run_sample_{i}",
            })

        print(f"  [dry-run/{strategy}] Generated {len(dataset)} samples "
              f"(D={hidden_dim}, V={vocab_size})")
        return dataset


# =========================================================================
# Goal embedding helper (reused from validate_bcvf_signal.py)
# =========================================================================


def _compute_goal_embeddings(
    hidden_states: torch.Tensor,
    strategy: str,
    prompt_length: int = 0,
) -> torch.Tensor:
    """
    Compute goal embeddings for each position.

    Args:
        hidden_states: [1, T, D]
        strategy: lookahead, prompt_mean, or random
        prompt_length: for prompt_mean

    Returns:
        goals: [T, D]
    """
    T, D = hidden_states.shape[1], hidden_states.shape[2]

    if strategy == "lookahead":
        goals = torch.zeros(
            T, D, device=hidden_states.device, dtype=hidden_states.dtype
        )
        goals[:-1] = hidden_states[0, 1:]
        goals[-1] = hidden_states[0, -1]
        return goals

    elif strategy == "prompt_mean":
        if prompt_length < 1:
            prompt_length = max(1, T // 4)
        prompt_hidden = hidden_states[0, :prompt_length]
        mean_goal = prompt_hidden.mean(dim=0)
        return mean_goal.unsqueeze(0).expand(T, -1)

    elif strategy == "random":
        torch.manual_seed(12345)
        return torch.randn(
            T, D, device=hidden_states.device, dtype=hidden_states.dtype
        )

    elif strategy == "bilinear":
        # Bilinear strategy doesn't use goal embeddings — return zeros
        # as a placeholder (decoder bypasses goal when bilinear is set).
        return torch.zeros(
            T, D, device=hidden_states.device, dtype=hidden_states.dtype
        )

    else:
        raise ValueError(f"Unknown strategy: {strategy}")


# =========================================================================
# Data loaders (thin wrappers to external sources)
# =========================================================================


def _load_humaneval_problems(
    path: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Load HumanEval problems from JSONL or HuggingFace."""
    if path is not None:
        p = Path(path)
        if p.exists():
            problems = []
            with open(p) as f:
                for line in f:
                    obj = json.loads(line)
                    problems.append({
                        "task_id": obj["task_id"],
                        "prompt": obj["prompt"],
                    })
            return problems

    try:
        from datasets import load_dataset
        ds = load_dataset("openai_humaneval", split="test")
        return [
            {"task_id": item["task_id"], "prompt": item["prompt"]}
            for item in ds
        ]
    except Exception as exc:
        print(f"  WARNING: Cannot load HumanEval ({exc})")
        return []


def _load_instruction_pairs(
    path: Optional[str] = None,
    max_pairs: int = 500,
) -> List[Dict[str, str]]:
    """Load instruction-response pairs from JSONL or HuggingFace Alpaca."""
    if path is not None:
        p = Path(path)
        if p.exists():
            pairs = []
            with open(p) as f:
                for line in f:
                    obj = json.loads(line)
                    pairs.append({
                        "instruction": obj.get("instruction", obj.get("prompt", "")),
                        "response": obj.get("response", obj.get("output", "")),
                    })
                    if len(pairs) >= max_pairs:
                        break
            return pairs

    try:
        from datasets import load_dataset
        ds = load_dataset("tatsu-lab/alpaca", split="train")
        pairs = []
        for item in ds:
            instr = item.get("instruction", "")
            inp = item.get("input", "")
            if inp:
                instr = instr + "\n" + inp
            pairs.append({
                "instruction": instr,
                "response": item.get("output", ""),
            })
            if len(pairs) >= max_pairs:
                break
        return pairs
    except Exception as exc:
        print(f"  WARNING: Cannot load instruction data ({exc})")
        return []


def _load_retrieval_data(
    path: Optional[str] = None,
    max_queries: int = 200,
) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Load retrieval QA data.  Returns (queries, corpus).

    Falls back to RAG data in data/rag/ if available.
    """
    if path is not None:
        p = Path(path)
        if p.exists():
            with open(p) as f:
                data = json.load(f)
            queries = data.get("queries", [])[:max_queries]
            corpus = data.get("corpus", [])
            return queries, corpus

    # Try loading from local RAG data
    rag_dir = Path(_PROJECT_ROOT) / "data" / "rag"
    if rag_dir.exists():
        corpus = []
        for json_file in sorted(rag_dir.rglob("*.json")):
            try:
                with open(json_file) as f:
                    doc = json.load(f)
                if isinstance(doc, dict) and "content" in doc:
                    corpus.append(doc["content"])
                elif isinstance(doc, list):
                    for item in doc:
                        if isinstance(item, dict) and "content" in item:
                            corpus.append(item["content"])
            except Exception:
                continue

        if corpus:
            # Synthesize queries from corpus passages
            queries = []
            for i, text in enumerate(corpus[:max_queries]):
                words = text.split()[:20]
                queries.append({
                    "query": " ".join(words),
                    "answer": text,
                })
            return queries, corpus

    # Try HuggingFace
    try:
        from datasets import load_dataset
        ds = load_dataset("wikitext", "wikitext-103-raw-v1", split="test")
        texts = [t for t in ds["text"] if len(t.strip()) > 200]
        rng = np.random.RandomState(42)
        rng.shuffle(texts)
        corpus = texts[:100]
        queries = []
        for text in corpus[:max_queries]:
            words = text.split()[:20]
            queries.append({
                "query": " ".join(words),
                "answer": text,
            })
        return queries, corpus
    except Exception as exc:
        print(f"  WARNING: Cannot load retrieval data ({exc})")
        return [], []


def _load_evaluation_texts(
    dataset_name: str = "wikitext",
    max_texts: int = 50,
) -> List[str]:
    """Load text passages for next-token evaluation."""
    try:
        from datasets import load_dataset
    except (ImportError, Exception) as exc:
        print(f"  WARNING: Cannot import datasets ({exc})")
        print("  Falling back to built-in texts")
        return _builtin_fallback_texts()[:max_texts]

    try:
        if dataset_name == "wikitext":
            ds = load_dataset(
                "wikitext", "wikitext-103-raw-v1", split="test"
            )
            texts = [t for t in ds["text"] if len(t.strip()) > 200]
        elif dataset_name == "openwebtext":
            ds = load_dataset("stas/openwebtext-10k", split="train")
            texts = [t for t in ds["text"] if len(t.strip()) > 200]
        elif dataset_name == "c4":
            ds = load_dataset(
                "allenai/c4", "en", split="validation", streaming=True,
            )
            texts = []
            for item in ds:
                if len(item["text"].strip()) > 200:
                    texts.append(item["text"])
                if len(texts) >= max_texts * 2:
                    break
        else:
            raise ValueError(f"Unknown dataset: {dataset_name}")
    except Exception as exc:
        print(f"  WARNING: Dataset load failed ({exc})")
        return _builtin_fallback_texts()[:max_texts]

    rng = np.random.RandomState(42)
    rng.shuffle(texts)
    return texts[:max_texts]


def _builtin_fallback_texts() -> List[str]:
    """Deterministic fallback texts when datasets cannot be loaded."""
    return [
        (
            "The transformer architecture revolutionized natural language "
            "processing by introducing self-attention mechanisms that allow "
            "models to weigh the importance of different parts of the input "
            "sequence simultaneously. Unlike recurrent neural networks, "
            "transformers process all positions in parallel, making them "
            "significantly faster to train on modern hardware. The key "
            "innovation is the scaled dot-product attention, which computes "
            "compatibility scores between query and key vectors, then uses "
            "these scores to create weighted combinations of value vectors. "
        ) * 4,
        (
            "In probability theory, calibration refers to the property that "
            "when a model assigns probability p to an event, that event "
            "should occur approximately p fraction of the time. A perfectly "
            "calibrated classifier has the property that among all instances "
            "where it predicts 70 percent confidence, exactly 70 percent "
            "are correct. Expected Calibration Error measures the average "
            "gap between predicted confidence and actual accuracy across "
            "probability bins. "
        ) * 4,
        (
            "Goal-conditioned reinforcement learning trains agents to reach "
            "specified target states rather than maximizing a single scalar "
            "reward. The agent receives a goal description alongside the "
            "current observation and must learn a policy that generalizes "
            "across different goals. Hindsight experience replay improves "
            "sample efficiency by relabeling failed trajectories with the "
            "actually achieved state as the goal. "
        ) * 4,
        (
            "The softmax function converts a vector of real-valued scores "
            "into a probability distribution by exponentiating each score "
            "and normalizing by the sum. In language models, softmax is "
            "applied to the logit vector to produce next-token "
            "probabilities. Temperature scaling divides logits by a "
            "constant before applying softmax, controlling the sharpness "
            "of the distribution. "
        ) * 4,
    ]


# =========================================================================
# Model loading
# =========================================================================


def load_hf_model(
    model_name: str,
    device: str = "auto",
    dtype: str = "auto",
) -> Tuple[Any, Any]:
    """Load HuggingFace model + tokenizer."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"Loading model: {model_name}")
    print(f"  device={device}, dtype={dtype}")

    torch_dtype = None
    if dtype == "float16":
        torch_dtype = torch.float16
    elif dtype == "bfloat16":
        torch_dtype = torch.bfloat16
    elif dtype == "float32":
        torch_dtype = torch.float32

    for trust_remote in (False, True):
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                model_name, trust_remote_code=trust_remote
            )
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch_dtype,
                device_map=device if device == "auto" else None,
                trust_remote_code=trust_remote,
                low_cpu_mem_usage=True,
            )
            if trust_remote:
                print("  (loaded with trust_remote_code=True)")
            break
        except (ValueError, KeyError, ImportError):
            if trust_remote:
                raise
            print("  Native loading failed, retrying with "
                  "trust_remote_code=True...")
            continue

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if device != "auto":
        model = model.to(device)

    model.eval()
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Loaded: {n_params / 1e9:.2f}B parameters")
    return model, tokenizer


class _DryRunModel(torch.nn.Module):
    """
    Pure-torch tiny model for dry-run.  No transformers dependency.

    Implements the minimal interface needed by the BCVF pipeline:
    - ``get_input_embeddings()`` returning an embedding layer
    - ``forward(input_ids, output_hidden_states=True)`` returning
      an object with ``.logits`` and ``.hidden_states``
    """

    def __init__(self, vocab_size: int = 50, d_model: int = 64):
        super().__init__()
        self.embedding = torch.nn.Embedding(vocab_size, d_model)
        self.linear = torch.nn.Linear(d_model, d_model)
        self.lm_head = torch.nn.Linear(d_model, vocab_size, bias=False)
        # Break weight tying so predictions are random
        with torch.no_grad():
            self.lm_head.weight.copy_(torch.randn_like(self.lm_head.weight))

    def get_input_embeddings(self) -> torch.nn.Embedding:
        return self.embedding

    def forward(
        self,
        input_ids: torch.Tensor,
        output_hidden_states: bool = False,
        use_cache: bool = False,
        **kwargs,
    ):
        emb = self.embedding(input_ids)       # [B, T, D]
        hidden = torch.relu(self.linear(emb))  # [B, T, D]
        logits = self.lm_head(hidden)          # [B, T, V]

        class _Output:
            pass

        out = _Output()
        out.logits = logits
        if output_hidden_states:
            out.hidden_states = (emb, hidden)
        return out


class _MinimalTokenizer:
    """Minimal tokenizer for dry-run.  No transformers dependency."""

    def __init__(self, vocab_size: int = 50):
        self.vocab_size = vocab_size
        self.eos_token_id = 1
        self.pad_token_id = 1
        self.pad_token = "<pad>"
        self.eos_token = "<eos>"

    def encode(self, text: str, return_tensors: str = "pt",
               truncation: bool = True, max_length: int = 256,
               **kwargs) -> torch.Tensor:
        ids = []
        for i, ch in enumerate(text):
            tok = (ord(ch) * 31 + i * 7) % (self.vocab_size - 2) + 2
            ids.append(tok)
        ids = ids[:max_length]
        if return_tensors == "pt":
            return torch.tensor([ids], dtype=torch.long)
        return ids

    def decode(self, ids, skip_special_tokens: bool = True) -> str:
        return f"<decoded {len(ids)} tokens>"


def create_dry_run_model(
    device: str = "cpu",
) -> Tuple[Any, Any]:
    """
    Create a tiny random-weight model for dry-run.  No network.

    Uses transformers GPT2 if available, otherwise falls back to a
    pure-torch stub that implements the same interface.
    """
    try:
        from transformers import GPT2Config, GPT2LMHeadModel

        print("DRY-RUN: Creating tiny GPT-2 model (no network)")
        config = GPT2Config(
            vocab_size=50, n_positions=256, n_embd=64,
            n_layer=2, n_head=2, n_inner=128,
            bos_token_id=0, eos_token_id=1,
        )
        model = GPT2LMHeadModel(config)
        with torch.no_grad():
            model.lm_head.weight = torch.nn.Parameter(
                torch.randn_like(model.lm_head.weight)
            )
    except ImportError:
        print("DRY-RUN: Creating pure-torch stub model (no transformers)")
        model = _DryRunModel(vocab_size=50, d_model=64)

    model.to(device)
    model.eval()

    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Tiny model: {n_params / 1e3:.1f}K params, "
          f"vocab=50, d_model=64")

    tokenizer = _MinimalTokenizer(vocab_size=50)
    return model, tokenizer


# =========================================================================
# Run helpers (thin — delegate to BenchmarkRunner)
# =========================================================================


def run_single_mode(
    mode: str,
    model: Any,
    tokenizer: Any,
    bcvf_config: DecodingConfig,
    goal_strategies: List[str],
    n_samples: int,
    device: str,
    max_seq_len: int,
    n_bootstrap: int,
    dataset_name: str = "wikitext",
    humaneval_path: Optional[str] = None,
    instruction_path: Optional[str] = None,
    retrieval_path: Optional[str] = None,
    is_dry_run: bool = False,
) -> List[BenchmarkResult]:
    """
    Run a single benchmark mode across all goal strategies.

    Returns list of BenchmarkResult (one per strategy or one if mode
    is strategy-agnostic).
    """
    runner = ExperimentRunner(
        model=model,
        tokenizer=tokenizer,
        base_config=bcvf_config,
        device=device,
    )

    energy_mode = "bayesian" if bcvf_config.use_bayesian_energy else "baseline"

    flags_bcvf = {
        "use_rerank": True,
        "use_logit_mod": False,
        "use_calibration": True,
        # use_bayesian_energy inherited from base_config via _make_config
    }
    flags_baseline = {
        "use_rerank": False,
        "use_logit_mod": False,
        "use_calibration": False,
        "use_bayesian_energy": False,  # baseline never uses energy softmax
    }

    results: List[BenchmarkResult] = []

    if mode == "wikitext":
        if is_dry_run:
            texts = _builtin_fallback_texts()
        else:
            texts = _load_evaluation_texts(dataset_name, max_texts=100)
            if not texts:
                texts = _builtin_fallback_texts()

        for strategy in goal_strategies:
            print(f"\n--- WikiText / {strategy} ---")
            if is_dry_run:
                dataset = DatasetAdapter.from_dry_run(
                    n_samples=n_samples, strategy=strategy,
                )
            else:
                dataset = DatasetAdapter.from_wikitext(
                    model, tokenizer, texts, strategy,
                    n_samples, device, max_seq_len,
                )

            if not dataset:
                print(f"  No data for {strategy}, skipping")
                continue

            result_bcvf = runner.run_single_experiment(flags_bcvf, dataset)
            result_base = runner.run_single_experiment(flags_baseline, dataset)

            br = _build_benchmark_result(
                result_bcvf, result_base,
                dataset_name=f"WikiText/{strategy}",
                benchmark_type="wikitext",
                goal_strategy=strategy,
                n_bootstrap=n_bootstrap,
                energy_mode=energy_mode,
            )
            results.append(br)

    elif mode == "humaneval":
        print("\n--- HumanEval ---")
        if is_dry_run:
            dataset = DatasetAdapter.from_dry_run(
                n_samples=n_samples, strategy="lookahead",
            )
        else:
            dataset = DatasetAdapter.from_humaneval(
                model, tokenizer, n_samples, device, max_seq_len,
                humaneval_path,
            )

        if dataset:
            result_bcvf = runner.run_single_experiment(flags_bcvf, dataset)
            result_base = runner.run_single_experiment(flags_baseline, dataset)
            br = _build_benchmark_result(
                result_bcvf, result_base,
                dataset_name="HumanEval",
                benchmark_type="code_gen",
                goal_strategy="code_problem_only",
                n_bootstrap=n_bootstrap,
                energy_mode=energy_mode,
            )
            results.append(br)

    elif mode == "instruction":
        print("\n--- Instruction-Following ---")
        if is_dry_run:
            dataset = DatasetAdapter.from_dry_run(
                n_samples=n_samples, strategy="lookahead",
            )
        else:
            pairs = _load_instruction_pairs(
                instruction_path, max_pairs=500,
            )
            if pairs:
                dataset = DatasetAdapter.from_instruction(
                    model, tokenizer, pairs, n_samples, device, max_seq_len,
                )
            else:
                dataset = []

        if dataset:
            result_bcvf = runner.run_single_experiment(flags_bcvf, dataset)
            result_base = runner.run_single_experiment(flags_baseline, dataset)
            br = _build_benchmark_result(
                result_bcvf, result_base,
                dataset_name="Instruction",
                benchmark_type="instruction",
                goal_strategy="instruction_only",
                n_bootstrap=n_bootstrap,
                energy_mode=energy_mode,
            )
            results.append(br)

    elif mode == "retrieval":
        print("\n--- Retrieval-Augmented ---")
        if is_dry_run:
            dataset = DatasetAdapter.from_dry_run(
                n_samples=n_samples, strategy="lookahead",
            )
        else:
            queries, corpus = _load_retrieval_data(
                retrieval_path, max_queries=200,
            )
            if queries and corpus:
                dataset = DatasetAdapter.from_retrieval(
                    model, tokenizer, queries, corpus,
                    n_samples, device, max_seq_len,
                )
            else:
                dataset = []

        if dataset:
            result_bcvf = runner.run_single_experiment(flags_bcvf, dataset)
            result_base = runner.run_single_experiment(flags_baseline, dataset)
            br = _build_benchmark_result(
                result_bcvf, result_base,
                dataset_name="Retrieval-Aug",
                benchmark_type="retrieval",
                goal_strategy="retrieval_context",
                n_bootstrap=n_bootstrap,
                energy_mode=energy_mode,
            )
            results.append(br)
    else:
        print(f"Unknown mode: {mode}")

    return results


def _build_benchmark_result(
    result_bcvf: ExperimentResult,
    result_base: ExperimentResult,
    dataset_name: str,
    benchmark_type: str,
    goal_strategy: str,
    n_bootstrap: int = 1000,
    energy_mode: str = "baseline",
) -> BenchmarkResult:
    """Build BenchmarkResult with bootstrap CIs from BCVF vs baseline."""
    bcvf_correct = np.array([
        1.0 if s.get("correct") else 0.0
        for s in result_bcvf.per_sample
    ])
    base_correct = np.array([
        1.0 if s.get("correct") else 0.0
        for s in result_base.per_sample
    ])

    delta_ci = bootstrap_pass_at_1_delta(
        base_correct, bcvf_correct,
        n_bootstrap=n_bootstrap, seed=42,
    )

    sb_values = np.array([
        s.get("sb", 0.0) for s in result_bcvf.per_sample
    ])
    sb_ci = bootstrap_spearman(
        sb_values, bcvf_correct,
        n_bootstrap=n_bootstrap, seed=42,
    )

    verdict = compute_verdict(
        result_bcvf.sb_correctness_corr,
        result_bcvf.base_logit_correctness_corr,
    )

    return BenchmarkResult(
        experiment_result=result_bcvf,
        dataset_name=dataset_name,
        benchmark_type=benchmark_type,
        goal_strategy=goal_strategy,
        pass_at_1_delta_ci=delta_ci,
        sb_rho_ci=sb_ci,
        verdict=verdict,
        energy_mode=energy_mode,
    )


# =========================================================================
# CLI Parser
# =========================================================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "BCVF Benchmark CLI — deployment-realistic evaluation "
            "with bootstrap CIs"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join([
            "Modes:",
            "  wikitext      Next-token prediction (WikiText-103)",
            "  humaneval     Code generation (OpenAI HumanEval)",
            "  instruction   Instruction-following (Alpaca)",
            "  retrieval     Retrieval-augmented generation",
            "  all           Run all benchmarks",
            "",
            "Models:",
            *(f"  {k:<14} {v}" for k, v in RECOMMENDED_MODELS.items()),
            "",
            "Examples:",
            "  python scripts/run_bcvf_benchmarks.py --dry-run",
            "  python scripts/run_bcvf_benchmarks.py --mode wikitext "
            "--model gpt2 --samples 100",
            "  python scripts/run_bcvf_benchmarks.py --mode all "
            "--model phi3 --samples 500",
            "  python scripts/run_bcvf_benchmarks.py --mode wikitext "
            "--goal-strategy lookahead prompt_mean random",
            "",
            "GoalDirNet examples:",
            "  python scripts/run_bcvf_benchmarks.py --dry-run "
            "--train-goal-dirnet",
            "  python scripts/run_bcvf_benchmarks.py --mode wikitext "
            "--model gpt2 --train-goal-dirnet --goal-features ht",
            "  python scripts/run_bcvf_benchmarks.py --mode all "
            "--model gpt2 --train-goal-dirnet "
            "--train-goal-samples 5000 --eval-goal-samples 1000",
            "  python scripts/run_bcvf_benchmarks.py --mode wikitext "
            "--model gpt2 --train-goal-dirnet --alpha-sweep 0.05 0.1 0.2",
            "",
            "CTR (Contrastive Token Ranking) examples:",
            "  # Fast kNN-Dir falsification (nonparametric)",
            "  python scripts/run_bcvf_benchmarks.py --dry-run --ctr-knn",
            "  python scripts/run_bcvf_benchmarks.py --mode wikitext "
            "--model phi3 --ctr-knn --ctr-direction delta "
            "--train-goal-samples 10000 --eval-goal-samples 2000",
            "  # Learned contrastive (InfoNCE)",
            "  python scripts/run_bcvf_benchmarks.py --mode wikitext "
            "--model phi3 --train-goal-contrastive --ctr-direction delta",
            "  # Both kNN and learned",
            "  python scripts/run_bcvf_benchmarks.py --mode wikitext "
            "--model phi3 --ctr-knn --train-goal-contrastive",
            "",
            "Bilinear BCVF examples:",
            "  # Dry-run bilinear training + eval",
            "  python scripts/run_bcvf_benchmarks.py --dry-run "
            "--train-bilinear",
            "  # WikiText with bilinear scorer",
            "  python scripts/run_bcvf_benchmarks.py --mode wikitext "
            "--model phi3 --train-bilinear --bilinear-train-samples 10000 "
            "--samples 5000",
            "  # HumanEval gate check",
            "  python scripts/run_bcvf_benchmarks.py --mode humaneval "
            "--model phi3 --samples 1640 --train-bilinear",
            "",
            "Bayesian Energy Softmax examples:",
            "  # Dry-run with default prob_var uncertainty",
            "  python scripts/run_bcvf_benchmarks.py --dry-run "
            "--bayesian-energy",
            "  # WikiText with margin-inverse uncertainty and custom alpha",
            "  python scripts/run_bcvf_benchmarks.py --mode wikitext "
            "--model gpt2 --bayesian-energy --uncertainty margin_inv "
            "--alpha 0.2",
            "  # Full suite with MC-Dropout uncertainty",
            "  python scripts/run_bcvf_benchmarks.py --mode all "
            "--model phi3 --bayesian-energy --uncertainty dropout_var",
            "",
            "Softmax-Entmax Mix examples:",
            "  # Dry-run with default entmax(1.5)",
            "  python scripts/run_bcvf_benchmarks.py --dry-run "
            "--softmax-entmax-mix",
            "  # WikiText with custom gamma thresholds",
            "  python scripts/run_bcvf_benchmarks.py --mode wikitext "
            "--model gpt2 --softmax-entmax-mix --gamma-low 0.5 "
            "--gamma-high 4.0",
            "  # Combined with Bayesian Energy",
            "  python scripts/run_bcvf_benchmarks.py --mode wikitext "
            "--model gpt2 --softmax-entmax-mix --bayesian-energy",
        ]),
    )

    # --- Mode ---
    parser.add_argument(
        "--mode", type=str, default="wikitext",
        choices=["wikitext", "humaneval", "instruction", "retrieval", "all"],
        help="Benchmark mode (default: wikitext)",
    )

    # --- Model ---
    parser.add_argument(
        "--model", type=str, default="gpt2",
        help="HuggingFace model name or alias (default: gpt2)",
    )
    parser.add_argument(
        "--dtype", type=str, default="auto",
        choices=["auto", "float16", "bfloat16", "float32"],
        help="Model dtype (default: auto)",
    )
    parser.add_argument(
        "--device", type=str, default="auto",
        help="Device: auto, cpu, cuda, cuda:0 (default: auto)",
    )

    # --- Dataset ---
    parser.add_argument(
        "--dataset", type=str, default="wikitext",
        choices=["wikitext", "openwebtext", "c4"],
        help="Text dataset for wikitext mode (default: wikitext)",
    )
    parser.add_argument(
        "--samples", type=int, default=500,
        help="Number of token positions to evaluate (default: 500)",
    )
    parser.add_argument(
        "--max-seq-len", type=int, default=512,
        help="Maximum sequence length per passage (default: 512)",
    )

    # --- Goal strategy ---
    parser.add_argument(
        "--goal-strategy", type=str, nargs="+",
        default=["lookahead", "prompt_mean", "random"],
        choices=["lookahead", "prompt_mean", "random", "bilinear"],
        help=(
            "Goal embedding strategies for wikitext mode "
            "(default: lookahead prompt_mean random). "
            "Use 'bilinear' with --train-bilinear for learned scorer."
        ),
    )

    # --- BCVF parameters ---
    parser.add_argument(
        "--beta", type=float, default=0.2,
        help="BCVF beta parameter (default: 0.2)",
    )
    parser.add_argument(
        "--top-m", type=int, default=500,
        help="Top-M candidates for BCVF (default: 500)",
    )
    parser.add_argument(
        "--lambda-c", type=float, default=0.25,
        help="Lambda_c consistency weight (default: 0.25)",
    )

    # --- Bootstrap ---
    parser.add_argument(
        "--n-bootstrap", type=int, default=1000,
        help="Bootstrap resamples for CIs (default: 1000)",
    )

    # --- Data paths (optional overrides) ---
    parser.add_argument(
        "--humaneval-path", type=str, default=None,
        help="Path to HumanEval JSONL file (optional)",
    )
    parser.add_argument(
        "--instruction-path", type=str, default=None,
        help="Path to instruction JSONL file (optional)",
    )
    parser.add_argument(
        "--retrieval-path", type=str, default=None,
        help="Path to retrieval JSON file (optional)",
    )

    # --- Output ---
    parser.add_argument(
        "--output", type=str, default=None,
        help="Path to save JSON report (default: print only)",
    )

    # --- Flags ---
    parser.add_argument(
        "--dry-run", action="store_true",
        help=(
            "Run with tiny random-weight model, no network. "
            "Verifies full pipeline end-to-end."
        ),
    )
    parser.add_argument(
        "--list-models", action="store_true",
        help="List recommended models and exit",
    )

    # --- GoalDirNet flags ---
    parser.add_argument(
        "--train-goal-dirnet", action="store_true",
        help=(
            "Train GoalDirNet to predict future hidden-state direction, "
            "then evaluate its trust score vs logit-derived baselines."
        ),
    )
    parser.add_argument(
        "--goal-features", type=str, default="ht",
        choices=["ht", "ht_mean", "ht_mean_logits"],
        help=(
            "GoalDirNet feature mode: ht (h_t only), ht_mean "
            "(h_t + mean pool), ht_mean_logits (+ logit features). "
            "Default: ht"
        ),
    )
    parser.add_argument(
        "--train-goal-samples", type=int, default=50000,
        help="Number of training positions for GoalDirNet (default: 50000)",
    )
    parser.add_argument(
        "--eval-goal-samples", type=int, default=5000,
        help="Number of eval positions for GoalDirNet (default: 5000)",
    )
    parser.add_argument(
        "--goal-hidden-dim", type=int, default=512,
        help="GoalDirNet MLP hidden dimension (default: 512)",
    )
    parser.add_argument(
        "--goal-epochs", type=int, default=3,
        help="GoalDirNet training epochs (default: 3)",
    )
    parser.add_argument(
        "--goal-lr", type=float, default=1e-3,
        help="GoalDirNet learning rate (default: 1e-3)",
    )
    parser.add_argument(
        "--alpha-sweep", type=float, nargs="*", default=None,
        help=(
            "Run logit modulation alpha sweep (gated by GoalDirNet win). "
            "Pass alpha values, e.g. --alpha-sweep 0.05 0.1 0.2"
        ),
    )

    # --- Contrastive Token Ranking (CTR) flags ---
    parser.add_argument(
        "--ctr-knn", action="store_true",
        help=(
            "Run kNN-Dir nonparametric CTR baseline. "
            "Fast falsification: if kNN fails, no learned model will help."
        ),
    )
    parser.add_argument(
        "--train-goal-contrastive", action="store_true",
        help=(
            "Train ContrastiveGoalNet with InfoNCE loss. "
            "Discriminative alternative to direction regression."
        ),
    )
    parser.add_argument(
        "--ctr-direction", type=str, default="delta",
        choices=["delta", "htp1"],
        help=(
            "Direction mode for CTR: delta = normalize(h_{t+1} - h_t), "
            "htp1 = normalize(h_{t+1}). Default: delta"
        ),
    )
    parser.add_argument(
        "--ctr-knn-k", type=int, default=32,
        help="Number of kNN neighbours for CTR (default: 32)",
    )
    parser.add_argument(
        "--ctr-tau", type=float, default=0.07,
        help="InfoNCE temperature for contrastive training (default: 0.07)",
    )
    parser.add_argument(
        "--ctr-epochs", type=int, default=5,
        help="ContrastiveGoalNet training epochs (default: 5)",
    )

    # --- Bilinear BCVF flags ---
    parser.add_argument(
        "--train-bilinear", action="store_true",
        help=(
            "Train BilinearScorer (low-rank bilinear metric learning) "
            "then evaluate as BCVF backward score replacement."
        ),
    )
    parser.add_argument(
        "--bilinear-rank", type=int, default=64,
        help="Low-rank dimension for bilinear projections U, V (default: 64)",
    )
    parser.add_argument(
        "--bilinear-train-samples", type=int, default=10000,
        help="Number of training positions for BilinearScorer (default: 10000)",
    )
    parser.add_argument(
        "--bilinear-eval-samples", type=int, default=5000,
        help="Number of eval positions for BilinearScorer (default: 5000)",
    )
    parser.add_argument(
        "--bilinear-use-sigmoid", action="store_true", default=True,
        help="Apply sigmoid to bilinear scores (default: True)",
    )
    parser.add_argument(
        "--bilinear-no-sigmoid", action="store_true", default=False,
        help="Disable sigmoid on bilinear scores (use raw scores).",
    )
    parser.add_argument(
        "--bilinear-epochs", type=int, default=3,
        help="BilinearScorer training epochs (default: 3)",
    )
    parser.add_argument(
        "--bilinear-lr", type=float, default=1e-3,
        help="BilinearScorer learning rate (default: 1e-3)",
    )
    parser.add_argument(
        "--bilinear-train-top-m", type=int, default=50,
        help=(
            "Candidate pool size during bilinear training (default: 50). "
            "Smaller = harder negatives.  Separate from --top-m (eval)."
        ),
    )

    # --- Bayesian Energy Softmax flags ---
    parser.add_argument(
        "--bayesian-energy", action="store_true",
        help=(
            "Enable Bayesian Energy Softmax: z'_y = z_y + α·σ²_y − β·penalty. "
            "Modifies logits before softmax at decode time."
        ),
    )
    parser.add_argument(
        "--alpha", type=float, default=0.1,
        help="Bayesian Energy α — uncertainty scaling (default: 0.1)",
    )
    parser.add_argument(
        "--energy-beta", type=float, default=0.0,
        help="Bayesian Energy β — penalty scaling (default: 0.0)",
    )
    parser.add_argument(
        "--uncertainty", type=str, default="prob_var",
        choices=["prob_var", "dropout_var", "margin_inv", "entropy_temp"],
        help=(
            "Uncertainty estimator for Bayesian Energy Softmax. "
            "prob_var: p(1-p), margin_inv: 1/(margin+ε), "
            "dropout_var: MC-Dropout variance, "
            "entropy_temp: entropy-conditioned temperature scaling "
            "(default: prob_var)"
        ),
    )

    # --- Softmax-Entmax Mix flags ---
    parser.add_argument(
        "--softmax-entmax-mix", action="store_true",
        help=(
            "Enable entropy-gated softmax + entmax(α) mixture at decode "
            "time.  In uncertain (high-entropy) regimes, entmax sparsifies "
            "the distribution; in confident regimes, softmax is preserved."
        ),
    )
    parser.add_argument(
        "--entmax-alpha", type=float, default=1.5,
        help="Entmax Tsallis alpha (> 1, default: 1.5)",
    )
    parser.add_argument(
        "--gamma-low", type=float, default=1.0,
        help=(
            "Lower entropy threshold for gamma ramp.  Below this entropy "
            "gamma=0 (pure softmax).  Default: 1.0"
        ),
    )
    parser.add_argument(
        "--gamma-high", type=float, default=5.0,
        help=(
            "Upper entropy threshold for gamma ramp.  Above this entropy "
            "gamma=1 (pure entmax).  Default: 5.0"
        ),
    )

    return parser


# =========================================================================
# Main — thin wrapper: parse → config → run → print
# =========================================================================


def main(argv: Optional[List[str]] = None) -> ComparisonReport:
    """
    CLI entry point.

    Args:
        argv: Optional argument list (for testing). Uses sys.argv if None.

    Returns:
        ComparisonReport for programmatic access.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_models:
        print("Recommended models for BCVF benchmarks:")
        print()
        for alias, desc in RECOMMENDED_MODELS.items():
            print(f"  {alias:<14} {desc}")
        print()
        print("Use --model <alias> or --model <full-hf-name>")
        return ComparisonReport()

    # --- Resolve device ---
    device = args.device
    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"

    # --- BCVF config ---
    top_m = args.top_m
    if args.dry_run:
        top_m = min(top_m, 25)
        args.samples = min(args.samples, 200)
        args.max_seq_len = min(args.max_seq_len, 256)

    bcvf_config = DecodingConfig(
        top_m=top_m,
        beta=args.beta,
        lambda_c=args.lambda_c,
        use_rerank=True,
        use_calibration=True,
        use_logit_mod=False,
        # Bayesian Energy Softmax
        use_bayesian_energy=args.bayesian_energy,
        energy_alpha=args.alpha,
        energy_beta=args.energy_beta,
        uncertainty_mode=args.uncertainty,
        # Softmax-Entmax Mix
        use_softmax_entmax_mix=args.softmax_entmax_mix,
        entmax_alpha=args.entmax_alpha,
        gamma_low=args.gamma_low,
        gamma_high=args.gamma_high,
    )

    # --- Load model ---
    if args.dry_run:
        model, tokenizer = create_dry_run_model(device=device)
        model_name = "dry-run-tiny-random"
    else:
        model_name = resolve_model_name(args.model)
        model, tokenizer = load_hf_model(model_name, device, args.dtype)

    effective_device = str(next(model.parameters()).device)
    n_params = sum(p.numel() for p in model.parameters())

    # --- Header ---
    print(f"\n{'='*70}")
    print("BCVF Benchmark Suite")
    print(f"  Model:   {model_name} ({n_params / 1e9:.2f}B params)")
    print(f"  Device:  {effective_device}")
    print(f"  Mode:    {args.mode}")
    print(f"  Samples: {args.samples}")
    print(f"  BCVF:    top_m={bcvf_config.top_m}, beta={bcvf_config.beta}, "
          f"lambda_c={bcvf_config.lambda_c}")
    print(f"  Bootstrap: {args.n_bootstrap} resamples")
    if args.mode == "wikitext":
        print(f"  Strategies: {args.goal_strategy}")
    if args.bayesian_energy:
        print(f"  Energy:  α={args.alpha}, β={args.energy_beta}, "
              f"uncertainty={args.uncertainty}")
    if args.softmax_entmax_mix:
        print(f"  Entmax:  α={args.entmax_alpha}, "
              f"γ_low={args.gamma_low}, γ_high={args.gamma_high}")
    print(f"{'='*70}")

    # --- GoalDirNet config ---
    goal_config = None
    if args.train_goal_dirnet:
        goal_train = args.train_goal_samples
        goal_eval = args.eval_goal_samples
        if args.dry_run:
            goal_train = min(goal_train, 500)
            goal_eval = min(goal_eval, 100)
        goal_config = GoalDirNetConfig(
            feature_mode=args.goal_features,
            hidden_dim=args.goal_hidden_dim,
            train_samples=goal_train,
            eval_samples=goal_eval,
            epochs=args.goal_epochs,
            lr=args.goal_lr,
            alpha_values=args.alpha_sweep or [0.05, 0.1, 0.2],
        )
        print(f"  GoalDirNet: features={goal_config.feature_mode}, "
              f"hidden={goal_config.hidden_dim}, "
              f"train={goal_config.train_samples}, "
              f"eval={goal_config.eval_samples}")

    # --- CTR config ---
    ctr_config = None
    run_ctr = args.ctr_knn or args.train_goal_contrastive
    if run_ctr:
        ctr_train = args.train_goal_samples
        ctr_eval = args.eval_goal_samples
        if args.dry_run:
            ctr_train = min(ctr_train, 500)
            ctr_eval = min(ctr_eval, 100)
        ctr_config = CTRConfig(
            direction_mode=args.ctr_direction,
            knn_k=args.ctr_knn_k,
            top_m=top_m,
            tau=args.ctr_tau,
            hidden_dim=args.goal_hidden_dim,
            lr=args.goal_lr,
            epochs=args.ctr_epochs,
            train_samples=ctr_train,
            eval_samples=ctr_eval,
            alpha_values=args.alpha_sweep or [0.01, 0.02, 0.05],
        )
        print(f"  CTR: direction={ctr_config.direction_mode}, "
              f"knn_k={ctr_config.knn_k}, "
              f"knn={args.ctr_knn}, learned={args.train_goal_contrastive}, "
              f"train={ctr_config.train_samples}, "
              f"eval={ctr_config.eval_samples}")

    # --- Bilinear BCVF config ---
    bilinear_config = None
    if args.train_bilinear:
        bl_train = args.bilinear_train_samples
        bl_eval = args.bilinear_eval_samples
        if args.dry_run:
            bl_train = min(bl_train, 500)
            bl_eval = min(bl_eval, 100)
        use_sigmoid = args.bilinear_use_sigmoid and not args.bilinear_no_sigmoid
        bilinear_config = BilinearConfig(
            rank=args.bilinear_rank,
            use_sigmoid=use_sigmoid,
            top_m=top_m,
            train_top_m=args.bilinear_train_top_m,
            lr=args.bilinear_lr,
            epochs=args.bilinear_epochs,
            train_samples=bl_train,
            eval_samples=bl_eval,
            alpha_values=args.alpha_sweep or [0.01, 0.02, 0.05, 0.1],
        )
        print(f"  Bilinear: rank={bilinear_config.rank}, "
              f"sigmoid={use_sigmoid}, "
              f"train_top_m={bilinear_config.train_top_m}, "
              f"train={bilinear_config.train_samples}, "
              f"eval={bilinear_config.eval_samples}, "
              f"epochs={bilinear_config.epochs}")

    # --- Determine modes to run ---
    if args.mode == "all":
        modes = ["wikitext", "humaneval", "instruction", "retrieval"]
    else:
        modes = [args.mode]

    # --- Run benchmarks ---
    all_results: List[BenchmarkResult] = []
    goal_datasets: Dict[str, List[Dict[str, Any]]] = {}
    t0 = time.time()

    for mode in modes:
        print(f"\n{'─'*50}")
        print(f"Running: {mode}")
        print(f"{'─'*50}")

        mode_results = run_single_mode(
            mode=mode,
            model=model,
            tokenizer=tokenizer,
            bcvf_config=bcvf_config,
            goal_strategies=args.goal_strategy,
            n_samples=args.samples,
            device=effective_device,
            max_seq_len=args.max_seq_len,
            n_bootstrap=args.n_bootstrap,
            dataset_name=args.dataset,
            humaneval_path=args.humaneval_path,
            instruction_path=args.instruction_path,
            retrieval_path=args.retrieval_path,
            is_dry_run=args.dry_run,
        )
        all_results.extend(mode_results)

        # Collect datasets for GoalDirNet / CTR / Bilinear if requested
        if args.train_goal_dirnet or run_ctr or args.train_bilinear:
            if goal_config is not None:
                goal_n = goal_config.train_samples + goal_config.eval_samples
            elif ctr_config is not None:
                goal_n = ctr_config.train_samples + ctr_config.eval_samples
            elif bilinear_config is not None:
                goal_n = bilinear_config.train_samples + bilinear_config.eval_samples
            else:
                goal_n = 10000
            if mode == "wikitext":
                # Use first goal strategy for GoalDirNet data
                strategy = args.goal_strategy[0]
                if args.dry_run:
                    gd_data = DatasetAdapter.from_dry_run(
                        n_samples=goal_n,
                        strategy=strategy,
                    )
                else:
                    texts = _load_evaluation_texts(
                        args.dataset, max_texts=100,
                    )
                    if not texts:
                        texts = _builtin_fallback_texts()
                    gd_data = DatasetAdapter.from_wikitext(
                        model, tokenizer, texts, strategy,
                        goal_n, effective_device, args.max_seq_len,
                    )
                goal_datasets[f"WikiText/{strategy}"] = gd_data
            elif mode == "humaneval":
                if args.dry_run:
                    gd_data = DatasetAdapter.from_dry_run(
                        n_samples=goal_n, strategy="lookahead",
                    )
                else:
                    gd_data = DatasetAdapter.from_humaneval(
                        model, tokenizer, goal_n, effective_device,
                        args.max_seq_len, args.humaneval_path,
                    )
                goal_datasets["HumanEval"] = gd_data
            elif mode == "instruction":
                if args.dry_run:
                    gd_data = DatasetAdapter.from_dry_run(
                        n_samples=goal_n, strategy="lookahead",
                    )
                else:
                    pairs = _load_instruction_pairs(
                        args.instruction_path, max_pairs=500,
                    )
                    if pairs:
                        gd_data = DatasetAdapter.from_instruction(
                            model, tokenizer, pairs, goal_n,
                            effective_device, args.max_seq_len,
                        )
                    else:
                        gd_data = []
                goal_datasets["Instruction"] = gd_data
            elif mode == "retrieval":
                if args.dry_run:
                    gd_data = DatasetAdapter.from_dry_run(
                        n_samples=goal_n, strategy="lookahead",
                    )
                else:
                    queries, corpus = _load_retrieval_data(
                        args.retrieval_path, max_queries=200,
                    )
                    if queries and corpus:
                        gd_data = DatasetAdapter.from_retrieval(
                            model, tokenizer, queries, corpus,
                            goal_n, effective_device, args.max_seq_len,
                        )
                    else:
                        gd_data = []
                goal_datasets["Retrieval"] = gd_data

    elapsed = time.time() - t0

    # --- Build report ---
    report = ComparisonReport(
        results=all_results,
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
    )

    # --- Print comparison table ---
    print(f"\n{'='*70}")
    table = BenchmarkSuite.print_comparison(report)

    print(f"\nTotal time: {elapsed:.1f}s")

    # --- Extended summary with bootstrap CIs ---
    if all_results:
        print()
        print_extended_summary(all_results)

    # --- Bayesian Energy Softmax comparison ---
    if args.bayesian_energy and all_results:
        print(f"\n{'='*70}")
        print("Bayesian Energy Softmax — Stop-Condition Evaluation")
        print(f"{'='*70}")

        # Re-run baselines without energy to get reference results
        baseline_config = DecodingConfig(
            top_m=bcvf_config.top_m,
            beta=bcvf_config.beta,
            lambda_c=bcvf_config.lambda_c,
            use_rerank=True,
            use_calibration=True,
            use_logit_mod=False,
            use_bayesian_energy=False,
        )
        baseline_runner = ExperimentRunner(
            model=model, tokenizer=tokenizer,
            base_config=baseline_config, device=effective_device,
        )
        baseline_flags = {
            "use_rerank": True,
            "use_logit_mod": False,
            "use_calibration": True,
            "use_bayesian_energy": False,
        }

        # Collect baseline results for each dataset (rerun without energy)
        baseline_bench: List[BenchmarkResult] = []
        for mode in modes:
            if mode == "wikitext":
                for strategy in args.goal_strategy:
                    if args.dry_run:
                        ds = DatasetAdapter.from_dry_run(
                            n_samples=args.samples, strategy=strategy,
                        )
                    else:
                        texts = _load_evaluation_texts(
                            args.dataset, max_texts=100,
                        )
                        if not texts:
                            texts = _builtin_fallback_texts()
                        ds = DatasetAdapter.from_wikitext(
                            model, tokenizer, texts, strategy,
                            args.samples, effective_device,
                            args.max_seq_len,
                        )
                    if ds:
                        res_bl = baseline_runner.run_single_experiment(
                            baseline_flags, ds
                        )
                        res_no = baseline_runner.run_single_experiment(
                            {"use_rerank": False, "use_logit_mod": False,
                             "use_calibration": False,
                             "use_bayesian_energy": False}, ds
                        )
                        baseline_bench.append(_build_benchmark_result(
                            res_bl, res_no,
                            dataset_name=f"WikiText/{strategy}",
                            benchmark_type="wikitext",
                            goal_strategy=strategy,
                            n_bootstrap=args.n_bootstrap,
                            energy_mode="baseline",
                        ))

        if baseline_bench and all_results:
            print_energy_comparison(
                baseline_bench, all_results,
                alpha=args.alpha,
                energy_beta=args.energy_beta,
                uncertainty_mode=args.uncertainty,
            )

    # --- GoalDirNet training + evaluation ---
    if args.train_goal_dirnet and goal_datasets:
        print(f"\n{'='*70}")
        print("GoalDirNet Training & Evaluation")
        print(f"{'='*70}")

        t1 = time.time()
        run_sweep = args.alpha_sweep is not None
        goal_eval_results, alpha_sweep_results = run_goal_dirnet_pipeline(
            model=model,
            tokenizer=tokenizer,
            datasets=goal_datasets,
            config=goal_config,
            device=effective_device,
            run_alpha_sweep_flag=run_sweep,
        )

        goal_elapsed = time.time() - t1
        print(f"\nGoalDirNet time: {goal_elapsed:.1f}s")

        # Print report
        if goal_eval_results:
            print_goal_dirnet_report(goal_eval_results, alpha_sweep_results)

    # --- CTR: Contrastive Token Ranking ---
    if run_ctr and goal_datasets:
        print(f"\n{'='*70}")
        print("Contrastive Token Ranking (CTR)")
        print(f"{'='*70}")

        t2 = time.time()
        ctr_results = run_ctr_pipeline(
            model=model,
            tokenizer=tokenizer,
            datasets=goal_datasets,
            config=ctr_config,
            device=effective_device,
            run_knn=args.ctr_knn,
            run_learned=args.train_goal_contrastive,
            run_nonparametric=True,
        )

        ctr_elapsed = time.time() - t2
        print(f"\nCTR time: {ctr_elapsed:.1f}s")

        if ctr_results:
            print_ctr_report(ctr_results)

    # --- Bilinear BCVF training + evaluation ---
    if args.train_bilinear and goal_datasets:
        print(f"\n{'='*70}")
        print("Bilinear BCVF (Low-Rank Metric Learning)")
        print(f"{'='*70}")

        t3 = time.time()
        bilinear_results, bilinear_loss_curves = run_bilinear_pipeline(
            model=model,
            tokenizer=tokenizer,
            datasets=goal_datasets,
            config=bilinear_config,
            device=effective_device,
        )

        bilinear_elapsed = time.time() - t3
        print(f"\nBilinear time: {bilinear_elapsed:.1f}s")

        if bilinear_results:
            print_bilinear_report(bilinear_results, bilinear_loss_curves)

    # --- Save if requested ---
    if args.output:
        BenchmarkSuite.save_report(report, args.output)
        print(f"\nReport saved to: {args.output}")

    return report


if __name__ == "__main__":
    main()
