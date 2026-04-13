# Mistral CG Domain Conditioning Architecture

Combined design spec integrating the existing SymbolU CG infrastructure with
domain-conditioned generation capabilities.

---

## Section 0 — Evaluation: What Exists vs What's New

Before designing, we must reconcile the ChatGPT proposal with what the
codebase already implements. This section is the audit.

### 0.1 Mapping Table

| ChatGPT Concept | Existing Module | Status | Gap |
|-----------------|----------------|--------|-----|
| **DomainStateProjector** | `SovereignStateProjector` (32D) + `domain_bridge.py` (3→8D) | PARTIAL | Existing projects 32D sovereign state. Domain detection is hardcoded 3-category (LANG/MATH/CODE) mapped to 8D soft distribution. No learned domain classifier. No risk/evidence/tone/action sub-distributions. |
| **DomainRouter** | `KoshaDomainRouter` (`kosha_router.py`) | EXISTS | Routes over 6 CG primitives using Kosha[12:17] × domain interaction. Trainable. But routes primitives, not adapters. |
| **DomainAdapters** | `phase_adapter` in `MistralCGWrapper` | PARTIAL | Single shared adapter (Bhava→phase→hidden residual). No per-domain adapters. No MoE-style routing across adapters. |
| **DomainShortlistReranker** | `IntegratedTokenScorer` + `FieldIntegratedSoftmax` + `TwoStageGenerator` | EXISTS (training-only) | Full shortlist rescoring pipeline. All 4 primitive scorers implemented. NOT wired into inference. |
| **DomainSamplingPolicy** | Vritti/Guna temperature gates in `MistralCGAdapter.call()` | PARTIAL | Temperature modulation from sovereign state slices exists. No explicit top-p, abstain threshold, or retrieval threshold control. |
| **Domain Data Schema** | `domain_bridge.py` + Gyroscope labels | PARTIAL | 3 coarse labels (LANG/MATH/CODE) → 8D soft distribution. No per-sample risk, evidence, tone, or action annotations. |
| **Teacher Signals** | `GovernanceService` + 18 signal adapters in `agentic/` | NOT WIRED | Full governance pipeline exists in agentic framework but produces inference-time decisions only. Not used as training labels. |

### 0.2 What the ChatGPT Spec Gets Right

1. **Five-layer separation** (base generator / domain state / conditioning /
   inference control / training supervision) — clean and maps well to the
   existing CG phases.

2. **Structured domain policy vector** z_dom = [d, r, e, t, a] — richer than
   the current flat 8D domain distribution. Risk, evidence requirement, tone,
   and action mode are genuinely useful signals.

3. **Teacher distillation from agentic framework** — the existing
   GovernanceService + DomainPolicyInterpreter + 18 signal adapters produce
   exactly the labels needed (risk level, action mode, confidence band). This
   is the biggest untapped resource.

4. **Phased deployment** — matches the existing CG curriculum pattern. Phase 1
   (domain projector only) through Phase 5 (domain-native scoring) is
   practical.

5. **Explicit ablation plan** — measurable and testable.

### 0.3 What Needs Reconciliation

1. **Domain taxonomy**: ChatGPT proposes 10 domains. Existing codebase has 8
   (`code, math, factual, chat, emotional, narrative, planning, retrieval`).
   The agentic `DomainProfile` registry is open-ended. Must unify.

2. **Router target**: ChatGPT routes α over per-domain adapters.
   Existing `KoshaDomainRouter` routes α over 6 CG primitives.
   These are different routing problems — adapter routing and primitive
   routing should coexist, not replace each other.

3. **Sovereign state relationship**: ChatGPT's z_dom is independent.
   In the existing architecture, domain state should be derived from or
   extend the 32D sovereign state, not be a parallel system. The Kosha
   slice [12:17] already encodes domain-like information.

4. **Phase adapter vs domain adapters**: The existing phase adapter is
   Bhava-conditioned. ChatGPT proposes per-domain adapters. These are
   complementary — the phase adapter provides state-conditioned correction,
   domain adapters provide domain-specialized correction. Both should exist.

5. **Inference wiring**: The existing `TwoStageGenerator` docstring
   explicitly states "NOT wired into MistralCGAdapter.call()". The ChatGPT
   spec assumes a reranker at inference. This is the primary engineering
   task.

### 0.4 What's Genuinely New (Must Be Built)

