#!/usr/bin/env python
"""§13.11 experiment — cross-family semantic-entropy probe (§1.3 revision).

Reference:
  Yoffe, Rafailov, et al. (2024). "DebUnc: Mitigating Hallucinations in
  Large Language Models via Uncertainty-Aware Multi-Agent Debate."
  Feng, Shi, Tsvetkov (2024). "Don't Hallucinate, Abstain: Identifying
  LLM Knowledge Gaps via Multi-LLM Collaboration."
  Farquhar et al. (2024). Nature 630, 625–630 (base technique).

Intent:
  §13.10 established that question-conditioned semantic entropy on a
  SINGLE model (Qwen2.5-7B-Instruct) reaches AUC = 0.661 on both
  TruthfulQA-MC and HaluEval-QA — TRUTH_CORRELATED_MARGINAL, clearing
  the §11 0.60 bar but below the §13.9 external-framing 0.75 bar. The
  §13.8 authorization gate promotes the §1.3 cross-family ensemble
  revision to top priority.

  This script generalizes `probe_semantic_entropy.py` from M=1 to
  M≥2 independent model families. Instead of sampling K completions
  from a single model, we sample K per model from M models, pool the
  M×K samples, and cluster the pooled set by question-conditioned
  bidirectional NLI entailment. Semantic entropy is then computed
  over the pooled cluster distribution.

  Hypothesis (pre-committed — see §13.11 bands below): cross-family
  disagreement is a stronger signal than within-family sampling
  variance, because independent pretraining corpora and tokenizers
  mean the models' failure modes are less correlated than K samples
  from one model. Literature (Yoffe 2024, Feng 2024) predicts a
  +0.05–0.10 AUC lift over §13.10's 0.661.

Protocol:
  1. For each question in the benchmark, for each model m in [0..M-1]:
     sample K completions at T=1.0, max_new_tokens=32.
  2. Also generate one greedy completion (T=0) from the label model
     (default model index 0) for the correctness label.
  3. Pool the M×K samples. Cluster by question-conditioned
     bidirectional NLI entailment using an MNLI-trained classifier,
     union-find over the pooled set.
  4. Compute semantic entropy = Shannon entropy (nats) over pooled
     cluster sizes.
  5. Label correctness via the label model's greedy generation
     (question-conditioned NLI: entails correct choice AND does not
     entail any distractor) — identical to §13.10 for direct AUC
     comparability.
  6. Compute AUC of (-semantic_entropy) as a truth predictor.

Pre-committed success bands (§13.11, confirmed before coding):
  - AUC ≥ 0.75 on both benchmarks → CROSS_FAMILY_STRONG.
    Gates the §13.9 VC-brief revision. Authorizes §13.11 writeup
    and follow-up 2nd-difference observable per §13.8 item 3.
  - 0.70 ≤ AUC < 0.75 on both → CROSS_FAMILY_INTERNAL_STRONG.
    Strong for internal research; VC-brief still held (§13.9 bar
    is 0.75).
  - 0.681 ≤ AUC < 0.70 on both → CROSS_FAMILY_MARGINAL_LIFT.
    Modest but real lift above §13.10's 0.661 + 0.02 band.
    Document; do not authorize further probe progression.
  - 0.641 ≤ AUC ≤ 0.681 on both → CROSS_FAMILY_SATURATION.
    Within ±0.02 of §13.10's 0.661. Cross-family adds nothing
    beyond within-family semantic entropy; §2.2 has saturated.
  - AUC < 0.641 on any benchmark → CROSS_FAMILY_ANTI_FINDING.
    Cross-family disagreement is noise, not signal. Pause LLM
    track pending separate-axis revision (embedding-space /
    activation probes).

Relationship to §13.10:
  This is the NEXT authorized probe per §13.8. It does NOT replace
  `probe_semantic_entropy.py` — that script's §13.10 result (AUC
  0.661 on both benchmarks) is pinned in the design doc and remains
  the single-model baseline. This script is a separate experiment
  layered on top: same §2.2 meaning-space metric (semantic entropy),
  different §1.3 ensemble (cross-family pool).

Do NOT update `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` on the basis of
any result from this probe. Per §13.9, VC-facing material is
gated on AUC ≥ 0.75 on BOTH benchmarks (CROSS_FAMILY_STRONG).
Anything less is internal research confidence only.

Usage:
    HF_HUB_DISABLE_XET=1 python scripts/probe_cross_family_entropy.py \\
        --num-questions 100 \\
        --benchmark truthfulqa_mc \\
        --models Qwen/Qwen2.5-7B-Instruct,meta-llama/Llama-3.1-8B-Instruct,mistralai/Mistral-7B-Instruct-v0.3 \\
        --k-samples 10 \\
        --dump-json

Runtime ~20–30 min at N=100, M=3, K=10 with co-resident loading on
a ≥48 GB GPU (80 GB configuration assumed per §13.11 authorization).
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
    question: str
    prompt: str
    correct_choice: str
    distractors: List[str]
    # Pooled M×K samples in a single flat list, with per-sample
    # provenance in `sample_model_ids` (index into the configured
    # model list). This keeps the clustering logic identical to
    # §13.10 while preserving family attribution for the JSON dump.
    samples: List[str]
    sample_model_ids: List[int]
    # Per-model prompt strings. Equal across models when --chat-template
    # is off (all use the shared "Q: ... A:" completion format, matching
    # §13.10). Diverge per family when --chat-template is on.
    prompts_by_model: List[str]
    greedy: str
    label_model_idx: int
    cluster_ids: List[int]
    num_clusters: int
    semantic_entropy: float
    greedy_matches_correct: bool
    label: int


def build_nli_checker(nli_model, nli_tokenizer, device: str, batch_size: int = 32):
    """Return a function (premises, hypotheses) -> List[bool] for batched
    entailment checks. Identical to the §13.10 implementation.

    Uses the standard MNLI 3-class head; returns True iff argmax is
    "entailment". Batches inputs so the M×K × (M×K−1) clustering pairs
    per question fit in a handful of forward passes rather than one
    call per pair.
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
    def check_batch(premises: List[str], hypotheses: List[str]) -> List[bool]:
        assert len(premises) == len(hypotheses)
        if not premises:
            return []
        verdicts: List[bool] = []
        for start in range(0, len(premises), batch_size):
            end = min(start + batch_size, len(premises))
            enc = nli_tokenizer(
                premises[start:end], hypotheses[start:end],
                return_tensors="pt", truncation=True, max_length=512,
                padding=True,
            ).to(device)
            logits = nli_model(**enc).logits
            preds = torch.argmax(logits, dim=-1).tolist()
            verdicts.extend(int(p) == ent_idx for p in preds)
        return verdicts

    return check_batch


