# Variable Binding and Unification: The Missing Symbolic Core

**Document Version**: 1.0.0
**Date**: January 2026
**Status**: Critical Design Specification
**Purpose**: Bridge the fundamental gap between neural and symbolic reasoning in Phase-Quad

---

## Executive Summary

Phase-Quad provides "soft symbolic" reasoning through the 32D Sovereign State, IMR logic templates, and Vritti validation. However, it lacks the two **foundational operations** of true symbolic AI:

1. **Variable Binding**: Associating a symbol (variable) with a value
2. **Unification**: Finding substitutions that make two expressions identical

Without these, Phase-Quad cannot perform:
- Logical inference with variables (∀x: P(x) → Q(x))
- Pattern matching with wildcards
- Compositional generalization
- Proof construction
- Constraint satisfaction

This document specifies how to add differentiable variable binding and unification to Phase-Quad while preserving end-to-end trainability.

---

## Part 1: The Problem

### 1.1 What Variable Binding Is

**Definition**: Variable binding associates a **symbol** (variable name) with a **value** (entity, number, concept).

```
SYMBOLIC AI:
  X = 5
  Y = X + 3
  → Y = 8

  Binding: {X → 5, Y → 8}

NEURAL AI (Current):
  "5" → embedding_5
  "X + 3" → embedding_expression
  → No explicit binding, just vector similarity
```

**Why it matters**:
```
Query: "If John gave Mary a book, who received the book?"

SYMBOLIC:
  gave(John, Mary, book)
  → receiver(gave(X, Y, Z)) = Y
  → Unify: X=John, Y=Mary, Z=book
  → Answer: Mary

NEURAL (Current):
  Attention over "John gave Mary a book"
  → Soft attention to "Mary" (hopefully)
  → No explicit variable binding, can fail on novel patterns
```

### 1.2 What Unification Is

**Definition**: Unification finds a **substitution** σ such that applying σ to two expressions makes them identical.

```
Expression 1: parent(X, Y)
Expression 2: parent(john, mary)

Unification:
  σ = {X → john, Y → mary}
  parent(X, Y)[σ] = parent(john, mary) ✓

More complex:
  Expression 1: f(X, g(Y))
  Expression 2: f(a, g(b))

  σ = {X → a, Y → b}
  f(X, g(Y))[σ] = f(a, g(b)) ✓
```

**Why it matters**:
```
Rule: ∀X,Y: parent(X,Y) ∧ parent(Y,Z) → grandparent(X,Z)

Facts:
  parent(alice, bob)
  parent(bob, charlie)

Query: grandparent(alice, charlie)?

SYMBOLIC UNIFICATION:
  1. Match parent(X,Y) with parent(alice, bob) → {X→alice, Y→bob}
  2. Match parent(Y,Z) with parent(bob, charlie) → {Y→bob, Z→charlie}
  3. Consistent: Y=bob in both
  4. Conclude: grandparent(alice, charlie) = True

NEURAL (Current):
  Soft pattern matching, may work on common patterns
  Fails on novel entity combinations
```

### 1.3 Current Phase-Quad Limitations

| Capability | Symbolic AI | Phase-Quad Current | Gap |
|------------|-------------|-------------------|-----|
| Variable declaration | X = value | None | ❌ Complete |
| Variable reference | use X later | Attention (soft) | ⚠️ Implicit |
| Pattern matching | f(X, Y) matches f(1, 2) | Embedding similarity | ⚠️ Approximate |
| Unification | Find σ for A[σ] = B | None | ❌ Complete |
| Substitution | Apply σ to expression | None | ❌ Complete |
| Scope management | Local vs global vars | None | ❌ Complete |
| Compositional generalization | Novel combinations | Limited | ⚠️ Weak |

---

## Part 2: Design Requirements

### 2.1 Must-Have Properties

1. **Differentiable**: Must support gradient-based training
2. **Scalable**: Must work with large vocabularies and long sequences
3. **Compositional**: Must handle nested structures
4. **Integrated**: Must work with existing Phase-Quad components
5. **Interpretable**: Bindings must be inspectable

### 2.2 Nice-to-Have Properties

1. **Typed**: Variables have types (entity, number, predicate)
2. **Scoped**: Local bindings don't pollute global state
3. **Reversible**: Can unbind and rebind
4. **Uncertain**: Support probabilistic bindings

---

## Part 3: Proposed Architecture

### 3.1 Neural Binding Memory (NBM)

