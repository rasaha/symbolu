#!/usr/bin/env python3
"""
Hard Diagnostic Probe Dataset for PhaseAttention vs Quadratic Attention
========================================================================

This script implements a HARD generalization benchmark that systematically
removes memorization shortcuts and forces true relational reasoning.

KEY ENHANCEMENTS (v2):
----------------------
1. INCREASED MODEL CAPACITY (d_model=128, num_heads=8, num_layers=4)
   - Phase needs room to encode: role phase, entity amplitude, operation effects
   - Previous 64×2 tested compression, not reasoning

2. OPERATION-CONDITIONED PHASE OFFSETS
   - NEG, PERMUTE, OVERWRITE tokens add learned phase shifts
   - Operations become STATE TRANSFORMATIONS, not passive symbols
   - This is how Phase is hypothesized to work - tests the hypothesis faithfully

3. PURE PERSISTENCE TEST (test_persist)
   - BIND + QUERY only, no NEG/PERMUTE/CONTEXT
   - Chain length 8-12
   - Isolates "memory" from "logic"
   - Shows Phase's clean O(n) advantage

KEY ENHANCEMENT (v3): INVERTED CURRICULUM
-----------------------------------------
Evidence from v2 shows Phase wins ONLY on test_persist (pure memory task).
This reveals: PhaseAttention is NOT a better attention mechanism.
              PhaseAttention IS a better STATE mechanism.

ARCHITECTURAL IMPLICATION:
- Early layers (close to input): Phase-heavy → capture and persist state
- Late layers (close to output): Quadratic-heavy → relational reasoning

The INVERTED CURRICULUM places Phase early for O(n) state persistence,
then Quadratic late for complex relational reasoning over that state.

WHY THE PREVIOUS DATASET FAILED:
---------------------------------
The easy dataset allowed quadratic attention to succeed because:
1. Fixed role tokens → memorize "R0 means slot 0"
2. Fixed entity tokens → memorize "E3 often correct for this pattern"
3. Single schema per sample → pattern match without state tracking
4. Short sequences → attention can "see everything" without state

THIS DATASET FIXES ALL FAILURE MODES:
-------------------------------------
1. HELD-OUT ROLE GENERALIZATION
   - Train: R0-R3, Test: R4-R6
   - Quadratic learns token-specific patterns → fails on new roles
   - Phase encodes role as phase offset → generalizes to new offsets

2. OPEN-WORLD ENTITY GENERALIZATION
   - Train: E0-E7, Test: E8-E15
   - Quadratic memorizes entity-specific outputs → fails on new entities
   - Phase encodes entities as values → generalizes

3. SCHEMA COMPOSITION (no single-pattern matching)
   - BIND_CHAIN: Multiple bindings with overwrites
   - BIND_NEG: Scoped negation of specific bindings
   - CHAIN_DEEP: 4-8 step chains requiring state persistence
   - PERMUTE: Role swapping to test relational invariance

4. LONG-CHAIN STATE PERSISTENCE
   - Train: 3-5 steps, Test: 6-8 steps, Persist: 8-12 steps
   - Tests O(n) state persistence vs attention span limits

EXPECTED OUTCOMES:
------------------
                          Train Acc    Test Acc
Quadratic Attention:      ~95%         <40%
Phase Attention:          ~95%         >70%

Author: Claude (Hard Diagnostic Benchmark for PhaseAttention)
Date: January 2026
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Set
from enum import Enum
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
    # Model - INCREASED CAPACITY for proper reasoning (not just compression)
    # Phase needs room to encode: role phase, entity amplitude, operation effects
    d_model: int = 128
    num_heads: int = 8
    num_layers: int = 4
    d_ff: int = 256  # 2x d_model
    dropout: float = 0.1
    max_seq_len: int = 80  # Longer for persistence test (chain 8-12)

    # Training
    batch_size: int = 64
    num_steps: int = 15000
    lr: float = 1e-3
    weight_decay: float = 0.01
    eval_every: int = 1000

    # Dataset
    train_samples: int = 20000
    test_samples_per_split: int = 1000

    # Hard probe settings
    bind_ratio: float = 0.6          # Ratio of BIND-dominant schemas
    train_chain_length: Tuple[int, int] = (3, 5)
    test_chain_length: Tuple[int, int] = (6, 8)
    persist_chain_length: Tuple[int, int] = (8, 12)  # Pure persistence test

    # Parameter matching
    match_params: bool = False  # If True, adjust to match parameter counts

    # Phase collapse fix
    bounded_phase: bool = True  # V9.9.11: Constrain φ to [-π, π] via π*sin()

    # Device
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


# =============================================================================
# VOCABULARY (48 tokens)
# =============================================================================

class HardVocabulary:
    """
    Extended vocabulary for hard generalization probes.

    Design: Large enough to prevent memorization, structured for splits.

    Tokens (total: 48):
        0: PAD
        1: SEP (separator between operations)
        2: QUERY
        3: ANS (answer marker)
        4: NULL (negated/empty result)
        5: NEG (negation operator)
        6: BIND (binding operator)
        7: PERMUTE (role swap operator)
        8: OVERWRITE (explicit overwrite marker)
        9-24: Entities E0-E15 (train: E0-E7, test: E8-E15)
        25-31: Roles R0-R6 (train: R0-R3, test: R4-R6)
        32-37: Contexts C0-C5 (for SI disambiguation)
        38-43: Verbs V0-V5 (for LP schemas)
        44-47: Filler F0-F3 (distractor tokens)
    """

    def __init__(self):
        # Special tokens
        self.PAD = 0
        self.SEP = 1
        self.QUERY = 2
        self.ANS = 3
        self.NULL = 4
        self.NEG = 5
        self.BIND = 6
        self.PERMUTE = 7
        self.OVERWRITE = 8

        # Entities: 16 total (split for generalization)
        self.entities = list(range(9, 25))  # E0-E15
        self.train_entities = list(range(9, 17))   # E0-E7
        self.test_entities = list(range(17, 25))   # E8-E15

        # Roles: 7 total (split for generalization)
        self.roles = list(range(25, 32))  # R0-R6
        self.train_roles = list(range(25, 29))  # R0-R3
        self.test_roles = list(range(29, 32))   # R4-R6

        # Contexts
        self.contexts = list(range(32, 38))  # C0-C5

        # Verbs
        self.verbs = list(range(38, 44))  # V0-V5

        # Fillers
        self.fillers = list(range(44, 48))  # F0-F3

        self.vocab_size = 48

        # Human-readable names
        self._build_names()

    def _build_names(self):
        self.id2name = {
            self.PAD: "PAD", self.SEP: "|", self.QUERY: "Q",
            self.ANS: "→", self.NULL: "NULL", self.NEG: "NOT",
            self.BIND: "BIND", self.PERMUTE: "PERM", self.OVERWRITE: "OVR",
        }
        for i, e in enumerate(self.entities):
            self.id2name[e] = f"E{i}"
        for i, r in enumerate(self.roles):
            self.id2name[r] = f"R{i}"
        for i, c in enumerate(self.contexts):
            self.id2name[c] = f"C{i}"
        for i, v in enumerate(self.verbs):
            self.id2name[v] = f"V{i}"
        for i, f in enumerate(self.fillers):
            self.id2name[f] = f"F{i}"

    def decode(self, ids: List[int]) -> str:
        return " ".join(self.id2name.get(t, f"[{t}]") for t in ids if t != self.PAD)

    def entity_to_idx(self, entity_id: int) -> int:
        """Convert entity token ID to classification index."""
        return self.entities.index(entity_id)

    def idx_to_entity(self, idx: int) -> int:
        """Convert classification index to entity token ID."""
        return self.entities[idx]


# =============================================================================
# SCHEMA TYPES
# =============================================================================

class SchemaType(Enum):
    """Types of composed schemas."""
    BIND_CHAIN = "bind_chain"           # Multiple bindings with overwrites
    BIND_NEG = "bind_neg"               # Scoped negation
    CHAIN_DEEP = "chain_deep"           # Long chains (4-8 steps)
    SI_BIND = "si_bind"                 # Symbol reinterpretation + binding
    LP_BIND = "lp_bind"                 # Long persistence + binding
    PERMUTE_BIND = "permute_bind"       # Role permutation


# =============================================================================
# SPLIT TYPES
# =============================================================================

class SplitType(Enum):
    """Test split types for separate evaluation."""
    TRAIN = "train"
    TEST_ROLES = "test_roles"           # Held-out roles R4-R6
    TEST_ENTITIES = "test_entities"     # Open-world entities E8-E15
    TEST_BOTH = "test_both"             # Both held-out
    TEST_LONG = "test_long"             # Long chains with train tokens
    TEST_PERSIST = "test_persist"       # Pure persistence: BIND+QUERY only, chain 8-12


# =============================================================================
# STATE TRACKER (for computing correct answers)
# =============================================================================

class BindingState:
    """
    Tracks binding state through composed operations.

    This is the "ground truth" state machine that computes correct answers.
    The model must learn to replicate this state tracking.
    """

    def __init__(self):
        self.bindings: Dict[int, int] = {}  # role -> entity
        self.negated_roles: Set[int] = set()
        self.permutations: List[Tuple[int, int]] = []  # (r1, r2) swaps

    def bind(self, entity: int, role: int):
        """Bind entity to role (overwrites existing)."""
        self.bindings[role] = entity

    def negate(self, role: int):
        """Mark role as negated."""
        self.negated_roles.add(role)

    def permute(self, role1: int, role2: int):
        """Swap bindings of two roles."""
        e1 = self.bindings.get(role1)
        e2 = self.bindings.get(role2)
        if e1 is not None:
            self.bindings[role2] = e1
        elif role2 in self.bindings:
            del self.bindings[role2]
        if e2 is not None:
            self.bindings[role1] = e2
        elif role1 in self.bindings:
            del self.bindings[role1]
        self.permutations.append((role1, role2))

    def query(self, role: int, null_entity: int) -> int:
        """Query binding for role, respecting negation."""
        if role in self.negated_roles:
            return null_entity
        return self.bindings.get(role, null_entity)


# =============================================================================
# SCHEMA GENERATORS
# =============================================================================

class ComposedSchemaGenerator:
    """
    Base class for composed schema generators.

    KEY DESIGN: Each generator produces multi-step sequences that require
    state tracking to solve. Single-pattern matching cannot succeed.
    """

    def __init__(
        self,
        vocab: HardVocabulary,
        max_seq_len: int,
        entities: List[int],
        roles: List[int],
        chain_length: Tuple[int, int] = (3, 5),
    ):
        self.vocab = vocab
        self.max_seq_len = max_seq_len
        self.entities = entities
        self.roles = roles
        self.chain_min, self.chain_max = chain_length

    def generate(self) -> Tuple[List[int], int, str]:
        """Generate (input_ids, target_entity_id, explanation)."""
        raise NotImplementedError

    def pad(self, ids: List[int]) -> List[int]:
        """Pad sequence to max_seq_len."""
        if len(ids) < self.max_seq_len:
            ids = ids + [self.vocab.PAD] * (self.max_seq_len - len(ids))
        return ids[:self.max_seq_len]


class BindChainGenerator(ComposedSchemaGenerator):
    """
    BIND_CHAIN: Multiple bindings with overwrites.

    Pattern: BIND E1 R0 | BIND E2 R1 | BIND E3 R0 | QUERY R0 → E3
                                       ↑ overwrites first binding

    WHY QUADRATIC FAILS:
    - Learns "first BIND with R0 → return that entity"
    - Cannot track that later BIND overwrites earlier one
    - Attention pattern for R0 points to wrong position

    WHY PHASE SUCCEEDS:
    - Cumsum state naturally accumulates (later overwrites earlier)
    - Phase offset for R0 always reflects most recent binding
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Number of bindings (includes overwrites)
        n_bindings = random.randint(self.chain_min, self.chain_max)

        # Select roles (some will be overwritten)
        n_roles = min(len(self.roles), max(2, n_bindings - 1))
        used_roles = random.sample(self.roles, n_roles)

        # Generate bindings (with intentional overwrites)
        bindings_made = []
        for i in range(n_bindings):
            entity = random.choice(self.entities)
            # Sometimes reuse a role (overwrite)
            if i > 0 and random.random() < 0.4:
                role = random.choice(used_roles)  # Reuse → overwrite
            else:
                role = random.choice(used_roles)

            ids.extend([self.vocab.BIND, entity, role, self.vocab.SEP])
            state.bind(entity, role)
            bindings_made.append((entity, role))

        # Query a role that was used
        query_role = random.choice(used_roles)
        ids.extend([self.vocab.QUERY, query_role, self.vocab.ANS])

        target = state.query(query_role, self.vocab.NULL)

        explanation = f"BIND_CHAIN: {len(bindings_made)} bindings, query {self.vocab.id2name[query_role]}"
        return self.pad(ids), target, explanation


