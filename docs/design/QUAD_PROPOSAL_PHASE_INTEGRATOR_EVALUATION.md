# Design Evaluation: Quad-as-Proposer + Phase-as-Integrator Architecture

**Date:** 2026-01-18
**Status:** Evaluation Only (Not Implemented)
**Source:** ChatGPT Proposal
**Evaluated Against:** Symbolu V10.3.8 Architecture

---

## Executive Summary

This document evaluates a proposed architectural reversal where **quadratic attention becomes a proposal generator** and **phase becomes the state integrator that decides meaning**. The goal is to prevent quad from "overpowering" phase through softmax dominance.

### Verdict: Theoretically Sound, But Symbolu Already Has a Different Solution

The proposal correctly identifies the problem (quad dominance via softmax winner-take-all), but **Symbolu's Protected Phase architecture already solves this problem differently** - through gradient routing rather than architectural inversion. The proposed change would be a fundamental paradigm shift, not an incremental improvement.

---

## 1. The Problem Being Addressed

### 1.1 Why Quad Dominates Phase (Root Cause Analysis)

The proposal correctly identifies three properties of quadratic attention that overpower phase:

| Property | Quad | Phase |
|----------|------|-------|
| **Loss Alignment** | Direct path to loss → strong gradients | Indirect (through Local/Quad) → weaker gradients |
| **Competitive Normalization** | Softmax: winner-take-all | Cumsum: additive accumulation |
| **Statefulness** | Stateless: re-decides every step | Stateful: carries forward |

**Consequence:** Even if phase learns, quad decides. PPL improves but semantic coherence doesn't.

### 1.2 Observed Symptoms in Symbolu

The diagnostic probes documented in `phase_transformer.py:2066-2068` confirm:
- When phase is mixed with quad: ~0% ablation drop (DECORATIVE)
- When phase is protected: -50% ablation drop (ESSENTIAL)

This validates the core problem - unprotected phase becomes meaningless.

---

## 2. The Proposed Solution

### 2.1 Core Architectural Change

**Current Symbolu Flow:**
```
tokens → Phase (cumsum) → memory_state
                              ↓
       → Quad (softmax attention over memory_state) → attended output
       → Local (windowed attention) → local output
                              ↓
                        local + quad → output
```

**Proposed Flow:**
```
tokens → Quad (TopK retrieval) → K proposals P = {p₁...pₖ}
                                        ↓
       → Phase (gating weights) → w_i = phase_gate(x, S_t, p_i)
       → Phase (integration)    → S_{t+1} = γS_t + Σwᵢ·ΔSᵢ
                                        ↓
                                  S_{t+1} → output
```

### 2.2 Key Equations (From Proposal)

**Step A: Quad becomes TopK proposal retrieval (no softmax)**
```
q_t = W_q[x_t; S_t]
s_{t,j} = (q_t^T k_j) / √d_k
J_t = TopK(s_{t,·}, K)
P_{t,i} = v_{J_t(i)}   for i = 1..K
```

**Step B: Phase computes gating weights**
```
u_{t,i} = W_u[x_t; S_t; p_{t,i}]
ℓ_{t,i} = w^T tanh(u_{t,i})
w_{t,i} = sigmoid(ℓ_{t,i}) / (Σ sigmoid(ℓ_{t,r}) + ε)
```

**Step C: Phase integrates proposals into state**
```
ΔS_{t,i} = f_φ(x_t, S_t, p_{t,i})
S_{t+1} = γ·S_t + Σ w_{t,i}·ΔS_{t,i}
```

**Step D: Gradient reversal**
```
∂L/∂p_{t,i} = ∂L/∂S_{t+1} · ∂S_{t+1}/∂p_{t,i}
            = ∂L/∂S_{t+1} · (w_{t,i}·∂f_φ/∂p_{t,i} + f_φ·∂w_{t,i}/∂p_{t,i})
```

Quad values learn: "What kinds of proposals are useful for phase integration?"
(Creative gradient, not selection gradient)

---

## 3. Comparison with Symbolu's Current Solution

### 3.1 Symbolu's Protected Phase Pattern

Symbolu already addresses quad dominance through **gradient routing**, not architectural inversion:

```python
# From phase_transformer.py:4466-4493
if self.protected_phase:
    # Phase runs first → outputs memory_state
    phase_memory = self.phase_attn(x, causal_mask, return_state=True)

    # Local's Q attends to Phase's memory_state (K/V)
    # This enforces: "Quadratic queries ONLY Phase memory"
    x_local = self.local_attn(x, causal_mask, phase_memory=phase_memory)

    # NO x_phase in output → gradients flow: loss → Local → Phase
    output = residual + x_local
```

**Key Insight:** Protected Phase makes phase essential by routing gradients through Local→Phase, not by eliminating softmax.

### 3.2 Feature Comparison

| Aspect | Proposed Architecture | Symbolu Protected Phase |
|--------|----------------------|------------------------|
| **Quad role** | Proposal generator (TopK, no softmax) | Memory querier (softmax over TopK) |
| **Phase role** | State integrator + gating | State accumulator (cumsum/EMA) |
| **Who decides meaning?** | Phase (via gating weights) | Local (via cross-attention to phase memory) |
| **Gradient flow** | loss → Phase → Quad values | loss → Local → Phase |
| **Softmax location** | Only in phase gating (over K) | In Quad (over TopK) |
| **State persistence** | Explicit S_{t+1} accumulation | Implicit via cumsum(kv_complex) |

### 3.3 What Symbolu Already Has That Matches the Proposal

1. **TopK Selection** - `BindingCacheQuadQuery` already does TopK (line 2398-2400)
2. **Binding Salience Bias** - Selection bias without modifying attention math (line 2387-2395)
3. **Phase State Accumulation** - O(n) cumsum/EMA in `BindingCachePhaseState` (line 2251-2261)
4. **Bounded Phase** - π·sin() constrains to S¹ manifold (line 2202-2205)
5. **Decay/γ Parameter** - Learned decay per head (line 2112-2125)

### 3.4 What the Proposal Adds That Symbolu Lacks

1. **Phase-computed gating weights** - Currently, Quad does softmax; proposal has Phase do gating
2. **Proposals as discrete objects** - Currently, Quad returns attended vector; proposal returns K separate proposals
3. **Explicit state update formula** - Currently implicit; proposal makes S_{t+1} = γS_t + Σw·ΔS explicit
4. **Query depends on state** - Proposal: q_t = W_q[x_t; S_t]; Current: Q comes only from x

---

## 4. Critical Analysis

### 4.1 Strengths of the Proposal

1. **Clear role separation** - Quad proposes, Phase decides. No ambiguity.
2. **Eliminates softmax competition** - Phase weights are not winner-take-all
3. **Gradients flow through Phase by construction** - Not just by routing
4. **Aligns with predictive coding / active inference** - More biologically plausible
5. **JEPA integration point is natural** - JEPA affects proposals, SRK/Kosha affects gating

### 4.2 Cost Savings Analysis (The Compelling Case for Plan B)

This is where the proposal has significant merit that deserves deeper consideration.

#### Current Symbolu Cost Per Layer (Always Runs All Three Paths)

| Component | Operation | Complexity | Notes |
|-----------|-----------|------------|-------|
| Phase | cumsum(kv_complex) | O(n·d) | Always runs |
| Quad | QK^T scores | O(n·n·d/h) or O(n·k·d/h) with TopK | Always runs |
| Quad | softmax over k | O(n·k) | Always runs |
| Quad | weighted sum V | O(n·k·d/h) | Always runs |
| Local | windowed attention | O(n·w·d/h) | Always runs |
| **Total** | | **O(n·(k+w)·d/h)** | **Fixed cost** |

#### Proposed Cost Per Layer (Conditional Computation)

| Component | Operation | Complexity | Notes |
|-----------|-----------|------------|-------|
| Phase state check | confidence(S_t) | O(d) | Cheap gate |
| **If confident:** | | | |
| └─ Phase only | S_{t+1} = γS_t | O(n·m) | Skip quad entirely |
| **If uncertain:** | | | |
| └─ Quad retrieval | TopK(scores) | O(n·k) | No softmax over values |
| └─ Phase gating | sigmoid(logits) | O(n·K) | K proposals, not k keys |
| └─ Phase integrate | Σw·ΔS | O(n·K·m) | m = state dim |

#### Key Savings

