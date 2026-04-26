#!/usr/bin/env python
"""§13.12 experiment — EigenScore embedding-space probe (§13.8 item 2).

Reference:
  Chen, Quan, Jia, Bao, Liu (2024). "INSIDE: LLMs' Internal States
  Retain the Power of Hallucination Detection." ICLR 2024.

Intent:
  §13.10 established that meaning-space semantic entropy on a single
  Qwen2.5-7B-Instruct target reaches AUC 0.661 on both TruthfulQA-MC
  and HaluEval-QA — TRUTH_CORRELATED_MARGINAL, clearing the §11
  0.60 marginal bar but not the §13.9 0.75 external-framing bar.
  §13.11 attempted to lift that result via the §1.3 cross-family
  ensemble revision (Qwen + Llama + Mistral) and landed combined
  CROSS_FAMILY_ANTI_FINDING — the heterogeneous TruthfulQA / HaluEval
  split (0.633 / 0.716) resolves to ANTI on the worst-benchmark rule,
  with a chat-template diagnostic confirming the result is not a
  prompt-format artifact.

  This probe tests the §13.8 item-2 alternative: instead of a sample-
  space metric (semantic entropy) or an ensemble metric (cross-family
  pool), use an internal-state metric (EigenScore over mid-layer
  hidden states across K sampled generations). Literature (Chen 2024)
  reports AUROC 0.74-0.81 on HaluEval/TruthfulQA — bracketing the
  §13.9 0.75 external-framing bar from both sides.

  Hypothesis (per §13.12 pre-commitment): if the truth signal is
  carried by the model's internal representations rather than its
  sampled outputs, EigenScore should clear the §13.10 baseline by a
  margin similar to the lift Chen 2024 reports. A clean EMBEDDING_
  SPACE_STRONG result on both benchmarks would gate the §13.9
  external-framing revision (the same gate §13.11 failed to clear).

Method:
  For each question, sample K=10 completions from the target model.
  Capture the mid-layer (layer L/2) hidden state at each sample's
  last non-pad generated token. Stack into X in R^{K x H}, compute
  the centered K x K Gram-matrix variant of EigenScore (Chen 2024,
  well-conditioned even when H >> K):

      X_c = X - X.mean(axis=0, keepdims=True)
      Sigma_K = (X_c @ X_c.T) / H + alpha * I_K
      EigenScore(q) = (1/K) * log(det(Sigma_K))

  Higher EigenScore = more spread in the K hidden states = more
  uncertainty. AUC computed on -EigenScore so the convention "higher
  = more truth-predictive" is preserved across §13.10 / §13.11 /
  §13.12.

Pre-committed success bands (§13.12, pinned in design doc BEFORE
implementation; same numerical partition as §13.11 because the §13.10
baseline of 0.661 is unchanged):

  - AUC >= 0.75 on both benchmarks -> EMBEDDING_SPACE_STRONG.
    Gates the §13.9 VC-brief revision (the same gate §13.11 failed
    to clear). Authorizes §13.13 writeup and re-opens §13.8 item 3
    (2nd-difference observable).
  - 0.70 <= AUC < 0.75 on both -> EMBEDDING_SPACE_INTERNAL_STRONG.
    Strong for internal research; VC-brief still held.
  - 0.681 <= AUC < 0.70 on both -> EMBEDDING_SPACE_MARGINAL_LIFT.
    Modest but real lift above §13.10's 0.661 + 0.02 saturation
    upper bound.
  - 0.641 <= AUC <= 0.681 on both -> EMBEDDING_SPACE_SATURATION.
    Within +/-0.02 of §13.10 baseline. Combined with §13.11's
    anti-finding, would be strong evidence single-axis revisions
    saturate.
  - AUC < 0.641 on any benchmark -> EMBEDDING_SPACE_ANTI_FINDING.
    Combined with §13.11, 2-of-2 anti across literature-backed
    single-axis revisions on this codebase.

Relationship to §13.10 / §13.11:
  This is a NEW probe per §13.8 item 2. It does NOT replace
  probe_semantic_entropy.py (§13.10 result pinned) or
  probe_cross_family_entropy.py (§13.11 result pinned). Same target
  model (Qwen2.5-7B-Instruct), same sampling protocol (K=10, T=1.0,
  max_new_tokens=32), same benchmarks (TruthfulQA-MC + HaluEval-QA at
  N=100), same correctness label (question-conditioned NLI on Qwen
  greedy). Only the per-question scalar differs: -EigenScore over
  hidden states instead of -semantic_entropy over NLI clusters.

Do NOT update AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md on the basis of any
result from this probe except EMBEDDING_SPACE_STRONG on BOTH
benchmarks (per §13.9). Anything less is internal research confidence
only.

Usage:
    HF_HUB_DISABLE_XET=1 python scripts/probe_eigenscore.py \\
        --num-questions 100 \\
        --benchmark truthfulqa_mc \\
        --dump-json

Runtime ~3-5 min at N=100 on a single 24+ GB GPU (cheaper than §13.10
because there is no NLI clustering pass on K samples — NLI is used
only for the correctness label, ~3 calls per question).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from dataclasses import dataclass
from typing import List, Tuple

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
    samples: List[str]
    # Per-sample sequence length AFTER prompt (number of generated
    # tokens including any trailing pad/eos). Diagnostic — not used
    # in EigenScore directly, but useful when reading the JSON dump
    # to spot pathological short-generation cases.
    sample_lengths: List[int]
    # Per-sample index of the last non-pad token IN THE GENERATED
    # SEGMENT (0 = first generated token). -1 means no non-pad
    # generation; in that case the prompt's last token's hidden state
    # was used as a fallback.
    last_token_indices: List[int]
    greedy: str
    eigenscore: float
    greedy_matches_correct: bool
    label: int  # 1 = correct, 0 = wrong


# §13.12 pre-committed band boundaries. Identical numerical partition
# to §13.11's CROSS_FAMILY_* bands because the §13.10 baseline of
# 0.661 is unchanged. Relabeled EMBEDDING_SPACE_* so the per-revision
# lineage stays legible in console output, JSON dumps, and grep.
BASELINE_AUC = 0.661               # §13.10 single-model semantic-entropy result.
SATURATION_DELTA = 0.02            # +/- window around the baseline.
STRONG_THRESHOLD = 0.75            # §13.9 VC-gate bar.
INTERNAL_STRONG_THRESHOLD = 0.70   # Strong-for-internal; VC still held.
MARGINAL_LIFT_THRESHOLD = BASELINE_AUC + SATURATION_DELTA   # 0.681
SATURATION_LOWER = BASELINE_AUC - SATURATION_DELTA          # 0.641


def classify(auc: float) -> Tuple[str, str]:
    """Map an AUC to a §13.12 band label and per-run recommendation.

    Bands are partitioned so every float in [0, 1] falls into exactly
    one label. "On both benchmarks" determination is made externally
    by running this script twice (truthfulqa_mc + halueval_qa) and
    comparing the two per-run classifications under the §13.12 worst-
    benchmark rule.
    """
    if auc >= STRONG_THRESHOLD:
        return "EMBEDDING_SPACE_STRONG", (
            "Strong pass. Gates the §13.9 VC-brief revision — but only "
            "if the OTHER benchmark also clears 0.75. Next: confirm on "
            "the second benchmark before any external-facing material "
            "is updated. Also re-opens §13.8 item 3 (2nd-difference "
            "observable) as a follow-up §0.8 pre-commitment."
        )
    if auc >= INTERNAL_STRONG_THRESHOLD:
        return "EMBEDDING_SPACE_INTERNAL_STRONG", (
            "Strong for internal research. EigenScore lifts AUC above "
            "0.70 but stays below the §13.9 VC-gate bar of 0.75. Do "
            "NOT update VC-facing material. Document in §13.13; "
            "consider whether a layer sweep (--layer) or alpha sweep "
            "(--alpha) closes the gap to the 0.75 strong band."
        )
    if auc >= MARGINAL_LIFT_THRESHOLD:
        return "EMBEDDING_SPACE_MARGINAL_LIFT", (
            "Real but modest lift above §13.10's 0.661 + 0.02 band. "
            "Document in §13.13; do NOT authorize further probe "
            "progression. Internal-state representation adds some "
            "signal but not enough to unlock §13.9 or §13.8 follow-ups."
        )
    if auc >= SATURATION_LOWER:
        return "EMBEDDING_SPACE_SATURATION", (
            "Within ±0.02 of §13.10's 0.661 single-model baseline. "
            "Internal-state representation adds nothing beyond meaning-"
            "space semantic entropy at this configuration. Combined "
            "with §13.11's CROSS_FAMILY_ANTI_FINDING, this is strong "
            "evidence that single-axis revisions (one literature-backed "
            "metric class change at a time) cannot clear the §13.9 0.75 "
            "bar on this codebase. Compound revisions (EigenScore + "
            "2nd-difference, or different model scale) are the remaining "
            "literature-backed options and require fresh §0.8 pre-"
            "commitments."
        )
    return "EMBEDDING_SPACE_ANTI_FINDING", (
        "AUC below §13.10 − 0.02. Internal-state representation does "
        "not carry truth signal at this configuration. Combined with "
        "§13.11, this is a 2-of-2 anti-finding across the literature-"
        "backed single-axis revisions tested on this codebase. Pause "
        "LLM track. Check for implementation bugs (layer index, "
        "hidden-state position, alpha numerics, last-token selection) "
        "before treating as a genuine anti-finding."
    )


def build_nli_checker(nli_model, nli_tokenizer, device: str, batch_size: int = 32):
    """Return a function (premises, hypotheses) -> List[bool] for batched
    entailment checks. Identical to §13.10 / §13.11 implementation —
    ensures the correctness labels produced here are the same labels
    those scripts produce on the same inputs.
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


