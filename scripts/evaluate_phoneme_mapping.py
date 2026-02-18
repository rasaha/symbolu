#!/usr/bin/env python3
"""
Evaluate Phoneme Mapping as BCVF Signal — Real Model Inference
===============================================================

Tests whether the Sanskrit phoneme prior produces structured,
non-random signal when evaluated against real LLM inference.

Unlike validate_phoneme_bcvf.py --dry-run (which uses fake tokenizers
that produce garbage G2P), this script:

    1. Loads a REAL model (GPT-2 / Phi-3 / any HF causal LM)
    2. Builds the token-phoneme matrix with REAL HybridG2P
    3. Validates structural properties of the REAL matrix
    4. Runs inference and compares REAL vs RANDOM phoneme priors
    5. Reports varna mapping coverage and varga clustering

The core question answered:

    Is the Sanskrit phoneme system producing structured, non-random
    signal aligned with linguistic grouping during real inference?

Usage::

    # Offline: train phoneme predictor, then test BCVF during inference
    python scripts/evaluate_phoneme_mapping.py --offline --samples 200

    # More training epochs, higher LR
    python scripts/evaluate_phoneme_mapping.py --offline --train-epochs 10 --train-lr 3e-3

    # Skip training (test with random MLP — untrained baseline)
    python scripts/evaluate_phoneme_mapping.py --offline --no-train --samples 200

    # GPT-2 (requires network for first download)
    python scripts/evaluate_phoneme_mapping.py --model gpt2 --samples 500

    # Phi-3 (larger, better signal)
    python scripts/evaluate_phoneme_mapping.py --model phi3 --samples 300

    # Lambda sweep with JSON output
    python scripts/evaluate_phoneme_mapping.py --offline --lambdas 0.0 0.1 0.5 1.0 --output report.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import torch
import torch.nn.functional as F

from csr_phoneme_provider import (
    ARPABET_TO_VARNA,
    PHONEME_MAP_ARPABET,
    CSRPhonemeHead,
    CSRPhonemeHeadConfig,
    HybridG2P,
    PhonemeBCVF,
    PhonemeBCVFConfig,
    create_phoneme_bcvf,
)
from varna_mapping import (
    VARGA_GROUPS,
    VRITTI_LABELS,
    VOWEL_STATES,
    get_varga,
    get_vritti,
)

# ---------------------------------------------------------------------------
# Model aliases (same as validate_bcvf_signal.py)
# ---------------------------------------------------------------------------

MODEL_ALIASES = {
    "gpt2": "gpt2",
    "phi2": "microsoft/phi-2",
    "phi3": "microsoft/phi-3.5-mini-instruct",
    "phi4": "microsoft/Phi-4-mini-instruct",
    "stablelm": "stabilityai/stablelm-zephyr-3b",
    "openllama": "openlm-research/open_llama_3b_v2",
}


# =========================================================================
# Result Dataclasses
# =========================================================================


@dataclass
class TrainingReport:
    """Phoneme predictor MLP training metrics."""
    epochs: int = 0
    train_steps: int = 0
    final_loss: float = 0.0
    initial_loss: float = 0.0
    best_loss: float = 0.0
    # Phoneme prediction quality
    phoneme_accuracy_before: float = 0.0
    phoneme_accuracy_after: float = 0.0
    # Prior quality
    prior_ratio_before: float = 0.0
    prior_ratio_after: float = 0.0
    elapsed_seconds: float = 0.0


@dataclass
class MatrixStructureReport:
    """Structural properties of the token-phoneme matrix."""
    vocab_size: int = 0
    num_phonemes: int = 0
    tokens_mapped: int = 0
    mapping_rate: float = 0.0
    # Sparsity
    mean_active_phonemes: float = 0.0
    max_active_phonemes: int = 0
    # Varga coverage
    varga_coverage: Dict[str, int] = field(default_factory=dict)
    # Frequency distribution
    phoneme_frequency_cv: float = 0.0
    top_5_phonemes: List[Tuple[str, float]] = field(default_factory=list)
    bottom_5_phonemes: List[Tuple[str, float]] = field(default_factory=list)
    # Real vs random
    real_cv: float = 0.0
    random_cv: float = 0.0
    real_beats_random: bool = False


@dataclass
class LambdaResult:
    """Inference diagnostics for one lambda value."""
    lambda_value: float
    # Token-level
    argmax_flip_rate: float = 0.0
    mean_kl: float = 0.0
    delta_nll: float = 0.0
    entropy_delta: float = 0.0
    accuracy_base: float = 0.0
    accuracy_biased: float = 0.0
    delta_accuracy: float = 0.0
    # Phoneme constraint
    mean_phi_selected: float = 0.0
    mean_phi_topk: float = 0.0
    var_logphi: float = 0.0
    # Real vs random comparison
    var_logphi_real: float = 0.0
    var_logphi_random: float = 0.0
    real_random_ratio: float = 0.0
    # Timing
    elapsed_seconds: float = 0.0
    n_positions: int = 0


@dataclass
class VarnaUsageReport:
    """Which varnas and vrittis are actually activated during inference."""
    total_tokens_decoded: int = 0
    varna_hit_counts: Dict[str, int] = field(default_factory=dict)
    varga_hit_counts: Dict[str, int] = field(default_factory=dict)
    vritti_hit_counts: Dict[str, int] = field(default_factory=dict)
    top_10_varnas: List[Tuple[str, int]] = field(default_factory=list)


@dataclass
class FullReport:
    """Complete evaluation report."""
    model_name: str
    model_params: str
    device: str
    n_positions: int
    matrix_structure: MatrixStructureReport = field(default_factory=MatrixStructureReport)
    training: Optional[TrainingReport] = None
    lambda_results: List[LambdaResult] = field(default_factory=list)
    varna_usage: VarnaUsageReport = field(default_factory=VarnaUsageReport)
    verdict: str = ""
    failure_modes: List[str] = field(default_factory=list)


# =========================================================================
# Model Loading
# =========================================================================


def load_model(
    model_name: str,
    device: str,
    dtype: str,
) -> Tuple[Any, Any, str]:
    """Load HuggingFace model + tokenizer. Returns (model, tokenizer, device)."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    resolved = MODEL_ALIASES.get(model_name.lower().replace("-", "").replace("_", ""), model_name)
    print(f"Loading model: {resolved}")

    torch_dtype = None
    if dtype == "float16":
        torch_dtype = torch.float16
    elif dtype == "bfloat16":
        torch_dtype = torch.bfloat16
    elif dtype == "float32":
        torch_dtype = torch.float32

    tokenizer = AutoTokenizer.from_pretrained(resolved)
    model = AutoModelForCausalLM.from_pretrained(
        resolved,
        torch_dtype=torch_dtype,
        low_cpu_mem_usage=True,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if device != "auto":
        model = model.to(device)
    model.eval()

    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Loaded: {n_params / 1e6:.1f}M params, dtype={next(model.parameters()).dtype}")

    return model, tokenizer, device


def load_offline_model(device: str) -> Tuple[Any, Any, str]:
    """
    Create random-weight GPT-2 with a REAL-WORD tokenizer.

    Unlike the old dry-run (which used hash-based fake tokenizer producing
    garbage strings), this tokenizer decodes every token ID to an actual
    English word, so HybridG2P produces REAL phoneme decompositions.

    The model weights are random — we don't care about prediction quality.
    What we're testing is whether the phoneme matrix built from a real
    vocabulary has structural properties during inference.
    """
    from transformers import GPT2Config, GPT2LMHeadModel

    # A real English vocabulary (1000 common words)
    # These are actual English words that HybridG2P can decompose
    _WORDS = [
        # Function words
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "must", "dare",
        "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
        "into", "through", "during", "before", "after", "above", "below",
        "between", "under", "over", "about", "against", "among", "within",
        "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
        "neither", "each", "every", "all", "any", "few", "more", "most",
        "other", "some", "such", "no", "only", "same", "than", "too", "very",
        "that", "this", "these", "those", "what", "which", "who", "whom",
        "how", "when", "where", "why", "if", "then", "because", "although",
        # Common nouns
        "time", "year", "people", "way", "day", "man", "woman", "child",
        "world", "life", "hand", "part", "place", "case", "week", "company",
        "system", "program", "question", "work", "government", "number",
        "night", "point", "home", "water", "room", "mother", "area", "money",
        "story", "fact", "month", "lot", "right", "study", "book", "eye",
        "job", "word", "business", "issue", "side", "kind", "head", "house",
        "service", "friend", "father", "power", "hour", "game", "line",
        "end", "member", "law", "car", "city", "community", "name",
        "president", "team", "minute", "idea", "body", "information", "back",
        "parent", "face", "others", "level", "office", "door", "health",
        "person", "art", "war", "history", "party", "result", "change",
        "morning", "reason", "research", "girl", "guy", "moment", "air",
        "teacher", "force", "education",
        # Common verbs
        "say", "get", "make", "go", "know", "take", "see", "come", "think",
        "look", "want", "give", "use", "find", "tell", "ask", "work", "seem",
        "feel", "try", "leave", "call", "keep", "let", "begin", "show",
        "hear", "play", "run", "move", "live", "believe", "bring", "happen",
        "write", "provide", "sit", "stand", "lose", "pay", "meet", "include",
        "continue", "set", "learn", "change", "lead", "understand", "watch",
        "follow", "stop", "create", "speak", "read", "allow", "add", "spend",
        "grow", "open", "walk", "win", "offer", "remember", "love", "consider",
        "appear", "buy", "wait", "serve", "die", "send", "expect", "build",
        "stay", "fall", "cut", "reach", "kill", "remain", "suggest", "raise",
        "pass", "sell", "require", "report", "decide", "pull",
        # Adjectives
        "good", "new", "first", "last", "long", "great", "little", "own",
        "old", "right", "big", "high", "different", "small", "large", "next",
        "early", "young", "important", "public", "bad", "same", "able",
        "free", "strong", "real", "hard", "full", "special", "easy", "clear",
        "recent", "certain", "personal", "open", "red", "dark", "simple",
        "natural", "sure", "past", "common", "whole", "current", "likely",
        "short", "single", "possible", "deep", "true", "serious", "human",
        "local", "final", "cold", "white", "black", "blue", "green",
        # Ka-varga (K, G) heavy words
        "karma", "king", "cage", "kick", "gap", "gift", "gang", "guess",
        "kiss", "cake", "goal", "gate", "gain", "game", "gone", "grab",
        "grid", "grip", "grow", "gust", "kite", "knot", "keen", "core",
        "calm", "cape", "card", "care", "cart", "class", "clean", "climb",
        "cloth", "coast", "cook", "cool", "copy", "count", "cover", "cross",
        # Pa-varga (P, B, M) heavy words
        "palm", "push", "pump", "bump", "bomb", "plum", "plug", "plan",
        "plot", "poem", "pool", "pose", "post", "pour", "pray", "pull",
        "pure", "bind", "bird", "bite", "bone", "born", "bowl", "burn",
        "moon", "mass", "math", "mild", "mine", "mood", "much",
        # Ta-varga (T, D) heavy words
        "task", "test", "tide", "tile", "tool", "tour", "trap", "trim",
        "tube", "dust", "date", "deal", "debt", "deck", "deed", "deer",
        "diet", "dirt", "dish", "dock", "dose", "down", "drag", "draw",
        "drop", "drum", "dull", "dump", "duty",
        # Fricative heavy words (F, S, SH)
        "fish", "flat", "flow", "foam", "fold", "food", "fork", "form",
        "soft", "safe", "sail", "salt", "sand", "save", "seed", "sell",
        "ship", "shop", "shot", "show", "shut", "sign", "silk", "sing",
        "skin", "slip", "slow", "snap", "snow", "soap", "sort", "soul",
        "sour", "spin", "spot", "star", "stem", "step", "stir", "suit",
        "surf", "swim", "shift", "shelf", "shame", "shape", "share", "sharp",
        # Nasal heavy words (M, N, NG)
        "morning", "meaning", "mining", "naming", "running", "singing",
        "humming", "manner", "mental", "minute", "monitor", "mount",
        "nerve", "north", "nurse", "nine", "night", "noise", "none", "noon",
        # Mixed / filler
        "able", "above", "across", "after", "along", "always", "among",
        "anger", "animal", "answer", "apart", "apple", "arise", "aside",
        "atom", "avoid", "award", "basic", "beach", "being", "below",
        "bench", "blade", "blank", "blast", "blend", "blind", "block",
        "blood", "blown", "board", "brain", "brand", "brave", "bread",
        "break", "brief", "broad", "brown", "brush", "bunch", "burst",
        "cabin", "chain", "chair", "charm", "chase", "cheap", "check",
        "cheek", "chief", "chunk", "claim", "clash", "cliff", "clock",
        "cloud", "coach", "coral", "crack", "craft", "crash", "cream",
        "crime", "crowd", "crush", "curve", "dance", "death", "delay",
        "depth", "devil", "doubt", "draft", "drain", "dream", "dress",
        "drift", "drink", "drive", "eager", "earth", "elite", "empty",
        "enemy", "enjoy", "enter", "equal", "error", "event", "exact",
        "exist", "extra", "faith", "false", "fancy", "fault", "feast",
        "field", "fifth", "fight", "final", "flame", "flash", "flesh",
        "float", "flood", "floor", "focus", "frame", "fresh", "front",
        "fruit", "ghost", "giant", "given", "glass", "globe", "glory",
        "grace", "grade", "grain", "grand", "grant", "grass", "grave",
        "green", "grind", "gross", "group", "grown", "guard", "guide",
        "happy", "harsh", "haven", "heart", "heavy", "hence", "horse",
        "hotel", "humor", "image", "index", "inner", "input", "irony",
        "issue", "ivory", "jewel", "joint", "juice", "labor", "laser",
        "later", "laugh", "layer", "lease", "legal", "lemon", "light",
        "limit", "linen", "liver", "loose", "lover", "lower", "lucky",
        "lunch", "magic", "major", "maker", "march", "match", "mayor",
        "media", "mercy", "metal", "midst", "might", "minor", "model",
        "moral", "motor", "mount", "mouse", "mouth", "music", "naked",
        "nerve", "noble", "novel", "ocean", "offer", "orbit", "order",
        "organ", "outer", "owner", "oxide", "paint", "panel", "panic",
        "patch", "pause", "peace", "penny", "phase", "phone", "photo",
        "piano", "pilot", "pitch", "pixel", "pizza", "place", "plain",
        "plane", "plant", "plate", "plaza", "plead", "point", "pound",
        "press", "price", "pride", "prime", "print", "prior", "prize",
        "proof", "proud", "queen", "quest", "quick", "quiet", "quota",
        "radar", "radio", "raise", "rally", "range", "rapid", "ratio",
        "realm", "rebel", "reign", "relax", "reply", "rider", "ridge",
        "rifle", "river", "robot", "rocky", "roman", "rough", "round",
        "route", "royal", "rural", "salad", "scale", "scene", "scope",
        "score", "sense", "serve", "seven", "shade", "shake", "shame",
        "shark", "sharp", "sheer", "shell", "shock", "shore", "shout",
        "sight", "sixth", "skill", "skull", "slave", "sleep", "slide",
        "smile", "smoke", "solar", "solid", "solve", "sound", "south",
        "space", "spare", "spark", "speak", "speed", "spell", "split",
        "sport", "spray", "squad", "stack", "staff", "stage", "stake",
        "stale", "stamp", "stare", "start", "state", "steal", "steam",
        "steel", "steep", "still", "stock", "stone", "store", "storm",
        "story", "stove", "stuff", "style", "sugar", "super", "swamp",
        "swear", "sweep", "sweet", "swing", "sword", "table", "taste",
        "teach", "thick", "thing", "thing", "third", "throw", "tight",
        "tired", "title", "today", "token", "topic", "total", "touch",
        "tough", "tower", "trace", "track", "trade", "trail", "train",
        "trait", "trash", "treat", "trend", "trial", "tribe", "trick",
        "troop", "truck", "truly", "trust", "truth", "twist", "ultra",
        "uncle", "under", "union", "unite", "unity", "upper", "upset",
        "urban", "usage", "usual", "valid", "value", "verse", "video",
        "vigor", "virus", "visit", "vital", "vocal", "voice", "voter",
        "waste", "watch", "water", "weigh", "weird", "wheat", "wheel",
        "where", "while", "white", "whole", "whose", "woman", "world",
        "worst", "worth", "wound", "wrist", "write", "yield", "youth",
    ]

    vocab_size = len(_WORDS)
    d_model = 128

    print(f"OFFLINE MODE: Random-weight GPT-2 with {vocab_size}-word English vocabulary")
    print(f"  Unlike --dry-run: tokenizer.decode(id) returns REAL English words")
    print(f"  So HybridG2P produces REAL phoneme decompositions")

    config = GPT2Config(
        vocab_size=vocab_size,
        n_positions=512,
        n_embd=d_model,
        n_layer=4,
        n_head=4,
        n_inner=d_model * 4,
        bos_token_id=0,
        eos_token_id=1,
    )
    model = GPT2LMHeadModel(config)
    model.to(device).eval()

    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Model: {n_params / 1e6:.1f}M params, d_model={d_model}, vocab={vocab_size}")

    class _RealWordTokenizer:
        """Tokenizer that maps IDs to real English words for G2P."""
        def __init__(self, words):
            self._words = words
            self.vocab_size = len(words)
            self.pad_token_id = 0
            self.pad_token = words[0]
            self.eos_token_id = 1
            self.eos_token = words[1]
            self.bos_token_id = None
            self.unk_token_id = None
            self.sep_token_id = None
            self.cls_token_id = None
            self.mask_token_id = None

        def decode(self, ids, **kwargs):
            if isinstance(ids, (list, tuple)):
                if len(ids) == 1:
                    idx = ids[0]
                    return self._words[idx] if 0 <= idx < len(self._words) else "unknown"
                return " ".join(
                    self._words[i] if 0 <= i < len(self._words) else "unknown"
                    for i in ids
                )
            idx = ids
            return self._words[idx] if 0 <= idx < len(self._words) else "unknown"

        def encode(self, text, return_tensors=None, truncation=True,
                   max_length=512, **kwargs):
            # Simple word-to-id encoding
            words = text.lower().split()
            word_to_id = {w: i for i, w in enumerate(self._words)}
            ids = [word_to_id.get(w, 2) for w in words][:max_length]
            if return_tensors == "pt":
                return torch.tensor([ids], dtype=torch.long)
            return ids

        def __len__(self):
            return self.vocab_size

    tokenizer = _RealWordTokenizer(_WORDS)
    return model, tokenizer, device


def load_texts(max_texts: int = 50) -> List[str]:
    """Load evaluation texts. Falls back to built-in if datasets unavailable."""
    try:
        from datasets import load_dataset
        ds = load_dataset("wikitext", "wikitext-103-raw-v1", split="test")
        texts = [t for t in ds["text"] if len(t.strip()) > 200]
        rng = np.random.RandomState(42)
        rng.shuffle(texts)
        print(f"  Loaded {len(texts[:max_texts])} passages from WikiText-103")
        return texts[:max_texts]
    except Exception as e:
        print(f"  datasets unavailable ({e}), using built-in texts")
        return _builtin_texts()[:max_texts]


def _builtin_texts() -> List[str]:
    """Deterministic fallback texts."""
    return [
        (
            "The transformer architecture revolutionized natural language "
            "processing by introducing self-attention mechanisms that allow "
            "models to weigh the importance of different parts of the input "
            "sequence simultaneously. Unlike recurrent neural networks, "
            "transformers process all positions in parallel, making them "
            "significantly faster to train on modern hardware. The key "
            "innovation is the scaled dot-product attention, which computes "
            "compatibility scores between query and key vectors. "
        ) * 5,
        (
            "In probability theory, calibration refers to the property that "
            "when a model assigns probability p to an event, that event "
            "should occur approximately p fraction of the time. A perfectly "
            "calibrated classifier has the property that among all instances "
            "where it predicts seventy percent confidence, exactly seventy "
            "percent are correct. Expected Calibration Error measures the "
            "average gap between predicted confidence and actual accuracy. "
        ) * 5,
        (
            "The Sanskrit phoneme system organizes sounds by articulation "
            "point and manner of production. Gutturals are produced at the "
            "throat, palatals at the palate, retroflexes at the roof of the "
            "mouth, dentals at the teeth, and labials at the lips. Each "
            "group contains voiced and voiceless variants, aspirated and "
            "unaspirated forms, creating a systematic classification that "
            "predates modern phonetics by millennia. "
        ) * 5,
        (
            "Machine learning models learn distributed representations where "
            "each concept is represented by a pattern of activity across many "
            "neurons, and each neuron participates in representing many "
            "concepts. This distributed encoding allows generalization through "
            "shared features. Word embeddings capture semantic relationships "
            "such that king minus man plus woman approximately equals queen. "
        ) * 5,
        (
            "Statistical hypothesis testing provides a framework for making "
            "decisions about population parameters based on sample data. The "
            "null hypothesis represents the default assumption, typically that "
            "there is no effect or no difference. The alternative hypothesis "
            "represents the claim being tested. The p-value measures the "
            "probability of observing results at least as extreme as those "
            "obtained, assuming the null hypothesis is true. "
        ) * 5,
        (
            "Gradient descent optimizes neural network parameters by computing "
            "the gradient of the loss function with respect to each parameter "
            "and updating in the opposite direction. Stochastic gradient "
            "descent uses random mini-batches rather than the full dataset, "
            "providing noisy but computationally efficient gradient estimates. "
            "Adam combines momentum with adaptive learning rates per parameter. "
        ) * 5,
    ]


# =========================================================================
# Phase 1: Matrix Structure Analysis
# =========================================================================


def analyze_matrix_structure(
    csr_head: CSRPhonemeHead,
    tokenizer: Any,
    verbose: bool = False,
) -> MatrixStructureReport:
    """Analyze structural properties of the real token-phoneme matrix."""
    matrix = csr_head._token_phoneme_weights  # [V, P]
    V, P = matrix.shape
    phoneme_list = list(PHONEME_MAP_ARPABET.keys())

    report = MatrixStructureReport(vocab_size=V, num_phonemes=P)

    # --- Mapping rate ---
    threshold = 0.01
    row_sums = matrix.sum(dim=1)
    mapped_mask = row_sums > threshold
    report.tokens_mapped = int(mapped_mask.sum().item())
    report.mapping_rate = report.tokens_mapped / V

    # --- Sparsity ---
    active_per_row = (matrix > threshold).float().sum(dim=1)
    active_mapped = active_per_row[mapped_mask]
    if len(active_mapped) > 0:
        report.mean_active_phonemes = active_mapped.mean().item()
        report.max_active_phonemes = int(active_mapped.max().item())

    # --- Phoneme frequency ---
    col_sums = matrix.sum(dim=0)
    nonzero_cols = col_sums[col_sums > 0]
    if len(nonzero_cols) > 1:
        report.phoneme_frequency_cv = (
            nonzero_cols.std().item() / (nonzero_cols.mean().item() + 1e-8)
        )

    # Top / bottom phonemes
    sorted_indices = col_sums.argsort(descending=True)
    report.top_5_phonemes = [
        (phoneme_list[int(idx)], col_sums[int(idx)].item())
        for idx in sorted_indices[:5]
        if col_sums[int(idx)] > 0
    ]
    nonzero_sorted = [
        (phoneme_list[int(idx)], col_sums[int(idx)].item())
        for idx in sorted_indices
        if col_sums[int(idx)] > 0
    ]
    report.bottom_5_phonemes = nonzero_sorted[-5:] if len(nonzero_sorted) >= 5 else nonzero_sorted

    # --- Varga coverage ---
    g2p = HybridG2P(use_neural=False, lazy_init=True)
    varga_counts: Dict[str, int] = {name: 0 for name in VARGA_GROUPS}

    for token_id in range(V):
        if not mapped_mask[token_id]:
            continue
        try:
            token_str = tokenizer.decode([token_id])
            phonemes = g2p.get_phonemes(token_str)
            for ph in phonemes:
                vg = get_varga(ph)
                if vg and vg in varga_counts:
                    varga_counts[vg] += 1
        except Exception:
            continue
    report.varga_coverage = varga_counts

    # --- Real vs random comparison ---
    torch.manual_seed(99)
    random_matrix = torch.zeros(V, P)
    for i in range(V):
        if not mapped_mask[i]:
            continue
        n_active = torch.randint(2, 5, (1,)).item()
        indices = torch.randperm(P)[:n_active]
        values = torch.rand(n_active)
        random_matrix[i, indices] = values / values.sum()

    real_freq = matrix.sum(dim=0)
    rand_freq = random_matrix.sum(dim=0)
    real_nz = real_freq[real_freq > 0]
    rand_nz = rand_freq[rand_freq > 0]

    report.real_cv = real_nz.std().item() / (real_nz.mean().item() + 1e-8) if len(real_nz) > 1 else 0
    report.random_cv = rand_nz.std().item() / (rand_nz.mean().item() + 1e-8) if len(rand_nz) > 1 else 0
    report.real_beats_random = report.real_cv > report.random_cv * 0.5

    if verbose:
        print(f"\n  Matrix Structure:")
        print(f"    Vocab: {V:,}, Phonemes: {P}")
        print(f"    Mapped: {report.tokens_mapped:,} ({report.mapping_rate:.1%})")
        print(f"    Mean active phonemes/token: {report.mean_active_phonemes:.1f}")
        print(f"    Phoneme freq CV: {report.phoneme_frequency_cv:.4f}")
        print(f"    Real CV: {report.real_cv:.4f}  Random CV: {report.random_cv:.4f}  "
              f"{'PASS' if report.real_beats_random else 'FAIL'}")
        print(f"    Top phonemes: {report.top_5_phonemes}")
        print(f"    Varga coverage: {report.varga_coverage}")

    return report


# =========================================================================
# Phase 0: Train Phoneme Predictor MLP
# =========================================================================


def train_phoneme_predictor(
    model: Any,
    tokenizer: Any,
    bcvf: PhonemeBCVF,
    texts: List[str],
    epochs: int = 3,
    lr: float = 1e-3,
    max_seq_len: int = 512,
    device: str = "cpu",
    verbose: bool = False,
) -> TrainingReport:
    """
    Train the phoneme predictor MLP inside PhonemeBCVF.

    The MLP learns: given hidden state h_t from position t,
    predict the phoneme decomposition of the NEXT token (t+1).

    Target: token_phoneme_weights[next_token_id]  (from Sanskrit G2P)
    Loss:   BCE between σ(MLP(h_t)) and target phoneme vector

    The base model is FROZEN — only the phoneme predictor MLP trains.
    This teaches the MLP to read the model's hidden state and predict
    which phonemes will appear next.
    """
    t0 = time.time()

    token_phoneme = bcvf.token_phoneme_weights  # [V, P] buffer

    # Freeze base model, train only phoneme predictor + lambda
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)

    trainable = list(bcvf.phoneme_predictor.parameters())
    trainable.append(bcvf.lambda_base)
    if hasattr(bcvf, 'lambda_net'):
        trainable.extend(bcvf.lambda_net.parameters())

    optimizer = torch.optim.Adam(trainable, lr=lr)

    # --- Measure BEFORE training ---
    acc_before, ratio_before = _measure_phoneme_quality(
        model, tokenizer, bcvf, texts[:2], max_seq_len, device,
    )

    report = TrainingReport(
        epochs=epochs,
        phoneme_accuracy_before=acc_before,
        prior_ratio_before=ratio_before,
    )

    all_losses = []
    step = 0

    for epoch in range(epochs):
        epoch_losses = []
        for text in texts:
            tokens = tokenizer.encode(
                text, return_tensors="pt", truncation=True,
                max_length=max_seq_len,
            ).to(device)

            if tokens.shape[1] < 10:
                continue

            # Get hidden states from frozen model
            with torch.no_grad():
                outputs = model(tokens, output_hidden_states=True, use_cache=False)
                hidden = outputs.hidden_states[-1].float()  # [1, T, D]

            # Targets: phoneme vector for each NEXT token
            next_ids = tokens[0, 1:]                         # [T-1]
            target_phonemes = token_phoneme[next_ids]         # [T-1, P]
            # Normalize to [0,1] for BCE
            target_binary = (target_phonemes > 0.05).float()  # [T-1, P]

            # Predict from h_t at positions 0..T-2
            h_context = hidden[:, :-1, :]                     # [1, T-1, D]
            pred_phi = bcvf.predict_phonemes(h_context)       # [1, T-1, P]
            pred_phi = pred_phi.squeeze(0)                    # [T-1, P]

            # BCE loss
            loss = F.binary_cross_entropy(pred_phi, target_binary)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            loss_val = loss.item()
            epoch_losses.append(loss_val)
            all_losses.append(loss_val)
            step += 1

            if step == 1:
                report.initial_loss = loss_val

        epoch_mean = np.mean(epoch_losses) if epoch_losses else 0
        if verbose:
            print(f"    Epoch {epoch+1}/{epochs}: loss={epoch_mean:.4f} ({len(epoch_losses)} batches)")

    # --- Measure AFTER training ---
    bcvf.eval()
    acc_after, ratio_after = _measure_phoneme_quality(
        model, tokenizer, bcvf, texts[:2], max_seq_len, device,
    )

    report.train_steps = step
    report.final_loss = all_losses[-1] if all_losses else 0
    report.best_loss = min(all_losses) if all_losses else 0
    report.phoneme_accuracy_after = acc_after
    report.prior_ratio_after = ratio_after
    report.elapsed_seconds = time.time() - t0

    return report


