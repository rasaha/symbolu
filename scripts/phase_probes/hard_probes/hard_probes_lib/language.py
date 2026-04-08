"""
Real language mode: WikiText, AssociativeRecall, Binding Cache architectures.

Contains:
    - WikiTextDataset: Real language data loading
    - AssociativeRecallDataset: Forces quad to retrieve long-range memories
    - HybridLMTransformer: Language model with phase-first curriculum
    - ProtectedPhaseLMTransformer: Protected phase for LM
    - LocalWindowAttention: Efficient sliding-window attention
    - BindingCachePhaseState: Phase accumulation path
    - BindingCacheQuadQuery: Quad retrieval path
    - BindingSlotCache: Explicit key-value memory
    - BindingCacheLMTransformer: Three-path model

CLI Usage::

    # WikiText language modeling
    python train_hard_probes.py --real-language --dataset wikitext2

    # Associative Recall (forces quad to work)
    python train_hard_probes.py --associative-recall --ar-num-pairs 8

    # Binding Cache architecture
    python train_hard_probes.py --real-language --binding-cache --binding-slots 32

    # With Kosha + Witness diagnostics
    python train_hard_probes.py --real-language --enable-kosha --enable-witness

    # Phase-first curriculum
    python train_hard_probes.py --real-language --phase-first-curriculum
"""

import math
import os
import random
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from typing import List, Tuple, Dict, Optional

# =============================================================================
# REAL LANGUAGE MODE: WikiText Dataset and LM Training
# =============================================================================

