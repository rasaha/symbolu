"""
Part 1 — Precision Data Collection
====================================

Load a controlled pretrained transformer (127M–162M parameters), freeze all
weights, run WikiText-103 through the model, and collect hidden states at
every layer for every token.

Stored per token:
    - Hidden state h_t^L ∈ R^d  (one per layer L)
    - Token position within the sequence
    - Sentence boundary flags
    - Raw token string (for downstream structural annotation)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class DataCollectionConfig:
    """Controls data collection from a pretrained transformer."""

    model_name: str = "gpt2"
    """HuggingFace model identifier.  Must be in the 127M–162M param range."""

    max_sequences: int = 2000
    """Maximum number of sequences to process from the corpus."""

    max_seq_len: int = 512
    """Maximum token length per sequence (truncated/padded)."""

    batch_size: int = 8
    """Batch size for forward passes."""

    dataset_name: str = "wikitext"
    dataset_config: str = "wikitext-103-raw-v1"
    dataset_split: str = "train"

    device: str = "cpu"
    """Device for inference ('cpu' or 'cuda')."""

    seed: int = 42


# ---------------------------------------------------------------------------
# Hidden-state store
# ---------------------------------------------------------------------------

@dataclass
class HiddenStateStore:
    """Container for collected hidden states + metadata.

    Attributes:
        states:  dict mapping layer index → np.ndarray of shape [N, d]
        positions: np.ndarray [N] – token position within its sequence
        sentence_ids: np.ndarray [N] – sentence index within the corpus
        sequence_ids: np.ndarray [N] – which sequence each token belongs to
        tokens: list[str] – decoded token strings
        d_model: int – hidden dimension
        n_layers: int – number of transformer layers
        attention_entropy: dict mapping layer index → np.ndarray [N, n_heads]
            Per-token, per-head attention entropy (in nats).
        n_heads: int – number of attention heads (0 if not collected)
    """

    states: Dict[int, np.ndarray] = field(default_factory=dict)
    positions: Optional[np.ndarray] = None
    tokens: List[str] = field(default_factory=list)
    sentence_ids: Optional[np.ndarray] = None
    sequence_ids: Optional[np.ndarray] = None
    d_model: int = 0
    n_layers: int = 0
    attention_entropy: Dict[int, np.ndarray] = field(default_factory=dict)
    n_heads: int = 0


# ---------------------------------------------------------------------------
# Hook-based hidden-state collector
# ---------------------------------------------------------------------------

class _LayerHookCollector:
    """Attaches forward hooks to every transformer layer to capture outputs.

    When ``collect_attention=True`` and the model is invoked with
    ``output_attentions=True``, each block returns attention weights as part
    of its output tuple.  Rather than storing the full [B, H, T, T] matrices
    (which would be enormous), we compute per-token, per-head entropy on the
    fly and store only the [B, T, H] scalar results.
    """

    def __init__(self, collect_attention: bool = False):
        self.layer_outputs: Dict[int, List[torch.Tensor]] = {}
        self.layer_attn_entropy: Dict[int, List[torch.Tensor]] = {}
        self._handles: list = []
        self._collect_attention = collect_attention

    def attach(self, model: nn.Module) -> None:
        """Find transformer blocks and register hooks."""
        blocks = _find_transformer_blocks(model)
        for idx, block in enumerate(blocks):
            self.layer_outputs[idx] = []
            if self._collect_attention:
                self.layer_attn_entropy[idx] = []
            handle = block.register_forward_hook(self._make_hook(idx))
            self._handles.append(handle)
        logger.info("Attached hooks to %d transformer blocks", len(blocks))

    def _make_hook(self, layer_idx: int):
        def hook_fn(module, inp, out):
            # out may be a tuple (hidden_states, ...) or just a tensor
            if isinstance(out, tuple):
                h = out[0]
            else:
                h = out
            self.layer_outputs[layer_idx].append(h.detach().cpu())

            # Collect attention entropy if available.
            # GPT-2 block output: (hidden_states, attn_weights) when
            # output_attentions=True.  Other architectures may place
            # attn_weights at index 2 (after KV cache).  We search for
            # the first 4-D tensor with matching [B, H, T, T] shape.
            if self._collect_attention and isinstance(out, tuple) and len(out) >= 2:
                attn_weights = _find_attn_weights(out)
                if attn_weights is not None:
                    entropy = _attention_entropy(attn_weights)  # [B, T, n_heads]
                    self.layer_attn_entropy[layer_idx].append(entropy.cpu())
        return hook_fn

    def detach(self) -> None:
        for h in self._handles:
            h.remove()
        self._handles.clear()

    def reset(self) -> None:
        for k in self.layer_outputs:
            self.layer_outputs[k] = []
        for k in self.layer_attn_entropy:
            self.layer_attn_entropy[k] = []


def _find_attn_weights(out: tuple) -> Optional[torch.Tensor]:
    """Extract attention weight tensor from a block's output tuple.

    Different architectures place attention weights at different indices.
    We look for the first 4-D tensor whose last two dims are equal (T, T),
    which is the hallmark of an attention matrix.
    """
    for item in out[1:]:  # skip index 0 (hidden states)
        if isinstance(item, torch.Tensor) and item.ndim == 4:
            # [B, n_heads, T_q, T_k] — T_q == T_k for self-attention
            if item.shape[-1] == item.shape[-2]:
                return item
    return None


def _attention_entropy(attn_weights: torch.Tensor) -> torch.Tensor:
    """Compute per-token, per-head Shannon entropy from attention weights.

    Args:
        attn_weights: [B, n_heads, T_q, T_k] attention probability matrix
            (already softmaxed, rows sum to 1).

    Returns:
        Tensor of shape [B, T_q, n_heads] containing entropy in nats for
        each query position and each head.
    """
    # Clamp to avoid log(0)
    p = attn_weights.clamp(min=1e-12)
    # H = -sum(p * log(p)) along the key dimension
    ent = -(p * p.log()).sum(dim=-1)  # [B, n_heads, T_q]
    return ent.permute(0, 2, 1)  # [B, T_q, n_heads]


def _find_transformer_blocks(model: nn.Module) -> list:
    """Locate the sequential transformer blocks inside the model."""
    # GPT-2 style: model.transformer.h
    for attr in ("transformer", "model"):
        parent = getattr(model, attr, None)
        if parent is not None:
            for block_attr in ("h", "layers", "blocks"):
                blocks = getattr(parent, block_attr, None)
                if blocks is not None and isinstance(blocks, nn.ModuleList):
                    return list(blocks)
    # Fallback: search named modules for a ModuleList of identical blocks
    for name, module in model.named_modules():
        if isinstance(module, nn.ModuleList) and len(module) > 2:
            return list(module)
    raise RuntimeError(
        "Could not locate transformer blocks. "
        "Ensure the model follows GPT-2 / LLaMA / OPT conventions."
    )


# ---------------------------------------------------------------------------
# Count parameters
# ---------------------------------------------------------------------------

def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


# ---------------------------------------------------------------------------
# Main collection routine
# ---------------------------------------------------------------------------

def collect_hidden_states(cfg: DataCollectionConfig) -> HiddenStateStore:
    """Run the full data-collection pipeline.

    1. Load model + tokenizer from HuggingFace.
    2. Validate parameter count is 127M–162M.
    3. Freeze all weights.
    4. Stream WikiText-103 through the model.
    5. Return a :class:`HiddenStateStore` with per-layer hidden states.
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer

    logger.info("Loading model: %s", cfg.model_name)
    tokenizer = AutoTokenizer.from_pretrained(cfg.model_name)
    # Use "eager" attention so that output_attentions=True returns actual
    # weight matrices.  The default SDPA backend uses fused kernels that
    # never materialise the attention matrix, returning None instead.
    model = AutoModelForCausalLM.from_pretrained(
        cfg.model_name, attn_implementation="eager",
    )

    n_params = count_parameters(model)
    logger.info("Model has %s parameters (%.1fM)", f"{n_params:,}", n_params / 1e6)
    if not (100_000_000 <= n_params <= 200_000_000):
        logger.warning(
            "Parameter count %dM is outside the recommended 127M–162M range. "
            "Proceeding anyway, but results may differ from spec.",
            n_params // 1_000_000,
        )

    # Freeze all weights
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)

    device = torch.device(cfg.device)
    model.to(device)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Prepare corpus
    sequences = _load_corpus(cfg, tokenizer)
    logger.info("Collected %d tokenized sequences", len(sequences))

    # Hook collector — also collect attention entropy for Part 7 gating analysis
    collector = _LayerHookCollector(collect_attention=True)
    collector.attach(model)

    all_positions: List[np.ndarray] = []
    all_tokens: List[str] = []
    all_seq_ids: List[np.ndarray] = []
    n_layers = len(collector.layer_outputs)
    layer_accum: Dict[int, List[np.ndarray]] = {i: [] for i in range(n_layers)}
    attn_ent_accum: Dict[int, List[np.ndarray]] = {i: [] for i in range(n_layers)}

    seq_offset = 0

    for batch_start in range(0, len(sequences), cfg.batch_size):
        batch_ids = sequences[batch_start : batch_start + cfg.batch_size]

        # Pad to same length within batch
        max_len = min(max(len(s) for s in batch_ids), cfg.max_seq_len)
        padded = []
        attn_masks = []
        for s in batch_ids:
            s = s[:max_len]
            pad_len = max_len - len(s)
            padded.append(s + [tokenizer.pad_token_id] * pad_len)
            attn_masks.append([1] * len(s) + [0] * pad_len)

        input_ids = torch.tensor(padded, dtype=torch.long, device=device)
        attention_mask = torch.tensor(attn_masks, dtype=torch.long, device=device)

        collector.reset()

        with torch.no_grad():
            # output_attentions=True makes each block return attn weights
            # in its output tuple, which our hook captures for entropy
            model(input_ids=input_ids, attention_mask=attention_mask,
                  output_attentions=True)

        # Gather per-token hidden states (skip padding)
        for b_idx in range(input_ids.shape[0]):
            real_len = attention_mask[b_idx].sum().item()
            token_ids = input_ids[b_idx, :real_len].cpu().tolist()

            positions = np.arange(real_len, dtype=np.int32)
            all_positions.append(positions)
            all_seq_ids.append(
                np.full(real_len, seq_offset + b_idx, dtype=np.int32)
            )

            decoded = [tokenizer.decode([tid]) for tid in token_ids]
            all_tokens.extend(decoded)

            for layer_idx in range(n_layers):
                h = collector.layer_outputs[layer_idx][-1]  # last batch tensor
                # h shape: [B, T, D]  – extract this sample, real tokens only
                layer_accum[layer_idx].append(
                    h[b_idx, :real_len, :].numpy()
                )
                # Attention entropy: [B, T, n_heads]
                if layer_idx in collector.layer_attn_entropy and collector.layer_attn_entropy[layer_idx]:
                    ae = collector.layer_attn_entropy[layer_idx][-1]
                    attn_ent_accum[layer_idx].append(
                        ae[b_idx, :real_len, :].numpy()
                    )

        seq_offset += len(batch_ids)
        # Report progress every batch so the user sees forward-pass activity
        elapsed_batches = seq_offset // cfg.batch_size
        total_batches = (len(sequences) + cfg.batch_size - 1) // cfg.batch_size
        logger.info(
            "Forward pass: batch %d/%d (%d/%d sequences)",
            elapsed_batches, total_batches, seq_offset, len(sequences),
        )

    collector.detach()

    # Concatenate
    store = HiddenStateStore()
    store.positions = np.concatenate(all_positions)
    store.sequence_ids = np.concatenate(all_seq_ids)
    store.tokens = all_tokens
    store.n_layers = n_layers

    for layer_idx in range(n_layers):
        arr = np.concatenate(layer_accum[layer_idx], axis=0)
        store.states[layer_idx] = arr
        if store.d_model == 0:
            store.d_model = arr.shape[1]

    # Concatenate attention entropy if collected
    for layer_idx in range(n_layers):
        if attn_ent_accum[layer_idx]:
            ae_arr = np.concatenate(attn_ent_accum[layer_idx], axis=0)
            store.attention_entropy[layer_idx] = ae_arr  # [N, n_heads]
            if store.n_heads == 0:
                store.n_heads = ae_arr.shape[1]

    if store.attention_entropy:
        logger.info(
            "Attention entropy collected: %d layers, %d heads/layer",
            len(store.attention_entropy),
            store.n_heads,
        )
    else:
        logger.warning(
            "Attention entropy not collected (model may not expose "
            "attention weights via output_attentions=True)"
        )

    logger.info(
        "Collection complete: %d tokens, %d layers, d=%d",
        len(store.tokens),
        store.n_layers,
        store.d_model,
    )
    return store


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------

