# CSR Guna/Vritti Symbolic Policy Layer — SPECIFICATION

> **Status: SPECIFICATION / DESIGN — NOT yet implemented.** Documents how Guna and Vritti are to be used
> as **deterministic symbolic control variables** over the already-validated C×R×S wrapper + Phase 3
> audit — **not** as decoded hidden-state vectors. This spec asserts no new empirical claim; each
> component below carries an explicit **validation status**. Nothing here changes Phase 1–3 or runtime
> until separately built and validated. Bhava stays out of runtime.

## 0. One line
`CSR_policy = Π(MATCH, TrajectoryMode, Guna_quality, [hidden_risk?], audit_trace)` — **`TrajectoryMode`
(a.k.a. `DerivedVrittiTrajectory`) is the audit-derived *movement* diagnostic** (NOT canonical Vritti),
Guna the *quality/stability* detector, C×R×S the *semantic-frame* controller. The canonical five-state
`p_v` and Bhava are **not** runtime control signals.

## 1. Why symbolic, not hidden-state (ties to Phase 4 results)
Phase 4 tested whether Bhava/Guna/Vritti are cleanly decodable from hidden states and got **multiply-
confirmed negatives**: Stage-B2 (supervised object-mode directions) collapsed and added nothing over
hidden-only; Phase 4D (Guna/Vritti-residual) hit definitional leakage (the audit's drift taxonomy *is*
the "Vritti" layer) and added nothing (`RESULTS_PHASE4_STAGEB2.md`, `RESULTS_PHASE4D.md`). The honest
conclusion: **do not depend on isolable hidden vectors.** This spec therefore defines Guna/Vritti as
**deterministic symbolic registers derived from the validated Phase 3 audit**, which is exactly where
the signal already lives.

## 2. Architecture (immediate product path — derived trajectory, NOT canonical p_v)
```
User query
  → C×R×S frame selection                 (VALIDATED, frozen — Phase 1)
  → framed prompt + LLM answer            (VALIDATED — Phase 2/2B)
  → Phase 3 answer audit                  (VALIDATED — deterministic findings)
  → DerivedVrittiTrajectory (TrajectoryMode)  (NEW [D]: relabels audit findings — NOT five-state p_v)
  → Guna_quality (quality/stability)      (NEW: partly [D] audit-derived, partly [N] new detectors)
  → CSR_policy   (answer / tighten / rewrite / escalate)   (NEW: extends existing rewrite gate)
  → final answer
```
This is explicitly `C×R×S → answer → audit → derived-trajectory + Guna diagnostics → deterministic
policy`. It is **NOT** `C×R×S → canonical five-state p_v runtime control`. The canonical `p_v` (§4.1) and
its `φ_t`/relevance consumers are a separate future track (§4.4), not in this path.

## 3. Validation-status legend (read before trusting any row below)
- **[V] Validated** — implemented and tested in this repo today.
- **[D] Derivable** — a deterministic relabel/grouping of [V] outputs; low-risk, not yet wired.
- **[N] New detector needed** — requires a new deterministic detector; UNvalidated until built + tested.
- **[X] Experimental** — correlational, model-dependent, heavy; gated, not part of the deterministic core.
- **[P] Patent-described / future** — appears in patent text; NOT implemented or validated in this repo.

## 4. Vritti — the FIVE cognitive states (canonical) + a derived movement layer
There are **two distinct things** that must not be conflated:

### 4.1 Canonical Vritti = the five cognitive states (Yoga Sūtra 1.6; patent `p_v`)
Vritti proper is a **distribution `p_v` over five cognitive states**, not a set of drift labels. It is
the `p_v[v]` used by the patent's template-fit `φ_t(t|p_v)` and relevance score.

```
V = {Pramāṇa, Viparyaya, Vikalpa, Nidrā, Smṛti}
  = {Evidence,  Error,    Imagination, Latency, Memory}
p_v = [p_evidence, p_error, p_imagination, p_latency, p_memory]   # sums to 1
```

