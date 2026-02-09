# Phase Quad Structured Reasoning: Engineering Specification

**Version:** 0.1.0 (Proposal)
**Status:** Design Document — Not Yet Implemented
**Depends on:** V11.0.0 Dimensional Separation, V10.4 Proposal Mode
**Goal:** Model-internal structural awareness for tables, JSON, CSV, config — without code-mediated manipulation

---

## 1. Problem Statement

### 1.1 The Code-Mediation Gap

Standard LLMs (Claude, GPT-4) handle structured data by **generating code** that manipulates it:

```
User: "Find the average revenue by region"
LLM → generates: df.groupby('region')['revenue'].mean()
Python executes → result
LLM → formats answer
```

The model never *understands* the table. It pattern-matches the question to pandas idioms learned during training. The actual structural reasoning happens in the Python runtime, not in the model's attention.

**Evidence:** Claude's Analysis Tool runs a sandboxed Ubuntu container with Python 3.12 + pandas/openpyxl. The model writes code; the container executes it. Structured understanding is **outsourced**.

### 1.2 What Model-Internal Structural Awareness Means

A model with native structural awareness would:

1. **Encode position in 2D** — know that token at (row=3, col=revenue) is a numeric value in the revenue column, not just "the 47th token"
2. **Recognize structural roles** — distinguish headers from values, keys from constraints, indices from data
3. **Retrieve by structure** — "all values in column 3" is a natural query, not a code generation task
4. **Validate structurally** — detect type mismatches, missing values, schema violations during inference
5. **Explain structurally** — attribution traces follow columns and rows, not just token positions

### 1.3 Why Phase Quad Has the Right Foundations

Phase Quad's existing architecture already separates concerns that map naturally to structured reasoning:

| Existing Component | Current Role | Structural Extension |
|---|---|---|
| `LocalWindowAttention` (L3162) | Syntax — O(n*w) sliding window | **Row-local**: tokens within a row are syntactically adjacent |
| `BindingCachePhaseState` (L2601) | Memory — O(n) cumsum/EMA state | **Column-persistent**: column semantics persist across rows |
| `BindingCacheQuadQuery` (L2891) | Retrieval — O(nk) Top-K cache | **Cross-row retrieval**: fetch related values from other rows |
| `OntologicalBindingAnnotator` (L2494) | Salience — per-position [B,N] | **Schema-aware salience**: headers get different salience than values |
| `IntentPhaseProjector` (L1674) | Phase rotation — 12D Bhava → θ | **Structure-conditioned rotation**: relationships change by data role |
| Vrittis `[17:22]` | Epistemic reliability | **Per-cell validation**: FACT/ERROR per output cell |

The key insight: **we don't need a new architecture — we need to teach the existing one about 2D structure.**

---

## 2. Architecture Extensions

### 2.1 Two-Dimensional Positional Encoding

**Current state** (`phase_transformer.py` lines 3535-3538):
```python
self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
# Forward: pos = torch.arange(N) → 1D absolute position
```

Tokens in a table are flattened to a 1D sequence. The model has no way to know that tokens 12 positions apart are in the same column of different rows.

**Extension: StructuralPositionEncoder**

```python
class StructuralPositionEncoder(nn.Module):
    """
    Adds 2D structural position to the standard 1D sequence position.

    Three position signals, additively combined:
      1. Sequence position  — existing pos_embed (preserved for non-table text)
      2. Row position       — which row this token belongs to (0 = header)
      3. Column position    — which column this token belongs to

    For non-table tokens, row_pos = col_pos = 0 (neutral embedding).
    """

    def __init__(self, max_rows=512, max_cols=256, embed_dim=768):
        super().__init__()
        self.row_embed = nn.Embedding(max_rows + 1, embed_dim)   # +1 for "not-a-table" token
        self.col_embed = nn.Embedding(max_cols + 1, embed_dim)   # +1 for "not-a-table" token

        # Gate: how much structural position to mix in (learned per-dimension)
        # Starts at 0 so pre-trained weights are not disrupted
        self.struct_gate = nn.Parameter(torch.zeros(embed_dim))

    def forward(self, seq_embed, row_ids, col_ids):
        """
        Args:
            seq_embed:  [B, N, D] — token + standard positional embedding
            row_ids:    [B, N]    — row index per token (0 = header, -1 = not-a-table → mapped to max_rows)
            col_ids:    [B, N]    — column index per token (-1 = not-a-table → mapped to max_cols)
        Returns:
            [B, N, D] — seq_embed + gated structural position
        """
        struct_pos = self.row_embed(row_ids) + self.col_embed(col_ids)
        gate = torch.sigmoid(self.struct_gate)  # [D], starts ≈ 0.5 (init from zeros → sigmoid(0)=0.5)
        return seq_embed + gate * struct_pos
```

**Design decisions:**
- **Additive, not replacing** — 1D position is preserved so the model still works on plain text
- **Gated entry** — `struct_gate` initialized to zeros (sigmoid → 0.5). Can be initialized smaller for gentler ramp-in. Prevents catastrophic forgetting of pre-trained positional knowledge
- **Row 0 = header** convention — the model learns that row-0 tokens define column semantics
- **-1 sentinel** for non-table tokens — maps to a dedicated "no structure" embedding

**Where it plugs in** (`phase_transformer.py` line ~3733):
```python
# Current:
x = self.dropout(self.token_embed(input_ids) + self.pos_embed(pos))

# Extended:
x = self.dropout(self.token_embed(input_ids) + self.pos_embed(pos))
if hasattr(self, 'struct_pos') and row_ids is not None:
    x = self.struct_pos(x, row_ids, col_ids)
```

### 2.2 Schema-Conditioned Binding Annotator

**Current state** (`phase_transformer.py` lines 2494-2598):