| Component | Why It Doesn't Exist Yet |
|-----------|-------------------------|
| **Learned domain classifier** | Current domain detection is hardcoded Gyroscope mapping. Need a learned projector from hidden states → domain distribution. |
| **Risk / evidence / tone / action sub-projectors** | Current domain state is flat. The structured z_dom = [d, r, e, t, a] is new. |
| **Per-domain adapters** | Only one shared phase adapter exists. Per-domain LoRA or MLP adapters are new. |
| **Domain adapter router** | Existing router targets primitives, not adapters. Need separate adapter routing. |
| **DomainSamplingPolicy module** | No explicit module maps domain state → sampling parameters. Current Vritti/Guna gates are implicit. |
| **Teacher signal pipeline** | No mechanism to extract agentic GovernanceService outputs as training labels. |
| **Domain-annotated training data** | No per-sample domain/risk/tone metadata in current datasets. |

---

## Section 1 — Objective, Scope, Principles

### 1.1 Objective

Extend Mistral CG so it can express domain-specific behavior at inference
without replacing the base Mistral decoder. The system must:

- Keep Mistral as the base language engine (frozen backbone, frozen LM head)
- Inject domain-specific control at inference through learned adapters and
  shortlist rescoring
- Capture domain logic during training via teacher signals from the agentic
  governance framework
- Support multiple domains cleanly without per-domain model copies
- Preserve ablatability, observability, and the existing CG infrastructure

**Primary goal**: Domain-aware, domain-conditioned generation first.
Domain-native token scoring (replacing softmax) is a future phase, gated
by ablation evidence.

### 1.2 Scope

**In scope:**
- Learned domain state projector (extending sovereign state)
- Per-domain adapter routing (MoE-style, alongside existing phase adapter)
- Shortlist rescoring at inference (wiring existing TwoStageGenerator)
- Domain-conditioned sampling policy
- Teacher signal pipeline from agentic framework → training labels
- Ablation plan with measurable metrics

**Out of scope (future work):**
- Replacing Mistral softmax with domain-native token scoring
- Multi-model ensemble or domain-specific fine-tunes
- Retrieval-augmented generation integration
- Real-time domain detection from streaming input

### 1.3 Design Principles

1. **Extend, don't replace.** The existing 32D sovereign state, phase adapter,
   and CG primitive scorers continue to operate unchanged. Domain conditioning
   layers are additive.

2. **Five-layer separation.** Each layer has a clear boundary:
   - Layer 1: Base generator (frozen Mistral + LM head)
   - Layer 2: Domain state (sovereign state + domain policy vector)
   - Layer 3: Conditioning (phase adapter + domain adapters)
   - Layer 4: Inference control (shortlist reranker + sampling policy)
   - Layer 5: Training supervision (domain losses + teacher distillation)

3. **Fail-open at inference.** If domain detection fails or returns
   `general`, the system degrades to the existing CG path (phase adapter
   only, no domain-specific routing). No domain-specific code is required
   for generation to work.

4. **Observability first.** Every new module logs its outputs at the same
   cadence as existing CG diagnostics. Domain routing weights, domain state,
   adapter contributions, and reranker decisions are all visible in training
   logs and TensorBoard.

5. **Train with teacher labels, infer without them.** The agentic
   GovernanceService provides rich domain labels during training. At
   inference, the learned DomainStateProjector must produce equivalent
   signals from hidden states alone.

6. **Ablate before advancing.** Each deployment phase requires ablation
   evidence before the next phase activates. No phase is assumed to help.

---

## Section 2 — Unified Domain Model

### 2.1 Domain Taxonomy

Reconcile the three existing domain systems into one:

| Source | Domains | Notes |
|--------|---------|-------|
| Existing `domain_bridge.py` | code, math, factual, chat, emotional, narrative, planning, retrieval (8) | Soft 8D distribution from Gyroscope |
| ChatGPT proposal | general, code, legal, medical, finance, enterprise_support, research, creative, safety_sensitive, spiritual_reflection (10) | Broader but no existing training signal |
| Agentic `DomainProfile` | Open registry, string-keyed | Extensible but no fixed schema |

**Unified taxonomy (K=12):**

```
DOMAINS = [
    "general",              # 0  — default / unclassified
    "code",                 # 1  — programming, devops
    "math",                 # 2  — formal reasoning, proofs
    "factual",              # 3  — knowledge retrieval, QA
    "creative",             # 4  — narrative, poetry, fiction
    "conversational",       # 5  — chat, dialogue, social
    "research",             # 6  — academic, analytical
    "medical",              # 7  — clinical, health
    "legal",                # 8  — regulatory, compliance
    "finance",              # 9  — markets, accounting
    "safety_sensitive",     # 10 — high-stakes, escalation-prone
    "spiritual_reflection", # 11 — contemplative, philosophical
]
```

**Backward compatibility:** The existing 8D `domain_bridge.py` maps into this
12D space via a fixed projection matrix. Gyroscope LANG → soft blend of
`[general, factual, creative, conversational]`. Gyroscope CODE → `[code]`.
Gyroscope MATH → `[math, factual]`.

### 2.2 Domain Policy State Vector

Extend domain representation beyond a flat distribution. Each token step
computes a structured domain policy vector:

```
z_dom = [d ; r ; e ; t ; a]
```

| Sub-vector | Dim | Activation | Meaning |
|------------|-----|------------|---------|
| **d** — domain distribution | 12 | softmax | Which domain(s) this context belongs to |
| **r** — risk profile | 3 | softmax | [low, medium, high] risk level |
| **e** — evidence requirement | 3 | softmax | [none, preferred, required] |
| **t** — tone mode | 4 | softmax | [direct, cautious, empathetic, exploratory] |
| **a** — action mode | 4 | softmax | [answer, clarify, retrieve, abstain] |
| **Total** | **26** | | |

**Relationship to sovereign state:** z_dom is projected FROM the sovereign
state, not parallel to it:

```
z_sov = state_projector(hidden)           # existing 32D
z_dom = domain_projector(z_sov, hidden)   # new 26D, derived from both
```

This preserves the sovereign state as the source of truth. The domain
projector learns to extract domain-relevant signals from the same
representation that drives Bhava, Kosha, Vritti, and Guna.

### 2.3 Mapping to Agentic Framework

The agentic `DomainPolicyInterpreter` produces `DomainPolicyResult` with:
- `mode: DomainActionMode` (7 levels: ALLOW → BLOCKED)
- `fired_rules`, `reason_codes`, `rationale`

The signal adapters produce:
- Risk signals (from `sovereign_health_adapter`, `plasticity_adapter`)
- Evidence signals (from `insight_adapter`, `predictive_signals_adapter`)
- Tone signals (from `output_modulation_adapter` DHA tone weights)
- Action signals (from `readiness_adapter` status)

These map to z_dom sub-vectors as **teacher labels** during training:

| Agentic Output | z_dom Target |
|----------------|-------------|
| `GovernanceService.authorize()` risk level | **r** (risk profile) |
| `InsightResolution.eligible` + `can_release` | **e** (evidence requirement) |
| `OutputModulationResolution.dha_tone_weights` | **t** (tone mode) |
| `ReadinessResolution.status` + action mode | **a** (action mode) |
| Gyroscope label + `DomainProfile.domain_id` | **d** (domain distribution) |

---

## Section 3 — Architecture: Layers and Forward Pass

### 3.1 Current Forward Pass (Baseline)

Reference: `mistral_wrapper.py:310-444`

```
x → frozen_Mistral_backbone → h_base [B, T, 4096]
h_base → state_projector(mean_pool(h_base)) → z_sov [B, 32]
z_sov → delta_bhava [B, 12]
delta_bhava → intent_projector → intent_phase [B, H]
intent_phase → phase_adapter → adapter_out [B, T, 4096]
h_adapted = h_base + sigmoid(gate) * adapter_out
logits = LM_head(h_adapted) [B, T, V]
```

No domain-specific logic touches logits. The phase adapter is the sole
learned modification, conditioned on Bhava (sovereign state [0:12]).

### 3.2 Proposed Forward Pass (Domain-Conditioned)

```
# Layer 1: Base generator (unchanged)
x → frozen_Mistral_backbone → h_base [B, T, 4096]

# Layer 2: Domain state
h_base → state_projector(mean_pool(h)) → z_sov [B, 32]        # existing
z_sov, h_base → domain_projector → z_dom [B, 26]              # NEW

# Layer 3: Conditioning
z_sov → delta_bhava → intent_phase → phase_adapter → A_shared  # existing
z_dom → domain_router → α [B, N+1]                             # NEW
z_dom, h_base → domain_adapters → A_1..A_N                     # NEW
h_adapted = h_base + gate_shared * A_shared
                   + Σ_i α_i * gate_dom * A_i

# Layer 1 continued: Logits
logits = LM_head(h_adapted) [B, T, V]

# Layer 4: Inference control (optional, inference-time only)
top_K = logits.topk(K)                                          # NEW
Z_star = integrated_scorer(T, h_base, z_sov, z_dom.d, top_K)   # existing module, NEW wiring
logits_final = interpolate(logits[top_K], Z_star, λ_rerank)     # NEW
T_eff, p_top, ... = sampling_policy(z_dom)                      # NEW
token = sample(logits_final, T_eff, p_top)
```

### 3.3 Layer Dependency Diagram

```
Layer 1          Layer 2           Layer 3              Layer 4
─────────        ────────          ────────             ────────
                                                        (inference only)
h_base ──────┬── z_sov ──────┬── phase_adapter ─┐
             │               │                   │
             ├── z_dom ──┬───┤── domain_router   ├── h_adapted ── logits
             │           │   │                   │        │
             │           │   ├── domain_adapters ┘        │
             │           │   │                            ▼
             │           │   │                      shortlist_reranker
             │           │   │                            │
             │           └───┴── sampling_policy ── T_eff, p_top
             │                                            │
             └────────────────────────────────────── final token
```

