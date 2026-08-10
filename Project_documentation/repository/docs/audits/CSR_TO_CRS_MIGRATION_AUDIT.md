# CSR → CRS Migration Audit (Phase 1)

**Date:** 2026-04-08
**Scope:** Mistral_CG training stack — audit only, no code changes
**Branch:** `claude/audit-mistral-cg-csr-crs-R2SHq`

---

## A. Executive Summary

The current Mistral_CG training stack implements a **fused phonemic/mental resonance scorer** called `CSRTokenScorer`. This scorer computes a single bilinear score `S_csr(w) = r_t^T M_csr r_w` from 12D phoneme affinity vectors. It is one of six primitives in the `TokenEvaluationTensor`, combined via Kosha-weighted routing (`α`) and Bliss coherence gating (`B`).

**The system is structurally CSR, not merely misnamed.** (Verdict: **Option Y**.)

The intended CRS doctrine requires three explicitly separated scoring branches — Cognitive (C), Resonance (R), Semantic (S) — with a non-negotiable semantic firewall ensuring that high resonance cannot override low semantic correctness. The current codebase has:

- **No separate `C` branch.** Cognitive/Kosha scoring is partially present via Vritti and Kosha routing, but not as an independent token-level compatibility score.
- **No separate `S` branch.** The base transformer logits (`S_base`) serve as the de facto semantic signal, but there is no explicit semantic compatibility scorer with firewall authority.
- **No semantic firewall.** The combination is a soft-weighted sum `Z(w) = Σ α_f S_f(w)` gated by Bliss disagreement. Nothing prevents high-C, high-R, low-S candidates from scoring well if routing weights favor non-semantic primitives.

The current CSR scorer covers only the `R` (Resonance) leg of CRS. The `C` and `S` legs must be built. The combination function must enforce semantic dominance.

**Recommended migration strategy:** Option 2 — Parallel migration. Build CRS as a new combined scorer alongside existing CSR, validate, then switch primitive registration.

---

## B. CSR Inventory Table

Classifications:
- **A** = Retainable backend (phoneme/varna utilities still useful under CRS)
- **B** = Must-change scorer logic (implements fused CSR scoring, must be replaced)
- **C** = Must-change cache schema (tensor layouts insufficient for CRS)
- **D** = Naming/docs/logging only (cosmetic)
- **E** = Inference-only dependency (not phase-1 critical)
- **F** = Dead/legacy (safe to ignore)

### Training-side components

