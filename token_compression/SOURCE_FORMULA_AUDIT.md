# SOURCE_FORMULA_AUDIT.md

**Purpose.** Formula-recovery and eligibility audit *before* any protected-context
compression harness is built. This document does **not** run or endorse any
experiment. It records, for every candidate formula, what the repo actually
implements versus what is a reconstruction, so that later claims are grounded in
source rather than in the ChatGPT description.

**Hard rules honored here.**
- No claim that SCC, USE, or KVPro "already proves token compression." None of them
  were built for it; the evidence below shows why each transfer is a *hypothesis*.
- Every formula carries exactly one interpretation label (§ legend) and is not
  mixed with another category.
- Disputed signs / weights were resolved from actual source, not assumption.

## Interpretation-label legend

| Label | Meaning |
|---|---|
| `DOCUMENTED_ORIGINAL_FORMULA` | Implemented in repo code (or a frozen spec) in its original domain |
| `GENERIC_REFERENCE_FORMULA` | Standard public math (cosine sim, plain INT4) — no proprietary content |
| `COMPRESSION_SPECIFIC_REFORMULATION` | Adapted *for* context compression; not an original repo formula |
| `PROPOSED_LEARNED_EXTENSION` | A learned/calibrated layer proposed on top; not yet built |
| `UNDERSPECIFIED_REQUIRES_SOURCE_RECOVERY` | Asserted to exist but not found as implemented; needs recovery before use |

**Audit field template (per §6 of the task):** (1) Formula · (2) Source file/document ·
(3) Exact vs reconstructed · (4) Variable definitions · (5) Compression role ·
(6) Fair baseline · (7) Failure modes · (8) Eligibility decision.

---

# A · SCC family (structural / semantic coherence)

## A1 — Per-layer coherence (SCC "S1") — **entropy sign resolved**

1. **Formula.**
   `Cᵢ = α·Sᵢ + β·Rᵢ + γ·(1−Eᵢ) + δ·Pᵢ`
   The entropy term enters as **`(1−Eᵢ)`** — high entropy *lowers* coherence. This is
   settled: 4 of 4 implementations and the authoritative spec use `(1−Eᵢ)`. The single
   `+γ·Eᵢ` occurrence is a docstring typo contradicted by its own inline comments and
   the code that consumes it.
2. **Source file/document.**
   - `symbolu_robotics/formulas/scc.py:202-208` (executed); docstring `:9-16`. Weights `α,β,γ,δ = 0.3,0.3,0.2,0.2` (`:91-94`).
   - `symbolu_extensions/image_gen/scc_image.py:364-371` (executed).
   - `symbolu/ontological/semantic_coherence.py:369-374` and `:894-899` (two implemented sites; mirror copy `symbolu_core/ontological/semantic_coherence.py`, identical lines).
   - Spec: `docs/design/COHERENCE_FORMULA_SPECIFICATION_v1.0.md:432` (+ symbol table `:435-443`).
   - **Typo to fix separately:** `symbolu_extensions/image_gen/config.py:203` prints `γ·Eᵢ` (drops the `1−`); its own attribute comment says "inverted" and `scc_image.py:369` computes `(1.0 − E_i)`.
3. **Exact vs reconstructed.** EXACT (implemented, multiple sites).
4. **Variable definitions** (from spec `:435-443`): `Sᵢ` semantic consistency, spec ref `1/(1+Var(hᵢ))`; `Rᵢ` resonance with neighbors `(C[i,i−1]+C[i,i+1])/2`; `Eᵢ` normalized Shannon entropy `−Σₖ pₖ log pₖ / log K`; `Pᵢ` predictability `Corr(hᵢ(t),hᵢ(t−1))`. **Domain of `i` is a *model layer* (or a sensor/diffusion channel), not a text unit / sentence / clause.**
5. **Compression role (hypothesized).** Weak per-unit importance signal (retain high-coherence units) — see A4/A5 for the safer validator role.
6. **Fair baseline.** Plain embedding-similarity importance and TF-IDF/entropy ranking, at identical token budget. SCC must beat these, not just correlate.
7. **Failure modes.** (a) **Domain mismatch:** `Sᵢ,Rᵢ,Pᵢ` are defined over layer hidden-state statistics; there is no implemented mapping from "sentence/clause" to these quantities — that mapping is the unbuilt work. (b) **Low-coherence ≠ droppable:** a decisive exception ("do not deploy on Friday") can be low-coherence yet critical, so this score must never authorize deletion. (c) **Weight ambiguity:** code defaults `0.3/0.3/0.2/0.2` differ from spec `0.30/0.25/0.25/0.20` — resolve before any calibration.
8. **Eligibility decision.** **ELIGIBLE ONLY as an auxiliary P1/P2 ranking signal, after a text-unit → (S,R,E,P) operationalization is built and preregistered. NOT eligible as a protection authority or standalone selector.** Label: `DOCUMENTED_ORIGINAL_FORMULA` (original domain) → its compression use is a hypothesis, not a proven transfer.