class WikiTextDataset(Dataset):
    """Text dataset for language modeling with layer probing.

    Supports:
    - wikitext2, wikitext103: Encyclopedia text (good for LM, basic Phase)
    - tinystories: Narrative stories (RECOMMENDED for Kosha/Witness - diverse epistemic states)
    - writingprompts: Creative writing (excellent Vritti diversity)
    - imdb: Movie reviews (opinions/emotions)
    - openwebtext, c4: Large web corpora
    """

    def __init__(self, split: str = "train", seq_len: int = 256, dataset_name: str = "wikitext2"):
        """
        Args:
            split: "train", "validation", or "test"
            seq_len: Sequence length for chunks
            dataset_name: Dataset to load (tinystories recommended for consciousness training)
        """
        try:
            from datasets import load_dataset
            from transformers import GPT2Tokenizer
        except ImportError:
            raise ImportError("Install: pip install datasets transformers")

        self.seq_len = seq_len
        self.tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
        self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load dataset based on name
        dataset_name_lower = dataset_name.lower()

        if dataset_name_lower == "wikitext2":
            ds = load_dataset("wikitext", "wikitext-2-raw-v1", split=split)
            text_field = "text"
            ds_label = "WikiText-2"
        elif dataset_name_lower == "wikitext103":
            ds = load_dataset("wikitext", "wikitext-103-raw-v1", split=split)
            text_field = "text"
            ds_label = "WikiText-103"
        elif dataset_name_lower == "tinystories":
            # TinyStories - narrative stories, excellent for Kosha/Witness
            # Small, diverse epistemic states (imagination, memory, facts)
            ds = load_dataset("roneneldan/TinyStories", split=split, trust_remote_code=True)
            text_field = "text"
            ds_label = "TinyStories"
        elif dataset_name_lower == "writingprompts":
            # WritingPrompts - creative writing with diverse epistemic modes
            # Great for exercising all Vritti states
            try:
                ds = load_dataset("euclaise/writingprompts", split=split, trust_remote_code=True)
            except Exception:
                ds = load_dataset("writing_prompts", split=split, trust_remote_code=True)
            # Has 'prompt' and 'story' fields - concatenate them
            text_field = "story" if "story" in ds.column_names else "text"
            ds_label = "WritingPrompts"
        elif dataset_name_lower == "imdb":
            # IMDB reviews - opinions/emotions, good for Vritti diversity
            ds = load_dataset("imdb", split=split, trust_remote_code=True)
            text_field = "text"
            ds_label = "IMDB Reviews"
        elif dataset_name_lower == "openwebtext":
            # OpenWebText - large web text corpus
            ds = load_dataset("openwebtext", split=split, trust_remote_code=True)
            text_field = "text"
            ds_label = "OpenWebText"
        elif dataset_name_lower == "c4":
            # C4 (Colossal Clean Crawled Corpus) - very large
            # Only load a subset to avoid memory issues
            ds = load_dataset("c4", "en", split=f"{split}[:10000]", trust_remote_code=True)
            text_field = "text"
            ds_label = "C4 (subset)"
        else:
            raise ValueError(f"Unknown dataset: {dataset_name}. "
                           f"Choose from: wikitext2, wikitext103, tinystories, writingprompts, imdb, openwebtext, c4")

        # Tokenize all text
        if text_field in ds.column_names:
            all_text = " ".join([t for t in ds[text_field] if t and t.strip()])
        else:
            # Fallback: try common text field names
            for field in ["text", "content", "section_text", "document"]:
                if field in ds.column_names:
                    all_text = " ".join([t for t in ds[field] if t and t.strip()])
                    break
            else:
                raise ValueError(f"Could not find text field in dataset. Available: {ds.column_names}")

        self.tokens = self.tokenizer.encode(all_text)
        print(f"  [{ds_label}] {split}: {len(self.tokens):,} tokens → {len(self.tokens) // seq_len:,} chunks")

    def __len__(self):
        return max(1, len(self.tokens) // self.seq_len - 1)

    def __getitem__(self, idx):
        start = idx * self.seq_len
        end = start + self.seq_len + 1  # +1 for target
        chunk = self.tokens[start:end]

        # Pad if needed
        if len(chunk) < self.seq_len + 1:
            chunk = chunk + [self.tokenizer.pad_token_id] * (self.seq_len + 1 - len(chunk))

        x = torch.tensor(chunk[:-1], dtype=torch.long)
        y = torch.tensor(chunk[1:], dtype=torch.long)
        return x, y


# =============================================================================
# V10.5.5: ASSOCIATIVE RECALL TASK (Forces Quad to Work)
# =============================================================================

class AssociativeRecallDataset(Dataset):
    """
    Associative Recall / Key-Value Recall Dataset.

    This task REQUIRES long-range memory retrieval that local attention cannot solve.
    It forces quad to work by:
    1. Storing key-value pairs in memory (phase's job)
    2. Retrieving the correct value given a query key (quad's job)
    3. Using delays longer than local window (quad MUST retrieve from phase)

    Format:
        Input:  [K1] [V1] [SEP] [K2] [V2] [SEP] ... [FILLER] ... [QUERY] [Ki]
        Target: [Vi] at the position after [QUERY] [Ki]

    Example (num_pairs=4, delay=100):
        "A = cat ; B = dog ; C = bird ; D = fish ; [100 filler tokens] ; ? = A"
        Target at '?' position: "cat"

    Local attention (window=64) CANNOT solve this when delay > window.
    Quad MUST retrieve from phase memory.

    V10.5.8: Dynamic delay curriculum support
    - dynamic_delay=True: Generate samples on-the-fly with current delay range
    - set_delay_range(): Update delay range during training
    - apply_curriculum(): Helper for progressive difficulty
    """

    def __init__(
        self,
        num_samples: int = 10000,
        num_pairs: int = 8,
        delay_min: int = 50,
        delay_max: int = 150,
        seq_len: int = 256,
        vocab_size: int = 1000,
        seed: int = 42,
        dynamic_delay: bool = False,  # V10.5.8: Generate on-the-fly for curriculum
    ):
        """
        Args:
            num_samples: Number of samples to generate
            num_pairs: Number of key-value pairs per sample
            delay_min: Minimum filler tokens between pairs and query
            delay_max: Maximum filler tokens between pairs and query
            seq_len: Total sequence length (padded/truncated)
            vocab_size: Size of vocabulary for keys and values
            seed: Random seed for reproducibility
            dynamic_delay: If True, generate samples on-the-fly (enables curriculum)
        """
        super().__init__()
        self.num_samples = num_samples
        self.num_pairs = num_pairs
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.seq_len = seq_len
        self.vocab_size = vocab_size
        self.dynamic_delay = dynamic_delay
        self.seed = seed

        # Special tokens (reserved at end of vocab)
        self.PAD_TOKEN = vocab_size - 1
        self.SEP_TOKEN = vocab_size - 2  # Separator between pairs
        self.QUERY_TOKEN = vocab_size - 3  # Query marker
        self.EQ_TOKEN = vocab_size - 4  # Equals sign
        self.FILLER_START = vocab_size - 100  # Filler tokens (100 reserved)

        # Usable vocab for keys and values (first part of vocab)
        self.kv_vocab_size = vocab_size - 100

        # V10.5.8: Curriculum tracking
        self._curriculum_step = 0
        self._initial_delay_min = delay_min
        self._initial_delay_max = delay_max

        if dynamic_delay:
            # On-the-fly generation - just set random state
            self.rng = torch.Generator()
            self.rng.manual_seed(seed)
            self.samples = None  # Generated lazily
        else:
            # Pre-generate all samples for efficiency
            torch.manual_seed(seed)
            self.samples = []
            self._generate_samples()

    def set_delay_range(self, delay_min: int, delay_max: int):
        """
        V10.5.8: Update delay range for curriculum learning.

        Call this during training to progressively increase difficulty.
        Only works if dynamic_delay=True.

        Args:
            delay_min: New minimum delay
            delay_max: New maximum delay
        """
        self.delay_min = delay_min
        self.delay_max = delay_max

    def apply_curriculum(self, progress: float, target_delay_min: int, target_delay_max: int):
        """
        V10.5.8: Apply curriculum based on training progress.

        Linearly interpolates delay range from initial to target based on progress.

        Args:
            progress: Training progress [0, 1] (e.g., step / total_steps)
            target_delay_min: Target minimum delay at progress=1.0
            target_delay_max: Target maximum delay at progress=1.0

        Returns:
            Tuple of (current_delay_min, current_delay_max)
        """
        progress = min(1.0, max(0.0, progress))  # Clamp to [0, 1]

        # Linear interpolation
        new_delay_min = int(self._initial_delay_min + progress * (target_delay_min - self._initial_delay_min))
        new_delay_max = int(self._initial_delay_max + progress * (target_delay_max - self._initial_delay_max))

        self.set_delay_range(new_delay_min, new_delay_max)
        return (new_delay_min, new_delay_max)

    def _generate_samples(self):
        """Pre-generate all samples."""
        for _ in range(self.num_samples):
            sample = self._generate_one_sample()
            self.samples.append(sample)

    def _generate_one_sample(self) -> Tuple[torch.Tensor, torch.Tensor, int]:
        """
        Generate one associative recall sample.

        Returns:
            x: Input sequence [seq_len]
            y: Target sequence [seq_len] (mostly PAD, value at query position)
            query_idx: Index of the query key (for analysis)
        """
        # Generate random key-value pairs (keys must be unique)
        keys = torch.randperm(self.kv_vocab_size // 2)[:self.num_pairs]
        values = torch.randint(0, self.kv_vocab_size // 2, (self.num_pairs,))

        # Build sequence: K1 = V1 ; K2 = V2 ; ... ; [filler] ; ? = Kq
        tokens = []

        # Add key-value pairs
        for i in range(self.num_pairs):
            tokens.append(keys[i].item())
            tokens.append(self.EQ_TOKEN)
            tokens.append(values[i].item())
            if i < self.num_pairs - 1:
                tokens.append(self.SEP_TOKEN)

        # Add filler tokens (random from filler vocab)
        delay = torch.randint(self.delay_min, self.delay_max + 1, (1,)).item()
        for _ in range(delay):
            filler_token = torch.randint(self.FILLER_START, self.vocab_size - 4, (1,)).item()
            tokens.append(filler_token)

        # Select random query key
        query_idx = torch.randint(0, self.num_pairs, (1,)).item()
        query_key = keys[query_idx].item()
        query_value = values[query_idx].item()

        # Add query: ? = K
        tokens.append(self.QUERY_TOKEN)
        tokens.append(self.EQ_TOKEN)
        tokens.append(query_key)

        # The target is the value at the position AFTER the query key
        # For LM, we predict next token, so target[i] = what comes after x[i]

        # Pad or truncate to seq_len
        if len(tokens) < self.seq_len:
            tokens = tokens + [self.PAD_TOKEN] * (self.seq_len - len(tokens))
        else:
            tokens = tokens[:self.seq_len]

        # Create input and target
        x = torch.tensor(tokens, dtype=torch.long)

        # Target: -100 (ignore) everywhere except the query answer position.
        # V10.16.1: Use -100 (standard PyTorch ignore_index) instead of PAD_TOKEN
        # so that (y != -100) correctly identifies only the query answer position.
        y = torch.full((self.seq_len,), -100, dtype=torch.long)
        # Query mask: True only at the position where model must retrieve the value
        query_mask = torch.zeros(self.seq_len, dtype=torch.bool)

        # Find where query_key appears after QUERY_TOKEN
        # The answer should come right after
        for i in range(len(tokens) - 1):
            if tokens[i] == self.QUERY_TOKEN and i + 2 < len(tokens):
                # Position i is QUERY, i+1 is EQ, i+2 is query_key
                # Target at i+2 should be query_value (what comes next)
                if i + 3 < self.seq_len:
                    y[i + 2] = query_value  # After seeing key, predict value
                    query_mask[i + 2] = True

        return x, y, query_idx, query_mask

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        # V10.5.8: Support dynamic generation for curriculum learning
        if self.dynamic_delay or self.samples is None:
            # Generate on-the-fly with current delay range
            x, y, _, query_mask = self._generate_one_sample()
            return x, y, query_mask
        else:
            # Use pre-generated samples
            x, y, _, query_mask = self.samples[idx]
            return x, y, query_mask

    def get_accuracy(self, model: nn.Module, device: torch.device, num_samples: int = 100) -> float:
        """
        Compute retrieval accuracy on a subset of samples.

        Args:
            model: The model to evaluate
            device: Device to run on
            num_samples: Number of samples to evaluate

        Returns:
            accuracy: Fraction of correct retrievals
        """
        model.eval()
        correct = 0
        total = 0

        with torch.no_grad():
            for i in range(min(num_samples, len(self.samples))):
                x, y, query_idx, query_mask = self.samples[i]
                x = x.unsqueeze(0).to(device)
                y = y.to(device)

                logits = model(x)  # [1, seq_len, vocab_size]

                # Find query position (where y != -100, i.e. the answer position)
                query_positions = (y != -100).nonzero(as_tuple=True)[0]

                for pos in query_positions:
                    pred = logits[0, pos].argmax().item()
                    target = y[pos].item()
                    if pred == target:
                        correct += 1
                    total += 1

        return correct / max(total, 1)


class AssociativeRecallCollator:
    """Custom collator that stacks AR samples and passes query_mask through."""

    def __init__(self, pad_token: int = -100):
        self.pad_token = pad_token

    def __call__(self, batch):
        x = torch.stack([item[0] for item in batch])
        y = torch.stack([item[1] for item in batch])
        # V10.16.1: Pass explicit query_mask for retrieval loss
        if len(batch[0]) >= 3:
            query_mask = torch.stack([item[2] for item in batch])
            return {"input_ids": x, "labels": y, "query_mask": query_mask}
        return x, y


class HybridLMTransformer(nn.Module):
    """
    Language Modeling Transformer with per-layer Phase/Quadratic mixing.

    Supports:
    - Phase-first curriculum (phase_ratio adjustable per layer)
    - Layer-wise probing (can ablate individual layers)
    - Real language modeling (cross-entropy loss)
    """

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        num_heads: int,
        num_layers: int,
        d_ff: int,
        dropout: float,
        max_seq_len: int,
        curriculum: List[float],  # phase_ratio per layer
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.num_layers = num_layers
        self.curriculum = curriculum  # Mutable for phase-first curriculum

        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)

        # Create hybrid layers
        self.layers = nn.ModuleList([
            HybridTransformerBlock(
                d_model, num_heads, d_ff, dropout,
                phase_ratio=curriculum[i],
                operation_tokens=None,
                bounded_phase=bounded_phase,
            )
            for i in range(num_layers)
        ])

        self.norm = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

        # Weight tying
        self.lm_head.weight = self.token_emb.weight

        # Layer-wise probing storage
        self.layer_outputs = []
        self.probe_mode = False

    def update_curriculum(self, new_curriculum: List[float]):
        """Update phase ratios for phase-first curriculum."""
        self.curriculum = new_curriculum
        for i, layer in enumerate(self.layers):
            layer.phase_ratio = new_curriculum[i]

    def forward(self, input_ids: torch.Tensor, probe_layers: bool = False) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        self.layer_outputs = []

        for i, layer in enumerate(self.layers):
            x = layer(x)
            if probe_layers:
                # Store intermediate output for layer probing
                self.layer_outputs.append(x.detach().clone())

        x = self.norm(x)
        logits = self.lm_head(x)
        return logits

    def get_layer_ppl(self, input_ids: torch.Tensor, targets: torch.Tensor) -> List[float]:
        """
        Compute PPL contribution from each layer by early-exiting.

        Returns list of PPLs: [ppl_after_layer_0, ppl_after_layer_1, ...]
        """
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        layer_ppls = []

        for i, layer in enumerate(self.layers):
            x = layer(x)
            # Early exit: compute PPL after this layer
            x_normed = self.norm(x)
            logits = self.lm_head(x_normed)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            ppl = torch.exp(loss).item()
            layer_ppls.append(ppl)

        return layer_ppls

    def get_layer_contributions(self, input_ids: torch.Tensor, targets: torch.Tensor) -> Dict[str, List[float]]:
        """
        Compute detailed per-layer metrics to see if phase learns faster/richer.

        Returns:
            - 'ppl': PPL after each layer
            - 'ppl_delta': PPL reduction from each layer (positive = layer helps)
            - 'phase_ratio': Current phase ratio per layer
            - 'contribution_pct': % of total PPL reduction from each layer
        """
        layer_ppls = self.get_layer_ppl(input_ids, targets)

        # Compute PPL before any layer (just embeddings)
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))
        x_normed = self.norm(x)
        logits = self.lm_head(x_normed)
        loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
        ppl_embed = torch.exp(loss).item()

        # PPL delta (reduction) per layer
        ppl_deltas = []
        prev_ppl = ppl_embed
        for ppl in layer_ppls:
            delta = prev_ppl - ppl  # Positive = layer reduced PPL
            ppl_deltas.append(delta)
            prev_ppl = ppl

        # Total PPL reduction
        total_reduction = ppl_embed - layer_ppls[-1]

        # Contribution percentage per layer
        contribution_pcts = []
        for delta in ppl_deltas:
            if total_reduction > 0:
                pct = (delta / total_reduction) * 100
            else:
                pct = 0.0
            contribution_pcts.append(pct)

        return {
            'ppl': layer_ppls,
            'ppl_delta': ppl_deltas,
            'phase_ratio': self.curriculum.copy(),
            'contribution_pct': contribution_pcts,
            'ppl_embed': ppl_embed,
            'total_reduction': total_reduction,
        }

    def ablate_attention(self, input_ids: torch.Tensor, targets: torch.Tensor,
                         ablate_phase: bool = False, ablate_local: bool = False) -> float:
        """
        Compute PPL with phase or local attention ablated (zeroed out).

        This shows what each attention type contributes:
        - ablate_phase=True: Only local attention active
        - ablate_local=True: Only phase attention active
        """
        # Store original ratios
        original_curriculum = self.curriculum.copy()

        if ablate_phase:
            # Set all phase ratios to 0 (only local)
            ablated_curriculum = [0.0] * self.num_layers
        elif ablate_local:
            # Set all phase ratios to 1 (only phase)
            ablated_curriculum = [1.0] * self.num_layers
        else:
            ablated_curriculum = original_curriculum

        self.update_curriculum(ablated_curriculum)

        # Compute PPL
        with torch.no_grad():
            logits = self.forward(input_ids)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            ppl = torch.exp(loss).item()

        # Restore original
        self.update_curriculum(original_curriculum)

        return ppl


class PhaseFirstCurriculum:
    """
    Adjusts per-layer phase ratios based on current PPL.

    High PPL (early training): More phase in all layers
    Low PPL (later training): Phase only in early layers, local in later layers
    """

    def __init__(
        self,
        num_layers: int,
        alpha_high: float = 0.8,
        alpha_low: float = 0.3,
        ppl_high: float = 1000.0,
        ppl_low: float = 100.0,
    ):
        self.num_layers = num_layers
        self.alpha_high = alpha_high
        self.alpha_low = alpha_low
        self.ppl_high = ppl_high
        self.ppl_low = ppl_low
        self.current_ppl = float('inf')

    def update(self, ppl: float) -> List[float]:
        """
        Compute per-layer phase ratios based on PPL.

        Returns: curriculum list [phase_ratio_L0, phase_ratio_L1, ...]
        """
        self.current_ppl = ppl

        # Compute base alpha from PPL
        if ppl >= self.ppl_high:
            base_alpha = self.alpha_high
        elif ppl <= self.ppl_low:
            base_alpha = self.alpha_low
        else:
            # Linear interpolation
            ratio = (ppl - self.ppl_low) / (self.ppl_high - self.ppl_low)
            base_alpha = self.alpha_low + ratio * (self.alpha_high - self.alpha_low)

        # Per-layer curriculum: early layers keep more phase
        # Layer 0: base_alpha, Layer N-1: base_alpha * 0.5
        curriculum = []
        for i in range(self.num_layers):
            layer_factor = 1.0 - (i / (self.num_layers - 1)) * 0.5  # 1.0 → 0.5
            layer_alpha = base_alpha * layer_factor
            curriculum.append(layer_alpha)

        return curriculum