def cluster_pooled_by_entailment(
    samples: List[str], check_batch, question: str,
) -> List[int]:
    """Union-find clustering by question-conditioned bidirectional NLI
    entailment over the POOLED M×K samples.

    Mechanically identical to §13.10's `cluster_by_entailment` — only
    the semantics of `samples` differ: here it is the concatenation
    of K samples from each of M models. The clustering rule makes no
    reference to source model, so any cross-model pair is free to
    fall into the same cluster if they're semantically equivalent.

    Question-conditioning rationale (unchanged from §13.10): short
    generations like "Paris" and "It's Paris" fail to entail each
    other in isolation but do when prefixed with the question. Omitting
    the question causes systematic over-clustering → inflated entropy
    → depressed AUC.

    All pooled_N × (pooled_N − 1) directional NLI pairs are submitted
    as a single batch to `check_batch`. For M=3, K=10 this is 30 × 29
    = 870 pairs per question.
    """
    n = len(samples)
    if n == 0:
        return []
    contextualized = [f"{question} {s}" for s in samples]

    pairs: List[Tuple[int, int]] = []
    premises: List[str] = []
    hypotheses: List[str] = []
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            pairs.append((i, j))
            premises.append(contextualized[i])
            hypotheses.append(contextualized[j])

    verdicts = check_batch(premises, hypotheses)
    entail = {pair: v for pair, v in zip(pairs, verdicts)}

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
            if entail.get((i, j)) and entail.get((j, i)):
                union(i, j)

    roots = [find(i) for i in range(n)]
    canon = {r: idx for idx, r in enumerate(sorted(set(roots)))}
    return [canon[r] for r in roots]


def semantic_entropy_nats(cluster_ids: List[int]) -> float:
    """Shannon entropy (nats) over cluster-size distribution over the
    pooled M×K samples. Identical formula to §13.10."""
    n = len(cluster_ids)
    sizes = Counter(cluster_ids).values()
    p = np.array([s / n for s in sizes], dtype=np.float64)
    return float(-np.sum(p * np.log(p)))