def _measure_phoneme_quality(
    model: Any,
    tokenizer: Any,
    bcvf: PhonemeBCVF,
    texts: List[str],
    max_seq_len: int,
    device: str,
) -> Tuple[float, float]:
    """Measure phoneme prediction accuracy and prior ratio on a few texts."""
    acc_vals = []
    ratio_vals = []

    with torch.no_grad():
        for text in texts:
            tokens = tokenizer.encode(
                text, return_tensors="pt", truncation=True,
                max_length=max_seq_len,
            ).to(device)

            if tokens.shape[1] < 10:
                continue

            outputs = model(tokens, output_hidden_states=True, use_cache=False)
            hidden = outputs.hidden_states[-1].float()

            h_context = hidden[:, :-1, :]
            next_ids = tokens[:, 1:]

            diag = bcvf.get_diagnostics(h_context, next_ids)
            acc_vals.append(diag['phoneme_accuracy'].item())
            ratio_vals.append(diag['prior_ratio'].item())

    acc = float(np.mean(acc_vals)) if acc_vals else 0.0
    ratio = float(np.mean(ratio_vals)) if ratio_vals else 0.0
    return acc, ratio


# =========================================================================
# Phase 2: Inference Evaluation
# =========================================================================


def evaluate_inference(
    model: Any,
    tokenizer: Any,
    csr_head: CSRPhonemeHead,
    texts: List[str],
    lambda_value: float,
    n_positions: int,
    device: str,
    max_seq_len: int = 512,
    trained_bcvf: Optional[PhonemeBCVF] = None,
) -> Tuple[LambdaResult, VarnaUsageReport]:
    """
    Run inference evaluation for one lambda value.

    Compares real phoneme matrix vs random baseline at every position.
    Tracks which varnas/vrittis are activated by selected tokens.

    If trained_bcvf is provided, reuses it (with updated lambda).
    Otherwise creates a fresh (untrained) BCVF.
    """
    t0 = time.time()

    # Build or reuse real BCVF
    if trained_bcvf is not None:
        real_bcvf = trained_bcvf
        # Update lambda for this sweep point
        with torch.no_grad():
            real_bcvf.lambda_base.fill_(lambda_value)
        real_bcvf.eval()
    else:
        real_bcvf = create_phoneme_bcvf(csr_head, lambda_init=lambda_value, dynamic_lambda=False)
        real_bcvf.to(device).eval()

    # Build random BCVF (same shape, random weights)
    torch.manual_seed(42)
    V = csr_head.config.vocab_size
    P = csr_head.num_phonemes
    random_weights = torch.zeros(V, P)
    mapped_mask = csr_head._token_phoneme_weights.sum(dim=1) > 0.01
    for i in range(V):
        if not mapped_mask[i]:
            continue
        n = torch.randint(2, 5, (1,)).item()
        idx = torch.randperm(P)[:n]
        vals = torch.rand(n)
        random_weights[i, idx] = vals / vals.sum()

    rand_config = PhonemeBCVFConfig(
        d_model=csr_head.config.d_model,
        num_phonemes=P,
        vocab_size=V,
        lambda_init=lambda_value,
        dynamic_lambda=False,
    )
    random_bcvf = PhonemeBCVF(rand_config, token_phoneme_weights=random_weights)
    random_bcvf.to(device).eval()

    # G2P for varna tracking
    g2p = HybridG2P(use_neural=False, lazy_init=True)
    phoneme_list = list(PHONEME_MAP_ARPABET.keys())

    # Accumulators
    flips = 0
    kl_values = []
    nll_base_values = []
    nll_biased_values = []
    entropy_base_values = []
    entropy_biased_values = []
    phi_selected_values = []
    phi_topk_values = []
    logphi_vars_real = []
    logphi_vars_random = []
    correct_base = 0
    correct_biased = 0
    total_positions = 0

    # Varna tracking
    varna_hits: Dict[str, int] = {}
    varga_hits: Dict[str, int] = {name: 0 for name in VARGA_GROUPS}
    vritti_hits: Dict[str, int] = {}

    for text in texts:
        if total_positions >= n_positions:
            break

        tokens = tokenizer.encode(
            text, return_tensors="pt", truncation=True,
            max_length=max_seq_len,
        ).to(device)

        if tokens.shape[1] < 10:
            continue

        with torch.no_grad():
            outputs = model(tokens, output_hidden_states=True, use_cache=False)
            logits_all = outputs.logits.float()
            hidden_all = outputs.hidden_states[-1].float()

        T = tokens.shape[1]
        ground_truth = tokens[0, 1:]

        positions = min(T - 1, n_positions - total_positions)
        for t in range(positions):
            h_t = hidden_all[:, t:t+1, :]
            base_logits = logits_all[:, t:t+1, :]
            gt_token = int(ground_truth[t].item())

            # Real BCVF
            with torch.no_grad():
                real_result = real_bcvf(base_logits, h_t)
                biased_logits = real_result['logits']
                phi_prior = real_result['phoneme_prior']

                # Random BCVF (same h_t, same base logits)
                rand_result = random_bcvf(base_logits, h_t)

            base_2d = base_logits.squeeze(1)
            biased_2d = biased_logits.squeeze(1)
            phi_1d = phi_prior.squeeze()

            # === Token-level ===
            base_top = torch.argmax(base_2d, dim=-1).item()
            biased_top = torch.argmax(biased_2d, dim=-1).item()
            if base_top != biased_top:
                flips += 1

            if base_top == gt_token:
                correct_base += 1
            if biased_top == gt_token:
                correct_biased += 1

            p_base = F.softmax(base_2d, dim=-1)
            p_biased = F.softmax(biased_2d, dim=-1)
            kl = F.kl_div(p_biased.log(), p_base, reduction='batchmean').item()
            kl_values.append(kl)

            nll_base = -F.log_softmax(base_2d, dim=-1)[0, gt_token].item()
            nll_biased = -F.log_softmax(biased_2d, dim=-1)[0, gt_token].item()
            nll_base_values.append(nll_base)
            nll_biased_values.append(nll_biased)

            eps = 1e-8
            H_base = -(p_base * (p_base + eps).log()).sum(-1).item()
            H_biased = -(p_biased * (p_biased + eps).log()).sum(-1).item()
            entropy_base_values.append(H_base)
            entropy_biased_values.append(H_biased)

            # === Phoneme constraint ===
            phi_sel = phi_1d[biased_top].item()
            phi_selected_values.append(phi_sel)

            top_k = min(50, phi_1d.shape[0])
            _, topk_idx = torch.topk(biased_2d, top_k, dim=-1)
            phi_topk = phi_1d[topk_idx.squeeze()]
            phi_topk_values.append(phi_topk.mean().item())

            # var(log(phi)) — real vs random
            logphi_real = torch.log(phi_topk + 1e-6)
            logphi_vars_real.append(logphi_real.var().item())

            rand_phi = rand_result['phoneme_prior'].squeeze()
            rand_phi_topk = rand_phi[topk_idx.squeeze()]
            logphi_rand = torch.log(rand_phi_topk + 1e-6)
            logphi_vars_random.append(logphi_rand.var().item())

            # === Varna tracking on selected token ===
            try:
                selected_str = tokenizer.decode([biased_top])
                selected_phonemes = g2p.get_phonemes(selected_str)
                for ph in selected_phonemes:
                    varna = ARPABET_TO_VARNA.get(ph)
                    if varna:
                        varna_hits[varna] = varna_hits.get(varna, 0) + 1
                    vg = get_varga(ph)
                    if vg and vg in varga_hits:
                        varga_hits[vg] += 1
                    vr = get_vritti(ph)
                    if vr:
                        vritti_hits[vr] = vritti_hits.get(vr, 0) + 1
            except Exception:
                pass

            total_positions += 1

        if total_positions % 200 == 0 and total_positions > 0:
            print(f"    [{total_positions}/{n_positions}]")

    elapsed = time.time() - t0

    # Build results
    result = LambdaResult(
        lambda_value=lambda_value,
        argmax_flip_rate=flips / max(total_positions, 1),
        mean_kl=float(np.mean(kl_values)) if kl_values else 0.0,
        delta_nll=float(np.mean(nll_biased_values) - np.mean(nll_base_values)) if nll_biased_values else 0.0,
        entropy_delta=float(np.mean(entropy_biased_values) - np.mean(entropy_base_values)) if entropy_biased_values else 0.0,
        accuracy_base=correct_base / max(total_positions, 1),
        accuracy_biased=correct_biased / max(total_positions, 1),
        delta_accuracy=(correct_biased - correct_base) / max(total_positions, 1),
        mean_phi_selected=float(np.mean(phi_selected_values)) if phi_selected_values else 0.0,
        mean_phi_topk=float(np.mean(phi_topk_values)) if phi_topk_values else 0.0,
        var_logphi=float(np.mean(logphi_vars_real)) if logphi_vars_real else 0.0,
        var_logphi_real=float(np.mean(logphi_vars_real)) if logphi_vars_real else 0.0,
        var_logphi_random=float(np.mean(logphi_vars_random)) if logphi_vars_random else 0.0,
        real_random_ratio=(
            float(np.mean(logphi_vars_real)) / (float(np.mean(logphi_vars_random)) + 1e-8)
            if logphi_vars_real and logphi_vars_random else 0.0
        ),
        elapsed_seconds=elapsed,
        n_positions=total_positions,
    )

    varna_report = VarnaUsageReport(
        total_tokens_decoded=total_positions,
        varna_hit_counts=varna_hits,
        varga_hit_counts=varga_hits,
        vritti_hit_counts=vritti_hits,
        top_10_varnas=sorted(varna_hits.items(), key=lambda x: -x[1])[:10],
    )

    return result, varna_report