`OntologicalBindingAnnotator` computes per-position salience `[B, N]` from:
- `hidden_states [B, N, D]` → MLP → `hidden_salience [B, N, 1]`
- `sovereign_state [B, 32]` → MLP → `state_salience [B, H]` (if use_srk)
- `kosha_activations [B, 5]` → learned weights → depth bias

Salience is **general-purpose** — it doesn't know whether a position is a header, a numeric value, or a delimiter.

**Extension: StructuralBindingAnnotator**

```python
class StructuralBindingAnnotator(OntologicalBindingAnnotator):
    """
    Extends OntologicalBindingAnnotator with schema-role awareness.

    Adds a structural role signal to salience computation:
      - HEADER  (role=1): Column name/schema definition
      - VALUE   (role=2): Data cell content
      - KEY     (role=3): Primary key / index column
      - DELIM   (role=4): Structural delimiter (comma, tab, pipe, brace)
      - META    (role=5): Schema metadata (type annotation, constraint)
      - TEXT    (role=0): Non-structural text (default, backward-compatible)

    The role embedding is ADDED to hidden_salience, not replacing it.
    Binding Annotator's core contract is preserved: output is [B, N] salience.
    """

    NUM_STRUCTURAL_ROLES = 6  # TEXT, HEADER, VALUE, KEY, DELIM, META

    def __init__(self, embed_dim, state_dim=32, num_heads=12, **kwargs):
        super().__init__(embed_dim, state_dim, num_heads, **kwargs)

        # Role embedding → salience contribution
        self.role_embed = nn.Embedding(self.NUM_STRUCTURAL_ROLES, embed_dim // 4)
        self.role_salience = nn.Sequential(
            nn.Linear(embed_dim // 4, embed_dim // 8),
            nn.GELU(),
            nn.Linear(embed_dim // 8, 1),
        )

        # Column-type embedding: learned per-column-index (captures "revenue is numeric")
        self.col_type_embed = nn.Embedding(256, embed_dim // 4)  # max 256 columns

        # Cross-signal: role × column_type → salience modifier
        self.cross_salience = nn.Linear(embed_dim // 4, 1)  # role ⊕ col_type → scalar

        # Initialize near-zero for backward compatibility
        nn.init.zeros_(self.role_salience[-1].weight)
        nn.init.zeros_(self.role_salience[-1].bias)
        nn.init.zeros_(self.cross_salience.weight)

    def forward(self, hidden_states, sovereign_state=None,
                kosha_activations=None, csr_mask=None,
                role_ids=None, col_ids=None):
        """
        Args:
            (all existing args preserved)
            role_ids: [B, N] — structural role per token (0=TEXT default)
            col_ids:  [B, N] — column index per token (0=no-column default)
        Returns:
            salience: [B, N] — enhanced with structural awareness
        """
        # Original salience computation (unchanged)
        base_salience = super().forward(
            hidden_states, sovereign_state, kosha_activations, csr_mask
        )

        if role_ids is None:
            return base_salience  # Backward compatible: no structure → original behavior

        # Structural salience contribution
        role_emb = self.role_embed(role_ids)          # [B, N, D//4]
        role_sal = self.role_salience(role_emb).squeeze(-1)  # [B, N]

        if col_ids is not None:
            col_emb = self.col_type_embed(col_ids)    # [B, N, D//4]
            cross = self.cross_salience(role_emb + col_emb).squeeze(-1)  # [B, N]
            role_sal = role_sal + cross

        return base_salience + role_sal
```

**What this enables:**
- Headers get **higher salience** → promoted into Top-K cache → columns carry their schema forward
- Keys get **persistent salience** → primary key values stay retrievable across long tables
- Delimiters get **low salience** → structural punctuation doesn't waste Top-K slots
- The cross-signal learns that "header × column-3" means "this is the revenue column name"

### 2.3 Column-Persistent Phase State

**Current state** (`phase_transformer.py` lines 2601-2812):

`BindingCachePhaseState` accumulates key-value pairs via cumsum/EMA:
```python
memory_state = cumsum(kv, dim=1)  # O(n) accumulation along sequence
```

All tokens accumulate into the same memory regardless of column structure. The phase rotation from `IntentPhaseProjector` modulates relationships by Bhava identity, not by column.

**Extension: Column-Aware Phase Accumulation**

The insight: columns in a table are **independent information channels**. Values in the "revenue" column should accumulate into a different phase subspace than values in the "region" column.

```python
class ColumnAwarePhaseState(BindingCachePhaseState):
    """
    Extends BindingCachePhaseState with column-conditioned phase offsets.

    Design: Each column gets a learned phase offset that creates a distinct
    "channel" in the complex plane. Values in different columns accumulate
    into separable subspaces of the memory state.

    This is NOT a separate memory per column (that would break O(n)).
    Instead, column identity modulates the key phase, so values from
    column-3 cluster at a different phase angle than values from column-7.
    The cumsum still runs over the full sequence — but column structure
    emerges from phase separation in the complex plane.

    Mathematical: φ_k' = φ_k + θ_intent + θ_column[col_id]
    """

    def __init__(self, embed_dim, num_heads=12, max_cols=256, **kwargs):
        super().__init__(embed_dim, num_heads=num_heads, **kwargs)

        # Per-column phase offset: learned separation in complex plane
        # Initialized to evenly spaced angles around the unit circle
        angles = torch.linspace(0, 2 * 3.14159, max_cols + 1)[:-1]  # [max_cols]
        self.col_phase_offset = nn.Parameter(angles.unsqueeze(0))    # [1, max_cols]

        # Column-head interaction: different heads may group columns differently
        self.col_head_proj = nn.Linear(max_cols, num_heads, bias=False)
        nn.init.eye_(self.col_head_proj.weight[:num_heads, :num_heads])  # Start as identity-ish

    def forward(self, x, intent_phase=None, col_ids=None, **kwargs):
        """
        Extended forward with column-conditioned phase.

        If col_ids is None, behaves exactly as parent (backward compatible).
        If col_ids is provided, adds per-column phase offsets before accumulation.
        """
        if col_ids is None:
            return super().forward(x, intent_phase=intent_phase, **kwargs)

        # Compute column phase offset per position
        # col_ids: [B, N] → one-hot [B, N, max_cols] → phase [B, N, H]
        col_one_hot = F.one_hot(col_ids, self.col_phase_offset.shape[1]).float()
        col_phase = col_one_hot @ self.col_phase_offset.squeeze(0)  # [B, N, 1]
        col_phase_per_head = self.col_head_proj(col_one_hot)         # [B, N, H]

        # Combine with intent phase
        if intent_phase is not None:
            combined_phase = intent_phase + col_phase_per_head
        else:
            combined_phase = col_phase_per_head

        return super().forward(x, intent_phase=combined_phase, **kwargs)
```

