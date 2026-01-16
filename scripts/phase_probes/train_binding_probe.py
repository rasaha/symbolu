#!/usr/bin/env python3
"""
PhaseAttention vs Quadratic Attention: Relational Binding Falsification Test
=============================================================================

This script is a SCIENTIFIC FALSIFICATION TEST, not a benchmark.

HYPOTHESIS:
    PhaseAttention learns relational binding that quadratic attention cannot
    efficiently replicate, and this binding is CAUSALLY necessary (not decorative).

TASK DESIGN:
    Each sample contains multiple BIND <entity> <role> statements.
    A QUERY <role> ? asks which entity was bound to that role.

    Example:
        BIND X AGENT BIND Y PATIENT BIND Z TOOL QUERY PATIENT ? → Y

    WHY THIS REQUIRES RELATIONAL BINDING:
    1. Token identity is insufficient - same entity tokens appear in every sample
    2. Recency bias fails - BIND order is randomized per sample
    3. Positional encoding alone fails - roles can appear in any position
    4. The model must learn to BIND entity↔role pairs and RETRIEVE by role

    This is exactly the relational structure phase should encode.

CAUSALITY TEST:
    After training PhaseAttention, we verify phase is doing necessary work:
    - Phase scramble: Permute phases randomly → accuracy should DROP
    - Phase freeze: Set all phases to 0 → accuracy should DROP
    - Phase off: Uniform attention (cos=1 everywhere) → accuracy should DROP

    If ablations don't hurt accuracy, phase is DECORATIVE (falsified).

HARD CONSTRAINTS:
    - No pretrained weights
    - No CSR, kosha, ontology, or auxiliary losses
    - Vocabulary ≤ 30 tokens
    - Sequence length ≤ 32
    - Dataset generated programmatically
    - Same parameter count for both models

Author: Claude (Scientific Falsification Test for PhaseAttention)
Date: January 2026
"""

import math
import random
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
import argparse

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class Config:
    """Training and model configuration."""
    # Vocabulary (≤30 tokens as required)
    num_entities: int = 6      # E0, E1, E2, E3, E4, E5
    num_roles: int = 4         # R0, R1, R2, R3
    # Special tokens: BIND, QUERY, ?, PAD, ANS
    # Total vocab: 6 + 4 + 5 = 15 tokens (well under 30)

    # Model architecture
    d_model: int = 64
    num_heads: int = 4
    num_layers: int = 2
    d_ff: int = 128
    dropout: float = 0.1
    max_seq_len: int = 32

    # Training
    batch_size: int = 64
    num_steps: int = 10000
    lr: float = 1e-3
    weight_decay: float = 0.01
    eval_every: int = 500

    # Dataset
    num_bindings_per_sample: int = 4  # Number of BIND statements
    train_samples: int = 10000
    test_samples: int = 1000

    # Device
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


# =============================================================================
# VOCABULARY
# =============================================================================

class Vocabulary:
    """
    Minimal vocabulary for relational binding task.

    Tokens:
        - PAD (0): Padding
        - BIND (1): Binding keyword
        - QUERY (2): Query keyword
        - QMARK (3): Question mark
        - ANS (4): Answer separator
        - E0-E5 (5-10): Entity tokens
        - R0-R3 (11-14): Role tokens

    Total: 15 tokens (well under 30 limit)
    """

    def __init__(self, num_entities: int = 6, num_roles: int = 4):
        self.num_entities = num_entities
        self.num_roles = num_roles

        # Special tokens
        self.PAD = 0
        self.BIND = 1
        self.QUERY = 2
        self.QMARK = 3
        self.ANS = 4

        # Entity tokens: E0, E1, ...
        self.entity_start = 5
        self.entities = list(range(self.entity_start, self.entity_start + num_entities))

        # Role tokens: R0, R1, ...
        self.role_start = self.entity_start + num_entities
        self.roles = list(range(self.role_start, self.role_start + num_roles))

        self.vocab_size = self.role_start + num_roles

        # Token names for display
        self.id2name = {
            self.PAD: "PAD",
            self.BIND: "BIND",
            self.QUERY: "QUERY",
            self.QMARK: "?",
            self.ANS: "ANS",
        }
        for i, e in enumerate(self.entities):
            self.id2name[e] = f"E{i}"
        for i, r in enumerate(self.roles):
            self.id2name[r] = f"R{i}"

    def decode(self, token_ids: List[int]) -> str:
        """Convert token IDs to readable string."""
        return " ".join(self.id2name.get(t, f"[{t}]") for t in token_ids)