# =========================================================================
# Verdict
# =========================================================================


def determine_verdict(
    matrix: MatrixStructureReport,
    results: List[LambdaResult],
) -> Tuple[str, List[str]]:
    """Determine overall verdict."""
    failures = []

    # Matrix structure checks
    if matrix.mapping_rate < 0.5:
        failures.append(f"LOW MAPPING: only {matrix.mapping_rate:.1%} of vocab mapped by G2P")

    if not matrix.real_beats_random:
        failures.append(f"RANDOM STRUCTURE: real matrix CV ({matrix.real_cv:.4f}) "
                       f"not higher than random ({matrix.random_cv:.4f})")

    # Find best non-zero lambda
    best = None
    for r in results:
        if r.lambda_value > 0:
            if best is None or r.var_logphi_real > best.var_logphi_real:
                best = r

    if best is None:
        return "INCOMPLETE", ["no_nonzero_lambda"]

    # Signal checks
    if best.mean_kl < 1e-5:
        failures.append(f"DEAD: KL={best.mean_kl:.6f} at lambda={best.lambda_value}")

    if best.var_logphi_real < 1e-4:
        failures.append(f"FLAT: var(logphi)={best.var_logphi_real:.6f} — prior has no discrimination")

    if best.entropy_delta > 0.5:
        failures.append(f"NOISE: entropy increased by {best.entropy_delta:.3f}")

    if best.argmax_flip_rate > 0.5:
        failures.append(f"DESTRUCTIVE: flip rate {best.argmax_flip_rate:.1%}")

    if best.delta_nll > 1.0:
        failures.append(f"PPL HARM: delta NLL = +{best.delta_nll:.3f}")

    # Real vs random
    if best.real_random_ratio < 0.5:
        failures.append(f"NO ADVANTAGE: real/random var(logphi) ratio = {best.real_random_ratio:.3f}")

    if not failures:
        verdict = "FUNCTIONAL — phoneme BCVF produces structured, non-random signal during inference"
    elif all("DEAD" in f or "FLAT" in f for f in failures):
        verdict = "DECORATIVE — signal exists but produces no discrimination"
    elif any("DESTRUCTIVE" in f or "PPL HARM" in f for f in failures):
        verdict = "HARMFUL — signal damages model quality"
    else:
        verdict = f"MIXED — {len(failures)} issue(s)"

    return verdict, failures


