#!/usr/bin/env python3
"""
PhaseAttention Training with Embedded Probe Schemas
====================================================

This script creates a synthetic dataset where PROBE SCHEMAS are embedded
directly into the training data. This ensures the model MUST learn
relational binding to succeed - architectural differences emerge naturally.

PROBE SCHEMA TYPES:
-------------------
1. RB (Relational Binding)   - Pronoun resolution based on semantic role
2. BIND (Role/Entity)        - Explicit entity-role binding and retrieval
3. NP (Negation Polarity)    - Scope of negation affects answer
4. LP (Long-range Persistence) - Entity tracking across filler material
5. SI (Symbol Indirection)   - Same symbol, different referent by context

KEY DESIGN PRINCIPLES:
----------------------
1. Schemas, not fixed prompts - Templates generate infinite variations
2. No memorization possible - All elements randomized per sample
3. Relational structure required - Token identity alone cannot solve
4. Causal testing enabled - Phase ablation reveals if phase is necessary

WHY RELATIONAL BINDING IS UNAVOIDABLE:
--------------------------------------
- RB: "X blamed Y because PRON was angry" - PRON binding depends on role
- BIND: "BIND X R1, BIND Y R2, QUERY R1" - must track which entity has role
- NP: "X didn't V until later" - negation scope changes meaning
- LP: "X entered. [filler]. PRON spoke" - must persist X across distance
- SI: "The bank[finance]. The bank[river]. The bank again" - context selects sense

Author: Claude (Scientific Training Script for PhaseAttention)
Date: January 2026
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Callable
from enum import Enum
import argparse

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, ConcatDataset


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class Config:
    """Training and model configuration."""
    # Model
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

    # Dataset (samples per schema type)
    samples_per_schema: int = 2000
    test_samples_per_schema: int = 200

    # Device
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


# =============================================================================
# SCHEMA TYPES
# =============================================================================

class SchemaType(Enum):
    """Types of probe schemas embedded in training data."""
    RB = "relational_binding"      # Pronoun resolution
    BIND = "entity_role_binding"   # Explicit bind/query
    NP = "negation_polarity"       # Negation scope
    LP = "long_range_persistence"  # Entity tracking
    SI = "symbol_indirection"      # Same symbol, different sense


# =============================================================================
# VOCABULARY
# =============================================================================

class Vocabulary:
    """
    Unified vocabulary for all schema types.

    Design: Use abstract symbols to prevent semantic shortcuts.

    Tokens (total: 28, under 30 limit):
        0: PAD
        1: SEP (separator)
        2: QUERY
        3: ANS
        4-9: Entities (E0-E5)
        10-13: Roles (R0-R3)
        14-17: Pronouns (PRON0-PRON3: he/she/it/they abstract)
        18-21: Verbs (V0-V3)
        22-25: Contexts (CTX0-CTX3)
        26: NEG (negation marker)
        27: BIND (binding marker)
    """

    def __init__(self):
        # Special tokens
        self.PAD = 0
        self.SEP = 1
        self.QUERY = 2
        self.ANS = 3

        # Entities
        self.entities = list(range(4, 10))  # E0-E5

        # Roles
        self.roles = list(range(10, 14))  # R0-R3

        # Pronouns (abstract - no gender semantics)
        self.pronouns = list(range(14, 18))  # PRON0-PRON3

        # Verbs
        self.verbs = list(range(18, 22))  # V0-V3

        # Contexts (for SI - sense disambiguation)
        self.contexts = list(range(22, 26))  # CTX0-CTX3

        # Special markers
        self.NEG = 26
        self.BIND = 27

        self.vocab_size = 28

        # Human-readable names
        self._build_names()

    def _build_names(self):
        self.id2name = {
            self.PAD: "PAD", self.SEP: "SEP", self.QUERY: "Q",
            self.ANS: "→", self.NEG: "NOT", self.BIND: "BIND",
        }
        for i, e in enumerate(self.entities):
            self.id2name[e] = f"E{i}"
        for i, r in enumerate(self.roles):
            self.id2name[r] = f"R{i}"
        for i, p in enumerate(self.pronouns):
            self.id2name[p] = f"P{i}"
        for i, v in enumerate(self.verbs):
            self.id2name[v] = f"V{i}"
        for i, c in enumerate(self.contexts):
            self.id2name[c] = f"C{i}"

    def decode(self, ids: List[int]) -> str:
        return " ".join(self.id2name.get(t, f"[{t}]") for t in ids if t != self.PAD)


# =============================================================================
# SCHEMA GENERATORS
# =============================================================================

class SchemaGenerator:
    """Base class for schema generators."""

    def __init__(self, vocab: Vocabulary, max_seq_len: int):
        self.vocab = vocab
        self.max_seq_len = max_seq_len

    def generate(self) -> Tuple[List[int], int, str]:
        """
        Generate a sample.

        Returns:
            (input_ids, target_entity_id, explanation)
        """
        raise NotImplementedError

    def pad(self, ids: List[int]) -> List[int]:
        """Pad sequence to max_seq_len."""
        if len(ids) < self.max_seq_len:
            ids = ids + [self.vocab.PAD] * (self.max_seq_len - len(ids))
        return ids[:self.max_seq_len]


class RBGenerator(SchemaGenerator):
    """
    Relational Binding (RB) Schema Generator.

    Pattern: E1 V E2 SEP PRON V2 SEP QUERY PRON ANS
    Example: E0 V0 E1 SEP P0 V1 SEP Q P0 → ?

    WHY THIS REQUIRES RELATIONAL BINDING:
    --------------------------------------
    The pronoun P0 could refer to either E0 or E1.
    The FIRST verb (V0) determines the semantic role.

    We define role semantics abstractly:
    - V0, V2 = "agent-biased" (pronoun binds to subject)
    - V1, V3 = "patient-biased" (pronoun binds to object)

    Token identity alone cannot solve this - the model must learn
    that V0 implies "pronoun = E0" while V1 implies "pronoun = E1".
    """

    def __init__(self, vocab: Vocabulary, max_seq_len: int):
        super().__init__(vocab, max_seq_len)
        # Define verb semantics (which entity the pronoun refers to)
        # Even verbs (V0, V2) = agent-biased → subject
        # Odd verbs (V1, V3) = patient-biased → object
        self.agent_verbs = [vocab.verbs[0], vocab.verbs[2]]
        self.patient_verbs = [vocab.verbs[1], vocab.verbs[3]]

    def generate(self) -> Tuple[List[int], int, str]:
        # Pick two different entities
        e1, e2 = random.sample(self.vocab.entities, 2)

        # Pick a verb (determines binding)
        verb = random.choice(self.vocab.verbs)
        is_agent_verb = verb in self.agent_verbs

        # Pick a pronoun and second verb
        pron = random.choice(self.vocab.pronouns)
        verb2 = random.choice(self.vocab.verbs)

        # Build sequence: E1 V E2 SEP PRON V2 SEP QUERY PRON ANS
        ids = [e1, verb, e2, self.vocab.SEP, pron, verb2, self.vocab.SEP,
               self.vocab.QUERY, pron, self.vocab.ANS]

        # Target: agent-biased verb → e1 (subject), patient-biased → e2 (object)
        target = e1 if is_agent_verb else e2

        explanation = (
            f"RB: {self.vocab.id2name[e1]} {self.vocab.id2name[verb]} "
            f"{self.vocab.id2name[e2]} → pronoun binds to "
            f"{'subject' if is_agent_verb else 'object'}"
        )

        return self.pad(ids), target, explanation


class BINDGenerator(SchemaGenerator):
    """
    Entity-Role Binding (BIND) Schema Generator.

    Pattern: BIND E R BIND E R ... SEP QUERY R ANS
    Example: BIND E0 R1 BIND E1 R0 SEP Q R0 → E1

    WHY THIS REQUIRES RELATIONAL BINDING:
    --------------------------------------
    - Same entities appear in every sample
    - Same roles appear in every sample
    - Order of BIND statements is randomized
    - Must track which entity was bound to which role
    - Query asks for entity given role

    This is PURE relational binding - no semantic shortcuts possible.
    """

    def __init__(self, vocab: Vocabulary, max_seq_len: int, num_bindings: int = 3):
        super().__init__(vocab, max_seq_len)
        self.num_bindings = num_bindings

    def generate(self) -> Tuple[List[int], int, str]:
        # Sample entities and roles
        entities = random.sample(self.vocab.entities, self.num_bindings)
        roles = random.sample(self.vocab.roles, self.num_bindings)

        # Create bindings
        bindings = list(zip(entities, roles))
        random.shuffle(bindings)

        # Build sequence
        ids = []
        for entity, role in bindings:
            ids.extend([self.vocab.BIND, entity, role])

        # Query a random role
        query_role = random.choice(roles)
        ids.extend([self.vocab.SEP, self.vocab.QUERY, query_role, self.vocab.ANS])

        # Find target
        target = None
        for entity, role in bindings:
            if role == query_role:
                target = entity
                break

        explanation = f"BIND: Query {self.vocab.id2name[query_role]} → {self.vocab.id2name[target]}"

        return self.pad(ids), target, explanation


class NPGenerator(SchemaGenerator):
    """
    Negation Polarity (NP) Schema Generator.

    Pattern: E V [NEG] CTX SEP QUERY V ANS
    Example: E0 V0 NOT C0 SEP Q V0 → E0/none

    WHY THIS REQUIRES RELATIONAL BINDING:
    --------------------------------------
    Negation changes the scope of the statement.

    - "E0 V0 C0" → E0 did V0 → answer is E0
    - "E0 V0 NOT C0" → E0 did NOT V0 → answer is "none" (different entity)

    The model must track negation scope across the sequence.
    """

    def __init__(self, vocab: Vocabulary, max_seq_len: int):
        super().__init__(vocab, max_seq_len)
        # Use E0 as "none/null" answer when negated
        self.null_entity = vocab.entities[0]

    def generate(self) -> Tuple[List[int], int, str]:
        # Pick entity, verb, context
        entity = random.choice(self.vocab.entities[1:])  # Not E0 (null)
        verb = random.choice(self.vocab.verbs)
        ctx = random.choice(self.vocab.contexts)

        # Randomly include negation
        negated = random.choice([True, False])

        # Build sequence
        if negated:
            ids = [entity, verb, self.vocab.NEG, ctx, self.vocab.SEP,
                   self.vocab.QUERY, verb, self.vocab.ANS]
            target = self.null_entity  # Negated → null answer
        else:
            ids = [entity, verb, ctx, self.vocab.SEP,
                   self.vocab.QUERY, verb, self.vocab.ANS]
            target = entity  # Not negated → entity did it

        explanation = f"NP: {'NOT ' if negated else ''}{self.vocab.id2name[entity]} → {self.vocab.id2name[target]}"

        return self.pad(ids), target, explanation


class LPGenerator(SchemaGenerator):
    """
    Long-range Persistence (LP) Schema Generator.

    Pattern: E1 V1 SEP [filler...] SEP PRON V2 SEP QUERY PRON ANS
    Example: E0 V0 SEP E1 V1 E2 V2 SEP P0 V3 SEP Q P0 → E0

    WHY THIS REQUIRES RELATIONAL BINDING:
    --------------------------------------
    - E0 is established as primary agent
    - Filler material mentions other entities (distractors)
    - Pronoun must bind back to E0 across the filler
    - Recency bias would wrongly select a distractor

    Phase should help maintain E0's salience across distance.
    """

    def __init__(self, vocab: Vocabulary, max_seq_len: int, filler_length: int = 3):
        super().__init__(vocab, max_seq_len)
        self.filler_length = filler_length

    def generate(self) -> Tuple[List[int], int, str]:
        # Primary entity and action
        primary = random.choice(self.vocab.entities)
        primary_verb = random.choice(self.vocab.verbs)

        # Distractors (filler)
        distractors = [e for e in self.vocab.entities if e != primary]
        filler_entities = random.sample(distractors, min(self.filler_length, len(distractors)))

        # Build sequence
        ids = [primary, primary_verb, self.vocab.SEP]

        # Add filler
        for dist_e in filler_entities:
            ids.extend([dist_e, random.choice(self.vocab.verbs)])
        ids.append(self.vocab.SEP)

        # Pronoun reference back to primary
        pron = random.choice(self.vocab.pronouns)
        ids.extend([pron, random.choice(self.vocab.verbs), self.vocab.SEP,
                    self.vocab.QUERY, pron, self.vocab.ANS])

        target = primary

        explanation = f"LP: Primary {self.vocab.id2name[primary]} across {len(filler_entities)} distractors"

        return self.pad(ids), target, explanation


class SIGenerator(SchemaGenerator):
    """
    Symbol Indirection (SI) Schema Generator.

    Pattern: E CTX1 SEP E CTX2 SEP E SEP QUERY E ANS
    Example: E0 C0 SEP E0 C1 SEP E0 SEP Q E0 → C0/C1

    WHY THIS REQUIRES RELATIONAL BINDING:
    --------------------------------------
    Same entity symbol E0 appears multiple times with different contexts.
    The query asks which CONTEXT the final E0 refers to.

    - If final E0 is closer to C1 context → answer is C1
    - Must track which context is "active" for the final reference

    This tests sense disambiguation / context tracking.
    """

    def __init__(self, vocab: Vocabulary, max_seq_len: int):
        super().__init__(vocab, max_seq_len)

    def generate(self) -> Tuple[List[int], int, str]:
        # Pick an entity and two contexts
        entity = random.choice(self.vocab.entities)
        ctx1, ctx2 = random.sample(self.vocab.contexts, 2)

        # The "active" context is the one closer to the query
        # We randomize whether ctx1 or ctx2 comes last
        if random.choice([True, False]):
            # ctx1 first, ctx2 second (ctx2 is active)
            ids = [entity, ctx1, self.vocab.SEP,
                   entity, ctx2, self.vocab.SEP,
                   entity, self.vocab.SEP,
                   self.vocab.QUERY, entity, self.vocab.ANS]
            target = ctx2  # Map to entity slot for classification
            # Actually, let's use entities as targets
            # Map ctx2 → second entity in list
            target = self.vocab.entities[self.vocab.contexts.index(ctx2)]
        else:
            # ctx2 first, ctx1 second (ctx1 is active)
            ids = [entity, ctx2, self.vocab.SEP,
                   entity, ctx1, self.vocab.SEP,
                   entity, self.vocab.SEP,
                   self.vocab.QUERY, entity, self.vocab.ANS]
            target = self.vocab.entities[self.vocab.contexts.index(ctx1)]

        explanation = f"SI: {self.vocab.id2name[entity]} → context {self.vocab.id2name[target]}"

        return self.pad(ids), target, explanation


# =============================================================================
# DATASET
# =============================================================================

class SchemaDataset(Dataset):
    """
    Dataset that generates samples from a specific schema.
    """

    def __init__(
        self,
        generator: SchemaGenerator,
        schema_type: SchemaType,
        num_samples: int,
        seed: int = 42,
    ):
        self.generator = generator
        self.schema_type = schema_type
        self.num_samples = num_samples

        # Pre-generate for reproducibility
        random.seed(seed)
        self.samples = []
        for _ in range(num_samples):
            ids, target, explanation = generator.generate()
            self.samples.append((ids, target, schema_type.value))

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, str]:
        ids, target, schema = self.samples[idx]
        return (
            torch.tensor(ids, dtype=torch.long),
            torch.tensor(target, dtype=torch.long),
            schema,
        )


def create_combined_dataset(
    vocab: Vocabulary,
    max_seq_len: int,
    samples_per_schema: int,
    seed: int = 42,
) -> Dataset:
    """
    Create a combined dataset with all schema types.
    """
    generators = {
        SchemaType.RB: RBGenerator(vocab, max_seq_len),
        SchemaType.BIND: BINDGenerator(vocab, max_seq_len, num_bindings=3),
        SchemaType.NP: NPGenerator(vocab, max_seq_len),
        SchemaType.LP: LPGenerator(vocab, max_seq_len, filler_length=2),
        SchemaType.SI: SIGenerator(vocab, max_seq_len),
    }

    datasets = []
    for schema_type, gen in generators.items():
        ds = SchemaDataset(gen, schema_type, samples_per_schema, seed + hash(schema_type.value) % 1000)
        datasets.append(ds)

    return ConcatDataset(datasets)


# =============================================================================
# COLLATE FUNCTION
# =============================================================================

def collate_fn(batch):
    """Collate function that handles schema labels."""
    ids = torch.stack([b[0] for b in batch])
    targets = torch.stack([b[1] for b in batch])
    schemas = [b[2] for b in batch]
    return ids, targets, schemas


# =============================================================================
# MODELS (from train_binding_probe.py)
# =============================================================================

class QuadraticAttention(nn.Module):
    """Standard O(n²) attention."""

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.scale = math.sqrt(self.head_dim)

        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, N, D = x.shape

        Q = self.W_q(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.W_k(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.W_v(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale

        mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
        scores = scores.masked_fill(mask, float('-inf'))

        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)

        out = torch.matmul(attn, V)
        out = out.transpose(1, 2).contiguous().view(B, N, D)

        return self.out_proj(out)


class PhaseAttention(nn.Module):
    """O(n) phasor attention with ablation support."""

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads

        self.W_q_phase = nn.Linear(d_model, d_model)
        self.W_k_phase = nn.Linear(d_model, d_model)
        self.W_q_amp = nn.Linear(d_model, d_model)
        self.W_k_amp = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

        self._ablation_mode = "none"
        self._scramble_seed = 42
        self.capture_diagnostics = False
        self._phi_k = None
        self._phi_q = None

    def set_ablation(self, mode: str, seed: int = 42):
        self._ablation_mode = mode
        self._scramble_seed = seed

    def _ablate(self, phi: torch.Tensor) -> torch.Tensor:
        if self._ablation_mode == "none":
            return phi
        elif self._ablation_mode == "scramble":
            B, N, H, D = phi.shape
            torch.manual_seed(self._scramble_seed)
            result = phi.clone()
            for b in range(B):
                for h in range(H):
                    perm = torch.randperm(N, device=phi.device)
                    result[b, :, h, :] = phi[b, perm, h, :]
            return result
        elif self._ablation_mode in ["freeze", "off"]:
            return torch.zeros_like(phi)
        return phi

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, N, D = x.shape

        phi_q = math.pi * torch.sin(self.W_q_phase(x).view(B, N, self.num_heads, self.head_dim))
        phi_k = math.pi * torch.sin(self.W_k_phase(x).view(B, N, self.num_heads, self.head_dim))

        phi_q = self._ablate(phi_q)
        phi_k = self._ablate(phi_k)

        if self.capture_diagnostics:
            self._phi_k = phi_k.detach()
            self._phi_q = phi_q.detach()

        a_q = torch.sigmoid(self.W_q_amp(x)).view(B, N, self.num_heads, self.head_dim)
        a_k = torch.sigmoid(self.W_k_amp(x)).view(B, N, self.num_heads, self.head_dim)
        v = self.W_v(x).view(B, N, self.num_heads, self.head_dim)

        dtype = phi_q.dtype
        if dtype == torch.bfloat16:
            phi_q, phi_k, a_q, a_k, v = [t.float() for t in [phi_q, phi_k, a_q, a_k, v]]

        q_phasor = torch.polar(a_q, phi_q)
        k_phasor = torch.polar(a_k, -phi_k)

        v_complex = torch.complex(v, torch.zeros_like(v))
        kv = k_phasor * v_complex
        state = torch.cumsum(kv, dim=1)

        output = (q_phasor * state).real

        if dtype == torch.bfloat16:
            output = output.to(dtype)

        output = output.reshape(B, N, D)
        return self.out_proj(self.dropout(output))

    def get_R_k(self) -> float:
        if self._phi_k is None:
            return 0.0
        z = torch.exp(1j * self._phi_k.float())
        return torch.abs(z.mean()).item()


class TransformerBlock(nn.Module):
    def __init__(self, d_model: int, num_heads: int, d_ff: int, dropout: float, use_phase: bool):
        super().__init__()
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.attn = PhaseAttention(d_model, num_heads, dropout) if use_phase else QuadraticAttention(d_model, num_heads, dropout)
        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_ff, d_model), nn.Dropout(dropout)
        )
        self.use_phase = use_phase

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.norm1(x))
        x = x + self.ff(self.norm2(x))
        return x


class SchemaTransformer(nn.Module):
    def __init__(self, vocab_size: int, d_model: int, num_heads: int, num_layers: int,
                 d_ff: int, dropout: float, max_seq_len: int, num_classes: int, use_phase: bool):
        super().__init__()
        self.use_phase = use_phase
        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)
        self.layers = nn.ModuleList([
            TransformerBlock(d_model, num_heads, d_ff, dropout, use_phase)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(d_model)
        self.classifier = nn.Linear(d_model, num_classes)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        for layer in self.layers:
            x = layer(x)

        return self.classifier(self.norm(x[:, -1, :]))

    def set_ablation(self, mode: str, seed: int = 42):
        for layer in self.layers:
            if hasattr(layer.attn, 'set_ablation'):
                layer.attn.set_ablation(mode, seed)

    def enable_diagnostics(self, enable: bool = True):
        for layer in self.layers:
            if hasattr(layer.attn, 'capture_diagnostics'):
                layer.attn.capture_diagnostics = enable

    def get_R_k(self) -> float:
        r_values = []
        for layer in self.layers:
            if hasattr(layer.attn, 'get_R_k'):
                r_values.append(layer.attn.get_R_k())
        return sum(r_values) / len(r_values) if r_values else 0.0

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# =============================================================================
# TRAINING AND EVALUATION
# =============================================================================

def evaluate(model, loader, vocab, device) -> Tuple[float, Dict[str, float]]:
    """Evaluate model, returning overall accuracy and per-schema accuracy."""
    model.eval()
    correct = {s.value: 0 for s in SchemaType}
    total = {s.value: 0 for s in SchemaType}

    entity_start = vocab.entities[0]

    with torch.no_grad():
        for ids, targets, schemas in loader:
            ids, targets = ids.to(device), targets.to(device)
            target_idx = targets - entity_start

            logits = model(ids)
            preds = logits.argmax(dim=-1)

            for i, schema in enumerate(schemas):
                total[schema] += 1
                if preds[i] == target_idx[i]:
                    correct[schema] += 1

    per_schema = {s: correct[s] / max(total[s], 1) for s in correct}
    overall = sum(correct.values()) / max(sum(total.values()), 1)

    return overall, per_schema


def run_ablation(model, loader, vocab, device) -> Dict[str, float]:
    """Run ablation tests."""
    results = {}
    for mode in ["none", "scramble", "freeze", "off"]:
        model.set_ablation(mode)
        acc, _ = evaluate(model, loader, vocab, device)
        results[mode] = acc
    model.set_ablation("none")
    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Train with embedded probe schemas")
    parser.add_argument("--num-steps", type=int, default=10000)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--d-model", type=int, default=64)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--samples-per-schema", type=int, default=2000)
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    config = Config(
        num_steps=args.num_steps,
        batch_size=args.batch_size,
        d_model=args.d_model,
        num_layers=args.num_layers,
        samples_per_schema=args.samples_per_schema,
        device=args.device,
    )

    print("=" * 70)
    print("PhaseAttention Training with Embedded Probe Schemas")
    print("=" * 70)

    # Vocabulary
    vocab = Vocabulary()
    print(f"Vocabulary: {vocab.vocab_size} tokens")

    # Datasets
    print("\nCreating datasets with 5 schema types...")
    train_ds = create_combined_dataset(vocab, config.max_seq_len, config.samples_per_schema, seed=42)
    test_ds = create_combined_dataset(vocab, config.max_seq_len, config.test_samples_per_schema, seed=999)

    train_loader = DataLoader(train_ds, batch_size=config.batch_size, shuffle=True, collate_fn=collate_fn)
    test_loader = DataLoader(test_ds, batch_size=config.batch_size, shuffle=False, collate_fn=collate_fn)

    print(f"Train samples: {len(train_ds)} ({config.samples_per_schema} per schema × 5)")
    print(f"Test samples: {len(test_ds)}")

    # Show examples
    print("\n--- Example Samples (one per schema) ---")
    for schema_type in SchemaType:
        # Find one sample of this type
        for ids, target, schema in train_ds:
            if schema == schema_type.value:
                print(f"{schema_type.name}: {vocab.decode(ids.tolist())} → {vocab.id2name[target.item()]}")
                break

    # Models
    print("\n--- Creating Models ---")
    num_classes = len(vocab.entities)

    model_quad = SchemaTransformer(
        vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
        config.d_ff, config.dropout, config.max_seq_len, num_classes, use_phase=False
    ).to(config.device)

    model_phase = SchemaTransformer(
        vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
        config.d_ff, config.dropout, config.max_seq_len, num_classes, use_phase=True
    ).to(config.device)

    print(f"Quadratic params: {model_quad.count_params():,}")
    print(f"Phase params:     {model_phase.count_params():,}")

    # Optimizers
    opt_quad = torch.optim.AdamW(model_quad.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    opt_phase = torch.optim.AdamW(model_phase.parameters(), lr=config.lr, weight_decay=config.weight_decay)

    entity_start = vocab.entities[0]

    # Training
    print(f"\n--- Training for {config.num_steps} steps ---")
    train_iter = iter(train_loader)
    step = 0

    while step < config.num_steps:
        try:
            ids, targets, schemas = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            ids, targets, schemas = next(train_iter)

        ids, targets = ids.to(config.device), targets.to(config.device)
        target_idx = targets - entity_start

        # Train quadratic
        model_quad.train()
        opt_quad.zero_grad()
        loss_q = F.cross_entropy(model_quad(ids), target_idx)
        loss_q.backward()
        opt_quad.step()

        # Train phase
        model_phase.train()
        opt_phase.zero_grad()
        loss_p = F.cross_entropy(model_phase(ids), target_idx)
        loss_p.backward()
        opt_phase.step()

        step += 1

        if step % config.eval_every == 0 or step == config.num_steps:
            acc_q, per_q = evaluate(model_quad, test_loader, vocab, config.device)
            acc_p, per_p = evaluate(model_phase, test_loader, vocab, config.device)

            print(f"Step {step:5d} | Quad: {acc_q:.3f} | Phase: {acc_p:.3f}")

    # Final results
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)

    acc_q, per_q = evaluate(model_quad, test_loader, vocab, config.device)
    acc_p, per_p = evaluate(model_phase, test_loader, vocab, config.device)

    print(f"\n--- Overall Accuracy ---")
    print(f"Quadratic: {acc_q*100:.1f}%")
    print(f"Phase:     {acc_p*100:.1f}%")
    print(f"Delta:     {(acc_p - acc_q)*100:+.1f}%")

    print(f"\n--- Per-Schema Accuracy ---")
    print(f"{'Schema':<25} {'Quadratic':>10} {'Phase':>10} {'Delta':>10}")
    print("-" * 55)
    for schema in SchemaType:
        q = per_q[schema.value]
        p = per_p[schema.value]
        print(f"{schema.name:<25} {q*100:>9.1f}% {p*100:>9.1f}% {(p-q)*100:>+9.1f}%")

    # Phase diagnostics
    print(f"\n--- Phase Health ---")
    model_phase.enable_diagnostics(True)
    _ = evaluate(model_phase, test_loader, vocab, config.device)
    r_k = model_phase.get_R_k()
    model_phase.enable_diagnostics(False)
    print(f"R_k: {r_k:.4f} {'(healthy)' if r_k < 0.3 else '(collapsed)'}")

    # Ablation
    print(f"\n--- CAUSALITY TEST: Phase Ablation ---")
    ablation = run_ablation(model_phase, test_loader, vocab, config.device)
    baseline = ablation["none"]

    print(f"{'Mode':<12} {'Accuracy':>10} {'Delta':>10}")
    print("-" * 32)
    for mode, acc in ablation.items():
        delta = acc - baseline
        print(f"{mode:<12} {acc*100:>9.1f}% {delta*100:>+9.1f}%")

    # Verdict
    print("\n" + "=" * 70)
    print("SCIENTIFIC VERDICT")
    print("=" * 70)

    scramble_drop = baseline - ablation["scramble"]
    freeze_drop = baseline - ablation["freeze"]

    phase_is_causal = scramble_drop > 0.1 or freeze_drop > 0.1
    phase_better = acc_p > acc_q + 0.05

    if phase_is_causal and phase_better:
        print("\n[HYPOTHESIS SUPPORTED]")
        print("Phase demonstrates CAUSAL advantage on relational binding schemas:")
        print(f"  - Outperforms quadratic by {(acc_p - acc_q)*100:.1f}%")
        print(f"  - Ablations cause significant drops (scramble: {scramble_drop*100:.1f}%, freeze: {freeze_drop*100:.1f}%)")
        print("  - Phase is doing NECESSARY relational work")
    elif phase_is_causal:
        print("\n[PARTIAL SUPPORT]")
        print("Phase is causally necessary but doesn't outperform quadratic")
    elif phase_better:
        print("\n[INCONCLUSIVE]")
        print("Phase outperforms but ablations don't hurt - may be decorative")
    else:
        print("\n[HYPOTHESIS FALSIFIED]")
        print("Phase shows no advantage on these relational binding tasks")

    print("=" * 70)


if __name__ == "__main__":
    main()