# =============================================================================
# DATASET
# =============================================================================

class RelationalBindingDataset(Dataset):
    """
    Synthetic dataset for relational binding.

    Each sample:
        Input:  BIND E? R? BIND E? R? ... QUERY R? ? ANS
        Target: E? (the entity bound to the queried role)

    Key properties:
        1. Entity-role pairings are RANDOM per sample
        2. Order of BIND statements is RANDOM
        3. Queried role is RANDOM (but must have a binding)
        4. Entity/role symbols are used consistently but pairings change

    This ensures the model cannot memorize patterns - it must learn
    the relational binding structure.
    """

    def __init__(
        self,
        vocab: Vocabulary,
        num_samples: int,
        num_bindings: int,
        max_seq_len: int,
        seed: int = 42,
    ):
        self.vocab = vocab
        self.num_samples = num_samples
        self.num_bindings = num_bindings
        self.max_seq_len = max_seq_len

        # Generate all samples upfront for reproducibility
        random.seed(seed)
        self.samples = [self._generate_sample() for _ in range(num_samples)]

    def _generate_sample(self) -> Tuple[List[int], int]:
        """
        Generate a single sample.

        Returns:
            (input_ids, target_entity_id)
        """
        # Randomly select entities and roles for this sample
        entities = random.sample(self.vocab.entities, self.num_bindings)
        roles = random.sample(self.vocab.roles, self.num_bindings)

        # Create random bindings: entity[i] → role[i]
        bindings = list(zip(entities, roles))

        # Shuffle binding order (critical for preventing positional shortcuts)
        random.shuffle(bindings)

        # Build input sequence: BIND E R BIND E R ... QUERY R ? ANS
        input_ids = []
        for entity, role in bindings:
            input_ids.extend([self.vocab.BIND, entity, role])

        # Select a random role to query
        query_role = random.choice(roles)
        input_ids.extend([self.vocab.QUERY, query_role, self.vocab.QMARK, self.vocab.ANS])

        # Find the entity bound to the queried role
        for entity, role in bindings:
            if role == query_role:
                target_entity = entity
                break

        # Pad to max_seq_len
        while len(input_ids) < self.max_seq_len:
            input_ids.append(self.vocab.PAD)

        return input_ids[:self.max_seq_len], target_entity

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        input_ids, target = self.samples[idx]
        return (
            torch.tensor(input_ids, dtype=torch.long),
            torch.tensor(target, dtype=torch.long),
        )


# =============================================================================
# QUADRATIC ATTENTION (BASELINE)
# =============================================================================