| Component | File | Current Role | Class. | Migration Note |
|-----------|------|-------------|--------|----------------|
| `CSRTokenScorer` | `symbolu_training/.../primitives/csr_scorer.py` | Bilinear scorer: 12D phoneme affinity → `d_c` repr → `S_csr(w) = r_t^T M_csr r_w`. Lines 25-126. | **B** | Becomes the `R` branch of CRS. Context proj and bilinear form are reusable, but must be wrapped, not used as standalone primitive. Token-side input (12D affinity) is pure resonance — retainable as `compute_R` backend. |
| `CSRTokenScorer` import | `symbolu_training/.../primitives/__init__.py:17` | Imports class into primitives package. | **D** | Rename import or add new CRS import alongside. |
| `TokenEvaluationTensor` | `symbolu_training/.../primitives/__init__.py:26-228` | Orchestrates 6 primitives into `T_t ∈ ℝ^{K×6}`. Column 3 = `S_csr`. Hardcoded `PRIMITIVE_NAMES = ["base", "ontology", "jepa", "csr", "vritti", "guna"]`. | **B** | Column layout must change. CRS replaces the single `csr` column with either a single combined CRS score or 3 sub-columns (C, R, S). `NUM_PRIMITIVES` and `PRIMITIVE_NAMES` must update. |
| `TokenPrimitiveCache` | `symbolu_training/.../token_cache.py:28-276` | Caches `R_tok (V, d_c)` for CSR. `set_scorers()` accepts `csr_scorer`. `refresh()` calls `csr_scorer.compute_token_repr(csr_affinity)`. | **C** | `R_tok` survives as the resonance cache. New buffers needed: `C_tok` (cognitive cache) and `S_tok` (semantic cache). `set_scorers()` signature must expand. |
| `csr_scorer` in `model_factory.py` | `symbolu_training/.../unified/model_factory.py:665-668, 687, 696, 707, 720` | Instantiates `CSRTokenScorer`, passes to `TokenEvaluationTensor`, registers in `conscious_gen` ModuleDict, registers with cache. | **B** | Must instantiate CRS combined scorer instead (or alongside). ModuleDict key `"csr_scorer"` must change. |
| `csr_token_dim` config | `symbolu_training/.../unified/config.py:1010` | Dimension `d_c` for CSR token representations (default 16). | **D** | Rename or keep as `resonance_dim`. Add `cognitive_dim`, `semantic_dim`. |
| `lambda_csr_token` config | `symbolu_training/.../unified/config.py:1021` | Loss weight for CSR token-level resonance loss. | **D** | Rename to `lambda_crs_token` or split into `lambda_C`, `lambda_R`, `lambda_S`. |
| `PrimitiveAuxiliaryLosses` | `symbolu_training/.../losses/primitive_auxiliary.py:43-48` | Hardcoded `DEFAULT_INDICES = {"jepa": 2, "csr": 3, "vritti": 4, "guna": 5}`. Column 3 = CSR. | **B** | Column index for CSR must change to match new `T` layout. May need separate C/R/S losses. |
| `KoshaDomainRouter` | `symbolu_training/.../governance/kosha_router.py:31` | `PRIMITIVE_NAMES = ["base", "ontology", "jepa", "csr", "vritti", "guna"]`. Routes over 6 primitives. MENTAL Kosha [14] → CSR. | **B** | Must route over new primitive set. MENTAL Kosha mapping may split to map C and R differently. |
| `BlissTokenGate` | `symbolu_training/.../governance/bliss_gate.py` | Computes disagreement `D(w)` across 6-column `T`. | **B** | Shape depends on `T` column count. If CRS replaces the `csr` column, shape changes. Disagreement semantics may also change (semantic firewall may override Bliss). |
| `IntegratedTokenScorer` | `symbolu_training/.../integration/token_scorer.py` | Combines router α and Bliss gate into `Z*(w)`. | **B** | Downstream of `T` shape. Also: CRS semantic firewall may need to intervene *before* or *instead of* the soft weighted sum. |
| `FieldIntegratedSoftmax` | `symbolu_training/.../integration/field_softmax.py` | Converts `Z*(w)` to log-probs. Agreement energy iterates over primitive pairs. | **B** | Pair count changes if primitive count changes. Agreement energy β matrix size = `P*(P-1)/2`. |
| `TwoStageGenerator` | `symbolu_training/.../integration/two_stage_generator.py` | Orchestrates TET → IntegratedScorer → FieldSoftmax. Training-only. | **D** | Pass-through; changes propagate from inner modules. |
| `KoshaRoutingLoss` | `symbolu_training/.../losses/kosha_routing.py` | Supervises routing weights over 6 primitives. | **B** | Must handle new primitive count/names. Agreement targets index into `T` columns. |
| `BlissCoherenceLoss` | `symbolu_training/.../losses/bliss_coherence.py` | Trains Bliss gate on correct/incorrect token disagreement. | **D** | No direct CSR reference. Only shape-dependent via `T`. |
| Train loop CSR wiring | `symbolu_training/.../unified/train.py:5669, 5157, 2433, 4969, 5282, 10086` | References `csr_scorer` for grad norms, `lambda_csr_token` for loss weighting, `csr_token_dim` CLI arg. | **D** | String/name changes. Loss weight key rename. |
| `use_csr_annotation` config | `symbolu_training/.../unified/config.py:120` | Binding Annotator flag — CSR affects binding salience. | **D** | Rename to `use_resonance_annotation` or `use_crs_annotation`. |
| `enable_csr` flag | `symbolu_core/phase_transformer.py:503` | Future-ready flag, `Optional[bool] = None`. No behavior attached. | **F** | Dead flag. Safe to repurpose or remove. |
| Adaptive diagnostics | `symbolu_training/.../diagnostics/adaptive_diagnostic_controller.py:43` | Tracks `R_tok` cache drift metric. | **D** | Metric name change. May add `C_tok`, `S_tok` drift. |

### Phoneme/Varna provider layer

| Component | File | Current Role | Class. | Migration Note |
|-----------|------|-------------|--------|----------------|
| `CSREmbeddingProvider` | `csr_phoneme_provider.py` (root, ~3000 lines) | Full phoneme pipeline: Token → G2P → ARPABET → Varna → 12D affinity → projection → hidden-state injection. | **A** | Core resonance feature builder. Survives as the `R` branch's feature source. The 12D affinity vectors feed `CSRTokenScorer.compute_token_repr()`. |
| `VarnaCSRBridge` | `csr_phoneme_provider.py` | ARPABET → Varna → 12D ontological vector lookup. | **A** | Pure phoneme/varna utility. Fully retainable. |
| `EntropySink` | `csr_phoneme_provider.py` | Layer-0 dormancy anchoring via entropy absorption. | **A** | Orthogonal to scoring. Retainable as-is. |
| `SynthesisGate` | `csr_phoneme_provider.py` | Layer-11 structure-flow synthesis gating. | **A** | Orthogonal to scoring. Retainable as-is. |
| `create_csr_phoneme_head()` | `csr_phoneme_provider.py:2580` | Factory for `CSRPhonemeHead` (learnable d_model phoneme embeddings). | **A** | Retainable. Name is cosmetic. |
| `CSRConfig`, `CSRPhonemeHeadConfig` | `csr_phoneme_provider.py` | Config dataclasses for CSR provider. | **D** | Rename or alias. |

### Inference-side components

| Component | File | Current Role | Class. | Migration Note |
|-----------|------|-------------|--------|----------------|
| `CSRInferenceGuard` | `symbolu/inference/csr_inference.py` | Entropy monitoring + synthesis gating during inference. No token-level CRS scoring. | **E** | Inference-only. Not phase-1 critical. Does not implement CSR *scoring* — only entropy safety. |
| `CSRInferenceGuard` (agentic copy) | `agentic/inference/csr_inference.py` | Mirror of above in agentic package. | **E** | Same as above. |
| `GenerationTracer._compute_csr()` | `symbolu/inference/generation_tracer.py:69-74` | Calls `csr_scorer.score_token()` for per-token tracing. | **E** | Must update method name and scorer interface when CRS lands at inference. |
| `GenerationTracer._compute_csr()` (agentic copy) | `agentic/inference/generation_tracer.py:69-74` | Mirror of above. | **E** | Same. |