1. **Conditional Quad Invocation**
   ```
   if phase_confidence(S_t) > threshold:
       S_{t+1} = γ * S_t  # O(n·m) - skip quad entirely
   else:
       # Full retrieval + integration
   ```
   - Early layers: High uncertainty → full computation
   - Later layers: State accumulated → often skip quad
   - **Potential 30-50% compute reduction** in later layers

2. **No Softmax Over Values**
   - Current: `softmax(scores) @ V` requires O(n·k·d/h) for weighted sum
   - Proposed: Just return `V[topk_indices]` - pure gather, no multiply-accumulate
   - **Saves ~k multiplications per query position**

3. **State Compression Reduces Downstream Work**
   - S_t is dimension m (can be << embed_dim d)
   - Once meaning is in S_t, don't need to re-derive from tokens
   - **Amortized cost over sequence length**

4. **Adaptive K Based on Uncertainty**
   ```
   K_effective = base_K * (1 - phase_confidence)
   ```
   - High confidence → K=8 (few proposals needed)
   - Low confidence → K=64 (explore more)
   - **Dynamic compute allocation**

#### Quantitative Estimate

For a 12-layer model with n=2048, k=64, w=256, d=768:

| Scenario | Current (GFLOPs) | Proposed (GFLOPs) | Savings |
|----------|------------------|-------------------|---------|
| All layers uncertain | ~X | ~X | 0% |
| 50% layers confident | ~X | ~0.6X | ~40% |
| 75% layers confident | ~X | ~0.4X | ~60% |

*Note: Exact numbers depend on state dimension m and gating overhead*

#### Why This Wasn't Weighted Heavily Initially

My initial evaluation focused on the **semantic** benefits (quad vs phase dominance) rather than **computational** benefits. But the cost savings are real and could be substantial:

1. **Inference speedup** - Confident layers skip quad entirely
2. **Training efficiency** - Fewer FLOPs per step
3. **Scaling properties** - Cost grows with uncertainty, not sequence length
4. **Memory bandwidth** - Fewer value reads when skipping quad

This makes Plan B more attractive for production deployment even if the semantic benefits are uncertain.

### 4.3 Weaknesses / Concerns

1. **Major architectural departure**
   - Not a refactor but a redesign
   - Existing pretrained weights would be incompatible
   - Requires revalidation of all diagnostic probes

2. **Training stability unknowns**
   - Softmax provides gradient stability via bounded outputs
   - Sigmoid+renorm over K proposals is less studied
   - May need entropy regularization (as proposal notes)

3. **Performance regression risk**
   - Proposal explicitly says "PPL won't immediately validate it"
   - May need to accept worse perplexity for better semantic coherence
   - Hard to justify without clear metrics

4. **TopK non-differentiability**
   - Proposal acknowledges: only V values get gradients
   - K values don't learn through selection
   - May need Gumbel-TopK or straight-through estimator

5. **Already solved differently**
   - Protected Phase achieves -50% ablation drop
   - Binding Cache architecture is validated
   - Why replace a working solution?

### 4.3 The Fundamental Question

> Is Symbolu's goal to make phase essential (already achieved via Protected Phase)?
> Or to make phase the **primary meaning bearer** (requires this proposal)?

The proposal is about making phase the **decider**, not just **essential**. This is a philosophical choice about what "phase" means in the architecture.

---

## 5. Implementation Implications

### 5.1 If We Were to Implement (Not Recommended Yet)

**Files requiring changes:**
- `phase_transformer.py`: BindingCacheQuadQuery, BindingCachePhaseState, BindingCacheBlock
- `sovereign/reasoning_kernel.py`: SRK integration points
- `train_hard_probes.py`: New diagnostic metrics

**Minimal surgical patch points:**

```python
# BindingCacheQuadQuery.forward() - Change return type
# FROM:
out = torch.einsum('bhqk,bhqkd->bhqd', attn_weights, top_V)  # attended vector
return self.out_proj(out.reshape(B, N, D))

# TO:
# Return proposals without softmax mixing
return top_V  # [B, H, N, K, D_h] - K proposals per position
```