**Why this works:**
- **O(n) preserved** — no per-column memory; column identity lives in the phase angle
- **Phase separation** — values from column A cluster at angle θ_A, column B at θ_B
- **Natural retrieval** — when Quad queries for "values in column 3", the phase match naturally selects them (cosine similarity in complex plane favors same-angle entries)
- **Header propagation** — header token for column 3 has the same col_phase as all values in column 3, so it stays retrievable

### 2.4 Structure-Conditioned Phase Rotation (Bhava Extension)

**Current state** (`phase_transformer.py` lines 1674-1780):

`IntentPhaseProjector` maps 12D Bhava delta → phase offset `[B, H]`:
```python
# Bhava identity modulates HOW tokens relate:
# EXE (Execution) → θ ≈ 0° → "the door is open" = opportunity
# WIT (Witness)   → θ ≈ π  → "the door is open" = observation
```

Bhavas encode **ontological** modes of being. They don't currently encode structural data roles.

**Extension: Structural Bhava Conditioning**

Rather than overloading Bhavas with data roles (which Appendix B correctly flagged as an over-claim), we add a **parallel structural conditioning path** that interacts with the Bhava phase:

```python
class StructuralPhaseProjector(nn.Module):
    """
    Parallel path to IntentPhaseProjector for structural context.

    Design principle: Bhavas remain ontological (WHAT mode of being).
    Structural context is a SEPARATE signal that MODULATES the Bhava phase,
    not replaces it.

    Mathematical:
        θ_total = θ_intent(ΔBhava) + θ_struct(struct_context)

    Where struct_context encodes:
        - Am I reading a header or a value? (role)
        - Am I in column 3 or column 7? (position)
        - Is this a numeric or categorical column? (type)
        - What operation is being performed? (query intent)

    The interaction term θ_intent × θ_struct captures:
        "In EXECUTION mode, looking at a NUMERIC VALUE in the REVENUE column"
    """

    STRUCT_CONTEXT_DIM = 16  # Compact structural context vector

    def __init__(self, num_heads=12, struct_dim=16):
        super().__init__()

        # Encode structural context to phase offset
        self.struct_phase_proj = nn.Sequential(
            nn.Linear(struct_dim, struct_dim),
            nn.GELU(),
            nn.Linear(struct_dim, num_heads),
        )

        # Interaction gate: how much structural phase to add
        # Starts near-zero so pre-trained Bhava paths are not disrupted
        self.struct_gate = nn.Parameter(torch.full((num_heads,), -2.0))  # sigmoid(-2) ≈ 0.12

        nn.init.zeros_(self.struct_phase_proj[-1].weight)
        nn.init.zeros_(self.struct_phase_proj[-1].bias)

    def forward(self, intent_phase, struct_context):
        """
        Args:
            intent_phase:   [B, H] — from IntentPhaseProjector (Bhava-driven)
            struct_context: [B, N, 16] — structural context per position
        Returns:
            [B, N, H] — combined phase offset (broadcast-ready for Phase path)
        """
        struct_phase = self.struct_phase_proj(struct_context)  # [B, N, H]
        gate = torch.sigmoid(self.struct_gate)                 # [H]

        # intent_phase [B, H] → [B, 1, H] for broadcasting
        combined = intent_phase.unsqueeze(1) + gate * struct_phase
        return combined
```

**What `struct_context [B, N, 16]` encodes (assembled from available signals):**
- Dims [0:6] — role one-hot (TEXT/HEADER/VALUE/KEY/DELIM/META)
- Dims [6:10] — column type learned embedding (projected from col_id)
- Dims [10:14] — row position encoding (log-scaled row index)
- Dims [14:16] — table/non-table indicator + nesting depth

### 2.5 Cross-Row Quad Retrieval

**Current state** (`phase_transformer.py` lines 2891-3159):

`BindingCacheQuadQuery` does Top-K retrieval based on dot-product scores + binding salience bias. It doesn't know about rows or columns — it retrieves the K most relevant positions globally.

**Extension: Structure-Biased Retrieval**

The key insight: for structured data queries like "what is the revenue for region=West?", the model needs to retrieve across rows **within a column**. The existing Top-K mechanism already supports this through binding salience — we just need the salience to be structure-aware (Section 2.2).

But there's a deeper opportunity: **column-coherent retrieval**.