def build_prompt_for_tokenizer(
    tokenizer, q_text: str, include_context: bool,
    knowledge: Optional[str], use_chat_template: bool,
) -> str:
    """Build the prompt string for a specific tokenizer.

    When ``use_chat_template`` is False (default, §13.10 parity): returns
    the classic ``"Q: ... A:"`` completion format, identical across all
    tokenizers in the run. This is what §13.11's initial pass used and
    what TruthfulQA-MC returned AUC 0.633 on.

    When ``use_chat_template`` is True (diagnostic mode for the TruthfulQA
    split): wraps the question as a ``user`` message and applies the
    tokenizer's ``chat_template``. Produces per-family prompt strings —
    ChatML for Qwen (``<|im_start|>user`` etc.), Llama-3 tags for Llama
    (``<|begin_of_text|><|start_header_id|>user<|end_header_id|>`` etc.),
    ``[INST] ... [/INST]`` for Mistral. Tests whether Llama and Mistral's
    high singleton-cluster rates were driven by prompt-format mismatch
    rather than genuine cross-family divergence.

    Per-family chat templates include their own special tokens (BOS, role
    markers). The caller must pair this with ``add_special_tokens=False``
    in the subsequent tokenizer(...) call to avoid double-BOS.
    """
    if include_context and knowledge:
        user_content = f"{knowledge}\n\nQuestion: {q_text}"
    else:
        user_content = q_text

    if use_chat_template:
        if getattr(tokenizer, "chat_template", None) is None:
            raise RuntimeError(
                f"Tokenizer {tokenizer.name_or_path!r} has no chat_template; "
                "cannot run with --chat-template."
            )
        messages = [{"role": "user", "content": user_content}]
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )
    # Completion-style — identical to §13.10 and the §13.11 initial pass.
    if include_context and knowledge:
        return f"{knowledge}\n\nQ: {q_text}\nA:"
    return f"Q: {q_text}\nA:"