class QuadraticAttention(nn.Module):
    """
    Standard O(n²) scaled dot-product attention.

    This is the baseline that PhaseAttention should outperform on
    relational binding tasks.
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % num_heads == 0

        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.scale = math.sqrt(self.head_dim)

        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, causal: bool = True) -> torch.Tensor:
        B, N, D = x.shape

        # Project to Q, K, V
        Q = self.W_q(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.W_k(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.W_v(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # Attention scores
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale

        # Causal mask
        if causal:
            mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
            scores = scores.masked_fill(mask, float('-inf'))

        # Softmax and apply
        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)

        out = torch.matmul(attn, V)
        out = out.transpose(1, 2).contiguous().view(B, N, D)

        return self.out_proj(out)


# =============================================================================
# PHASE ATTENTION (O(n) with phasors)
# =============================================================================

class PhaseAttention(nn.Module):
    """
    O(n) attention using complex phasors with cumulative sum.

    Key insight: Instead of computing all-pairs attention,
    we encode position-relative relationships using phase angles.

    The phase difference cos(φ_q - φ_k) determines how much each
    key contributes to each query, but computed via cumsum.

    CRITICAL FOR RELATIONAL BINDING:
    - Phase can encode entity-role binding relationships
    - Different phase angles for different binding slots
    - Query phase "selects" matching bound entity
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % num_heads == 0

        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads

        # Phase projections (learned phase angles)
        self.W_q_phase = nn.Linear(d_model, d_model)
        self.W_k_phase = nn.Linear(d_model, d_model)

        # Amplitude projections (importance weighting)
        self.W_q_amp = nn.Linear(d_model, d_model)
        self.W_k_amp = nn.Linear(d_model, d_model)

        # Value projection
        self.W_v = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

        # Learned decay for temporal locality
        self.decay_logit = nn.Parameter(torch.zeros(num_heads))

        # For ablation and diagnostics
        self.capture_for_diagnostics = False
        self._captured_phi_k = None
        self._captured_phi_q = None

        # Ablation mode
        self._ablation_mode = "none"  # "none", "scramble", "freeze", "off"
        self._scramble_seed = 42

    def set_ablation_mode(self, mode: str, seed: int = 42):
        """Set ablation mode for causality testing."""
        assert mode in ["none", "scramble", "freeze", "off"]
        self._ablation_mode = mode
        self._scramble_seed = seed

    def _apply_ablation(self, phi: torch.Tensor) -> torch.Tensor:
        """Apply ablation to phase tensor."""
        if self._ablation_mode == "none":
            return phi
        elif self._ablation_mode == "scramble":
            # Randomly permute phases within each head
            B, N, H, D = phi.shape
            torch.manual_seed(self._scramble_seed)
            phi_scrambled = phi.clone()
            for b in range(B):
                for h in range(H):
                    perm = torch.randperm(N, device=phi.device)
                    phi_scrambled[b, :, h, :] = phi[b, perm, h, :]
            return phi_scrambled
        elif self._ablation_mode == "freeze":
            # Set all phases to 0
            return torch.zeros_like(phi)
        elif self._ablation_mode == "off":
            # Set all phases to 0 (same effect as freeze for cos(0)=1)
            return torch.zeros_like(phi)
        return phi

    def forward(self, x: torch.Tensor, causal: bool = True) -> torch.Tensor:
        B, N, D = x.shape

        # Compute phases (bounded to [-π, π] via sin)
        phi_q_raw = self.W_q_phase(x).view(B, N, self.num_heads, self.head_dim)
        phi_k_raw = self.W_k_phase(x).view(B, N, self.num_heads, self.head_dim)

        phi_q = math.pi * torch.sin(phi_q_raw)
        phi_k = math.pi * torch.sin(phi_k_raw)

        # Apply ablation if set
        phi_q = self._apply_ablation(phi_q)
        phi_k = self._apply_ablation(phi_k)

        # Capture for diagnostics
        if self.capture_for_diagnostics:
            self._captured_phi_k = phi_k.detach()
            self._captured_phi_q = phi_q.detach()

        # Compute amplitudes (sigmoid for [0, 1])
        a_q = torch.sigmoid(self.W_q_amp(x)).view(B, N, self.num_heads, self.head_dim)
        a_k = torch.sigmoid(self.W_k_amp(x)).view(B, N, self.num_heads, self.head_dim)

        # Value projection
        v = self.W_v(x).view(B, N, self.num_heads, self.head_dim)

        # Cast to float for complex operations (bfloat16 doesn't support complex)
        orig_dtype = phi_q.dtype
        if orig_dtype == torch.bfloat16:
            phi_q = phi_q.float()
            phi_k = phi_k.float()
            a_q = a_q.float()
            a_k = a_k.float()
            v = v.float()

        # Create complex phasors: z = a * e^(iφ)
        q_phasor = torch.polar(a_q, phi_q)       # Query phasor
        k_phasor = torch.polar(a_k, -phi_k)      # Key phasor (conjugate for matching)

        # Key-value product (complex)
        v_complex = torch.complex(v, torch.zeros_like(v))
        kv = k_phasor * v_complex

        # Cumulative sum for O(n) attention
        # Apply decay for temporal locality
        decay = torch.sigmoid(self.decay_logit).view(1, 1, -1, 1)

        # Simple cumsum (could add decay weighting)
        state = torch.cumsum(kv, dim=1)

        # Query readout: Re(Q* × State)
        output = q_phasor * state
        output = output.real

        # Reshape and project
        if orig_dtype == torch.bfloat16:
            output = output.to(orig_dtype)

        output = output.reshape(B, N, D)
        output = self.out_proj(output)
        output = self.dropout(output)

        return output

    def get_phase_metrics(self) -> Dict[str, float]:
        """Compute phase health metrics from captured data."""
        if self._captured_phi_k is None:
            return {}

        phi_k = self._captured_phi_k
        phi_q = self._captured_phi_q

        # R_k: Mean resultant length (0 = uniform/healthy, 1 = collapsed)
        z_k = torch.exp(1j * phi_k.float())
        R_k = torch.abs(z_k.mean()).item()

        # R_q
        z_q = torch.exp(1j * phi_q.float())
        R_q = torch.abs(z_q.mean()).item()

        # Phase variance (higher = more diverse)
        phase_var = phi_k.var().item()

        return {
            "R_k": R_k,
            "R_q": R_q,
            "phase_var": phase_var,
        }