| state (Sanskrit) | English | operational reading in the answer-audit context | candidate deterministic proxy | status |
|---|---|---|---|---|
| Pramāṇa | Evidence / valid cognition | grounded, factual, stays on the C×R×S primary frame | `frame_compliant ∧ factuality_preserved` | **[N]** proxy / **[P]** canonical |
| Viparyaya | Error / misperception | false claim or rejected-domain assertion | `factuality_suspected ∨ rejected_domain_promoted` | **[N]/[P]** |
| Vikalpa | Imagination / conceptual-only (verbal construct, no object) | frame-label parroting / contentless abstraction | `is_meta_parrot ∨ answer_too_generic(conceptual)` | **[N]/[P]** |
| Nidrā | Latency / inertia (absence) | non-answer, empty, generic escape, refusal | `answer_too_generic(low-content)` | **[N]/[P]** |
| Smṛti | Memory / recall | repetition/retrieval of supplied material | `must_include` verbatim recall | **[N]/[P]** |

**Status is [P]/[N], NOT [V]/[D]:** the patent computes `p_v` via a syllable→softmax
`p_v(v|σ,c)=softmax_v(W_v·features(σ,c))` — **[P], not implemented**. A *deterministic audit-derived
proxy distribution* over the five states is **[N] (new, unvalidated)** — the audit findings only loosely
and partially cover the five, and the mapping above is interpretive. **Do not claim the five Vrittis are
decoded** from anything today.

### 4.2 Patent template-fit `φ_t` (reference, [P], not implemented)
```
φ_t(t | p_v) = softmax_t( β · [ w_t^Evidence·p_v[Evidence] + w_t^Imagination·p_v[Imagination]
                              + w_t^Error·p_v[Error] + w_t^Latency·p_v[Latency]
                              + w_t^Memory·p_v[Memory] ] )
```
Older 3-state form uses `{Pramāṇa, Vikalpa, Viparyaya}`. This `φ_t` and the relevance score that consumes
it (§8) are **patent-scope, not built here**.

### 4.3 `DerivedVrittiTrajectory` (`TrajectoryMode`) — the RUNTIME movement layer (NOT canonical p_v)
**This is the layer the product uses today.** It is an **audit-derived movement/trajectory diagnostic**
— *how the answer moved relative to the C×R×S frame* — and is a **DIFFERENT object from the five-state
`p_v`** (§4.1). It deliberately does **not** carry the Sanskrit names (Pramāṇa/Viparyaya/…), precisely
because the audit→five-state mapping is unvalidated. Canonical name for code/enums:
**`DerivedVrittiTrajectory`** (the layer) / **`TrajectoryMode`** (the per-finding flag).

It is **multi-label** (an answer can be both `secondary_promoted` and `frame_parroting`); represent it
as the *set* of active `TrajectoryMode` flags, not a single mode.

| `TrajectoryMode` flag | source (audit finding) | status |
|---|---|---|
| `primary_frame_stable` | `frame_compliant` | **[D]** |
| `secondary_promoted` | `secondary_promoted_to_primary` | **[D]** |
| `rejected_domain_drift` | `rejected_domain_promoted` | **[D]** |
| `primary_frame_missing` | `primary_frame_missing` | **[D]** |
| `frame_parroting` | `is_meta_parrot` (⚠ over-fires ~64% — needs tightening) | **[N]** |
| `generic_escape` | `answer_too_generic` | **[D]** |
| `phoneme_overreach` | `phoneme_overreach_claim` | **[D]** |
| `associative_jump` / `domain_jump` / `over_expansion` | — (no detector today) | **[N]** |

The trajectory layer is **[D]** (relabels validated findings) and drives the deterministic policy hooks
(§6). It is NOT canonical Vritti and makes no claim about the five cognitive states.