```python
class StructuralQuadQuery(BindingCacheQuadQuery):
    """
    Extends BindingCacheQuadQuery with optional structural retrieval modes.

    Mode 1 (default): Standard Top-K (unchanged)
    Mode 2 (column_coherent): Retrieve Top-K but ensure at least one
            representative from each column in the table.
    Mode 3 (row_complete): When retrieving a value, also retrieve
            other values from the same row (for join/comparison operations).

    Mode selection is LEARNED, not hardcoded — the model discovers
    which mode is useful for which query type.
    """

    def __init__(self, embed_dim, num_heads=12, top_k=64, max_cols=256, **kwargs):
        super().__init__(embed_dim, num_heads, top_k, **kwargs)

        # Mode selector: query-dependent choice of retrieval strategy
        self.mode_proj = nn.Linear(embed_dim, 3)  # 3 soft modes

        # Column diversity bonus: encourages Top-K to cover multiple columns
        self.diversity_bonus = nn.Parameter(torch.tensor(0.1))

    def forward(self, x, memory_state, causal_mask=None,
                binding_salience=None, col_ids=None, **kwargs):
        """
        Extended with optional column-diversity-aware Top-K.
        """
        if col_ids is None:
            return super().forward(x, memory_state, causal_mask,
                                   binding_salience, **kwargs)

        # Compute mode weights per position
        mode_weights = F.softmax(self.mode_proj(x), dim=-1)  # [B, N, 3]

        # Standard retrieval (always computed)
        # We override the scoring step to add diversity bonus
        B, N, D = x.shape
        H = self.num_heads
        D_h = D // H

        Q = self.W_q(x).view(B, N, H, D_h)
        K = self.W_k(memory_state).view(B, N, H, D_h)
        V = self.W_v(memory_state).view(B, N, H, D_h)

        scores = torch.einsum('bnhd,bmhd->bhnm', Q, K) / (D_h ** 0.5)

        if binding_salience is not None:
            selection_scores = scores + binding_salience.unsqueeze(1).unsqueeze(1)
        else:
            selection_scores = scores

        # Column diversity bonus: positions from under-represented columns
        # get a retrieval boost, encouraging the Top-K to cover the table
        if col_ids is not None and self.diversity_bonus > 0:
            col_counts = torch.zeros(B, col_ids.max() + 1, device=x.device)
            col_counts.scatter_add_(1, col_ids, torch.ones_like(col_ids, dtype=torch.float))
            # Inverse frequency: rare columns get bonus
            inv_freq = 1.0 / (col_counts.gather(1, col_ids) + 1e-6)  # [B, N]
            inv_freq = inv_freq / inv_freq.max(dim=1, keepdim=True).values  # normalize to [0, 1]
            diversity = self.diversity_bonus * inv_freq  # [B, N]
            selection_scores = selection_scores + diversity.unsqueeze(1).unsqueeze(1)

        K_sel = min(self.top_k, N)
        _, top_indices = selection_scores.topk(K_sel, dim=-1, largest=True)

        # Gather original scores (pure attention math, no salience/diversity bias)
        top_scores = torch.gather(scores, -1, top_indices)
        top_weights = F.softmax(top_scores, dim=-1)

        top_values = torch.gather(
            V.unsqueeze(2).expand(-1, -1, N, -1, -1),
            3,
            top_indices.unsqueeze(-1).expand(-1, -1, -1, -1, D_h)
        )

        output = torch.einsum('bhnk,bhnkd->bnhd', top_weights, top_values)
        return output.reshape(B, N, D)
```

### 2.6 Vritti-Driven Schema Validation

**Current state** (`phase_transformer.py` lines 145-152):

Vrittis `[17:22]` track epistemic reliability as a probability distribution:
```
FACT=17, ERROR=18, IMAGINATION=19, VOID=20, MEMORY=21
```

Currently applied globally — the model has one Vritti state for the entire sequence.

**Extension: Per-Cell Vritti Validation**

For structured outputs (e.g., generating a table, filling cells), the Vritti signal should be **per-position** to provide cell-level confidence:

```python
class StructuralVrittiValidator(nn.Module):
    """
    Projects per-position hidden states to per-cell Vritti reliability scores.

    Global Vrittis [17:22] tell us the overall epistemic state.
    Per-cell Vrittis tell us: "I'm confident about the revenue for Q3,
    but uncertain about the revenue for Q4 (it's an extrapolation)."

    This enables:
      1. Cell-level confidence in generated tables
      2. Highlighting uncertain cells in structured outputs
      3. Selective human-in-the-loop for low-confidence cells
      4. Schema violation detection (type mismatch, range violation)
    """

    def __init__(self, embed_dim, num_vrittis=5):
        super().__init__()

        self.cell_vritti_proj = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 4),
            nn.GELU(),
            nn.Linear(embed_dim // 4, num_vrittis),
        )

        # Schema constraint head: detects violations
        self.constraint_head = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 8),
            nn.GELU(),
            nn.Linear(embed_dim // 8, 4),  # type_ok, range_ok, nullable_ok, format_ok
        )

    def forward(self, hidden_states, global_vrittis=None):
        """
        Args:
            hidden_states:  [B, N, D] — per-position representations
            global_vrittis: [B, 5]    — sovereign Vritti state (optional context)
        Returns:
            cell_vrittis:   [B, N, 5] — per-position FACT/ERROR/IMAGINATION/VOID/MEMORY
            constraints:    [B, N, 4] — per-position schema constraint satisfaction
        """
        cell_vrittis = F.softmax(self.cell_vritti_proj(hidden_states), dim=-1)
        constraints = torch.sigmoid(self.constraint_head(hidden_states))

        # If global Vrittis available, use as prior (residual gate)
        if global_vrittis is not None:
            # Global context: if global ERROR is high, shift all cells toward ERROR
            global_bias = global_vrittis.unsqueeze(1)  # [B, 1, 5]
            cell_vrittis = 0.8 * cell_vrittis + 0.2 * global_bias

        return cell_vrittis, constraints

    def flag_unreliable(self, cell_vrittis, constraints,
                         fact_threshold=0.5, constraint_threshold=0.7):
        """
        Returns mask of positions that should be flagged for review.

        A cell is unreliable if:
          - FACT score < threshold (model isn't confident this is factual)
          - ERROR score is highest Vritti (model thinks this might be wrong)
          - Any constraint score < threshold (schema violation detected)
        """
        fact_low = cell_vrittis[:, :, 0] < fact_threshold       # FACT dim
        error_high = cell_vrittis.argmax(dim=-1) == 1           # ERROR is dominant
        constraint_fail = (constraints < constraint_threshold).any(dim=-1)

        return fact_low | error_high | constraint_fail  # [B, N] boolean mask
```