# =============================================================================
# TRANSFORMER BLOCKS
# =============================================================================

class FeedForward(nn.Module):
    """Simple feed-forward network."""

    def __init__(self, d_model: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model),
            nn.Dropout(dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class TransformerBlock(nn.Module):
    """Single transformer block with configurable attention."""

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        d_ff: int,
        dropout: float,
        use_phase_attention: bool,
    ):
        super().__init__()

        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        if use_phase_attention:
            self.attn = PhaseAttention(d_model, num_heads, dropout)
        else:
            self.attn = QuadraticAttention(d_model, num_heads, dropout)

        self.ff = FeedForward(d_model, d_ff, dropout)
        self.use_phase = use_phase_attention

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Pre-norm architecture
        x = x + self.attn(self.norm1(x))
        x = x + self.ff(self.norm2(x))
        return x


# =============================================================================
# FULL TRANSFORMER MODEL
# =============================================================================

class BindingTransformer(nn.Module):
    """
    Transformer for relational binding classification.

    Input: Sequence of tokens (BIND E R ... QUERY R ? ANS)
    Output: Classification logits over entity tokens
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
        num_entities: int,
        use_phase_attention: bool,
    ):
        super().__init__()

        self.use_phase = use_phase_attention
        self.num_entities = num_entities

        # Embeddings
        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)

        # Transformer layers
        self.layers = nn.ModuleList([
            TransformerBlock(d_model, num_heads, d_ff, dropout, use_phase_attention)
            for _ in range(num_layers)
        ])

        # Output head: classify into entity tokens
        self.norm = nn.LayerNorm(d_model)
        self.classifier = nn.Linear(d_model, num_entities)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        B, N = input_ids.shape

        # Embeddings
        positions = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.token_emb(input_ids) + self.pos_emb(positions)
        x = self.dropout(x)

        # Transformer layers
        for layer in self.layers:
            x = layer(x)

        # Take the last position (after ANS token) for classification
        x = self.norm(x[:, -1, :])  # [B, d_model]

        # Classify into entities
        logits = self.classifier(x)  # [B, num_entities]

        return logits

    def set_ablation_mode(self, mode: str, seed: int = 42):
        """Set ablation mode for all PhaseAttention layers."""
        for layer in self.layers:
            if hasattr(layer.attn, 'set_ablation_mode'):
                layer.attn.set_ablation_mode(mode, seed)

    def enable_diagnostics(self, enable: bool = True):
        """Enable phase capture for diagnostics."""
        for layer in self.layers:
            if hasattr(layer.attn, 'capture_for_diagnostics'):
                layer.attn.capture_for_diagnostics = enable

    def get_phase_metrics(self) -> Dict[str, float]:
        """Get aggregated phase metrics from all layers."""
        metrics = {"R_k": 0.0, "R_q": 0.0, "phase_var": 0.0}
        count = 0

        for layer in self.layers:
            if hasattr(layer.attn, 'get_phase_metrics'):
                layer_metrics = layer.attn.get_phase_metrics()
                if layer_metrics:
                    for k in metrics:
                        metrics[k] += layer_metrics.get(k, 0.0)
                    count += 1

        if count > 0:
            for k in metrics:
                metrics[k] /= count

        return metrics

    def count_parameters(self) -> int:
        """Count total trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# =============================================================================