### 4.4 Canonical five-state `p_v` — SEPARATE FUTURE TRACK (not in runtime)
The canonical five-state `p_v` (§4.1) and its consumers `φ_t(t|p_v)` / relevance score are **out of the
runtime product** until a future, independently pre-registered effort: (1) pre-register a `p_v`
estimator; (2) define proxy labels for the five states carefully; (3) test separability, entropy, and
incremental value over the trajectory layer (same strict gate as Phase 4); (4) only then consider
feeding `φ_t`/relevance. Until that passes, `p_v` is **[P]/[N]** and never a product control signal.

## 5. Guna registry — "quality of expression"
| Guna quality | source | status |
|---|---|---|
| `generic_low_signal` | `answer_too_generic` | **[D]** |
| `ungrounded_factuality` | `factuality_suspected` | **[D]** |
| `parroting` | `is_meta_parrot` (needs fix) | **[N]** |
| `clear_stable` / `specific_grounded` | — (no detector) | **[N]** |
| `noisy_unstable` / `overconfident` / `hedged_uncertain` | — (no detector) | **[N]** |

**Guna is mostly [N]:** only generic/factuality/parroting exist today; clarity, specificity,
overconfidence, hedging, and noise require **new deterministic detectors** (surface/tone heuristics) and
must be validated before use. Do not assert Guna tone control works until those detectors exist and are
tested.

## 5.1 Guna representation provenance & selection rationale (neutral record)
The codebase computes "Guna" **four different ways**. This subsection records them and the locked
runtime selection so no one later wires the wrong form into CSR.

| form | where (evidence) | representation | distribution? | `H_G` definable? | runtime status |
|---|---|---|---|---|---|
| **A. symbolic / audit-derived** | `csr_match_filter/guna.py` (this layer); `phase4d_residual_bhava` `guna_label` | discrete multi-label flags from Phase 3 audit findings | n/a | n/a | **CSR runtime** ([D]/[N]) |
| B. sigmoid 6-D slice | `losses/kosha_gyroscope.py:2329` `GUNA_SLICE=slice(22,28)`; `conscious_generation/token_ontology.py:93` `sigmoid(raw[22:28])`; `jepa/state_projector.py:197` | 6 independent [0,1] dims of the learned 32-D state | **NO** (does not sum to 1) | **not well-defined** | symbolu_training telemetry / probe |
| C. softmax 3-D | `conscious_generation/governance/bliss_gate.py:124` `softmax(guna_proj(guna_6d))` | distribution over Sattva/Rajas/Tamas | **YES** (simplex) | **yes** | symbolu_training governance (generation-active) |
| D. CG-entropy | `signal_gov/diagnostics/d5_entropy_def.py` | scalar entropy folded into `cg_entropy` | derived | it *is* the entropy | offline diagnostic (D5 flags `CG_ENTROPY_DEGENERATE` risk) |

**Selection decision (locked):**
1. **CSR runtime uses A (symbolic / audit-derived) ONLY** — deterministic, model-agnostic, boundary-safe,
   Phase-3-audit-compatible, no hidden-state or generation-active wiring.
2. **Softmax 3-D (C) remains the canonical FUTURE `p_g` form** — it is the correct theory object for
   Sattva/Rajas/Tamas (a simplex), supports a proper `H_G`, and belongs to the patent entropy-feedback
   engine. It is **not** wired into CSR until independently validated (a separate estimator track, same
   bar as the five-state `p_v` future track §4.4).
3. **Do NOT use the sigmoid 6-D slice (B) directly as `p_g`** — it is not a distribution, does not sum to
   1, and `H_G` is undefined on it unless projected/normalized (which is exactly what C's `guna_proj`
   does).
4. **P-A Guna is NOT canonical Guna.** It is **`GunaQualityDiagnostic`**, an audit-derived symbolic
   quality layer. Canonical `p_g` is reserved for the later estimator track.