### Tests, scripts, and benchmarks

| Component | File | Current Role | Class. | Migration Note |
|-----------|------|-------------|--------|----------------|
| `test_cg_phases.py` | `scripts/test_cg_phases.py:42, 85, 163, 326` | Structural validation — checks `csr_scorer` exists in `conscious_gen`, uses `lambda_csr_token=0.01`, `csr_token_dim=8`. | **D** | Update names/keys after migration. |
| `csr_bridge.py` | `scripts/phase_probes/.../csr_bridge.py` | Benchmarks full CSR pipeline (G2P → Varna → 12D → injection). Tests phoneme decomposition, VarnaCSRBridge, EntropySink, SynthesisGate. | **A** | Tests the resonance *feature* pipeline, not the scoring doctrine. Fully retainable. |
| `test_sovereign_handshake.py` | `test_sovereign_handshake.py` | Integration test importing `CSREmbeddingProvider` from `csr_phoneme_provider`. | **A/D** | Import names cosmetic. Test logic tests phoneme injection, not scoring. |
| `test_sanskrit_g2p.py` | `tests/test_sanskrit_g2p.py:31` | Tests G2P from `csr_phoneme_provider`. | **A** | Phoneme utility test. Retainable. |
| `test_varna_mapping.py` | `tests/test_varna_mapping.py:32` | Tests varna mapping from `csr_phoneme_provider`. | **A** | Retainable. |
| `test_phoneme_bcvf_signal.py` | `tests/test_phoneme_bcvf_signal.py:43` | Tests phoneme BCVF signal from `csr_phoneme_provider`. | **A** | Retainable. |
| `evaluate_phoneme_mapping.py` | `scripts/evaluate_phoneme_mapping.py:67` | Evaluates phoneme mapping quality. | **A** | Retainable. |
| `validate_phoneme_bcvf.py` | `scripts/validate_phoneme_bcvf.py:71` | Validates phoneme BCVF signal. | **A** | Retainable. |

### Documentation

| Component | File | Current Role | Class. | Migration Note |
|-----------|------|-------------|--------|----------------|
| `CONSCIOUS_GENERATION_DESIGN.md` | `docs/design/CONSCIOUS_GENERATION_DESIGN.md` | Master design doc. References `S_csr`, `R_tok`, `M_csr`, `CSRTokenScorer` extensively (50+ references). | **D** | Must update to CRS terminology after migration. |
| `CG_MISTRAL_SIGNAL_AUDIT.md` | `docs/audits/CG_MISTRAL_SIGNAL_AUDIT.md` | Signal audit referencing `csr_scorer`, `S_csr`. | **D** | Update references. |
| `CSR_GUNA_INFERENCE_DESIGN_SPEC.md` | `docs/specs/CSR_GUNA_INFERENCE_DESIGN_SPEC.md` | Inference design spec for CSR + Guna. | **D/E** | Update terminology. Inference-side. |
| `TRAINING_DIAGNOSIS_FIX_v9.9.0.md` | Root | References CSR engagement/disengagement thresholds. | **D** | Historical doc. Low priority. |

---

## C. Structural Verdict

**Option Y: The implementation is genuinely CSR in architecture. Migrating to CRS requires structural changes.**

### Evidence

**1. The current `CSRTokenScorer` is a single fused primitive, not a separated doctrine.**

At `csr_scorer.py:104-125`, the forward pass is:

```python
def forward(self, r_ctx, R_tok):
    if self.use_low_rank:
        intermediate = r_ctx @ self.B
        m_r = intermediate @ self.A.t()
    else:
        m_r = r_ctx @ self.M.t()
    return m_r @ R_tok.t()
```

This produces one scalar score per candidate token. There is no internal decomposition into C, R, or S sub-scores. The bilinear form `r_t^T M_csr r_w` mixes whatever signal the network learns into `r_ctx` and `R_tok` — there is no constraint that forces these to separate cognitive, resonance, and semantic concerns.

**2. The input features are purely phonemic/resonance.**

`CSRTokenScorer.compute_token_repr()` at line 76 takes `csr_affinity: (V, 12)` — 12D phoneme affinity vectors from the ARPABET → Varna pipeline. This is a resonance signal only. There is no cognitive state input and no semantic feature input to this scorer.

The context-side projection (`compute_context_repr` at line 88) takes `[h_t; o_t]` (hidden state + ontological code), which *could* carry semantic and cognitive information, but it is projected through a single MLP to a single `d_c`-dimensional vector. There is no branching into C/R/S sub-projections.

**3. The combination layer has no semantic firewall.**

The `IntegratedTokenScorer` at `integration/token_scorer.py:89` computes:

```python
Z_star = B * Z  # Z = Σ α_f S_f(w)
```