```python
# BindingCachePhaseState - Add gating and integration
# NEW method:
def integrate_proposals(self, x, proposals, prev_state):
    # proposals: [B, H, N, K, D_h]
    # Compute gating logits
    logits = self.gate_proj(concat(x, prev_state, proposals))  # [B, N, K]
    weights = sigmoid(logits) / (sigmoid(logits).sum(-1, keepdim=True) + eps)

    # Compute state deltas
    deltas = self.delta_proj(concat(x, prev_state, proposals))  # [B, N, K, M]

    # Integrate
    state = self.gamma * prev_state + (weights.unsqueeze(-1) * deltas).sum(dim=2)
    return state
```

### 5.2 Required New Components

1. **Gate projection** - W_gate: [D + M + D_v] → K
2. **Delta projection** - f_φ: [D + M + D_v] → M (state dimension)
3. **State dimension M** - New hyperparameter (currently implicit in embed_dim)
4. **Explicit state tensor** - prev_state must be passed through layers

### 5.3 Training Stability Measures (From Proposal)

1. Start with sigmoid+renorm gating (not softmax)
2. Keep γ ≈ 0.9 (existing)
3. Keep K small (32-64) (existing top_k)
4. Add entropy floor early: L_ent = -λ Σ w_i log(w_i + ε)
5. Decay λ over training

---

## 6. Recommendation

### 6.1 Revised Assessment: Plan B Has Stronger Case Than Initially Evaluated

The proposal is not just theoretically interesting - **the cost savings make it practically compelling**:

| Factor | Initial Weight | Revised Weight | Notes |
|--------|---------------|----------------|-------|
| Semantic benefits | High | Medium | Protected Phase already works |
| Cost savings | Low | **High** | 30-60% potential reduction |
| Implementation risk | High | Medium | Can be done incrementally |
| Production value | Unknown | **High** | Inference speedup matters |

### 6.2 Two-Phase Approach (Recommended)

**Phase 1: Validate Cost Savings (Low Risk)**
1. Add phase confidence metric to current architecture
2. Measure how often phase "could" skip quad (without actually skipping)
3. Instrument: `confident_layers / total_layers` across training
4. If >30% layers show high confidence → proceed to Phase 2

**Phase 2: Incremental Implementation**
1. Start with **inference-only** conditional quad skip
2. Don't change training - just skip quad during eval when confident
3. Measure: speedup vs quality degradation
4. If quality holds → consider training with conditional computation

### 6.3 Conditions That Would Make This Urgent

1. **Inference cost becomes bottleneck** - Production deployment at scale
2. **Long-context scaling needed** - n=8K+ where O(nk) per layer hurts
3. **Edge deployment** - Mobile/embedded where FLOPs matter
4. **Sample quality already good** - Can afford to trade PPL for speed

### 6.4 What NOT to Do

1. Don't implement full architectural reversal immediately
2. Don't remove softmax from quad without measuring confidence first
3. Don't change gradient flow without Protected Phase validation
4. Don't optimize for cost before semantic coherence is achieved

### 6.5 Incremental Steps (If Proceeding)

If we want to move toward this direction without full commitment:

1. **Phase-gated quad output** - Keep softmax but multiply by phase-derived gate
   ```python
   quad_out = softmax(QK^T)V
   phase_gate = sigmoid(gate_proj(phase_state))
   output = quad_out * phase_gate  # Phase modulates, doesn't replace
   ```

2. **Dual-channel scoring** - Already partially implemented in V10.3.8
   ```python
   s_content = cos(φ_q - φ_k)  # What matches
   s_align = cos(θ_JEPA - θ_SRK)  # Intent agreement
   score = s_content * (1 + α * s_align)
   ```

3. **State-conditioned query** - Add state to Q formation
   ```python
   Q = W_q(concat(x, phase_state))  # Query knows accumulated state
   ```

---

## 7. Relationship to Other Symbolu Concepts

### 7.1 SRK/CSR/Kosha/Witness

The proposal suggests:
- **JEPA** → affects scores/query (what to retrieve)
- **SRK/CSR/Kosha/Witness** → affects gating logits (what survives)

This aligns with Symbolu's Master/Sensor duality but inverts control:
- Current: SRK influences φ_k (storage), JEPA influences φ_q (retrieval)
- Proposed: JEPA influences proposals, SRK/Kosha influences integration

### 7.2 Dual-Channel Attention (V10.3.8)