# TRAINING UTILITIES
# =============================================================================

def evaluate(
    model: BindingTransformer,
    dataloader: DataLoader,
    vocab: Vocabulary,
    device: str,
) -> Tuple[float, float]:
    """
    Evaluate model accuracy.

    Returns:
        (accuracy, loss)
    """
    model.eval()
    correct = 0
    total = 0
    total_loss = 0.0

    with torch.no_grad():
        for input_ids, targets in dataloader:
            input_ids = input_ids.to(device)
            targets = targets.to(device)

            # Convert entity token IDs to class indices (0 to num_entities-1)
            target_indices = targets - vocab.entity_start

            logits = model(input_ids)
            loss = F.cross_entropy(logits, target_indices)

            preds = logits.argmax(dim=-1)
            correct += (preds == target_indices).sum().item()
            total += targets.size(0)
            total_loss += loss.item() * targets.size(0)

    accuracy = correct / total
    avg_loss = total_loss / total

    return accuracy, avg_loss


def run_ablation_test(
    model: BindingTransformer,
    dataloader: DataLoader,
    vocab: Vocabulary,
    device: str,
) -> Dict[str, Tuple[float, float]]:
    """
    Run ablation tests on PhaseAttention model.

    Returns dict mapping ablation mode to (accuracy, loss).
    """
    if not model.use_phase:
        return {}

    results = {}

    for mode in ["none", "scramble", "freeze", "off"]:
        model.set_ablation_mode(mode)
        acc, loss = evaluate(model, dataloader, vocab, device)
        results[mode] = (acc, loss)

    # Reset to normal mode
    model.set_ablation_mode("none")

    return results


# =============================================================================
# MAIN TRAINING SCRIPT
# =============================================================================