All six primitives (base, ontology, JEPA, CSR, Vritti, Guna) are weighted by learned Kosha routing weights `α` and gated by Bliss disagreement `B`. There is no mechanism that says "if semantics are low, suppress the candidate regardless of resonance or cognitive scores." The Bliss gate penalizes *disagreement*, not semantic failure — a candidate with uniformly high scores across all primitives (including high resonance but low semantic correctness) would get *high* Bliss and pass through.

**4. The closest analogs to C and S exist but are not wired as CRS branches.**

- `VrittiTokenScorer` (cognitive mode compatibility) is conceptually close to `C`, but it operates as a *separate* primitive in column 4 of `T`, not as part of a CRS combined score.
- `S_base` (transformer logits) carries semantic signal, but it occupies column 0 and has no special authority.
- `OntologyCompatibilityScorer` overlaps with cognitive/semantic concerns but is also just another equal primitive.

None of these are combined into a `C+R+S` doctrine with semantic dominance.

**5. This is not a naming problem.**

A rename from "CSR" to "CRS" would not fix the architecture. The current code would still produce a fused single-primitive score with no semantic firewall. The migration requires:
- Splitting the CSR scorer into separate C, R, S computation branches
- Adding a semantic compatibility scorer that does not currently exist
- Adding a governed combination function with semantic dominance
- Changing the token evaluation tensor column layout
- Adding branch-level diagnostics

---

## D. CRS Gap Analysis

| CRS Requirement | Status | Evidence |
|-----------------|--------|----------|
| **Separate C, R, S computation branches** | **Missing** | No function signatures `compute_C()`, `compute_R()`, `compute_S()` exist. The six primitives (base, ontology, JEPA, CSR, Vritti, Guna) are conceptually overlapping with C/R/S but are not organized as a C+R+S doctrine. CSR is fused; C and S are not isolated. |
| **Cognitive / mental-state / Kosha scoring path for C** | **Partial** | `VrittiTokenScorer` (`vritti_scorer.py:27-111`) computes cognitive mode compatibility via 5-class dot product `S_vritti(w) = q_t^T q_w`. This captures FACT/ERROR/IMAGINATION/VOID/MEMORY cognitive modes. `KoshaDomainRouter` (`kosha_router.py:43-241`) extracts Kosha [12:17] for routing. Both carry cognitive signal, but neither is packaged as a standalone `compute_C()` branch with its own scalar output feeding into CRS. The Vritti scorer is a separate primitive (column 4), not a sub-component of a combined CRS score. |
| **Resonance / dual-polarity / consonant alignment path for R** | **Partial** | `CSRTokenScorer` (`csr_scorer.py:25-126`) computes phonemic resonance via 12D affinity → bilinear score. This IS the `R` computation. However, it does not separately expose dual-polarity or consonant alignment sub-signals — it fuses them into a single `S_csr` scalar. The upstream `VarnaCSRBridge` and `CSREmbeddingProvider` in `csr_phoneme_provider.py` DO carry dual-polarity and consonant vritti information in the 12D vector, but this structure is collapsed by the scorer's MLP projection. **The feature source is present; the scorer flattens it.** |
| **Semantic / reference correctness scorer for S** | **Missing** | `S_base` (column 0 in `T`) is the transformer's raw logit — this is the closest thing to a semantic signal. But it is not an explicit semantic *compatibility* scorer. It has no dedicated projection, no semantic feature extraction, and no special authority. `OntologyCompatibilityScorer` (`ontology_scorer.py`) computes `S_ont(w) = o_t^T M_ont o_w` which captures ontological identity alignment, which is partially semantic — but it operates on the 32D sovereign state, not on token-level semantic features. There is no scorer whose explicit contract is "does this token make semantic sense in this context?" |
| **Semantic firewall / semantic dominance rule** | **Missing** | The combination function is `Z(w) = Σ α_f S_f(w)` (soft weighted sum) gated by `B(w) = exp(-λ D(w))` (disagreement penalty). This is governance-by-consensus, not governance-by-semantic-authority. A candidate with C=0.8, R=0.9, S=0.2 could score well if Kosha routing assigns high weight to resonance primitives and low weight to base/semantic. The Bliss gate only penalizes *disagreement* — if the semantic primitive gives a low score but routing barely weights it, disagreement is low and the candidate passes. **There is no hard or soft floor on semantic score.** |
| **Branch-level diagnostics (C_mean, R_mean, S_mean)** | **Missing** | Current diagnostics track per-primitive means via `KoshaDomainRouter.get_diagnostics()` (alpha means per primitive) and `TokenPrimitiveCache.get_diagnostics()` (cache norms for R_tok, P_tok, etc.). But there are no logged metrics named `C_mean`, `R_mean`, `S_mean` that correspond to the CRS branches. The `PrimitiveAuxiliaryLosses` tracks `L_csr`, `L_jepa`, `L_vritti`, `L_guna` — these are per-primitive, not per-CRS-branch. |
| **Clean final combination function (not fused primitive)** | **Missing** | `IntegratedTokenScorer.forward()` at `integration/token_scorer.py:42-106` produces `Z_star = B * Z` where `Z = Σ α_f S_f(w)`. This is a clean combination function, but it combines 6 *equal* primitives, not 3 CRS branches with semantic dominance. There is no `combine_crs(C, R, S, mode="soft_gated")` function. |
| **Training tensor integration path for CRS as active primitive** | **Missing** | The `TokenEvaluationTensor` produces `T ∈ ℝ^{K×6}` with column order `[S_base, S_ont, S_plausibility, S_csr, S_vritti, S_guna]`. CRS is not a registered primitive. The CSR scorer occupies one column (index 3) of the 6-column tensor. To make CRS the active primitive, either: (a) CRS replaces the CSR column with a combined score, or (b) CRS produces 3 columns replacing/augmenting the current layout, or (c) CRS wraps the entire TET as a meta-scorer. |

