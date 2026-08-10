# Hybrid LLM vNext — Component Disposition

**Audit date:** 2026-08-03 · Machine-readable twin: [`artifacts/hybrid_llm_component_disposition.json`](artifacts/hybrid_llm_component_disposition.json)

> **This audit deletes nothing.** Every disposition is a recommendation for a later, separately-authorized
> packaging phase. Vocabulary: `RETAIN_UNCHANGED`, `RETAIN_WITH_HARDENING`, `REIMPLEMENT`, `REPLACE`,
> `OPTIONAL_EXTENSION`, `LEGACY_COMPATIBILITY`, `BENCHMARK_ONLY`, `RESEARCH_ONLY`, `ARCHIVE`, `DELETE_LATER`.
> Phase components additionally carry `EXCLUDED_FROM_PACKAGING` per the binding directive.

## Model core (Phase family — all excluded from packaging)

| Component | Disposition | Packaging | Why |
|---|---|---|---|
| `PhaseAttentionLayer` | RESEARCH_ONLY | **EXCLUDED** | fluency-only; no retrieval; decorative; no kernel path |
| `LightweightPhaseAttention` | RESEARCH_ONLY / LEGACY_BENCHMARK | **EXCLUDED** | frozen reference; keep for repro |
| `HybridPhaseTransformer` | RESEARCH_ONLY | **EXCLUDED** | full-prefix-replay decode; no checkpoints; replaced by KDA-MLA |
| `BindingCachePhaseState` | RESEARCH_ONLY | **EXCLUDED** | Phase write-side; superseded by delta-rule state |
| `BindingCacheQuadQuery` | RESEARCH_ONLY | **EXCLUDED** | N×N before Top-K; role filled by periodic MLA |
| `BindingCacheBlock/Transformer` | RESEARCH_ONLY | **EXCLUDED** | two N×N/layer; no KV cache; Phase-dependent |
| `OntologicalBindingCacheTransformer` | RESEARCH_ONLY | **EXCLUDED** | unvalidated ontological + Phase |

## Memory subsystems

| Component | Disposition | Packaging | Why |
|---|---|---|---|
| `BoundedBindingSlots` (clean) | **OPTIONAL_EXTENSION** | EXPERIMENT_REQUIRED → OPTIONAL_ENTERPRISE_MEMORY | only impl with source/version/supersession/eviction; fragile single-fact recall (1/3 seeds); **backbone must not depend on it** |
| `SlotMemoryGCT` | REIMPLEMENT (if slots retained) | EXPERIMENT_REQUIRED | bounded but soft-EMA-only; no deletion/version/source — reimplement on the clean contract |

The bounded-slot decision is **independent of Phase's exclusion.** Slots may enter the package only after
meeting predefined multi-seed thresholds for entity–attribute binding, source attribution, supersession,
multi-key retrieval, and causal slots-off degradation (see the Falsification Plan). Until then they are an
optional enterprise-memory extension, not part of the canonical LM core.

## Attention / mixer components

| Component | Disposition | Why |
|---|---|---|
| `LocalWindowAttention` (production) | **REPLACE** | materializes N×N despite "O(n*w)"; replace with SWA/MLA |
| `LocalWindowAttention` (clean) | BENCHMARK_ONLY | correct O(N·W) reference baseline |
| `GCT` (Gated Coherence Transformer) | RESEARCH_ONLY | separate O(n²)+gating arch; misleadingly co-located; out of scope |
| `hybrid_token_event_attention` | RESEARCH_ONLY / BENCHMARK_ONLY | Phase-free evidence-typed experiment; keep as research |

## Adjacent systems (separate products — not the model package)

| Component | Disposition | Why |
|---|---|---|
| `hybrid_handover` (#9) + SEEB | RETAIN_WITH_HARDENING | small→frontier handover scaffold; different capability boundary |
| `SemanticRouter` (H-router) | RESEARCH_ONLY | routes to internal sub-models; not the mixer package |
| LLM Steering Controller (CRS) | RETAIN_UNCHANGED | governance/steering; not a model |
| Model Selection Policy (#8) | RETAIN_UNCHANGED | provider-selection governance; must **not** merge with #9 |

## Training / harness / docs

| Component | Disposition | Why |
|---|---|---|
| `train_unified_llm*.py`, `symbolu/training/unified/` | RETAIN_WITH_HARDENING / REIMPLEMENT | dispatcher (defaults to ontological, not Phase); vNext needs a fresh scoped harness on the FLA/KDA stack |
| `train_hybrid_7b.py`, `run_*_wiki103.sh`, `run_gct_training.sh` | BENCHMARK_ONLY / RESEARCH_ONLY | Phase/GCT recipes; no verified checkpoints |
| `phase_lc` / `phase_guided_slots[_v2]` / `enterprise_slots_quadratic` harnesses | BENCHMARK_ONLY | clean matched-baseline references for the vNext experiment |
| Stored Phase/Hybrid checkpoints & results | ARCHIVE / BENCHMARK_ONLY | micro-scale / self-reported; keep for provenance |
| `HYBRID_LLM_VC_BRIEF` v1/v2 | ARCHIVE | SUPERSEDED by v3 |
| v3 brief + claim ledger + falsification + comparative | RETAIN_UNCHANGED | canonical historical record; already skeptical |
| `tests/test_claims_validation.py`, `tests/test_unvalidated_claims.py` | LEGACY_COMPATIBILITY / DELETE_LATER | documentation tests; never cite as model evidence; do not carry as "validation" |

## Package-boundary requirement (Phase exclusion, enforceable)

The future canonical package must contain **no imports from Phase implementation paths**. AST-based tests
must prove the package does not import `symbolu.phase_transformer`, `PhaseAttentionLayer`,
`HybridPhaseTransformer`, `BindingCachePhaseState`, or `BindingCacheTransformer`, and the wheel must
contain no Phase implementation code, benchmarks, checkpoints, diagrams, config, or model claims. The
package docs may include a single migration note: *Phase was evaluated and excluded due to insufficient
capability evidence.* (These tests are authored in the packaging phase, not this audit.)