---

## 3. Input Pipeline: Structural Tokenization

### 3.1 The Structure Annotation Problem

Standard tokenizers destroy structure. Given a CSV row:
```
West,4200000,Q3-2024,approved
```

A BPE tokenizer produces: `["West", ",", "42", "000", "00", ",", "Q", "3", "-", "2024", ...]`

The token "42" doesn't know it's in column 2 (revenue), row 15, and that it's a numeric prefix.

### 3.2 Structural Annotation Layer

We don't modify the tokenizer — we add a **post-tokenization annotation layer** that provides `row_ids`, `col_ids`, and `role_ids` alongside the token IDs:

```python
class StructuralAnnotator:
    """
    Post-tokenization annotation for structured data formats.

    Detects structured regions in the token stream and assigns
    row_ids, col_ids, and role_ids. Non-structured text gets
    default values (row=0, col=0, role=TEXT).

    Supported formats:
      - CSV/TSV (delimiter-separated)
      - JSON (key-value pairs, arrays)
      - Markdown tables (pipe-separated)
      - HTML tables (<tr>/<td>)
      - Key-value config files
    """

    # Format detection patterns
    FORMATS = {
        'csv':      {'delimiters': [',', '\t', '|'], 'row_sep': '\n'},
        'json':     {'open': ['{', '['], 'close': ['}', ']'], 'kv_sep': ':'},
        'markdown': {'row_start': '|', 'header_sep': '---'},
    }

    def annotate(self, text: str, token_offsets: list) -> dict:
        """
        Args:
            text:          raw input text
            token_offsets: list of (start, end) character positions per token
        Returns:
            {
                'row_ids':  [N] int — row index per token
                'col_ids':  [N] int — column index per token
                'role_ids': [N] int — structural role per token
            }
        """
        # Step 1: Detect format
        fmt = self._detect_format(text)

        if fmt is None:
            # Not structured data — return defaults
            N = len(token_offsets)
            return {
                'row_ids':  [0] * N,
                'col_ids':  [0] * N,
                'role_ids': [0] * N,  # TEXT role
            }

        # Step 2: Parse structure boundaries
        cells = self._parse_cells(text, fmt)

        # Step 3: Map tokens to cells
        return self._map_tokens_to_cells(token_offsets, cells, fmt)

    def _detect_format(self, text):
        """Heuristic format detection."""
        lines = text.strip().split('\n')
        if len(lines) < 2:
            return None

        # CSV: consistent delimiter count across lines
        for delim in [',', '\t', '|']:
            counts = [line.count(delim) for line in lines[:5]]
            if len(set(counts)) == 1 and counts[0] > 0:
                return {'type': 'csv', 'delimiter': delim}

        # JSON: starts with { or [
        stripped = text.strip()
        if stripped.startswith('{') or stripped.startswith('['):
            return {'type': 'json'}

        return None

    def _parse_cells(self, text, fmt):
        """
        Returns list of Cell(row, col, start, end, role) for each data cell.
        """
        cells = []

        if fmt['type'] == 'csv':
            delim = fmt['delimiter']
            for row_idx, line in enumerate(text.strip().split('\n')):
                col_offset = 0
                for col_idx, value in enumerate(line.split(delim)):
                    start = text.index(value, col_offset)
                    end = start + len(value)
                    role = 'HEADER' if row_idx == 0 else 'VALUE'
                    cells.append({
                        'row': row_idx, 'col': col_idx,
                        'start': start, 'end': end,
                        'role': role
                    })
                    col_offset = end

                    # Mark delimiter
                    delim_pos = text.find(delim, end)
                    if delim_pos >= 0 and delim_pos < end + 2:
                        cells.append({
                            'row': row_idx, 'col': col_idx,
                            'start': delim_pos, 'end': delim_pos + 1,
                            'role': 'DELIM'
                        })

        elif fmt['type'] == 'json':
            # JSON parsing: track nesting depth as row, key index as column
            # Simplified: treat each key-value pair as a cell
            pass  # Full implementation would use json tokenizer

        return cells

    def _map_tokens_to_cells(self, token_offsets, cells, fmt):
        """Map each token to its cell based on character offsets."""
        N = len(token_offsets)
        row_ids = [0] * N
        col_ids = [0] * N
        role_ids = [0] * N  # 0=TEXT

        ROLE_MAP = {'TEXT': 0, 'HEADER': 1, 'VALUE': 2, 'KEY': 3, 'DELIM': 4, 'META': 5}

        for i, (tok_start, tok_end) in enumerate(token_offsets):
            for cell in cells:
                if tok_start >= cell['start'] and tok_end <= cell['end']:
                    row_ids[i] = cell['row']
                    col_ids[i] = cell['col']
                    role_ids[i] = ROLE_MAP.get(cell['role'], 0)
                    break

        return {'row_ids': row_ids, 'col_ids': col_ids, 'role_ids': role_ids}
```

### 3.3 Mixed-Content Handling

Real inputs contain both structured and unstructured regions:

```
Please analyze the following sales data and find the top region:

region,revenue,quarter,status
West,4200000,Q3-2024,approved
East,3100000,Q3-2024,pending
North,2800000,Q3-2024,approved

Which region has the highest revenue?
```

The annotator marks only the CSV block as structured (rows 1-4). The surrounding text gets `role=TEXT, row=0, col=0`. The model processes both with the same architecture — structural components simply have no effect on non-structural tokens (due to zero-initialized gates).

---

## 4. Training Curriculum

### 4.1 Phase 1: Structure Recognition (Pre-training Extension)

**Objective:** Learn 2D positional encoding and role embeddings.

**Data:**
- WikiTables (570K tables) — HTML tables with headers, types, and values
- GitHub CSV/JSON (filtered for quality) — real-world structured data
- SQuAD-like QA pairs over tables — "What is X where Y = Z?"