Dual-channel already separates content from intent:
```
s_content = cos(φ_q - φ_k)        # Pure content matching
s_align = cos(θ_JEPA - θ_SRK)     # Intent alignment
```

The proposal would make this separation even more explicit by having:
- Content → proposals
- Intent → gating weights

---

## 8. Open Questions

1. **What is the semantic coherence metric?** Without one, we can't validate the proposal's claims.

2. **How does chunk persistence work?** Current cumsum carries prev_state; proposal's explicit S_t needs similar mechanism.

3. **Where does Local attention fit?** Proposal focuses on Quad/Phase but Symbolu has three paths.

4. **How does this interact with GQA?** Grouped Query Attention may complicate proposal implementation.

5. **What about the FFN?** Proposal doesn't discuss feed-forward; is state used there too?

---

## Appendix A: Pseudocode from Proposal

```python
# Inputs: x_t, S_t, cache K_keys[M,d], V_vals[M,dv]
q = Wq(concat(x_t, S_t))                      # query from content+state
scores = (K_keys @ q) / sqrt(dk)              # [M]
idx = topk(scores, K)                         # discrete indices (K)
P = V_vals[idx]                               # proposals [K,dv]

# phase decides weights (NOT quad softmax)
logits = []
deltas = []
for i in range(K):
    u = Wu(concat(x_t, S_t, P[i]))
    logits.append( w_gate @ tanh(u) )
    deltas.append( f_phi(x_t, S_t, P[i]) )    # proposal -> state update

w = normalize(sigmoid(stack(logits)))         # or softmax(logits/tau)
S_next = gamma * S_t + sum_i( w[i] * deltas[i] )

# output head uses S_next (and maybe x_t)
y = head(concat(x_t, S_next))
return y, S_next
```

---

## Appendix B: Gradient Flow Comparison

### Current (Protected Phase)
```
Token Loss
    ↓
Output (residual + local_out)
    ↓
Local Attention (cross-attends to phase_memory K/V)
    ↓
Phase memory_state (cumsum output)
    ↓
Phase projections (W_k_phase, W_k_amp, W_v)
```

### Proposed
```
Token Loss
    ↓
Output head(x_t, S_{t+1})
    ↓
Phase Integration (S_{t+1} = γS_t + Σw·ΔS)
    ↓
├─ Phase Gating (w_i = gate(x, S_t, p_i))
│       ↓
└─ Quad Proposals (P = V[topk(scores)])
         ↓
    Quad Values (V learned via phase gradients)
```

---

## Appendix C: Success Criteria (If Implemented)

From the proposal:
1. **Quad dominance disappears** - "phase-heavy layers 100%" stops being a warning
2. **Samples improve before PPL** - Fewer punctuation storms, more clause structure
3. **Witness vrittis become meaningful** - Less collapse to IMAGINATION/MISCONCEPTION

---

*Document prepared for architectural evaluation. Implementation deferred pending validation of current Protected Phase experiments.*

---

## Appendix D: ChatGPT Response to Gap Analysis (2026-01-19)

**Context:** After Claude's evaluation identified several "gaps" in the implementation (interface/contract gaps vs conceptual flaws), ChatGPT provided this detailed response with direct answers and minimal paths to close the gaps.

### D.1 OntoControl Struct: Do You Need It?

**Answer: Not strictly.** The current `binding_salience` scalar is effectively an **OntoControl-lite**.

#### When OntoControl is Worth Adding

Add a formal `OntoControl` only if you want:
- **(a)** Interpretability
- **(b)** Consistent control-plane APIs across CSR/Kosha/Onto
- **(c)** Dynamic routing at scale (larger models / multi-task)

#### Minimal OntoControl That Matches Current Codebase

You don't need full `type_logits` immediately. The minimal struct that closes most gaps is:

| Field | Status | Notes |
|-------|--------|-------|
| `binding_salience` | Already exists | Core scalar control |
| `enable_slots` | Derived | From salience + pattern detection |
| `enable_quad` | Derived | From query marker / uncertainty |
| `enable_csr` | Derived | From domain/type |
| `quad_bias_mask` | Optional | Can be scalar bias rather than mask |
| `budget_topk` | Optional | Dynamic K allocation |

This preserves current flow and adds explicit control semantics.

---

### D.2 Dynamic Module Routing: Should Onto Gate BindingSlotCache?