### 3.4 Key Constraints

1. **h_base is detached for domain adapters.** Domain adapters receive
   `h_base.detach()` — no backbone gradients flow through domain conditioning.
   Only adapter parameters train. (Same pattern as existing phase adapter.)

2. **z_dom derives from z_sov.** The domain projector takes sovereign state
   as primary input. This ensures domain detection is grounded in the same
   representation the CG governance system uses, and gradients from domain
   losses also train the state projector.

3. **Phase adapter and domain adapters are additive.** The phase adapter
   continues to provide Bhava-conditioned correction. Domain adapters
   provide additional domain-specialized corrections. Their outputs sum.

4. **Shortlist reranker is inference-optional.** During training, the
   existing CG curriculum (Stages C/D) trains the primitive scorers and
   IntegratedTokenScorer via auxiliary losses. At inference, the reranker
   runs only if explicitly enabled (Mode C/D in Section 6).

5. **Domain router uses sparse top-2.** With 12 domains but typically 1-2
   active, sparse routing avoids computing all domain adapters. Only the
   top-2 routed adapters execute their forward pass.

---

## Section 4 — Module Definitions

### 4.1 DomainStateProjector (NEW)

**Purpose:** Infer structured domain policy state from sovereign state and
hidden representation.

**Inputs:**
- `z_sov` [B, 32] — sovereign state (from existing SovereignStateProjector)
- `h_pool` [B, D] — mean-pooled hidden states

**Outputs:**
- `z_dom` [B, 26] — structured domain policy vector

**Architecture:**
```python
class DomainStateProjector(nn.Module):
    def __init__(self, state_dim=32, hidden_dim=4096, intermediate=128):
        # Shared trunk: [z_sov; h_pool] → intermediate representation
        self.trunk = nn.Sequential(
            nn.Linear(state_dim + hidden_dim, intermediate),
            nn.GELU(),
            nn.LayerNorm(intermediate),
        )
        # Per-facet projection heads
        self.head_d = nn.Linear(intermediate, 12)   # domain distribution
        self.head_r = nn.Linear(intermediate, 3)    # risk profile
        self.head_e = nn.Linear(intermediate, 3)    # evidence requirement
        self.head_t = nn.Linear(intermediate, 4)    # tone mode
        self.head_a = nn.Linear(intermediate, 4)    # action mode

    def forward(self, z_sov, h_pool):
        x = self.trunk(torch.cat([z_sov, h_pool], dim=-1))
        d = F.softmax(self.head_d(x), dim=-1)  # [B, 12]
        r = F.softmax(self.head_r(x), dim=-1)  # [B, 3]
        e = F.softmax(self.head_e(x), dim=-1)  # [B, 3]
        t = F.softmax(self.head_t(x), dim=-1)  # [B, 4]
        a = F.softmax(self.head_a(x), dim=-1)  # [B, 4]
        z_dom = torch.cat([d, r, e, t, a], dim=-1)  # [B, 26]
        return z_dom, {'d': d, 'r': r, 'e': e, 't': t, 'a': a}
```

**Parameters:** ~530K (dominated by trunk Linear(4128, 128)).
**Init:** Xavier normal, gain=0.3 → near-uniform initial distributions.

### 4.2 DomainAdapterRouter (NEW)

**Purpose:** Compute sparse mixture weights over domain-specific adapters.

**Inputs:**
- `z_sov` [B, 32] — sovereign state
- `z_dom` [B, 26] — domain policy state

**Outputs:**
- `α` [B, N+1] — routing weights (α_0 = shared, α_1..N = per-domain)
- `top_indices` [B, top_k] — which adapters to activate

**Architecture:**
```python
class DomainAdapterRouter(nn.Module):
    def __init__(self, state_dim=32, dom_dim=26, num_adapters=12, top_k=2):
        self.router = nn.Linear(state_dim + dom_dim, num_adapters + 1)
        self.top_k = top_k
        # Load balancing loss coefficient
        self.balance_coeff = 0.01

    def forward(self, z_sov, z_dom):
        logits = self.router(torch.cat([z_sov, z_dom], dim=-1))
        # Sparse top-k routing
        top_vals, top_idx = logits.topk(self.top_k, dim=-1)
        α_sparse = F.softmax(top_vals, dim=-1)
        # Load balance auxiliary loss
        balance_loss = self._load_balance_loss(logits)
        return α_sparse, top_idx, balance_loss
```

**Parameters:** ~800 (Linear(58, 13)).
**Relationship to KoshaDomainRouter:** These are separate routers. The
KoshaDomainRouter routes over CG primitives (6 ways) for the training
loss pipeline. The DomainAdapterRouter routes over inference-time adapters
(12+1 ways). Both consume z_sov but serve different purposes.