5. **P-B evaluation stays honest:** test whether the CSR policy using symbolic diagnostics beats the
   current Phase 3 `needs_rewrite` gate, with `hidden_risk_weight = 0`, `canonical_p_g_weight = 0`, and
   `new_Guna_detector_weight = 0` until each is separately validated.

**Intra-CSR note:** even within form A there are two proxies — `guna.py` (P-A) = `{generic_low_signal,
parroting}` with factuality moved to `audit_severity` for non-overlap; `phase4d` `guna_label =
answer_too_generic ∨ factuality_suspected`. **P-B uses the P-A definition** (factuality is severity, not
Guna).

## 6. CSR policy layer
**Do NOT** compute `CSR = isolated Bhava + isolated Vritti + isolated Guna`. Use a policy function over
the validated frame + diagnostics:
```
CSR_policy = Π(MATCH, Vritti_mode, Guna_quality, [hidden_risk], audit_trace)
```
Practical deterministic scoring form (weights `w*` and thresholds `τ*` are **to be tuned and
PRE-REGISTERED before any "improves outcomes" claim** — currently unset):
```
policy_risk = w1·(1 − MATCH_primary) + w2·trajectory_drift + w3·guna_instability
            + w4·hidden_risk        + w5·audit_severity
action:
  policy_risk < τ_answer    → answer normally
  policy_risk < τ_rewrite   → answer with tighter frame
  policy_risk < τ_escalate  → rewrite / rerank
  else                      → ask clarifying question / escalate
```
**⚠ Collinearity / double-counting caveat (learned from Phase 4D).** `trajectory_drift`, `audit_severity`,
and `(1 − MATCH_primary)` are **not independent** — `trajectory_drift` is *derived from* the same audit
findings that define `audit_severity`, and frame drift lowers MATCH alignment. Summing them with free
weights double-counts one signal (the same nesting that made Phase 4D leak). Therefore: define the terms
to be **non-overlapping** (e.g., `audit_severity` = critical/factuality findings only; `trajectory_drift`
= frame-movement findings only), and the **near-term policy must be shown to BEAT the current Phase 3
`needs_rewrite` gate** under a pre-registered test before claiming added value — most of `CSR_policy`
today is a *repackaging* of the existing audit decision, and the only genuinely NEW signal would come
from the [N] Guna detectors and the [X] `hidden_risk`, both unvalidated.

Deterministic policy hooks (extend the existing Phase 3 `needs_rewrite` gate; **[D]/[N]**):
```
rejected_domain_drift ∈ TrajectoryMode  → rewrite_with_primary_frame()        # [D]
secondary_promoted    ∈ TrajectoryMode  → demote_secondary_frame()            # [D]
guna == generic_low_signal             → ask_for_specificity_or_rewrite()    # [D]
guna == overconfident AND csr_alignment_low → add_caution_and_audit()         # [N] (needs detector)
```
Near-term, run the policy on **[D]/[V] terms only** (`MATCH`, `trajectory_drift`, `audit_severity`); keep
`w3` (Guna) and `w4` (hidden_risk) at **0** until the [N] detectors and [X] probe are separately validated.
**`hidden_risk` is [X] (experimental, optional):** the Stage-B1 finding — the pre-answer hidden state
predicts `frame_violation` (~0.76) and `rejected_domain_leak` (~0.83) within-arm — is real but
**correlational, model-specific, and requires running a probe at inference**. It is NOT part of the
deterministic product; if used, it is a gated add-on with `w4` defaulting to 0.

## 7. C×R×S facts to keep accurate (docs-vs-code reconciliation)
The implemented, **frozen** C×R×S differs from the simplified patent text — the spec uses the code:
- `MATCH = C · R · S`. **C** = ontological allowance (S-gated); **R** = **grouped** realization
  (group-aware, NOT flat 12D cosine — flat cosine was found non-discriminative and replaced); **S** =
  non-phonemic semantic coherence. The 12D profile is **phonemic** (from letters), **not a Bhava vector**.