## A2 — Cross-representation semantic similarity (cosine)

1. **Formula.** `S_ij = (eᵢ·eⱼ)/(‖eᵢ‖‖eⱼ‖)`; per-unit original-vs-compressed `Sᵢ^{o,c} = cos(eᵢ^{(o)}, eᵢ^{(c)})`.
2. **Source.** Generic; cosine similarity is used throughout the repo (e.g. `symbolu_robotics/formulas/use.py:105` computes `R = normalized·normalizedᵀ`). No proprietary content.
3. **Exact vs reconstructed.** EXACT as generic math.
4. **Variables.** `eᵢ` = embedding/semantic representation of unit `i`.
5. **Compression role.** Drift detector between original and compressed unit: `L_semantic = 1 − (Σ wᵢ Sᵢ^{o,c})/(Σ wᵢ)`.
6. **Fair baseline.** It *is* the baseline every other validator must beat.
7. **Failure modes.** **Cannot prove completeness.** A fluent compressed passage can score high cosine while dropping one decisive token ("not"). High similarity ≠ preserved meaning.
8. **Eligibility.** ELIGIBLE as a cheap secondary drift signal only; **never** as a preservation proof. Label: `GENERIC_REFERENCE_FORMULA`.

## A3 — Combined coherence × similarity `C'ᵢ = Cᵢ^{(c)}·Sᵢ^{o,c}`

1. **Formula.** `C'_ij = C_ij × S_ij` (per-unit `C'ᵢ = Cᵢ^{(c)}·Sᵢ^{o,c}`).
2. **Source.** The task calls this "a documented combined form." **Recovery result: NOT found as an implemented `C×S` product in the SCC code.** The implemented SCC sites compute `Cᵢ` (A1) but do not multiply it by an original-vs-compressed cosine.
3. **Exact vs reconstructed.** RECONSTRUCTED (compression-specific); the "documented" claim is unsubstantiated.
4. **Variables.** As A1/A2.
5. **Compression role.** Proposed combined preservation score.
6. **Fair baseline.** Must beat A2 alone *and* exact-field/numeric/entity checks (B-series in §D).
7. **Failure modes.** Inherits A1's domain-mismatch and A2's completeness blindness; multiplying two imperfect signals does not create a guarantee. No fixed threshold (0.7/0.9) is admissible without calibration.
8. **Eligibility.** **NOT eligible until sourced.** Label: `UNDERSPECIFIED_REQUIRES_SOURCE_RECOVERY` (if a real `C×S` source exists it must be cited; otherwise treat as `COMPRESSION_SPECIFIC_REFORMULATION`).

## A4 — SCC coherence-drift validator `L_SCC-drift = Σ wᵢ |Cᵢ^{(o)} − Cᵢ^{(c)}|`

1. **Formula.** `ΔCᵢ = |Cᵢ^{(o)} − Cᵢ^{(c)}|`; `L_SCC-drift = Σ wᵢ ΔCᵢ`; accept iff `L_SCC-drift ≤ τ_C`.
2. **Source.** No implemented drift metric found; built on A1's `Cᵢ`.
3. **Exact vs reconstructed.** RECONSTRUCTED.
4. **Variables.** `Cᵢ^{(o)}`, `Cᵢ^{(c)}` = A1 score on original vs compressed; `wᵢ` unit weight; `τ_C` calibrated threshold.
5. **Compression role.** **Reject/relax trigger only** — may lower ratio, restore units, or reject; **may never override a failed exact-protection check.**
6. **Fair baseline.** Same validator without the SCC term (the incremental test `Δ_SCC` below).
7. **Failure modes.** Coherence can be *preserved* while a fact is *deleted* (drift ≈ 0, meaning lost); τ_C is dataset-dependent.
8. **Eligibility.** ELIGIBLE as a *non-authoritative* relax/reject signal, pending the `Δ_SCC` incremental test. Label: `COMPRESSION_SPECIFIC_REFORMULATION`.

## A5 — SCC preservation-confidence head `p_preserved = σ(b₀ + b₁C' − b₂L_drift − b₃L_contradiction − b₄L_ref-break)`