### 4.3 DomainAdapters (NEW)

**Purpose:** Provide domain-specialized hidden-state corrections.

**Structure:** One shared adapter (always active) + one lightweight adapter
per domain. Each adapter is a bottleneck MLP:

```python
class DomainAdapter(nn.Module):
    def __init__(self, hidden_dim=4096, dom_dim=26, bottleneck=64):
        self.down = nn.Linear(hidden_dim, bottleneck)
        self.dom_proj = nn.Linear(dom_dim, bottleneck)  # domain conditioning
        self.up = nn.Linear(bottleneck, hidden_dim)
        # Zero-init output → starts as identity
        nn.init.zeros_(self.up.weight)
        nn.init.zeros_(self.up.bias)

    def forward(self, h, z_dom):
        x = F.gelu(self.down(h) + self.dom_proj(z_dom.unsqueeze(1)))
        return self.up(x)  # [B, T, D]
```

**Parameters per adapter:** ~530K (two Linear(4096, 64) + Linear(26, 64)).
**Total for 12 + 1 shared:** ~6.9M parameters.

**Alternative: LoRA adapters.** If parameter budget is tight, replace
bottleneck MLP with rank-16 LoRA (A: 4096×16, B: 16×4096) at ~131K per
adapter, ~1.7M total. Decision deferred to ablation (Section 6).

### 4.4 DomainShortlistReranker (WIRING EXISTING)

**Purpose:** Inject domain-specific scoring at inference without replacing
the decoder softmax.

This module wires the existing `IntegratedTokenScorer` +
`FieldIntegratedSoftmax` into the inference path. No new modules needed.

**Inference flow:**
```python
# Step 1: Get top-K candidates from base logits
base_logits = LM_head(h_adapted)                    # [B, T, V]
top_k_logits, top_k_ids = base_logits.topk(K)       # [B, T, K], K=64

# Step 2: Compute primitive scores over shortlist
# (Uses existing TokenPrimitiveCache, refreshed once at model load)
T = token_eval_tensor.assemble(
    h_base, z_sov, top_k_ids, cache)                 # [B, T, K, 6]

# Step 3: Route and integrate via existing CG modules
integ = integrated_scorer(
    T, h_base, z_sov, z_dom.d, top_k_ids)           # existing module
Z_star = integ['Z_star']                              # [B, T, K]

# Step 4: Interpolate base logits with domain-scored logits
λ = sigmoid(rerank_gate)  # learned scalar, init=-2 → λ≈0.12
final_logits = (1 - λ) * top_k_logits + λ * Z_star

# Step 5: Sample from reranked shortlist
probs = F.softmax(final_logits, dim=-1)
token = sample(probs)
```

**Parameters:** ~10 new (one `rerank_gate` scalar + optional interpolation
MLP). All scoring parameters come from existing trained CG modules.

**Training:** The CG curriculum (Stages C/D) already trains the primitive
scorers, KoshaDomainRouter, and BlissTokenGate. The reranker simply
reuses their learned representations at inference.

### 4.5 DomainSamplingPolicy (NEW)

**Purpose:** Convert domain state into explicit sampling controls.

**Inputs:**
- `z_dom` [B, 26] — domain policy state

**Outputs:**
- `T_eff` — effective temperature
- `p_top` — nucleus sampling threshold
- `rep_penalty` — repetition penalty
- `τ_abstain` — abstention confidence threshold
- `τ_retrieve` — retrieval trigger threshold

**Architecture:**
```python
class DomainSamplingPolicy(nn.Module):
    def __init__(self, dom_dim=26):
        self.w_T = nn.Linear(dom_dim, 1)        # temperature
        self.w_p = nn.Linear(dom_dim, 1)        # top-p
        self.w_rep = nn.Linear(dom_dim, 1)      # repetition penalty
        self.w_abstain = nn.Linear(dom_dim, 1)  # abstain threshold
        self.w_retrieve = nn.Linear(dom_dim, 1) # retrieval threshold
        # Base values
        self.T_0 = 0.7
        self.p_0 = 0.9
        self.rep_0 = 1.1

    def forward(self, z_dom):
        T_eff = self.T_0 * (1 + torch.tanh(self.w_T(z_dom)))
        T_eff = T_eff.clamp(0.1, 2.0)

        p_top = self.p_0 + 0.1 * torch.tanh(self.w_p(z_dom))
        p_top = p_top.clamp(0.5, 1.0)

        rep_penalty = self.rep_0 + 0.2 * torch.tanh(self.w_rep(z_dom))
        rep_penalty = rep_penalty.clamp(1.0, 1.5)

        τ_abstain = torch.sigmoid(self.w_abstain(z_dom))
        τ_retrieve = torch.sigmoid(self.w_retrieve(z_dom))

        return {
            'temperature': T_eff,
            'top_p': p_top,
            'repetition_penalty': rep_penalty,
            'abstain_threshold': τ_abstain,
            'retrieve_threshold': τ_retrieve,
        }
```