# =========================================================================
# Report Formatting
# =========================================================================


def format_report(report: FullReport) -> str:
    """Format human-readable report."""
    lines = []
    w = 90
    lines.append("=" * w)
    lines.append("Phoneme Mapping Evaluation — Real Model Inference")
    lines.append("=" * w)
    lines.append(f"Model:      {report.model_name} ({report.model_params})")
    lines.append(f"Device:     {report.device}")
    lines.append(f"Positions:  {report.n_positions}")
    lines.append("")

    # Matrix structure
    ms = report.matrix_structure
    lines.append("--- Matrix Structure ---")
    lines.append(f"  Vocab mapped:    {ms.tokens_mapped:,}/{ms.vocab_size:,} ({ms.mapping_rate:.1%})")
    lines.append(f"  Phonemes active: {ms.mean_active_phonemes:.1f} avg, {ms.max_active_phonemes} max")
    lines.append(f"  Frequency CV:    {ms.phoneme_frequency_cv:.4f}")
    lines.append(f"  Real vs Random:  CV {ms.real_cv:.4f} vs {ms.random_cv:.4f}  "
                f"{'STRUCTURED' if ms.real_beats_random else 'RANDOM'}")
    lines.append(f"  Top phonemes:    {ms.top_5_phonemes}")
    lines.append(f"  Varga coverage:  {ms.varga_coverage}")
    lines.append("")

    # Training
    if report.training is not None:
        tr = report.training
        lines.append("--- Phoneme Predictor Training ---")
        lines.append(f"  Epochs: {tr.epochs}  Steps: {tr.train_steps}  Time: {tr.elapsed_seconds:.1f}s")
        lines.append(f"  Loss:   {tr.initial_loss:.4f} -> {tr.final_loss:.4f} (best: {tr.best_loss:.4f})")
        lines.append(f"  Phoneme accuracy: {tr.phoneme_accuracy_before:.1%} -> {tr.phoneme_accuracy_after:.1%}")
        lines.append(f"  Prior ratio:      {tr.prior_ratio_before:.3f} -> {tr.prior_ratio_after:.3f}")
        lines.append("")
    else:
        lines.append("--- Phoneme Predictor: UNTRAINED (random MLP) ---")
        lines.append("")

    # Lambda sweep
    lines.append("--- Lambda Sweep ---")
    cols = ["lambda", "flip%", "KL", "dNLL", "dH", "phi_sel", "var(lgp)",
            "var_real", "var_rand", "ratio", "acc_d"]
    header = "  " + "  ".join(f"{c:>9}" for c in cols)
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))

    for r in report.lambda_results:
        row = [
            f"{r.lambda_value:9.3f}",
            f"{r.argmax_flip_rate:8.1%}",
            f"{r.mean_kl:9.5f}",
            f"{r.delta_nll:+9.4f}",
            f"{r.entropy_delta:+9.4f}",
            f"{r.mean_phi_selected:9.4f}",
            f"{r.var_logphi:9.5f}",
            f"{r.var_logphi_real:9.5f}",
            f"{r.var_logphi_random:9.5f}",
            f"{r.real_random_ratio:9.3f}",
            f"{r.delta_accuracy:+8.1%}",
        ]
        lines.append("  " + "  ".join(row))
    lines.append("")

    # Varna usage
    vu = report.varna_usage
    if vu.top_10_varnas:
        lines.append("--- Varna Usage (inference) ---")
        lines.append(f"  Top varnas:  {vu.top_10_varnas}")
        top_vargas = sorted(vu.varga_hit_counts.items(), key=lambda x: -x[1])
        lines.append(f"  Varga dist:  {top_vargas}")
        top_vrittis = sorted(vu.vritti_hit_counts.items(), key=lambda x: -x[1])[:10]
        lines.append(f"  Top vrittis: {top_vrittis}")
        lines.append("")

    # Verdict
    lines.append("=" * w)
    lines.append(f"VERDICT: {report.verdict}")
    if report.failure_modes:
        lines.append("")
        for f in report.failure_modes:
            lines.append(f"  ! {f}")
    lines.append("=" * w)

    return "\n".join(lines)