A differentiable key-value memory that implements variable binding.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    NEURAL BINDING MEMORY (NBM)                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  STRUCTURE:                                                                     │
│  ══════════                                                                     │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  BINDING SLOTS (N slots, e.g., N=32)                                    │   │
│  │                                                                         │   │
│  │  Slot 0: [key_0, value_0, strength_0, type_0, scope_0]                  │   │
│  │  Slot 1: [key_1, value_1, strength_1, type_1, scope_1]                  │   │
│  │  ...                                                                    │   │
│  │  Slot N: [key_N, value_N, strength_N, type_N, scope_N]                  │   │
│  │                                                                         │   │
│  │  key_i ∈ ℝ^d_key     : Variable name embedding                          │   │
│  │  value_i ∈ ℝ^d_value : Bound value embedding                            │   │
│  │  strength_i ∈ [0,1]  : Binding confidence                               │   │
│  │  type_i ∈ ℝ^d_type   : Variable type embedding                          │   │
│  │  scope_i ∈ ℤ         : Scope level (0=global, 1+=local)                 │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  OPERATIONS:                                                                    │
│  ═══════════                                                                    │
│                                                                                 │
│  1. BIND(key, value, type, scope):                                              │
│     - Find empty slot or lowest-strength slot                                   │
│     - Write: slot.key = key, slot.value = value                                │
│     - Set: slot.strength = 1.0, slot.type = type, slot.scope = scope           │
│                                                                                 │
│  2. LOOKUP(query_key) → (value, strength):                                      │
│     - Compute attention: α_i = softmax(query_key · key_i / √d)                 │
│     - Return: value = Σ α_i * value_i, strength = Σ α_i * strength_i           │
│                                                                                 │
│  3. UNBIND(key):                                                                │
│     - Find slot with matching key                                               │
│     - Set: slot.strength = 0.0 (soft delete)                                   │
│                                                                                 │
│  4. SCOPE_PUSH():                                                               │
│     - Increment scope level                                                     │
│     - New bindings go to higher scope                                           │
│                                                                                 │
│  5. SCOPE_POP():                                                                │
│     - Decrement scope level                                                     │
│     - Zero out bindings at popped scope                                         │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Implementation

```python
class NeuralBindingMemory(nn.Module):
    """
    Differentiable variable binding memory.

    Implements symbolic variable binding in a neural-compatible way:
    - Soft attention for variable lookup
    - Gradient-friendly binding operations
    - Scope management for local/global variables
    """

    def __init__(
        self,
        n_slots: int = 32,
        d_key: int = 64,
        d_value: int = 256,
        d_type: int = 16,
    ):
        super().__init__()
        self.n_slots = n_slots
        self.d_key = d_key
        self.d_value = d_value
        self.d_type = d_type

        # Binding memory
        self.keys = nn.Parameter(torch.zeros(n_slots, d_key))
        self.values = nn.Parameter(torch.zeros(n_slots, d_value))
        self.strengths = nn.Parameter(torch.zeros(n_slots))
        self.types = nn.Parameter(torch.zeros(n_slots, d_type))
        self.scopes = nn.Parameter(torch.zeros(n_slots))

        # Binding controller
        self.bind_gate = nn.Linear(d_key + d_value, 1)
        self.slot_selector = nn.Linear(d_key, n_slots)

        # Type embeddings
        self.type_embeddings = nn.Embedding(8, d_type)  # 8 basic types

        # Initialize
        self._reset_memory()

    def _reset_memory(self):
        """Reset all bindings."""
        nn.init.zeros_(self.keys)
        nn.init.zeros_(self.values)
        nn.init.zeros_(self.strengths)
        nn.init.zeros_(self.types)
        nn.init.zeros_(self.scopes)

    def bind(
        self,
        key: torch.Tensor,      # [B, d_key] variable name
        value: torch.Tensor,    # [B, d_value] bound value
        var_type: int = 0,      # Variable type index
        scope: int = 0,         # Scope level
    ) -> torch.Tensor:
        """
        Bind a variable to a value.

        Differentiable via soft slot selection.

        Returns:
            binding_strength: How strongly the binding was made
        """
        B = key.shape[0]

        # Compute binding gate (should we bind?)
        gate_input = torch.cat([key, value], dim=-1)
        gate = torch.sigmoid(self.bind_gate(gate_input))  # [B, 1]

        # Select slot (soft attention over slots)
        # Prefer empty slots (low strength) and matching keys
        key_similarity = torch.matmul(key, self.keys.T)  # [B, n_slots]
        emptiness = 1.0 - self.strengths.unsqueeze(0)     # [1, n_slots]
        slot_scores = key_similarity + emptiness * 2.0    # Prefer empty
        slot_weights = F.softmax(slot_scores, dim=-1)     # [B, n_slots]

        # Update memory (soft write)
        # keys[slot] += gate * slot_weight * (key - keys[slot])
        for slot in range(self.n_slots):
            w = slot_weights[:, slot:slot+1] * gate  # [B, 1]

            # Soft update keys
            key_delta = key - self.keys[slot:slot+1]
            self.keys.data[slot] += (w.mean() * key_delta.mean(dim=0)).detach()

            # Soft update values
            value_delta = value - self.values[slot:slot+1]
            self.values.data[slot] += (w.mean() * value_delta.mean(dim=0)).detach()

            # Update strength
            self.strengths.data[slot] = max(
                self.strengths.data[slot],
                (w.mean() * gate.mean()).item()
            )

            # Update type and scope
            if (w.mean() * gate.mean()).item() > 0.5:
                self.types.data[slot] = self.type_embeddings.weight[var_type].detach()
                self.scopes.data[slot] = scope

        return gate.squeeze(-1)

    def lookup(
        self,
        query_key: torch.Tensor,  # [B, d_key]
        scope_mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Look up a variable binding.

        Returns:
            value: Retrieved value (weighted by attention)
            confidence: Lookup confidence (0 = not found, 1 = certain)
        """
        # Compute attention over slots
        attention = torch.matmul(query_key, self.keys.T)  # [B, n_slots]
        attention = attention / (self.d_key ** 0.5)

        # Mask by strength (ignore unbound slots)
        strength_mask = self.strengths.unsqueeze(0)  # [1, n_slots]
        attention = attention + torch.log(strength_mask + 1e-10)

        # Mask by scope if provided
        if scope_mask is not None:
            attention = attention.masked_fill(~scope_mask, float('-inf'))

        attention = F.softmax(attention, dim=-1)  # [B, n_slots]

        # Retrieve value
        value = torch.matmul(attention, self.values)  # [B, d_value]

        # Compute confidence (weighted strength)
        confidence = (attention * self.strengths.unsqueeze(0)).sum(dim=-1)

        return value, confidence

    def get_bindings_dict(self) -> Dict[str, Any]:
        """Export current bindings for inspection."""
        bindings = []
        for i in range(self.n_slots):
            if self.strengths[i] > 0.1:
                bindings.append({
                    'slot': i,
                    'key_norm': self.keys[i].norm().item(),
                    'value_norm': self.values[i].norm().item(),
                    'strength': self.strengths[i].item(),
                    'scope': int(self.scopes[i].item()),
                })
        return {'bindings': bindings, 'n_active': len(bindings)}


class TypedVariable:
    """Type system for variables."""

    TYPES = {
        0: 'ANY',       # Untyped
        1: 'ENTITY',    # Named entity (person, place, thing)
        2: 'NUMBER',    # Numeric value
        3: 'PREDICATE', # Relation or function
        4: 'LIST',      # Sequence of values
        5: 'BOOLEAN',   # True/False
        6: 'STRING',    # Text
        7: 'COMPOUND',  # Nested structure
    }

    @staticmethod
    def compatible(type1: int, type2: int) -> bool:
        """Check if two types are compatible for unification."""
        if type1 == 0 or type2 == 0:  # ANY matches anything
            return True
        return type1 == type2
```