def generate_samples(
    model, tokenizer, prompt: str, k: int, temperature: float,
    max_new_tokens: int, device: str, seed: int,
    add_special_tokens: bool = True,
) -> List[str]:
    """Sample `k` completions from (model, tokenizer). Returns decoded
    strings with the prompt prefix stripped.

    ``add_special_tokens`` defaults to True for §13.10 parity on
    completion-style prompts. Callers using chat-templated prompts
    (built via ``build_prompt_for_tokenizer`` with
    ``use_chat_template=True``) must pass ``add_special_tokens=False``
    because the chat template already emits BOS / role tokens.
    """
    import torch

    torch.manual_seed(seed)
    enc = tokenizer(prompt, return_tensors="pt", add_special_tokens=add_special_tokens)
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
    add_special_tokens: bool = True,
) -> str:
    """Deterministic T=0 completion from (model, tokenizer). Used by
    the label model to produce the greedy reference for correctness
    labeling, matching §13.10's methodology.

    ``add_special_tokens`` defaults to True; see ``generate_samples``
    for the chat-template note."""
    import torch

    enc = tokenizer(prompt, return_tensors="pt", add_special_tokens=add_special_tokens)
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
    check_batch, question: str,
) -> bool:
    """Question-conditioned correctness label. Identical to §13.10 —
    the label model's greedy generation is correct iff
    (question + greedy) entails (question + correct_choice) AND does
    not entail (question + distractor) for any distractor.

    Using a single-model greedy as the label (rather than a cross-
    family consensus) preserves direct AUC comparability with the
    §13.10 baseline: any lift is attributable to the ensemble change
    in the predictor, not to a relabeling confound.
    """
    premise = f"{question} {greedy_gen}"
    candidates = [correct_choice] + list(distractors)
    contextualized_candidates = [f"{question} {c}" for c in candidates]
    verdicts = check_batch(
        [premise] * len(candidates),
        contextualized_candidates,
    )
    entails_correct = verdicts[0]
    entails_any_distractor = any(verdicts[1:])
    return bool(entails_correct and not entails_any_distractor)


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Binary AUC via tie-aware rank sum. Matches observables/base.py
    and §13.10's probe_semantic_entropy.py. Reproduced here so this
    script has no internal project imports (it can run in a clean
    checkout of just scripts/)."""
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


# §13.11 pre-committed band boundaries. Expressed as module-level
# constants so the report writer can render them in the output without
# hard-coding them twice.
BASELINE_AUC = 0.661      # §13.10 single-model semantic entropy result.
SATURATION_DELTA = 0.02   # ±window around the baseline counted as "no lift".
STRONG_THRESHOLD = 0.75           # §13.9 VC-gate bar.
INTERNAL_STRONG_THRESHOLD = 0.70  # Strong-for-internal; VC still held.
MARGINAL_LIFT_THRESHOLD = BASELINE_AUC + SATURATION_DELTA   # 0.681
SATURATION_LOWER = BASELINE_AUC - SATURATION_DELTA          # 0.641


def classify(auc: float) -> Tuple[str, str]:
    """Map an AUC to a §13.11 band label and per-run recommendation.

    Bands are partitioned so every float in [0, 1] falls into exactly
    one label. "On both benchmarks" determination is made externally
    by running this script twice (truthfulqa_mc + halueval_qa) and
    comparing the two per-run classifications.
    """
    if auc >= STRONG_THRESHOLD:
        return "CROSS_FAMILY_STRONG", (
            "Strong pass. Gates the §13.9 VC-brief revision — but only "
            "if the OTHER benchmark also clears 0.75. Next: confirm on "
            "the second benchmark before any external-facing material "
            "is updated. Also authorizes §13.8 item 3 (2nd-difference "
            "observable) as a follow-up §0.8 pre-commitment."
        )
    if auc >= INTERNAL_STRONG_THRESHOLD:
        return "CROSS_FAMILY_INTERNAL_STRONG", (
            "Strong for internal research. Cross-family ensemble lifts "
            "AUC above 0.70, but stays below the §13.9 VC-gate bar of "
            "0.75. Do NOT update VC-facing material. Document in "
            "§13.11; consider whether a larger label/NLI model closes "
            "the gap to the 0.75 strong band."
        )
    if auc >= MARGINAL_LIFT_THRESHOLD:
        return "CROSS_FAMILY_MARGINAL_LIFT", (
            "Real but modest lift above §13.10's 0.661 + 0.02 band. "
            "Document in §13.11; do NOT authorize further probe "
            "progression. Cross-family adds some signal but not enough "
            "to unlock §13.8 follow-ups."
        )
    if auc >= SATURATION_LOWER:
        return "CROSS_FAMILY_SATURATION", (
            "Within ±0.02 of §13.10's 0.661 single-model baseline. "
            "Cross-family ensembling adds nothing beyond within-family "
            "semantic entropy at this configuration. §2.2 meaning-space "
            "metric appears saturated; further lift requires a "
            "separate-axis change (embedding-space / activation probes, "
            "per §13.8 item 2) or a 2nd-difference observable."
        )
    return "CROSS_FAMILY_ANTI_FINDING", (
        "AUC below §13.10 − 0.02. Cross-family disagreement is noise, "
        "not signal, at this configuration. Pause LLM track pending "
        "a separate-axis revision. Check for implementation bugs "
        "(prompt formatting, tokenizer handling, per-model decode) "
        "before treating as a genuine anti-finding."
    )


DEFAULT_MODELS = ",".join([
    "Qwen/Qwen2.5-7B-Instruct",
    "meta-llama/Llama-3.1-8B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
])


def parse_models_flag(raw: str) -> List[str]:
    """Split a comma-separated --models value into a list of HF IDs.
    Whitespace around commas is tolerated. Empty entries are rejected
    (a bare trailing comma is almost always a typo)."""
    names = [s.strip() for s in raw.split(",")]
    if any(not n for n in names):
        raise argparse.ArgumentTypeError(
            f"--models list contains an empty entry: {raw!r}"
        )
    if len(names) < 2:
        raise argparse.ArgumentTypeError(
            f"--models must list at least 2 model IDs (got {len(names)}). "
            f"For M=1, use scripts/probe_semantic_entropy.py instead."
        )
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-questions", type=int, default=100)
    parser.add_argument(
        "--benchmark", choices=("truthfulqa_mc", "halueval_qa"),
        default="truthfulqa_mc",
        help="Identical benchmark semantics to §13.10's "
             "probe_semantic_entropy.py — only the predictor differs.",
    )
    parser.add_argument(
        "--include-context", action="store_true",
        help="halueval_qa only: prepend the 'knowledge' passage. "
             "Default False to mirror §13.10's closed-book setting.",
    )
    parser.add_argument(
        "--models", type=parse_models_flag, default=DEFAULT_MODELS,
        help="Comma-separated list of HuggingFace model IDs. Default "
             "is the §13.11 pre-committed triple (Qwen2.5-7B-Instruct, "
             "Llama-3.1-8B-Instruct, Mistral-7B-Instruct-v0.3). At "
             "least 2 models required.",
    )
    parser.add_argument(
        "--label-model-idx", type=int, default=0,
        help="Index into --models of the model whose greedy generation "
             "is used for the correctness label. Default 0 (the first "
             "listed model, typically Qwen for §13.10 comparability). "
             "Changing this across runs confounds the AUC comparison.",
    )
    parser.add_argument(
        "--nli-model",
        default="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        help="MNLI-trained classifier for entailment checks. Same "
             "default as §13.10.",
    )
    parser.add_argument(
        "--chat-template", action="store_true",
        help="Apply each tokenizer's apply_chat_template() to wrap the "
             "question as a user message (ChatML for Qwen, Llama-3 tags "
             "for Llama, [INST] for Mistral). Default False — §13.10 "
             "'Q: ... A:' completion format, shared across all families. "
             "Enable as a §13.11 diagnostic to test whether prompt-format "
             "mismatch drove the TruthfulQA-MC AUC 0.633 anti-finding "
             "while HaluEval-QA cleared 0.716. Pre-commitment: a strong "
             "lift on TruthfulQA-MC under --chat-template (≥ 0.68, into "
             "the SATURATION band) reclassifies the §13.11 pre-committed "
             "result. No lift means the prompt-format hypothesis is "
             "falsified and the combined ANTI_FINDING stands.",
    )
    parser.add_argument("--k-samples", type=int, default=10,
                        help="Samples per model per question. Pool "
                             "size is M×K (default 3×10 = 30).")
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
        help="Also write a per-question JSON dump next to the report, "
             "including per-sample source-model attribution.",
    )
    args = parser.parse_args()

    if not (0 <= args.label_model_idx < len(args.models)):
        parser.error(
            f"--label-model-idx {args.label_model_idx} out of range for "
            f"{len(args.models)} configured models."
        )

    # Auto-suffix the output filenames when --chat-template is on and the
    # user didn't supply their own suffix. Prevents silently overwriting
    # the §13.11 initial-pass reports (the ones that produced the 0.633
    # / 0.716 result) with diagnostic variant numbers.
    if args.chat_template and not args.suffix:
        args.suffix = "_chat"
        print(
            "Auto-applied --suffix=_chat to keep diagnostic outputs "
            "separate from the §13.11 initial-pass reports.",
            flush=True,
        )

    import torch
    from datasets import load_dataset
    from transformers import (
        AutoModelForCausalLM, AutoModelForSequenceClassification,
        AutoTokenizer,
    )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}", flush=True)
    if device == "cuda":
        total_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"  GPU total memory: {total_gb:.1f} GB", flush=True)

    # Co-resident loading: all M causal LMs + the NLI classifier held
    # in VRAM simultaneously. Authorized under the §13.11 80 GB GPU
    # assumption. Three ~8B fp16 models ≈ 45–50 GB; DeBERTa-v3-base
    # adds ~0.5 GB; plenty of headroom for the generation KV cache at
    # batch_size = K = 10.
    tokenizers: List = []
    models: List = []
    for name in args.models:
        print(f"Loading causal LM: {name}", flush=True)
        tok = AutoTokenizer.from_pretrained(name)
        mdl = AutoModelForCausalLM.from_pretrained(
            name, torch_dtype=torch.float16,
        ).to(device)
        mdl.eval()
        tokenizers.append(tok)
        models.append(mdl)
        if device == "cuda":
            alloc_gb = torch.cuda.memory_allocated() / (1024**3)
            print(f"  VRAM after load: {alloc_gb:.1f} GB", flush=True)

    print(f"Loading NLI model: {args.nli_model}", flush=True)
    nli_tokenizer = AutoTokenizer.from_pretrained(args.nli_model)
    nli_dtype = torch.float16 if device == "cuda" else torch.float32
    nli_model = AutoModelForSequenceClassification.from_pretrained(
        args.nli_model, torch_dtype=nli_dtype,
    ).to(device)
    nli_model.eval()
    check_batch = build_nli_checker(nli_model, nli_tokenizer, device)
    if device == "cuda":
        alloc_gb = torch.cuda.memory_allocated() / (1024**3)
        print(f"  VRAM after NLI load: {alloc_gb:.1f} GB", flush=True)

    if args.benchmark == "truthfulqa_mc":
        print("Loading TruthfulQA (multiple_choice, validation) ...", flush=True)
        ds = load_dataset(
            "truthful_qa", "multiple_choice", split="validation",
        )
    elif args.benchmark == "halueval_qa":
        print("Loading HaluEval (qa, data) ...", flush=True)
        ds = load_dataset("pminervini/HaluEval", "qa", split="data")
    else:
        raise ValueError(f"unsupported benchmark: {args.benchmark}")
    ds = ds.select(range(min(args.num_questions, len(ds))))

    label_tok = tokenizers[args.label_model_idx]
    label_mdl = models[args.label_model_idx]
    label_name = args.models[args.label_model_idx]
    print(
        f"Correctness label source: model[{args.label_model_idx}] "
        f"= {label_name}",
        flush=True,
    )

    results: List[QuestionResult] = []
    t_start = time.perf_counter()

    for q_idx, row in enumerate(ds):
        knowledge: Optional[str] = None
        if args.benchmark == "truthfulqa_mc":
            q_text = row["question"]
            choices = list(row["mc1_targets"]["choices"])
            labels = list(row["mc1_targets"]["labels"])
            correct_index = int(labels.index(1))
            correct_choice = choices[correct_index]
            distractors = [
                c for i, c in enumerate(choices) if i != correct_index
            ]
        else:  # halueval_qa
            q_text = row["question"]
            correct_choice = row["right_answer"]
            distractors = [row["hallucinated_answer"]]
            if args.include_context:
                knowledge = row.get("knowledge")

        # Build per-model prompts. Identical across models unless
        # --chat-template is on, in which case each family gets its
        # own tokenizer's chat template applied.
        prompts_by_model = [
            build_prompt_for_tokenizer(
                tok, q_text, args.include_context, knowledge,
                args.chat_template,
            )
            for tok in tokenizers
        ]
        label_prompt = prompts_by_model[args.label_model_idx]

        # Sample K completions from EACH model, pooling into a flat
        # list with parallel source-id tracking. The seed is perturbed
        # per (question, model) so different models don't share a seed
        # that could couple their sampling streams in unintended ways.
        pooled_samples: List[str] = []
        pooled_model_ids: List[int] = []
        for m_idx, (tok, mdl, prompt_m) in enumerate(
            zip(tokenizers, models, prompts_by_model)
        ):
            samples_m = generate_samples(
                mdl, tok, prompt_m,
                k=args.k_samples, temperature=args.temperature,
                max_new_tokens=args.max_new_tokens, device=device,
                seed=args.seed + q_idx * len(models) + m_idx,
                add_special_tokens=(not args.chat_template),
            )
            pooled_samples.extend(samples_m)
            pooled_model_ids.extend([m_idx] * len(samples_m))

        greedy = generate_greedy(
            label_mdl, label_tok, label_prompt,
            max_new_tokens=args.max_new_tokens, device=device,
            add_special_tokens=(not args.chat_template),
        )

        cluster_ids = cluster_pooled_by_entailment(
            pooled_samples, check_batch, q_text,
        )
        sem_entropy = semantic_entropy_nats(cluster_ids)
        is_correct = label_correctness(
            greedy, correct_choice, distractors, check_batch, q_text,
        )

        results.append(QuestionResult(
            q_idx=q_idx, question=q_text, prompt=label_prompt,
            correct_choice=correct_choice, distractors=distractors,
            samples=pooled_samples,
            sample_model_ids=pooled_model_ids,
            prompts_by_model=prompts_by_model,
            greedy=greedy,
            label_model_idx=args.label_model_idx,
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
                f"mean_entropy="
                f"{np.mean([r.semantic_entropy for r in results]):.3f} "
                f"mean_clusters="
                f"{np.mean([r.num_clusters for r in results]):.2f}",
                flush=True,
            )

    # --- AUC + summary stats --- #
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
    mean_clusters = float(
        np.mean([r.num_clusters for r in results]) if results else 0.0
    )

    # --- Per-family diagnostic: how uniform is each family's
    # contribution to the pooled clusters? High "singleton rate" for
    # a family means that family's samples tend not to merge with the
    # others — the cross-family signal is carried by THAT family's
    # idiosyncratic generations. Low rate means the family mostly
    # agrees with the others. Pure diagnostic; not in any pass-band.
    per_family_singleton_rate: List[float] = []
    for m_idx in range(len(args.models)):
        total = 0
        singletons = 0
        for r in results:
            # Group cluster ids by source-model within this question.
            clusters_by_source = Counter(
                cid for cid, src in zip(r.cluster_ids, r.sample_model_ids)
                if src == m_idx
            )
            for cid, count in clusters_by_source.items():
                # "Singleton" = this family contributed to a cluster
                # that no OTHER family contributed to.
                other_contrib = sum(
                    1 for c, s in zip(r.cluster_ids, r.sample_model_ids)
                    if c == cid and s != m_idx
                )
                total += count
                if other_contrib == 0:
                    singletons += count
        per_family_singleton_rate.append(
            singletons / total if total > 0 else 0.0
        )

    # --- Console report --- #
    print()
    print(f"{'metric':<42} {'value':>12}")
    print("-" * 57)
    print(f"{'N questions':<42} {len(results):>12}")
    print(f"{'Models (M)':<42} {len(args.models):>12}")
    print(f"{'Samples per model (K)':<42} {args.k_samples:>12}")
    print(f"{'Pool size per question (M×K)':<42} "
          f"{len(args.models) * args.k_samples:>12}")
    print(f"{'Correct (label-model greedy)':<42} {n_pos:>12}")
    print(f"{'Wrong':<42} {n_neg:>12}")
    print(f"{'Greedy accuracy':<42} {overall_correct_rate:>12.3f}")
    print(f"{'Mean clusters per question':<42} {mean_clusters:>12.2f}")
    print(f"{'Mean semantic entropy (all)':<42} "
          f"{float(scalars.mean()):>12.4f}")
    print(f"{'Mean semantic entropy (correct)':<42} {mean_correct:>12.4f}")
    print(f"{'Mean semantic entropy (wrong)':<42} {mean_wrong:>12.4f}")
    print(f"{'AUC (-entropy as truth predictor)':<42} {auc:>12.3f}")
    print(f"{'vs §13.10 baseline (0.661)':<42} "
          f"{auc - BASELINE_AUC:>+12.3f}")
    print(f"{'Classification':<42} {classification:>12}")
    print()
    for m_idx, name in enumerate(args.models):
        print(
            f"  singleton-cluster rate for model[{m_idx}] "
            f"({name}): {per_family_singleton_rate[m_idx]:.3f}"
        )
    print()
    print(f"Recommendation: {recommendation}")

    # --- Markdown report --- #
    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / (
        f"probe_cross_family_entropy_{args.benchmark}{args.suffix}.md"
    )
    family_lines = [
        f"  - model[{m_idx}] = `{name}` "
        f"(singleton-cluster rate = {per_family_singleton_rate[m_idx]:.3f})"
        for m_idx, name in enumerate(args.models)
    ]
    lines = [
        "# §13.11 Revision Experiment — Cross-Family Semantic-Entropy Probe\n",
        "References: Yoffe 2024 (DebUnc); Feng 2024 (Don't Hallucinate, "
        "Abstain); Farquhar 2024 (Nature 630, 625–630) — base technique.\n",
        "## Configuration\n",
        f"- **Models (M = {len(args.models)}):**",
        *family_lines,
        f"- **Label model:** `{label_name}` "
        f"(index {args.label_model_idx}, Qwen default per §13.10 "
        f"comparability)",
        f"- **NLI model:** `{args.nli_model}`",
        (
            f"- **Prompt format:** per-family chat templates "
            f"(apply_chat_template) — §13.11 diagnostic variant"
            if args.chat_template
            else (
                "- **Prompt format:** shared `Q: ... A:` completion "
                "(§13.10 parity)"
            )
        ),
        f"- **Benchmark:** `{args.benchmark}`",
        (
            "- **Dataset:** `truthful_qa / multiple_choice / validation`"
            if args.benchmark == "truthfulqa_mc"
            else (
                "- **Dataset:** `pminervini/HaluEval / qa / data` "
                f"(include_context={args.include_context})"
            )
        ),
        f"- **N questions:** {len(results)}",
        f"- **Samples per model per question (K):** {args.k_samples}",
        f"- **Pooled samples per question (M×K):** "
        f"{len(args.models) * args.k_samples}",
        f"- **Sampling temperature:** {args.temperature}",
        f"- **Max new tokens per sample:** {args.max_new_tokens}",
        f"- **Seed (base):** {args.seed} "
        f"(per (question, model) seed = base + q_idx × M + m_idx)\n",
        "## Result\n",
        "| Metric | Value |",
        "|---|---|",
        f"| N questions | {len(results)} |",
        f"| Greedy accuracy (correct / N) | {n_pos}/{len(results)} "
        f"= {overall_correct_rate:.3f} |",
        f"| Mean clusters per question | {mean_clusters:.2f} |",
        f"| Mean semantic entropy (all) | {float(scalars.mean()):.4f} |",
        f"| Mean semantic entropy (correct) | {mean_correct:.4f} |",
        f"| Mean semantic entropy (wrong) | {mean_wrong:.4f} |",
        f"| **AUC (-entropy as truth predictor)** | **{auc:.3f}** |",
        f"| Δ vs §13.10 baseline (0.661) | **{auc - BASELINE_AUC:+.3f}** |",
        f"| **Classification** | **`{classification}`** |\n",
        "## Per-family singleton-cluster rates\n",
        "Fraction of a family's samples that land in clusters no other "
        "family contributed to. High rate → that family's outputs "
        "diverge from the pool (contributes more to cross-family "
        "entropy). Low rate → that family mostly agrees with the "
        "others. Pure diagnostic; not in any pass-band.\n",
        "| Model | Singleton rate |",
        "|---|---|",
        *[
            f"| `{name}` | {per_family_singleton_rate[m_idx]:.3f} |"
            for m_idx, name in enumerate(args.models)
        ],
        "",
        "## §13.11 pre-committed bands\n",
        f"- `AUC ≥ {STRONG_THRESHOLD}` → **CROSS_FAMILY_STRONG** — "
        "gates the §13.9 VC-brief revision when cleared on BOTH "
        "benchmarks.",
        f"- `{INTERNAL_STRONG_THRESHOLD} ≤ AUC < {STRONG_THRESHOLD}` "
        "→ **CROSS_FAMILY_INTERNAL_STRONG** — strong for internal "
        "research; VC-brief still held.",
        f"- `{MARGINAL_LIFT_THRESHOLD:.3f} ≤ AUC < "
        f"{INTERNAL_STRONG_THRESHOLD}` → **CROSS_FAMILY_MARGINAL_LIFT** "
        "— modest but real lift above §13.10 + 0.02.",
        f"- `{SATURATION_LOWER:.3f} ≤ AUC ≤ "
        f"{MARGINAL_LIFT_THRESHOLD:.3f}` → **CROSS_FAMILY_SATURATION** "
        f"— within ±{SATURATION_DELTA} of §13.10's {BASELINE_AUC} "
        "single-model baseline.",
        f"- `AUC < {SATURATION_LOWER:.3f}` → "
        "**CROSS_FAMILY_ANTI_FINDING** — pause LLM track pending a "
        "separate-axis revision.\n",
        "## Recommendation\n",
        recommendation + "\n",
        "## Interpretation guidance\n",
        "This probe tests whether pooling K samples from each of M "
        "independent model families, then clustering the pooled set "
        "by question-conditioned NLI entailment, produces a stronger "
        "truth-correlated entropy signal than the M=1 baseline. The "
        "§13.10 single-model result (AUC 0.661 on both benchmarks) is "
        "the baseline. A lift to AUC ≥ 0.75 on both benchmarks would "
        "clear the §13.9 VC-gate; AUC within ±0.02 of 0.661 indicates "
        "the §2.2 meaning-space metric has saturated at this scale "
        "and further lift requires a separate-axis change "
        "(embedding-space / activation probes, per §13.8 item 2).\n",
        "Critically: this script does NOT authorize any update to "
        "`AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` on its own. Per §13.9, "
        "the external framing revision requires "
        "`CROSS_FAMILY_STRONG` on BOTH benchmarks, confirmed by a "
        "second run of this script with `--benchmark halueval_qa` "
        "(or `truthfulqa_mc`, whichever wasn't run first).\n",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nMarkdown report: {md_path}")

    if args.dump_json:
        json_path = args.out_dir / (
            f"probe_cross_family_entropy_{args.benchmark}{args.suffix}.json"
        )
        with json_path.open("w", encoding="utf-8") as f:
            json.dump({
                "config": {
                    "models": list(args.models),
                    "label_model_idx": args.label_model_idx,
                    "nli_model": args.nli_model,
                    "benchmark": args.benchmark,
                    "include_context": bool(args.include_context),
                    "chat_template": bool(args.chat_template),
                    "num_questions": args.num_questions,
                    "k_samples": args.k_samples,
                    "temperature": args.temperature,
                    "max_new_tokens": args.max_new_tokens,
                    "seed": args.seed,
                },
                "summary": {
                    "n": len(results),
                    "n_correct": n_pos,
                    "n_wrong": n_neg,
                    "greedy_accuracy": overall_correct_rate,
                    "mean_clusters": mean_clusters,
                    "mean_entropy_all": float(scalars.mean()),
                    "mean_entropy_correct": mean_correct,
                    "mean_entropy_wrong": mean_wrong,
                    "auc": auc,
                    "baseline_auc_s13_10": BASELINE_AUC,
                    "auc_delta_vs_baseline": auc - BASELINE_AUC,
                    "classification": classification,
                    "per_family_singleton_rate": (
                        per_family_singleton_rate
                    ),
                },
                "questions": [
                    {
                        "q_idx": r.q_idx,
                        "question": r.question,
                        "prompt": r.prompt,
                        "correct_choice": r.correct_choice,
                        "distractors": r.distractors,
                        "greedy": r.greedy,
                        "label_model_idx": r.label_model_idx,
                        "prompts_by_model": r.prompts_by_model,
                        "samples": r.samples,
                        "sample_model_ids": r.sample_model_ids,
                        "cluster_ids": r.cluster_ids,
                        "num_clusters": r.num_clusters,
                        "semantic_entropy": r.semantic_entropy,
                        "greedy_matches_correct": (
                            r.greedy_matches_correct
                        ),
                    }
                    for r in results
                ],
            }, f, indent=2)
        print(f"Per-question JSON dump: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
