# CSR Audit — for the Bhava+CSR Supervised Probe

> Read-only audit of what **CSR** actually is in this repo, before any probe code. Generation-quality
> representation track only. No governance/trust code, no generation/attention/mid-layer injection.

## 0. Two unrelated "CSR" exist — disambiguate first

| Name | Location | Meaning | In scope? |
|------|----------|---------|-----------|
| **CSR (this probe)** | `symbolu_training/.../primitives/csr_scorer.py` + `csr_phoneme_provider.py` | **C**ontextual **S**emantic **R**esonance — phonemic/varna resonance scoring | **YES** |
| CSR (governance) | `agentic/inference/csr_inference.py` | "Constraint-Structure-Resonance" inference guard (entropy/safety) | **NO — out of bounds** |

Everything below is the training-side phonemic CSR.

## 1. The intended CSR has TWO separable parts (both implemented)

CSR binds a **Sanskrit-vowel/varna sound basis** (per token) to a **contextual meaning state** (per
position) via a bilinear resonance. The two parts must not be collapsed.

### Part 1 — Sanskrit-vowel / Bhava-derived sound structure — **IMPLEMENTED**
- `varna_mapping.py` (repo root): `ARPABET_TO_VARNA` (every English phoneme → a Sanskrit varṇa);
  **`VOWEL_STATES`** = Māheśvara-Sūtra vowels → *states of consciousness*; `VRITTI_LABELS`
  (consonants → mental propensities); `VARGA_GROUPS` (articulatory classes). Pure data layer.
- `symbolu/formulas/data/varna_bridge_map_v1.json` (+ `symbolu_core/resonance/varna_bridge.py`):
  the Sanskrit-native varṇa → 12D ontological-layer mapping.
- `csr_phoneme_provider.py`:
  - `HybridG2P` (`:174`): word → ARPABET phonemes (CMUdict → custom → g2p_en neural, with a
    **char-level fallback** so it degrades without the heavy deps).
  - `VarnaCSRBridge` (`:794`): varṇa → **12D** vector; `vowel_to_12d` (`:863`) maps vowel
    "bridge_meaning" (consciousness state) → 12D.
  - **`CSREmbeddingProvider`** (`:1249`): `forward(input_ids) → {"csr_affinity": [B,T,12], ...}` —
    the per-token **12D Sanskrit-varna affinity**. This is the extractable sound-basis tensor.
- **Per-example feature** (`vowel_bhava`): pool `csr_affinity` over the prompt tokens → 12D. It is a
  function of the *input text* (token ids), model-independent.
- Trained projection (token-side): `CSRTokenScorer.token_proj`: 12D affinity → `R_tok` (V, 16),
  cached in `token_cache.R_tok` (registered buffer, `token_cache.py:79`).

### Part 2 — Contextual meaning / semantic support — **IMPLEMENTED**
- `CSRTokenScorer.context_proj` (`csr_scorer.py:59-63`): `[hidden ; o_ctx_32d] → 16D r_ctx`
  (`compute_context_repr`, `:88`). Per position; the contextual CSR state. **Trained** (the
  Active-CG run used `--lambda_csr_token 0.005`).
- Resonance binding: `forward(r_ctx, R_tok) → S_csr` (`:104`), bilinear `r_ctx^T M r_w`
  (low-rank `M = A Bᵀ`, `csr_dim=16`, `rank=8`). Per (position, vocab) — ties the contextual state
  back to the vowel-token basis.

## 2. The 10 audit questions, answered

1. **Modules**: `CSRTokenScorer` (`primitives/csr_scorer.py`), `CSREmbeddingProvider` /
   `VarnaCSRBridge` / `HybridG2P` (`csr_phoneme_provider.py`), `varna_mapping.py`,
   `token_cache.py` (R_tok cache), `crs_combined_scorer.py` (optional CRS gate, off by default).
2. **Tensors/states**:
   - `csr_affinity` `[B,T,12]` — Sanskrit-varna affinity per token (sound basis).
   - `r_ctx` `[B,T,16]` — contextual CSR state (context_proj output).
   - `R_tok` `[V,16]` — token-side CSR reprs (trained, cached buffer).
   - `S_csr` `[B,T,V]` — resonance scores (context × vocab).