**Parameters:** ~135 (5 × Linear(26, 1)).

**Expected domain behavior (learned, not hardcoded):**

| Domain | T_eff | p_top | τ_abstain | τ_retrieve |
|--------|-------|-------|-----------|------------|
| code | low (0.3-0.5) | low (0.7) | low | low |
| medical | low (0.4-0.6) | mid (0.8) | high | high |
| creative | high (0.9-1.2) | high (0.95) | low | low |
| finance | low (0.4-0.6) | mid (0.8) | high | mid |
| general | mid (0.7) | mid (0.9) | mid | mid |

These are learned from teacher signals, not hardcoded.

---

## Section 5 — Training Design

### 5.1 Composite Training Objective

```
L = L_tok + λ_dom L_dom + λ_route L_route + λ_policy L_policy
    + λ_cal L_cal + L_CG_existing
```

where `L_CG_existing` encompasses the current CG losses (ontological,
kosha routing, bliss coherence, vritti, guna, JEPA, CSR) — unchanged.

### 5.2 Loss Components

**A. Token loss (existing, unchanged):**
```
L_tok = -Σ_t log p(x_t | x_{<t})
```

**B. Domain classification loss (NEW):**

Train z_dom sub-vectors to match teacher labels:
```
L_dom = CE(d, d*) + CE(r, r*) + CE(e, e*) + CE(t, t*) + CE(a, a*)
```

where d*, r*, e*, t*, a* are teacher labels from the agentic framework
(see Section 5.3). Each CE term is weighted equally initially; can be
tuned per-facet if needed.

**C. Router balance loss (NEW):**

Prevent routing collapse to a single domain adapter:
```
L_route = balance_coeff * CV(load)²
```

where `load_i = Σ_batch 1[i ∈ top_k]` counts how often each adapter is
selected, and CV is the coefficient of variation. This is standard MoE
load balancing.

If teacher routing labels exist:
```
L_route += KL(α || α*)
```

**D. Policy distillation loss (NEW):**

Distill agentic framework decisions into sampling policy parameters:
```
L_policy = CE(a, a_teacher) + CE(e, e_teacher)
           + MSE(T_eff, T_teacher) + MSE(τ_abstain, τ_teacher)
```

where teacher values come from GovernanceService + signal adapter outputs.

**E. Calibration loss (NEW, safety-sensitive domains only):**

For domains where overconfidence is dangerous (medical, legal, finance,
safety_sensitive):
```
L_cal = E[max(0, conf - conf_target) * 1_wrong]
```

This penalizes high-confidence wrong predictions specifically in
high-stakes domains. Active only when `r_high > 0.5` in the domain
state vector.

### 5.3 Teacher Signal Pipeline

**This is the bridge between the agentic framework and training.**

The agentic GovernanceService + 18 signal adapters already produce
structured decisions at inference. The teacher pipeline runs these
modules offline on training data to produce per-sample labels.

**Offline labeling workflow:**

```
training_sample →
  1. Run frozen Mistral forward → h_base
  2. Run SovereignStateProjector → z_sov
  3. Run ExpertRouter(domain=detect(sample)) → expert activations
  4. Run GovernanceService.authorize() → risk, action mode
  5. Run signal adapters:
     - sovereign_health_adapter → risk level
     - insight_adapter → evidence requirement
     - output_modulation_adapter → tone weights
     - readiness_adapter → action mode
     - entropy_adapter → confidence gate
  6. Package as teacher labels:
     d* = domain_from_gyroscope_or_metadata
     r* = risk_from_sovereign_health
     e* = evidence_from_insight
     t* = tone_from_dha
     a* = action_from_readiness
```

**Output schema per training sample:**
```json
{
  "text": "...",
  "teacher_labels": {
    "domain": [0.0, 0.8, 0.0, 0.2, ...],
    "risk": [0.1, 0.7, 0.2],
    "evidence": [0.0, 0.3, 0.7],
    "tone": [0.6, 0.3, 0.0, 0.1],
    "action": [0.8, 0.1, 0.1, 0.0],
    "teacher_temperature": 0.55,
    "teacher_abstain_threshold": 0.82
  }
}
```

**Important:** Teacher labels are soft distributions, not hard labels.
This allows the model to learn domain blends (e.g., a medical-legal
document gets d = [0, 0, 0, 0, 0, 0, 0, 0.5, 0.4, 0.1, 0, 0]).

### 5.4 Training Curriculum Integration

Domain conditioning trains alongside the existing CG curriculum:

| CG Stage | Steps (5K run) | Existing CG Losses | Domain Losses Added |
|----------|----------------|--------------------|--------------------|
| A (backbone) | 0-200 | λ_ont=0.01 | λ_dom=0.01 (domain classification only, other losses off) |
| B (ontology) | 200-500 | L_ont ramps, JEPA/CSR start | λ_dom ramps to target |
| C (primitives) | 500-2750 | kosha/bliss/vritti/guna activate | λ_route, λ_policy activate |
| D (integrated) | 2750-5000 | field softmax | λ_cal activates for safety domains |

**Rationale:** Domain classification (L_dom) starts early because it's
low-risk — it only trains the DomainStateProjector, not the adapters.
Router and policy losses wait until Stage C when the CG primitives
are active and producing meaningful signals.

### 5.5 Gradient Flow

```
L_dom ───────→ DomainStateProjector → SovereignStateProjector (via z_sov input)
L_route ─────→ DomainAdapterRouter
L_policy ────→ DomainSamplingPolicy
L_CG_existing → KoshaDomainRouter → IntegratedTokenScorer → state_projector
                (existing path, gradient-unblock fix already applied)
```

Domain adapters receive gradients from L_tok (the main token loss)
because they modify h_adapted which feeds into logits → L_tok. This
is the primary training signal for adapter specialization.

---

## Section 6 — Inference Modes and Deployment Phases

### 6.1 Inference Modes

Four progressive modes, each adding one capability:

**Mode A — Domain-conditioned generation (minimal)**

Active modules: DomainStateProjector + shared adapter (existing phase
adapter, unchanged).

```
h_base → z_sov → z_dom (logged but not yet acting on adapters)
h_adapted = h_base + gate * phase_adapter(intent_phase)  # existing path
logits = LM_head(h_adapted)
token = sample(logits, T=0.7, p=0.9)  # fixed sampling params
```

**Value:** Domain state is computed and logged. No generation behavior
changes. Establishes baseline metrics for domain classification accuracy.

**Mode B — Domain adapters + sampling control**

Active modules: DomainStateProjector + DomainAdapterRouter + Domain
Adapters + DomainSamplingPolicy.

```
h_adapted = h_base + gate_shared * A_shared
                   + Σ_i α_i * gate_dom * A_i(h_base, z_dom)
logits = LM_head(h_adapted)
T_eff, p_top = sampling_policy(z_dom)
token = sample(logits, T=T_eff, p=p_top)
```

**Value:** Domain-specific hidden-state modulation and sampling. Adapters
specialize output distribution; sampling policy adjusts risk tolerance.

**Mode C — Domain adapters + shortlist reranking**

Active modules: All of Mode B + DomainShortlistReranker (wiring existing
IntegratedTokenScorer + FieldIntegratedSoftmax).

```
logits = LM_head(h_adapted)
top_K = logits.topk(64)
Z_star = integrated_scorer(T, h_base, z_sov, z_dom.d, top_K)
final = (1-λ) * logits[top_K] + λ * Z_star
token = sample(final, T=T_eff, p=p_top)
```

**Value:** Domain-specific token-level scoring. CG primitives (CSR,
Vritti, Guna, Ontological) directly influence which tokens are selected,
weighted by Kosha routing and gated by Bliss coherence.

**Mode D — Domain-native generation (future)**

Full replacement of softmax with field-integrated scoring. Out of scope
for this spec. Requires ablation evidence from Mode C showing reranking
improves generation quality.

### 6.2 Deployment Phases

| Phase | What Ships | Prerequisite | Estimated Effort |
|-------|-----------|-------------|-----------------|
| **Phase 1** | DomainStateProjector only. Train z_dom to predict domain labels. Log domain state. No generation changes. | Teacher labeling pipeline exists. | 1-2 weeks |
| **Phase 2** | Domain adapters + router. Train with L_tok + L_dom + L_route. Inference Mode B. | Phase 1 domain classification accuracy > 80%. | 2-3 weeks |
| **Phase 3** | DomainSamplingPolicy. Add L_policy. Wire teacher distillation from agentic framework. | Phase 2 adapters show measurable PPL improvement in at least 2 domains. | 1-2 weeks |
| **Phase 4** | Shortlist reranker. Wire existing TwoStageGenerator into inference. Inference Mode C. | Phase 3 sampling policy produces domain-appropriate behavior (validated by human eval). | 2-3 weeks |
| **Phase 5** | Calibration loss for safety domains. Add L_cal. | Phase 4 reranking stable. Safety domain test suite exists. | 1-2 weeks |

### 6.3 Ablation Plan

**Required ablations at each phase gate:**