### Summary

| Requirement | Verdict |
|-------------|---------|
| Separate C, R, S branches | **Missing** |
| Cognitive scoring path (C) | **Partial** — Vritti + Kosha exist but not as CRS sub-branch |
| Resonance scoring path (R) | **Partial** — CSRTokenScorer exists but is fused, not R-only |
| Semantic scoring path (S) | **Missing** — no dedicated semantic compatibility scorer |
| Semantic firewall | **Missing** |
| Branch-level diagnostics | **Missing** |
| Clean combination function | **Missing** — current combiner is 6-primitive weighted sum |
| CRS as active training primitive | **Missing** |

---

## E. Recommended Migration Strategy

**Recommendation: Option 2 — Parallel migration.**

### Why not Option 1 (in-place rename and refactor)?

In-place refactoring of `csr_scorer.py` into a 3-branch CRS scorer would:
- Break any existing checkpoint that references `csr_scorer.*` parameter names
- Make it impossible to A/B test old CSR vs new CRS behavior
- Force all downstream consumers (TET, cache, losses, router) to change simultaneously — a big-bang migration with high risk of silent training regression
- Lose the ability to roll back to working CSR if CRS has training issues

### Why not Option 3 (meta-wrapper)?

Wrapping CSR as a sub-primitive inside CRS is architecturally misleading. CSR computes `r_t^T M_csr r_w` — this is the `R` branch, not the entire CRS. Making CRS a wrapper around CSR implies CSR is a self-contained sub-unit, when in fact:
- The `C` branch needs to source from Vritti/Kosha features that CSR does not touch
- The `S` branch needs semantic features that CSR does not compute
- The combination function needs semantic firewall logic that CSR's bilinear form cannot provide

A wrapper would end up being a new scorer that *contains* CSR but doesn't actually delegate to it meaningfully — just a misleading abstraction.

### Why Option 2 (parallel migration)?

1. **Checkpoint safety:** Existing checkpoints with `conscious_gen.csr_scorer.*` keys continue to load. The new CRS scorer gets new parameter names. No key collisions.

2. **A/B testability:** A config flag (`use_crs_combined_scorer: bool = False`) can toggle between old CSR (column 3 in 6-column T) and new CRS (replacing one or more columns). Training runs can compare loss curves, perplexity, and per-branch diagnostics.

3. **Incremental rollout:** CRS can be built and validated in stages:
   - Stage 2a: Add `CRSCombinedScorer` as a new module in `primitives/`
   - Stage 2b: Add `C_tok`, `S_tok` buffers to `TokenPrimitiveCache`
   - Stage 2c: Wire CRS into `TokenEvaluationTensor` behind a flag
   - Stage 2d: Add semantic firewall to `IntegratedTokenScorer` or `combine_crs()`
   - Stage 2e: Validate training stability, then deprecate standalone CSR

4. **Lowest implementation risk:** Each stage can be tested independently. If CRS shows training instability, the flag flips back to CSR with zero code rollback needed.

5. **Clarity of architecture:** CRS is a *new* scoring doctrine, not a refactored version of CSR. Giving it its own module makes the intent clear: CRS *uses* the resonance features that CSR computes, but adds cognitive and semantic branches plus a governed combination.

### Concrete migration order

1. Create `primitives/crs_combined_scorer.py` with `compute_C()`, `compute_R()`, `compute_S()`, `combine_crs()`
2. Add `C_tok`, `S_tok` cache buffers to `TokenPrimitiveCache`
3. Add `CRSCombinedScorer` to `model_factory.py` behind `use_crs_combined_scorer` flag
4. Extend `TokenEvaluationTensor` to handle CRS column layout (flag-gated)
5. Add semantic firewall to combination function
6. Add `C_mean`, `R_mean`, `S_mean` diagnostics
7. Validate: compare training loss/PPL/primitive diagnostics between CSR and CRS
8. Promote CRS to default, deprecate CSR standalone path
9. Update docs, configs, test names

---

## F. Target CRS Interface

### Core scorer API