3. **Dimensions**: affinity 12, context/token repr 16 (`csr_token_dim=16`), rank 8.
4. **Granularity**: `csr_affinity` & `r_ctx` are **per-token** (poolable to per-sequence). `R_tok` is a
   **per-vocab** table. **Not recurrent, not slot-memory** — `CSRTokenScorer` is feed-forward
   bilinear. No temporal/memory state to preserve (so `csr_temporal/csr_slots/csr_memory_state`
   are **not applicable** — will be recorded `feature_unavailable`).
5. **Used when**: **training** (token-resonance loss `lambda_csr_token`; `R_tok` refreshed every
   `ontology_cache_refresh_interval`). Not in the wrapper's generation logit path (confirmed by the
   earlier audit — the wrapper forward never calls csr).
6. **Connected to**: hidden state (context_proj input), 32D ontological state / **Bhava** (o_ctx is the
   32D state whose `[0:12]` is Bhava; context_proj consumes it), token ontology (shares the
   `token_cache`), phoneme/varna basis (token side). **NOT** connected to phase/intent or to the
   generation logits.
7. **Subparts not to collapse**: yes — (a) vowel/varna sound basis (`csr_affinity`/`R_tok`) and
   (b) contextual meaning (`r_ctx`), bound by (c) resonance `S_csr`. Probe keeps them separate.
8. **Temporal/contextual fields**: `r_ctx` is contextual (depends on hidden+state) but **not
   temporal/recurrent**. No sequence-memory tensor exists to preserve.
9. **Checkpoints with CSR**: `model.conscious_gen = nn.ModuleDict({... "csr_scorer", "token_cache"
   ...})` (`model_factory.py:732-746`) → CSR params + `R_tok` are in the **full** `{stem}_model.pt`
   under `conscious_gen.csr_scorer.*` and `conscious_gen.token_cache.R_tok`.
10. **Active-CG checkpoint**: the run trained `--lambda_csr_token 0.005`, so
    `conscious_gen.csr_scorer.context_proj.*`, `.token_proj.*`, `.A`/`.B`, and `token_cache.R_tok`
    **should be present** in `checkpoints_cg_active/best_model.pt`. The extractor **verifies** this at
    runtime and records `feature_unavailable` if any key is missing. (Note: the *ablation* loader
    filters to CG-head keys only, so the probe extractor must read the **full** checkpoint directly.)

## 3. What is extractable as a per-example feature (and how)

| Group | Source | Dim | Availability |
|-------|--------|-----|--------------|
| `bhava_value` | `state[0:12]` (+entropy) | 13 | from wrapper forward (have it) |
| `vowel_bhava` | `CSREmbeddingProvider(input_ids).csr_affinity`, pooled | 12 | needs provider (char-fallback ok) |
| `csr_contextual` | `context_proj([hidden_pooled; state_32d])` | 16 | needs `csr_scorer.context_proj` in ckpt |
| `csr_resonance` | summary(`S_csr` = bilinear(r_ctx, R_tok)) | ~6 | needs context_proj + A/B + R_tok |
| `delta_bhava` | bhava(full) − bhava(prompt[:-1]) | 13 | have it (≈0, dead path) |
| `hidden_*` | pooled/last final hidden | 4096 | have it (PCA'd) |

`csr_temporal`, `csr_slots`, `csr_memory_state` → **feature_unavailable** (reason: CSRTokenScorer is
feed-forward; no temporal/slot/memory tensor exists).

## 4. Implications for the probe
- The two-part CSR is **real and implemented** — do **not** report it missing. But each per-example
  feature has a runtime availability gate (provider importable; checkpoint keys present); the
  extractor records `feature_unavailable: {reason}` rather than fabricating.
- `vowel_bhava` is **model-independent** (text-derived) — a clean separable basis.
- `csr_contextual` is a **trained projection of [hidden; state]** — so it is, by construction, partly a
  function of `hidden`. The fair test (per-group PCA + paired-vs-hidden) must check it adds signal
  **beyond** hidden, exactly as for Bhava.
- The hypothesis to test: does **bhava + vowel_bhava + csr_contextual** beat hidden_only / bhava_only
  / csr_only — i.e. is there complementary structure neither part captures alone.