def label_correctness(
    greedy_gen: str, correct_choice: str, distractors: List[str],
    check_batch, question: str,
) -> bool:
    """Question-conditioned correctness label. Identical to §13.10 /
    §13.11 — Qwen greedy generation is correct iff
    (question + greedy) entails (question + correct_choice) AND does
    not entail (question + distractor) for any distractor.

    Holding this labeling step fixed across §13.10 / §13.11 / §13.12
    is what makes the AUC numbers directly comparable across the three
    probes. Any change here would force a §0.8-style re-pre-commitment
    of the §13.10 baseline.
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


def generate_samples_with_hidden_states(
    model, tokenizer, prompt: str, k: int, temperature: float,
    max_new_tokens: int, device: str, seed: int, layer_idx: int,
):
    """Sample `k` completions from (model, tokenizer), capturing each
    sample's hidden state at ``layer_idx`` for the last non-pad
    generated token.

    Returns a tuple ``(decoded_samples, hidden_X, last_token_indices,
    sample_lengths)`` where:
      - decoded_samples : List[str], length k. Generation strings with
        prompt prefix stripped (matches §13.10 / §13.11 convention).
      - hidden_X : np.ndarray of shape (k, H), float32. Each row is
        ``hidden_states[gen_step][layer_idx][sample, 0, :]`` for the
        sample's last non-pad generated token. Falls back to the
        prompt's last position if the sample produced zero non-pad
        tokens (rare; flagged in last_token_indices = -1).
      - last_token_indices : List[int], length k. Per-sample index of
        the chosen token within the GENERATED segment (0 = first
        generated token); -1 = fallback to prompt's last token.
      - sample_lengths : List[int], length k. Total non-pad token
        count in the generated segment per sample.

    Implementation note — HuggingFace ``generate`` with
    ``output_hidden_states=True, return_dict_in_generate=True`` returns
    ``hidden_states`` as a tuple of length ``T_new + 1``: index 0 is
    the prompt's full forward pass (shape (k, prompt_len, H) per
    layer), indices 1..T_new are the per-step new-token forward passes
    (shape (k, 1, H) per layer). To get the hidden state at the
    sample's last meaningful token, find that token's position in the
    generated segment and look up the corresponding step.
    """
    import torch

    torch.manual_seed(seed)
    enc = tokenizer(prompt, return_tensors="pt", add_special_tokens=True)
    input_ids = enc.input_ids.to(device)
    attention_mask = torch.ones_like(input_ids)
    prompt_len = int(input_ids.shape[1])

    pad_id = tokenizer.pad_token_id
    if pad_id is None:
        pad_id = tokenizer.eos_token_id

    with torch.inference_mode():
        out = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            do_sample=True,
            temperature=temperature,
            num_return_sequences=k,
            max_new_tokens=max_new_tokens,
            pad_token_id=pad_id,
            output_hidden_states=True,
            return_dict_in_generate=True,
        )

    sequences = out.sequences  # (k, prompt_len + T_new_actual)
    # T_new_actual is min(max_new_tokens, longest sample's generation
    # before EOS). HF pads shorter samples with pad_id up to that.
    gen_segment = sequences[:, prompt_len:]                 # (k, T_new)

    # Per-sample: count non-pad tokens, find last non-pad position
    # within the generated segment. If a sample emitted zero non-pad
    # tokens (very rare; usually means immediate EOS), we fall back
    # to the prompt's last token's hidden state and mark with -1.
    is_non_pad = (gen_segment != pad_id)                    # (k, T_new), bool
    sample_lengths = is_non_pad.sum(dim=1).tolist()
    last_indices: List[int] = []
    for k_idx in range(k):
        non_pad_pos = is_non_pad[k_idx].nonzero(as_tuple=False)
        if non_pad_pos.numel() == 0:
            last_indices.append(-1)
        else:
            last_indices.append(int(non_pad_pos[-1].item()))

    # hidden_states: tuple of length T_new (one entry per generated
    # token). Entry t is the forward pass that produced the token at
    # generated position t:
    #   - Entry 0 has shape (k, prompt_len, H) — the prompt's full
    #     forward; its LAST sequence position is the hidden state used
    #     to predict the first new token.
    #   - Entries 1..T_new-1 have shape (k, 1, H) — single-token
    #     forwards, where position 0 (the only position) is the hidden
    #     state used to predict the (t+1)-th new token.
    # So the hidden state that "produced" the token at generated
    # position t is at hidden_states[t][L][k, -1, :] uniformly:
    # for t=0 this is the prompt's last token, for t>0 this is the
    # only position of step t. The earlier `t + 1` indexing was an
    # off-by-one assumption that hidden_states had a separate prompt
    # entry at index 0; HF actually folds the prompt forward INTO the
    # first generation step.
    H_rows: List[np.ndarray] = []
    for k_idx in range(k):
        t = last_indices[k_idx]
        if t == -1:
            # Sample emitted zero non-pad tokens (immediate EOS).
            # Fall back to the prompt's last-token representation,
            # which is the same hidden state that predicted the EOS.
            h = out.hidden_states[0][layer_idx][k_idx, -1, :]
        else:
            # Last non-pad token of sample k is at generated position
            # t; its producing hidden state lives at hidden_states[t]'s
            # last sequence position (regardless of whether t == 0,
            # where seq_len == prompt_len, or t > 0, where seq_len
            # == 1).
            h = out.hidden_states[t][layer_idx][k_idx, -1, :]
        H_rows.append(h.detach().to(torch.float32).cpu().numpy())
    hidden_X = np.stack(H_rows, axis=0)                     # (k, H), float32

    decoded_samples = [
        tokenizer.decode(g, skip_special_tokens=True).strip()
        for g in gen_segment
    ]
    return decoded_samples, hidden_X, last_indices, sample_lengths


def generate_greedy(
    model, tokenizer, prompt: str, max_new_tokens: int, device: str,
) -> str:
    """Deterministic T=0 completion. Used by the correctness labeler;
    no hidden-state capture needed (EigenScore is over the K stochastic
    samples, not the greedy)."""
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


def eigenscore(hidden_X: np.ndarray, alpha: float) -> float:
    """Chen et al. 2024 ICLR EigenScore — K×K Gram-matrix variant.

    Given hidden state matrix ``X`` of shape ``(K, H)`` (K samples,
    hidden dim H), compute:

        X_c     = X - X.mean(axis=0, keepdims=True)
        Sigma_K = (X_c @ X_c.T) / H + alpha * I_K
        score   = (1/K) * log(det(Sigma_K))

    The K×K Gram form is used (rather than the H×H covariance) because
    H >> K typically (3584 >> 10 for Qwen-7B with K=10), so the H×H
    covariance is rank-deficient and its log-det is degenerate. The
    K×K Gram matrix has the same non-zero eigenvalues up to a scaling
    constant, so log-det of the regularized Gram captures the same
    spread information without numerical pathologies.

    The ``alpha`` regularization (default 1e-3 per §13.12 spec) makes
    Sigma_K positive-definite even when X_c is rank-deficient (which
    happens whenever K samples produce highly similar hidden states).
    Without alpha, log(det) -> -inf for confident questions and the
    AUC computation breaks.

    ``slogdet`` is used rather than ``log(det(...))`` for numerical
    stability — det can underflow to 0 for very confident questions
    even with regularization, but slogdet returns log|det| robustly.
    The ``sign`` returned by slogdet should always be +1 here because
    Sigma_K is positive-definite by construction; if it isn't (sign
    <= 0), the function raises rather than returning a misleading
    scalar.
    """
    K, H = hidden_X.shape
    if K < 2:
        raise ValueError(f"EigenScore requires K >= 2 samples; got K={K}")
    X_c = hidden_X - hidden_X.mean(axis=0, keepdims=True)   # (K, H)
    Sigma_K = (X_c @ X_c.T) / float(H) + alpha * np.eye(K)  # (K, K)
    sign, logabsdet = np.linalg.slogdet(Sigma_K)
    if sign <= 0:
        raise RuntimeError(
            f"slogdet returned sign={sign} on a regularized Gram matrix; "
            f"this should not happen with alpha={alpha} > 0. Check for "
            f"NaN/Inf in hidden states (alpha too small for the "
            f"hidden-state norm scale of this model)."
        )
    return float(logabsdet / K)


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Binary AUC via tie-aware rank sum. Matches observables/base.py
    and §13.10 / §13.11. Reproduced here so this script has no
    internal project imports (runs in a clean checkout of just
    scripts/)."""
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-questions", type=int, default=100)
    parser.add_argument(
        "--benchmark", choices=("truthfulqa_mc", "halueval_qa"),
        default="truthfulqa_mc",
        help="Identical benchmark semantics to §13.10 / §13.11 — only "
             "the per-question scalar differs (-EigenScore over hidden "
             "states instead of -semantic_entropy over NLI clusters).",
    )
    parser.add_argument(
        "--include-context", action="store_true",
        help="halueval_qa only: prepend the 'knowledge' passage. "
             "Default False to mirror §13.10 / §13.11 closed-book.",
    )
    parser.add_argument(
        "--model", default="Qwen/Qwen2.5-7B-Instruct",
        help="Target model. §13.12 pre-commitment pins this to "
             "Qwen2.5-7B-Instruct for direct §13.10 baseline "
             "comparability; changing it is a §0.8 deviation.",
    )
    parser.add_argument(
        "--nli-model",
        default="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        help="MNLI-trained classifier for the correctness label. Same "
             "default as §13.10 / §13.11.",
    )
    parser.add_argument(
        "--layer", type=int, default=None,
        help="Hidden-state layer index. Default None → "
             "model.config.num_hidden_layers // 2 (= 14 for "
             "Qwen2.5-7B-Instruct, the §13.12-pinned middle layer). "
             "A non-default value here is a §13.12 deviation and "
             "must be flagged in the report.",
    )
    parser.add_argument(
        "--alpha", type=float, default=1e-3,
        help="EigenScore regularization. Default 1e-3 per Chen 2024 "
             "and §13.12 pre-commitment.",
    )
    parser.add_argument("--k-samples", type=int, default=10,
                        help="Samples per question. Pinned to 10 by "
                             "§13.12 for §13.10 / §13.11 parity.")
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
        help="Also write a per-question JSON dump next to the report. "
             "Includes per-sample lengths and last-token indices for "
             "diagnostic inspection of pathological short generations.",
    )
    args = parser.parse_args()

    if args.k_samples < 2:
        parser.error(
            f"--k-samples must be >= 2 (EigenScore is undefined at K=1); "
            f"got {args.k_samples}."
        )
    if args.alpha <= 0:
        parser.error(f"--alpha must be > 0; got {args.alpha}.")

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

    print(f"Loading target model: {args.model}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.float16,
    ).to(device)
    model.eval()
    num_hidden_layers = int(model.config.num_hidden_layers)
    hidden_size = int(model.config.hidden_size)
    layer_idx = (
        args.layer if args.layer is not None
        else num_hidden_layers // 2
    )
    if not (0 <= layer_idx <= num_hidden_layers):
        parser.error(
            f"--layer {layer_idx} out of range [0, {num_hidden_layers}] "
            f"for {args.model} (hidden_states has num_hidden_layers + 1 "
            f"entries including the embedding layer at index 0)."
        )
    layer_is_default = (args.layer is None)
    print(
        f"  num_hidden_layers={num_hidden_layers}, hidden_size={hidden_size}, "
        f"using layer={layer_idx}"
        + ("" if layer_is_default else "  [§13.12 DEVIATION: non-default layer]"),
        flush=True,
    )

    print(f"Loading NLI model: {args.nli_model}", flush=True)
    nli_tokenizer = AutoTokenizer.from_pretrained(args.nli_model)
    nli_dtype = torch.float16 if device == "cuda" else torch.float32
    nli_model = AutoModelForSequenceClassification.from_pretrained(
        args.nli_model, torch_dtype=nli_dtype,
    ).to(device)
    nli_model.eval()
    check_batch = build_nli_checker(nli_model, nli_tokenizer, device)

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

    results: List[QuestionResult] = []
    t_start = time.perf_counter()

    for q_idx, row in enumerate(ds):
        if args.benchmark == "truthfulqa_mc":
            q_text = row["question"]
            choices = list(row["mc1_targets"]["choices"])
            labels = list(row["mc1_targets"]["labels"])
            correct_index = int(labels.index(1))
            correct_choice = choices[correct_index]
            distractors = [
                c for i, c in enumerate(choices) if i != correct_index
            ]
            prompt = f"Q: {q_text}\nA:"
        else:  # halueval_qa
            q_text = row["question"]
            correct_choice = row["right_answer"]
            distractors = [row["hallucinated_answer"]]
            if args.include_context and row.get("knowledge"):
                prompt = f"{row['knowledge']}\n\nQ: {q_text}\nA:"
            else:
                prompt = f"Q: {q_text}\nA:"

        decoded_samples, hidden_X, last_indices, sample_lengths = (
            generate_samples_with_hidden_states(
                model, tokenizer, prompt,
                k=args.k_samples, temperature=args.temperature,
                max_new_tokens=args.max_new_tokens, device=device,
                seed=args.seed + q_idx, layer_idx=layer_idx,
            )
        )
        score = eigenscore(hidden_X, alpha=args.alpha)

        greedy = generate_greedy(
            model, tokenizer, prompt,
            max_new_tokens=args.max_new_tokens, device=device,
        )
        is_correct = label_correctness(
            greedy, correct_choice, distractors, check_batch, q_text,
        )

        results.append(QuestionResult(
            q_idx=q_idx, question=q_text, prompt=prompt,
            correct_choice=correct_choice, distractors=distractors,
            samples=decoded_samples,
            sample_lengths=sample_lengths,
            last_token_indices=last_indices,
            greedy=greedy,
            eigenscore=score,
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
                f"mean_eigenscore="
                f"{np.mean([r.eigenscore for r in results]):.4f}",
                flush=True,
            )

    # --- AUC + summary stats --- #
    scalars = np.array([r.eigenscore for r in results], dtype=np.float64)
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
    # A sample with last_token_index == -1 emitted zero non-pad tokens
    # (immediate EOS), so its hidden state was taken from the prompt's
    # last token instead. Count questions where AT LEAST ONE of the K
    # samples hit that fallback — useful diagnostic for spotting
    # pathological short-generation cases.
    n_zero_gen = sum(
        1 for r in results
        if any(li == -1 for li in r.last_token_indices)
    )

    # --- Console report --- #
    print()
    print(f"{'metric':<42} {'value':>20}")
    print("-" * 65)
    print(f"{'N questions':<42} {len(results):>20}")
    print(f"{'Target model':<42} {args.model:>20}")
    print(f"{'num_hidden_layers':<42} {num_hidden_layers:>20}")
    print(f"{'hidden_size (H)':<42} {hidden_size:>20}")
    print(f"{'Layer used':<42} {layer_idx:>20}")
    print(f"{'Samples per question (K)':<42} {args.k_samples:>20}")
    print(f"{'Regularization alpha':<42} {args.alpha:>20.2e}")
    print(f"{'Questions w/ any zero-gen sample':<42} {n_zero_gen:>20}")
    print(f"{'Correct (greedy matches)':<42} {n_pos:>20}")
    print(f"{'Wrong':<42} {n_neg:>20}")
    print(f"{'Greedy accuracy':<42} {overall_correct_rate:>20.3f}")
    print(f"{'Mean EigenScore (all)':<42} {float(scalars.mean()):>20.4f}")
    print(f"{'Mean EigenScore (correct)':<42} {mean_correct:>20.4f}")
    print(f"{'Mean EigenScore (wrong)':<42} {mean_wrong:>20.4f}")
    print(f"{'AUC (-EigenScore as truth predictor)':<42} {auc:>20.3f}")
    print(f"{'vs §13.10 baseline (0.661)':<42} "
          f"{auc - BASELINE_AUC:>+20.3f}")
    print(f"{'Classification':<42} {classification:>20}")
    print()
    print(f"Recommendation: {recommendation}")

    # --- Markdown report --- #
    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / (
        f"probe_eigenscore_{args.benchmark}{args.suffix}.md"
    )
    deviation_note = (
        ""
        if layer_is_default
        else f"  ⚠ §13.12 DEVIATION: non-default layer (pinned default = {num_hidden_layers // 2})\n"
    )
    lines = [
        "# §13.12 Experiment — EigenScore Embedding-Space Probe\n",
        "Reference: Chen, Quan, Jia, Bao, Liu (2024). "
        "\"INSIDE: LLMs' Internal States Retain the Power of "
        "Hallucination Detection.\" ICLR 2024.\n",
        "## Configuration\n",
        f"- **Target model:** `{args.model}`",
        f"- **Hidden-state layer:** {layer_idx} of {num_hidden_layers} "
        f"({'default — model.config.num_hidden_layers // 2' if layer_is_default else 'non-default'})",
        deviation_note,
        f"- **Hidden dimension (H):** {hidden_size}",
        f"- **Hidden-state position:** last non-pad generated token "
        f"(per-sample, falls back to prompt's last token if no non-pad "
        f"generation; {n_zero_gen} of {len(results)} questions had at "
        f"least one zero-generation sample)",
        f"- **EigenScore α:** {args.alpha:.2e}",
        f"- **NLI model (correctness label):** `{args.nli_model}`",
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
        f"- **Samples per question (K):** {args.k_samples}",
        f"- **Sampling temperature:** {args.temperature}",
        f"- **Max new tokens per sample:** {args.max_new_tokens}",
        f"- **Seed:** {args.seed}\n",
        "## Result\n",
        "| Metric | Value |",
        "|---|---|",
        f"| N questions | {len(results)} |",
        f"| Greedy accuracy (correct / N) | {n_pos}/{len(results)} = "
        f"{overall_correct_rate:.3f} |",
        f"| Mean EigenScore (all) | {float(scalars.mean()):.4f} |",
        f"| Mean EigenScore (correct) | {mean_correct:.4f} |",
        f"| Mean EigenScore (wrong) | {mean_wrong:.4f} |",
        f"| **AUC (-EigenScore as truth predictor)** | **{auc:.3f}** |",
        f"| Δ vs §13.10 baseline (0.661) | **{auc - BASELINE_AUC:+.3f}** |",
        f"| **Classification** | **`{classification}`** |\n",
        "## §13.12 pre-committed bands\n",
        f"- `AUC ≥ {STRONG_THRESHOLD}` → **EMBEDDING_SPACE_STRONG** — "
        "gates §13.9 VC-brief revision when cleared on BOTH benchmarks.",
        f"- `{INTERNAL_STRONG_THRESHOLD:.3f} ≤ AUC < {STRONG_THRESHOLD:.3f}` "
        "→ **EMBEDDING_SPACE_INTERNAL_STRONG** — strong for internal "
        "research; VC-brief still held.",
        f"- `{MARGINAL_LIFT_THRESHOLD:.3f} ≤ AUC < "
        f"{INTERNAL_STRONG_THRESHOLD:.3f}` → **EMBEDDING_SPACE_MARGINAL_LIFT** "
        "— modest but real lift above §13.10 + 0.02.",
        f"- `{SATURATION_LOWER:.3f} ≤ AUC ≤ "
        f"{MARGINAL_LIFT_THRESHOLD:.3f}` → **EMBEDDING_SPACE_SATURATION** "
        f"— within ±{SATURATION_DELTA} of §13.10's {BASELINE_AUC} "
        "baseline.",
        f"- `AUC < {SATURATION_LOWER:.3f}` → **EMBEDDING_SPACE_ANTI_FINDING** "
        "— pause LLM track pending compound revision.\n",
        "## Recommendation\n",
        recommendation + "\n",
        "## Interpretation guidance\n",
        "This probe tests Chen 2024's INSIDE / EigenScore — covariance "
        "of mid-layer hidden states across K=10 sampled generations. "
        "The §13.10 single-model semantic-entropy result (AUC 0.661 on "
        "both benchmarks) is the baseline; §13.11's combined "
        "CROSS_FAMILY_ANTI_FINDING established that the §1.3 cross-"
        "family ensemble revision did not lift past §13.10. EigenScore "
        "is the §13.8 item-2 alternative — internal-state metric "
        "rather than sample-space or ensemble metric. A lift to "
        "AUC ≥ 0.75 on both benchmarks would clear the §13.9 VC-gate; "
        "saturation (within ±0.02 of §13.10) combined with §13.11's "
        "anti would be strong evidence that single-axis revisions "
        "saturate at this scale.\n",
        "Critically: this script does NOT authorize any update to "
        "`AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` on its own. Per §13.9, "
        "the external framing revision requires "
        "`EMBEDDING_SPACE_STRONG` on BOTH benchmarks, confirmed by a "
        "second run of this script with the other `--benchmark`.\n",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nMarkdown report: {md_path}")

    if args.dump_json:
        json_path = args.out_dir / (
            f"probe_eigenscore_{args.benchmark}{args.suffix}.json"
        )
        with json_path.open("w", encoding="utf-8") as f:
            json.dump({
                "config": {
                    "model": args.model,
                    "num_hidden_layers": num_hidden_layers,
                    "hidden_size": hidden_size,
                    "layer": layer_idx,
                    "layer_is_default": layer_is_default,
                    "alpha": args.alpha,
                    "nli_model": args.nli_model,
                    "benchmark": args.benchmark,
                    "include_context": bool(args.include_context),
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
                    "n_questions_with_zero_gen_sample": n_zero_gen,
                    "greedy_accuracy": overall_correct_rate,
                    "mean_eigenscore_all": float(scalars.mean()),
                    "mean_eigenscore_correct": mean_correct,
                    "mean_eigenscore_wrong": mean_wrong,
                    "auc": auc,
                    "baseline_auc_s13_10": BASELINE_AUC,
                    "auc_delta_vs_baseline": auc - BASELINE_AUC,
                    "classification": classification,
                },
                "questions": [
                    {
                        "q_idx": r.q_idx,
                        "question": r.question,
                        "prompt": r.prompt,
                        "correct_choice": r.correct_choice,
                        "distractors": r.distractors,
                        "greedy": r.greedy,
                        "samples": r.samples,
                        "sample_lengths": r.sample_lengths,
                        "last_token_indices": r.last_token_indices,
                        "eigenscore": r.eigenscore,
                        "greedy_matches_correct": r.greedy_matches_correct,
                    }
                    for r in results
                ],
            }, f, indent=2)
        print(f"Per-question JSON dump: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