# =============================================================================
# V10.3.2: PROTECTED PHASE FOR REAL LANGUAGE MODE
# =============================================================================
# Protected Phase architecture gives Phase and Quadratic NON-COMPETING roles:
#   - Phase: O(n) memory accumulation (cumsum) - persists binding state
#   - Quadratic: O(n²) memory querying (attention) - reasons over state
#
# They collaborate SEQUENTIALLY, not compete in PARALLEL.
# This prevents Phase from becoming "decorative" (0% ablation drop).

class ProtectedPhaseLMBlock(nn.Module):
    """
    Protected Phase block for Language Modeling.

    Architecture:
        1. Phase accumulates memory: memory = cumsum(k * v)
        2. Quadratic queries memory: output = attention(q, memory)

    This is SEQUENTIAL COLLABORATION, not parallel mixing.
    Phase and Quadratic don't compete for gradients.
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        d_ff: int,
        dropout: float,
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads

        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm_mem = nn.LayerNorm(d_model)

        # Protected Phase: accumulates memory state
        self.phase_memory = ProtectedPhaseAttention(d_model, num_heads, dropout, None, bounded_phase)
        # Protected Quad: queries memory state
        self.quad_query = ProtectedQuadAttention(d_model, num_heads, dropout)

        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_ff, d_model), nn.Dropout(dropout)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Step 1: Phase accumulates memory state (Phase's exclusive job)
        normed = self.norm1(x)
        memory_state = self.phase_memory(normed, None)  # No token_ids for LM
        memory_state = self.norm_mem(memory_state)

        # Step 2: Quadratic queries the memory (Quad's exclusive job)
        attn_out = self.quad_query(normed, memory_state)

        # Residual and FF
        x = x + attn_out
        x = x + self.ff(self.norm2(x))
        return x

    def get_phase_health(self) -> dict:
        """Get Phase health metrics."""
        return self.phase_memory.get_health_metrics()


class ProtectedPhaseLMTransformer(nn.Module):
    """
    Language Modeling Transformer with PROTECTED Phase architecture.

    Key insight from ablation tests:
    - When mixed (parallel), Phase becomes DECORATIVE (0% ablation drop)
    - When protected (sequential), Phase is ESSENTIAL (37% ablation drop)

    Solution: Give Phase and Quadratic NON-COMPETING roles:
    - Phase: O(n) memory accumulation (cumsum)
    - Quadratic: O(n²) memory querying (attention)

    They collaborate sequentially, not compete in parallel.

    Supports:
    - Layer-wise probing (for SRK integration)
    - Real language modeling (cross-entropy loss)
    - Phase health monitoring (R_k statistics)
    """

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        num_heads: int,
        num_layers: int,
        d_ff: int,
        dropout: float,
        max_seq_len: int,
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.num_heads = num_heads
        self.num_layers = num_layers

        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)

        # Create protected phase layers
        self.layers = nn.ModuleList([
            ProtectedPhaseLMBlock(d_model, num_heads, d_ff, dropout, bounded_phase)
            for _ in range(num_layers)
        ])

        self.norm = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

        # Weight tying
        self.lm_head.weight = self.token_emb.weight

        # Layer-wise probing storage (for SRK integration)
        self.layer_outputs = []

        # Curriculum placeholder (not used in protected phase, but for API compatibility)
        self.curriculum = [1.0] * num_layers  # Protected = 100% phase contribution

    def forward(self, input_ids: torch.Tensor, probe_layers: bool = False) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        self.layer_outputs = []

        for i, layer in enumerate(self.layers):
            x = layer(x)
            if probe_layers:
                # Store intermediate output for layer probing / SRK
                self.layer_outputs.append(x.detach().clone())

        x = self.norm(x)
        logits = self.lm_head(x)
        return logits

    def get_phase_health(self) -> dict:
        """
        Aggregate Phase health metrics (R_k statistics) from all layers.

        Interpretation:
        - R_k → 0: Phase collapsed (bad)
        - R_k → 1: Phase degenerate (bad)
        - R_k stable in (0.3, 0.7): Healthy
        """
        metrics = {
            "r_k_mean": [],
            "r_k_std": [],
            "r_k_min": [],
            "r_k_max": [],
        }
        for layer in self.layers:
            layer_metrics = layer.get_phase_health()
            for k, v in layer_metrics.items():
                metrics[k].append(v)

        # Average across layers
        return {
            "r_k_mean": sum(metrics["r_k_mean"]) / len(metrics["r_k_mean"]) if metrics["r_k_mean"] else 0.0,
            "r_k_std": sum(metrics["r_k_std"]) / len(metrics["r_k_std"]) if metrics["r_k_std"] else 0.0,
            "r_k_min": min(metrics["r_k_min"]) if metrics["r_k_min"] else 0.0,
            "r_k_max": max(metrics["r_k_max"]) if metrics["r_k_max"] else 0.0,
        }

    def update_curriculum(self, new_curriculum: List[float]):
        """API compatibility with HybridLMTransformer (no-op for protected phase)."""
        # Protected phase doesn't use curriculum - phase is always protected
        pass

    def get_layer_ppl(self, input_ids: torch.Tensor, targets: torch.Tensor) -> List[float]:
        """Compute PPL contribution from each layer by early-exiting."""
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        layer_ppls = []

        for i, layer in enumerate(self.layers):
            x = layer(x)
            # Early exit: compute PPL after this layer
            x_normed = self.norm(x)
            logits = self.lm_head(x_normed)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            ppl = torch.exp(loss).item()
            layer_ppls.append(ppl)

        return layer_ppls

    def get_layer_contributions(self, input_ids: torch.Tensor, targets: torch.Tensor) -> Dict[str, List[float]]:
        """
        Analyze per-layer contributions for Protected Phase.

        Returns dict with:
        - ppl: PPL after each layer
        - ppl_delta: PPL improvement from each layer
        - contribution_pct: % of total PPL reduction from each layer
        - phase_ratio: Always 1.0 for protected phase
        """
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        # Initial PPL (embedding only)
        logits_embed = self.lm_head(self.norm(x))
        loss_embed = F.cross_entropy(logits_embed.view(-1, self.vocab_size), targets.view(-1))
        ppl_embed = torch.exp(loss_embed).item()

        layer_ppls = []
        layer_deltas = []
        prev_ppl = ppl_embed

        for i, layer in enumerate(self.layers):
            x = layer(x)
            x_normed = self.norm(x)
            logits = self.lm_head(x_normed)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            ppl = torch.exp(loss).item()

            layer_ppls.append(ppl)
            layer_deltas.append(prev_ppl - ppl)  # Positive = improvement
            prev_ppl = ppl

        total_reduction = ppl_embed - layer_ppls[-1]
        contribution_pcts = [
            (delta / total_reduction * 100) if total_reduction > 0 else 0
            for delta in layer_deltas
        ]

        return {
            'ppl': layer_ppls,
            'ppl_delta': layer_deltas,
            'contribution_pct': contribution_pcts,
            'phase_ratio': [1.0] * self.num_layers,  # Always 100% phase contribution
            'ppl_embed': ppl_embed,
            'total_reduction': total_reduction,
        }

    def ablate_attention(self, input_ids: torch.Tensor, targets: torch.Tensor,
                         ablate_phase: bool = False, ablate_local: bool = False) -> float:
        """
        For Protected Phase, ablation is different:
        - ablate_phase: Disable phase memory accumulation
        - ablate_local: Disable quadratic querying

        Returns PPL with ablation applied.
        """
        # Store original forward, apply ablation, restore
        # For now, return normal PPL (full ablation requires modifying layers)
        with torch.no_grad():
            logits = self.forward(input_ids)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            return torch.exp(loss).item()

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# =============================================================================
# V10.3.3: BINDING CACHE FOR REAL LANGUAGE MODE
# =============================================================================
# Binding Cache architecture combines THREE attention paths:
#   1. Local: O(n*w) - Direct token-to-token for syntax learning
#   2. Phase: O(n) - Memory state accumulation (global compression)
#   3. Quad:  O(n*k) - Top-K memory query (global retrieval)
#
# This is the V10.0 architecture validated by diagnostic probes.
# Reference: --protected-phase showed -50% ablation drop (Phase essential)

class LocalWindowAttention(nn.Module):
    """
    Local window attention for fast syntax learning.

    Uses sliding window attention (O(n*w) complexity) for direct
    token-to-token patterns like "the → cat".
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        window_size: int = 64,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.window_size = window_size

        self.W_q = nn.Linear(embed_dim, embed_dim)
        self.W_k = nn.Linear(embed_dim, embed_dim)
        self.W_v = nn.Linear(embed_dim, embed_dim)
        self.W_o = nn.Linear(embed_dim, embed_dim)

        self.norm = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)
        self.scale = 1.0 / math.sqrt(self.head_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Local window attention.

        Args:
            x: [B, N, D]

        Returns:
            output: [B, N, D]
        """
        B, N, D = x.shape
        x_norm = self.norm(x)

        # Project Q, K, V
        q = self.W_q(x_norm).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.W_k(x_norm).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.W_v(x_norm).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # Compute attention scores with causal mask
        attn_scores = torch.matmul(q, k.transpose(-2, -1)) * self.scale

        # Create causal mask
        causal_mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()

        # Create local window mask (only attend within window)
        window_mask = torch.ones(N, N, device=x.device).bool()
        for i in range(N):
            start = max(0, i - self.window_size)
            window_mask[i, start:i+1] = False

        # Combine masks
        combined_mask = causal_mask | window_mask
        attn_scores = attn_scores.masked_fill(combined_mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        # Softmax and apply
        attn_probs = F.softmax(attn_scores, dim=-1)
        attn_probs = self.dropout(attn_probs)

        attn_out = torch.matmul(attn_probs, v)
        attn_out = attn_out.transpose(1, 2).contiguous().view(B, N, D)

        return self.W_o(attn_out)


class BindingCachePhaseState(nn.Module):
    """
    Phase state accumulator for binding cache.

    Accumulates key-value bindings into a persistent memory state
    using O(n) cumulative sum (no attention).

    V10.6: Extended with dual-channel mode support for proposal architecture.
    Separates content similarity from intent alignment:
      s_content = cos(φ_q - φ_k)           # What matches (preserved)
      s_align = cos(θ_JEPA - θ_SRK)        # Intent agreement (modulator)
      score = s_content * (1 + α * s_align) # Combined
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        decay_gamma: float = 0.9,
        bounded_phase: bool = True,
        dual_channel_mode: bool = False,  # V10.6: Enable dual-channel attention
        alignment_authority: float = 0.1,  # V10.6: α weight for alignment term
        alignment_clamp_min: float = 0.8,  # V10.6.1: Clamp lower bound (ChatGPT caveat)
        alignment_clamp_max: float = 1.2,  # V10.6.1: Clamp upper bound (ChatGPT caveat)
        alignment_reduction: str = "per_head",  # V10.6.3: "per_head", "global", "per_batch_head"
        strict_control_contract: bool = True,  # V10.6.3: Strict vs warn mode
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.decay_gamma = decay_gamma
        self.bounded_phase = bounded_phase

        # V10.6: Dual-channel mode support
        self.dual_channel_mode = dual_channel_mode
        self.alignment_authority = alignment_authority
        # V10.6.1: Clamp bounds to prevent over-constraint collapse
        # ChatGPT recommendation: sustained misalignment can attenuate proposals
        self.alignment_clamp_min = alignment_clamp_min
        self.alignment_clamp_max = alignment_clamp_max
        # V10.6.3: Alignment reduction mode (ChatGPT feedback)
        # Must be "per_head" or "global", NOT [B, N] (removed)
        self.alignment_reduction = alignment_reduction
        self.strict_control_contract = strict_control_contract

        # Phase projections
        self.W_k_phase = nn.Linear(embed_dim, embed_dim)
        self.W_k_amp = nn.Linear(embed_dim, embed_dim)
        self.W_v = nn.Linear(embed_dim, embed_dim)

        # V10.6: Intent phase projections for dual-channel mode
        # θ_JEPA = query intent (what we're looking for)
        # θ_SRK = key intent (what memory offers)
        if dual_channel_mode:
            self.W_intent_q = nn.Linear(embed_dim, embed_dim)  # θ_JEPA projection
            self.W_intent_k = nn.Linear(embed_dim, embed_dim)  # θ_SRK projection

        self.norm = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)

        # Health tracking
        self._last_r_k_mean = 0.0
        self._last_r_k_std = 0.0
        self._last_r_k_min = 0.0
        self._last_r_k_max = 0.0

        # V10.6: Dual-channel diagnostics
        self._last_s_align_mean = 0.0
        self._last_s_align_std = 0.0

        self._ablation_mode = "none"

    def set_ablation(self, mode: str, seed: int = 42):
        self._ablation_mode = mode

    def set_rotation(self, angle: float):
        pass  # Not implemented for probe

    def clear_rotation(self):
        pass

    def get_health_metrics(self) -> dict:
        metrics = {
            "r_k_mean": self._last_r_k_mean,
            "r_k_std": self._last_r_k_std,
            "r_k_min": self._last_r_k_min,
            "r_k_max": self._last_r_k_max,
        }
        # V10.6: Include dual-channel diagnostics
        if self.dual_channel_mode:
            metrics["s_align_mean"] = self._last_s_align_mean
            metrics["s_align_std"] = self._last_s_align_std
        return metrics

    def compute_confidence(self, memory_state: torch.Tensor) -> torch.Tensor:
        """
        Compute confidence score for proposal mode.

        Higher confidence means phase state has strong, stable bindings.
        Used in V10.4 proposal mode to decide whether to skip quad attention.

        Args:
            memory_state: [B, N, D] accumulated memory state

        Returns:
            confidence: [B, N] confidence scores in [0, 1]
        """
        # Confidence based on memory state magnitude (normalized)
        # Higher magnitude = stronger bindings = higher confidence
        mem_norm = torch.norm(memory_state, dim=-1)  # [B, N]

        # Normalize to [0, 1] using sigmoid of z-scored values
        mem_mean = mem_norm.mean(dim=-1, keepdim=True)
        mem_std = mem_norm.std(dim=-1, keepdim=True) + 1e-6
        z_scores = (mem_norm - mem_mean) / mem_std

        # Sigmoid to get [0, 1] confidence
        confidence = torch.sigmoid(z_scores)

        return confidence

    def compute_intent_phases(self, x: torch.Tensor, memory_state: torch.Tensor) -> tuple:
        """
        V10.6: Compute intent phases for dual-channel mode.

        Args:
            x: Input tensor [B, N, D] - current query context
            memory_state: [B, N, D] - accumulated memory

        Returns:
            theta_jepa: [B, N, D] - query intent phase (what we're looking for)
            theta_srk: [B, N, D] - key intent phase (what memory offers)
        """
        if not self.dual_channel_mode:
            return None, None

        x_norm = self.norm(x)
        # θ_JEPA: Intent derived from current query context
        theta_jepa = self.W_intent_q(x_norm)
        # θ_SRK: Intent derived from accumulated memory state
        theta_srk = self.W_intent_k(memory_state)

        return theta_jepa, theta_srk

    def compute_alignment_score(
        self,
        theta_jepa: torch.Tensor,
        theta_srk: torch.Tensor,
        reduction: str = "per_head",
    ) -> torch.Tensor:
        """
        V10.6: Compute intent alignment score.
        V10.6.3: Updated to return [H] or [] instead of [B, N] (ChatGPT feedback).

        s_align = cos(θ_JEPA - θ_SRK)

        CRITICAL CONTRACT (V10.6.3):
            Control signals may be scalar or per-head, but must NEVER vary
            across token positions. [B, N] is NOT allowed because:
            - Token-wise scalar still leaks structure into Phase
            - Allows alignment to suppress/amplify specific tokens
            - Phase turns into a soft attention map

        Args:
            theta_jepa: [B, N, D] or [B, N, K, D] - query intent
            theta_srk: [B, N, D] or [B, N, K, D] - key intent
            reduction: How to reduce the alignment:
                - "per_head": [H] - per-head control (recommended)
                - "global": [] - batch-level scalar (safest)
                - "per_batch_head": [B, H] - per-batch, per-head

        Returns:
            s_align: Shape depends on reduction mode:
                - "per_head": [H]
                - "global": []
                - "per_batch_head": [B, H]
        """
        if theta_jepa is None or theta_srk is None:
            return None

        # Intent difference
        theta_diff = theta_jepa - theta_srk

        # Cosine over the last dimension, then reduce appropriately
        # theta_diff: [B, N, D] → cos: [B, N, D]
        cos_diff = torch.cos(theta_diff)

        # Reshape to [B, N, H, D_h] for per-head reduction
        B, N, D = cos_diff.shape
        H = self.num_heads
        D_h = D // H
        cos_diff_heads = cos_diff.view(B, N, H, D_h)

        if reduction == "global":
            # Option A (ChatGPT): batch-level scalar (safest)
            # Mean over all dimensions → []
            s_align = cos_diff_heads.mean()
        elif reduction == "per_head":
            # Option B (ChatGPT): per-head control (recommended)
            # Mean over batch, seq, head_dim → [H]
            s_align = cos_diff_heads.mean(dim=(0, 1, 3))  # [H]
        elif reduction == "per_batch_head":
            # Variant: per-batch per-head
            # Mean over seq, head_dim → [B, H]
            s_align = cos_diff_heads.mean(dim=(1, 3))  # [B, H]
        else:
            raise ValueError(
                f"Invalid reduction mode: {reduction}. "
                f"Must be 'global', 'per_head', or 'per_batch_head'."
            )

        # V10.6.3: Validate that result is NOT token-position dependent
        # This enforces the contract: control signals must never vary across tokens
        from symbolu.phase_transformer import assert_alignment_signal_shape
        assert_alignment_signal_shape(
            s_align,
            name="s_align (alignment score)",
            num_heads=self.num_heads,
            seq_len=N,
            strict=self.strict_control_contract,  # V10.6.3: Use configured mode
        )

        return s_align

    def integrate_proposals(
        self,
        x: torch.Tensor,
        memory_state: torch.Tensor,
        proposals: torch.Tensor,
        proposal_scores: torch.Tensor,
        gamma: float = 0.9,
    ) -> torch.Tensor:
        """
        V10.4: Integrate quad proposals into phase state.
        V10.6: Extended with dual-channel alignment modulation.
        V10.6.1: Added clamp bounds for stability.

        This implements the "phase-as-integrator" pattern where phase
        decides which proposals survive and integrates them into state.

        Dual-channel mode (V10.6):
            s_align = cos(θ_JEPA - θ_SRK)
            weighted_proposals = weighted_proposals * clamp(1 + α * s_align, min, max)

        V10.6.1 Stability (ChatGPT Caveat 1):
            Clamping prevents over-constraint collapse from sustained misalignment.

        FUTURE WORK (ChatGPT Caveat 2):
            Currently s_align is global (per-step/per-batch), not per-proposal.
            Conceptually, different proposals may align differently:
            - θ_JEPA = query direction (what we're looking for)
            - θ_SRK = memory coherence (what each proposal offers)
            A future V10.7 could compute s_align_k per proposal k and modulate
            proposals individually. Not implementing now to avoid destabilizing
            early training.

        Args:
            x: Input tensor [B, N, D]
            memory_state: Current phase state [B, N, D]
            proposals: [B, N, K, D] - K proposals from quad
            proposal_scores: [B, N, K] - retrieval scores for each proposal
            gamma: Decay factor for state (0 < gamma < 1)

        Returns:
            integrated_output: [B, N, D] - integrated state update
        """
        B, N, K, D = proposals.shape

        # Phase computes gating weights (NOT quad softmax)
        # Use sigmoid + normalize for smoother gradients than softmax
        gate_logits = proposal_scores  # [B, N, K]

        # Sigmoid + normalize (not winner-take-all like softmax)
        gate_weights_raw = torch.sigmoid(gate_logits)  # [B, N, K]
        gate_weights = gate_weights_raw / (gate_weights_raw.sum(dim=-1, keepdim=True) + 1e-8)  # [B, N, K]

        # Weighted sum of proposals
        # [B, N, K, 1] * [B, N, K, D] -> [B, N, K, D] -> sum -> [B, N, D]
        weighted_proposals = (gate_weights.unsqueeze(-1) * proposals).sum(dim=2)  # [B, N, D]

        # V10.6: Dual-channel alignment modulation
        # V10.6.3: s_align is now [H] or [] (NOT [B, N])
        if self.dual_channel_mode:
            theta_jepa, theta_srk = self.compute_intent_phases(x, memory_state)
            s_align = self.compute_alignment_score(
                theta_jepa, theta_srk,
                reduction=self.alignment_reduction,
            )

            if s_align is not None:
                # Track diagnostics
                with torch.no_grad():
                    self._last_s_align_mean = s_align.mean().item()
                    if s_align.numel() > 1:
                        self._last_s_align_std = s_align.std().item()
                    else:
                        self._last_s_align_std = 0.0

                # V10.6.3: s_align is now [H] or [] (not [B, N])
                # Reshape for broadcasting to [B, N, D]
                # weighted_proposals: [B, N, D] where D = H * D_h
                if s_align.dim() == 0:
                    # Global scalar [] - broadcast to everything
                    alignment_modulator = 1.0 + self.alignment_authority * s_align
                elif s_align.dim() == 1:
                    # Per-head [H] - expand to [1, 1, H, 1] then reshape to [1, 1, D]
                    H = s_align.shape[0]
                    D_h = self.head_dim
                    # Replicate each head value D_h times: [H] -> [1, 1, H*D_h]
                    s_align_expanded = s_align.unsqueeze(0).unsqueeze(0)  # [1, 1, H]
                    s_align_expanded = s_align_expanded.repeat(1, 1, D_h)  # [1, 1, H*D_h]
                    # This broadcasts correctly: [1, 1, D] * [B, N, D] -> [B, N, D]
                    alignment_modulator = 1.0 + self.alignment_authority * s_align_expanded
                elif s_align.dim() == 2:
                    # Per-batch per-head [B, H] - expand to [B, 1, H*D_h]
                    B_s, H = s_align.shape
                    D_h = self.head_dim
                    s_align_expanded = s_align.unsqueeze(1)  # [B, 1, H]
                    s_align_expanded = s_align_expanded.repeat(1, 1, D_h)  # [B, 1, H*D_h]
                    alignment_modulator = 1.0 + self.alignment_authority * s_align_expanded
                else:
                    raise ValueError(f"Unexpected s_align shape: {s_align.shape}")

                # V10.6.1: Clamp to prevent over-constraint collapse (ChatGPT caveat)
                # Sustained JEPA/SRK misalignment can attenuate proposals and reduce
                # effective learning signal. Clamping ensures safe scaling range.
                alignment_modulator = torch.clamp(
                    alignment_modulator,
                    min=self.alignment_clamp_min,
                    max=self.alignment_clamp_max
                )

                weighted_proposals = weighted_proposals * alignment_modulator

        # State update: decay old state + integrate new proposals
        # S_{t+1} = gamma * S_t + (1 - gamma) * weighted_proposals
        integrated = gamma * memory_state + (1 - gamma) * weighted_proposals

        return integrated

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Compute memory state via cumsum.

        Args:
            x: [B, N, D]

        Returns:
            memory_state: [B, N, D]
        """
        B, N, D = x.shape
        x_norm = self.norm(x)

        # Compute phase and amplitude
        phi_k_raw = self.W_k_phase(x_norm).view(B, N, self.num_heads, self.head_dim)
        if self.bounded_phase:
            phi_k = math.pi * torch.sin(phi_k_raw)
        else:
            phi_k = phi_k_raw

        a_k = torch.sigmoid(self.W_k_amp(x_norm)).view(B, N, self.num_heads, self.head_dim)
        v = self.W_v(x_norm).view(B, N, self.num_heads, self.head_dim)

        # Track R_k health
        with torch.no_grad():
            r_k = a_k.mean(dim=(0, 1))  # [H, D_h]
            self._last_r_k_mean = r_k.mean().item()
            self._last_r_k_std = r_k.std().item()
            self._last_r_k_min = r_k.min().item()
            self._last_r_k_max = r_k.max().item()

        # Complex representation: z = a * e^(i*phi)
        z_real = a_k * torch.cos(phi_k)
        z_imag = a_k * torch.sin(phi_k)

        # Weighted value
        weighted_v = v * a_k

        # Cumsum for memory accumulation (with decay)
        if self.decay_gamma < 1.0:
            # Apply exponential decay
            decay_weights = torch.pow(
                torch.tensor(self.decay_gamma, device=x.device),
                torch.arange(N, device=x.device).float()
            ).view(1, N, 1, 1)
            weighted_v = weighted_v * decay_weights

        memory_state = torch.cumsum(weighted_v, dim=1)

        # Reshape back
        memory_state = memory_state.view(B, N, D)
        return memory_state


class BindingCacheQuadQuery(nn.Module):
    """
    Quadratic query with Top-K cache for efficient memory retrieval.

    Uses Top-K selection to reduce O(n²) attention to O(n*k).

    V10.5.4: Soft routing warmup support
    - soft_routing=True: Use full softmax attention (differentiable everywhere)
    - soft_routing=False: Use hard top-K selection (sparse but non-differentiable)

    Warmup schedule: Start with soft_routing=True, switch to False after warmup_steps.
    This allows gradients to flow to quad during early training.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        top_k: int = 64,
        use_cache: bool = True,
        proposal_mode: bool = False,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.top_k = top_k
        self.use_cache = use_cache
        self.proposal_mode = proposal_mode

        self.W_q = nn.Linear(embed_dim, embed_dim)
        self.W_o = nn.Linear(embed_dim, embed_dim)

        self.norm = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)
        self.scale = 1.0 / math.sqrt(self.head_dim)

        # V10.5.4: Soft routing warmup
        self.soft_routing = True  # Start with soft routing (full softmax)

    def set_soft_routing(self, enabled: bool):
        """V10.5.4: Enable/disable soft routing for warmup schedule."""
        self.soft_routing = enabled

    def get_proposals(
        self,
        x: torch.Tensor,
        memory_state: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        V10.4: Get TopK proposals WITHOUT softmax mixing.

        Instead of returning attention-weighted output, returns raw proposals
        for Phase to integrate. This implements the "quad-as-proposer" pattern.

        Args:
            x: Input tensor [B, N, D] - source for queries
            memory_state: [B, N, D] - from BindingCachePhaseState

        Returns:
            proposals: [B, N, K, D] - K proposal values per position
            scores: [B, N, K] - retrieval scores (before softmax) for each proposal
        """
        B, N, D = x.shape
        K = min(self.top_k, N)

        x_norm = self.norm(x)

        # Query projection
        q = self.W_q(x_norm).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)  # [B, H, N, D_h]

        # Memory as key-value
        mem = memory_state.view(B, N, self.num_heads, self.head_dim).transpose(1, 2)  # [B, H, N, D_h]

        # Compute attention scores
        scores = torch.matmul(q, mem.transpose(-2, -1)) * self.scale  # [B, H, N, N]

        # Causal mask
        causal_mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
        scores = scores.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        # TopK selection - NO SOFTMAX
        top_scores, top_indices = scores.topk(K, dim=-1, largest=True)  # [B, H, N, K]

        # Gather corresponding values
        top_indices_expanded = top_indices.unsqueeze(-1).expand(-1, -1, -1, -1, self.head_dim)
        mem_expanded = mem.unsqueeze(2).expand(-1, -1, N, -1, -1)  # [B, H, N, N, D_h]
        top_mem = torch.gather(mem_expanded, 3, top_indices_expanded)  # [B, H, N, K, D_h]

        # Reshape: [B, H, N, K, D_h] -> [B, N, K, H*D_h] = [B, N, K, D]
        proposals = top_mem.permute(0, 2, 3, 1, 4).reshape(B, N, K, D)

        # Scores: [B, H, N, K] -> [B, N, K] (mean across heads)
        proposal_scores = top_scores.permute(0, 2, 3, 1).mean(dim=-1)  # [B, N, K]

        return proposals, proposal_scores

    def forward(
        self,
        x: torch.Tensor,
        memory_state: torch.Tensor,
    ) -> torch.Tensor:
        """
        Query memory state with Top-K selection or soft routing.

        V10.5.4: Soft routing warmup
        - soft_routing=True: Full softmax attention (differentiable, O(n²))
        - soft_routing=False: Hard top-K selection (sparse, O(n*k))

        Args:
            x: [B, N, D]
            memory_state: [B, N, D] from Phase accumulator

        Returns:
            output: [B, N, D]
        """
        B, N, D = x.shape
        x_norm = self.norm(x)

        # Query projection
        q = self.W_q(x_norm).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)  # [B, H, N, D_h]

        # Memory as key-value
        mem = memory_state.view(B, N, self.num_heads, self.head_dim).transpose(1, 2)  # [B, H, N, D_h]

        # Compute attention scores
        attn_scores = torch.matmul(q, mem.transpose(-2, -1)) * self.scale  # [B, H, N, N]

        # Causal mask
        causal_mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
        attn_scores = attn_scores.masked_fill(causal_mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        # V10.5.4: Soft routing warmup - use full softmax during warmup
        if self.soft_routing:
            # Full attention (differentiable everywhere, allows gradients to flow)
            attn_probs = F.softmax(attn_scores, dim=-1)
            attn_probs = self.dropout(attn_probs)
            attn_out = torch.matmul(attn_probs, mem)
        elif self.use_cache and self.top_k < N:
            # Hard Top-K selection (sparse, non-differentiable for non-selected)
            k = min(self.top_k, N)
            top_k_scores, top_k_indices = torch.topk(attn_scores, k, dim=-1)

            # Create sparse attention (only top-k positions)
            attn_probs = F.softmax(top_k_scores, dim=-1)
            attn_probs = self.dropout(attn_probs)

            # Gather top-k memory values
            top_k_indices_expanded = top_k_indices.unsqueeze(-1).expand(-1, -1, -1, -1, self.head_dim)
            mem_expanded = mem.unsqueeze(2).expand(-1, -1, N, -1, -1)  # [B, H, N, N, D_h]
            top_k_mem = torch.gather(mem_expanded, 3, top_k_indices_expanded)  # [B, H, N, k, D_h]

            attn_out = torch.matmul(attn_probs.unsqueeze(-2), top_k_mem).squeeze(-2)  # [B, H, N, D_h]
        else:
            # Full attention (no cache configured)
            attn_probs = F.softmax(attn_scores, dim=-1)
            attn_probs = self.dropout(attn_probs)
            attn_out = torch.matmul(attn_probs, mem)

        attn_out = attn_out.transpose(1, 2).contiguous().view(B, N, D)
        return self.W_o(attn_out)


# =============================================================================
# V10.5.7: BINDING SLOT CACHE (Explicit Key-Value Memory)
# =============================================================================
# Minimal symbolic structure for associative recall.
# This module provides explicit key-value slots that Quad can query,
# separate from the decayed Phase memory.
#
# Key insight from AR experiment: Phase's decayed cumsum creates a "blurred
# superposition" that cannot be inverted. Binding slots provide discrete,
# content-addressable storage.

class BindingSlotCache(nn.Module):
    """
    Explicit key-value binding slots for discrete memory retrieval.

    Solves the associative recall problem by providing:
    1. Identity - each slot stores a distinct (key, value) pair
    2. Stability - slots don't decay or blend
    3. Addressability - content-based retrieval via key similarity

    Architecture:
    - N slots, each with key_emb and value_emb [D]
    - Write: detect (K, V) patterns, store in next available slot
    - Read: query by key similarity, return corresponding value
    - Separate from Phase decay - slots persist until overwritten

    V10.5.7b Fixes for failure modes:
    - Failure Mode A: Force slot usage at query positions (query_mask output)
    - Failure Mode B: Contextualized keys with position encoding

    This is a minimal Memory Network / NTM-style component.
    """

    def __init__(
        self,
        embed_dim: int,
        num_slots: int = 16,
        num_heads: int = 8,
        dropout: float = 0.1,
        max_seq_len: int = 512,  # For positional encoding
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_slots = num_slots
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.max_seq_len = max_seq_len

        # Learnable slot embeddings (keys and values)
        # These are updated during forward pass based on input patterns
        self.register_buffer('slot_keys', torch.zeros(1, num_slots, embed_dim))
        self.register_buffer('slot_values', torch.zeros(1, num_slots, embed_dim))
        self.register_buffer('slot_used', torch.zeros(1, num_slots, dtype=torch.bool))
        self.register_buffer('write_head', torch.zeros(1, dtype=torch.long))

        # V10.5.7b: Positional encoding for contextualized keys (Failure Mode B fix)
        self.pos_emb = nn.Embedding(max_seq_len, embed_dim)

        # Projections for key-value - now includes position context
        # Key projection: combines token hidden state with position
        self.key_proj = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim),  # hidden + position
            nn.ReLU(),
            nn.Linear(embed_dim, embed_dim),
        )
        self.value_proj = nn.Linear(embed_dim, embed_dim)

        # Query projection for reading
        self.query_proj = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim),  # hidden + position for query too
            nn.ReLU(),
            nn.Linear(embed_dim, embed_dim),
        )
        self.output_proj = nn.Linear(embed_dim, embed_dim)

        # Write gate - learns when to write (triggered by patterns like K=V)
        self.write_gate = nn.Sequential(
            nn.Linear(embed_dim * 2, embed_dim),
            nn.ReLU(),
            nn.Linear(embed_dim, 1),
            nn.Sigmoid(),
        )

        self.norm = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)
        self.scale = 1.0 / math.sqrt(self.head_dim)

    def reset_slots(self, batch_size: int, device: torch.device):
        """Reset slots for a new sequence (call at start of each batch)."""
        self.slot_keys = torch.zeros(batch_size, self.num_slots, self.embed_dim, device=device)
        self.slot_values = torch.zeros(batch_size, self.num_slots, self.embed_dim, device=device)
        self.slot_used = torch.zeros(batch_size, self.num_slots, dtype=torch.bool, device=device)
        self.write_head = torch.zeros(batch_size, dtype=torch.long, device=device)

    def write_binding(
        self,
        key_emb: torch.Tensor,  # [B, D]
        value_emb: torch.Tensor,  # [B, D]
        write_mask: torch.Tensor,  # [B] - which batch items to write
    ):
        """
        Write a key-value binding to the next available slot.

        Args:
            key_emb: Key embedding to store [B, D]
            value_emb: Value embedding to store [B, D]
            write_mask: Boolean mask indicating which batch items should write [B]
        """
        B = key_emb.shape[0]

        for b in range(B):
            if write_mask[b] and self.write_head[b] < self.num_slots:
                slot_idx = self.write_head[b].item()
                self.slot_keys[b, slot_idx] = key_emb[b].detach()  # Detach to avoid long BPTT
                self.slot_values[b, slot_idx] = value_emb[b].detach()
                self.slot_used[b, slot_idx] = True
                self.write_head[b] = min(self.write_head[b] + 1, self.num_slots - 1)

    def read_by_query(
        self,
        query: torch.Tensor,  # [B, N, D] - already projected with position
    ) -> torch.Tensor:
        """
        Read from slots by querying with key similarity.

        Args:
            query: Query embeddings [B, N, D] (already projected)

        Returns:
            retrieved: Retrieved values [B, N, D]
        """
        B, N, D = query.shape

        # Compute attention over slots
        # query: [B, N, D], slot_keys: [B, num_slots, D]
        attn_scores = torch.matmul(query, self.slot_keys.transpose(-2, -1)) * self.scale  # [B, N, num_slots]

        # Mask unused slots
        slot_mask = ~self.slot_used  # [B, num_slots]
        attn_scores = attn_scores.masked_fill(slot_mask.unsqueeze(1), float('-inf'))

        # Softmax over slots
        attn_probs = F.softmax(attn_scores, dim=-1)  # [B, N, num_slots]
        attn_probs = self.dropout(attn_probs)

        # Retrieve values
        # attn_probs: [B, N, num_slots], slot_values: [B, num_slots, D]
        retrieved = torch.matmul(attn_probs, self.slot_values)  # [B, N, D]

        return self.output_proj(retrieved)

    def forward(
        self,
        x: torch.Tensor,
        input_ids: Optional[torch.Tensor] = None,
        eq_token_id: Optional[int] = None,
        query_token_id: Optional[int] = None,  # V10.5.7b: For detecting query positions
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Process input: detect write patterns, read from slots.

        For associative recall, we detect K=V patterns:
        - Position i has EQ_TOKEN (=)
        - Key is at position i-1
        - Value is at position i+1
        - Write (key, value) to slot

        V10.5.7b: Returns query_mask to force slot usage at query positions.

        Args:
            x: Input embeddings [B, N, D]
            input_ids: Original token IDs [B, N] (for pattern detection)
            eq_token_id: The token ID for '=' (EQ_TOKEN)
            query_token_id: The token ID for '?' (QUERY_TOKEN) - for forcing slot usage

        Returns:
            output: Retrieved memories [B, N, D]
            query_mask: Positions where slots should be forced [B, N] (Failure Mode A fix)
        """
        B, N, D = x.shape
        x_norm = self.norm(x)

        # Get position embeddings
        positions = torch.arange(N, device=x.device).unsqueeze(0).expand(B, -1)
        pos_emb = self.pos_emb(positions.clamp(max=self.max_seq_len - 1))  # [B, N, D]

        # Reset slots at sequence start (position 0)
        # In practice, this should be called externally before each sequence
        if not hasattr(self, '_initialized') or self.slot_keys.shape[0] != B:
            self.reset_slots(B, x.device)
            self._initialized = True

        # V10.5.7b: Detect query positions for Failure Mode A fix
        query_mask = torch.zeros(B, N, dtype=torch.bool, device=x.device)
        if input_ids is not None and query_token_id is not None:
            query_mask = (input_ids == query_token_id)  # [B, N]

        # Pattern detection and writing (if input_ids provided)
        if input_ids is not None and eq_token_id is not None:
            # Find positions where EQ_TOKEN appears
            eq_mask = (input_ids == eq_token_id)  # [B, N]

            # For each EQ position, write (key=prev, value=next)
            for pos in range(1, N - 1):
                write_mask = eq_mask[:, pos]  # [B]
                if write_mask.any():
                    # V10.5.7b: Contextualized key with position (Failure Mode B fix)
                    # Key is at pos-1, combine hidden state with position
                    key_hidden = x_norm[:, pos - 1]  # [B, D]
                    key_pos = pos_emb[:, pos - 1]  # [B, D]
                    key_emb = self.key_proj(torch.cat([key_hidden, key_pos], dim=-1))  # [B, D]

                    value_emb = self.value_proj(x_norm[:, pos + 1])  # [B, D]
                    self.write_binding(key_emb, value_emb, write_mask)

        # V10.5.7b: Contextualized query with position
        query_input = torch.cat([x_norm, pos_emb], dim=-1)  # [B, N, 2D]
        query = self.query_proj(query_input)  # [B, N, D]

        # Read from slots using current position as query
        retrieved = self.read_by_query(query)

        return retrieved, query_mask

    def get_slot_usage(self) -> Dict[str, float]:
        """Get diagnostic info about slot usage."""
        used_count = self.slot_used.sum().item()
        total_slots = self.slot_used.numel()
        return {
            'used_slots': used_count,
            'total_slots': total_slots,
            'usage_ratio': used_count / total_slots if total_slots > 0 else 0.0,
        }


class BindingCacheLMBlock(nn.Module):
    """
    Binding Cache block for Language Modeling.

    V10.5.3 Independent Paths Architecture (Option A):
    1. Local: O(n*w) - Syntax attention (independent path)
    2. Phase: O(n) - Pure memory bank (K/V for quad only)
    3. Quad:  O(n*k) - Memory retriever (queries phase using raw x)

    Key design: Local and Quad are INDEPENDENT paths, both operating on raw x.
    Phase is a pure memory bank - it only provides K/V for quad, no direct output.

    Information flow:
        local_out = local_attn(x)           # Syntax (independent)
        memory_state = phase_state(x)       # Memory bank
        quad_out = quad_query(x, memory_state)  # Retrieval (independent)
        output = local_ratio * local_out + quad_ratio * quad_out

    Evolution:
    - V10.0: Phase leaked to output, quad redundant (0.1% gradients)
    - V10.5.2: Cross-attention (Q=local_out), still 0.1% gradients
    - V10.5.3: Independent paths (Q=x), testing clean architecture
    - V10.6: Added dual-channel mode support (JEPA/SRK intent alignment)
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        ff_dim: int,
        dropout: float = 0.1,
        decay_gamma: float = 0.9,
        bounded_phase: bool = True,
        top_k: int = 64,
        use_cache: bool = True,
        local_window_size: int = 64,
        local_ratio: float = 0.4,
        phase_ratio: float = 0.3,
        quad_ratio: float = 0.3,
        proposal_mode: bool = False,  # V10.4: Quad proposes, Phase integrates
        confidence_threshold: float = 0.7,  # V10.4: Skip quad if confidence > threshold
        dual_channel_mode: bool = False,  # V10.6: Enable JEPA/SRK intent alignment
        alignment_authority: float = 0.1,  # V10.6: α weight for alignment term
        alignment_clamp_min: float = 0.8,  # V10.6.1: Clamp lower bound
        alignment_clamp_max: float = 1.2,  # V10.6.1: Clamp upper bound
        alignment_reduction: str = "per_head",  # V10.6.3: Alignment reduction mode
        strict_control_contract: bool = True,  # V10.6.3: Strict vs warn mode
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.proposal_mode = proposal_mode
        self.confidence_threshold = confidence_threshold

        # V10.6: Dual-channel mode
        self.dual_channel_mode = dual_channel_mode
        self.alignment_authority = alignment_authority
        # V10.6.1: Clamp bounds
        self.alignment_clamp_min = alignment_clamp_min
        self.alignment_clamp_max = alignment_clamp_max
        # V10.6.3: Alignment reduction and strict mode
        self.alignment_reduction = alignment_reduction
        self.strict_control_contract = strict_control_contract

        # Store ratios for weighted combination
        self.local_ratio = local_ratio
        self.phase_ratio = phase_ratio
        self.quad_ratio = quad_ratio

        # Local attention for syntax learning
        self.local_attn = LocalWindowAttention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            window_size=local_window_size,
            dropout=dropout,
        )

        # Phase state accumulator
        self.phase_state = BindingCachePhaseState(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            decay_gamma=decay_gamma,
            bounded_phase=bounded_phase,
            dual_channel_mode=dual_channel_mode,  # V10.6
            alignment_authority=alignment_authority,  # V10.6
            alignment_clamp_min=alignment_clamp_min,  # V10.6.1
            alignment_clamp_max=alignment_clamp_max,  # V10.6.1
        )

        # Quad memory query
        self.quad_query = BindingCacheQuadQuery(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            top_k=top_k,
            use_cache=use_cache,
            proposal_mode=proposal_mode,
        )

        # Feed-forward
        self.norm_ff = nn.LayerNorm(embed_dim)
        self.ff = nn.Sequential(
            nn.Linear(embed_dim, ff_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ff_dim, embed_dim),
            nn.Dropout(dropout),
        )

        # V10.4: Instrumentation for proposal mode
        self._last_confidence_mean = 0.0
        self._last_skip_rate = 0.0

    def get_phase_health(self) -> dict:
        return self.phase_state.get_health_metrics()

    def get_proposal_metrics(self) -> dict:
        """V10.4: Return proposal mode instrumentation."""
        return {
            "confidence_mean": self._last_confidence_mean,
            "skip_rate": self._last_skip_rate,
        }

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Independent paths architecture (V10.5.3 - Option A).

        V10.5.3 Change: Clean independent paths design
        - Local: syntax attention (independent path)
        - Phase: pure memory bank (provides K/V for quad)
        - Quad: memory retriever (queries phase using raw x, independent path)

        Key insight from V10.5.2: Cross-attention (Q=local_out) didn't help quad.
        Window=8 diagnostic confirmed quad's 0.1% gradients is NOT due to local masking.
        Option A tests if independent paths help quad optimization.

        Information flow:
        1. Local: local_out = local_attn(x)     [O(n*w)] - syntax, independent
        2. Phase: memory = phase_state(x)       [O(n)]   - memory bank
        3. Quad:  quad_out = quad_query(x, memory) [O(n*k)] - retrieves from phase

        Output = x + (local_ratio * local_out + quad_ratio * quad_out) + ff
        Note: Local and Quad are INDEPENDENT paths operating on raw input x
        """
        # Step 1: Local attention for syntax (independent path)
        local_out = self.local_attn(x)

        # Step 2: Phase accumulates memory state (pure memory bank for quad)
        memory_state = self.phase_state(x)

        if self.proposal_mode:
            # V10.4: Proposal Mode - quad proposes, phase integrates
            confidence = self.phase_state.compute_confidence(memory_state)

            with torch.no_grad():
                self._last_confidence_mean = confidence.mean().item()
                self._last_skip_rate = (confidence > self.confidence_threshold).float().mean().item()

            # V10.5.3: Get proposals using x as query source (independent from local)
            proposals, proposal_scores = self.quad_query.get_proposals(x, memory_state)

            # Phase integrates proposals
            quad_out = self.phase_state.integrate_proposals(
                x, memory_state, proposals, proposal_scores
            )
        else:
            # V10.5.3: Quad queries memory using raw x (independent from local)
            quad_out = self.quad_query(x, memory_state)

        # V10.5.3: Independent paths combination
        # Local and Quad operate independently on x, no serial dependency
        attn_out = (
            self.local_ratio * local_out +
            self.quad_ratio * quad_out
        )

        # Residual and FF
        x = x + attn_out
        x = x + self.ff(self.norm_ff(x))

        return x


class BindingCacheLMTransformer(nn.Module):
    """
    Language Modeling Transformer with Binding Cache architecture (V10.0).

    Validated by diagnostic probes:
    - Phase: O(n) state accumulator (exclusive role)
    - Quad: O(n*k) memory query via Top-K cache (exclusive role)
    - Local: O(n*w) direct syntax attention

    Reference: --protected-phase showed -50% ablation drop when Phase
    has protected role (vs ~0% when mixed with Quad).

    Supports:
    - Layer-wise probing for SRK integration
    - Phase health monitoring (R_k statistics)
    - Top-K cache for O(n*k) complexity
    """

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        num_heads: int,
        num_layers: int,
        d_ff: int,
        dropout: float,
        max_seq_len: int,
        bounded_phase: bool = True,
        top_k: int = 64,
        use_cache: bool = True,
        decay_gamma: float = 0.9,
        window_size: int = 64,
        phase_ratios: List[float] = None,
        local_ratios: List[float] = None,
        quad_ratios: List[float] = None,
        proposal_mode: bool = False,  # V10.4: Quad proposes, Phase integrates
        confidence_threshold: float = 0.7,  # V10.4: Skip quad if confidence > threshold
        # V10.5.7: Binding Slot Cache for explicit key-value memory
        binding_slots: int = 0,  # 0 = disabled, >0 = number of slots
        binding_slot_eq_token: int = None,  # Token ID for '=' (triggers write)
        binding_slot_query_token: int = None,  # V10.5.7b: Token ID for '?' (forces slot read)
        # V10.6: Dual-channel mode (JEPA/SRK intent alignment)
        dual_channel_mode: bool = False,
        alignment_authority: float = 0.1,
        # V10.6.1: Clamp bounds to prevent over-constraint collapse
        alignment_clamp_min: float = 0.8,
        alignment_clamp_max: float = 1.2,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.num_heads = num_heads
        self.num_layers = num_layers
        self.proposal_mode = proposal_mode

        # V10.6: Dual-channel mode
        self.dual_channel_mode = dual_channel_mode
        self.alignment_authority = alignment_authority
        # V10.6.1: Clamp bounds
        self.alignment_clamp_min = alignment_clamp_min
        self.alignment_clamp_max = alignment_clamp_max

        # V10.5.7: Binding slot configuration
        self.binding_slots_enabled = binding_slots > 0
        self.binding_slot_eq_token = binding_slot_eq_token
        self.binding_slot_query_token = binding_slot_query_token  # V10.5.7b

        # Default ratios if not specified
        if phase_ratios is None:
            phase_ratios = [0.3] * num_layers
        if local_ratios is None:
            local_ratios = [0.4] * num_layers
        if quad_ratios is None:
            quad_ratios = [0.3] * num_layers

        # Store ratios for logging
        self.phase_ratios = phase_ratios
        self.local_ratios = local_ratios
        self.quad_ratios = quad_ratios

        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)

        # V10.5.7: Binding Slot Cache (shared across layers, first layer only)
        self.binding_slot_cache = None
        if self.binding_slots_enabled:
            self.binding_slot_cache = BindingSlotCache(
                embed_dim=d_model,
                num_slots=binding_slots,
                num_heads=num_heads,
                dropout=dropout,
                max_seq_len=max_seq_len,  # V10.5.7b: For positional encoding
            )
            # Learnable gate to combine slot output with main path
            self.slot_gate = nn.Sequential(
                nn.Linear(d_model * 2, d_model),
                nn.ReLU(),
                nn.Linear(d_model, 1),
                nn.Sigmoid(),
            )

        # Binding Cache blocks with per-layer ratios
        self.layers = nn.ModuleList([
            BindingCacheLMBlock(
                embed_dim=d_model,
                num_heads=num_heads,
                ff_dim=d_ff,
                dropout=dropout,
                decay_gamma=decay_gamma,
                bounded_phase=bounded_phase,
                top_k=top_k,
                use_cache=use_cache,
                local_window_size=window_size,
                local_ratio=local_ratios[i],
                phase_ratio=phase_ratios[i],
                quad_ratio=quad_ratios[i],
                proposal_mode=proposal_mode,
                confidence_threshold=confidence_threshold,
                dual_channel_mode=dual_channel_mode,  # V10.6
                alignment_authority=alignment_authority,  # V10.6
                alignment_clamp_min=alignment_clamp_min,  # V10.6.1
                alignment_clamp_max=alignment_clamp_max,  # V10.6.1
            )
            for i in range(num_layers)
        ])

        self.norm = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

        # Weight tying
        self.lm_head.weight = self.token_emb.weight

        # Layer outputs for SRK probing
        self.layer_outputs = []

        # Curriculum placeholder (for API compatibility)
        self.curriculum = [1.0] * num_layers

    def forward(self, input_ids: torch.Tensor, probe_layers: bool = False) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        self.layer_outputs = []

        # V10.5.7: Reset binding slot cache for new batch
        if self.binding_slots_enabled and self.binding_slot_cache is not None:
            self.binding_slot_cache.reset_slots(B, input_ids.device)

        for i, layer in enumerate(self.layers):
            x = layer(x)

            # V10.5.7: Apply binding slot cache after first layer
            # This allows embeddings to be processed before write/read
            if i == 0 and self.binding_slots_enabled and self.binding_slot_cache is not None:
                # Get slot retrieval and query mask
                slot_out, query_mask = self.binding_slot_cache(
                    x,
                    input_ids=input_ids,
                    eq_token_id=self.binding_slot_eq_token,
                    query_token_id=self.binding_slot_query_token,  # V10.5.7b
                )

                # Gated combination: gate * slot_out + (1-gate) * x
                gate_input = torch.cat([x, slot_out], dim=-1)
                gate = self.slot_gate(gate_input)  # [B, N, 1]

                # V10.5.7b: Force slot usage at query positions (Failure Mode A fix)
                # At query positions, override gate to be high (0.9) to force slot retrieval
                if query_mask.any():
                    # Create forced gate: 0.9 at query positions, learned elsewhere
                    forced_gate = torch.where(
                        query_mask.unsqueeze(-1),  # [B, N, 1]
                        torch.tensor(0.9, device=gate.device, dtype=gate.dtype),
                        gate
                    )
                    gate = forced_gate

                x = gate * slot_out + (1 - gate) * x

            if probe_layers:
                self.layer_outputs.append(x.detach().clone())

        x = self.norm(x)
        logits = self.lm_head(x)
        return logits

    def get_slot_usage(self) -> Dict[str, float]:
        """V10.5.7: Get binding slot usage diagnostics."""
        if self.binding_slot_cache is not None:
            return self.binding_slot_cache.get_slot_usage()
        return {'used_slots': 0, 'total_slots': 0, 'usage_ratio': 0.0}

    def get_phase_health(self) -> dict:
        """Aggregate Phase health metrics from all layers."""
        metrics = {"r_k_mean": [], "r_k_std": [], "r_k_min": [], "r_k_max": []}
        for layer in self.layers:
            layer_metrics = layer.get_phase_health()
            for k, v in layer_metrics.items():
                metrics[k].append(v)

        return {
            "r_k_mean": sum(metrics["r_k_mean"]) / len(metrics["r_k_mean"]) if metrics["r_k_mean"] else 0.0,
            "r_k_std": sum(metrics["r_k_std"]) / len(metrics["r_k_std"]) if metrics["r_k_std"] else 0.0,
            "r_k_min": min(metrics["r_k_min"]) if metrics["r_k_min"] else 0.0,
            "r_k_max": max(metrics["r_k_max"]) if metrics["r_k_max"] else 0.0,
        }

    def get_proposal_metrics(self) -> dict:
        """
        V10.4: Aggregate proposal mode metrics from all layers.

        Returns:
            dict with confidence_mean, skip_rate, and per-layer metrics
        """
        if not self.proposal_mode:
            return {
                "confidence_mean": 0.0,
                "skip_rate": 0.0,
                "per_layer_confidence": [],
                "per_layer_skip_rate": [],
            }

        confidence_means = []
        skip_rates = []
        for layer in self.layers:
            metrics = layer.get_proposal_metrics()
            confidence_means.append(metrics["confidence_mean"])
            skip_rates.append(metrics["skip_rate"])

        return {
            "confidence_mean": sum(confidence_means) / len(confidence_means) if confidence_means else 0.0,
            "skip_rate": sum(skip_rates) / len(skip_rates) if skip_rates else 0.0,
            "per_layer_confidence": confidence_means,
            "per_layer_skip_rate": skip_rates,
        }

    def update_curriculum(self, new_curriculum: List[float]):
        """API compatibility (no-op for binding cache)."""
        pass

    def get_layer_ppl(self, input_ids: torch.Tensor, targets: torch.Tensor) -> List[float]:
        """Compute PPL contribution from each layer by early-exiting."""
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        layer_ppls = []
        for layer in self.layers:
            x = layer(x)
            x_normed = self.norm(x)
            logits = self.lm_head(x_normed)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            ppl = torch.exp(loss).item()
            layer_ppls.append(ppl)

        return layer_ppls

    def get_layer_contributions(self, input_ids: torch.Tensor, targets: torch.Tensor) -> Dict[str, List[float]]:
        """Analyze per-layer contributions."""
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        # Initial PPL (embedding only)
        logits_embed = self.lm_head(self.norm(x))
        loss_embed = F.cross_entropy(logits_embed.view(-1, self.vocab_size), targets.view(-1))
        ppl_embed = torch.exp(loss_embed).item()

        layer_ppls = []
        layer_deltas = []
        prev_ppl = ppl_embed

        for layer in self.layers:
            x = layer(x)
            x_normed = self.norm(x)
            logits = self.lm_head(x_normed)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            ppl = torch.exp(loss).item()

            layer_ppls.append(ppl)
            layer_deltas.append(prev_ppl - ppl)
            prev_ppl = ppl

        total_reduction = ppl_embed - layer_ppls[-1]
        contribution_pcts = [
            (delta / total_reduction * 100) if total_reduction > 0 else 0
            for delta in layer_deltas
        ]

        return {
            'ppl': layer_ppls,
            'ppl_delta': layer_deltas,
            'contribution_pct': contribution_pcts,
            'phase_ratio': [1.0] * self.num_layers,
            'ppl_embed': ppl_embed,
            'total_reduction': total_reduction,
        }

    def ablate_attention(self, input_ids: torch.Tensor, targets: torch.Tensor,
                         ablate_phase: bool = False, ablate_local: bool = False) -> float:
        """Return normal PPL (full ablation not implemented for probe)."""
        with torch.no_grad():
            logits = self.forward(input_ids)
            loss = F.cross_entropy(logits.view(-1, self.vocab_size), targets.view(-1))
            return torch.exp(loss).item()

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    # =========================================================================
    # V10.5.4: Soft Routing Warmup Control
    # =========================================================================
    def set_soft_routing(self, enabled: bool):
        """
        V10.5.4: Enable/disable soft routing for all quad query layers.

        Soft routing uses full softmax attention (differentiable everywhere)
        instead of hard top-K selection (non-differentiable for non-selected).

        Args:
            enabled: True = soft routing (warmup), False = hard top-K (normal)
        """
        for layer in self.layers:
            if hasattr(layer, 'quad_query') and hasattr(layer.quad_query, 'set_soft_routing'):
                layer.quad_query.set_soft_routing(enabled)

    # =========================================================================
    # V10.5: FIX 3 - True Gradient Norm Diagnostic (not curriculum-based)
    # =========================================================================
    def get_component_grad_norms(self) -> Dict[str, List[float]]:
        """
        Measure actual gradient norms for each attention component per layer.

        Returns dict with per-layer gradient norms for:
        - local: LocalWindowAttention gradients
        - phase: BindingCachePhaseState gradients
        - quad:  BindingCacheQuadQuery gradients
        - ff:    Feed-forward gradients

        This replaces the broken curriculum-based "gradient dominance" diagnostic
        which falsely reported 100% phase-heavy for Protected Phase architecture.
        """
        grad_norms = {
            'local': [],
            'phase': [],
            'quad': [],
            'ff': [],
        }

        for layer in self.layers:
            # Local attention gradient norm
            local_norm = 0.0
            for p in layer.local_attn.parameters():
                if p.grad is not None:
                    local_norm += p.grad.data.norm(2).item() ** 2
            grad_norms['local'].append(local_norm ** 0.5)

            # Phase state gradient norm
            phase_norm = 0.0
            for p in layer.phase_state.parameters():
                if p.grad is not None:
                    phase_norm += p.grad.data.norm(2).item() ** 2
            grad_norms['phase'].append(phase_norm ** 0.5)

            # Quad query gradient norm
            quad_norm = 0.0
            for p in layer.quad_query.parameters():
                if p.grad is not None:
                    quad_norm += p.grad.data.norm(2).item() ** 2
            grad_norms['quad'].append(quad_norm ** 0.5)

            # Feed-forward gradient norm
            ff_norm = 0.0
            for p in layer.ff.parameters():
                if p.grad is not None:
                    ff_norm += p.grad.data.norm(2).item() ** 2
            grad_norms['ff'].append(ff_norm ** 0.5)

        return grad_norms

    def get_gradient_dominance_report(self) -> Dict[str, any]:
        """
        Analyze which components receive gradients and detect dominance issues.

        A healthy model should have gradients flowing to all components at all layers.
        Gradient dominance (one component >> others) indicates learning imbalance.

        Returns:
            dict with:
            - component_totals: Total gradient norm per component
            - component_pcts: Percentage contribution per component
            - per_layer_dominant: Which component dominates each layer
            - dominance_detected: True if one component > 70% of total
            - layer_gradient_decay: Ratio of L_last / L_0 gradients (healthy > 0.1)
        """
        grad_norms = self.get_component_grad_norms()

        # Sum across layers for each component
        totals = {k: sum(v) for k, v in grad_norms.items()}
        grand_total = sum(totals.values()) + 1e-10  # Avoid division by zero

        # Percentage contribution per component
        pcts = {k: (v / grand_total * 100) for k, v in totals.items()}

        # Per-layer dominant component
        per_layer_dominant = []
        for i in range(self.num_layers):
            layer_norms = {k: grad_norms[k][i] for k in grad_norms.keys()}
            dominant = max(layer_norms, key=layer_norms.get)
            per_layer_dominant.append(dominant)

        # Check for dominance (any component > 70%)
        max_pct = max(pcts.values())
        dominance_detected = max_pct > 70

        # Layer gradient decay: how much gradient reaches later layers
        # Healthy models should have layer_gradient_decay > 0.1
        total_per_layer = [sum(grad_norms[k][i] for k in grad_norms.keys())
                          for i in range(self.num_layers)]
        if total_per_layer[0] > 1e-10:
            layer_gradient_decay = total_per_layer[-1] / total_per_layer[0]
        else:
            layer_gradient_decay = 0.0

        return {
            'component_totals': totals,
            'component_pcts': pcts,
            'per_layer_dominant': per_layer_dominant,
            'dominance_detected': dominance_detected,
            'layer_gradient_decay': layer_gradient_decay,
            'per_layer_totals': total_per_layer,
        }

    # =========================================================================
    # V10.5: FIX 1 - Deep Supervision for Depth Utilization
    # =========================================================================
    def init_deep_supervision(self, lambda_decay: float = 1.0):
        """
        Initialize auxiliary classification heads for deep supervision.

        Deep supervision forces later layers to learn useful representations
        by adding auxiliary losses at intermediate layers. This prevents
        L0 overfitting where only the first layer contributes to PPL reduction.

        Args:
            lambda_decay: Controls how much later layers are weighted.
                          Loss_i = lambda_decay * (i / num_layers) * CE(proj_i(h_i), targets)
                          Higher values encourage later layers more strongly.
        """
        self.deep_supervision_enabled = True
        self.deep_supervision_lambda = lambda_decay

        # Auxiliary projection heads - one per layer (except last)
        # These project intermediate representations to logits
        # We use weight-tied heads (share with lm_head) to reduce params
        self.aux_norms = nn.ModuleList([
            nn.LayerNorm(self.d_model) for _ in range(self.num_layers - 1)
        ])

        # Move to same device as model
        device = next(self.parameters()).device
        self.aux_norms = self.aux_norms.to(device)

    def forward_with_deep_supervision(
        self,
        input_ids: torch.Tensor,
        targets: torch.Tensor,
        ignore_index: int = -100  # V10.5.6: For associative recall (ignore PAD tokens)
    ) -> Tuple[torch.Tensor, torch.Tensor, List[float]]:
        """
        Forward pass with deep supervision losses at intermediate layers.

        Args:
            input_ids: [B, N] input token IDs
            targets: [B, N] target token IDs for loss computation
            ignore_index: Token ID to ignore in loss computation (-100 = none)

        Returns:
            logits: [B, N, V] final layer logits
            deep_loss: Scalar tensor with weighted sum of auxiliary losses
            layer_losses: List of per-layer auxiliary losses (for monitoring)
        """
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        layer_losses = []
        deep_loss = torch.tensor(0.0, device=input_ids.device)

        for i, layer in enumerate(self.layers):
            x = layer(x)

            # Compute auxiliary loss for all layers except the last
            if hasattr(self, 'deep_supervision_enabled') and self.deep_supervision_enabled:
                if i < self.num_layers - 1:
                    # Layer weight: increases with depth to emphasize later layers
                    # λ * (i+1) / num_layers ensures L0 gets minimal weight, Ln-1 gets max
                    layer_weight = self.deep_supervision_lambda * (i + 1) / self.num_layers

                    # Project to logits using shared lm_head
                    x_normed = self.aux_norms[i](x)
                    aux_logits = self.lm_head(x_normed)
                    aux_loss = F.cross_entropy(
                        aux_logits.view(-1, self.vocab_size),
                        targets.view(-1),
                        ignore_index=ignore_index  # V10.5.6: Ignore PAD for AR
                    )

                    layer_losses.append(aux_loss.item())
                    deep_loss = deep_loss + layer_weight * aux_loss

        # Final layer
        x = self.norm(x)
        logits = self.lm_head(x)

        return logits, deep_loss, layer_losses


# =============================================================================