**Answer: Only partially.** Pattern detection (EQ_TOKEN) is a *ground-truth trigger*; Onto is an *inference trigger*.

**Status: ✅ IMPLEMENTED (V10.6.2)**

#### Correct Architecture

| Path | Gating Strategy | Rationale |
|------|-----------------|-----------|
| **Write path** (binding formation) | Keep **hard trigger** based on EQ_TOKEN | Prevents false positives, keeps mechanism crisp |
| **Read path** (retrieval) | Allow Onto/CSR to **bias or gate** | Controlled, debuggable retrieval activation |

**Recommendation:**
- **Don't replace** EQ_TOKEN-based writes with Onto gating
- **Do add** `enable_slots_read` (or `slots_read_weight`) to make retrieval activation explicit and debuggable

This is the best of both worlds: **deterministic writes + controlled reads**.

#### V10.6.2 Implementation

The `enable_slots_read` parameter has been added to:
- `BindingCacheBlock.forward()` - Core block implementation
- `BindingCacheTransformer.forward()` - Transformer wrapper
- `BindingCacheTransformer.forward_hidden()` - Hidden state extraction

When `enable_slots_read=False`:
- Phase write path continues (accumulates memory state)
- Quad read path is skipped (only local attention runs)
- Allows Onto/CSR to gate retrieval without affecting storage

---

### D.3 CSR → Phase Coupling: Should CSR Modulate Phase Decay/Gain?

**Answer: Not by default.** Current design—CSR gating at synthesis/output—is safer.

#### Why "Not Implemented" Is Correct

The intentional avoidance of letting CSR "touch the field dynamics" is a **good conservative choice**.

#### When Dynamic γ/α Modulation Becomes Useful

Only if you observe one of these:
1. Phase health metrics degrade under safety constraints
2. CSR gating causes "thrash" (oscillatory decisions)
3. Model needs "rapid forgetting" under detected contamination (prompt injection / adversarial patterns)

#### Minimal Safe CSR→Phase Modulation (If Needed Later)

Do **not** let CSR modulate per-head learned timescales directly. Instead:
- Keep learned γ as-is
- Apply a small, clamped **global scalar** on integration strength:

```python
α_t = clamp(α_base * α_csr, α_min, α_max)
```

This keeps Phase stable and avoids hard-to-debug dynamics.

**Priority Assessment:** LOW priority, unless diagnostics justify it.

---

### D.4 Failure Modes C and D: What Should You Do?

#### Failure Mode C: "Onto Decides Content"

Claude said "partial" because Onto biases TopK selection. That's fine **as long as it's routing/bias, not templating**.

**Rule to Enforce:**
> Onto may only affect *which memory/proposals are considered*, not *what tokens are output*.

| If Onto does this... | Status |
|---------------------|--------|
| Influences logits directly | ⚠️ **DANGEROUS** |
| Changes retrieval candidates / attention bias | ✅ **OK** |

#### Failure Mode D: "Over-constraint Collapse"

Treat this as **real risk** once you add more control signals.

**Yes: Implement a min-gain clamp (or equivalent)**

Even if untested, it's cheap and prevents degeneracy:

```python
phase_gain = clamp(phase_gain, g_min, g_max)
# Same for any CSR damping multiplier
```

This is a **low-cost safety invariant**.

---

### D.5 No-Write Contracts: Should You Implement Assertions?

**Answer: Yes.** This is the **highest value "gap fix."**

#### What You Want to Prevent

Anything that looks like **token-wise content** being injected into Phase control.

#### What You Want to Allow

Scalars or per-head/per-layer control:
- `[layers, heads]`
- `[batch, heads]`
- `[heads]`
- Broadcastable scalars

#### The Contract in One Sentence

> `intent_phase` (and any control) must be **low-dimensional, broadcastable, and not token-position dependent**.

**Status: ✅ IMPLEMENTED (V10.6.2, UPDATED V10.6.3)**

#### V10.6.3 Clarification

> Control signals may be **scalar or per-head**, but must **never vary across token positions**.

This means `[B, N]` (token-position scalar) is **INVALID for alignment signals** because:
- Token-wise scalar still leaks structural information into Phase
- Allows alignment to suppress/amplify specific tokens
- Phase turns into a soft attention map