class BindNegGenerator(ComposedSchemaGenerator):
    """
    BIND_NEG: Scoped negation of specific bindings.

    Pattern: BIND E1 R0 | BIND E2 R1 | NEG R1 | QUERY R0 → E1
                                                QUERY R1 → NULL

    WHY QUADRATIC FAILS:
    - Cannot track which specific roles are negated
    - NEG applies to R1, not R0 — requires relational scope tracking
    - Pattern matching sees "NEG somewhere" → might negate everything

    WHY PHASE SUCCEEDS:
    - NEG operation modifies phase state for specific role
    - Query phase alignment detects negation state per-role
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Generate base bindings (allow role reuse if chain > available roles)
        max_unique = min(len(self.roles), len(self.entities))
        effective_min = min(self.chain_min, max_unique)
        effective_max = min(self.chain_max, max_unique)
        n_bindings = random.randint(effective_min, effective_max)
        used_roles = random.sample(self.roles, n_bindings)
        used_entities = random.sample(self.entities, n_bindings)

        for entity, role in zip(used_entities, used_roles):
            ids.extend([self.vocab.BIND, entity, role, self.vocab.SEP])
            state.bind(entity, role)

        # Negate some roles (not all)
        n_negations = random.randint(1, max(1, n_bindings - 1))
        negated_roles = random.sample(used_roles, n_negations)

        for role in negated_roles:
            ids.extend([self.vocab.NEG, role, self.vocab.SEP])
            state.negate(role)

        # Query (mix of negated and non-negated)
        query_role = random.choice(used_roles)
        ids.extend([self.vocab.QUERY, query_role, self.vocab.ANS])

        target = state.query(query_role, self.vocab.NULL)

        explanation = f"BIND_NEG: negated {negated_roles}, query {self.vocab.id2name[query_role]}"
        return self.pad(ids), target, explanation


class ChainDeepGenerator(ComposedSchemaGenerator):
    """
    CHAIN_DEEP: Long chains requiring state persistence across many steps.

    Pattern: BIND E1 R0 | BIND E2 R1 | ... | BIND En Rm | ... | QUERY R0 → E1

    WHY QUADRATIC FAILS:
    - At small model sizes, attention span is limited
    - Early bindings get "washed out" by later processing
    - Must attend to position 0-3 from position 30+ (attention decay)

    WHY PHASE SUCCEEDS:
    - Cumsum maintains state with O(n) complexity
    - Early bindings persist in accumulated state
    - No attention span limitation
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Force longer chains for this schema
        n_bindings = random.randint(max(4, self.chain_min), self.chain_max)
        n_roles = min(len(self.roles), n_bindings)
        used_roles = random.sample(self.roles, n_roles)

        # Generate many bindings
        for i in range(n_bindings):
            entity = random.choice(self.entities)
            role = used_roles[i % n_roles]  # Cycle through roles

            ids.extend([self.vocab.BIND, entity, role, self.vocab.SEP])
            state.bind(entity, role)

            # Add filler between some bindings (increases distance)
            if i < n_bindings - 1 and random.random() < 0.3:
                n_filler = random.randint(1, 3)
                for _ in range(n_filler):
                    ids.append(random.choice(self.vocab.fillers))
                ids.append(self.vocab.SEP)

        # Query an early role (tests long-range persistence)
        query_role = used_roles[0]  # Always query first role used
        ids.extend([self.vocab.QUERY, query_role, self.vocab.ANS])

        target = state.query(query_role, self.vocab.NULL)

        explanation = f"CHAIN_DEEP: {n_bindings} steps, query early R0"
        return self.pad(ids), target, explanation


class PermuteBindGenerator(ComposedSchemaGenerator):
    """
    PERMUTE_BIND: Role permutation to test true relational invariance.

    Pattern: BIND E1 R0 | BIND E2 R1 | PERMUTE R0 R1 | QUERY R0 → E2
                                                       QUERY R1 → E1

    WHY QUADRATIC FAILS:
    - Learns token-specific attention patterns
    - "R0" always attends to same relative positions
    - Cannot dynamically swap role meanings

    WHY PHASE SUCCEEDS:
    - Phase encodes role as relational offset, not token identity
    - PERMUTE swaps phase offsets → queries work correctly
    - True relational encoding, not token lookup
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Need at least 2 roles for permutation
        n_bindings = random.randint(max(2, self.chain_min), self.chain_max)
        n_roles = min(len(self.roles), n_bindings)
        used_roles = random.sample(self.roles, max(2, n_roles))
        used_entities = random.sample(self.entities, len(used_roles))

        # Initial bindings
        for entity, role in zip(used_entities, used_roles):
            ids.extend([self.vocab.BIND, entity, role, self.vocab.SEP])
            state.bind(entity, role)

        # Permute two roles
        r1, r2 = random.sample(used_roles, 2)
        ids.extend([self.vocab.PERMUTE, r1, r2, self.vocab.SEP])
        state.permute(r1, r2)

        # Query one of the permuted roles
        query_role = random.choice([r1, r2])
        ids.extend([self.vocab.QUERY, query_role, self.vocab.ANS])

        target = state.query(query_role, self.vocab.NULL)

        explanation = f"PERMUTE: swapped {self.vocab.id2name[r1]}↔{self.vocab.id2name[r2]}, query {self.vocab.id2name[query_role]}"
        return self.pad(ids), target, explanation


class SIBindGenerator(ComposedSchemaGenerator):
    """
    SI_BIND: Symbol reinterpretation + binding.

    Pattern: BIND E1 R0 C0 | BIND E1 R1 C1 | QUERY E1 C0 → R0 (returns entity bound in C0 context)

    Note: Simplified to return entity, querying by context.

    WHY QUADRATIC FAILS:
    - Same entity token E1 appears multiple times
    - Cannot track which context applies to which binding
    - Pattern matching on E1 is ambiguous

    WHY PHASE SUCCEEDS:
    - Context modifies phase, creating distinct states
    - Query with context selects correct binding
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Use same entity in different contexts
        entity = random.choice(self.entities)
        contexts = random.sample(self.vocab.contexts, 2)
        roles = random.sample(self.roles, 2)

        # Bind same entity to different roles in different contexts
        # We'll encode context as part of the role selection
        for ctx, role in zip(contexts, roles):
            ids.extend([self.vocab.BIND, entity, role, ctx, self.vocab.SEP])
            # For simplicity, bind entity to role (context just adds complexity)
            state.bind(entity, role)

        # Add some noise bindings
        for _ in range(random.randint(1, 2)):
            other_entity = random.choice([e for e in self.entities if e != entity])
            other_role = random.choice([r for r in self.roles if r not in roles])
            ids.extend([self.vocab.BIND, other_entity, other_role, self.vocab.SEP])
            state.bind(other_entity, other_role)

        # Query by role (the context was a distractor that complicates patterns)
        query_role = random.choice(roles)
        ids.extend([self.vocab.QUERY, query_role, self.vocab.ANS])

        target = state.query(query_role, self.vocab.NULL)

        explanation = f"SI_BIND: context-varied bindings"
        return self.pad(ids), target, explanation