| # | Configuration | Measures |
|---|--------------|---------|
| 1 | Base Mistral only (no CG) | PPL, accuracy (baseline) |
| 2 | Base + existing phase adapter (current system) | PPL delta, generation quality |
| 3 | Base + phase adapter + DomainStateProjector (Mode A) | Domain classification accuracy, PPL (should be neutral) |
| 4 | Base + phase adapter + domain adapters (Mode B) | Per-domain PPL, generation quality per domain |
| 5 | Mode B + DomainSamplingPolicy | Calibration error, abstention precision/recall |
| 6 | Mode B + shortlist reranker (Mode C) | Per-domain PPL, token-level domain adherence |
| 7 | Full system (Mode C + sampling + calibration) | All metrics |

**Metrics per ablation:**

| Metric | What It Measures | Target |
|--------|-----------------|--------|
| Perplexity (overall) | LM quality preservation | < 5% regression from baseline |
| Perplexity (per-domain) | Domain-specific improvement | Lower PPL in domain-specific eval sets |
| Domain classification accuracy | z_dom quality | > 80% top-1 accuracy |
| Calibration error (ECE) | Confidence reliability | < 0.10 for safety domains |
| Abstention precision/recall | Knows when to say "I don't know" | Precision > 0.8, Recall > 0.6 |
| Retrieval trigger F1 | Knows when to look things up | F1 > 0.7 |
| Style/tone adherence | Matches domain expectations | Human eval (A/B test) |
| Code syntax validity | Code domain correctness | > 95% parseable |
| Hallucination rate | Factual domain reliability | < baseline (measured by fact-check) |
| Router entropy | Routing diversity | > 1.0 (not collapsed) |
| Adapter contribution norm | Domain adapters contribute | > 0.01 mean norm |

### 6.4 Observability

Every new module logs at the existing CG diagnostic cadence:

**Per-step (every `log_every` steps):**
- `dom_d_entropy` — domain distribution entropy (collapsed = bad)
- `dom_top1` — top domain ID
- `dom_router_entropy` — adapter routing entropy
- `dom_adapter_norm` — mean adapter output norm
- `dom_rerank_λ` — reranker interpolation weight

**Per-snapshot (every `cg_sample_every` steps):**
- Full z_dom breakdown: d, r, e, t, a distributions
- Per-domain adapter activation counts
- Reranker: how many tokens in top-K changed ranking
- Sampling policy: T_eff, p_top, τ_abstain values

**TensorBoard scalars:**
- `domain/classification_loss`
- `domain/router_balance_loss`
- `domain/policy_distillation_loss`
- `domain/calibration_loss`
- `domain/top1_accuracy` (when teacher labels available)
- `domain/adapter_contribution_norm`
- `domain/rerank_agreement` (fraction of tokens where reranker agrees with base)

---

## Section 7 — Parameter Budget Summary

| Module | Parameters | When Active |
|--------|-----------|-------------|
| SovereignStateProjector (existing) | ~200K | Always |
| Phase adapter + intent projector (existing) | ~4.3M | Always |
| **DomainStateProjector** | ~530K | Phase 1+ |
| **DomainAdapterRouter** | ~800 | Phase 2+ |
| **DomainAdapters (13 × bottleneck-64)** | ~6.9M | Phase 2+ |
| **DomainSamplingPolicy** | ~135 | Phase 3+ |
| **Reranker gate** | ~10 | Phase 4+ |
| CG primitive scorers (existing) | ~12.8M | Phase 4+ (inference) |
| **Total new parameters** | **~7.4M** | |
| **Total system (new + existing trainable)** | **~25M** | vs 7B frozen backbone |

The new domain conditioning adds ~7.4M parameters on top of the existing
~17.6M CG parameters. All parameters are small relative to the 7B frozen
backbone.

---

## Section 8 — What This Architecture Gives You

1. **Explicit domain awareness** — z_dom makes domain state visible,
   measurable, and actionable at every token step.

2. **Inference-time control** — Domain adapters, sampling policy, and
   shortlist reranking all operate at inference without retraining.

3. **Domain capture during training** — Teacher signals from the agentic
   GovernanceService flow into training as supervised labels, bridging the
   gap between the governance framework and the LLM.

4. **Clean integration** — Extends rather than replaces the existing CG
   architecture. All existing modules (state projector, phase adapter,
   kosha router, primitive scorers) continue unchanged.

5. **Measurable ablations** — Every component can be toggled independently.
   The ablation plan provides clear evidence gates for each phase.

6. **Future path** — Mode D (domain-native generation) is architecturally
   prepared. The shortlist reranker in Mode C is a subset of the full
   FieldIntegratedSoftmax replacement. If Mode C shows significant quality
   improvement, Mode D is a natural extension.

**Bottom line:** Capture agentic domain logic during training as supervised
policy/state targets, then use that learned domain state at inference for
adapter routing, sampling control, and shortlist reranking. This is the
most stable bridge between the agentic framework and mistral_cg.