**Exception:** `[B, N]` is **ONLY valid for `binding_salience`** which explicitly needs per-position gating.

See **D.10** for full correction details and shape validation table.

#### Specific Checks

| Check | Pass Condition |
|-------|----------------|
| Sequence length dimension | Must NOT have (except binding_salience) |
| `d_model` last dim | Must NOT have |
| Shape compatibility | Must be broadcastable to `[B, H, 1, 1]`-like shapes |
| Alignment signals | Must be `[H]`, `[]`, or `[B, H]` - NOT `[B, N]` |

This is the single best way to make the **"Phase integrates influence, not structure"** principle enforceable.

#### V10.6.2 Implementation

Shape assertion utilities added to `phase_transformer.py`:
- `assert_control_shape()` - Validates individual control signals
- `validate_control_signals()` - Validates multiple controls at once
- `ControlShapeViolation` - Exception for strict mode violations
- `assert_alignment_signal_shape()` - Validates alignment signals are NOT `[B, N]` (V10.6.3)

---

### D.6 Test Priority Matrix

**Status: ✅ IMPLEMENTED (V10.6.2)**

Claude's test list is solid. Prioritize like this:

#### HIGH Priority (Do These Now) - ✅ DONE

| Test | Purpose | Status |
|------|---------|--------|
| **Leak detector test** | Assert control signals cannot be token-wise embeddings | ✅ `test_hard_probes_d6_control_plane.py` Group A |
| **AR regression** | Enable/disable Onto & CSR controls and verify AR accuracy does not collapse | ✅ `test_hard_probes_d6_control_plane.py` Group B |

#### MEDIUM Priority

| Test | Purpose |
|------|---------|
| **WikiText2 sanity** | Confirm quad remains mostly dormant; measure quad utilization and gate distributions |

#### OPTIONAL (After Formalization)

| Test | Purpose |
|------|---------|
| OntoControl struct tests | Only after you formalize OntoControl |

#### Additional D.2 Tests - ✅ DONE

| Test | Purpose | Status |
|------|---------|--------|
| **enable_slots_read tests** | Verify read path gating works correctly | ✅ `test_hard_probes_d6_control_plane.py` Group C |

---

### D.7 Current PoC Status Assessment

#### What Can Be Claimed With Evidence

| Status | Claim |
|--------|-------|
| ✅ | Quad proposals + Phase integrator works |
| ✅ | Identity is isolated (BindingSlotCache) and retrieval is correct (96%+) |
| ✅ | CSR/Kosha influence Phase through scalar control, not content injection |
| ✅ | Control-plane API explicit via `enable_slots_read` (V10.6.2 - D.2) |
| ✅ | No-write contracts enforced via `assert_control_shape()` (V10.6.2 - D.5) |
| ✅ | HIGH priority tests implemented (V10.6.2 - D.6) |

**Assessment:** This is a **strong PoC** with **enforced invariants**. The remaining work is expanding test coverage.

---

### D.8 Direct Answers Summary

| Question | Answer | Status |
|----------|--------|--------|
| Do we need OntoControl? | Not yet; a minimal control struct later is enough | Deferred |
| Should Onto gate slots? | Gate slot *reads*; keep slot *writes* deterministic via EQ_TOKEN | ✅ V10.6.2 |
| Should CSR modulate γ? | Only if diagnostics demand it; otherwise keep CSR at synthesis/output | Deferred |
| What's the top priority? | **Enforce no-write contracts + add regression tests** | ✅ V10.6.2 |

---

### D.9 Implementation Recommendations

#### Immediate Actions (Gap Closure) - ✅ COMPLETED V10.6.2

1. **Add shape assertions for control signals** ✅
   ```python
   # Implemented in phase_transformer.py
   def assert_control_shape(tensor, name, d_model, seq_len=None, strict=True):
       """Enforce no-write contract: control must not be token-wise."""
       # Checks: dim <= 4, no d_model last dim, no seq_len dim, no [B,N,D] shape
       ...

   def validate_control_signals(d_model, seq_len=None, strict=True, **controls):
       """Validate multiple control signals at once."""
       ...
   ```