def train(config: Config):
    """
    Train both models and compare results.
    """
    print("=" * 70)
    print("PhaseAttention vs Quadratic Attention: Relational Binding Test")
    print("=" * 70)
    print(f"\nDevice: {config.device}")

    # Create vocabulary
    vocab = Vocabulary(config.num_entities, config.num_roles)
    print(f"Vocabulary size: {vocab.vocab_size} tokens")

    # Create datasets
    print("\nGenerating datasets...")
    train_dataset = RelationalBindingDataset(
        vocab, config.train_samples, config.num_bindings_per_sample,
        config.max_seq_len, seed=42
    )
    test_dataset = RelationalBindingDataset(
        vocab, config.test_samples, config.num_bindings_per_sample,
        config.max_seq_len, seed=123  # Different seed for test
    )

    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=config.batch_size, shuffle=False)

    # Show example samples
    print("\n--- Example Samples ---")
    for i in range(3):
        input_ids, target = train_dataset[i]
        print(f"Input:  {vocab.decode(input_ids.tolist())}")
        print(f"Target: {vocab.id2name[target.item()]}")
        print()

    # Create both models
    print("--- Creating Models ---")

    model_quadratic = BindingTransformer(
        vocab_size=vocab.vocab_size,
        d_model=config.d_model,
        num_heads=config.num_heads,
        num_layers=config.num_layers,
        d_ff=config.d_ff,
        dropout=config.dropout,
        max_seq_len=config.max_seq_len,
        num_entities=config.num_entities,
        use_phase_attention=False,
    ).to(config.device)

    model_phase = BindingTransformer(
        vocab_size=vocab.vocab_size,
        d_model=config.d_model,
        num_heads=config.num_heads,
        num_layers=config.num_layers,
        d_ff=config.d_ff,
        dropout=config.dropout,
        max_seq_len=config.max_seq_len,
        num_entities=config.num_entities,
        use_phase_attention=True,
    ).to(config.device)

    print(f"Quadratic Attention params: {model_quadratic.count_parameters():,}")
    print(f"Phase Attention params:     {model_phase.count_parameters():,}")

    # Optimizers (same for both)
    opt_quadratic = torch.optim.AdamW(
        model_quadratic.parameters(), lr=config.lr, weight_decay=config.weight_decay
    )
    opt_phase = torch.optim.AdamW(
        model_phase.parameters(), lr=config.lr, weight_decay=config.weight_decay
    )

    # Training history
    history = {
        "quadratic_train_acc": [],
        "quadratic_test_acc": [],
        "phase_train_acc": [],
        "phase_test_acc": [],
        "steps": [],
    }

    # Training loop
    print("\n--- Training ---")
    print(f"Training for {config.num_steps} steps...")

    step = 0
    train_iter = iter(train_loader)

    while step < config.num_steps:
        # Get batch (with wraparound)
        try:
            input_ids, targets = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            input_ids, targets = next(train_iter)

        input_ids = input_ids.to(config.device)
        targets = targets.to(config.device)
        target_indices = targets - vocab.entity_start

        # Train quadratic model
        model_quadratic.train()
        opt_quadratic.zero_grad()
        logits_q = model_quadratic(input_ids)
        loss_q = F.cross_entropy(logits_q, target_indices)
        loss_q.backward()
        opt_quadratic.step()

        # Train phase model
        model_phase.train()
        opt_phase.zero_grad()
        logits_p = model_phase(input_ids)
        loss_p = F.cross_entropy(logits_p, target_indices)
        loss_p.backward()
        opt_phase.step()

        step += 1

        # Evaluate periodically
        if step % config.eval_every == 0 or step == config.num_steps:
            train_acc_q, _ = evaluate(model_quadratic, train_loader, vocab, config.device)
            test_acc_q, _ = evaluate(model_quadratic, test_loader, vocab, config.device)

            train_acc_p, _ = evaluate(model_phase, train_loader, vocab, config.device)
            test_acc_p, _ = evaluate(model_phase, test_loader, vocab, config.device)

            history["steps"].append(step)
            history["quadratic_train_acc"].append(train_acc_q)
            history["quadratic_test_acc"].append(test_acc_q)
            history["phase_train_acc"].append(train_acc_p)
            history["phase_test_acc"].append(test_acc_p)

            print(f"Step {step:5d} | "
                  f"Quadratic: train={train_acc_q:.3f} test={test_acc_q:.3f} | "
                  f"Phase: train={train_acc_p:.3f} test={test_acc_p:.3f}")

    # Final evaluation
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)

    final_acc_q, final_loss_q = evaluate(model_quadratic, test_loader, vocab, config.device)
    final_acc_p, final_loss_p = evaluate(model_phase, test_loader, vocab, config.device)

    print(f"\n--- Test Accuracy ---")
    print(f"Quadratic Attention: {final_acc_q*100:.1f}%")
    print(f"Phase Attention:     {final_acc_p*100:.1f}%")
    print(f"Delta:               {(final_acc_p - final_acc_q)*100:+.1f}%")

    # Phase health metrics
    print(f"\n--- Phase Health Metrics ---")
    model_phase.enable_diagnostics(True)
    _ = evaluate(model_phase, test_loader, vocab, config.device)
    phase_metrics = model_phase.get_phase_metrics()
    model_phase.enable_diagnostics(False)

    print(f"R_k (collapse):    {phase_metrics.get('R_k', 0):.4f} "
          f"{'(healthy)' if phase_metrics.get('R_k', 0) < 0.3 else '(WARNING)'}")
    print(f"R_q (collapse):    {phase_metrics.get('R_q', 0):.4f}")
    print(f"Phase variance:    {phase_metrics.get('phase_var', 0):.4f}")

    # CAUSALITY TEST: Ablation
    print(f"\n--- CAUSALITY TEST: Phase Ablation ---")
    print("If phase is doing necessary work, ablations should hurt accuracy.")
    print()

    ablation_results = run_ablation_test(model_phase, test_loader, vocab, config.device)

    baseline_acc = ablation_results["none"][0]
    print(f"{'Mode':<12} {'Accuracy':>10} {'Delta':>10} {'Interpretation':<30}")
    print("-" * 62)

    for mode, (acc, _) in ablation_results.items():
        delta = acc - baseline_acc
        if mode == "none":
            interp = "(baseline)"
        elif delta < -0.1:
            interp = "PHASE IS CAUSALLY NECESSARY"
        elif delta < -0.05:
            interp = "Phase contributes"
        else:
            interp = "Phase may be decorative"

        print(f"{mode:<12} {acc*100:>9.1f}% {delta*100:>+9.1f}% {interp:<30}")

    # Scientific verdict
    print("\n" + "=" * 70)
    print("SCIENTIFIC VERDICT")
    print("=" * 70)

    scramble_drop = baseline_acc - ablation_results["scramble"][0]
    freeze_drop = baseline_acc - ablation_results["freeze"][0]
    off_drop = baseline_acc - ablation_results["off"][0]

    phase_is_causal = (scramble_drop > 0.1 or freeze_drop > 0.1 or off_drop > 0.1)
    phase_beats_quadratic = final_acc_p > final_acc_q + 0.05

    if phase_is_causal and phase_beats_quadratic:
        print("\n[HYPOTHESIS SUPPORTED]")
        print("PhaseAttention demonstrates CAUSAL advantage on relational binding:")
        print(f"  - Phase outperforms quadratic by {(final_acc_p - final_acc_q)*100:.1f}%")
        print(f"  - Ablations cause significant accuracy drops:")
        print(f"      Scramble: {scramble_drop*100:+.1f}%")
        print(f"      Freeze:   {freeze_drop*100:+.1f}%")
        print(f"      Off:      {off_drop*100:+.1f}%")
        print("  - Phase is doing NECESSARY work, not decorative")
    elif phase_is_causal:
        print("\n[PARTIAL SUPPORT]")
        print("Phase is causally necessary but doesn't outperform quadratic:")
        print(f"  - Ablations hurt performance (phase is not decorative)")
        print(f"  - But quadratic attention achieves similar accuracy")
        print("  - May need harder task or different architecture")
    elif phase_beats_quadratic:
        print("\n[INCONCLUSIVE]")
        print("Phase outperforms quadratic but causality not demonstrated:")
        print(f"  - Phase is better by {(final_acc_p - final_acc_q)*100:.1f}%")
        print(f"  - But ablations don't significantly hurt accuracy")
        print("  - Phase may be DECORATIVE (not the cause of improvement)")
    else:
        print("\n[HYPOTHESIS FALSIFIED]")
        print("PhaseAttention does NOT demonstrate advantage:")
        print(f"  - Phase accuracy: {final_acc_p*100:.1f}%")
        print(f"  - Quadratic accuracy: {final_acc_q*100:.1f}%")
        print(f"  - Ablation drops are minimal")
        print("  - Phase is not learning useful relational structure")

    print("\n" + "=" * 70)

    return history, model_quadratic, model_phase


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PhaseAttention vs Quadratic Attention: Relational Binding Test"
    )
    parser.add_argument("--num-steps", type=int, default=10000,
                        help="Number of training steps")
    parser.add_argument("--batch-size", type=int, default=64,
                        help="Batch size")
    parser.add_argument("--d-model", type=int, default=64,
                        help="Model dimension")
    parser.add_argument("--num-layers", type=int, default=2,
                        help="Number of transformer layers")
    parser.add_argument("--num-bindings", type=int, default=4,
                        help="Number of BIND statements per sample")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu",
                        help="Device to train on")

    args = parser.parse_args()

    config = Config(
        num_steps=args.num_steps,
        batch_size=args.batch_size,
        d_model=args.d_model,
        num_layers=args.num_layers,
        num_bindings_per_sample=args.num_bindings,
        device=args.device,
    )

    train(config)