### 3.3 Differentiable Unification

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    DIFFERENTIABLE UNIFICATION                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  CLASSICAL UNIFICATION (Robinson's Algorithm):                                  │
│  ═════════════════════════════════════════════                                  │
│  Input: Two terms t1, t2                                                        │
│  Output: Most General Unifier (MGU) σ, or FAIL                                  │
│                                                                                 │
│  Algorithm:                                                                     │
│    1. If t1 = t2, return {}                                                     │
│    2. If t1 is variable X, return {X → t2}                                      │
│    3. If t2 is variable Y, return {Y → t1}                                      │
│    4. If t1 = f(s1,...,sn) and t2 = f(r1,...,rn):                               │
│       - Recursively unify si with ri                                            │
│       - Compose substitutions                                                   │
│    5. Otherwise FAIL                                                            │
│                                                                                 │
│  PROBLEM: Not differentiable (discrete decisions, FAIL is not gradient)         │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  DIFFERENTIABLE UNIFICATION (Our Approach):                                     │
│  ══════════════════════════════════════════                                     │
│                                                                                 │
│  Key insight: Replace discrete matching with soft matching                      │
│               Replace FAIL with low confidence score                            │
│                                                                                 │
│  Input:                                                                         │
│    term1: TermEmbedding (structure + embeddings)                                │
│    term2: TermEmbedding (structure + embeddings)                                │
│                                                                                 │
│  Output:                                                                        │
│    substitution: Dict[VarEmbedding → ValueEmbedding]                            │
│    confidence: float in [0, 1] (1 = perfect unification)                        │
│                                                                                 │
│  Algorithm:                                                                     │
│                                                                                 │
│  1. STRUCTURAL ALIGNMENT:                                                       │
│     - Compute structure similarity: sim_struct = cos(struct1, struct2)          │
│     - If sim_struct < θ_struct: confidence *= sim_struct (soft fail)            │
│                                                                                 │
│  2. ARGUMENT MATCHING:                                                          │
│     - For each position i:                                                      │
│       - arg1_i, arg2_i = arguments at position i                                │
│       - If arg1_i is variable:                                                  │
│           - Add soft binding: substitution[arg1_i] = arg2_i                     │
│           - confidence *= binding_confidence                                    │
│       - Else if arg2_i is variable:                                             │
│           - Add soft binding: substitution[arg2_i] = arg1_i                     │
│           - confidence *= binding_confidence                                    │
│       - Else:                                                                   │
│           - Recursively unify arg1_i with arg2_i                                │
│           - confidence *= recursive_confidence                                  │
│                                                                                 │
│  3. CONSISTENCY CHECK:                                                          │
│     - For each variable X bound multiple times:                                 │
│       - Check value consistency: sim = cos(value1, value2)                      │
│       - confidence *= sim                                                       │
│                                                                                 │
│  4. RETURN (substitution, confidence)                                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.4 Term Representation

```python
@dataclass
class TermEmbedding:
    """
    Neural representation of a logical term.

    Supports:
    - Constants: f(a, b) where a, b are ground terms
    - Variables: f(X, Y) where X, Y are variables
    - Nested: f(g(X), h(a, Y))
    """

    # Functor/predicate embedding
    functor: torch.Tensor  # [d_functor]

    # Argument embeddings (variable or value)
    arguments: List['TermEmbedding']  # Recursive structure

    # Is this a variable?
    is_variable: bool = False

    # Variable ID (if is_variable)
    variable_id: Optional[int] = None

    # Confidence that this term is well-formed
    well_formed_score: float = 1.0

    @property
    def arity(self) -> int:
        return len(self.arguments)

    def flatten(self) -> torch.Tensor:
        """Flatten to single embedding for comparison."""
        if not self.arguments:
            return self.functor

        arg_embs = torch.stack([arg.flatten() for arg in self.arguments])
        combined = torch.cat([self.functor, arg_embs.mean(dim=0)])
        return combined


class DifferentiableUnifier(nn.Module):
    """
    Differentiable unification algorithm.

    Finds soft substitutions that make two terms similar.
    """

    def __init__(
        self,
        d_embedding: int = 256,
        d_functor: int = 64,
        structure_threshold: float = 0.5,
    ):
        super().__init__()
        self.d_embedding = d_embedding
        self.d_functor = d_functor
        self.structure_threshold = structure_threshold

        # Structure comparator
        self.struct_compare = nn.Bilinear(d_functor, d_functor, 1)

        # Argument aligner
        self.arg_aligner = nn.MultiheadAttention(d_embedding, num_heads=4)

        # Variable detector
        self.var_detector = nn.Linear(d_embedding, 1)

        # Binding memory for substitutions
        self.binding_memory = NeuralBindingMemory(
            n_slots=16,
            d_key=d_embedding,
            d_value=d_embedding,
        )

    def unify(
        self,
        term1: TermEmbedding,
        term2: TermEmbedding,
    ) -> Tuple[Dict[int, torch.Tensor], float]:
        """
        Compute differentiable unification.

        Args:
            term1: First term (may contain variables)
            term2: Second term (may contain variables)

        Returns:
            substitution: Dict mapping variable IDs to value embeddings
            confidence: Unification confidence (0 = fail, 1 = success)
        """
        substitution = {}
        confidence = 1.0

        # 1. Check structural compatibility
        struct_sim = self._structure_similarity(term1, term2)
        if struct_sim < self.structure_threshold:
            confidence *= struct_sim

        # 2. Handle variable cases
        if term1.is_variable:
            # X unifies with anything
            substitution[term1.variable_id] = term2.flatten()
            confidence *= self._occurs_check(term1.variable_id, term2)
            return substitution, confidence

        if term2.is_variable:
            # Anything unifies with Y
            substitution[term2.variable_id] = term1.flatten()
            confidence *= self._occurs_check(term2.variable_id, term1)
            return substitution, confidence

        # 3. Both are compound terms - check functor match
        functor_sim = F.cosine_similarity(
            term1.functor.unsqueeze(0),
            term2.functor.unsqueeze(0)
        ).item()
        confidence *= functor_sim

        # 4. Check arity match
        if term1.arity != term2.arity:
            # Soft penalty for arity mismatch
            arity_penalty = 1.0 / (1.0 + abs(term1.arity - term2.arity))
            confidence *= arity_penalty
            # Align arguments up to minimum arity
            min_arity = min(term1.arity, term2.arity)
        else:
            min_arity = term1.arity

        # 5. Recursively unify arguments
        for i in range(min_arity):
            arg_sub, arg_conf = self.unify(term1.arguments[i], term2.arguments[i])

            # Merge substitutions
            for var_id, value in arg_sub.items():
                if var_id in substitution:
                    # Check consistency
                    existing = substitution[var_id]
                    consistency = F.cosine_similarity(
                        existing.unsqueeze(0),
                        value.unsqueeze(0)
                    ).item()
                    confidence *= consistency

                    # Keep more confident binding
                    # (Could also average, but this is simpler)
                else:
                    substitution[var_id] = value

            confidence *= arg_conf

        return substitution, confidence

    def _structure_similarity(
        self,
        term1: TermEmbedding,
        term2: TermEmbedding,
    ) -> float:
        """Compute structural similarity between terms."""
        # Functor similarity
        functor_sim = self.struct_compare(
            term1.functor.unsqueeze(0),
            term2.functor.unsqueeze(0)
        ).sigmoid().item()

        # Arity similarity
        arity_sim = 1.0 / (1.0 + abs(term1.arity - term2.arity))

        return (functor_sim + arity_sim) / 2.0

    def _occurs_check(self, var_id: int, term: TermEmbedding) -> float:
        """
        Soft occurs check: penalize if variable occurs in term.

        Classical occurs check prevents X = f(X) which is infinite.
        We make this soft: low confidence instead of hard fail.
        """
        if term.is_variable and term.variable_id == var_id:
            return 0.1  # Self-reference: very low confidence

        for arg in term.arguments:
            if self._occurs_check(var_id, arg) < 0.5:
                return 0.3  # Nested self-reference: low confidence

        return 1.0  # No occurs violation

    def apply_substitution(
        self,
        term: TermEmbedding,
        substitution: Dict[int, torch.Tensor],
    ) -> TermEmbedding:
        """
        Apply substitution to a term.

        Replaces variables with their bound values.
        """
        if term.is_variable and term.variable_id in substitution:
            # Replace variable with bound value
            return TermEmbedding(
                functor=substitution[term.variable_id],
                arguments=[],
                is_variable=False,
            )

        if not term.arguments:
            return term

        # Recursively apply to arguments
        new_args = [
            self.apply_substitution(arg, substitution)
            for arg in term.arguments
        ]

        return TermEmbedding(
            functor=term.functor,
            arguments=new_args,
            is_variable=term.is_variable,
            variable_id=term.variable_id,
        )
```

### 3.5 Integration with Phase-Quad

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PHASE-QUAD + BINDING/UNIFICATION                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  INTEGRATION POINTS:                                                            │
│  ═══════════════════                                                            │
│                                                                                 │
│  1. QUAD PROPOSAL + BINDING MEMORY                                              │
│     ─────────────────────────────                                               │
│     Current: Quad retrieves from memory bank                                    │
│     Enhanced: Quad also retrieves from binding memory                           │
│                                                                                 │
│     quad_output = concat(                                                       │
│         quad_proposal(hidden_state, memory_bank),                               │
│         binding_memory.lookup(variable_query)                                   │
│     )                                                                           │
│                                                                                 │
│  2. PHASE INTEGRATOR + UNIFICATION                                              │
│     ────────────────────────────────                                            │
│     Current: Phase state accumulates via GRU                                    │
│     Enhanced: Phase state includes unification results                          │
│                                                                                 │
│     phase_state = GRU(                                                          │
│         phase_state_prev,                                                       │
│         concat(input, unification_result)                                       │
│     )                                                                           │
│                                                                                 │
│  3. IMR TEMPLATES + UNIFICATION                                                 │
│     ──────────────────────────────                                              │
│     Current: 5 fixed logic templates (DEDUCTION, etc.)                          │
│     Enhanced: Templates include unification patterns                            │
│                                                                                 │
│     DEDUCTION_UNIFIED:                                                          │
│       Pattern: ∀X: P(X) → Q(X)                                                  │
│       Fact: P(a)                                                                │
│       Unify: X = a                                                              │
│       Conclude: Q(a)                                                            │
│                                                                                 │
│  4. SRK LAYER 4 + BINDING                                                       │
│     ──────────────────────────                                                  │
│     Current: DNA Bridge grounds in Bhava space                                  │
│     Enhanced: Also extracts and binds entities                                  │
│                                                                                 │
│     Layer 4 operations:                                                         │
│       a. Ground in Bhava (existing)                                             │
│       b. Detect entities → bind to variables                                    │
│       c. Detect relations → create term structures                              │
│                                                                                 │
│  5. REFLECTIVE + UNIFICATION                                                    │
│     ─────────────────────────                                                   │
│     Current: Critic evaluates quality                                           │
│     Enhanced: Critic checks unification consistency                             │
│                                                                                 │
│     Quality = f(coherence, correctness, completeness,                           │
│                 BINDING_CONSISTENCY, UNIFICATION_VALID)                         │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.6 Symbolic Reasoning with Binding + Unification

```python
class SymbolicReasoningModule(nn.Module):
    """
    Symbolic reasoning using binding and unification.

    Extends Phase-Quad with true symbolic capabilities.
    """

    def __init__(
        self,
        d_model: int = 768,
        n_binding_slots: int = 32,
        n_rules: int = 100,
    ):
        super().__init__()

        # Binding memory
        self.binding_memory = NeuralBindingMemory(
            n_slots=n_binding_slots,
            d_key=d_model // 4,
            d_value=d_model,
        )

        # Unifier
        self.unifier = DifferentiableUnifier(
            d_embedding=d_model,
            d_functor=d_model // 4,
        )

        # Rule memory (learnable rule patterns)
        self.rule_patterns = nn.Parameter(torch.randn(n_rules, d_model))
        self.rule_conclusions = nn.Parameter(torch.randn(n_rules, d_model))

        # Entity detector
        self.entity_detector = nn.Linear(d_model, 1)

        # Relation detector
        self.relation_detector = nn.Linear(d_model * 2, d_model // 4)

        # Variable generator
        self.var_generator = nn.Linear(d_model, d_model // 4)

    def forward(
        self,
        hidden_states: torch.Tensor,  # [B, T, D]
        query: Optional[torch.Tensor] = None,  # [B, D] optional query
    ) -> Dict[str, Any]:
        """
        Apply symbolic reasoning to hidden states.

        Steps:
        1. Extract entities and bind to variables
        2. Extract relations and create terms
        3. Match against rule patterns (unification)
        4. Apply matched rules to derive conclusions
        5. Return enriched hidden states + reasoning trace
        """
        B, T, D = hidden_states.shape

        # 1. Extract entities
        entity_scores = self.entity_detector(hidden_states).squeeze(-1)  # [B, T]
        entity_mask = entity_scores > 0.5

        # Bind entities to variables
        for b in range(B):
            for t in range(T):
                if entity_mask[b, t]:
                    var_key = self.var_generator(hidden_states[b, t])
                    self.binding_memory.bind(
                        key=var_key.unsqueeze(0),
                        value=hidden_states[b, t:t+1],
                        var_type=1,  # ENTITY
                        scope=0,  # Global
                    )

        # 2. Extract relations (between consecutive entities)
        relations = []
        for b in range(B):
            entity_positions = entity_mask[b].nonzero().squeeze(-1)
            for i in range(len(entity_positions) - 1):
                pos1, pos2 = entity_positions[i], entity_positions[i + 1]
                rel_input = torch.cat([
                    hidden_states[b, pos1],
                    hidden_states[b, pos2]
                ])
                rel_embedding = self.relation_detector(rel_input)
                relations.append(TermEmbedding(
                    functor=rel_embedding,
                    arguments=[
                        TermEmbedding(functor=hidden_states[b, pos1], arguments=[]),
                        TermEmbedding(functor=hidden_states[b, pos2], arguments=[]),
                    ]
                ))

        # 3. Match against rules
        matched_rules = []
        for rel in relations:
            for rule_idx in range(self.rule_patterns.shape[0]):
                rule_pattern = TermEmbedding(
                    functor=self.rule_patterns[rule_idx, :D//4],
                    arguments=[
                        TermEmbedding(functor=torch.zeros(D), arguments=[], is_variable=True, variable_id=0),
                        TermEmbedding(functor=torch.zeros(D), arguments=[], is_variable=True, variable_id=1),
                    ]
                )

                substitution, confidence = self.unifier.unify(rule_pattern, rel)

                if confidence > 0.7:
                    matched_rules.append({
                        'rule_idx': rule_idx,
                        'substitution': substitution,
                        'confidence': confidence,
                    })

        # 4. Apply matched rules
        derived_facts = []
        for match in matched_rules:
            conclusion_pattern = TermEmbedding(
                functor=self.rule_conclusions[match['rule_idx']],
                arguments=[
                    TermEmbedding(functor=torch.zeros(D), arguments=[], is_variable=True, variable_id=0),
                    TermEmbedding(functor=torch.zeros(D), arguments=[], is_variable=True, variable_id=1),
                ]
            )

            derived = self.unifier.apply_substitution(
                conclusion_pattern,
                match['substitution']
            )
            derived_facts.append({
                'term': derived,
                'confidence': match['confidence'],
            })

        # 5. Answer query if provided
        query_answer = None
        if query is not None:
            query_term = TermEmbedding(
                functor=query[:, :D//4].mean(dim=0),
                arguments=[
                    TermEmbedding(functor=torch.zeros(D), arguments=[], is_variable=True, variable_id=99),
                ]
            )

            best_match = None
            best_confidence = 0.0

            for fact in derived_facts:
                sub, conf = self.unifier.unify(query_term, fact['term'])
                if conf > best_confidence:
                    best_confidence = conf
                    best_match = sub

            if best_match and 99 in best_match:
                query_answer = best_match[99]

        return {
            'hidden_states': hidden_states,
            'entities_found': entity_mask.sum().item(),
            'relations_found': len(relations),
            'rules_matched': len(matched_rules),
            'derived_facts': len(derived_facts),
            'query_answer': query_answer,
            'bindings': self.binding_memory.get_bindings_dict(),
        }
```

---

## Part 4: Training

### 4.1 Loss Functions

```python
class BindingUnificationLoss(nn.Module):
    """
    Loss functions for training binding and unification.
    """

    def __init__(self):
        super().__init__()

    def binding_loss(
        self,
        predicted_bindings: Dict[int, torch.Tensor],
        target_bindings: Dict[int, torch.Tensor],
    ) -> torch.Tensor:
        """
        Loss for variable binding accuracy.

        Penalizes:
        - Missing bindings
        - Incorrect bindings
        - Extra bindings
        """
        loss = 0.0

        # Penalize missing bindings
        for var_id, target_value in target_bindings.items():
            if var_id in predicted_bindings:
                pred_value = predicted_bindings[var_id]
                # Cosine distance
                loss += 1.0 - F.cosine_similarity(
                    pred_value.unsqueeze(0),
                    target_value.unsqueeze(0)
                ).mean()
            else:
                # Missing binding penalty
                loss += 1.0

        # Penalize extra bindings
        for var_id in predicted_bindings:
            if var_id not in target_bindings:
                loss += 0.5  # Smaller penalty for extra bindings

        return loss

    def unification_loss(
        self,
        predicted_confidence: float,
        should_unify: bool,
        predicted_substitution: Dict[int, torch.Tensor],
        target_substitution: Optional[Dict[int, torch.Tensor]],
    ) -> torch.Tensor:
        """
        Loss for unification accuracy.

        Penalizes:
        - False positives (unified when shouldn't)
        - False negatives (didn't unify when should)
        - Incorrect substitutions
        """
        loss = 0.0

        # Confidence loss
        target_confidence = 1.0 if should_unify else 0.0
        loss += (predicted_confidence - target_confidence) ** 2

        # Substitution loss (if should unify)
        if should_unify and target_substitution is not None:
            loss += self.binding_loss(predicted_substitution, target_substitution)

        return torch.tensor(loss)

    def consistency_loss(
        self,
        binding_memory: NeuralBindingMemory,
    ) -> torch.Tensor:
        """
        Loss for binding consistency.

        Penalizes:
        - Same variable bound to different values
        - Circular bindings
        """
        loss = 0.0

        # Check for duplicate keys with different values
        keys = binding_memory.keys
        values = binding_memory.values
        strengths = binding_memory.strengths

        for i in range(binding_memory.n_slots):
            if strengths[i] < 0.1:
                continue
            for j in range(i + 1, binding_memory.n_slots):
                if strengths[j] < 0.1:
                    continue

                # Key similarity
                key_sim = F.cosine_similarity(
                    keys[i].unsqueeze(0),
                    keys[j].unsqueeze(0)
                ).item()

                if key_sim > 0.9:  # Same variable
                    # Value should be similar
                    value_sim = F.cosine_similarity(
                        values[i].unsqueeze(0),
                        values[j].unsqueeze(0)
                    ).item()

                    loss += (1.0 - value_sim) * key_sim

        return torch.tensor(loss)
```

### 4.2 Training Data

```python
class BindingUnificationDataset:
    """
    Dataset for training binding and unification.

    Includes:
    - Simple bindings: "X = 5" → {X → 5}
    - Unification examples: "parent(X, Y)" + "parent(john, mary)" → {X→john, Y→mary}
    - Inference chains: "parent(john, mary)" + "parent(mary, bob)" → "grandparent(john, bob)"
    """

    @staticmethod
    def generate_binding_examples(n: int = 1000) -> List[Dict]:
        """Generate simple binding examples."""
        examples = []

        for _ in range(n):
            # Generate random entity
            entity = random.choice(['john', 'mary', 'alice', 'bob', 'paris', 'london'])
            var_name = random.choice(['X', 'Y', 'Z', 'W'])

            examples.append({
                'input': f"{var_name} = {entity}",
                'target_bindings': {var_name: entity},
            })

        return examples

    @staticmethod
    def generate_unification_examples(n: int = 1000) -> List[Dict]:
        """Generate unification examples."""
        examples = []

        predicates = ['parent', 'friend', 'loves', 'knows', 'owns']
        entities = ['john', 'mary', 'alice', 'bob']

        for _ in range(n):
            pred = random.choice(predicates)
            e1, e2 = random.sample(entities, 2)

            # Pattern with variables
            pattern = f"{pred}(X, Y)"
            # Ground instance
            instance = f"{pred}({e1}, {e2})"

            examples.append({
                'pattern': pattern,
                'instance': instance,
                'should_unify': True,
                'target_substitution': {'X': e1, 'Y': e2},
            })

            # Negative example (different predicate)
            other_pred = random.choice([p for p in predicates if p != pred])
            examples.append({
                'pattern': pattern,
                'instance': f"{other_pred}({e1}, {e2})",
                'should_unify': False,
                'target_substitution': None,
            })

        return examples

    @staticmethod
    def generate_inference_examples(n: int = 1000) -> List[Dict]:
        """Generate inference chain examples."""
        examples = []

        # Grandparent rule
        for _ in range(n // 2):
            names = random.sample(['alice', 'bob', 'carol', 'dave'], 3)

            examples.append({
                'facts': [
                    f"parent({names[0]}, {names[1]})",
                    f"parent({names[1]}, {names[2]})",
                ],
                'rule': "∀X,Y,Z: parent(X,Y) ∧ parent(Y,Z) → grandparent(X,Z)",
                'query': f"grandparent({names[0]}, {names[2]})?",
                'answer': True,
            })

        # Sibling rule
        for _ in range(n // 2):
            names = random.sample(['alice', 'bob', 'carol', 'dave'], 3)

            examples.append({
                'facts': [
                    f"parent({names[0]}, {names[1]})",
                    f"parent({names[0]}, {names[2]})",
                ],
                'rule': "∀X,Y,Z: parent(X,Y) ∧ parent(X,Z) ∧ Y≠Z → sibling(Y,Z)",
                'query': f"sibling({names[1]}, {names[2]})?",
                'answer': True,
            })

        return examples
```

---

## Part 5: Explainability

### 5.1 Binding Trace

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    BINDING TRACE EXAMPLE                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  INPUT: "John gave Mary a book. Who received the book?"                         │
│                                                                                 │
│  STEP 1: ENTITY EXTRACTION                                                      │
│  ══════════════════════════                                                     │
│  Detected entities: ["John", "Mary", "book"]                                    │
│  Entity scores: [0.95, 0.92, 0.88]                                              │
│                                                                                 │
│  STEP 2: BINDING                                                                │
│  ═══════════════                                                                │
│  BIND(X_0, "John", type=ENTITY, scope=0) → strength=0.95                        │
│  BIND(X_1, "Mary", type=ENTITY, scope=0) → strength=0.92                        │
│  BIND(X_2, "book", type=ENTITY, scope=0) → strength=0.88                        │
│                                                                                 │
│  STEP 3: RELATION EXTRACTION                                                    │
│  ═══════════════════════════                                                    │
│  Detected: gave(X_0, X_1, X_2)                                                  │
│  Confidence: 0.91                                                               │
│                                                                                 │
│  STEP 4: RULE MATCHING                                                          │
│  ══════════════════════                                                         │
│  Rule: gave(GIVER, RECEIVER, OBJECT) → received(RECEIVER, OBJECT)               │
│  Unification:                                                                   │
│    GIVER ← X_0 ("John")                                                         │
│    RECEIVER ← X_1 ("Mary")                                                      │
│    OBJECT ← X_2 ("book")                                                        │
│  Confidence: 0.89                                                               │
│                                                                                 │
│  STEP 5: INFERENCE                                                              │
│  ═════════════════                                                              │
│  Derived: received(X_1, X_2)                                                    │
│  Substituted: received("Mary", "book")                                          │
│  Confidence: 0.89                                                               │
│                                                                                 │
│  STEP 6: QUERY ANSWERING                                                        │
│  ═══════════════════════                                                        │
│  Query: "Who received the book?"                                                │
│  Pattern: received(WHO, "book")                                                 │
│  Unify with: received("Mary", "book")                                           │
│  WHO ← "Mary"                                                                   │
│                                                                                 │
│  ANSWER: "Mary"                                                                 │
│  Confidence: 0.89                                                               │
│                                                                                 │
│  BINDING MEMORY STATE:                                                          │
│  ═════════════════════                                                          │
│  Slot 0: X_0 → "John"  (strength=0.95, type=ENTITY, scope=0)                   │
│  Slot 1: X_1 → "Mary"  (strength=0.92, type=ENTITY, scope=0)                   │
│  Slot 2: X_2 → "book"  (strength=0.88, type=ENTITY, scope=0)                   │
│  Slot 3: GIVER → X_0   (strength=0.89, type=VAR, scope=1)                      │
│  Slot 4: RECEIVER → X_1 (strength=0.89, type=VAR, scope=1)                     │
│  Slot 5: OBJECT → X_2  (strength=0.89, type=VAR, scope=1)                      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 6: Implementation Roadmap

### Phase 1: Neural Binding Memory (0-3 months)

| Deliverable | Effort | Impact |
|-------------|--------|--------|
| NeuralBindingMemory implementation | High | Critical |
| Integration with Quad Proposal | Medium | High |
| Binding loss functions | Medium | High |
| Training data generation | Medium | High |
| Unit tests and validation | Medium | Medium |

### Phase 2: Differentiable Unification (3-6 months)

| Deliverable | Effort | Impact |
|-------------|--------|--------|
| TermEmbedding representation | Medium | Critical |
| DifferentiableUnifier implementation | Very High | Critical |
| Soft occurs check | Medium | High |
| Unification loss functions | Medium | High |
| Integration with IMR templates | High | Very High |

### Phase 3: Symbolic Reasoning Module (6-9 months)

| Deliverable | Effort | Impact |
|-------------|--------|--------|
| Entity/relation extraction | High | High |
| Rule matching with unification | Very High | Critical |
| Inference chain execution | Very High | Critical |
| Query answering | High | High |
| Integration with SRK | High | Very High |

### Phase 4: Training and Evaluation (9-12 months)

| Deliverable | Effort | Impact |
|-------------|--------|--------|
| Large-scale training data | High | High |
| Compositional generalization benchmarks | High | Very High |
| Proof construction evaluation | High | Very High |
| Integration with Reflective Phase-Quad | Medium | High |
| Production deployment | Medium | High |

---

## Conclusion

Variable binding and unification are the **missing core** of symbolic reasoning in Phase-Quad. This document specifies:

1. **Neural Binding Memory (NBM)**: Differentiable key-value store for variable bindings
2. **Differentiable Unification**: Soft matching that replaces FAIL with low confidence
3. **Term Representation**: Neural encoding of logical terms with variables
4. **Integration Points**: How binding/unification connects to existing Phase-Quad components
5. **Training Strategy**: Loss functions and data generation for learning binding/unification
6. **Explainability**: Complete trace of binding and unification operations

With these additions, Phase-Quad would achieve **true symbolic reasoning capability** while maintaining differentiability, enabling:
- Logical inference with variables
- Compositional generalization to novel entity combinations
- Proof construction and validation
- Constraint satisfaction
- Formal verification

This bridges the final gap between neural pattern matching and symbolic logical reasoning.

---

*Document prepared for Phase-Quad Architecture Team*
*Symbolu AI Systems*
*January 2026*