class LPBindGenerator(ComposedSchemaGenerator):
    """
    LP_BIND: Long persistence + binding.

    Pattern: E1 V0 | F0 F1 F2 | BIND E1 R0 | QUERY R0 → E1

    WHY QUADRATIC FAILS:
    - Filler tokens dilute attention to E1
    - Must persist entity salience across distractors
    - Then bind the persisted entity

    WHY PHASE SUCCEEDS:
    - Phase state accumulates entity information
    - Filler doesn't erase state (cumsum persists)
    - Binding captures persisted entity
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Primary entity with verb
        primary = random.choice(self.entities)
        verb = random.choice(self.vocab.verbs)
        ids.extend([primary, verb, self.vocab.SEP])

        # Filler (distractors)
        n_filler = random.randint(2, 4)
        for _ in range(n_filler):
            ids.append(random.choice(self.vocab.fillers))
        ids.append(self.vocab.SEP)

        # Now bind the primary entity (must have persisted it)
        role = random.choice(self.roles)
        ids.extend([self.vocab.BIND, primary, role, self.vocab.SEP])
        state.bind(primary, role)

        # Add more bindings for complexity
        for _ in range(random.randint(1, 2)):
            other = random.choice([e for e in self.entities if e != primary])
            other_role = random.choice([r for r in self.roles if r != role])
            ids.extend([self.vocab.BIND, other, other_role, self.vocab.SEP])
            state.bind(other, other_role)

        # Query the persisted entity's role
        ids.extend([self.vocab.QUERY, role, self.vocab.ANS])
        target = state.query(role, self.vocab.NULL)

        explanation = f"LP_BIND: persist {self.vocab.id2name[primary]} across {n_filler} fillers"
        return self.pad(ids), target, explanation


class PureBindGenerator(ComposedSchemaGenerator):
    """
    PURE_BIND: Pure persistence test - BIND + QUERY only, no operations.

    Pattern: BIND E1 R0 | BIND E2 R1 | ... | BIND En Rm | QUERY Rx → Ex

    This isolates STATE PERSISTENCE from LOGICAL COMPOSITION.
    No NEG, no PERMUTE, no CONTEXT - just raw binding and retrieval.

    WHY THIS MATTERS:
    -----------------
    This shows Phase's clean O(n) advantage for pure memory tasks.
    It separates "can the model remember bindings?" from "can it reason about operations?"

    WHY QUADRATIC FAILS:
    - At chain length 8-12, attention span limits kick in
    - Early bindings get washed out by later processing
    - No attention "shortcut" to early positions from late queries

    WHY PHASE SUCCEEDS:
    - Cumsum maintains state with O(n) complexity
    - Early bindings persist indefinitely in accumulated state
    - Query phase alignment retrieves correct binding regardless of distance
    """

    def generate(self) -> Tuple[List[int], int, str]:
        state = BindingState()
        ids = []

        # Number of bindings (long chains for persistence test)
        n_bindings = random.randint(self.chain_min, self.chain_max)

        # Use all available roles, cycle if needed
        n_roles = min(len(self.roles), n_bindings)
        used_roles = random.sample(self.roles, n_roles)

        # Track which entity is bound to which role (last binding wins)
        role_to_entity = {}

        # Generate bindings (some roles may be overwritten)
        for i in range(n_bindings):
            entity = random.choice(self.entities)
            role = used_roles[i % n_roles]  # Cycle through roles

            ids.extend([self.vocab.BIND, entity, role, self.vocab.SEP])
            state.bind(entity, role)
            role_to_entity[role] = entity

        # Query an early role (tests long-range persistence)
        # Prefer querying a role that was bound early
        query_role = used_roles[0]
        ids.extend([self.vocab.QUERY, query_role, self.vocab.ANS])

        target = state.query(query_role, self.vocab.NULL)

        explanation = f"PURE_BIND: {n_bindings} bindings, query early role"
        return self.pad(ids), target, explanation


# =============================================================================
# DATASET
# =============================================================================

class HardProbeDataset(Dataset):
    """
    Dataset with strict train/test splits for generalization testing.

    CRITICAL: No leakage between splits.
    - Training uses only train_entities and train_roles
    - Test splits use held-out tokens as specified
    """

    def __init__(
        self,
        vocab: HardVocabulary,
        split: SplitType,
        num_samples: int,
        max_seq_len: int,
        chain_length: Tuple[int, int],
        bind_ratio: float = 0.6,
        seed: int = 42,
    ):
        self.vocab = vocab
        self.split = split
        self.num_samples = num_samples
        self.bind_ratio = bind_ratio

        # Determine allowed entities and roles based on split
        self._persist_only = False  # Special flag for pure persistence test
        if split == SplitType.TRAIN:
            entities = vocab.train_entities
            roles = vocab.train_roles
        elif split == SplitType.TEST_ROLES:
            entities = vocab.train_entities  # Same entities
            roles = vocab.test_roles         # Held-out roles
        elif split == SplitType.TEST_ENTITIES:
            entities = vocab.test_entities   # Held-out entities
            roles = vocab.train_roles        # Same roles
        elif split == SplitType.TEST_BOTH:
            entities = vocab.test_entities   # Held-out
            roles = vocab.test_roles         # Held-out
        elif split == SplitType.TEST_LONG:
            entities = vocab.train_entities  # Same tokens
            roles = vocab.train_roles        # Same tokens
            # But chain_length is longer (set externally)
        elif split == SplitType.TEST_PERSIST:
            entities = vocab.train_entities  # Same tokens
            roles = vocab.train_roles        # Same tokens
            self._persist_only = True        # Only use PureBindGenerator
            # Chain length 8-12 for pure persistence test (set externally)
        else:
            raise ValueError(f"Unknown split: {split}")

        # Create generators
        self.generators = self._create_generators(
            vocab, max_seq_len, entities, roles, chain_length
        )

        # Pre-generate samples
        random.seed(seed)
        self.samples = []
        for _ in range(num_samples):
            gen = self._select_generator()
            ids, target, explanation = gen.generate()
            self.samples.append((ids, target, explanation))

    def _create_generators(
        self,
        vocab: HardVocabulary,
        max_seq_len: int,
        entities: List[int],
        roles: List[int],
        chain_length: Tuple[int, int],
    ) -> Dict[SchemaType, ComposedSchemaGenerator]:
        """Create all generators with specified entity/role pools."""
        gens = {
            SchemaType.BIND_CHAIN: BindChainGenerator(
                vocab, max_seq_len, entities, roles, chain_length
            ),
            SchemaType.BIND_NEG: BindNegGenerator(
                vocab, max_seq_len, entities, roles, chain_length
            ),
            SchemaType.CHAIN_DEEP: ChainDeepGenerator(
                vocab, max_seq_len, entities, roles, chain_length
            ),
            SchemaType.PERMUTE_BIND: PermuteBindGenerator(
                vocab, max_seq_len, entities, roles, chain_length
            ),
            SchemaType.SI_BIND: SIBindGenerator(
                vocab, max_seq_len, entities, roles, chain_length
            ),
            SchemaType.LP_BIND: LPBindGenerator(
                vocab, max_seq_len, entities, roles, chain_length
            ),
        }
        # Also create PureBindGenerator for persistence-only tests
        self._pure_bind_gen = PureBindGenerator(
            vocab, max_seq_len, entities, roles, chain_length
        )
        return gens

    def _select_generator(self) -> ComposedSchemaGenerator:
        """Select generator based on bind_ratio curriculum or persist_only mode."""
        # For pure persistence test: only use PureBindGenerator
        if self._persist_only:
            return self._pure_bind_gen

        bind_schemas = [
            SchemaType.BIND_CHAIN,
            SchemaType.BIND_NEG,
            SchemaType.CHAIN_DEEP,
            SchemaType.PERMUTE_BIND,
        ]
        other_schemas = [
            SchemaType.SI_BIND,
            SchemaType.LP_BIND,
        ]

        if random.random() < self.bind_ratio:
            schema = random.choice(bind_schemas)
        else:
            schema = random.choice(other_schemas)

        return self.generators[schema]

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, str]:
        ids, target, explanation = self.samples[idx]
        return (
            torch.tensor(ids, dtype=torch.long),
            torch.tensor(target, dtype=torch.long),
            explanation,
        )


def collate_fn(batch):
    """Collate function that handles explanations."""
    ids = torch.stack([b[0] for b in batch])
    targets = torch.stack([b[1] for b in batch])
    explanations = [b[2] for b in batch]
    return ids, targets, explanations


# =============================================================================
# MODELS
# =============================================================================

class QuadraticAttention(nn.Module):
    """Standard O(n^2) attention."""

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

        # Causal mask
        mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
        scores = scores.masked_fill(mask, float('-inf'))

        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)

        out = torch.matmul(attn, V)
        out = out.transpose(1, 2).contiguous().view(B, N, D)

        return self.out_proj(out)

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


class PhaseAttention(nn.Module):
    """
    O(n) phasor attention with operation-conditioned phase offsets.

    KEY ENHANCEMENT: Operation tokens (NEG, PERMUTE, OVERWRITE) add learned
    phase shifts before the cumsum. This allows operations to be true STATE
    TRANSFORMATIONS rather than passive symbols.

    WHY THIS MATTERS:
    -----------------
    Without operation-conditioned offsets, operations like NEG are just tokens
    that the model must learn to interpret through content-based attention.
    With offsets, operations directly transform the phase state, which is how
    Phase is hypothesized to encode relational structure.

    This is NOT cheating - it tests the hypothesis more faithfully by making
    operations act as they're theoretically supposed to.
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1,
                 operation_tokens: List[int] = None, bounded_phase: bool = True):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.bounded_phase = bounded_phase  # V9.9.11: Constrain φ to [-π, π] via π*sin()

        self.W_q_phase = nn.Linear(d_model, d_model)
        self.W_k_phase = nn.Linear(d_model, d_model)
        self.W_q_amp = nn.Linear(d_model, d_model)
        self.W_k_amp = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

        # Operation-conditioned phase offsets
        # Each operation token gets a learned phase shift per head
        self.operation_tokens = operation_tokens or []
        if self.operation_tokens:
            # Map operation token IDs to indices 0, 1, 2, ...
            self.op_to_idx = {tok: i for i, tok in enumerate(self.operation_tokens)}
            # Learned phase shifts: [num_ops, num_heads, head_dim]
            self.op_phase_shifts = nn.Parameter(
                torch.randn(len(self.operation_tokens), num_heads, self.head_dim) * 0.1
            )
        else:
            self.op_to_idx = {}
            self.op_phase_shifts = None

        self._ablation_mode = "none"
        self._scramble_seed = 42
        self.capture_diagnostics = False
        self._phi_k = None
        self._phi_q = None

        # Rotation test: add a global phase rotation to φ_q
        self._rotation_angle = 0.0  # in radians

    def set_ablation(self, mode: str, seed: int = 42):
        self._ablation_mode = mode
        self._scramble_seed = seed

    def set_rotation(self, angle_radians: float):
        """
        Set a global phase rotation to apply to φ_q.

        This tests whether phase encodes relational structure:
        - If roles are phase-encoded, rotating φ_q should shift which bindings are retrieved
        - If phase is decorative, rotation should have minimal effect

        Args:
            angle_radians: Rotation angle in radians (e.g., π/4 = 45°)
        """
        self._rotation_angle = angle_radians

    def clear_rotation(self):
        """Clear any applied rotation."""
        self._rotation_angle = 0.0

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

    def _apply_operation_phase_shifts(self, phi_k: torch.Tensor,
                                       token_ids: torch.Tensor) -> torch.Tensor:
        """
        Apply learned phase shifts for operation tokens.

        When NEG, PERMUTE, or OVERWRITE appears, add its learned phase shift
        to phi_k at that position. This transforms the state before cumsum.
        """
        if self.op_phase_shifts is None or token_ids is None:
            return phi_k

        B, N, H, D = phi_k.shape

        # Create mask for each operation type and apply its phase shift
        for tok_id, op_idx in self.op_to_idx.items():
            # Mask: [B, N] where operation token appears
            mask = (token_ids == tok_id).float()  # [B, N]
            # Expand mask to [B, N, H, D]
            mask = mask.unsqueeze(-1).unsqueeze(-1).expand(B, N, H, D)
            # Get phase shift for this operation: [H, D] -> [1, 1, H, D]
            shift = self.op_phase_shifts[op_idx].unsqueeze(0).unsqueeze(0)
            # Apply: add shift where operation token appears
            phi_k = phi_k + mask * shift

        return phi_k

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None) -> torch.Tensor:
        """
        Forward pass with optional operation-conditioned phase shifts.

        Args:
            x: Input tensor [B, N, D]
            token_ids: Token IDs [B, N] for operation-conditioned phase shifts
        """
        B, N, D = x.shape

        # Compute phase projections
        phi_q_raw = self.W_q_phase(x).view(B, N, self.num_heads, self.head_dim)
        phi_k_raw = self.W_k_phase(x).view(B, N, self.num_heads, self.head_dim)

        # V9.9.11: Bounded phase parameterization (constrain φ to [-π, π] via π*sin())
        if self.bounded_phase:
            phi_q = math.pi * torch.sin(phi_q_raw)
            phi_k = math.pi * torch.sin(phi_k_raw)
        else:
            phi_q = phi_q_raw
            phi_k = phi_k_raw

        # Apply operation-conditioned phase shifts BEFORE ablation
        phi_k = self._apply_operation_phase_shifts(phi_k, token_ids)

        phi_q = self._ablate(phi_q)
        phi_k = self._ablate(phi_k)

        # Apply rotation to φ_q (tests phase selectivity)
        if self._rotation_angle != 0.0:
            phi_q = phi_q + self._rotation_angle

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
        """Mean resultant length (phase health metric)."""
        if self._phi_k is None:
            return 0.0
        z = torch.exp(1j * self._phi_k.float())
        return torch.abs(z.mean()).item()

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


class TransformerBlock(nn.Module):
    def __init__(self, d_model: int, num_heads: int, d_ff: int, dropout: float,
                 use_phase: bool, extra_ff: int = 0, operation_tokens: List[int] = None,
                 bounded_phase: bool = True):
        super().__init__()
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        # PhaseAttention gets operation_tokens for conditioned phase shifts
        if use_phase:
            self.attn = PhaseAttention(d_model, num_heads, dropout, operation_tokens, bounded_phase)
        else:
            self.attn = QuadraticAttention(d_model, num_heads, dropout)

        # Extra FF parameters for matching (added to quadratic when match_params=True)
        actual_d_ff = d_ff + extra_ff
        self.ff = nn.Sequential(
            nn.Linear(d_model, actual_d_ff), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(actual_d_ff, d_model), nn.Dropout(dropout)
        )
        self.use_phase = use_phase

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None) -> torch.Tensor:
        # Pass token_ids to PhaseAttention for operation-conditioned phase shifts
        if self.use_phase and token_ids is not None:
            x = x + self.attn(self.norm1(x), token_ids)
        else:
            x = x + self.attn(self.norm1(x))
        x = x + self.ff(self.norm2(x))
        return x


class HybridTransformerBlock(nn.Module):
    """
    Hybrid block that MIXES Phase and Quadratic attention outputs.

    WHY MIXING (not switching):
    ---------------------------
    Instead of choosing one attention type per layer, we combine both:
      output = phase_ratio * phase_out + (1 - phase_ratio) * quad_out

    This allows smooth interpolation and lets the model learn to leverage
    Phase for state persistence and Quadratic for reasoning within each layer.

    The INVERTED CURRICULUM sets:
    - Early layers: phase_ratio ≈ 0.9 (mostly Phase for state capture)
    - Late layers: phase_ratio ≈ 0.1 (mostly Quadratic for reasoning)
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        d_ff: int,
        dropout: float,
        phase_ratio: float = 0.5,  # 0.0 = pure Quadratic, 1.0 = pure Phase
        operation_tokens: List[int] = None,
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.phase_ratio = phase_ratio
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        # Both attention types
        self.phase_attn = PhaseAttention(d_model, num_heads, dropout, operation_tokens, bounded_phase)
        self.quad_attn = QuadraticAttention(d_model, num_heads, dropout)

        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_ff, d_model), nn.Dropout(dropout)
        )

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None) -> torch.Tensor:
        normed = self.norm1(x)

        # Run both attention types
        phase_out = self.phase_attn(normed, token_ids)
        quad_out = self.quad_attn(normed)

        # Mix outputs according to phase_ratio
        attn_out = self.phase_ratio * phase_out + (1 - self.phase_ratio) * quad_out

        x = x + attn_out
        x = x + self.ff(self.norm2(x))
        return x

    def set_ablation(self, mode: str, seed: int = 42):
        """Set ablation mode for Phase attention component."""
        self.phase_attn.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """Set rotation angle for Phase attention component."""
        self.phase_attn.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from Phase attention component."""
        self.phase_attn.clear_rotation()


class HybridTransformer(nn.Module):
    """
    Transformer with per-layer Phase/Quadratic mixing (INVERTED CURRICULUM).

    INVERTED CURRICULUM RATIONALE:
    ------------------------------
    Evidence shows PhaseAttention excels at STATE PERSISTENCE, not reasoning.
    Therefore:
    - Early layers: Phase-heavy → capture input state with O(n) efficiency
    - Late layers: Quadratic-heavy → reason over persisted state

    Curriculum format: List of phase_ratios per layer
    - [0.9, 0.7, 0.3, 0.1] = Inverted (Phase early, Quad late) ← RECOMMENDED
    - [0.1, 0.3, 0.7, 0.9] = Standard (Quad early, Phase late)
    - [0.5, 0.5, 0.5, 0.5] = Balanced
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
        num_classes: int,
        curriculum: List[float],  # phase_ratio per layer
        operation_tokens: List[int] = None,
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.curriculum = curriculum
        self.operation_tokens = operation_tokens

        assert len(curriculum) == num_layers, \
            f"Curriculum length ({len(curriculum)}) must match num_layers ({num_layers})"

        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)

        self.layers = nn.ModuleList([
            HybridTransformerBlock(
                d_model, num_heads, d_ff, dropout,
                phase_ratio=curriculum[i],
                operation_tokens=operation_tokens,
                bounded_phase=bounded_phase,
            )
            for i in range(num_layers)
        ])

        self.norm = nn.LayerNorm(d_model)
        self.classifier = nn.Linear(d_model, num_classes)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        for layer in self.layers:
            x = layer(x, input_ids)

        return self.classifier(self.norm(x[:, -1, :]))

    def set_ablation(self, mode: str, seed: int = 42):
        """Set ablation mode for all Phase attention components."""
        for layer in self.layers:
            layer.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """Set rotation angle for all Phase attention layers."""
        for layer in self.layers:
            layer.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from all Phase attention layers."""
        for layer in self.layers:
            layer.clear_rotation()

    def enable_diagnostics(self, enable: bool = True):
        """Enable/disable phase diagnostics capture."""
        for layer in self.layers:
            layer.phase_attn.capture_diagnostics = enable

    def get_R_k(self) -> float:
        """Get mean R_k across all Phase attention layers."""
        r_values = []
        for layer in self.layers:
            r_values.append(layer.phase_attn.get_R_k())
        return sum(r_values) / len(r_values) if r_values else 0.0

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def describe_curriculum(self) -> str:
        """Return human-readable curriculum description."""
        parts = []
        for i, ratio in enumerate(self.curriculum):
            parts.append(f"L{i}:{ratio*100:.0f}%P")
        return " → ".join(parts)