**Training signals:**
- Standard language modeling loss on flattened table tokens
- **Structural position prediction** (auxiliary): given a masked token, predict its (row, col, role) — forces the model to learn the 2D encoding
- **Column consistency loss** (auxiliary): values in the same column should have similar hidden representations — encourages column-coherent phase accumulation

```python
def structural_position_loss(hidden, row_ids, col_ids, role_ids):
    """Auxiliary loss: predict structural position from hidden states."""
    row_logits = row_head(hidden)    # [B, N, max_rows]
    col_logits = col_head(hidden)    # [B, N, max_cols]
    role_logits = role_head(hidden)  # [B, N, 6]

    loss = (
        F.cross_entropy(row_logits.view(-1, max_rows), row_ids.view(-1)) +
        F.cross_entropy(col_logits.view(-1, max_cols), col_ids.view(-1)) +
        F.cross_entropy(role_logits.view(-1, 6), role_ids.view(-1))
    )
    return loss / 3.0

def column_consistency_loss(hidden, col_ids):
    """Encourage same-column tokens to have similar representations."""
    # For each column, compute mean hidden state
    # Pull same-column tokens together, push different-column tokens apart
    unique_cols = col_ids.unique()
    col_means = []
    for c in unique_cols:
        if c == 0:
            continue  # skip non-table tokens
        mask = (col_ids == c)
        col_mean = hidden[mask].mean(dim=0)
        col_means.append(col_mean)

    if len(col_means) < 2:
        return torch.tensor(0.0)

    col_means = torch.stack(col_means)  # [C, D]

    # Contrastive: same-column tokens should be closer than different-column
    sim_matrix = F.cosine_similarity(
        col_means.unsqueeze(0), col_means.unsqueeze(1), dim=-1
    )
    # Diagonal = self-similarity (should be high) — off-diagonal should be low
    target = torch.eye(len(col_means), device=hidden.device)
    return F.mse_loss(sim_matrix, target)
```

### 4.2 Phase 2: Structural Reasoning (Fine-tuning)

**Objective:** Learn to use structural awareness for downstream tasks.

**Benchmarks and datasets:**
- **WikiTableQuestions (WTQ)** — multi-hop table QA
- **SQA** — sequential question answering over tables
- **TabFact** — table fact verification (entailment)
- **TAPAS-style** tasks — table parsing and cell selection
- **HybridQA** — questions requiring both table and text reasoning
- **Spider** — text-to-SQL (tests structural understanding)

**Training signals:**
- Task-specific loss (QA accuracy, fact verification, cell selection)
- **Vritti supervision** (auxiliary): when the model generates a wrong cell value, the Vritti ERROR signal should be high — supervised from training labels
- **Schema validation loss** (auxiliary): when generating structured output, the constraint head should predict type/range violations that exist in the ground truth

### 4.3 Phase 3: Schema Validation (Specialization)

**Objective:** Per-cell confidence and constraint satisfaction.

**Data:**
- Synthetic tables with injected errors (type mismatches, range violations, null violations)
- Real-world data quality datasets (dirty vs clean tables)
- Schema definitions paired with data instances

**Training signal:**
- Binary cell-level labels: is this cell correct/incorrect given the schema?
- Multi-label constraint satisfaction: type_ok, range_ok, nullable_ok, format_ok

---

## 5. Inference Flow: End-to-End Example

### 5.1 Query

```
Given this data:
product,price,quantity,total
Widget A,25.99,100,2599.00
Widget B,14.50,250,3625.00
Widget C,42.00,75,3150.50

Find the row where total doesn't match price × quantity.
```

### 5.2 Processing Steps

```
STEP 1: TOKENIZATION + ANNOTATION
  StructuralAnnotator detects CSV format
  Assigns row_ids: [0,0,0,...,1,1,1,...,2,2,2,...,3,3,3,...]
  Assigns col_ids: [0,1,2,3,...,0,1,2,3,...,0,1,2,3,...,0,1,2,3,...]
  Assigns role_ids: [HEADER,HEADER,...,VALUE,VALUE,...,VALUE,VALUE,...]
  Non-table text gets role=TEXT, row=0, col=0

STEP 2: EMBEDDING + STRUCTURAL POSITION
  x = token_embed + pos_embed + gate * (row_embed + col_embed)
  Token "2599.00" knows it's at (row=1, col=3, role=VALUE)
  Token "25.99" knows it's at (row=1, col=1, role=VALUE)
  Token "total" knows it's at (row=0, col=3, role=HEADER)

STEP 3: SOVEREIGN STATE
  compute_state_delta → state[32D], delta_bhava[12D]
  Bhava: RSN (Reason) + COG (Cognition) activated
    → model is in analytical/verification mode
  Vritti: FACT high globally (structured data, clear question)
  Kosha: INTELLECTUAL active (pattern/comparison depth)

STEP 4: PHASE ROTATION (per layer)
  IntentPhaseProjector: delta_bhava[12D] → θ_intent[H]
  StructuralPhaseProjector: struct_context[16D] → θ_struct[N, H]
  Combined: θ = θ_intent + gate * θ_struct

  Column-conditioned phase:
    col=3 ("total" column) → phase offset θ_col3
    col=1 ("price" column) → phase offset θ_col1
    Same column values cluster in complex plane

STEP 5: THREE-PATH PROCESSING (per layer)

  LOCAL (O(n*w)):
    Window attention within each row
    "25.99" attends to "Widget A", "100", "2599.00" (same-row syntax)
    Learns within-row relationships

  PHASE (O(n)):
    Column-aware accumulation
    All "total" values accumulate at θ_col3 phase angle
    All "price" values accumulate at θ_col1 phase angle
    Memory state separates column channels in complex plane

  QUAD (O(nk)):
    StructuralBindingAnnotator: HEADER tokens get high salience
      → "total", "price", "quantity" stay in Top-K cache
    Retrieves: for each value, header defines its semantics
    "3150.50" retrieves "total" header → knows its role
    Cross-row: "2599.00" can retrieve "3625.00" (same column, different row)

  COMBINATION: attn_out = local_out + mem_out (additive, separable)

STEP 6: REASONING (across layers)

  Layer 1-3: Build structural representations
    Each cell knows its row, column, role, and type

  Layer 4-6: Cross-reference computation
    For each row: retrieve price, quantity from same row
    Compute expected = price × quantity (learned operation)
    Compare with actual total value

  Layer 7-8: Discrepancy detection
    Row 3 (Widget C): price=42.00, quantity=75
    Expected total: 42.00 × 75 = 3150.00
    Actual total: 3150.50
    Mismatch detected: 0.50 difference

STEP 7: VRITTI VALIDATION
  StructuralVrittiValidator on output hidden states:
    Row 1, 2: cell_vritti[FACT] > 0.9 → consistent
    Row 3, col 3: cell_vritti[ERROR] > 0.7 → flagged

  constraint_head:
    Row 3, col 3: range_ok = 0.3 (expected 3150.00, got 3150.50)
    → Schema violation flagged

STEP 8: OUTPUT GENERATION
  "Widget C (row 3) has an inconsistent total.
   Price ($42.00) × Quantity (75) = $3,150.00,
   but the total column shows $3,150.50 — a $0.50 discrepancy."

  + per-cell confidence annotations (from Vritti validator)
  + structural attribution (from path separation)
```

