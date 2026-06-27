# v2 Audit (assumption-free) + v3 Fix Plan

Per instruction: audit v2 **as it exists, assuming nothing is correct**, then decide
patch-vs-v3 and fix. Extends `V2_WIRING_AUDIT.md` with deeper, assumption-free
findings. No API credits spent.

## 1. v2 wiring audit — what actually happens

Traced statically + with read-only stub/perturbation runs:

| stage | what is actually computed / consumed |
|---|---|
| draft | real LLM draft (mock when no key) ✅ |
| state | `compute_state(draft)`: vritti (canonical), guna (**derived, lossy**), kosha (derived), guna/kosha-resonance (canonical fn), valence (canonical, **real** — verified 11 analyze calls/0 exc), pse_meaning/pse_resonance (canonical-wrapped). **Aspect: NOT computed.** |
| → policy | `translate()` reads **only `guna`, `valence`, `guna_resonance`** |
| policy → rewrite | `policy.render()` text is embedded in the revision prompt ✅ |
| judge | sees prompt+draft+final, scores final on rubric + prefer_final ✅ |

**Effective signal reaching the policy = 2 bits:** `guna_top ∈ {rajas, tamas}`
(sattva unreachable) × `valence ∈ {binding, mixed}`. Result: **4 distinct policies
across 12 prompts.** Everything else computed is discarded.

## 2. Defect list (assumption-free)

**Critical (invalidate the stated hypothesis):**
- **D1 — Most of the "full state" is inert.** `kosha`, `kosha_resonance`,
  `pse_meaning`, `pse_resonance`, `valence_sign` have **zero** downstream influence
  (perturbation test). The report claims the full ontology drives policy; only
  guna+valence do.
- **D2 — `aspect` is never computed** despite being claimed in the state/report.
- **D3 — `sattva` is structurally unreachable.** Guna derivation maps sattva ←
  RELEASE-vritti only (≈0 in English) → sattva mass 0.03–0.09, never top → the
  "calm/clear" tone never fires; guna degenerates to a **noisy rajas/tamas
  near-tie** (0.495 vs 0.477) → the dominant driver is coin-flip-unstable.
- **D4 — Dead branches.** `guna_resonance < 0.5` never fires (range 0.71–0.92);
  `valence == "liberating"` never occurs; `clarity` is a hard-coded constant.
- **D5 — `guna` is not independent of `vritti`** (deterministic 5→3 collapse), so
  "Guna drives policy" = "coarsened Vritti drives policy"; one signal, not several.

**Serious (distort results / claims):**
- **D6 — State-source mismatch.** `structural_report` (incl. the "0.583 relabel"
  headline) uses **prompt**-states; the experiment uses **draft**-states.
- **D7 — Silent fallbacks.** `_valence`→`("mixed",0)` and `judge`→all-zeros swallow
  errors; a flaky judge response would silently zero an arm.
- **D8 — Partial relabel control.** `_relabel_state` permutes only `guna` labels,
  not the `valence` categories the policy also consumes → incomplete ontology test.

**Verified genuinely-working (not defects):** pipeline flow (stub trace), vritti
canonical + normalized (no degenerate states), valence really computed, judge
rubric independent (no keyword markers / regex / oracle lexicon), 8 arms + modes,
mock gated by `is_real` (no mock-in-production).

## 3. Can v2 be trusted? — **No.**

v2 will run without crashing, but it tests a **2-bit (rajas/tamas)×(binding/mixed)
policy**, not the full Symbol-U ontology, and its single dominant driver
(`guna_top`) is a noise-sensitive near-tie with one of three categories
unreachable. **Spending API credits on v2 would measure a misrepresented, degenerate
hypothesis.** v2 is trustworthy only as a documented record of what not to do.

## 4. Required v3 fixes

1. **Every state variable must reach a distinct policy axis** (enforced by a
   field-influence self-test that fails CI if any claimed field has zero influence):
   - vritti distribution → directness/energy (use directly, not only via guna)
   - guna → tone, with **sattva made reachable** (drive sattva from *balance*, i.e.
     high `guna_resonance`, not RELEASE-only mass)
   - kosha → reasoning depth / abstraction
   - aspect (phase4a distortion vs sublimate) → caution
   - resonance → uncertainty/confidence (relative threshold, not the dead `<0.5`)
   - valence → speculation/escalation handling
2. **Compute Aspect** via `varna_lens → symbolu.ontology.phase4a.lookup`.
3. **Kill dead branches:** relative/percentile thresholds; ensure all tone values
   and `liberating` (or drop it) are reachable; make `clarity` state-driven.
4. **Use draft-states everywhere** (reconcile structural vs quality).
5. **Remove silent fallbacks** — surface/count errors; no all-zero judge default.
6. **Complete the relabel control** — permute every ontology category the policy
   consumes (guna + valence + any added).
7. Keep the **sound v2 harness** (llm/judge/data) reused, not rewritten.

## 5. Recommendation: **create v3, keep v2 intact**

The defects are concentrated in two modules (state derivation + `translate`) but are
**deep** (structural sattva-unreachability, full-state non-consumption, dead
branches) — a surgical patch would churn the same files heavily and erase the
audited-defective record. **Build `v2/` → new `v3/`** that **reuses v2's verified
harness** (`llm.py`, `judge.py`, `data.py`) and **replaces** the state + policy +
pilot with corrected versions, plus a **field-influence self-test** so this class of
defect cannot silently recur. v2 stays as the documented baseline (nothing deleted).

**Status:** implementing v3 now; the paid run stays blocked until v3 passes the
field-influence self-test (every claimed Symbol-U variable provably influences the
policy) and the dead-branch checks.