```python
class CRSCombinedScorer(nn.Module):
    """
    Combined Cognitive-Resonance-Semantic scorer with semantic firewall.
    
    Produces three separate branch scores and a governed combination.
    Semantic branch has veto authority: high C + high R + low S → suppressed.
    """

    def compute_C(
        self,
        hidden: torch.Tensor,         # (..., embed_dim) — transformer hidden state
        o_ctx: torch.Tensor,           # (..., 32) — context ontological code
        C_tok: torch.Tensor,           # (K, d_c_cog) — cached cognitive token reprs
        vritti_ctx: torch.Tensor,      # (..., 5) — context Vritti profile
        kosha_ctx: torch.Tensor,       # (..., 5) — context Kosha distribution
    ) -> torch.Tensor:
        """
        Cognitive compatibility: does this token fit the current mental-state /
        Kosha context? Sources from Vritti mode and Kosha sheath signals.
        
        Returns: (..., K) cognitive compatibility scores
        """
        ...

    def compute_R(
        self,
        hidden: torch.Tensor,         # (..., embed_dim)
        o_ctx: torch.Tensor,           # (..., 32)
        R_tok: torch.Tensor,           # (K, d_c) — cached resonance token reprs (from 12D phoneme affinity)
    ) -> torch.Tensor:
        """
        Resonance compatibility: does this token's phonemic/varna structure
        align with the current consonant resonance and dual-polarity vritti?
        
        This is the existing CSRTokenScorer bilinear form, isolated as R-only.
        
        Returns: (..., K) resonance scores
        """
        ...

    def compute_S(
        self,
        hidden: torch.Tensor,         # (..., embed_dim)
        o_ctx: torch.Tensor,           # (..., 32)
        S_tok: torch.Tensor,           # (K, d_s) — cached semantic token reprs
        base_logits: torch.Tensor,     # (..., K) — base transformer logits for candidates
    ) -> torch.Tensor:
        """
        Semantic compatibility: does this token make referential/contextual sense?
        Combines base logit signal with a learned semantic projection.
        
        Returns: (..., K) semantic correctness scores
        """
        ...

    def combine_crs(
        self,
        C: torch.Tensor,              # (..., K)
        R: torch.Tensor,              # (..., K)
        S: torch.Tensor,              # (..., K)
        mode: str = "soft_gated",
    ) -> torch.Tensor:
        """
        Governed combination with semantic dominance.
        
        mode="soft_gated":
            S_gate = sigmoid(k_s * (S - s_threshold))   # semantic gate ∈ [0, 1]
            CRS(w) = S_gate * (w_c * C + w_r * R + w_s * S)
            
            When S < s_threshold, S_gate → 0, suppressing the candidate
            regardless of C and R values.
        
        mode="hard_floor":
            If S < s_min: CRS(w) = -inf (hard rejection)
            Else: CRS(w) = w_c * C + w_r * R + w_s * S
        
        Returns: (..., K) combined CRS scores with semantic authority enforced
        """
        ...

    def forward(
        self,
        hidden: torch.Tensor,
        o_ctx: torch.Tensor,
        cache: TokenPrimitiveCache,
        candidate_ids: torch.Tensor,
        base_logits: torch.Tensor,
        vritti_ctx: torch.Tensor,
        kosha_ctx: torch.Tensor,
        mode: str = "soft_gated",
    ) -> Dict[str, torch.Tensor]:
        """
        Full CRS forward pass.
        
        Returns:
            'crs_score': Combined CRS score (..., K)
            'C': Cognitive branch score (..., K)
            'R': Resonance branch score (..., K)
            'S': Semantic branch score (..., K)
            'S_gate': Semantic gate values (..., K)
        """
        ...
```

### Token-side cached features

