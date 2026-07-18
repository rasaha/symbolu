> **SUPERSEDED by `docs/STL_CSR_REFACTOR_PLAN.md`** (canonical, with corrected naming: state_bhava / phoneme_bhava / vritti_consonant / context r_ctx / semantic / resonance). Kept for history.

# CSR = Context × Semantic × Resonance — Supervised Probe Plan (PRE-REGISTERED)

> Representation/probe track only. Read-only diagnostics; **no** generation/attention/mid-layer
> injection, **no** governance/trust code. Conceptual frame locked with the user (4 answers below).
> Falsification-first. Builds on `docs/CSR_AUDIT.md` (integrity: "CSR" is overloaded; only the token
> scorer #1 + the model-independent varna basis are trained/available here).

## 0. Conceptual frame (locked)

**STL — temporal law of meaning evolution:** `Signal → Transformation → Laya`. *Out of scope for
this probe* (static features only; ΔBhava already shown ≈dead). STL is the future track.

**CSR — per-step coherence = `Context × Semantic × Resonance`** (meaning formation, NOT pairwise word
matching — the latter is what the existing code accidentally implemented):
- **C = Context** — current latent meaning field. **Tensor: `r_ctx` (16D)** = `context_proj([hidden;
  state_32d])` from the trained CSR token scorer (#1).
- **S = Semantic** — referential meaning. **Tensor: pooled hidden state** (and, separately, the
  learned `state[0:12]` "state-Bhava" summary + 32D state / O_tok).
- **R = Resonance** — Bhava coherence from Sanskrit phonemes = **Bhava(vowels) × Vritti(consonants)**.
  Text-derived, model-independent.

**Two-Bhava resolution (locked — "Separate roles"):** `state[0:12]` ("state-Bhava", the AUROC-0.82
learned hidden summary) is a **Semantic/Context** feature. The **phoneme-Bhava** (vowels) is the
**Resonance** feature. They are never merged under one "Bhava" label.

## 1. The question this probe answers

> Does **Resonance** (Sanskrit-phoneme Bhava×Vritti) add generation-quality signal **beyond
> Semantic + Context** — i.e. beyond what the transformer's hidden state and trained context already
> encode? Or is the phoneme resonance redundant?

Continue CG-representation work **only** if Resonance is **complementary** (adds over Semantic+Context
and/or over hidden_only with a significant paired delta). Park otherwise. Beating chance alone, or
hidden alone predicting correctness, is **not** sufficient.

## 2. Feature groups (separated by C/S/R role)

| Group | Role | Source | Dim | Availability |
|-------|------|--------|-----|--------------|
| `semantic_hidden` | S | pooled final hidden (the referential baseline / control) | 4096 (PCA'd) | have it |
| `state_bhava` | S | `state[0:12]` (+entropy) — learned hidden summary | 13 | have it |
| `cg_state_32d` | S | full 32D state | 32 | have it |
| `context_csr` | C | `context_proj([hidden; state])` (r_ctx) | 16 | needs csr_scorer #1 in ckpt |
| `resonance_combined` | R | 12D varna affinity (vowels+consonants merged) | 12 | text-derived (provider/varna) |
| `resonance_vowel` | R | vowel→Bhava cognitive-mode histogram | ~10 | text-derived (varna_mapping) |
| `resonance_consonant` | R | consonant→Vritti motion histogram | ~N | text-derived (varna_mapping) |
| `delta_bhava_only` | — | ΔBhava (≈0, dead) — reported for completeness | 13 | have it |

Resonance extracted **both** combined and vowel/consonant-split (locked answer). Resonance is
**model-independent** (function of the input text), so it is available even though CSR #2/#3 are
untrained. `context_csr` is gated on the checkpoint containing `csr_scorer.context_proj` → else
`feature_unavailable`. Unavailable parts are recorded, never fabricated.

Combos: `S+C` (hidden+context), `S+R` (hidden+resonance), `C+R`, `S+C+R` (full CSR),
`semantic_plus_context_plus_resonance` vs `semantic_plus_context` is the **decisive** pair.

## 3. Fair controls
Per-group PCA (in-fold) on the high-dim **hidden** so it cannot swamp the low-dim Context/Resonance.
AUROC primary (imbalance-robust) + bootstrap CI. Paired deltas vs `hidden_only`, vs `semantic+context`,
vs each part. Hewitt–Liang selectivity. Same balanced graded-difficulty `correctness` labels.

## 4. Report must answer
1. Does Resonance alone beat chance? 2. Does each Resonance part (vowel / consonant) beat chance?
3. Does Context (r_ctx) add over Semantic(hidden)? 4. Does Resonance add over Semantic+Context?
5. Does S+C+R beat hidden_only? 6. Is Resonance redundant with hidden? 7. Is state-Bhava redundant
with hidden (already measured: yes)?

## 5. Decision categories (pre-registered)

```
NO_SIGNAL                semantic, context, resonance all ~chance
SEMANTIC_ONLY            hidden(semantic) decodes; context & resonance add nothing over it
CONTEXT_ADDS_NOT_RESONANCE  context adds over semantic; resonance still adds nothing
RESONANCE_REDUNDANT      resonance decodable but S+C+R does not beat S+C
RESONANCE_COMPLEMENTARY  S+C+R beats S+C (significant paired delta) — Resonance adds
RESONANCE_STRONG         RESONANCE_COMPLEMENTARY AND S+C+R beats hidden_only (significant)
INSUFFICIENT_DATA        too few examples/classes or unstable CI
```

**CONTINUE** only on `RESONANCE_COMPLEMENTARY` or `RESONANCE_STRONG`. (This realizes the user's rule:
continue only if the combination adds complementary signal neither hidden nor the parts already have.)
Park on everything else.

## 6. Known limitations (pre-stated)
- `context_csr` is a trained projection of `[hidden; state]` → partly *is* hidden; the fair test is
  whether **Resonance** adds over it, not whether context decodes.
- `resonance` quality depends on G2P coverage (CMUdict/g2p_en vs char-fallback) — recorded in metadata.
- Resonance is text-derived: it can only carry signal if the *Sanskrit-phoneme structure of the prompt
  text* correlates with the model getting the answer right — a strong, falsifiable prior.
- Probe = correlation; generation path already parked, so a positive result informs only a future
  *readout* direction (and an STL temporal study), not the inert wrapper.