1. **Formula.** As stated (learned logistic calibration).
2. **Source.** None; proposed on top of A3/A4.
3. **Exact vs reconstructed.** RECONSTRUCTED / not built.
4. **Variables.** `b*` learned; inputs are A3/A4 losses plus contradiction and reference-break losses (both themselves unbuilt).
5. **Compression role.** Calibrated accept/relax gate.
6. **Fair baseline.** **The identical logistic head without the SCC terms.** Incremental test: `Δ_SCC = Perf(simple validators + SCC) − Perf(simple validators)`. SCC survives only if `Δ_SCC` is practically and statistically favorable (mirror BCVF's fair-capacity-matched discipline in `cyber_security/behavioral_biometrics/study/bcvf.py`).
7. **Failure modes.** Over-fitting to a benchmark; hides catastrophic rare misses behind average calibration.
8. **Eligibility.** **NOT eligible to build until A1's text operationalization + A4 exist and `Δ_SCC` is preregistered.** Label: `PROPOSED_LEARNED_EXTENSION`.

---

# B · USE family (relationship / synchronization)

## B1 — Windowed phase-correlation (USE "U1") `C_ij(t) = (1/W) Σ_{k=0}^{W−1} cos(φᵢ(t−k) − φⱼ(t−k))`

1. **Formula.** As written; part of the U1–U5 "Universal/Unified Synchronization Engine" set (U2 total coherence `Σ_{i<j} M_ij C_ij`, U3 mean-field gradient `−N·sin(φᵢ−φ_mean)`, U4 sync step, U5 threshold interpretation).
2. **Source.** IMPLEMENTED, **neural/signal phases only**:
   - `simulator/use_6g/core/state.py:247-291` (RF antenna element phases; U2–U5 in same file `:293-505`).
   - `symbolu_extensions/image_gen/use_image.py:217-234` (diffusion / 12 ontological-layer phase vectors); U2 `:264-294`, U3 `:357-414`.
   - `symbolu_extensions/vision/phase_integrator_3d.py:248-292`, `symbolu_extensions/vision/video/fscsv_wrapper.py:270-304` (video-diffusion phasors).
   - Also `simulator/ctm_plus/controllers/ctm_plus.py:129,139` (KV-page phases), `ndol/scheduler.py:50`, `symbolu/sovereign/metrics.py:589-591`.
3. **Exact vs reconstructed.** EXACT (implemented, original domain).
4. **Variables.** `φᵢ` = phase of a *signal / oscillator / neural layer*, over a window `W`; `M_ij` coupling weight (U2). **No text nodes anywhere.**
5. **Compression role.** None as-is. The task's own guardrail applies: *"Do not force phase onto ordinary text clauses. Phase is only valid when a meaningful ordered/oscillatory representation exists."* Text clauses have no such phase.
6. **Fair baseline.** N/A for text until a legitimate phase representation of text exists (none does).
7. **Failure modes.** **Category error** if applied to text: cosine-of-phase presupposes an oscillatory latent that text units do not possess.
8. **Eligibility.** **NOT eligible for text/context compression.** Eligible only in its native signal/neural domains (out of scope here). Label: `DOCUMENTED_ORIGINAL_FORMULA`.

## B2 — Phase-amplitude interaction / Phase-Quad `A_ij = aᵢ·aⱼ·cos(φᵢ−φⱼ)`, `cos(φᵢ−φⱼ)=Re(e^{iφᵢ}·e^{−iφⱼ})`

1. **Formula.** As written, with cumulative state `State_t = Σ_{j≤t} K_j·V_j`, `Q = a·e^{iφ}`, `K = a·e^{−iφ}`, `Out = Re(Q·State)`.
2. **Source.** IMPLEMENTED as `PhaseAttentionLayer` in `symbolu/phase_transformer.py` (docstring `:1911-1921`; forward `:2405-2472`; cumulative state `torch.cumsum` `:2470/2472`). Mirror `symbolu_core/phase_transformer.py`. Doc: `docs/PHASE_ATTENTION_ALGORITHM.md:34,45`, `docs/PHASE_ATTENTION_PAPER.md:41,53,68`.
3. **Exact vs reconstructed.** EXACT.
4. **Variables.** `aᵢ,φᵢ` = *learned per-token* amplitude/phase of **neural token embeddings**; `State` = cumulative KV phasor sum. This is an O(N) linear-attention mechanism, not a text-relationship metric.
5. **Compression role.** None. It is a model internal, not a context-preservation measure.
6. **Fair baseline.** N/A.
7. **Failure modes.** Same category error as B1 if reinterpreted as clause-relationship scoring.
8. **Eligibility.** **NOT eligible** as a compression validator. Label: `DOCUMENTED_ORIGINAL_FORMULA`.

## B3 — Text-graph relationship recall `R_USE = Σ_{(i,j)∈E_o} w_ij·1[(i,j)∈E_c] / Σ w_ij`

1. **Formula.** Weighted recall of original relation edges (rule→exception, condition→consequence, claim→citation, entity→alias, pronoun→referent, action→approval, action→rollback, instruction→scope, event→consequence); `L_USE = 1 − R_USE`.
2. **Source.** **No implemented source.** Recovery found *no* text-graph coupling formula named USE. The only real multi-stream coupling, `cyber_security/behavioral_biometrics/coupling.py`, deliberately uses lagged cross-correlation / CCA / spectral coherence (`:86-152,227-238`), **not** the phase-cosine or an edge-recall metric. The semantic `R[v,a]` matrix in `symbolu/chitta_vritti/coupling.py` is a fixed hand-authored 5×12 multiply, not a relation-recall formula.
3. **Exact vs reconstructed.** RECONSTRUCTED; **must be labeled as such** (task §5). It is *not* USE U1.
4. **Variables.** `E_o,E_c` original/compressed relation edges; `w_ij` edge weight.
5. **Compression role.** Primary *relationship-preservation* validator — the genuinely useful USE-inspired idea for compression. It requires a **relation extractor** to build `E_o` — that extractor is the real work and does not exist yet.
6. **Fair baseline.** Deterministic dependency-edge recall (spaCy/UD parse edges, coref) at identical budget. `R_USE` earns a place only if it reduces relation breakage / catastrophic omissions / decision flips / multi-hop failures *beyond* that deterministic extractor (task §2.6).
7. **Failure modes.** Edge-detection recall < 1 silently drops relations; binary `1[·]` ignores partial/aliased edges (see B4).
8. **Eligibility.** ELIGIBLE as a *candidate* validator **pending an extractor + the USE incremental test**, and only under its true label. **Do not present as reuse of the USE patent.** Label: `COMPRESSION_SPECIFIC_REFORMULATION`.

## B4 — Soft relation similarity `R_soft = Σ w_ij·sim(r_ij^{(o)}, r_ij^{(c)}) / Σ w_ij`

1. **Formula.** As written; `sim` ∈ {cosine, relation-embedding, entailment, conditional MI, dependency-label agreement, graph alignment}.
2. **Source.** None; generalizes B3.
3. **Exact vs reconstructed.** RECONSTRUCTED.
4. **Variables.** `r_ij` = semantic relation representation between units `i,j`.
5. **Compression role.** Non-binary relaxation of B3.
6. **Fair baseline.** B3 (binary recall) itself.
7. **Failure modes.** `sim` choice dominates results; entailment `sim` reintroduces an LLM call (cost/latency/own error rate).
8. **Eligibility.** Deferred to after B3. Label: `COMPRESSION_SPECIFIC_REFORMULATION`.

## B5 — Cross-source coupling `U_mn = Σ_{i∈m} Σ_{j∈n} w_ij·C_ij` and protected-relation set `E_protected-rel = {(i,j): w_ij·C_ij ≥ τ_U}`

1. **Formula.** Coupling score across sources `m,n` (ticket↔deploy, policy↔approval, log↔incident, schema↔argument, action↔state); high-weight coupled pairs must retain both endpoints or an explicit lossless reference.
2. **Source.** As a *phase* `C_ij` → B1 (neural only, ineligible). As a *statistical* coupling over real streams → `behavioral_biometrics/coupling.py` uses CCA/xcorr, which could instantiate `C_ij` but is not wired to text.
3. **Exact vs reconstructed.** RECONSTRUCTED for text; the coupling primitive exists only in the biometric statistical form.
4. **Variables.** `C_ij` = coordination measure between linked units; `τ_U` protection threshold.
5. **Compression role.** Identify cross-source pairs that must be co-retained — directly relevant to enterprise agent context.
6. **Fair baseline.** Deterministic join on shared identifiers (ticket id, resource arn) — a keyed lookup already preserves most such pairs without any coupling score.
7. **Failure modes.** If `C_ij` is the phase form, category error (B1); if statistical, needs paired-stream data that agent context may not present as time series.
8. **Eligibility.** ELIGIBLE as a candidate only with a *non-phase* `C_ij` and only if it beats a deterministic keyed join. Label: `COMPRESSION_SPECIFIC_REFORMULATION`.

## B6 — USE-assisted unit importance `Iᵢ^{USE} = Σ_j w_ij·|C_ij|`

1. **Formula.** Relationship centrality of a unit.
2. **Source.** Reconstruction over B3/B5 edges.
3. **Exact vs reconstructed.** RECONSTRUCTED.
4. **Variables.** `C_ij` coupling/relation strength.
5. **Compression role.** Rank P1/P2 units by how much important information they connect (e.g. a short exception clause with low query relevance but strong tie to a policy rule). **Ranking signal only; must not override P0.**
6. **Fair baseline.** Graph degree/PageRank on the deterministic dependency graph.
7. **Failure modes.** Inherits edge-extraction recall limits.
8. **Eligibility.** ELIGIBLE as auxiliary ranking, after B3. Label: `COMPRESSION_SPECIFIC_REFORMULATION`.

---

# C · KVPro / INT4-protected family

> **Recovery headline.** The "int4_protected" mechanism **is implemented** (not a stub,
> no NDA gate in the repo), but it reduces to **generic asymmetric per-group INT4 + a
> static top-4% max-abs outlier-channel bf16/int8 sidecar** (KVQuant/AWQ-style). There is
> **no** per-element mask `m_j`, **no** dynamic outlier threshold, **no** error-bound /
> loss-optimized mask, and **no** adaptive protected budget `B_P`. KVPro operates on the
> **KV cache after tokenization** — it does **not** reduce input tokens and cannot, by
> itself, prove context compression.

## C1 — Generic asymmetric group-INT4 arithmetic

1. **Formula.** `s_g = (x_max − x_min)/15` (clamp ≥ 1e-8); `q = round((x − x_min)/s_g).clip(0,15)`; `x̂ = q·s_g + x_min`. Two 4-bit codes packed per byte.
2. **Source.** `CTM_plus/KVPolicy/kv_policy/phase5b_streaming_quantizer.py:245-271` (`_ASYM_DIV=15.0`, `:49-51`); live paged writer `CTM_plus/KVPolicy/kv_policy/phase5b_4c_paged_writer.py:1045-1051` (V), `:1108-1114` (K).
3. **Exact vs reconstructed.** EXACT, and **generic**.
4. **Variables.** `q_max=15`; group = vLLM block (16 in streaming, 32 in shipped backend, `int4_protected.py:117`); asymmetric zero-point implicit in float `x_min`.
5. **Compression role.** Downstream KV-memory reduction only; **orthogonal** to input-token count. `Total efficiency ≈ (fewer input tokens) × (fewer KV bytes/retained token)`.
6. **Fair baseline.** vLLM FP16 KV and naïve INT4 (this *is* the naïve INT4 reference).
7. **Failure modes.** Naïve INT4 collapses on hard long-context retrieval (the KVPro brief's own motivation); numeric distortion, not information deletion.
8. **Eligibility.** ELIGIBLE only as a **complementary post-tokenization layer**, never counted in an input-token-reduction claim. Label: `GENERIC_REFERENCE_FORMULA`.

## C2 — prot-int8 static-scale variant

1. **Formula.** `s = (x_max − x_min)/255` (clamp ≥ 1e-8); `code = round((x − x_min)/s).clip(0,255)`; `x̂ = code·s + x_min`; scales static per-(layer,head,channel) from calibration.
2. **Source.** `CTM_plus/KVPolicy/kv_policy/phase5b_4c_paged_writer.py:711-773` (`_PROT_INT8_DIV=255`).
3. **Exact vs reconstructed.** EXACT, generic INT8 (novelty = static calibrated scales only).
4. **Variables.** `q_max=255`.
5. **Compression role.** Storage form for protected channels (denser than bf16 sidecar).
6. **Fair baseline.** bf16 sidecar.
7. **Failure modes.** Static ranges clip on out-of-calibration activations (mitigated by 1.1× `_widen_minmax` margin).
8. **Eligibility.** ELIGIBLE as a codec detail, out of scope for context compression. Label: `GENERIC_REFERENCE_FORMULA`.

## C3 — Protected-channel selection (the actual "KVPro" differentiator)

1. **Formula.** `mag = |K|.amax over calibration tokens` (per channel); per (layer, kv-head) protect the **top-k channels by `mag`**, `n_protect = max(1, round(D × protect_fraction))`, `protect_fraction = 0.04`. Protected channels stored per-token at full precision (bf16 / prot-int8) in a sidecar that overrides the 4-bit grid at read time.
2. **Source.** `CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py:297-320` (max-abs accumulation), `:394,406-408` (top-k), `:474` (exact-count assert). Applied: `phase5b_streaming_quantizer.py:210-213`; `phase5b_4c_paged_writer.py:1079-1082`. Mask artifact loaded `:804-869`.
3. **Exact vs reconstructed.** EXACT — but it is a **standard static outlier-channel heuristic**, not a proprietary optimization. Do not describe it as an exotic protected-mask solver.
4. **Variables.** Mask `m` shape `(layers, H_kv, D)`, static per-model, per-**channel** (not per-element, not per-token, not per-sequence); "budget" = fixed fraction 4%.
5. **Compression role (transferable *principle* only).** "Protect the small high-leverage subset exactly; compress the bulk." This is the design analogy for P0/P1/P2 (§C5) — **not** a reusable formula (magnitude ≠ semantic criticality; task §3.1 warning).
6. **Fair baseline.** KVQuant / AWQ outlier-channel protection (identical idea, published).
7. **Failure modes.** Max-abs magnitude does **not** identify semantically critical tokens (a low-magnitude channel can carry a negation/exception); calibration is per-model and must be redone per model (`int4_protected.py:36-39`).
8. **Eligibility.** The *principle* is ELIGIBLE as the P0/P1/P2 design analogy. The *magnitude-selection formula* is **NOT eligible** to pick semantic protected units. Label: `DOCUMENTED_ORIGINAL_FORMULA` (implementation) used only as `COMPRESSION_SPECIFIC_REFORMULATION` analogy.

## C4 — Protected-mask optimization abstraction `min MemoryCost s.t. L_task ≤ ε, max_{protected}|x−x̂| ≤ ε_P, Σ m_j ≤ B_P`

1. **Formula.** As written (constrained mask optimization).
2. **Source.** **Not implemented.** Recovery found only `topk(max-abs)` selection + a 1.1× clip margin; no loss, no error bound, no `argmin`, no budget solver. (Separate `kv_qat_*.py` learned-rotation experiments exist but do not feed the shipped mask.)
3. **Exact vs reconstructed.** RECONSTRUCTED abstraction of what KVPro *could* be, not what it *is*.
4. **Variables.** `B_P` protected budget, `ε_P` protected error tol, `ε_task` task tol — none present in the shipped codec.
5. **Compression role.** Generic mathematical framing of protect-vs-compress.
6. **Fair baseline.** The actual top-k heuristic (C3).
7. **Failure modes.** Presenting this as the implemented mechanism would misstate the repo.
8. **Eligibility.** Framing only. Label: `GENERIC_REFERENCE_FORMULA` (must not be attributed to the shipped KVPro codec).

## C5 — Context-compression transfer: P0/P1/P2 tiers + `Compress(C)` with `D(C_orig)=D(C_comp)`

1. **Formula.**
   `m_i ∈ {0,1}` protected indicator; tiers `P0` (exact/lossless), `P1` (meaning-preserving), `P2` (compressible).
   `Compress(C) = {C_{P0}^{exact}, C_{P1}^{meaning-preserved}, Compress(C_{P2}), provenance}`.
   `min Tokens(C_comp)` s.t. `Recall(P0)=1`, `MeaningFidelity(P1) ≥ τ_{P1}`, `TaskLoss ≤ ε`, and for ActionGate cases `D(C_orig)=D(C_comp)`.
2. **Source.** No implemented source; the *analogy* is to C3 (protect small subset, compress bulk). `D(·)` is real — see §D.
3. **Exact vs reconstructed.** RECONSTRUCTED (this is the proposed product core).
4. **Variables.** `Recall(P0)` worst-case protected-unit recall; `τ_{P1}` meaning threshold; `D` = ActionGate decision (§D).
5. **Compression role.** The central architecture. `P0` protection is a **hard constraint**, outside any weighted score (task §4).
6. **Fair baseline.** LLMLingua-2 / Selective Context / extractive summ / truncation / top-k RAG, at matched ratio.
7. **Failure modes.** `Recall(P0)=1` is only as good as the P0 *detector* (negations, numbers, entities, approvals) — the detector is the unbuilt product; `MeaningFidelity(P1)` needs an NLI/entailment predicate that reintroduces LLM cost.
8. **Eligibility.** ELIGIBLE as the architecture to build **P0 + deterministic structural layer first** (the only layer that can claim `Recall=1` by construction). Label: `COMPRESSION_SPECIFIC_REFORMULATION`.

## C6 — WarmTier snapshot/restore

1. **Formula/mechanism.** Serialize packed K/V nibbles + 5 sidecars (`k_scale,k_xmin,k_protect,v_scale,v_xmin`); restore into fresh paged allocation; `verify_roundtrip` byte gate.
2. **Source.** `CTM_plus/KVPolicy/kv_policy/tier5b_snapshot.py` (primitive). Live backend `ndol/experiments/warmtier_backends.py:174-199` **raises `NotImplementedError`**.
3. **Exact vs reconstructed.** Primitive EXACT but **HARDWARE-UNTESTED** (`tier5b_snapshot.py:8-13`); live engine wiring absent.
4. **Variables.** n/a.
5. **Compression role.** Context-memory tiering analogy (hot / protected / warm / cold) — relevant to "reference substitution" in structural compression.
6. **Fair baseline.** APC HOT reuse (`kvpro_apc_backend`), which is the working path today.
7. **Failure modes.** Claiming a working WarmTier serving path would overstate the repo (backend raises).
8. **Eligibility.** Concept ELIGIBLE as tiering inspiration; **do not cite as a shipped capability.** Label: `DOCUMENTED_ORIGINAL_FORMULA` (primitive) with status *untested*.

---

# D · ActionGate decision function `D`

1. **Formula/mechanism.** `D = gate.evaluate(envelope, signed_policy, evidence, approvals, now, …)` → one of six frozen outcomes `{ALLOW, ALLOW_WITH_CONSTRAINTS, SIMULATE_AND_RETRY, REQUEST_MORE_EVIDENCE, ESCALATE_TO_HUMAN, DENY}`. Envelope = canonical **24-field** structure built by `build_envelope` from a `ToolRequest`, JCS-canonicalized and hashed.
2. **Source.** `cyber_security/action_gate_reference/action_gate_ref/gate.py:144` (`evaluate` signature), `:46-72` (deterministic `extract_facts`); envelope `cyber_security/action_gateway/action_gateway/mapping.py:96-132`; consumer `cyber_security/action_gateway/action_gateway/gateway.py`.
3. **Exact vs reconstructed.** EXACT, deterministic, and **frozen**. The gate docstring states: *"No broad consequence reasoning, no AI, no BCVF/USE/SCC."* — the gate is deliberately free of the heuristics audited above.
4. **Variables.** Envelope fields (operation, target_resource, arguments, credential_scope, reversibility, policy_version, state_freshness, approvals, evidence, …). Decision-relevant facts extracted deterministically from `arguments`.
5. **Compression role.** **The differentiated, exactly-measurable metric: decision invariance `D(C_orig)=D(C_comp)`.** Computable offline, no LLM in the loop, because `D` is a real deterministic function. No competitor lacking an admissibility oracle can even define this.
6. **Fair baseline.** Generic compressors' decision-invariance at matched ratio (they can only be *measured* against `D` here, not equipped with it).
7. **Failure modes.** **Coverage caveat:** the gate reads a *structured* envelope, so invariance is only meaningful when compression sits upstream of, and can perturb, envelope construction (amounts, approvals, reversibility, policy_version, state_freshness). If a compressed fact never touches any of the 24 fields, `D(C_orig)=D(C_comp)` is trivially true and proves nothing. The honest metric is decision invariance on a task set **deliberately seeded** with envelope-affecting context.
8. **Eligibility.** **ELIGIBLE and recommended as the headline preservation metric**, with the coverage caveat enforced by construction of the eval set. Label: the metric is a `COMPRESSION_SPECIFIC_REFORMULATION` built on a `DOCUMENTED_ORIGINAL_FORMULA` (`D`).

---

# E · Combined candidate importance score

1. **Formula.** `Iᵢ = α Rᵢ + β Nᵢ + γ Cᵢ^{constraint} + δ Dᵢ^{dependency} + ε Uᵢ^{removal} + ζ Sᵢ^{consequence} − η Xᵢ^{redundancy}`, with protection applied **outside** the score (`u_i∈P0 ⇒ exact`; `P1 ⇒ meaning-preserving only`; `P2 ⇒ rankable/summarizable/droppable`).
2. **Source.** None; the term operators (constraint/dependency/consequence extractors) are unbuilt.
3. **Exact vs reconstructed.** RECONSTRUCTED; the hard 90% is the extractors, which the Greek letters hide.
4. **Variables.** As labeled; each coefficient multiplies an *undefined operator*.
5. **Compression role.** P1/P2 ranking within budget; **never** a gate on P0.
6. **Fair baseline.** LLMLingua-2 token-importance and entropy ranking.
7. **Failure modes.** A high `Rᵢ` "paying for" deletion of a decisive `not`/amount/approval — the exact reason protection must be a hard constraint, not a score term.
8. **Eligibility.** ELIGIBLE as a P1/P2 ranker only after its operators exist and after the deterministic structural + P0 layers are validated. Label: `PROPOSED_LEARNED_EXTENSION`.

---

# F · Validator stack and precedence (recovered rule)

`V_simple = f(P0 recall, numbers, entities, negations, dependencies)` — deterministic, authoritative.
`V_SCC = f(V_simple, C'_preserve, L_SCC-drift)` — advisory (A3/A4).
`V_USE = f(V_simple, R_USE)` — advisory (B3).

**Accept iff `V_simple = 1`** and no advisory validator raises additional risk. **SCC and USE
may only cause restoration, reduced compression, extra validation, or rejection — they may
never authorize deletion of a deterministically protected (P0) unit.** This precedence
mirrors the frozen ActionGate rule that keeps `D` free of SCC/USE/BCVF.

---

# G · Eligibility summary

| # | Formula | Label | Eligible for compression? |
|---|---|---|---|
| A1 | SCC S1 coherence `α S+β R+γ(1−E)+δ P` | `DOCUMENTED_ORIGINAL_FORMULA` | Only as auxiliary P1/P2 rank after text-operationalization + preregistration |
| A2 | Cosine similarity | `GENERIC_REFERENCE_FORMULA` | Yes, as weak drift signal (never a proof) |
| A3 | Combined `C×S` | `UNDERSPECIFIED_REQUIRES_SOURCE_RECOVERY` | No — source not found |
| A4 | SCC-drift validator | `COMPRESSION_SPECIFIC_REFORMULATION` | Yes, as non-authoritative relax/reject |
| A5 | SCC preservation head | `PROPOSED_LEARNED_EXTENSION` | No — pending `Δ_SCC` test |
| B1 | USE U1 phase-correlation | `DOCUMENTED_ORIGINAL_FORMULA` | No — neural-phase only; category error on text |
| B2 | Phase-Quad `a a cos` | `DOCUMENTED_ORIGINAL_FORMULA` | No — model internal, not a text metric |
| B3 | Text-graph `R_USE` recall | `COMPRESSION_SPECIFIC_REFORMULATION` | Candidate — needs extractor + incremental test; **not** the USE patent |
| B4 | Soft relation `R_soft` | `COMPRESSION_SPECIFIC_REFORMULATION` | Deferred to after B3 |
| B5 | Cross-source coupling `U_mn` | `COMPRESSION_SPECIFIC_REFORMULATION` | Candidate with non-phase `C_ij`, vs keyed-join baseline |
| B6 | USE unit importance | `COMPRESSION_SPECIFIC_REFORMULATION` | Auxiliary rank after B3 |
| C1 | Generic group-INT4 | `GENERIC_REFERENCE_FORMULA` | Complementary post-tokenization only |
| C2 | prot-int8 | `GENERIC_REFERENCE_FORMULA` | Codec detail, out of scope |
| C3 | Protect-channel top-k max-abs | `DOCUMENTED_ORIGINAL_FORMULA` (as analogy) | Principle only; magnitude ≠ semantic criticality |
| C4 | Mask-optimization abstraction | `GENERIC_REFERENCE_FORMULA` | Framing only; not the shipped mechanism |
| C5 | P0/P1/P2 + `Compress(C)` | `COMPRESSION_SPECIFIC_REFORMULATION` | **Yes — build P0 + structural layer first** |
| C6 | WarmTier snapshot | `DOCUMENTED_ORIGINAL_FORMULA` (untested) | Concept only; not a shipped capability |
| D | ActionGate `D` decision invariance | reformulation on `DOCUMENTED_ORIGINAL_FORMULA` | **Yes — headline metric, with coverage caveat** |
| E | Combined importance `Iᵢ` | `PROPOSED_LEARNED_EXTENSION` | P1/P2 ranker after operators exist |

## Load-bearing conclusions

1. **SCC entropy sign is `(1−Eᵢ)`** (high entropy penalized) — settled from source; the lone
   `γ·Eᵢ` is a docstring typo (`image_gen/config.py:203`). Code/spec weight mismatch
   (`0.3/0.3/0.2/0.2` vs `0.30/0.25/0.25/0.20`) is unresolved and must be pinned before use.
2. **"USE" as an implemented text-graph coupling does not exist.** Every implemented USE/phase
   formula is over neural/signal phases; applying phase to text is a category error the task
   itself forbids. The useful USE-inspired idea (`R_USE` relation recall) is a *new*
   reformulation needing its own extractor and incremental test — not reuse of the patent.
3. **KVPro "int4_protected" = generic asymmetric group-INT4 + static top-4% max-abs
   outlier-channel sidecar.** No per-element mask, no error-bound optimization, no `B_P` solver;
   WarmTier is hardware-untested with a `NotImplementedError` live backend. Reuse is a *design
   analogy* (protect-small / compress-bulk), never INT4 arithmetic reuse, and magnitude selection
   must not be used to pick semantic protected units.
4. **The one exactly-measurable differentiator is ActionGate decision invariance `D(C_orig)=D(C_comp)`**,
   valid only on an eval set seeded to perturb the 24 envelope fields.
5. **No experiment is authorized by this document.** Per task §6, SCC/USE/protected-context
   experiments must wait until this audit is committed. Next step is preregistration of the
   deterministic-structural + P0 layer (the only layer with `Recall(P0)=1` by construction) and
   the `Δ_SCC` / USE incremental tests, each with a BCVF-style kill criterion.

---

*Scope: formula recovery and eligibility only. No results are reported; none were run. Every
"eligible" verdict is a gate to *test*, not a claim of advantage.*
