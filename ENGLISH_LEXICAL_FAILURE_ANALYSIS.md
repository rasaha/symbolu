# Failure Analysis — the English Lexical Semantic Hypothesis

> **Analysis only. No implementation code, no new mathematical model, no new dataset, no rescue
> attempt.** The objective is to isolate *which* assumption of the Symbol-U lexical-semantic
> hypothesis failed, and to delete from the research program every hypothesis that is no longer
> justified. Branch D.1 is treated as the current best evidence. Negative conclusions are stated
> without softening.

## 0. What was actually established (evidence base)

| Experiment | What it measured | Outcome (decisive numbers) |
|---|---|---|
| **Branch D** | `I(Y; phoneme-identity \| articulatory phonology)`, Y=Warriner VAD, linear/additive ridge, N=13383. DPI upper bound on any deterministic per-phoneme essence table. | Marginal raw positive: valence ΔR²=0.0067, partial r=0.082, perm p=0.005; dominance partial r=0.086; arousal null. Random-E control ≈0. → UPPER_BOUND_POSITIVE (marginal, 0.05–0.10 band). |
| **Branch D.1** | Same estimand + morphology/length deconfounding + rime-grouped (leakage-controlled) CV. | Positive vanishes. Decisive cell (valence, deconf+grouped): ΔR²=−0.0029, partial r=0.000, p=0.30. **Both** controls *individually* already kill it (deconf-only partial r 0.048 n.s.; grouped-only 0.036 n.s.). PHON→PHON+morph base R² jumps 0.0020→0.0349. → UPPER_BOUND_NULL_AFTER_CONTROLS. |
| **D₀′ / D₀′.1** | Gauge-invariant operator-algebra structural invariants; adversarial specificity vs 5 null ensembles. | Invariants (`algebra_dim=16`, `reachability=4`, `trace_order_frac=0`, …) are **generator-determined** (Burnside irreducibility; su(2)± 2-plane placement), provably **feature-blind**. F-sensitive magnitudes showed no significant specificity. → NOT SPECIFIC. |
| **B.0 / B.0.1 / B.0.2** | Synthetic-harness calibration of the probes. | Probes detect planted signal when present (incl. an operator/order regime that a *linear* probe provably **cannot** represent) and are null when absent. → instruments validated; a null is a real null, not an instrument failure. |

Two facts from this base govern the whole analysis:

- **(i)** Articulatory phonology explains almost none of the affective variance (PHON valence R²≈0.002). The thing that absorbed the Branch D increment was **morphology/length + rhyme-family leakage**, not phonology.
- **(ii)** The measuring instrument is sound (B.0). So the post-control zero is a genuine zero *within the linear/additive model class on English mature-lexicon words* — not a missed detection. It is silent, by construction, about nonlinear/order-dependent structure (B.0 proved the linear probe is blind to the operator regime).

---

## 1. Candidate-by-candidate evaluation

Legend: ✓ consistent / supports · ~ neutral · ✗ inconsistent / contradicts.

### A. The phoneme-level semantic signal never existed.
- Branch D: **✗ weakens.** A raw, reproducible marginal positive appeared (partial r 0.08, p=0.005). Something existed at the correlational level.
- Branch D.1: **~** residual → 0 after controls is consistent with A — but *equally* consistent with C (absorption). The mature-lexicon test cannot separate "nothing there" from "fully absorbed."
- D₀′: ~ (structural, silent on semantic existence).
- Calibration: ~ / mild support (probe sensitivity confirmed ⇒ the zero is real, not missed).
- Literature: **✗** documented small but real sound–meaning effects (Blasi et al. 2016 cross-linguistic; Sapir 1929 mil/mal; bouba/kiki) contradict a universal "never."
- **Rating: UNLIKELY.** The universal non-existence claim is contradicted by the raw signal and the literature, and is observationally degenerate with C on all reachable data.