| Buffer | Shape | Source | Survives from CSR? |
|--------|-------|--------|--------------------|
| `R_tok` | `(V, d_c)` | `CSRTokenScorer.compute_token_repr(csr_affinity)` — 12D phoneme affinity → learned projection | **Yes, unchanged.** This is the resonance cache. |
| `C_tok` | `(V, d_c_cog)` | **New.** Cognitive token representations. Derived from `[e_w; vritti_profile_w; kosha_hint_w]`. Captures each token's cognitive mode propensity. Dimension `d_c_cog` ~ 8-16. | **New buffer** |
| `S_tok` | `(V, d_s)` | **New.** Semantic token representations. Derived from `[e_w; o_w]` via a semantic-specific projection (distinct from ontology scorer's codes). Captures referential/contextual token semantics. Dimension `d_s` ~ 16-32. | **New buffer** |
| `O_tok` | `(V, 32)` | Unchanged — ontological codes | Unchanged |
| `P_tok` | `(V, d_j)` | Unchanged — plausibility representations | Unchanged |
| `V_tok` | `(V, 5)` | Unchanged — Vritti cognitive mode profiles | Unchanged |
| `G_tok` | `(V, 3)` | Unchanged — Guna energetic profiles | Unchanged |

**Memory impact:** At V=50,257, fp16: adding `C_tok (V, 16)` and `S_tok (V, 32)` adds ~50,257 × 48 × 2 ≈ 4.8 MB. Total cache grows from ~7.2 MB to ~12.0 MB. Acceptable.

### What happens to `R_tok`

`R_tok` **survives unchanged**. It stores the resonance representations derived from 12D phoneme affinity vectors. Under CRS, it feeds `compute_R()` exactly as it feeds the current `CSRTokenScorer.forward()`. The tensor shape `(V, d_c)` with `d_c=16` does not change.

### Training diagnostics to log

| Metric | Description |
|--------|-------------|
| `C_mean` | Mean cognitive compatibility score across batch |
| `R_mean` | Mean resonance score across batch |
| `S_mean` | Mean semantic correctness score across batch |
| `S_gate_mean` | Mean semantic gate activation (how often S is above threshold) |
| `S_gate_reject_rate` | Fraction of candidates where `S_gate < 0.1` (effectively suppressed) |
| `CRS_combined_mean` | Mean combined CRS score |
| `C_R_S_correlation` | Pairwise Pearson correlation between C, R, S branches (should be low — branches should be decorrelated) |
| `semantic_override_rate` | Fraction of positions where the top-CRS token differs from top-R token due to semantic gating |
| `L_C`, `L_R`, `L_S` | Per-branch contrastive auxiliary losses |

---

## G. Highest-Risk Breakpoints

- **Token Evaluation Tensor column layout (`primitives/__init__.py:50, 176`).** The hardcoded `PRIMITIVE_NAMES = ["base", "ontology", "jepa", "csr", "vritti", "guna"]` and `T = torch.stack([s_base, s_ont, s_jepa, s_csr, s_vritti, s_guna], dim=-1)` define a 6-column contract consumed by every downstream module: `KoshaDomainRouter` (6 routing weights), `BlissTokenGate` (6-column disagreement), `PrimitiveAuxiliaryLosses` (hardcoded column indices `{"csr": 3}`), `KoshaRoutingLoss`, `FieldIntegratedSoftmax` (pair count = 15). If CRS changes the column count or reorders columns, **every consumer silently misinterprets the data** unless all are updated atomically. This is the single highest-risk breakpoint.

- **Primitive auxiliary loss column indices (`losses/primitive_auxiliary.py:43-48`).** `DEFAULT_INDICES = {"jepa": 2, "csr": 3, "vritti": 4, "guna": 5}` is hardcoded. If CRS replaces column 3 with a combined CRS score, the loss computation for that column changes meaning. If CRS adds columns (expanding T from 6 to 8), all indices shift. **Silent training regression** — the loss would train on wrong columns.

- **KoshaDomainRouter routing weight count (`kosha_router.py:30-31`).** `NUM_PRIMITIVES = 6` and `PRIMITIVE_NAMES` are module-level constants. The router's output layer is `nn.Linear(hidden, num_primitives)`. If primitive count changes, the router's parameter shape changes, breaking checkpoint loading.

- **Checkpoint key compatibility.** Existing checkpoints contain keys like `conscious_gen.csr_scorer.A`, `conscious_gen.csr_scorer.B`, `conscious_gen.csr_scorer.token_proj.weight`, etc. If CRS replaces `csr_scorer` in the `conscious_gen` ModuleDict, these keys become orphaned. If `csr_scorer` is renamed, `strict=True` loading fails. **Mitigation:** Option 2 (parallel migration) avoids this entirely by adding CRS as a new key while CSR remains loadable.

- **TokenPrimitiveCache buffer registration (`token_cache.py:69-75`).** Adding `C_tok` and `S_tok` buffers changes the cache's `state_dict()`. Old checkpoints won't have these keys. Loading must handle missing buffers gracefully (initialize to zeros). The `refresh()` method must conditionally populate new buffers only when CRS scorers are registered.

- **Bliss disagreement semantics under semantic firewall.** Currently `D(w) = Σ α_f (S_f(w) - μ(w))^2` treats all primitives equally in disagreement. If CRS introduces a semantic firewall that suppresses candidates *before* Bliss gating, the meaning of "disagreement" changes. A candidate rejected by semantic firewall has `CRS(w) → 0` but the underlying primitive scores in `T` still show the disagreement pattern. If Bliss is computed on raw `T` but the final score uses CRS-gated values, the Bliss loss signal becomes disconnected from the actual selection. **The interaction between semantic firewall and Bliss gate must be designed carefully.**

- **Agreement energy pair count (`field_softmax.py:54`).** `num_pairs = num_primitives * (num_primitives - 1) // 2`. Currently 15 pairs for 6 primitives. If CRS changes primitive count, this changes, breaking checkpoint `beta` parameter shape.

- **`model_factory.py` wiring order (`model_factory.py:665-724`).** The factory instantiates scorers, passes them to TET, registers them in ModuleDict, and registers with cache — all in a specific order with specific keys. The CRS scorer must be wired in parallel without disrupting this sequence. A flag-gated approach is safest.

- **Accidental semantic regression if old CSR logic is retained under CRS name.** If CRS's `compute_R()` simply delegates to the old `CSRTokenScorer` and `compute_C()` / `compute_S()` are initialized to near-zero (as is common with small gain init), CRS would initially behave as `CRS ≈ R` — reproducing old CSR behavior. The semantic firewall would have no learned semantic signal to gate on. This would appear "working" in early training but provide no actual CRS benefit. **Mitigation:** Initialize `compute_S()` to pass through base logits (not learned from scratch), so semantic signal is present from step 0.

- **Loss weighting imbalance.** Currently `lambda_csr_token` controls one auxiliary loss. Under CRS, there are three branch losses (`L_C`, `L_R`, `L_S`) plus the combined CRS loss. If all three branch lambdas start at the same value as the old `lambda_csr_token`, the total auxiliary loss contribution triples, potentially destabilizing training. **Mitigation:** Initial CRS branch lambdas should sum to the old `lambda_csr_token` value.

---

## H. File-by-File Action Plan

### New files to create

| File | Action | Description |
|------|--------|-------------|
| `symbolu_training/.../primitives/crs_combined_scorer.py` | **Add new** | `CRSCombinedScorer` with `compute_C()`, `compute_R()`, `compute_S()`, `combine_crs()`. Semantic firewall logic lives here. |
| `symbolu_training/.../losses/crs_branch_losses.py` | **Add new** | Per-branch contrastive losses `L_C`, `L_R`, `L_S` and semantic firewall supervision. |
| `symbolu_training/.../diagnostics/crs_diagnostics.py` | **Add new** | `C_mean`, `R_mean`, `S_mean`, `S_gate_mean`, correlation metrics. |
| `tests/test_crs_combined_scorer.py` | **Add new** | Unit tests for CRS: branch separation, semantic firewall behavior, combine_crs modes. |

### Existing files to modify

| File | Action | Phase-1 Scope |
|------|--------|---------------|
| `symbolu_training/.../primitives/csr_scorer.py` | **Keep** | No changes in phase 1. Remains as the `R` branch backend. CRS's `compute_R()` will delegate to it or clone its logic. |
| `symbolu_training/.../primitives/__init__.py` | **Modify** | Add `CRSCombinedScorer` import. Behind flag: extend `PRIMITIVE_NAMES` and `TokenEvaluationTensor` to accept CRS. |
| `symbolu_training/.../token_cache.py` | **Modify** | Add `C_tok`, `S_tok` buffer registration. Extend `set_scorers()` to accept CRS scorer. Extend `refresh()` to populate new buffers. Handle missing buffers in checkpoint loading. |
| `symbolu_training/.../unified/model_factory.py` | **Modify** | Behind `use_crs_combined_scorer` flag: instantiate `CRSCombinedScorer`, register in `conscious_gen` ModuleDict alongside (not replacing) `csr_scorer`. |
| `symbolu_training/.../unified/config.py` | **Modify** | Add `use_crs_combined_scorer: bool = False`, `cognitive_dim: int = 16`, `semantic_dim: int = 32`, `crs_semantic_threshold: float = 0.3`, `lambda_C_token`, `lambda_R_token`, `lambda_S_token`. Keep existing CSR configs. |
| `symbolu_training/.../losses/primitive_auxiliary.py` | **Modify** | Behind flag: update `DEFAULT_INDICES` to handle CRS column layout. |
| `symbolu_training/.../governance/kosha_router.py` | **Modify** | Behind flag: handle new primitive count in routing weights. |
| `symbolu_training/.../governance/bliss_gate.py` | **Modify** | Behind flag: handle new `T` column count. |
| `symbolu_training/.../integration/token_scorer.py` | **Modify** | Behind flag: integrate semantic firewall with Bliss gating. |
| `symbolu_training/.../integration/field_softmax.py` | **Modify** | Behind flag: update pair count for agreement energy. |
| `symbolu_training/.../unified/train.py` | **Modify** | Add CRS loss wiring behind flag. Add CRS diagnostics logging. |

### Files requiring name/doc changes only (defer to post-validation)

| File | Action | Phase-1 Scope |
|------|--------|---------------|
| `csr_phoneme_provider.py` | **No change** | Phoneme/varna pipeline. Name is historical. Defer rename. |
| `symbolu/inference/csr_inference.py` | **No change** | Inference-only. Not phase-1 scope. |
| `agentic/inference/csr_inference.py` | **No change** | Mirror. Not phase-1 scope. |
| `symbolu/inference/generation_tracer.py` | **No change** | Inference tracer. Update when CRS reaches inference. |
| `agentic/inference/generation_tracer.py` | **No change** | Mirror. |
| `scripts/test_cg_phases.py` | **Modify** | Add CRS-path structural validation alongside existing CSR tests. |
| `scripts/phase_probes/.../csr_bridge.py` | **No change** | Tests phoneme pipeline, not scoring doctrine. |
| `tests/test_sovereign_handshake.py` | **No change** | Tests phoneme injection. |
| `tests/test_sanskrit_g2p.py` | **No change** | G2P utility test. |
| `tests/test_varna_mapping.py` | **No change** | Varna utility test. |
| `docs/design/CONSCIOUS_GENERATION_DESIGN.md` | **Defer** | Update after CRS is validated and promoted. |
| `docs/audits/CG_MISTRAL_SIGNAL_AUDIT.md` | **Defer** | Update after migration. |
| `symbolu_core/phase_transformer.py` | **No change** | `enable_csr` flag is dead. Ignore for now. |

### Files safe to ignore

| File | Reason |
|------|--------|
| `symbolu_training/.../losses/bliss_coherence.py` | No direct CSR reference. Shape changes propagate from T. |
| `symbolu_training/.../losses/kosha_routing.py` | Indexes into T columns — changes propagate from TET. |
| `symbolu_training/.../integration/two_stage_generator.py` | Pass-through orchestrator. Changes propagate from inner modules. |
| `symbolu_training/.../diagnostics/adaptive_diagnostic_controller.py` | Metric name change only (`R_tok` drift). Defer. |
| `CTM_plus/CUDA/.../mm_scoring_kernel.cu` | CUDA kernel for fused scoring. Not in CG training path. |

---

*End of Phase 1 audit. No code changes made. Next step: Phase 2 implementation per Section E migration order.*
