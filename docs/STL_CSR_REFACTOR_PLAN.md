# STL / CSR Conceptual Refactor + Static Probe Plan (PRE-REGISTERED)

> Conceptual + probe-wiring cleanup. **NOT** generation injection. No mid-layer/attention injection,
> no ΔBhava-wrapper revival, no trust/governance changes, no change to the ablation verdict logic
> (docs/reporting only). Supersedes `docs/BHAVA_CSR_PROBE_PLAN.md`. See `docs/CSR_AUDIT.md` for the
> "CSR is overloaded across ≥4 subsystems" integrity findings.

## Task 1 — Audit: where the layers collapse (exact locations)

| Finding | Location | What it is | Mismatch |
|---|---|---|---|
| Pairwise word-matching `C×R×S` | `primitives/crs_combined_scorer.py:7-17` | `C=Cognitive (Vritti×Kosha)`, `R=Resonance (phonemic varna, **combined**, delegates to CSRTokenScorer)`, `S=Semantic (Bhava ontology, "semantic firewall")` — token↔context **compatibility** gate | Word-MATCHING, not meaning-formation; **off by default** (`use_crs_combined_scorer=False`) → absent from ckpt |
| Vowels/consonants **merged** | `csr_phoneme_provider.py` `csr_affinity [B,T,12]`; `csr_scorer.py:52` `token_proj(12→16)` | 12D varna affinity merges vowels+consonants | Resonance not split into phoneme-Bhava(vowels) × Vritti(consonants) |
| "Bhava" overloaded | `state_projector` `state[0:12]` vs `varna_mapping.VOWEL_STATES` | learned hidden slice **and** vowel cognitive-mode both called "Bhava" | state-Bhava (Semantic/Context summary) ≠ phoneme-Bhava (Resonance) |
| Context not isolated | `csr_scorer.py:88` `context_proj([hidden; state_32d])→r_ctx(16)` | r_ctx exists, but 32D state mixes Bhava back in | Using 32D state as Context blurs C vs S vs R |
| "CSR" acronym overloaded | see `CSR_AUDIT.md §0` | ≥4 subsystems; only the token scorer (#1) trained here | naming corruption |

**Where each thing currently lives (answers to Task-1 items 1-7):**
1. Vowels-as-C: **not** as Context — the code puts vowels (with consonants) under **R** (varna affinity)
   and labels a *different* C = Cognitive(Vritti×Kosha). 2. Consonants-as-R: merged into the same 12D
   varna R, not a separate Vritti branch. 3. Semantic-as-S: the code's S = **Bhava ontology** identity
   (`crs_combined_scorer.py:9`), conflating Bhava with Semantic. 4. Exposed tensors: `state_bhava`
   (state[0:12]) ✔, `r_ctx`/context ✔ (in ckpt #1), `resonance_combined` ✔ (12D varna, text-derived),
   `phoneme_bhava`/`vritti_consonant` ✔ (derivable from `varna_mapping` VOWEL_STATES/VRITTI_LABELS),
   semantic referent ✔ (input embeddings / O_tok). 5. In Active-CG ckpt: `state_bhava`, `r_ctx`
   (csr_scorer.context_proj), O_tok/R_tok buffers — yes; CRS combined (#3) and spatial CSR (#2) — no.
   6. Implemented vs documented: token scorer #1 **implemented + trained**; CRS combined **implemented
   but off/untrained**; spatial CSR **implemented but untrained here**. 7. Pairwise matching vs
   meaning-formation: `crs_combined_scorer` and `csr_scorer.forward` are **pairwise** (context↔token
   compatibility), not meaning-formation support.

## Task 2 — Corrected hierarchy

### A. Current mismatch
Old/implemented: a pairwise `Match = C(Cognitive) × R(Resonance) × S(Semantic=Bhava)` compatibility
score. This collapses layers: it puts **Bhava under Semantic**, merges **vowels+consonants** into one
R, and is a **word-matching gate**, not a meaning-formation decomposition.

### B. Corrected hierarchy
```
STL  = Signal → Transformation → Laya            (temporal; DEFERRED — see §D)
CSR  = Context × Semantic × Resonance            (static; THIS probe)
Resonance = phoneme-Bhava(vowels) × Vritti(consonants)
```
- **Signal** = raw token/perception entering. **Transformation** = interpretation/association/context
  processing. **Laya** = absorption into coherent, stabilized meaning (**not** disappearance).

### C. Corrected feature roles (and exact names)
```
state_bhava       = state[0:12]  — learned hidden-state semantic/context summary (baseline)
state_32d         = full 32D CG state (Bhava+Kosha+Vritti+Guna+Reserved) — broader baseline
phoneme_bhava     = vowel → cognitive-mode profile        (Resonance part)
vritti_consonant  = consonant → motion-tendency profile   (Resonance part)
resonance_combined= phoneme_bhava × vritti / 12D varna affinity
context (r_ctx)   = context_proj([hidden; state_32d])      (Context — PRIMARY context var)
semantic          = referential embedding / ontology meaning (input embeddings; O_tok if present)
hidden            = pooled final hidden state              (generic strong baseline/control)
```
Context = `r_ctx` (NOT the 32D state, which re-mixes Bhava and blurs the decomposition).
Sanskrit phonemes belong under **Resonance**, never directly under Context or Semantic.

### D. Static probe scope (locked)
This task tests **static** `CSR = Context × Semantic × Resonance`. **STL temporal evolution is
deferred** — no ΔBhava, no state-change, no step-to-step deltas, no Signal→Transformation→Laya
sequence modeling as features (ΔBhava already shown ≈dead in the wrapper).

### E. Untouched
No generation/injection changes. No trust/governance changes. No mid-layer/attention changes. No
ΔBhava-wrapper revival. Ablation verdict logic unchanged (this is reporting/probe code only).

## Task 3/4 — Probe feature groups + report questions

Singles: `state_bhava_only`, `phoneme_bhava_only`, `vritti_consonant_only`, `resonance_combined`,
`context_r_ctx_only`, `semantic_only`, `hidden_only`, `state_32d`.
Resonance combos: `phoneme_bhava_plus_vritti`, `state_bhava_plus_resonance`.
CSR combos: `csr_static` (= context_r_ctx + semantic + resonance_combined), `state_bhava_plus_csr`,
`hidden_plus_state_bhava`, `hidden_plus_csr`, `hidden_plus_state_bhava_plus_csr`.

Per-component `feature_unavailable: {component, reason}` when a tensor path is missing — never faked.
Fair controls: per-group PCA (in-fold) on high-dim hidden/semantic so they cannot swamp the low-dim
Context/Resonance; AUROC primary + bootstrap CI; paired deltas vs hidden_only / vs csr parts / vs
state_bhava. Report answers Q1–Q10 (state-Bhava? phoneme-Bhava? vritti? resonance? context? semantic?
does CSR beat its parts? does state_bhava+CSR beat state_bhava? does hidden+state_bhava+CSR beat
hidden? does CSR add complementary signal beyond hidden?).

## Task 5 — Decision categories
```
NO_SIGNAL  STATE_BHAVA_ONLY_SIGNAL  RESONANCE_ONLY_SIGNAL  CONTEXT_ONLY_SIGNAL
SEMANTIC_ONLY_SIGNAL  CSR_REDUNDANT  CSR_COMPLEMENTARY  CSR_STRONG_SIGNAL
HIDDEN_ONLY_SIGNAL  INSUFFICIENT_DATA
```
- `CSR_COMPLEMENTARY`: static CSR (C+S+R) beats its best individual part (significant paired delta).
- `CSR_STRONG_SIGNAL`: `hidden + state_bhava + CSR` beats `hidden_only` (significant paired delta).
- **CONTINUE only on `CSR_COMPLEMENTARY` or `CSR_STRONG_SIGNAL`.** Park otherwise. Beating chance with
  one part, or hidden alone predicting correctness, is **not** sufficient.

## Known limitations
- `context_r_ctx` is a trained projection of `[hidden; state]` → partly *is* hidden; fair test =
  whether Resonance/CSR add *beyond* a PCA'd hidden baseline.
- `resonance`/`phoneme_bhava`/`vritti_consonant` are text-derived (G2P coverage caveat, recorded).
- Probe = correlation; the generation path is parked, so a positive result informs only a future
  *readout* + STL temporal track, not the inert wrapper.
