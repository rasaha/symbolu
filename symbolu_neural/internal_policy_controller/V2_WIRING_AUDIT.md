# v2 Internal Policy Controller — Logic & Wiring Audit

**Scope:** read-only structural audit (no quality evaluation, no redesign) to verify
the v2 pipeline actually tests the stated hypothesis *before* spending API credits.
All claims verified against the code + read-only stub/perturbation runs.

**Headline verdict:** the **execution flow is correctly wired stage-to-stage**
(stub trace below threads cleanly), **but the policy-translation layer
under-tests the hypothesis.** Of the 8 computed Symbol-U state fields, **only 2
(`guna`, `valence`) influence the policy at all.** `kosha`, `kosha_resonance`,
`pse_meaning`, `pse_resonance`, `valence_sign` have **zero** downstream influence;
`guna_resonance` is read but its branch is **dead** (threshold never reached);
**`aspect` is never computed**. So a real run would test *"does a (coarse-guna +
binary-valence) policy beat controls,"* **not** *"does the full Symbol-U ontology
drive useful policy."* **Recommend wiring fixes (or narrowing the claims) before
API spend.** No code changed (defects weaken, not invalidate, the run).

---

## 1. Execution flow — verified

Intended vs actual (from `pilot.run_quality` + stub trace §3):

```
Prompt ✅ → LLM Draft ✅ → compute_state(DRAFT) ✅ → translate(state) ✅
       → PolicySpec ✅ → revision prompt (policy.render()) ✅
       → LLM rewrite ✅ → Final ✅ → independent judge(prompt,draft,final) ✅
```

Every stage is executed and the right object is passed to the next. **One flow
divergence:** `pilot.structural_report` (the offline divergence numbers, incl. the
"0.583 relabel" headline) computes state **from the PROMPT**, while
`run_quality` correctly computes state **from the DRAFT**. The structural numbers
were therefore measured on a *different input* than the experiment uses (§5).

## 2. Field-influence test (perturb one state field → does the policy change?)

| state field | influences policy? | why |
|---|---|---|
| `guna` | ✅ INFLUENCES | drives tone, caution, directness, speculation |
| `valence` | ✅ INFLUENCES | drives caution, uncertainty, speculation |
| `vritti` | ⚠ only via `guna` | `translate()` never reads vritti directly; guna = lossy 5→3 collapse of vritti |
| `guna_resonance` | ❌ DEAD | read as `< 0.5`, but observed range **[0.713, 0.924]** → branch never fires |
| `kosha` | ❌ ZERO | computed, never read by `translate()` |
| `kosha_resonance` | ❌ ZERO | computed, never read |
| `pse_meaning` (131-d) | ❌ ZERO | computed (expensive), never read |
| `pse_resonance` | ❌ ZERO | computed, never read |
| `valence_sign` | ❌ ZERO | computed, never read |
| `aspect` | ❌ ABSENT | never computed into the state object at all |

Also: `policy.clarity` is **hard-coded `"high"`** in `translate()` → constant for
the Symbol-U arm (verified: clarity set across 12 prompts = `{"high"}`).
And `valence` only ever takes `{binding, mixed}` (never `liberating`) across the
prompt set, so the `liberating` handling is also effectively dead.

## 3. Stub execution trace (deterministic, no API)

```
1) PROMPT:  "My production database just got deleted and my boss is furious..."
2) DRAFT (stub): "[STUB DRAFT] Restart the service and check the config."
3) SYMBOL-U STATE (of the DRAFT):
     vritti_top=ACTIVATION  guna={sattva:.06, rajas:.60, tamas:.33}  guna_top=rajas
     kosha_top=pranamaya    guna_resonance=0.767   valence=binding
4) POLICY (arm=symbolu):
     tone="direct and energetic"  caution="high"  directness="high"
     clarity="high"  uncertainty="acknowledge uncertainty explicitly"
     speculation_reduction="high"
5) REVISION PROMPT: "PROMPT:…\nDRAFT:…\nRevise your draft to follow this response
     policy… - Tone: direct and energetic. - Caution: high. …Return only the revised answer."
6) FINAL (stub): "[STUB FINAL] Restart the service and check the config."
7) JUDGE OUTPUT (stub): {clarity:4,…,meaning_preservation:4,fluency:4,prefer_final:true}
```

Information flow is intact end-to-end. Note in step 4 that `kosha_top=pranamaya`
and the whole `kosha`/`pse` content **never appear** in step 5's revision prompt —
they are computed in step 3 and dropped.

## 4. Module-by-module audit