### 5.3 What's Different from Code-Mediated

| Aspect | Claude (Code-Mediated) | Phase Quad (Model-Internal) |
|---|---|---|
| **How it finds the error** | Generates `df[df.price * df.quantity != df.total]` → Python executes | Model's attention natively cross-references columns via phase separation |
| **Where computation happens** | External Python sandbox | Inside the model's forward pass |
| **Attribution** | "I wrote code that found it" | "Local path saw row syntax, Phase accumulated column values, Quad cross-referenced header semantics" |
| **Cell-level confidence** | Binary (code ran or didn't) | Per-cell Vritti scores (FACT 0.95 for rows 1-2, ERROR 0.73 for row 3) |
| **Failure mode** | Code error → crash, retry | Low confidence → flag for review, escalate via ConfidenceGate |
| **Structured position** | Text tokens, no 2D awareness | 2D row/col embeddings, column-aware phase separation |
| **Schema validation** | Must be coded explicitly | Constraint head learns from training data |

---

## 6. Integration Points with Existing Architecture

### 6.1 Files to Modify

| File | Change | Scope |
|---|---|---|
| `symbolu/phase_transformer.py` L3535 | Add `StructuralPositionEncoder` | New class, ~40 lines |
| `symbolu/phase_transformer.py` L3733 | Wire structural positions into embedding | 3-line forward pass change |
| `symbolu/phase_transformer.py` L2494 | Extend `OntologicalBindingAnnotator` | Subclass, ~60 lines |
| `symbolu/phase_transformer.py` L2601 | Extend `BindingCachePhaseState` | Subclass, ~40 lines |
| `symbolu/phase_transformer.py` L2891 | Extend `BindingCacheQuadQuery` | Subclass, ~50 lines |
| `symbolu/phase_transformer.py` L1674 | Add parallel `StructuralPhaseProjector` | New class, ~40 lines |
| `symbolu/phase_transformer.py` L3284 | Wire structural IDs through `BindingCacheBlock` | Forward signature + 5 lines |
| New: `symbolu/structural/annotator.py` | `StructuralAnnotator` | ~200 lines |
| New: `symbolu/structural/validator.py` | `StructuralVrittiValidator` | ~80 lines |
| `train_unified_llm.py` | Structural training curriculum | Auxiliary losses + data pipeline |

### 6.2 Backward Compatibility

Every extension is designed with **gated entry**:

- If `row_ids=None` and `col_ids=None` → all structural components are bypassed
- Gates initialized near-zero → pre-trained weights are not disrupted
- Subclasses preserve parent class contracts (salience is still `[B, N]`, etc.)
- Non-table text is unaffected — structural embeddings default to neutral values

### 6.3 Computational Cost

| Component | Cost | Notes |
|---|---|---|
| StructuralPositionEncoder | O(N) embedding lookup | Negligible — same as existing pos_embed |
| StructuralBindingAnnotator | +O(N × D/4) | Small MLP on role embeddings |
| ColumnAwarePhaseState | +O(N × H) | Column phase offset per position |
| StructuralQuadQuery | +O(N × C) diversity | C = number of columns, typically < 100 |
| StructuralVrittiValidator | +O(N × D/4) | Only on output layer, not every layer |
| StructuralAnnotator | O(N) pre-processing | CPU-side, before GPU forward pass |
| **Total overhead** | **< 3% of forward pass** | Dominated by existing O(n*w) + O(n*k) |

---

## 7. Evaluation Plan

### 7.1 Benchmarks

| Benchmark | Task | Metric | Target |
|---|---|---|---|
| WikiTableQuestions | Multi-hop table QA | Denotation accuracy | > 55% (TAPAS: 48.8%) |
| SQA | Sequential table QA | Sequence accuracy | > 65% (TAPAS: 67.2%) |
| TabFact | Table fact verification | Accuracy | > 80% (TAPAS: 81.0%) |
| HybridQA | Table + text QA | EM / F1 | > 50% / 60% |
| Spider | Text-to-SQL | Execution accuracy | > 70% |
| Custom: Cell Confidence | Per-cell reliability | AUROC | > 0.85 |
| Custom: Schema Validation | Constraint detection | F1 | > 0.80 |

### 7.2 Ablation Studies

| Ablation | Tests |
|---|---|
| Remove 2D position | Does the model lose column awareness? |
| Remove column phase | Does phase path degrade to position-unaware accumulation? |
| Remove structural salience | Do headers drop out of Top-K cache? |
| Remove Vritti validation | Does cell-level confidence degrade? |
| Standard LM (no structure) | Baseline: what does the pre-trained model achieve without extensions? |

### 7.3 Explainability Metrics (Phase Quad Advantage)

These metrics are **unique to Phase Quad** — no standard LLM can produce them:

| Metric | Source | What It Shows |
|---|---|---|
| Path attribution (Local/Phase/Quad) | Three-path separation | Which path contributed to this answer? |
| Column phase coherence | ColumnAwarePhaseState | Are same-column values clustering correctly? |
| Header retrieval rate | StructuralBindingAnnotator | Are headers staying in Top-K cache? |
| Cell Vritti distribution | StructuralVrittiValidator | Per-cell FACT/ERROR/IMAGINATION breakdown |
| Schema constraint satisfaction | Constraint head | Per-cell type/range/null/format scores |
| Phase drift per column | compute_phase_health_diagnostics | Is any column's phase angle drifting (instability)? |
| Retrieval diversity | StructuralQuadQuery | Is Top-K covering all columns or over-indexing on one? |

---

## 8. Comparison: Three Approaches to Structured Data

| Dimension | Code-Mediated (Claude) | Post-hoc (TAPAS/TableFormer) | Model-Internal (Phase Quad) |
|---|---|---|---|
| **Architecture** | Standard transformer + Python sandbox | Standard transformer + table linearization + special tokens | Three-path phase transformer + 2D position + column-aware phase |
| **Where structure lives** | External code (pandas) | Flattened input tokens with [SEP]/[HEADER] markers | 2D positional encoding + phase angle separation in complex plane |
| **How it queries** | Generates code: `df[col][condition]` | Learned cell selection via special output heads | Native attention: phase-coherent retrieval within column channels |
| **Cell confidence** | None (code succeeds or fails) | None (standard softmax) | Per-cell Vritti (FACT/ERROR) + constraint satisfaction scores |
| **Failure mode** | Code error → crash → retry | Silent hallucination | Low confidence → flag → escalate via ConfidenceGate |
| **Explainability** | "Here's the code I wrote" | Attention heatmap (post-hoc) | Structural attribution: which path, which column, which retrieval |
| **Mixed content** | Separate: text reasoning vs code execution | Table-only (can't handle surrounding text) | Unified: structural gates activate for table regions, deactivate for text |
| **Strengths** | Exact computation, arbitrary complexity | Pre-trained table understanding | Native 2D awareness, cell-level confidence, conservative degradation |
| **Weaknesses** | Outsourced understanding, no cell confidence | Limited to table-only tasks | Unvalidated, requires structured training data |

---

## 9. Open Questions

1. **Phase separation capacity** — Can the complex plane sustain separation for tables with > 50 columns? Phase angles may crowd.
   - Mitigation: Per-head column assignment (different heads specialize on different column groups)

2. **Cross-table reasoning** — How to handle queries that span multiple tables (JOINs)?
   - Approach: Each table gets a separate row-offset; Quad retrieval spans both tables

3. **Nested structures** — JSON with arbitrary nesting depth vs flat CSV
   - Approach: Nesting depth as additional positional dimension; recursive structural annotation

4. **Training data scale** — How much structured data is needed to learn column-coherent phase accumulation?
   - Estimate: 10-50B tokens of structured data (WikiTables + GitHub + synthetic)

5. **Interference with text reasoning** — Does structural training hurt performance on non-structured tasks?
   - Safeguard: All gates initialized near-zero; structural components are opt-in per token

6. **Arithmetic** — Phase Quad still computes via learned representations, not exact arithmetic. "price × quantity" is approximate.
   - Mitigation: Detect arithmetic operations → route to exact compute (hybrid approach) or accept approximation with confidence bounds

---

## 10. Implementation Priority

| Priority | Component | Effort | Impact | Dependencies |
|---|---|---|---|---|
| **P0** | StructuralAnnotator | 1 week | Enables all downstream work | None |
| **P0** | StructuralPositionEncoder | 3 days | 2D awareness for all paths | Annotator |
| **P1** | StructuralBindingAnnotator | 1 week | Schema-aware Top-K selection | Annotator, 2D position |
| **P1** | ColumnAwarePhaseState | 1 week | Column-coherent memory | 2D position |
| **P2** | StructuralPhaseProjector | 3 days | Structure-conditioned rotation | Column phase |
| **P2** | StructuralQuadQuery | 1 week | Cross-row retrieval | Structural salience |
| **P3** | StructuralVrittiValidator | 1 week | Per-cell confidence | All above trained |
| **P3** | Training curriculum Phase 1 | 2 weeks | Structure recognition | Annotator + all components |
| **P4** | Training curriculum Phase 2 | 2 weeks | Structured reasoning | Phase 1 trained |
| **P4** | Benchmark evaluation | 1 week | Validation | Phase 2 trained |

**Total estimated engineering effort: ~10 weeks** from first line of code to benchmark results.

---

## 11. Summary

Phase Quad's three-path architecture provides genuine architectural foundations for model-internal structural awareness:

- **Local path** naturally maps to **within-row** syntax processing
- **Phase path** naturally maps to **within-column** persistent memory (via phase angle separation)
- **Quad path** naturally maps to **cross-row** retrieval (via structure-biased Top-K)
- **Binding Annotator** naturally extends to **schema-aware** salience
- **Vrittis** naturally extend to **per-cell** reliability validation
- **ConfidenceGate** provides **conservative degradation** that code-mediated approaches lack

None of this exists yet. But unlike post-hoc modifications to standard transformers (special tokens, linearization tricks, output heads), these extensions **follow the grain** of the existing architecture. They don't fight the model — they teach it a new kind of structure using mechanisms it already has.

The gap between Phase Quad and native structured reasoning is **engineering** (training data, positional encoding, auxiliary losses), not **architectural**. The architecture is already right.
