#!/usr/bin/env python
"""§13 experiment — semantic-entropy probe on TruthfulQA-MC.

Reference: Farquhar, Kossen, Kuhn, Gal (2024). "Detecting hallucinations
in large language models using semantic entropy." Nature 630, 625-630.

Intent:
  The probability-simplex BCVF probe (§12, §13) returned a clean null
  on TruthfulQA (all 11 observables AUC in [0.476, 0.527] at N=100).
  Literature predicts this null — same-family logit-space disagreement
  is a known dead end. The published working technique is semantic
  entropy: sample K completions, cluster by bidirectional NLI
  entailment, compute entropy over cluster sizes.

  This script replicates that technique on TruthfulQA-MC as a §13
  revision test. If semantic entropy clears AUC 0.60, the BCVF-for-
  LLM hypothesis is revived under a meaning-space metric (§2.2
  revision). If it does not clear 0.60, the null strengthens to a
  field-consistent result.

Protocol:
  1. For each TruthfulQA-MC question, sample K completions from the
     target model at T=1.0, max_new_tokens=32.
  2. Also generate one greedy completion (T=0, deterministic) for
     the correctness label.
  3. Cluster the K stochastic samples by bidirectional NLI
     entailment using an MNLI-trained model.
  4. Compute semantic entropy = Shannon entropy over cluster sizes.
  5. Label correctness: greedy generation matches the correct MC
     choice (highest NLI entailment) more than any distractor.
  6. Compute AUC of (-semantic_entropy) as a correctness predictor
     (higher entropy → less confident → more likely wrong, so
     negate for AUC convention of "higher = more truth-predictive").

Pre-committed success criteria (§13 revision):
  - AUC ≥ 0.70 → STRONG pass, semantic-entropy BCVF replacement
    authorized, §2.2 metric revision lands.
  - 0.60 ≤ AUC < 0.70 → MARGINAL pass, expand to HaluEval for
    cross-benchmark confirmation before §2.2 revision.
  - 0.55 ≤ AUC < 0.60 → NOISE BAND, no revision authorized.
  - AUC < 0.55 → SECOND NULL, §13 null result strengthened to
    field-consistent; pause LLM track pending §1.3 cross-family
    ensemble revision.

Usage:
    HF_HUB_DISABLE_XET=1 python scripts/probe_semantic_entropy.py \\
        --num-questions 100 \\
        --model Qwen/Qwen2.5-7B-Instruct \\
        --k-samples 10

~30-45 min on a single GPU with Qwen-7B + DeBERTa-v3-base-MNLI.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@dataclass
class QuestionResult:
    q_idx: int
    prompt: str
    correct_choice: str
    distractors: List[str]
    samples: List[str]
    greedy: str
    cluster_ids: List[int]
    num_clusters: int
    semantic_entropy: float
    greedy_matches_correct: bool
    label: int  # 1 = correct, 0 = wrong


def build_nli_checker(nli_model, nli_tokenizer, device: str):
    """Return a function (premise, hypothesis) -> bool that tests entailment.

    Uses the standard MNLI 3-class (entailment / neutral / contradiction)
    head; returns True iff argmax class is "entailment".
    """
    import torch

    ent_idx = None
    if hasattr(nli_model.config, "label2id"):
        for k, v in nli_model.config.label2id.items():
            if "entail" in k.lower():
                ent_idx = int(v)
                break
    if ent_idx is None:
        ent_idx = 0

    @torch.inference_mode()
    def check(premise: str, hypothesis: str) -> bool:
        enc = nli_tokenizer(
            premise, hypothesis,
            return_tensors="pt", truncation=True, max_length=512,
        ).to(device)
        logits = nli_model(**enc).logits[0]
        return int(torch.argmax(logits).item()) == ent_idx

    return check


def cluster_by_entailment(
    samples: List[str], check_entailment,
) -> List[int]:
    """Union-find clustering by bidirectional NLI entailment.

    Two samples are in the same cluster iff each entails the other.
    Returns a cluster-id list aligned with `samples`.
    """
    n = len(samples)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if check_entailment(samples[i], samples[j]) and \
               check_entailment(samples[j], samples[i]):
                union(i, j)

    # Normalize cluster ids to 0..num_clusters-1.
    roots = [find(i) for i in range(n)]
    canon = {r: idx for idx, r in enumerate(sorted(set(roots)))}
    return [canon[r] for r in roots]


def semantic_entropy_nats(cluster_ids: List[int]) -> float:
    """Shannon entropy (nats) over cluster-size distribution."""
    k = len(cluster_ids)
    sizes = Counter(cluster_ids).values()
    p = np.array([s / k for s in sizes], dtype=np.float64)
    return float(-np.sum(p * np.log(p)))


def generate_samples(
    model, tokenizer, prompt: str, k: int, temperature: float,
    max_new_tokens: int, device: str, seed: int,
) -> List[str]:
    """Sample `k` completions from `model`. Returns decoded strings.

    Strips the prompt prefix so returned strings are generations only.
    """
    import torch

    torch.manual_seed(seed)
    enc = tokenizer(prompt, return_tensors="pt", add_special_tokens=True)
    input_ids = enc.input_ids.to(device)
    attention_mask = torch.ones_like(input_ids)
    prompt_len = input_ids.shape[1]

    with torch.inference_mode():
        out = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            do_sample=True,
            temperature=temperature,
            num_return_sequences=k,
            max_new_tokens=max_new_tokens,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
    gens = out[:, prompt_len:]
    return [
        tokenizer.decode(g, skip_special_tokens=True).strip()
        for g in gens
    ]


def generate_greedy(
    model, tokenizer, prompt: str, max_new_tokens: int, device: str,
) -> str:
    import torch

    enc = tokenizer(prompt, return_tensors="pt", add_special_tokens=True)
    input_ids = enc.input_ids.to(device)
    attention_mask = torch.ones_like(input_ids)
    prompt_len = input_ids.shape[1]

    with torch.inference_mode():
        out = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            do_sample=False,
            max_new_tokens=max_new_tokens,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
    gen = out[0, prompt_len:]
    return tokenizer.decode(gen, skip_special_tokens=True).strip()


def label_correctness(
    greedy_gen: str, correct_choice: str, distractors: List[str],
    check_entailment,
) -> bool:
    """Greedy generation is correct iff it entails the correct choice
    but does not entail any distractor."""
    entails_correct = check_entailment(greedy_gen, correct_choice)
    entails_any_distractor = any(
        check_entailment(greedy_gen, d) for d in distractors
    )
    return bool(entails_correct and not entails_any_distractor)


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Binary AUC via tie-aware rank sum. Matches observables/base.py."""
    labels = labels.astype(bool)
    n_pos = int(labels.sum())
    n_neg = int(labels.size - n_pos)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=np.float64)
    i = 0
    while i < len(scores):
        j = i
        while j + 1 < len(scores) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    rank_sum_pos = float(ranks[labels].sum())
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def classify(auc: float) -> Tuple[str, str]:
    if auc >= 0.70:
        return "TRUTH_CORRELATED_STRONG", (
            "Semantic-entropy replacement authorized. §2.2 metric "
            "revision lands. Next: HaluEval cross-benchmark + §1.3 "
            "independent-family ensemble as the full revision."
        )
    if auc >= 0.60:
        return "TRUTH_CORRELATED_MARGINAL", (
            "Marginal pass. Expand to HaluEval cross-benchmark before "
            "§2.2 revision lands. Compare AUC across benchmarks to "
            "verify robustness."
        )
    if auc >= 0.55:
        return "NOISE_BAND_LIFT", (
            "Above random but below §11 bar. No revision authorized. "
            "Consider whether sampling temperature / K are sub-optimal."
        )
    return "SECOND_NULL", (
        "Second null result. §13 null strengthens to field-consistent. "
        "Pause LLM track pending §1.3 independent-family ensemble "
        "revision (the only remaining literature-backed fix)."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-questions", type=int, default=100)
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument(
        "--nli-model",
        default="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        help="MNLI-trained classifier for entailment checks.",
    )
    parser.add_argument("--k-samples", type=int, default=10,
                        help="Samples per question (Farquhar 2024 uses 10).")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--out-dir", type=pathlib.Path,
        default=_REPO_ROOT / "docs" / "experiments",
    )
    parser.add_argument("--suffix", type=str, default="")
    parser.add_argument(
        "--dump-json", action="store_true",
        help="Also write a per-question JSON dump next to the report.",
    )
    args = parser.parse_args()

    import torch
    from datasets import load_dataset
    from transformers import (
        AutoModelForCausalLM, AutoModelForSequenceClassification,
        AutoTokenizer,
    )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}", flush=True)

    print(f"Loading target model: {args.model}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.float16, device_map=device,
    )
    model.eval()

    print(f"Loading NLI model: {args.nli_model}", flush=True)
    nli_tokenizer = AutoTokenizer.from_pretrained(args.nli_model)
    nli_model = AutoModelForSequenceClassification.from_pretrained(
        args.nli_model,
    ).to(device)
    nli_model.eval()
    check_entailment = build_nli_checker(nli_model, nli_tokenizer, device)

    print("Loading TruthfulQA (multiple_choice, validation) ...", flush=True)
    ds = load_dataset("truthful_qa", "multiple_choice", split="validation")
    ds = ds.select(range(min(args.num_questions, len(ds))))

    results: List[QuestionResult] = []
    t_start = time.perf_counter()

    for q_idx, row in enumerate(ds):
        q_text = row["question"]
        choices = list(row["mc1_targets"]["choices"])
        labels = list(row["mc1_targets"]["labels"])
        correct_index = int(labels.index(1))
        correct_choice = choices[correct_index]
        distractors = [c for i, c in enumerate(choices) if i != correct_index]

        prompt = f"Q: {q_text}\nA:"

        samples = generate_samples(
            model, tokenizer, prompt,
            k=args.k_samples, temperature=args.temperature,
            max_new_tokens=args.max_new_tokens, device=device,
            seed=args.seed + q_idx,
        )
        greedy = generate_greedy(
            model, tokenizer, prompt,
            max_new_tokens=args.max_new_tokens, device=device,
        )

        cluster_ids = cluster_by_entailment(samples, check_entailment)
        sem_entropy = semantic_entropy_nats(cluster_ids)
        is_correct = label_correctness(
            greedy, correct_choice, distractors, check_entailment,
        )

        results.append(QuestionResult(
            q_idx=q_idx, prompt=prompt,
            correct_choice=correct_choice, distractors=distractors,
            samples=samples, greedy=greedy,
            cluster_ids=cluster_ids,
            num_clusters=len(set(cluster_ids)),
            semantic_entropy=sem_entropy,
            greedy_matches_correct=is_correct,
            label=1 if is_correct else 0,
        ))

        if (q_idx + 1) % 5 == 0 or q_idx + 1 == len(ds):
            elapsed = time.perf_counter() - t_start
            eta = elapsed / (q_idx + 1) * (len(ds) - q_idx - 1)
            n_correct = sum(r.label for r in results)
            print(
                f"  [{q_idx + 1}/{len(ds)}] elapsed={elapsed:.0f}s "
                f"eta={eta:.0f}s correct={n_correct}/{len(results)} "
                f"mean_entropy={np.mean([r.semantic_entropy for r in results]):.3f}",
                flush=True,
            )

    # Compute AUC. Semantic entropy is "higher = more suspicious", so for
    # AUC-as-truth-predictor we negate.
    scalars = np.array([r.semantic_entropy for r in results], dtype=np.float64)
    labels_np = np.array([r.label for r in results], dtype=np.float64)
    auc = roc_auc(-scalars, labels_np.astype(bool))
    classification, recommendation = classify(auc)

    mean_correct = (
        float(scalars[labels_np == 1.0].mean())
        if (labels_np == 1.0).any() else 0.0
    )
    mean_wrong = (
        float(scalars[labels_np == 0.0].mean())
        if (labels_np == 0.0).any() else 0.0
    )
    n_pos = int(labels_np.sum())
    n_neg = int(labels_np.size - n_pos)
    overall_correct_rate = n_pos / len(results) if results else 0.0

    # --- Report --- #
    print()
    print(f"{'metric':<40} {'value':>12}")
    print("-" * 55)
    print(f"{'N questions':<40} {len(results):>12}")
    print(f"{'Correct (greedy matches MC correct)':<40} {n_pos:>12}")
    print(f"{'Wrong':<40} {n_neg:>12}")
    print(f"{'Greedy accuracy':<40} {overall_correct_rate:>12.3f}")
    print(f"{'Mean semantic entropy (all)':<40} {float(scalars.mean()):>12.4f}")
    print(f"{'Mean semantic entropy (correct)':<40} {mean_correct:>12.4f}")
    print(f"{'Mean semantic entropy (wrong)':<40} {mean_wrong:>12.4f}")
    print(f"{'AUC (-entropy as truth predictor)':<40} {auc:>12.3f}")
    print(f"{'Classification':<40} {classification:>12}")
    print()
    print(f"Recommendation: {recommendation}")

    # --- Markdown report --- #
    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / f"probe_semantic_entropy{args.suffix}.md"
    lines = [
        "# §13 Revision Experiment — Semantic-Entropy Probe on TruthfulQA-MC\n",
        "Reference: Farquhar, Kossen, Kuhn, Gal (2024). Nature 630, 625–630.\n",
        "## Configuration\n",
        f"- **Target model:** `{args.model}`",
        f"- **NLI model:** `{args.nli_model}`",
        f"- **Dataset:** `truthful_qa / multiple_choice / validation`",
        f"- **N questions:** {len(results)}",
        f"- **Samples per question (K):** {args.k_samples}",
        f"- **Sampling temperature:** {args.temperature}",
        f"- **Max new tokens per sample:** {args.max_new_tokens}",
        f"- **Seed:** {args.seed}\n",
        "## Result\n",
        "| Metric | Value |",
        "|---|---|",
        f"| N questions | {len(results)} |",
        f"| Greedy accuracy (correct / N) | {n_pos}/{len(results)} = {overall_correct_rate:.3f} |",
        f"| Mean semantic entropy (all) | {float(scalars.mean()):.4f} |",
        f"| Mean semantic entropy (correct) | {mean_correct:.4f} |",
        f"| Mean semantic entropy (wrong) | {mean_wrong:.4f} |",
        f"| **AUC (-entropy as truth predictor)** | **{auc:.3f}** |",
        f"| **Classification** | **`{classification}`** |\n",
        "## §13 pre-committed bands\n",
        "- `AUC ≥ 0.70` → TRUTH_CORRELATED_STRONG — §2.2 metric revision lands.",
        "- `0.60 ≤ AUC < 0.70` → TRUTH_CORRELATED_MARGINAL — HaluEval confirmation required.",
        "- `0.55 ≤ AUC < 0.60` → NOISE_BAND_LIFT — no revision authorized.",
        "- `AUC < 0.55` → SECOND_NULL — §13 null strengthens to field-consistent.\n",
        "## Recommendation\n",
        recommendation + "\n",
        "## Interpretation guidance\n",
        "This probe tests whether moving BCVF's §2.2 metric from "
        "probability-simplex Euclidean distance to meaning-space "
        "(semantic-entropy clusters of sampled generations) restores "
        "the truth-correlated signal that the §13 N=100 null result "
        "showed was absent in simplex-space. Per published "
        "literature (Farquhar 2024, Kuhn 2023), semantic entropy "
        "should reach AUC 0.70–0.79 on free-form generation "
        "benchmarks with K=10 at T=1.0.\n",
    ]
    md_path.write_text("\n".join(lines) + "\n")
    print(f"\nMarkdown report: {md_path}")

    if args.dump_json:
        json_path = args.out_dir / f"probe_semantic_entropy{args.suffix}.json"
        with json_path.open("w") as f:
            json.dump([
                {
                    "q_idx": r.q_idx,
                    "prompt": r.prompt,
                    "correct_choice": r.correct_choice,
                    "greedy": r.greedy,
                    "samples": r.samples,
                    "cluster_ids": r.cluster_ids,
                    "num_clusters": r.num_clusters,
                    "semantic_entropy": r.semantic_entropy,
                    "greedy_matches_correct": r.greedy_matches_correct,
                }
                for r in results
            ], f, indent=2)
        print(f"Per-question JSON dump: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