### B. The signal exists but is entirely explained by articulatory phonology.
- Branch D: **✗ contradicts.** PHON valence R²≈0.002 — phonology predicts essentially nothing; the increment was measured *over* phonology.
- Branch D.1: **✗ contradicts.** What killed the increment was morphology/length (base R² 0.002→0.035) and rhyme-family grouping — not articulatory features.
- D₀′: ~. Calibration: ~.
- Literature: ~/✗ (phonology-encodes-meaning is not a sound-symbolism position).
- **Rating: RULED OUT.** Articulatory phonology is the one explanation the data directly exclude.

### C. The signal exists but is absorbed by morphology and lexical family structure.
- Branch D: **✓** a confounded-but-present pattern looks exactly like the raw marginal positive.
- Branch D.1: **✓✓ strongly supports.** Morphology/length deconfounding *and* rhyme-family-grouped CV each *independently* nullify the increment; the decisive cell is exactly zero. This is the textbook signature of confound absorption, not of nonexistence (which would not have produced the raw positive in the first place).
- D₀′: ~. Calibration: **✓** (probe works ⇒ disappearance is genuine absorption).
- Literature: **✓✓** phonaesthemes, shared etymology, and morphology are *the* known confounds in lexicon-level phonosemantics (Bergen 2004; Otis & Sagi).
- **Rating: SUPPORTED.** Best-supported explanation of the failure.

### D. The signal exists but is nonlinear, invisible to the additive linear probe.
- Branch D / D.1: **~** linear/additive by construction; cannot see a nonlinear signal. The DPI bound only constrains *linear/additive* essence aggregation.
- D₀′/D₀′.1: **✗ weakens** the operator-specific nonlinear form — its structural invariants are feature-blind (generator-determined).
- Calibration (B.0): **✓ confirms the blind spot is real** — a linear bigram probe provably cannot represent operator-order signal. So a genuinely nonlinear signal *would* be invisible here.
- Literature: ~ (positional/nonlinear effects exist but are not larger than linear ones).
- **Rating: WEAKENED.** Not ruled out — a real, demonstrated blind spot — but with **zero positive evidence** pointing into it. As stated it is an unfalsifiable escape hatch: it becomes scientific only if the nonlinear form is pre-specified and then tested. D is the linear-failure special case of G.

### E. The signal exists only outside English (Sanskrit-privilege).
- Branch D / D.1: **~** English-only; says nothing about other languages.
- D₀′ / calibration: ~ (language-independent).
- Literature: **✗ weakens** — the documented weak effects (Blasi et al. 2016) are *cross-linguistically universal and present in English too*; the "English-absent" shape is the wrong one. The Sanskrit-specific strong claim is untested.
- **Rating: WEAKENED.** Alive but unmotivated and partly contradicted; testing requires external multilingual data.

### F. The signal exists only in coined/non-lexical forms (pseudowords), not mature lexicons.
- Branch D: **✓** mature lexicon → weak/confounded, as predicted.
- Branch D.1: **✓ supports** — the mature-lexicon null is exactly F's prediction: the lexicon is *where the C-confounds live*. F is the complement of C (confounds present in lexicons ⇒ absent in pseudowords).
- D₀′ / calibration: ~.
- Literature: **✓✓ strongly supports** — the robust effects (bouba/kiki, mil/mal, McCormick/Glasgow size & shape ratings) are overwhelmingly *pseudoword* paradigms; mature-lexicon effects are weak and confounded.
- **Rating: SUPPORTED — but untested by us** (the pseudoword test is the data-blocked A′).

### G. The hypothesis is correct but requires a representation richer than deterministic per-phoneme mappings.
- Branch D / D.1: **~** bound out the per-phoneme deterministic (linear) form; this sets G up rather than refuting it.
- D₀′ / D₀′.1: **✗ weakens** the *specific* richer representation Symbol-U proposes (operator composition): its gauge-invariant structure is generator-determined and carries **no feature/meaning specificity**. The richness lives in the fixed so(4) generators, not in the phonosemantic features.
- Calibration: **~/✓** an order-aware probe *can* detect operator signal when planted — the instrument exists.
- Literature: ~ (no specific support for operator-algebraic semantic representations).
- **Rating: WEAKENED** (operator-specific form bordering UNLIKELY). G strictly contains D; both are untested escape hatches, and G carries *negative* structural evidence (D₀′.1) against its concrete proposed form.