# =============================================================================
# PROTECTED PHASE ARCHITECTURE (v5)
# =============================================================================
# Evidence shows Phase becomes DECORATIVE when mixed with Quadratic.
# Solution: Give Phase and Quadratic EXCLUSIVE, NON-COMPETING roles.
#
# Architecture:
#   Phase:     memory_state = cumsum(keys * values)  # Accumulate bindings
#   Quadratic: output = attention(query, memory_state)  # Query the memory
#
# This is NOT mixing - it's COLLABORATION:
#   - Phase has exclusive control over state accumulation
#   - Quadratic has exclusive control over state querying
#   - They don't compete for the same gradient signal
# =============================================================================

class ProtectedPhaseAttention(nn.Module):
    """
    Phase attention that outputs a MEMORY STATE for Quadratic to query.

    Unlike regular PhaseAttention which outputs attention-weighted values,
    this outputs the raw cumsum state that Quadratic can query.

    Phase's exclusive job: Accumulate key-value pairs into persistent state.
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1,
                 operation_tokens: List[int] = None, bounded_phase: bool = True):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.bounded_phase = bounded_phase  # V9.9.11: Constrain φ to [-π, π] via π*sin()

        # Phase projections for keys
        self.W_k_phase = nn.Linear(d_model, d_model)
        self.W_k_amp = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)

        # Operation-conditioned phase offsets
        self.operation_tokens = operation_tokens or []
        if self.operation_tokens:
            self.op_to_idx = {tok: i for i, tok in enumerate(self.operation_tokens)}
            self.op_phase_shifts = nn.Parameter(
                torch.randn(len(self.operation_tokens), num_heads, self.head_dim) * 0.1
            )
        else:
            self.op_to_idx = {}
            self.op_phase_shifts = None

        self.dropout = nn.Dropout(dropout)
        self._ablation_mode = "none"
        self._rotation_angle = 0.0  # For rotation test (applied to phi_k)

        # Health tracking: R_k (amplitude) statistics
        self._last_r_k_mean = 0.0
        self._last_r_k_std = 0.0
        self._last_r_k_min = 0.0
        self._last_r_k_max = 0.0

    def set_ablation(self, mode: str, seed: int = 42):
        self._ablation_mode = mode
        self._scramble_seed = seed

    def set_rotation(self, angle_radians: float):
        """
        Set a global phase rotation to apply to φ_k.

        For Protected Phase, we rotate φ_k (not φ_q) because:
        - Protected Phase uses φ_k for memory accumulation (cumsum)
        - There is no φ_q in this architecture (Quadratic handles queries)

        This tests whether phase encodes relational structure:
        - If roles are phase-encoded in keys, rotating φ_k should disrupt retrieval
        - If phase is decorative, rotation should have minimal effect

        Args:
            angle_radians: Rotation angle in radians (e.g., π/4 = 45°)
        """
        self._rotation_angle = angle_radians

    def clear_rotation(self):
        """Clear any applied rotation."""
        self._rotation_angle = 0.0

    def get_health_metrics(self) -> dict:
        """Return Phase health metrics (R_k statistics)."""
        return {
            "r_k_mean": self._last_r_k_mean,
            "r_k_std": self._last_r_k_std,
            "r_k_min": self._last_r_k_min,
            "r_k_max": self._last_r_k_max,
        }

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None) -> torch.Tensor:
        """
        Compute Phase memory state via cumsum.

        Returns: memory_state [B, N, D] - the accumulated state for Quadratic to query
        """
        B, N, D = x.shape

        # Compute phase projection for keys
        phi_k_raw = self.W_k_phase(x).view(B, N, self.num_heads, self.head_dim)

        # V9.9.11: Bounded phase parameterization (constrain φ to [-π, π] via π*sin())
        if self.bounded_phase:
            phi_k = math.pi * torch.sin(phi_k_raw)
        else:
            phi_k = phi_k_raw

        a_k = torch.sigmoid(self.W_k_amp(x)).view(B, N, self.num_heads, self.head_dim)
        v = self.W_v(x).view(B, N, self.num_heads, self.head_dim)

        # Track R_k health metrics (amplitude statistics)
        with torch.no_grad():
            self._last_r_k_mean = a_k.mean().item()
            self._last_r_k_std = a_k.std().item()
            self._last_r_k_min = a_k.min().item()
            self._last_r_k_max = a_k.max().item()

        # Apply operation-conditioned phase shifts
        if self.op_phase_shifts is not None and token_ids is not None:
            for tok_id, op_idx in self.op_to_idx.items():
                mask = (token_ids == tok_id).float().unsqueeze(-1).unsqueeze(-1)
                mask = mask.expand(B, N, self.num_heads, self.head_dim)
                shift = self.op_phase_shifts[op_idx].unsqueeze(0).unsqueeze(0)
                phi_k = phi_k + mask * shift

        # Ablation
        if self._ablation_mode == "scramble":
            torch.manual_seed(self._scramble_seed)
            for b in range(B):
                for h in range(self.num_heads):
                    perm = torch.randperm(N, device=phi_k.device)
                    phi_k[b, :, h, :] = phi_k[b, perm, h, :]
        elif self._ablation_mode in ["freeze", "off"]:
            phi_k = torch.zeros_like(phi_k)

        # Apply rotation to φ_k (tests phase selectivity for Protected Phase)
        # Note: We rotate φ_k here because Protected Phase has no φ_q
        if self._rotation_angle != 0.0:
            phi_k = phi_k + self._rotation_angle

        # Compute complex phasor and accumulate via cumsum
        dtype = phi_k.dtype
        if dtype == torch.bfloat16:
            phi_k, a_k, v = phi_k.float(), a_k.float(), v.float()

        k_phasor = torch.polar(a_k, -phi_k)
        v_complex = torch.complex(v, torch.zeros_like(v))
        kv = k_phasor * v_complex

        # CUMSUM: This is Phase's exclusive job - accumulate state
        memory_state = torch.cumsum(kv, dim=1)

        # Return real part as memory state for Quadratic to query
        memory_state = memory_state.real

        if dtype == torch.bfloat16:
            memory_state = memory_state.to(dtype)

        return memory_state.reshape(B, N, D)


class ProtectedQuadAttention(nn.Module):
    """
    Quadratic attention that QUERIES a memory state (from Phase).

    Unlike regular QuadraticAttention which computes K,V from input,
    this uses the Phase memory state as keys/values.

    Quadratic's exclusive job: Query the Phase-accumulated memory.
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.scale = math.sqrt(self.head_dim)

        # Query projection (from input)
        self.W_q = nn.Linear(d_model, d_model)
        # Key/Value projections (from memory state)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, memory_state: torch.Tensor) -> torch.Tensor:
        """
        Query the Phase memory state.

        Args:
            x: Input tensor [B, N, D] - used for queries
            memory_state: Phase memory [B, N, D] - used for keys/values
        """
        B, N, D = x.shape

        # Queries from input
        Q = self.W_q(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        # Keys and Values from Phase memory state
        K = self.W_k(memory_state).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.W_v(memory_state).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # Standard attention over memory
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale

        # Causal mask
        mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
        scores = scores.masked_fill(mask, float('-inf'))

        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)

        out = torch.matmul(attn, V)
        out = out.transpose(1, 2).contiguous().view(B, N, D)

        return self.out_proj(out)


class ProtectedPhaseBlock(nn.Module):
    """
    Block with PROTECTED Phase and Quadratic roles.

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
        operation_tokens: List[int] = None,
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm_mem = nn.LayerNorm(d_model)

        # Protected Phase: accumulates memory state
        self.phase_memory = ProtectedPhaseAttention(d_model, num_heads, dropout, operation_tokens, bounded_phase)
        # Protected Quad: queries memory state
        self.quad_query = ProtectedQuadAttention(d_model, num_heads, dropout)

        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_ff, d_model), nn.Dropout(dropout)
        )

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None) -> torch.Tensor:
        # Step 1: Phase accumulates memory state (Phase's exclusive job)
        normed = self.norm1(x)
        memory_state = self.phase_memory(normed, token_ids)
        memory_state = self.norm_mem(memory_state)

        # Step 2: Quadratic queries the memory (Quad's exclusive job)
        attn_out = self.quad_query(normed, memory_state)

        # Residual and FF
        x = x + attn_out
        x = x + self.ff(self.norm2(x))
        return x

    def set_ablation(self, mode: str, seed: int = 42):
        """Set ablation mode for Phase component."""
        self.phase_memory.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """Set rotation angle for Phase component (applied to φ_k)."""
        self.phase_memory.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from Phase component."""
        self.phase_memory.clear_rotation()


