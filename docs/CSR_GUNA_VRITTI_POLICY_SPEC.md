# CSR Guna/Vritti Symbolic Policy Layer — SPECIFICATION

> **Status: SPECIFICATION / DESIGN — NOT yet implemented.** Documents how Guna and Vritti are to be used
> as **deterministic symbolic control variables** over the already-validated C×R×S wrapper + Phase 3
> audit — **not** as decoded hidden-state vectors. This spec asserts no new empirical claim; each
> component below carries an explicit **validation status**. Nothing here changes Phase 1–3 or runtime
> until separately built and validated. Bhava stays out of runtime.

## 0. One line
`CSR_policy = Π(MATCH, Vritti_mode, Guna_quality, [hidden_risk?], audit_trace)` — Vritti is the
*movement* detector, Guna the *quality/stability* detector, C×R×S the *semantic-frame* controller,
Bhava is **not** a runtime control signal.

## 1. Why symbolic, not hidden-state (ties to Phase 4 results)
Phase 4 tested whether Bhava/Guna/Vritti are cleanly decodable from hidden states and got **multiply-
confirmed negatives**: Stage-B2 (supervised object-mode directions) collapsed and added nothing over
hidden-only; Phase 4D (Guna/Vritti-residual) hit definitional leakage (the audit's drift taxonomy *is*
the "Vritti" layer) and added nothing (`RESULTS_PHASE4_STAGEB2.md`, `RESULTS_PHASE4D.md`). The honest
conclusion: **do not depend on isolable hidden vectors.** This spec therefore defines Guna/Vritti as
**deterministic symbolic registers derived from the validated Phase 3 audit**, which is exactly where
the signal already lives.

## 2. Architecture
```
User query
  → C×R×S frame selection            (VALIDATED, frozen — Phase 1)
  → framed prompt + LLM answer       (VALIDATED — Phase 2/2B)
  → Phase 3 answer audit             (VALIDATED — deterministic findings)
  → Vritti_mode  (movement)          (NEW: relabels/groups audit findings)
  → Guna_quality (quality/stability) (NEW: partly audit-derived, partly new detectors)
  → CSR_policy   (answer / tighten / rewrite / escalate)   (NEW: extends existing rewrite gate)
  → final answer
```

## 3. Validation-status legend (read before trusting any row below)
- **[V] Validated** — implemented and tested in this repo today.
- **[D] Derivable** — a deterministic relabel/grouping of [V] outputs; low-risk, not yet wired.
- **[N] New detector needed** — requires a new deterministic detector; UNvalidated until built + tested.
- **[X] Experimental** — correlational, model-dependent, heavy; gated, not part of the deterministic core.
- **[P] Patent-described / future** — appears in patent text; NOT implemented or validated in this repo.

## 4. Vritti registry — "how the answer is moving"
Vritti is a deterministic function of the Phase 3 audit `finding_types` (the validated detectors):
`('frame_compliant','primary_frame_missing','secondary_promoted_to_primary','rejected_domain_promoted',
'rejected_domain_mentioned_as_refutation','alternate_true_sense_allowed','phoneme_overreach_claim',
'factuality_suspected','answer_too_generic')` plus `is_meta_parrot`.

| Vritti mode | source (audit finding) | status |
|---|---|---|
| `primary_frame_stable` | `frame_compliant` (audit passed) | **[D]** |
| `secondary_promoted` | `secondary_promoted_to_primary` | **[D]** |
| `rejected_domain_drift` | `rejected_domain_promoted` | **[D]** |
| `primary_frame_missing` | `primary_frame_missing` | **[D]** |
| `frame_parroting` | `is_meta_parrot` (⚠ detector over-fires, 64% — needs tightening) | **[N]** (fix detector) |
| `generic_escape` | `answer_too_generic` | **[D]** |
| `phoneme_overreach` | `phoneme_overreach_claim` | **[D]** |
| `associative_jump` / `domain_jump` / `over_expansion` | — (no detector today) | **[N]** |

Vritti is intended to drive: rewrite triggers, secondary-frame demotion, domain-jump penalties,
retrieval/rerank filtering, and audit finding categories. **Most Vritti modes are [D]** — a renaming of
findings the frozen auditor already emits.

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

## 6. CSR policy layer
**Do NOT** compute `CSR = isolated Bhava + isolated Vritti + isolated Guna`. Use a policy function over
the validated frame + diagnostics:
```
CSR_policy = Π(MATCH, Vritti_mode, Guna_quality, [hidden_risk], audit_trace)
```
Practical deterministic scoring form (weights `w*` and thresholds `τ*` are **to be tuned and
PRE-REGISTERED before any "improves outcomes" claim** — currently unset):
```
policy_risk = w1·(1 − MATCH_primary) + w2·vritti_drift + w3·guna_instability
            + w4·hidden_risk        + w5·audit_severity
action:
  policy_risk < τ_answer    → answer normally
  policy_risk < τ_rewrite   → answer with tighter frame
  policy_risk < τ_escalate  → rewrite / rerank
  else                      → ask clarifying question / escalate
```
Deterministic policy hooks (extend the existing Phase 3 `needs_rewrite` gate; **[D]/[N]**):
```
vritti == rejected_domain_drift  → rewrite_with_primary_frame()         # [D]
vritti == secondary_promoted     → demote_secondary_frame()             # [D]
guna   == generic_low_signal     → ask_for_specificity_or_rewrite()     # [D]
guna   == overconfident AND csr_alignment_low → add_caution_and_audit() # [N] (needs overconfidence detector)
```
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
1. **P-A [D]:** `vritti.py` + `guna.py` registries that map the **existing** audit findings →
   Vritti_mode / Guna_quality (pure relabel; unit-tested against `answer_audit` outputs). No behavior
   change — diagnostic only.
2. **P-B [D]:** `csr_policy.py` deterministic policy over `(MATCH, Vritti_mode, Guna_quality,
   audit_trace)` that reproduces and then extends the current `needs_rewrite` gate. Off by default;
   opt-in flag; A/B against the Phase 3 audit so it never regresses the validated behavior.
3. **P-C [N]:** new Guna detectors (clarity/specificity/overconfidence/hedging) + fixed `frame_parroting`
   detector, each with its own held-out validation before entering policy.
4. **Pre-registration required** before any claim that the policy *improves* answers: define the metric,
   the control (current audit), and the gate — exactly as Phase 2B/4 were gated.
5. `hidden_risk` **[X]** remains optional/off until separately justified.

## 10. Boundaries & patent-safe positioning
- **Valid framing:** *Guna and Vritti are symbolic control variables the wrapper uses to modulate
  retrieval, framing, reranking, tone, audit, and rewrite policy. They are not asserted to be directly
  separable hidden-state entities. Bhava remains an interpretive latent disposition unless separately
  validated.* (Claims scoping is a matter for patent counsel; this spec is engineering-only.)
- **Do NOT claim:** consciousness; Bhava proven/runtime-active; hidden-state CSR active; the patent
  symbolic engine is implemented; causal generation control; cross-model generalization.
- **Unchanged invariants:** Phase 1 scorer/thresholds frozen; Phase 2 prompt, rubric_v2, Phase 3 audit
  rules unchanged; no model weights/hidden-states/logits modified; Bhava out of runtime.