### Summary table

| Hyp | Branch D | Branch D.1 | D₀′/.1 | Calibration | Literature | **Rating** |
|---|---|---|---|---|---|---|
| A never existed | weakens | neutral (≡C) | ~ | mild support | against | **UNLIKELY** |
| B phonology explains it | contradicts | contradicts | ~ | ~ | ~/against | **RULED OUT** |
| C morphology/family absorb | supports | **strongly supports** | ~ | supports | **strongly supports** | **SUPPORTED** |
| D nonlinear/invisible | neutral | neutral | weakens (operator form) | confirms blind spot | ~ | **WEAKENED** |
| E non-English/Sanskrit | neutral | neutral | ~ | weakens | weakens | **WEAKENED** |
| F pseudowords only | supports | **supports** | ~ | ~ | **strongly supports** | **SUPPORTED** |
| G richer representation | sets up | sets up | **weakens** | ~/feasible | ~ | **WEAKENED** |

---

## 2. Dependency graph of surviving hypotheses

Ruled out (B) and unlikely (A) are removed as standalone threads (see §5). Surviving: **C, F**
(supported) and **D/G, E** (weakened, untested). The structure collapses to a single crux.

```
                       Does a phoneme→meaning signal exist BEYOND lexical confounds?
                                              │
              ┌───────────────────────────────┴───────────────────────────────┐
              │  C and F are the SAME claim seen from two sides:               │
              │  "real but confound-absorbed in lexicons (C) ⇒ visible where  │
              │   confounds are absent, i.e. pseudowords (F)."                 │
              └───────────────────────────────┬───────────────────────────────┘
                                              │
                              CRUX TEST: pseudoword phonosemantics (A′-class)
                                              │
                 ┌─────────────────────────────┴─────────────────────────────┐
            POSITIVE                                                       NULL
   C+F supported; A refuted.                                  A becomes SUPPORTED; C's
   Effect is real but weak and                                "absorption" was vacuous
   confined to non-lexical forms.                             (nothing to absorb); F ruled out.
                 │                                                          │
                 │ (only if a linear pseudoword test is null               │
                 │  yet theory still predicts an effect)                   │
                 ▼                                                          ▼
        D / G (nonlinear / richer representation):                 program terminates on the
        the residual escape hatch. G's operator-                   lexical-semantic hypothesis
        specific form already weakened by D₀′.1;                   (negative result is the result).
        scientific ONLY if the nonlinear form is
        pre-specified before testing.

   E (non-English / Sanskrit) sits ORTHOGONAL to the whole tree: independent of the English
   crux, weakened by cross-linguistic universality, testable only with external multilingual data.
```

Key structural facts:
- **C and F are not independent hypotheses** — they are one claim ("real signal, masked by lexical confounds") evaluated in two regimes. Confirming F confirms C; a null in F demotes C to vacuity and promotes A.
- **A is downstream of F, not a parallel hypothesis.** On all *reachable* (mature-lexicon) data A and C are observationally identical; only the pseudoword regime distinguishes them. A therefore has no independent experiment.
- **D ⊂ G.** They are one residual "the model class is too poor" branch, reachable only after a linear pseudoword test fails.

---

## 3. Ranked experiments that could discriminate