- **Frozen thresholds (authoritative):** `reject_C = reject_S = 0.20`, `primary_match = 0.20`,
  `secondary_match = 0.05`. ⚠ The patent text's `MATCH ≥ 0.60` (primary) / `≥ 0.30` (secondary) are
  **NOT** the validated thresholds — do not use them; defer to the frozen scorer.

## 8. Relationship to the patent symbolic engine (reference only — [P], NOT implemented)
The patent describes a larger symbolic stack — syllable→Vṛtti softmax `p_v(v|σ,c)`, Guna `p_g`, 10-aspect
`p_w[a]`, dimensional/Vṛtti/Guna entropies `H_D/H_V/H_G`, entropy-feedback confidence `c=f(H_D,H_G)`,
the relevance score `rel_i = p_w[a]^θ₁·(Σ_v p_v[v]R[v,a])^θ₂·φ_d^θ₃·φ_t^θ₄·c^θ₅`, redundancy/domain-jump
penalties, and the stitching objective `S* = argmax Σ rel_i − λ₁·red − λ₂·dj`. **None of this is
implemented or validated in this repo.** It is recorded here as patent-scope/future architecture, not as
a description of current behavior. Any future build of it is a separate, independently-validated effort
with its own pre-registration; nothing in this spec claims those formulas work.

## 9. Implementation plan (phased; deterministic-first; each phase gated)
1. **P-A [D]:** `trajectory.py` (`DerivedVrittiTrajectory` / `TrajectoryMode`, multi-label) + `guna.py`
   registries that map the **existing** audit findings → trajectory flags / Guna_quality (pure relabel;
   unit-tested against `answer_audit` outputs). No behavior change — diagnostic only. **Canonical
   five-state `p_v` is explicitly NOT built here** (it is the §4.4 future track).
2. **P-B [D]:** `csr_policy.py` deterministic policy over `(MATCH, Vritti_mode, Guna_quality,
   audit_trace)` that reproduces and then extends the current `needs_rewrite` gate. Off by default;
   opt-in flag; A/B against the Phase 3 audit so it never regresses the validated behavior.
3. **P-C [N]:** new Guna detectors (clarity/specificity/overconfidence/hedging) + fixed `frame_parroting`
   detector, each with its own held-out validation before entering policy.
4. **Pre-registration required** before any claim that the policy *improves* answers: define the metric,
   the control (current audit), and the gate — exactly as Phase 2B/4 were gated.
5. `hidden_risk` **[X]** remains optional/off until separately justified.

## 10. Boundaries & patent-safe positioning
- **Naming boundary (explicit):** the runtime layer is **`DerivedVrittiTrajectory` / `TrajectoryMode`**
  — an audit-derived movement diagnostic. It is **not** canonical Vritti and is **not** the five-state
  `p_v`. The canonical five-state `p_v` (Pramāṇa/Viparyaya/Vikalpa/Nidrā/Smṛti), `φ_t`, and the relevance
  formula stay a **separate future track** (§4.4) and are never described as runtime-active.
- **Valid framing:** *Guna and the derived Vritti-trajectory are symbolic control variables the wrapper
  uses to modulate retrieval, framing, reranking, tone, audit, and rewrite policy. They are not asserted
  to be directly separable hidden-state entities, nor the canonical five-state p_v. Bhava remains an
  interpretive latent disposition unless separately validated.* (Claims scoping is for patent counsel;
  this spec is engineering-only.)
- **Do NOT claim:** consciousness; Bhava proven/runtime-active; hidden-state CSR active; the patent
  symbolic engine is implemented; causal generation control; cross-model generalization.
- **Unchanged invariants:** Phase 1 scorer/thresholds frozen; Phase 2 prompt, rubric_v2, Phase 3 audit
  rules unchanged; no model weights/hidden-states/logits modified; Bhava out of runtime.