class ProtectedPhaseTransformer(nn.Module):
    """
    Transformer with PROTECTED Phase architecture.

    Key insight from ablation tests:
    - When mixed, Phase becomes DECORATIVE (0% ablation drop)
    - When alone, Phase is ESSENTIAL (37% ablation drop)

    Solution: Give Phase and Quadratic NON-COMPETING roles:
    - Phase: O(n) memory accumulation (cumsum)
    - Quadratic: O(n²) memory querying (attention)

    They collaborate sequentially, not compete in parallel.
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
        num_classes: int,
        operation_tokens: List[int] = None,
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.operation_tokens = operation_tokens

        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)

        self.layers = nn.ModuleList([
            ProtectedPhaseBlock(d_model, num_heads, d_ff, dropout, operation_tokens, bounded_phase)
            for _ in range(num_layers)
        ])

        self.norm = nn.LayerNorm(d_model)
        self.classifier = nn.Linear(d_model, num_classes)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        for layer in self.layers:
            x = layer(x, input_ids)

        return self.classifier(self.norm(x[:, -1, :]))

    def set_ablation(self, mode: str, seed: int = 42):
        """Set ablation mode for all Phase components."""
        for layer in self.layers:
            layer.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """
        Set rotation angle for all Phase components (applied to φ_k).

        Note: ProtectedPhaseTransformer uses φ_k only (for memory accumulation),
        not φ_q. So we rotate φ_k to test whether phase encodes relational structure.

        Args:
            angle_radians: Rotation angle in radians (e.g., π/4 = 45°)
        """
        for layer in self.layers:
            layer.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from all Phase components."""
        for layer in self.layers:
            layer.clear_rotation()

    def enable_diagnostics(self, enable: bool = True):
        """Enable/disable phase diagnostics (placeholder for compatibility)."""
        pass

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
            layer_metrics = layer.phase_memory.get_health_metrics()
            for k, v in layer_metrics.items():
                metrics[k].append(v)

        # Average across layers
        return {
            "r_k_mean": sum(metrics["r_k_mean"]) / len(metrics["r_k_mean"]) if metrics["r_k_mean"] else 0.0,
            "r_k_std": sum(metrics["r_k_std"]) / len(metrics["r_k_std"]) if metrics["r_k_std"] else 0.0,
            "r_k_min": min(metrics["r_k_min"]) if metrics["r_k_min"] else 0.0,
            "r_k_max": max(metrics["r_k_max"]) if metrics["r_k_max"] else 0.0,
        }

    def get_R_k(self) -> float:
        """Get mean R_k metric for backward compatibility."""
        return self.get_phase_health()["r_k_mean"]

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class HardProbeTransformer(nn.Module):
    """Transformer for hard probe classification with operation-conditioned phase shifts."""

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        num_heads: int,
        num_layers: int,
        d_ff: int,
        dropout: float,
        max_seq_len: int,
        num_classes: int,
        use_phase: bool,
        extra_ff_per_layer: int = 0,  # For parameter matching
        operation_tokens: List[int] = None,  # Tokens that trigger phase shifts
        bounded_phase: bool = True,  # V9.9.11: Constrain φ to [-π, π] via π*sin()
    ):
        super().__init__()
        self.use_phase = use_phase
        self.operation_tokens = operation_tokens
        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)
        self.layers = nn.ModuleList([
            TransformerBlock(d_model, num_heads, d_ff, dropout, use_phase,
                           extra_ff_per_layer, operation_tokens, bounded_phase)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(d_model)
        self.classifier = nn.Linear(d_model, num_classes)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        # Pass input_ids to layers for operation-conditioned phase shifts
        for layer in self.layers:
            x = layer(x, input_ids if self.use_phase else None)

        return self.classifier(self.norm(x[:, -1, :]))

    def set_ablation(self, mode: str, seed: int = 42):
        for layer in self.layers:
            if hasattr(layer.attn, 'set_ablation'):
                layer.attn.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """Set rotation angle for all Phase attention layers."""
        for layer in self.layers:
            if hasattr(layer.attn, 'set_rotation'):
                layer.attn.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from all Phase attention layers."""
        for layer in self.layers:
            if hasattr(layer.attn, 'clear_rotation'):
                layer.attn.clear_rotation()

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


def compute_param_diff(d_model: int, num_heads: int, num_layers: int) -> int:
    """
    Compute parameter difference between Phase and Quadratic attention.

    Phase has extra W_q_phase, W_k_phase, W_q_amp, W_k_amp projections.
    Quadratic has W_q, W_k, W_v.

    Difference per layer = 2 * d_model^2 (two extra projections)
    """
    # Phase: W_q_phase, W_k_phase, W_q_amp, W_k_amp, W_v, out_proj = 6
    # Quadratic: W_q, W_k, W_v, out_proj = 4
    # Difference: 2 projections per layer
    extra_per_layer = 2 * d_model * d_model
    return extra_per_layer * num_layers


# =============================================================================
# EVALUATION
# =============================================================================

def evaluate(
    model: nn.Module,
    loader: DataLoader,
    vocab: HardVocabulary,
    device: str,
) -> float:
    """Evaluate model accuracy."""
    model.eval()
    correct = 0
    total = 0

    with torch.no_grad():
        for ids, targets, _ in loader:
            ids, targets = ids.to(device), targets.to(device)

            # Convert entity IDs to class indices
            target_idx = torch.tensor([
                vocab.entity_to_idx(t.item()) if t.item() in vocab.entities else 0
                for t in targets
            ], device=device)

            logits = model(ids)
            preds = logits.argmax(dim=-1)

            # Handle NULL (maps to class 0 by convention, or separate handling)
            for i in range(len(targets)):
                if targets[i].item() == vocab.NULL:
                    # NULL target — check if prediction is outside entity range or class 0
                    # For simplicity, we'll treat NULL as predicting the "NULL entity" which is vocab.entities[0]
                    target_idx[i] = 0

            correct += (preds == target_idx).sum().item()
            total += len(targets)

    return correct / max(total, 1)


def evaluate_all_splits(
    model: nn.Module,
    test_loaders: Dict[SplitType, DataLoader],
    vocab: HardVocabulary,
    device: str,
) -> Dict[str, float]:
    """Evaluate on all test splits separately."""
    results = {}
    for split, loader in test_loaders.items():
        acc = evaluate(model, loader, vocab, device)
        results[split.value] = acc
    return results


def run_ablation(
    model: nn.Module,
    loader: DataLoader,
    vocab: HardVocabulary,
    device: str,
) -> Dict[str, float]:
    """Run phase ablation tests."""
    results = {}
    for mode in ["none", "scramble", "freeze", "off"]:
        model.set_ablation(mode)
        acc = evaluate(model, loader, vocab, device)
        results[mode] = acc
    model.set_ablation("none")
    return results


def run_rotation_test(
    model: nn.Module,
    loader: DataLoader,
    vocab: HardVocabulary,
    device: str,
    angles_degrees: List[float] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Run phase rotation tests to verify phase encodes relational structure.

    HYPOTHESIS:
    -----------
    If roles are encoded as phase offsets (e.g., R0 → φ=0, R1 → φ=π/2):
    - Rotating φ_q by θ should shift which role's binding is retrieved
    - Larger rotations should cause larger accuracy drops
    - Specific rotations might "swap" roles (retrieve R1 when querying R0)

    If phase is decorative:
    - Rotation should have minimal/random effect on accuracy
    - No systematic relationship between rotation angle and accuracy

    Args:
        model: Model with phase attention (must have set_rotation method)
        loader: DataLoader for evaluation
        vocab: Vocabulary for decoding
        device: Device to run on
        angles_degrees: List of rotation angles in degrees (default: 0, 45, 90, 135, 180)

    Returns:
        Dictionary with:
        - 'accuracy': {angle: accuracy} for each angle
        - 'delta': {angle: accuracy_change} relative to baseline
        - 'sensitivity': float (mean absolute delta, higher = more sensitive)
        - 'systematic': bool (True if accuracy decreases monotonically with angle)
    """
    if angles_degrees is None:
        angles_degrees = [0, 45, 90, 135, 180, 270]

    if not hasattr(model, 'set_rotation'):
        return {
            'accuracy': {0: evaluate(model, loader, vocab, device)},
            'delta': {0: 0.0},
            'sensitivity': 0.0,
            'systematic': False,
            'error': 'Model does not support rotation (no set_rotation method)'
        }

    results = {'accuracy': {}, 'delta': {}}

    # Get baseline (0° rotation)
    model.set_rotation(0.0)
    baseline = evaluate(model, loader, vocab, device)
    results['accuracy'][0] = baseline
    results['delta'][0] = 0.0

    # Test each rotation angle
    for angle_deg in angles_degrees:
        if angle_deg == 0:
            continue  # Already computed

        angle_rad = math.radians(angle_deg)
        model.set_rotation(angle_rad)
        acc = evaluate(model, loader, vocab, device)
        results['accuracy'][angle_deg] = acc
        results['delta'][angle_deg] = acc - baseline

    # Clear rotation
    model.clear_rotation()

    # Compute sensitivity metrics
    deltas = [abs(d) for a, d in results['delta'].items() if a != 0]
    results['sensitivity'] = sum(deltas) / len(deltas) if deltas else 0.0

    # Check if accuracy drops systematically with angle (up to 180°)
    angles_sorted = sorted([a for a in results['accuracy'].keys() if a <= 180])
    accs_sorted = [results['accuracy'][a] for a in angles_sorted]
    # Systematic if accuracy generally decreases (allowing small fluctuations)
    decreasing_pairs = sum(1 for i in range(len(accs_sorted)-1) if accs_sorted[i] >= accs_sorted[i+1] - 0.02)
    results['systematic'] = decreasing_pairs >= (len(accs_sorted) - 2) if len(accs_sorted) > 2 else False

    # Additional analysis: find angle of maximum disruption
    if results['delta']:
        min_delta_angle = min(results['delta'].items(), key=lambda x: x[1])
        results['max_disruption_angle'] = min_delta_angle[0]
        results['max_disruption_delta'] = min_delta_angle[1]

    return results


def print_rotation_test_results(
    results: Dict[str, Dict[str, float]],
    model_name: str = "Phase",
) -> None:
    """Pretty-print rotation test results."""
    print(f"\n--- PHASE ROTATION TEST: {model_name} ---")

    if 'error' in results:
        print(f"  ERROR: {results['error']}")
        return

    print(f"\n  {'Angle':>8}  {'Accuracy':>10}  {'Δ from 0°':>10}")
    print(f"  {'-'*8}  {'-'*10}  {'-'*10}")

    for angle in sorted(results['accuracy'].keys()):
        acc = results['accuracy'][angle]
        delta = results['delta'][angle]
        delta_str = f"{delta*100:+.1f}%" if angle != 0 else "baseline"
        print(f"  {angle:>6}°  {acc*100:>9.1f}%  {delta_str:>10}")

    print(f"\n  Sensitivity (mean |Δ|): {results['sensitivity']*100:.2f}%")
    print(f"  Systematic decrease:    {'Yes' if results['systematic'] else 'No'}")

    if 'max_disruption_angle' in results:
        print(f"  Max disruption at:      {results['max_disruption_angle']}° ({results['max_disruption_delta']*100:+.1f}%)")

    # Interpretation
    print(f"\n  INTERPRETATION:")
    if results['sensitivity'] > 0.10:
        print(f"    → Phase is SENSITIVE to rotation (sensitivity > 10%)")
        print(f"    → Phase likely encodes meaningful relational structure")
        if results['systematic']:
            print(f"    → Systematic decrease suggests phase offset = role encoding")
    elif results['sensitivity'] > 0.03:
        print(f"    → Phase shows MODERATE sensitivity to rotation")
        print(f"    → Phase may partially encode relational structure")
    else:
        print(f"    → Phase is INSENSITIVE to rotation (sensitivity < 3%)")
        print(f"    → Phase appears DECORATIVE (not encoding relations)")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Hard Diagnostic Probe Training for PhaseAttention",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default run (Quadratic vs Phase)
  python train_hard_probes.py

  # BIND-dominant curriculum (recommended)
  python train_hard_probes.py --bind-ratio 0.7

  # Parameter-matched comparison
  python train_hard_probes.py --match-params

  # Longer chains for harder test
  python train_hard_probes.py --test-chain-min 6 --test-chain-max 8

  # v3: Test INVERTED CURRICULUM hypothesis (Phase=state, Quad=reasoning)
  python train_hard_probes.py --compare-curricula

  # v3: Custom curriculum (90% Phase L0 → 10% Phase L3)
  python train_hard_probes.py --run-hybrid --curriculum 0.9,0.7,0.3,0.1

  # Full scientific comparison
  python train_hard_probes.py --compare-curricula --bind-ratio 0.7 --match-params

  # Phase rotation test (verify phase encodes relational structure)
  python train_hard_probes.py --rotation-test

  # Custom rotation angles
  python train_hard_probes.py --rotation-test --rotation-angles 0,30,60,90,120,150,180
        """
    )

    # Model - INCREASED CAPACITY (d_model=128, num_heads=8, num_layers=4)
    parser.add_argument("--d-model", type=int, default=128,
                        help="Model dimension (increased for reasoning capacity)")
    parser.add_argument("--num-heads", type=int, default=8,
                        help="Number of attention heads")
    parser.add_argument("--num-layers", type=int, default=4,
                        help="Number of transformer layers")
    parser.add_argument("--d-ff", type=int, default=256,
                        help="FFN dimension (2x d_model)")

    # Training
    parser.add_argument("--num-steps", type=int, default=15000)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)

    # Dataset
    parser.add_argument("--train-samples", type=int, default=20000)
    parser.add_argument("--test-samples", type=int, default=1000,
                        help="Samples per test split")
    parser.add_argument("--bind-ratio", type=float, default=0.6,
                        help="Ratio of BIND-dominant schemas (0.0-1.0)")

    # Chain lengths
    parser.add_argument("--train-chain-min", type=int, default=3)
    parser.add_argument("--train-chain-max", type=int, default=5)
    parser.add_argument("--test-chain-min", type=int, default=6)
    parser.add_argument("--test-chain-max", type=int, default=8)
    parser.add_argument("--persist-chain-min", type=int, default=8,
                        help="Min chain length for pure persistence test")
    parser.add_argument("--persist-chain-max", type=int, default=12,
                        help="Max chain length for pure persistence test")

    # Parameter matching
    parser.add_argument("--match-params", action="store_true",
                        help="Add extra FF params to quadratic to match phase param count")

    # Hybrid curriculum (v3)
    parser.add_argument("--run-hybrid", action="store_true",
                        help="Also run Hybrid model with inverted curriculum")
    parser.add_argument("--curriculum", type=str, default="0.9,0.7,0.3,0.1",
                        help="Phase ratios per layer (comma-separated). "
                             "Inverted=0.9,0.7,0.3,0.1 (Phase early, Quad late)")
    parser.add_argument("--compare-curricula", action="store_true",
                        help="Compare inverted vs standard curriculum")

    # Protected Phase (v5)
    parser.add_argument("--protected-phase", action="store_true",
                        help="Run Protected Phase model (Phase accumulates, Quad queries)")

    # Phase Rotation Test
    parser.add_argument("--rotation-test", action="store_true",
                        help="Run phase rotation test after training to verify phase encodes relations")
    parser.add_argument("--rotation-angles", type=str, default="0,45,90,135,180,270",
                        help="Comma-separated rotation angles in degrees for rotation test")

    # Phase collapse fix (V9.9.11)
    parser.add_argument("--bounded-phase", action="store_true", default=True,
                        help="Constrain phase to [-π, π] via π*sin() (default: True)")
    parser.add_argument("--no-bounded-phase", dest="bounded_phase", action="store_false",
                        help="Disable bounded phase (use raw linear projection)")

    # Device
    parser.add_argument("--device", type=str,
                        default="cuda" if torch.cuda.is_available() else "cpu")

    args = parser.parse_args()

    # Parse curriculum
    curriculum = [float(x) for x in args.curriculum.split(",")]
    # Pad/truncate to match num_layers
    while len(curriculum) < args.num_layers:
        curriculum.append(curriculum[-1] if curriculum else 0.5)
    curriculum = curriculum[:args.num_layers]

    # Build config
    config = Config(
        d_model=args.d_model,
        num_heads=args.num_heads,
        num_layers=args.num_layers,
        d_ff=args.d_ff,
        num_steps=args.num_steps,
        batch_size=args.batch_size,
        lr=args.lr,
        train_samples=args.train_samples,
        test_samples_per_split=args.test_samples,
        bind_ratio=args.bind_ratio,
        train_chain_length=(args.train_chain_min, args.train_chain_max),
        test_chain_length=(args.test_chain_min, args.test_chain_max),
        persist_chain_length=(args.persist_chain_min, args.persist_chain_max),
        match_params=args.match_params,
        bounded_phase=args.bounded_phase,
        device=args.device,
    )

    print("=" * 70)
    print("HARD DIAGNOSTIC PROBE: PhaseAttention vs Quadratic Attention")
    print("=" * 70)
    print("\nThis benchmark tests TRUE RELATIONAL GENERALIZATION:")
    print("  - Held-out roles (R4-R6 never seen in training)")
    print("  - Open-world entities (E8-E15 never seen in training)")
    print("  - Long chains (6-8 steps vs 3-5 in training)")
    print("  - Schema composition (no single-pattern shortcuts)")
    print()

    # Vocabulary
    vocab = HardVocabulary()
    print(f"Vocabulary: {vocab.vocab_size} tokens")
    print(f"  Train entities: E0-E7 ({len(vocab.train_entities)})")
    print(f"  Test entities:  E8-E15 ({len(vocab.test_entities)})")
    print(f"  Train roles:    R0-R3 ({len(vocab.train_roles)})")
    print(f"  Test roles:     R4-R6 ({len(vocab.test_roles)})")

    # Datasets
    print(f"\nCreating datasets...")
    print(f"  BIND ratio: {config.bind_ratio:.0%}")
    print(f"  Train chain length: {config.train_chain_length}")
    print(f"  Test chain length: {config.test_chain_length}")
    print(f"  Persist chain length: {config.persist_chain_length}")

    train_ds = HardProbeDataset(
        vocab, SplitType.TRAIN, config.train_samples, config.max_seq_len,
        config.train_chain_length, config.bind_ratio, seed=42
    )

    test_datasets = {
        SplitType.TEST_ROLES: HardProbeDataset(
            vocab, SplitType.TEST_ROLES, config.test_samples_per_split,
            config.max_seq_len, config.train_chain_length, config.bind_ratio, seed=100
        ),
        SplitType.TEST_ENTITIES: HardProbeDataset(
            vocab, SplitType.TEST_ENTITIES, config.test_samples_per_split,
            config.max_seq_len, config.train_chain_length, config.bind_ratio, seed=200
        ),
        SplitType.TEST_BOTH: HardProbeDataset(
            vocab, SplitType.TEST_BOTH, config.test_samples_per_split,
            config.max_seq_len, config.train_chain_length, config.bind_ratio, seed=300
        ),
        SplitType.TEST_LONG: HardProbeDataset(
            vocab, SplitType.TEST_LONG, config.test_samples_per_split,
            config.max_seq_len, config.test_chain_length, config.bind_ratio, seed=400
        ),
        # Pure persistence test: BIND+QUERY only, long chains (8-12)
        SplitType.TEST_PERSIST: HardProbeDataset(
            vocab, SplitType.TEST_PERSIST, config.test_samples_per_split,
            config.max_seq_len, config.persist_chain_length, config.bind_ratio, seed=500
        ),
    }

    train_loader = DataLoader(train_ds, batch_size=config.batch_size,
                              shuffle=True, collate_fn=collate_fn)
    test_loaders = {
        split: DataLoader(ds, batch_size=config.batch_size,
                          shuffle=False, collate_fn=collate_fn)
        for split, ds in test_datasets.items()
    }

    print(f"\nTrain samples: {len(train_ds)}")
    for split, ds in test_datasets.items():
        print(f"  {split.value}: {len(ds)}")

    # Show examples
    print("\n--- Example Samples ---")
    for i in range(min(5, len(train_ds))):
        ids, target, explanation = train_ds.samples[i]
        print(f"  {vocab.decode(ids)} → {vocab.id2name.get(target, target)}")
        print(f"    ({explanation})")

    # Models
    print("\n--- Creating Models ---")
    num_classes = len(vocab.entities)  # Classify into entity slots

    # Compute parameter matching if needed
    extra_ff = 0
    if config.match_params:
        param_diff = compute_param_diff(config.d_model, config.num_heads, config.num_layers)
        # Add to d_ff to approximately match
        extra_ff = param_diff // (2 * config.d_model * config.num_layers)
        print(f"Parameter matching: adding {extra_ff} to d_ff for quadratic")

    # Operation tokens for phase-conditioned shifts (NEG, PERMUTE, OVERWRITE)
    operation_tokens = [vocab.NEG, vocab.PERMUTE, vocab.OVERWRITE]
    print(f"Operation tokens for phase shifts: {[vocab.id2name[t] for t in operation_tokens]}")

    model_quad = HardProbeTransformer(
        vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
        config.d_ff, config.dropout, config.max_seq_len, num_classes,
        use_phase=False, extra_ff_per_layer=extra_ff if config.match_params else 0
    ).to(config.device)

    model_phase = HardProbeTransformer(
        vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
        config.d_ff, config.dropout, config.max_seq_len, num_classes,
        use_phase=True, extra_ff_per_layer=0,
        operation_tokens=operation_tokens,  # Enable operation-conditioned phase shifts
        bounded_phase=config.bounded_phase,  # V9.9.11: Constrain φ to [-π, π]
    ).to(config.device)

    print(f"Quadratic params: {model_quad.count_params():,}")
    print(f"Phase params:     {model_phase.count_params():,}")
    if config.bounded_phase:
        print(f"  Bounded Phase: ENABLED (π*sin() bounds φ to [-π, π])")
    else:
        print(f"  Bounded Phase: DISABLED (raw linear projection)")
    if config.match_params:
        diff = abs(model_phase.count_params() - model_quad.count_params())
        print(f"  Param difference: {diff:,} ({diff / model_phase.count_params() * 100:.1f}%)")

    # Hybrid model with inverted curriculum (v3)
    model_hybrid = None
    model_hybrid_std = None  # For curriculum comparison
    opt_hybrid = None
    opt_hybrid_std = None

    if args.run_hybrid or args.compare_curricula:
        # Inverted curriculum: Phase-heavy early, Quadratic-heavy late
        inverted_curriculum = curriculum  # From CLI arg
        print(f"\n--- Hybrid Model (INVERTED CURRICULUM) ---")
        print(f"  Curriculum: {' → '.join(f'L{i}:{r*100:.0f}%P' for i, r in enumerate(inverted_curriculum))}")
        print(f"  Interpretation: Phase-heavy early (state capture) → Quadratic-heavy late (reasoning)")

        model_hybrid = HybridTransformer(
            vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
            config.d_ff, config.dropout, config.max_seq_len, num_classes,
            curriculum=inverted_curriculum,
            operation_tokens=operation_tokens,
            bounded_phase=config.bounded_phase,
        ).to(config.device)
        print(f"  Hybrid params: {model_hybrid.count_params():,}")

        opt_hybrid = torch.optim.AdamW(model_hybrid.parameters(), lr=config.lr,
                                        weight_decay=config.weight_decay)

    if args.compare_curricula:
        # Standard curriculum: Quadratic-heavy early, Phase-heavy late (for comparison)
        standard_curriculum = list(reversed(curriculum))
        print(f"\n--- Hybrid Model (STANDARD CURRICULUM - for comparison) ---")
        print(f"  Curriculum: {' → '.join(f'L{i}:{r*100:.0f}%P' for i, r in enumerate(standard_curriculum))}")
        print(f"  Interpretation: Quadratic-heavy early → Phase-heavy late")

        model_hybrid_std = HybridTransformer(
            vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
            config.d_ff, config.dropout, config.max_seq_len, num_classes,
            curriculum=standard_curriculum,
            operation_tokens=operation_tokens,
            bounded_phase=config.bounded_phase,
        ).to(config.device)
        print(f"  Standard Hybrid params: {model_hybrid_std.count_params():,}")

        opt_hybrid_std = torch.optim.AdamW(model_hybrid_std.parameters(), lr=config.lr,
                                            weight_decay=config.weight_decay)

    # Protected Phase model (v5) - Phase accumulates, Quad queries
    model_protected = None
    opt_protected = None

    if args.protected_phase:
        print(f"\n--- Protected Phase Model (v5) ---")
        print(f"  Architecture: Phase → Memory State → Quadratic Query")
        print(f"  Phase's job:  Accumulate bindings via O(n) cumsum")
        print(f"  Quad's job:   Query memory via O(n²) attention")
        print(f"  Key insight:  No gradient competition - they collaborate")

        model_protected = ProtectedPhaseTransformer(
            vocab.vocab_size, config.d_model, config.num_heads, config.num_layers,
            config.d_ff, config.dropout, config.max_seq_len, num_classes,
            operation_tokens=operation_tokens,
            bounded_phase=config.bounded_phase,
        ).to(config.device)
        print(f"  Protected params: {model_protected.count_params():,}")

        opt_protected = torch.optim.AdamW(model_protected.parameters(), lr=config.lr,
                                           weight_decay=config.weight_decay)

    # Optimizers
    opt_quad = torch.optim.AdamW(model_quad.parameters(), lr=config.lr,
                                  weight_decay=config.weight_decay)
    opt_phase = torch.optim.AdamW(model_phase.parameters(), lr=config.lr,
                                   weight_decay=config.weight_decay)

    # Training
    print(f"\n--- Training for {config.num_steps} steps ---")
    train_iter = iter(train_loader)
    step = 0

    # Loss tracking for training dynamics analysis
    loss_history = {
        "quad": [],
        "phase": [],
        "hybrid": [],
        "hybrid_std": [],
        "protected": [],
    }

    while step < config.num_steps:
        try:
            ids, targets, _ = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            ids, targets, _ = next(train_iter)

        ids, targets = ids.to(config.device), targets.to(config.device)

        # Convert targets to class indices
        target_idx = torch.tensor([
            vocab.entity_to_idx(t.item()) if t.item() in vocab.entities else 0
            for t in targets
        ], device=config.device)

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

        # Train hybrid (inverted curriculum)
        if model_hybrid is not None:
            model_hybrid.train()
            opt_hybrid.zero_grad()
            loss_h = F.cross_entropy(model_hybrid(ids), target_idx)
            loss_h.backward()
            opt_hybrid.step()

        # Train hybrid (standard curriculum - for comparison)
        if model_hybrid_std is not None:
            model_hybrid_std.train()
            opt_hybrid_std.zero_grad()
            loss_hs = F.cross_entropy(model_hybrid_std(ids), target_idx)
            loss_hs.backward()
            opt_hybrid_std.step()

        # Train protected phase (v5)
        loss_prot = None
        if model_protected is not None:
            model_protected.train()
            opt_protected.zero_grad()
            loss_prot = F.cross_entropy(model_protected(ids), target_idx)
            loss_prot.backward()
            opt_protected.step()

        # Track losses for training dynamics
        loss_history["quad"].append(loss_q.item())
        loss_history["phase"].append(loss_p.item())
        if model_hybrid is not None:
            loss_history["hybrid"].append(loss_h.item())
        if model_hybrid_std is not None:
            loss_history["hybrid_std"].append(loss_hs.item())
        if model_protected is not None:
            loss_history["protected"].append(loss_prot.item())

        step += 1

        if step % config.eval_every == 0 or step == config.num_steps:
            # Quick train accuracy check
            train_acc_q = evaluate(model_quad, train_loader, vocab, config.device)
            train_acc_p = evaluate(model_phase, train_loader, vocab, config.device)

            # Compute recent average loss (last eval_every steps)
            window = config.eval_every
            recent_loss_q = sum(loss_history["quad"][-window:]) / window
            recent_loss_p = sum(loss_history["phase"][-window:]) / window

            msg = f"Step {step:5d} | Acc: Q={train_acc_q:.3f} P={train_acc_p:.3f}"
            loss_msg = f" | Loss: Q={recent_loss_q:.3f} P={recent_loss_p:.3f}"

            if model_hybrid is not None:
                train_acc_h = evaluate(model_hybrid, train_loader, vocab, config.device)
                recent_loss_h = sum(loss_history["hybrid"][-window:]) / window
                msg += f" H={train_acc_h:.3f}"
                loss_msg += f" H={recent_loss_h:.3f}"
            if model_hybrid_std is not None:
                train_acc_hs = evaluate(model_hybrid_std, train_loader, vocab, config.device)
                recent_loss_hs = sum(loss_history["hybrid_std"][-window:]) / window
                msg += f" Hs={train_acc_hs:.3f}"
                loss_msg += f" Hs={recent_loss_hs:.3f}"
            if model_protected is not None:
                train_acc_prot = evaluate(model_protected, train_loader, vocab, config.device)
                recent_loss_prot = sum(loss_history["protected"][-window:]) / window
                msg += f" Prot={train_acc_prot:.3f}"
                loss_msg += f" Prot={recent_loss_prot:.3f}"

                # R_k health metrics
                health = model_protected.get_phase_health()
                msg += f" | R_k={health['r_k_mean']:.3f}±{health['r_k_std']:.3f}"

            print(msg + loss_msg)

    # ==========================================================================
    # TRAINING DYNAMICS ANALYSIS
    # ==========================================================================
    print("\n" + "=" * 70)
    print("TRAINING DYNAMICS ANALYSIS")
    print("=" * 70)

    def compute_loss_stats(losses, name, window=1000):
        """Compute loss statistics for training dynamics."""
        if not losses:
            return None
        early = losses[:window] if len(losses) >= window else losses
        late = losses[-window:] if len(losses) >= window else losses
        return {
            "name": name,
            "early_mean": sum(early) / len(early),
            "late_mean": sum(late) / len(late),
            "final": losses[-1],
            "improvement": (sum(early) / len(early)) - (sum(late) / len(late)),
        }

    print(f"\n--- Loss Dynamics (early vs late {min(1000, len(loss_history['quad']))} steps) ---")
    print(f"{'Model':<12} {'Early Loss':>12} {'Late Loss':>12} {'Improvement':>12}")
    print("-" * 50)

    for model_name in ["quad", "phase", "protected"]:
        if loss_history[model_name]:
            stats = compute_loss_stats(loss_history[model_name], model_name)
            print(f"{stats['name']:<12} {stats['early_mean']:>12.4f} {stats['late_mean']:>12.4f} {stats['improvement']:>+12.4f}")

    # Check for Phase plateau (red flag)
    if loss_history["protected"]:
        early_phase_loss = sum(loss_history["protected"][:min(2000, len(loss_history["protected"]))]) / min(2000, len(loss_history["protected"]))
        late_phase_loss = sum(loss_history["protected"][-1000:]) / min(1000, len(loss_history["protected"]))
        if early_phase_loss - late_phase_loss < 0.1:
            print(f"\n  ⚠️  WARNING: Protected Phase loss barely improved ({early_phase_loss:.4f} → {late_phase_loss:.4f})")
            print(f"     This may indicate Phase is not learning or Quad is bypassing Phase.")

    # R_k Health Report
    if model_protected is not None:
        print(f"\n--- Phase Health (R_k = amplitude) ---")
        health = model_protected.get_phase_health()
        print(f"  R_k mean:  {health['r_k_mean']:.4f}")
        print(f"  R_k std:   {health['r_k_std']:.4f}")
        print(f"  R_k range: [{health['r_k_min']:.4f}, {health['r_k_max']:.4f}]")

        # Interpret health
        if health['r_k_mean'] < 0.1:
            print(f"\n  🚨 R_k → 0: Phase COLLAPSED (amplitude too small)")
        elif health['r_k_mean'] > 0.9:
            print(f"\n  🚨 R_k → 1: Phase DEGENERATE (amplitude saturated)")
        elif 0.3 <= health['r_k_mean'] <= 0.7:
            print(f"\n  ✅ R_k in healthy range (0.3-0.7)")
        else:
            print(f"\n  ⚠️  R_k outside ideal range but not critical")

    # ==========================================================================
    # FINAL EVALUATION (SEPARATE REPORTING - NO AVERAGING)
    # ==========================================================================
    print("\n" + "=" * 70)
    print("FINAL RESULTS: GENERALIZATION TEST")
    print("=" * 70)

    # Train accuracy
    train_acc_q = evaluate(model_quad, train_loader, vocab, config.device)
    train_acc_p = evaluate(model_phase, train_loader, vocab, config.device)
    train_acc_h = evaluate(model_hybrid, train_loader, vocab, config.device) if model_hybrid else None
    train_acc_hs = evaluate(model_hybrid_std, train_loader, vocab, config.device) if model_hybrid_std else None
    train_acc_prot = evaluate(model_protected, train_loader, vocab, config.device) if model_protected else None

    print(f"\n--- Training Accuracy (should be high for all) ---")
    print(f"Quadratic:        {train_acc_q*100:.1f}%")
    print(f"Phase:            {train_acc_p*100:.1f}%")
    if train_acc_h is not None:
        print(f"Hybrid (Inv):     {train_acc_h*100:.1f}%")
    if train_acc_hs is not None:
        print(f"Hybrid (Std):     {train_acc_hs*100:.1f}%")
    if train_acc_prot is not None:
        print(f"Protected:        {train_acc_prot*100:.1f}%")

    # Per-split test accuracy (NO AVERAGING)
    results_quad = evaluate_all_splits(model_quad, test_loaders, vocab, config.device)
    results_phase = evaluate_all_splits(model_phase, test_loaders, vocab, config.device)
    results_hybrid = evaluate_all_splits(model_hybrid, test_loaders, vocab, config.device) if model_hybrid else None
    results_hybrid_std = evaluate_all_splits(model_hybrid_std, test_loaders, vocab, config.device) if model_hybrid_std else None
    results_protected = evaluate_all_splits(model_protected, test_loaders, vocab, config.device) if model_protected else None

    # Protected Phase results (v5)
    if model_protected is not None:
        print(f"\n--- PROTECTED PHASE RESULTS (v5) ---")
        print(f"    Architecture: Phase accumulates → Quad queries (no competition)")
        print(f"{'Split':<16} {'Quad':>8} {'Phase':>8} {'Protect':>8} {'Best':>8}")
        print("-" * 52)

        for split in [SplitType.TEST_ROLES, SplitType.TEST_ENTITIES,
                      SplitType.TEST_BOTH, SplitType.TEST_LONG, SplitType.TEST_PERSIST]:
            q = results_quad[split.value]
            p = results_phase[split.value]
            prot = results_protected[split.value]
            scores = {"Quad": q, "Phase": p, "Protect": prot}
            best = max(scores, key=scores.get)
            print(f"{split.value:<16} {q*100:>7.1f}% {p*100:>7.1f}% {prot*100:>7.1f}% {best:>8}")

        # Summary
        prot_avg = sum(results_protected.values()) / len(results_protected)
        q_avg = sum(results_quad.values()) / len(results_quad)
        p_avg = sum(results_phase.values()) / len(results_phase)

        print(f"\n  Average Test Accuracy:")
        print(f"    Quadratic:  {q_avg*100:.1f}%")
        print(f"    Pure Phase: {p_avg*100:.1f}%")
        print(f"    Protected:  {prot_avg*100:.1f}%")

        if prot_avg > max(q_avg, p_avg) + 0.02:
            print(f"\n  → PROTECTED PHASE WINS by {(prot_avg - max(q_avg, p_avg))*100:.1f}%")
            print(f"    Phase and Quadratic collaborate better than compete!")
        elif prot_avg > p_avg + 0.02:
            print(f"\n  → Protected beats Pure Phase by {(prot_avg - p_avg)*100:.1f}%")
            print(f"    Quadratic querying helps Phase's accumulated state")

    if model_hybrid is not None:
        print(f"\n--- Test Accuracy by Generalization Type (FULL COMPARISON) ---")
        if model_hybrid_std is not None:
            print(f"{'Split':<16} {'Quad':>8} {'Phase':>8} {'HybInv':>8} {'HybStd':>8} {'Best':>8}")
            print("-" * 64)
        else:
            print(f"{'Split':<16} {'Quad':>8} {'Phase':>8} {'HybInv':>8} {'Best':>8}")
            print("-" * 52)

        for split in [SplitType.TEST_ROLES, SplitType.TEST_ENTITIES,
                      SplitType.TEST_BOTH, SplitType.TEST_LONG, SplitType.TEST_PERSIST]:
            q = results_quad[split.value]
            p = results_phase[split.value]
            h = results_hybrid[split.value]
            scores = {"Quad": q, "Phase": p, "HybInv": h}

            if model_hybrid_std is not None:
                hs = results_hybrid_std[split.value]
                scores["HybStd"] = hs
                best = max(scores, key=scores.get)
                print(f"{split.value:<16} {q*100:>7.1f}% {p*100:>7.1f}% {h*100:>7.1f}% {hs*100:>7.1f}% {best:>8}")
            else:
                best = max(scores, key=scores.get)
                print(f"{split.value:<16} {q*100:>7.1f}% {p*100:>7.1f}% {h*100:>7.1f}% {best:>8}")

        # Summary: Which curriculum wins?
        if model_hybrid_std is not None:
            print(f"\n--- CURRICULUM COMPARISON SUMMARY ---")
            inv_avg = sum(results_hybrid.values()) / len(results_hybrid)
            std_avg = sum(results_hybrid_std.values()) / len(results_hybrid_std)
            q_avg = sum(results_quad.values()) / len(results_quad)
            p_avg = sum(results_phase.values()) / len(results_phase)

            print(f"Average Test Accuracy:")
            print(f"  Quadratic:        {q_avg*100:.1f}%")
            print(f"  Pure Phase:       {p_avg*100:.1f}%")
            print(f"  Hybrid (Inv):     {inv_avg*100:.1f}%  [Phase early → Quad late]")
            print(f"  Hybrid (Std):     {std_avg*100:.1f}%  [Quad early → Phase late]")

            if inv_avg > std_avg + 0.02:
                print(f"\n  → INVERTED CURRICULUM WINS by {(inv_avg - std_avg)*100:.1f}%")
                print(f"    Supports: Phase = STATE mechanism, Quadratic = REASONING mechanism")
            elif std_avg > inv_avg + 0.02:
                print(f"\n  → STANDARD CURRICULUM WINS by {(std_avg - inv_avg)*100:.1f}%")
                print(f"    Counter-evidence: Original hypothesis may be correct")
            else:
                print(f"\n  → CURRICULA ARE COMPARABLE (diff: {abs(inv_avg - std_avg)*100:.1f}%)")
    else:
        # Original output format without hybrid
        print(f"\n--- Test Accuracy by Generalization Type (NO AVERAGING) ---")
        print(f"{'Split':<20} {'Quadratic':>12} {'Phase':>12} {'Delta':>12}")
        print("-" * 56)

        for split in [SplitType.TEST_ROLES, SplitType.TEST_ENTITIES,
                      SplitType.TEST_BOTH, SplitType.TEST_LONG, SplitType.TEST_PERSIST]:
            q = results_quad[split.value]
            p = results_phase[split.value]
            delta = p - q
            marker = "**" if delta > 0.1 else ""
            print(f"{split.value:<20} {q*100:>11.1f}% {p*100:>11.1f}% {delta*100:>+11.1f}% {marker}")

    # Phase diagnostics
    print(f"\n--- Phase Health ---")
    model_phase.enable_diagnostics(True)
    # Run one batch to capture diagnostics
    with torch.no_grad():
        sample_ids, _, _ = next(iter(train_loader))
        _ = model_phase(sample_ids.to(config.device))
    r_k = model_phase.get_R_k()
    model_phase.enable_diagnostics(False)
    print(f"R_k (mean resultant length): {r_k:.4f}")
    print(f"  Interpretation: {'HEALTHY (diverse phases)' if r_k < 0.3 else 'COLLAPSED (phases aligned)'}")

    # Ablation (on test_roles split)
    print(f"\n--- CAUSALITY TEST: Phase Ablation (on test_roles) ---")
    test_roles_loader = test_loaders[SplitType.TEST_ROLES]
    ablation = run_ablation(model_phase, test_roles_loader, vocab, config.device)
    baseline = ablation["none"]

    print(f"{'Mode':<12} {'Accuracy':>12} {'Delta':>12}")
    print("-" * 36)
    for mode, acc in ablation.items():
        delta = acc - baseline
        print(f"{mode:<12} {acc*100:>11.1f}% {delta*100:>+11.1f}%")

    # ==========================================================================
    # HYBRID ABLATION TESTS (v4) - Is Phase decorative or useful in hybrids?
    # ==========================================================================
    ablation_hybrid_inv = None
    ablation_hybrid_std = None

    if model_hybrid is not None:
        print(f"\n--- HYBRID ABLATION: HybridInv (Phase early → Quad late) ---")
        print(f"    Testing if Phase in EARLY layers contributes or is decorative")
        ablation_hybrid_inv = run_ablation(model_hybrid, test_roles_loader, vocab, config.device)
        baseline_inv = ablation_hybrid_inv["none"]

        print(f"{'Mode':<12} {'Accuracy':>12} {'Delta':>12} {'Interpretation':<30}")
        print("-" * 70)
        for mode, acc in ablation_hybrid_inv.items():
            delta = acc - baseline_inv
            if mode == "none":
                interp = ""
            elif abs(delta) < 0.05:
                interp = "← Phase is DECORATIVE"
            elif delta < -0.15:
                interp = "← Phase is CRITICAL"
            else:
                interp = "← Phase contributes"
            print(f"{mode:<12} {acc*100:>11.1f}% {delta*100:>+11.1f}% {interp}")

    if model_hybrid_std is not None:
        print(f"\n--- HYBRID ABLATION: HybridStd (Quad early → Phase late) ---")
        print(f"    Testing if Phase in LATE layers contributes or is decorative")
        ablation_hybrid_std = run_ablation(model_hybrid_std, test_roles_loader, vocab, config.device)
        baseline_std = ablation_hybrid_std["none"]

        print(f"{'Mode':<12} {'Accuracy':>12} {'Delta':>12} {'Interpretation':<30}")
        print("-" * 70)
        for mode, acc in ablation_hybrid_std.items():
            delta = acc - baseline_std
            if mode == "none":
                interp = ""
            elif abs(delta) < 0.05:
                interp = "← Phase is DECORATIVE"
            elif delta < -0.15:
                interp = "← Phase is CRITICAL"
            else:
                interp = "← Phase contributes"
            print(f"{mode:<12} {acc*100:>11.1f}% {delta*100:>+11.1f}% {interp}")

    # Protected Phase ablation (v5)
    ablation_protected = None
    if model_protected is not None:
        print(f"\n--- PROTECTED PHASE ABLATION (v5) ---")
        print(f"    Testing if Phase contributes when it has PROTECTED role")
        print(f"    (Phase accumulates, Quad queries - no competition)")
        ablation_protected = run_ablation(model_protected, test_roles_loader, vocab, config.device)
        baseline_prot = ablation_protected["none"]

        print(f"{'Mode':<12} {'Accuracy':>12} {'Delta':>12} {'Interpretation':<30}")
        print("-" * 70)
        for mode, acc in ablation_protected.items():
            delta = acc - baseline_prot
            if mode == "none":
                interp = ""
            elif abs(delta) < 0.05:
                interp = "← Phase is DECORATIVE"
            elif delta < -0.15:
                interp = "← Phase is CRITICAL"
            else:
                interp = "← Phase contributes"
            print(f"{mode:<12} {acc*100:>11.1f}% {delta*100:>+11.1f}% {interp}")

        drop_prot = baseline_prot - ablation_protected["scramble"]
        print(f"\n  Protected Phase ablation drop: {drop_prot*100:>+.1f}%")
        if drop_prot > 0.15:
            print(f"  → Phase is ESSENTIAL in protected architecture!")
            print(f"  → No gradient competition = Phase learns meaningful representations")
        elif drop_prot > 0.05:
            print(f"  → Phase CONTRIBUTES in protected architecture")
        else:
            print(f"  → Phase still decorative even when protected")

    # ==========================================================================
    # PHASE ROTATION TEST - Does phase encode relational structure?
    # ==========================================================================
    if args.rotation_test:
        rotation_angles = [float(x) for x in args.rotation_angles.split(",")]
        print(f"\n" + "=" * 70)
        print("PHASE ROTATION TEST")
        print("=" * 70)
        print("\nHypothesis: If phase encodes roles, rotating φ_q should shift bindings.")
        print(f"Testing angles: {rotation_angles}")

        # Test pure Phase model
        rotation_phase = run_rotation_test(
            model_phase, test_roles_loader, vocab, config.device, rotation_angles
        )
        print_rotation_test_results(rotation_phase, "Pure Phase")

        # Test Hybrid models if available
        if model_hybrid is not None:
            rotation_hybrid = run_rotation_test(
                model_hybrid, test_roles_loader, vocab, config.device, rotation_angles
            )
            print_rotation_test_results(rotation_hybrid, "Hybrid (Inverted)")

        if model_hybrid_std is not None:
            rotation_hybrid_std = run_rotation_test(
                model_hybrid_std, test_roles_loader, vocab, config.device, rotation_angles
            )
            print_rotation_test_results(rotation_hybrid_std, "Hybrid (Standard)")

        if model_protected is not None:
            rotation_protected = run_rotation_test(
                model_protected, test_roles_loader, vocab, config.device, rotation_angles
            )
            print_rotation_test_results(rotation_protected, "Protected Phase")

        # Summary
        print(f"\n--- ROTATION TEST SUMMARY ---")
        print(f"  Pure Phase sensitivity:     {rotation_phase['sensitivity']*100:.2f}%")
        if model_hybrid is not None:
            print(f"  Hybrid (Inv) sensitivity:   {rotation_hybrid['sensitivity']*100:.2f}%")
        if model_hybrid_std is not None:
            print(f"  Hybrid (Std) sensitivity:   {rotation_hybrid_std['sensitivity']*100:.2f}%")
        if model_protected is not None:
            print(f"  Protected sensitivity:      {rotation_protected['sensitivity']*100:.2f}%")

        if rotation_phase['sensitivity'] > 0.10:
            print(f"\n  CONCLUSION: Phase encodes MEANINGFUL relational structure")
            print(f"             (rotation significantly affects binding retrieval)")
        elif rotation_phase['sensitivity'] > 0.03:
            print(f"\n  CONCLUSION: Phase shows PARTIAL relational encoding")
            print(f"             (moderate sensitivity to rotation)")
        else:
            print(f"\n  CONCLUSION: Phase is DECORATIVE (rotation has no effect)")
            print(f"             (phase not encoding relational structure)")

    # Summary comparison of ablation impacts
    if ablation_hybrid_inv is not None and ablation_hybrid_std is not None:
        print(f"\n--- ABLATION SUMMARY: Is Phase Decorative? ---")
        drop_pure = baseline - ablation["scramble"]
        drop_inv = ablation_hybrid_inv["none"] - ablation_hybrid_inv["scramble"]
        drop_std = ablation_hybrid_std["none"] - ablation_hybrid_std["scramble"]

        print(f"  Ablation drop (scramble):")
        print(f"    Pure Phase:   {drop_pure*100:>+6.1f}%  {'← Phase is PRIMARY' if drop_pure > 0.15 else ''}")
        print(f"    HybridInv:    {drop_inv*100:>+6.1f}%  {'← Phase EARLY matters' if drop_inv > 0.10 else '← Phase early is weak'}")
        print(f"    HybridStd:    {drop_std*100:>+6.1f}%  {'← Phase LATE matters' if drop_std > 0.10 else '← Phase late is DECORATIVE'}")

        print(f"\n  Conclusion:")
        if drop_std < 0.05:
            print(f"    → Phase is DECORATIVE when Quadratic dominates early")
            print(f"    → Quadratic 'steals' the learning signal")
            print(f"    → Consider: Protected Phase, Sequential, or Different Tasks")
        elif drop_inv < 0.05:
            print(f"    → Phase is DECORATIVE when it comes first")
            print(f"    → Phase can't establish useful representations alone")
            print(f"    → Quadratic late can compensate")
        elif drop_inv > drop_std:
            print(f"    → Phase EARLY contributes more than Phase LATE")
            print(f"    → Supports: Phase = state capture mechanism")
        else:
            print(f"    → Phase LATE contributes more than Phase EARLY")
            print(f"    → Supports: Phase = retrieval mechanism")

    # ==========================================================================
    # SCIENTIFIC VERDICT
    # ==========================================================================
    print("\n" + "=" * 70)
    print("SCIENTIFIC VERDICT")
    print("=" * 70)

    # Compute average test accuracy
    avg_test_q = sum(results_quad.values()) / len(results_quad)
    avg_test_p = sum(results_phase.values()) / len(results_phase)
    avg_test_h = sum(results_hybrid.values()) / len(results_hybrid) if results_hybrid else None
    avg_test_hs = sum(results_hybrid_std.values()) / len(results_hybrid_std) if results_hybrid_std else None

    # Criteria
    quad_memorizes = train_acc_q > 0.85
    quad_fails_generalization = avg_test_q < 0.50
    phase_generalizes = avg_test_p > avg_test_q + 0.15
    phase_is_causal = (baseline - ablation["scramble"]) > 0.1 or (baseline - ablation["freeze"]) > 0.1

    print(f"\nCriteria Check:")
    print(f"  [{'PASS' if quad_memorizes else 'FAIL'}] Quadratic memorizes training ({train_acc_q*100:.1f}% > 85%)")
    print(f"  [{'PASS' if quad_fails_generalization else 'FAIL'}] Quadratic fails generalization ({avg_test_q*100:.1f}% < 50%)")
    print(f"  [{'PASS' if phase_generalizes else 'FAIL'}] Phase outperforms quadratic by >15% ({(avg_test_p - avg_test_q)*100:.1f}%)")
    print(f"  [{'PASS' if phase_is_causal else 'FAIL'}] Phase ablation causes significant drops")

    # NEW: Inverted curriculum hypothesis (v3)
    if results_hybrid is not None:
        hybrid_beats_both = avg_test_h > max(avg_test_q, avg_test_p) + 0.02
        print(f"  [{'PASS' if hybrid_beats_both else 'FAIL'}] Hybrid (inverted) beats both pure models ({avg_test_h*100:.1f}% > {max(avg_test_q, avg_test_p)*100:.1f}%)")

        if results_hybrid_std is not None:
            inverted_beats_standard = avg_test_h > avg_test_hs + 0.02
            print(f"  [{'PASS' if inverted_beats_standard else 'FAIL'}] Inverted curriculum beats standard ({avg_test_h*100:.1f}% > {avg_test_hs*100:.1f}%)")

    # Verdict logic
    if results_hybrid is not None and results_hybrid_std is not None:
        # v3 verdict: Test the STATE vs REASONING hypothesis
        if avg_test_h > max(avg_test_q, avg_test_p, avg_test_hs) + 0.02:
            print("\n" + "=" * 70)
            print("[INVERTED CURRICULUM HYPOTHESIS SUPPORTED]")
            print("=" * 70)
            print("The Hybrid model with INVERTED curriculum achieves best generalization:")
            print(f"  - Phase early (state capture): {curriculum[0]*100:.0f}% → {curriculum[-1]*100:.0f}%")
            print(f"  - Quadratic late (reasoning):  {(1-curriculum[0])*100:.0f}% → {(1-curriculum[-1])*100:.0f}%")
            print(f"\nThis supports the hypothesis:")
            print(f"  PhaseAttention = STATE mechanism (O(n) memory)")
            print(f"  Quadratic      = REASONING mechanism (O(n²) attention)")
            print(f"\nOptimal architecture: Phase-heavy early layers + Quadratic-heavy late layers")
        elif avg_test_h > avg_test_hs + 0.02:
            print("\n[INVERTED > STANDARD]")
            print("Inverted curriculum outperforms standard, supporting Phase-as-state hypothesis.")
            print("But hybrid doesn't beat pure models — consider tuning curriculum ratios.")
        elif avg_test_hs > avg_test_h + 0.02:
            print("\n[STANDARD > INVERTED]")
            print("Standard curriculum outperforms inverted — counter to the hypothesis.")
            print("Phase may be better for reasoning after all, or task requires different mixing.")
        else:
            print("\n[CURRICULA COMPARABLE]")
            print("No significant difference between inverted and standard curriculum.")
            print("Try more extreme ratios: --curriculum 0.95,0.8,0.2,0.05")
    elif quad_memorizes and quad_fails_generalization and phase_generalizes and phase_is_causal:
        print("\n" + "=" * 70)
        print("[HYPOTHESIS STRONGLY SUPPORTED]")
        print("=" * 70)
        print("PhaseAttention demonstrates TRUE RELATIONAL GENERALIZATION:")
        print(f"  - Quadratic memorizes ({train_acc_q*100:.1f}%) but fails to generalize ({avg_test_q*100:.1f}%)")
        print(f"  - Phase generalizes significantly better ({avg_test_p*100:.1f}%)")
        print(f"  - Phase is causally necessary (ablations hurt performance)")
        print("\nThis is strong evidence that phase encodes RELATIONAL STRUCTURE,")
        print("not token-specific patterns.")
    elif phase_generalizes and phase_is_causal:
        print("\n[HYPOTHESIS SUPPORTED]")
        print("Phase shows generalization advantage, but quadratic didn't fail as hard as expected.")
        print("Consider increasing chain length or bind_ratio.")
    elif not quad_fails_generalization:
        print("\n[DATASET TOO EASY]")
        print(f"Quadratic achieved {avg_test_q*100:.1f}% on test — should be <50%.")
        print("Try: --test-chain-min 7 --test-chain-max 10 --bind-ratio 0.8")
    else:
        print("\n[INCONCLUSIVE]")
        print("Results do not clearly support or refute the hypothesis.")
        if results_hybrid is None:
            print("\nTry: --compare-curricula to test Phase-as-state hypothesis")

    print("=" * 70)


if __name__ == "__main__":
    main()