1. **Pseudoword phonosemantic upper-bound test (A′-class).** The crux. Discriminates {C,F} vs A, and is the only experiment that can resurrect any positive form of the hypothesis. Same estimand/DPI logic as Branch D, applied to pseudoword rating norms (size/shape/affect) where morphology and etymology are absent by construction.
2. **Monomorphemic-subset re-analysis of the existing English data (sharpens C vs A).** Restrict Branch D/D.1 to morphologically simple, single-family words and re-run the *same* deconfound + grouped pipeline. If the null persists even where C's confounds are minimized, C is insufficient and weight shifts to A (within English). If a residual reappears, C is confirmed as the mechanism and F gains indirect support.
3. **Pre-specified nonlinear / positional probe on the existing data (tests D within English).** Onset/coda-positional or phoneme-pair (interaction) features, with the *same* morphology + rime-grouped controls. A null further constrains D inside the English mature lexicon (it cannot confirm D — only a positive could).
4. **Cross-linguistic test (tests E).** Sound-form × meaning-vector association across multiple languages with confound controls. Orthogonal to the English crux.
5. **Operator-representation *semantic* test (tests the surviving part of G).** Apply the operator construction to real words against a construct-aligned Y. The *structural* half is already done and came back feature-blind (D₀′.1), so this is the lowest-yield branch and partly pre-empted.

---

## 4. External-data vs immediately-executable

**Require external data (currently unreachable on the allowlist):**
- (1) Pseudoword norms — the crux. This is the data-blocked A′ (Glasgow/McCormick/C2-type size/shape/affect ratings per pseudoword). **Without this datum the surviving program cannot be confirmed, only further narrowed.**
- (4) Multilingual form×meaning data for E.
- (5) Construct-aligned semantic Y for the operator/G test.

**Executable immediately on already-reachable data (CMUdict / PanPhon / Warriner), no new code written here:**
- (2) Monomorphemic-subset re-analysis (reuses the Branch D.1 morphology tags and rime grouping).
- (3) Pre-specified nonlinear/positional probe.

Both immediately-executable experiments can only **tighten the bound toward A** (or, at most, re-expose a residual that still points to the data-blocked pseudoword test). Neither can rescue the hypothesis. The entire *confirmatory* power of the surviving program is gated on external pseudoword data.

---

## 5. Hypotheses that are now scientifically unnecessary

1. **B — RULED OUT.** Articulatory phonology explains essentially none of the variance (PHON R²≈0.002) and is not what absorbed the signal. No experiment in the program should target B.
2. **A — UNNECESSARY as a standalone hypothesis.** On every reachable (mature-lexicon) measurement A is observationally identical to C; it has no independent test of its own and is contradicted as a *universal* claim by the raw Branch D positive and the literature. A re-enters the program *only* as the specific outcome "pseudoword test (1) is also null." Until then it requires no separate experiment.
3. **The deterministic-per-phoneme × linear × English-mature-lexicon cell — EXHAUSTED.** Branch D + D.1 closed it. Any further English-lexicon linear probe of per-phoneme essence is unnecessary; it would only reproduce UPPER_BOUND_NULL_AFTER_CONTROLS.
4. **D and G — MERGE.** They are one residual "model class too poor" branch (D is the linear special case of G). Keeping them as two threads is unjustified; the operator-specific form already carries negative structural evidence (D₀′.1) and neither is scientific until a nonlinear form is pre-specified.

**Net simplification.** Seven candidates reduce to **one crux** — the pseudoword test (C≡F vs A) — plus **one orthogonal branch** (E, cross-linguistic) and **one merged residual escape hatch** (D/G), both gated on external data, and **two immediately-runnable English re-analyses** (monomorpheme subset; pre-specified nonlinear probe) that can only narrow toward A. B is eliminated; A and the deterministic-linear-English cell carry no independent experiment.

---

## 6. Bottom line

The English lexical-semantic test did not fail because the probe was weak (B.0 validates it) or because phonology pre-empted the signal (B is ruled out). It failed because **the only phoneme-level signal that appeared was, on direct test, entirely attributable to morphology and rhyme-family structure (C)** — the precise confound the sound-symbolism literature flags for mature lexicons. The honest consequence is that **the lexical-semantic hypothesis is not separately testable on reachable English data**: every remaining confirmatory experiment requires external pseudoword (or multilingual) norms that the environment cannot reach, and every immediately-runnable experiment can only push further toward the null. This does not validate Symbol-U, and it does not resurrect it; it removes four of seven hypotheses from active consideration and reduces the program to a single data-blocked crux.

> structure, not validated meaning.