2. **Add `enable_slots_read` control flag** ✅
   - Added to `BindingCacheBlock.forward()`
   - Added to `BindingCacheTransformer.forward()` and `forward_hidden()`
   - Separate from write path (which stays deterministic)
   - Allows Onto/CSR to gate retrieval without affecting storage

3. **Add min-gain clamp as safety invariant** ✅
   - Already present in alignment clamp (V10.6.1)

4. **Add D.6 HIGH priority tests** ✅
   - `tests/test_hard_probes_d6_control_plane.py`
   - Group A: Leak detector tests (10 tests)
   - Group B: AR regression tests (7 tests)
   - Group C: enable_slots_read tests (6 tests)

#### Deferred Actions

- Formal OntoControl struct (wait for multi-task/scaling needs)
- CSR→Phase γ modulation (wait for diagnostic evidence)
- Full type_logits implementation (not needed for current PoC)

---

### D.10 V10.6.3: Alignment Signal Shape Correction (ChatGPT Feedback)

**Date:** 2026-01-19

#### The Problem

The V10.6.2 implementation had a subtle contract violation in the example code:

```python
# PREVIOUS (INCORRECT):
s_align = cos(θ_JEPA - θ_SRK).mean(dim=-1)  # [B, N] - scalar per position
phase_output = phase_output * (1 + α * s_align)
```

**Why `[B, N]` violates the contract:**

Even though `[B, N]` looks like "just a scalar per position," it is **token-position dependent**:
- ❌ Token-wise scalar still leaks structural information into Phase
- ❌ Allows alignment to suppress/amplify *specific tokens*
- ❌ Phase turns into a soft attention map
- ❌ This reintroduces the failures from intent sneaking into Phase

#### The Correction

**The updated contract rule:**
> Control signals may be scalar or per-head, but must **never vary across token positions**.

**Correct implementation options:**

| Option | Code | Shape | Description |
|--------|------|-------|-------------|
| A (safest) | `s_align = cos(θ_diff).mean()` | `[]` | Batch-level scalar |
| B (recommended) | `s_align = cos(θ_diff).mean(dim=(0, 1, 3))` | `[H]` | Per-head control |
| C | `s_align = cos(θ_diff).mean(dim=(1, 3))` | `[B, H]` | Per-batch per-head |

#### Updated Shape Validation Table

| Shape | Valid? | Reason |
|-------|--------|--------|
| `[]` | ✅ | Global scalar (safest) |
| `[H]` | ✅ | Per-head control (recommended for alignment) |
| `[B, H]` | ✅ | Per-batch per-head |
| `[B, H, D_h]` | ✅ | Per-head rotation (for intent_phase) |
| `[B, N]` | ⚠️ | **ONLY valid for `binding_salience`** (explicitly per-position gating) |
| `[B, N]` | ❌ | **INVALID for `s_align`** (token-position dependent = leaks structure) |
| `[B, N, D]` | ❌ | Full embedding (content injection) |
| `[B, N, H, D_h]` | ❌ | Per-position per-head embeddings |

#### Implementation Changes (V10.6.3)

1. **`phase_transformer.py`**:
   - Added `assert_alignment_signal_shape()` for stricter validation
   - Updated contract docstrings to clarify `[B, N]` restrictions
   - Added V10.6.3 clarification note

2. **`train_hard_probes.py`**:
   - Updated `compute_alignment_score()` to return `[H]` or `[]` (not `[B, N]`)
   - Added `--alignment-reduction` flag: `per_head` (default), `global`, `per_batch_head`
   - Added `--strict-control-contract` / `--no-strict-control-contract` flags
   - Updated `integrate_proposals()` to handle new s_align shapes

3. **Config additions**:
   - `alignment_reduction: str = "per_head"`
   - `strict_control_contract: bool = True`

#### Status

| Item | Status |
|------|--------|
| Contract documentation updated | ✅ V10.6.3 |
| `compute_alignment_score()` fixed | ✅ V10.6.3 |
| `assert_alignment_signal_shape()` added | ✅ V10.6.3 |
| Strict vs warn mode flag | ✅ V10.6.3 |
| Shape table updated | ✅ V10.6.3 |

---

*V10.6.3 update 2026-01-19. Source: ChatGPT feedback on alignment signal shape contract violation.*

---

*Appendix added 2026-01-19. Source: ChatGPT analysis of Claude evaluation gaps.*