# =========================================================================
# CLI
# =========================================================================


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Evaluate phoneme mapping as BCVF signal with real model inference",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train + test (default)
  python scripts/evaluate_phoneme_mapping.py --offline --samples 200
  python scripts/evaluate_phoneme_mapping.py --offline --train-epochs 10 --train-lr 3e-3

  # Untrained baseline
  python scripts/evaluate_phoneme_mapping.py --offline --no-train --samples 200

  # Real models (require network)
  python scripts/evaluate_phoneme_mapping.py --model gpt2 --samples 500 --verbose
  python scripts/evaluate_phoneme_mapping.py --model phi3 --samples 300
  python scripts/evaluate_phoneme_mapping.py --model gpt2 --lambdas 0.0 0.1 0.5 1.0
""",
    )

    p.add_argument("--model", default="gpt2", help="HF model: gpt2, phi3, or full name")
    p.add_argument("--dtype", default="float32", choices=["float16", "bfloat16", "float32"])
    p.add_argument("--device", default="auto")
    p.add_argument("--samples", type=int, default=200, help="Number of token positions")
    p.add_argument("--max-seq-len", type=int, default=512)
    p.add_argument("--max-texts", type=int, default=50)
    p.add_argument("--lambdas", type=float, nargs="+", default=[0.0, 0.1, 0.3, 1.0])
    p.add_argument("--output", type=str, default=None, help="Save JSON report")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--offline", action="store_true",
                   help="Offline mode: random-weight GPT-2 with real-word tokenizer "
                        "(no downloads, but exercises real G2P pipeline)")

    # Training args
    p.add_argument("--train-epochs", type=int, default=3,
                   help="Epochs to train phoneme predictor MLP (0 = skip training)")
    p.add_argument("--train-lr", type=float, default=1e-3,
                   help="Learning rate for phoneme predictor training")
    p.add_argument("--no-train", action="store_true",
                   help="Skip training entirely (test with random MLP weights)")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Device
    device = args.device
    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"

    print(f"Device: {device}")

    # Load model
    if args.offline:
        model, tokenizer, device = load_offline_model(device)
    else:
        model, tokenizer, device = load_model(args.model, device, args.dtype)

    # Build CSRPhonemeHead with REAL tokenizer
    d_model = 64
    for attr in ['hidden_size', 'n_embd', 'embed_dim', 'd_model', 'dim']:
        if hasattr(model.config, attr):
            d_model = getattr(model.config, attr)
            break
    vocab_size = getattr(model.config, 'vocab_size', 50257)

    print(f"\nBuilding token-phoneme matrix with REAL G2P...")
    csr_config = CSRPhonemeHeadConfig(d_model=d_model, vocab_size=vocab_size)
    csr_head = CSRPhonemeHead(csr_config, tokenizer=tokenizer)

    if csr_head._token_phoneme_weights is None:
        print("FATAL: G2P failed to build token-phoneme matrix")
        print("  This means HybridG2P could not process any tokens from the tokenizer")
        sys.exit(1)

    # Phase 1: Matrix structure
    print("\n=== Phase 1: Matrix Structure Analysis ===")
    matrix_report = analyze_matrix_structure(csr_head, tokenizer, verbose=args.verbose)

    # Load texts
    texts = load_texts(max_texts=args.max_texts)

    n_params = sum(p.numel() for p in model.parameters())
    model_params_str = f"{n_params / 1e9:.2f}B" if n_params > 1e8 else f"{n_params / 1e6:.1f}M"

    # Phase 0: Train phoneme predictor MLP (unless --no-train)
    trained_bcvf = None
    training_report = None

    if not args.no_train and args.train_epochs > 0:
        print(f"\n=== Phase 0: Train Phoneme Predictor MLP ===")
        print(f"  Objective: MLP(h_t) → phoneme vector of next token")
        print(f"  Epochs: {args.train_epochs}, LR: {args.train_lr}")
        print(f"  Base model FROZEN — only MLP trains")

        # Create BCVF for training (lambda doesn't matter, will be overridden per sweep)
        trained_bcvf = create_phoneme_bcvf(csr_head, lambda_init=0.1, dynamic_lambda=False)
        trained_bcvf.to(device)

        training_report = train_phoneme_predictor(
            model=model,
            tokenizer=tokenizer,
            bcvf=trained_bcvf,
            texts=texts,
            epochs=args.train_epochs,
            lr=args.train_lr,
            max_seq_len=args.max_seq_len,
            device=device,
            verbose=args.verbose,
        )

        print(f"\n  Training complete ({training_report.elapsed_seconds:.1f}s):")
        print(f"    Loss: {training_report.initial_loss:.4f} → {training_report.final_loss:.4f} "
              f"(best: {training_report.best_loss:.4f})")
        print(f"    Phoneme accuracy: {training_report.phoneme_accuracy_before:.1%} → "
              f"{training_report.phoneme_accuracy_after:.1%}")
        print(f"    Prior ratio (target/mean): {training_report.prior_ratio_before:.3f} → "
              f"{training_report.prior_ratio_after:.3f}")
    else:
        if args.no_train:
            print("\n  Skipping training (--no-train)")
        else:
            print("\n  Skipping training (--train-epochs 0)")

    # Phase 2: Inference evaluation
    lambdas = sorted(set(args.lambdas))
    print(f"\n=== Phase 2: Inference Evaluation ===")
    label = "TRAINED" if trained_bcvf is not None else "UNTRAINED"
    print(f"  Phoneme predictor: {label}")
    print(f"  Lambda sweep: {lambdas}")
    print(f"  Positions: {args.samples}")

    lambda_results = []
    varna_usage = VarnaUsageReport()

    for lam in lambdas:
        print(f"\n  --- lambda = {lam} ---")
        lr, vu = evaluate_inference(
            model=model,
            tokenizer=tokenizer,
            csr_head=csr_head,
            texts=texts,
            lambda_value=lam,
            n_positions=args.samples,
            device=device,
            max_seq_len=args.max_seq_len,
            trained_bcvf=trained_bcvf,
        )
        lambda_results.append(lr)

        # Keep varna usage from the highest non-zero lambda
        if lam > 0:
            varna_usage = vu

        print(f"    flip={lr.argmax_flip_rate:.1%}  KL={lr.mean_kl:.5f}  "
              f"dNLL={lr.delta_nll:+.4f}  dH={lr.entropy_delta:+.4f}")
        print(f"    phi_sel={lr.mean_phi_selected:.4f}  var(logphi)={lr.var_logphi:.5f}")
        print(f"    real_var={lr.var_logphi_real:.5f}  rand_var={lr.var_logphi_random:.5f}  "
              f"ratio={lr.real_random_ratio:.3f}")
        print(f"    acc: {lr.accuracy_base:.1%} -> {lr.accuracy_biased:.1%}  ({lr.elapsed_seconds:.1f}s)")

    # Verdict
    verdict, failures = determine_verdict(matrix_report, lambda_results)

    report = FullReport(
        model_name=args.model,
        model_params=model_params_str,
        device=device,
        n_positions=args.samples,
        matrix_structure=matrix_report,
        training=training_report,
        lambda_results=lambda_results,
        varna_usage=varna_usage,
        verdict=verdict,
        failure_modes=failures,
    )

    print("\n")
    print(format_report(report))

    # Save JSON
    if args.output:
        output_path = Path(args.output)
        output_data = asdict(report)
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2, default=str)
        print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