| module | status | notes |
|---|---|---|
| `data.py` (prompts) | ✅ Correct | 12 prompts + paraphrases + category; consumed. |
| `llm.py` | ✅ Correct | anthropic/mistral real; mock gated by `is_real`. No mock-in-production path. ⚠ judge-parse failure falls back to all-zeros silently. |
| `symbolu_state.py` | ⚠ Partially wired | Computes vritti(canonical)/guna(derived)/kosha(derived)/resonances/valence/pse. **Aspect never computed despite being claimed.** kosha/pse/valence_sign/kosha_resonance computed-but-unused. ⚠ `_valence` silently returns `("mixed",0.0)` on any exception. |
| `policy.translate()` | ⚠ Partially wired | Reads only guna, valence, guna_resonance(dead). clarity constant. Ignores kosha/aspect/pse/valence_sign and vritti-direct. |
| `policy.policy_for_arm()` + arms | ✅ Correct | 8 arms, modes {none, self_refine, policy} correct; relabel permutes guna *labels* (genuinely changes policy); shuffled uses neighbour-draft state; random/sentiment/nl distinct. |
| `judge.py` | ✅ Correct | independent rubric judge; no keyword markers / regex / oracle lexicon. ⚠ silent zero fallback. |
| `pilot.run_quality()` | ✅ Correct flow | draft→state(draft)→policy→rewrite→judge; refuses verdict under mock. |
| `pilot.structural_report()` | ⚠ Inconsistent | computes state from PROMPT, not DRAFT (mismatch vs the quality path). |
| `cli.py` / `tests/` | ✅ Correct | exercise both paths. |

## 5. Architectural inconsistencies

1. **Claim vs reality (most important).** Report/README say v2 "computes the **full**
   Symbol-U state … Vritti/Guna/Kosha/Aspect/Resonance/PSE" and uses it to drive
   policy. **In wiring, only `guna` + `valence` reach the policy.** Aspect is not
   even computed. This misrepresents what the experiment tests.
2. **Guna is not independent of Vritti.** `guna` is a deterministic 5→3 collapse of
   the vritti distribution (`_VRITTI_TO_GUNA`). So "Guna drives the policy" reduces
   to "a coarsened Vritti drives the policy" — one signal, not several.
3. **State-source mismatch.** Structural divergence (incl. the 0.583 relabel
   headline) is computed on **prompt**-states; the real experiment uses
   **draft**-states. The numbers are not measured on the experiment's actual inputs.
4. **Dead/degenerate branches.** `guna_resonance < 0.5` never fires (range
   0.71–0.92); `valence == "liberating"` never occurs; `clarity` is constant. These
   silently shrink the policy's effective degrees of freedom.
5. **Partial relabel control.** `_relabel_state` permutes only `guna` labels, not
   the valence categories the policy also consumes — so the "ontology relabel"
   control relabels only part of the consumed ontology.
6. **Silent fallbacks.** `_valence` (→"mixed") and `judge` (→all-zeros) swallow
   errors; a flaky API judge response would silently zero an arm and distort the
   comparison with no signal.

## 6. Unused / weakly-connected components

- **Zero downstream influence:** `kosha`, `kosha_resonance`, `pse_meaning`,
  `pse_resonance`, `valence_sign`, and (effectively) `guna_resonance`.
- **Claimed but absent:** `aspect`.
- **Constant, not state-driven:** `policy.clarity`.
- **Mediated only:** `vritti` (acts solely through the coarse `guna`).

## 7. End-to-end answers

- **If every module worked as intended, would it test the hypothesis?**
  It would test a **narrow** version — "does a policy driven by (coarse guna +
  binary valence) beat generic refinement / sentiment / random / shuffled /
  relabeled?" It would **not** test the advertised "full Symbol-U ontology
  (Vritti/Guna/Kosha/Aspect/Resonance/PSE) → policy," because 6 of 8 fields are inert.
- **Anything fundamentally missing before real API experiments?** Yes: the
  policy-translation layer must actually **consume** Kosha/Aspect/Resonance/PSE (or
  the claims must be narrowed to match), the dead branches recalibrated, and the
  structural/quality state source reconciled.
- **Where is the hypothesis unintentionally weakened?** Exactly at `translate()`:
  the "full state" is computed then discarded down to guna+valence. Paradoxically
  this could *flatter or flatten* Symbol-U depending on which way the unused signal
  would have pointed — either way the result wouldn't mean what the report says.

## 8. Recommended fixes before spending API credits

Priority order (do **not** run the paid eval until at least 1–4 are addressed):

1. **Make the state→policy wiring honest.** Either (a) extend `translate()` to
   consume Kosha, Aspect, Resonance, and (if claimed) PSE — each mapped to a policy
   axis — or (b) explicitly **narrow the report/README** to "guna+valence policy"
   and drop the unused fields from the state. Pick one; today's code claims (a) but
   does (b).
2. **Compute Aspect** (the `varna_lens → symbolu.ontology.phase4a.lookup` chain the
   audit found) if "Aspect" is to remain in the hypothesis; otherwise remove it
   from the provenance/claims.
3. **Fix dead branches.** Recalibrate `guna_resonance` threshold to its real range
   (or use a relative/percentile cut); make `clarity` state-driven or drop it as an
   axis; handle the never-seen `liberating` case or document its absence.
4. **Reconcile state source.** Compute `structural_report` divergence on
   **draft**-states (or relabel those numbers explicitly as prompt-state).
5. **Replace silent fallbacks** in `_valence` and `judge` with explicit
   error counters / retries so a bad judge response cannot silently zero an arm.
6. **Complete the relabel control** to permute every ontology category the policy
   consumes (guna *and* valence), so it is a full ontology-sensitivity test.

**Bottom line:** the plumbing is sound and the run will not crash — but as wired it
would spend credits measuring a much smaller claim than "Symbol-U." Fix the
translation-layer wiring (item 1) first; that single change determines whether the
API experiment tests the hypothesis you actually want to test.