def _load_corpus(
    cfg: DataCollectionConfig,
    tokenizer,
) -> List[List[int]]:
    """Load and tokenize WikiText-103 sequences."""
    try:
        from datasets import load_dataset

        ds = load_dataset(
            cfg.dataset_name,
            cfg.dataset_config,
            split=cfg.dataset_split,
            trust_remote_code=True,
        )
    except Exception as e:
        logger.warning("Could not load %s from HuggingFace: %s", cfg.dataset_name, e)
        logger.info("Falling back to synthetic corpus for testing")
        return _synthetic_corpus(cfg, tokenizer)

    sequences: List[List[int]] = []
    for row in ds:
        text = row.get("text", "")
        if len(text.strip()) < 20:
            continue
        ids = tokenizer.encode(text, add_special_tokens=False)
        if len(ids) < 10:
            continue
        # Chunk long texts into max_seq_len segments
        for start in range(0, len(ids), cfg.max_seq_len):
            chunk = ids[start : start + cfg.max_seq_len]
            if len(chunk) >= 10:
                sequences.append(chunk)
        if len(sequences) >= cfg.max_sequences:
            break

    return sequences[: cfg.max_sequences]


def _synthetic_corpus(
    cfg: DataCollectionConfig,
    tokenizer,
) -> List[List[int]]:
    """Generate a synthetic corpus when real data is unavailable."""
    import random

    random.seed(cfg.seed)
    templates = [
        "The {noun} {verb} the {noun2} in the {place}.",
        "After the {noun} arrived, the {noun2} {verb} quickly.",
        "Although {noun} was {adj}, the {noun2} remained calm.",
        "The {adj} {noun} that {verb} the {noun2} was remarkable.",
        "{noun} and {noun2} both {verb} near the {place}.",
    ]
    nouns = ["cat", "dog", "professor", "student", "bird", "scientist",
             "child", "river", "mountain", "theory"]
    verbs = ["observed", "chased", "studied", "found", "examined",
             "crossed", "described", "measured", "noticed", "followed"]
    adjs = ["large", "small", "curious", "ancient", "mysterious",
            "complex", "simple", "elegant", "bright", "dark"]
    places = ["garden", "laboratory", "forest", "library", "valley",
              "city", "ocean", "classroom", "museum", "desert"]

    sequences = []
    for _ in range(cfg.max_sequences):
        sents = []
        for _ in range(random.randint(3, 8)):
            tmpl = random.choice(templates)
            text = tmpl.format(
                noun=random.choice(nouns),
                noun2=random.choice(nouns),
                verb=random.choice(verbs),
                adj=random.choice(adjs),
                place=random.choice(places),
            )
            sents.append(text)
        full = " ".join(sents)
        ids = tokenizer.encode(full, add_special_tokens=False)
        sequences.append(ids[: cfg.max_seq_len])

    return sequences
