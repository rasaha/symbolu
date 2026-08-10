# ROADMAP_ADVERSARIAL_AUDIT

> **STATUS — Independent adversarial program review of `IMPLEMENTATION_ROADMAP.md`.**
> Documentation only. No code, no implementation, no Stage A change, no weakened caveat.
> Written as an NSF/DARPA-style review whose goal is the **fastest path to validation or
> termination**, not the defense of Symbol-U. Conclusions are critical by design.
> **Candidate hypothesis · Not validated · Stage A untouched · No Sanskrit privilege ·
> No semantic claims · Preserve ⊥.**
> **structure, not validated meaning.**

Phase↔Milestone map: Phase 0 = Milestone A, Phase 1 = Milestones B+C, Phase 2 = Milestone D,
Phase 3 = Milestone E, Phase 4 = Milestone F, Phase 5 = Milestone G.

## Bottom line

The roadmap's **principle** is correct (cheapest falsifier first; validation before
representation; terminal mass early). Its **execution** carries four load-bearing assumptions
that, if wrong, make the early kill tests either invalid or non-minimal:

1. **Substrate necessity.** The roadmap treats an atomic/additive null as a kill of L2. It is
   not. L2's distinctive claim is *non-additivity*; an atomic null is the **predicted** result
   under a pure-emergence theory (XOR/parity: zero first-order MI, full interaction MI). The
   flagship "cheapest kill test" (Phase 1) can falsify the *additive sound-symbolism* branch
   (S1/S2/Level-B) but **cannot logically falsify the order-dependent `F`**. Terminating on it
   is a **resource decision dressed as a logical gate**.
2. **The cheapest falsifier is not in the roadmap.** A desk-level **information-theoretic upper
   bound** on existing public norm datasets (is there *any* conditional MI between
   sound-symbolic dimensions and semantic observables beyond phonology?) is cheaper than Phase
   1, needs no new data, no harness, and no sourced `E`, and can terminate the program for
   free. "The price of one harness module" understates Phase 1's true cost (it also needs a
   sourced `E` — currently **unresolved** — a `Y` dataset, and a power-calibrated probe).
3. **"Validate operators" (Phase 2) is ill-posed as written.** Operators are defined only up to
   a gauge (similarity transform), so there is no gauge-invariant "the operators are correct"
   without a stated gauge-fixing. Estimating operators *from* behavior and then finding
   structure *in* the fit is near-circular: it risks validating "language has order effects"
   (trivially true) rather than "Symbol-U's specific assignment is right".
4. **The F-family and the probe≠decoder asymmetry form an unfalsifiability shield.** The
   admissible `F`-family is infinite and unenumerated; decoder failures never propagate up to
   kill L2 ("wrong decoder, `z` is fine"). Without a pre-registered finite `F`-ladder and a
   decoder stopping rule, Phases 3–4 are a degenerating research program (Lakatos): auxiliary
   failures absorb arbitrarily many nulls without termination.

**Unconditional probability of reaching validation given current evidence: ~1–3%. Expected
stopping point: Phase 0/1, most mass on a clean null at the upper-bound or atomic stage. That
is the correct, desirable outcome — but the roadmap should reach it ~one phase and several
months cheaper than currently planned.**

## 1. Hidden assumptions (per phase)

**Phase 0 — Foundations.** Assumes a gloss-independent `E` exists (status: **unresolved**;
only path-3 sound-symbolism admissible, no source identified). Assumes `Y` (lexical
meaning/VAD/embeddings) is the right observable for the theory's content — if `z` is a
non-lexical coordinate, `I(z;Y)≈0` while the theory is "true in its own terms" →
unfalsifiable/vacuous. Assumes the phonology baseline can be defined sharply enough to be
conditioned on (near-collinearity → unestimable, not null). Assumes anti-circularity = "no
gloss leakage", while the **binding** firewall is "E ≠ phonology", only partially handled.

**Phase 1 — Atomic falsifier.** **Substrate necessity** (atomic signal necessary for
compositional signal — false under emergence). Assumes a fixed **additive aggregation** `A(w)`,
which pre-judges against the non-additive theory. Assumes the probe has **known power** — no
calibration milestone exists, so a Phase-1 ⊥ is currently **uninterpretable**. Assumes MI
estimators are unbiased at the available N (they are positively biased at small N → false
positives).

**Phase 2 — Operator estimation + G1–G4.** Assumes operators are **identifiable** from
obtainable data (`n·d²` params; Hankel-rank identifiability needs many distinct sequences).
Assumes a **gauge fix** exists. Assumes behavior-estimated operators *are* the `E`-derived
operators — the **two routes are never reconciled**. Assumes G1–G4 can pass, though **G4
(factorization) is already NOT VALIDATED** on cleaner feature-derived operators → likely
inherited failure. Assumes order effects are attributable to Symbol-U vs generic composition
(G1 passes trivially: "dog bites man" ≠ "man bites dog") — no generic-composition baseline
specified. Assumes the phonology baseline is also applied to behavioral effects (order effects
can be phonotactic).

**Phase 3 — One admissible `F`.** Assumes the family is non-empty and a single member's failure
is informative, while "family exhausted" is operationally undefined → infinite researcher
degrees of freedom. Assumes the additive quantity tested in Phase 1 is the relevant substrate
for a possibly-nonlinear `F` (not necessarily).

**Phase 4 — Decoders.** Assumes the probe≠decoder asymmetry is a nicety, not an
unfalsifiability hatch (it is the hatch: no decoder failure can kill L2 as stated). Assumes the
nested ladder is the right complexity ordering and each level is separable given finite data.

**Phase 5 — Comparative.** Assumes the comparison is meaningful even if `z` is weak (comparing
two near-null signals is uninformative). Low risk — last.

## 2. Dependency analysis

**Is the graph correct?** Mostly, but it **encodes assumption #1**. The stated graph
A→B→C→D→E→F→G places the atomic `E`-test (B) before the operator/order test (D), with B
terminal. B tests *essences*; D tests *operators*. A pure-emergence theory (atomic null,
compositional signal) is **killed at B before D ever runs** — valid only if substrate-necessity
holds, the very assumption in question.

**Could a later phase invalidate an earlier one?** Yes — Phase 2 can reveal the
behavior-estimated operators bear no relation to the `E` used in Phase 1 (wrong object tested).
Yes — a nonlinear Phase 3 `F` makes the additive aggregate Phase 1 tested irrelevant, so a
Phase-1 null does not constrain Phase 3.

**Circular dependencies:** `E → stimuli → behavior → operators → "validate E"` if Phase 0's `E`
informs Phase 2 stimulus design (needs a firewall). The gloss firewall is stated; the
**phonology firewall is the binding one and is under-specified**.

**Reordering a systems engineer would make:** pull a **minimal order-effect existence test** out
of D into Phase 1 (distinguish "no signal anywhere" from "no *atomic* signal"); insert a **desk
upper-bound** computation before Phase 0 sourcing (doubles as source search + atomic
falsifier); insert **synthetic harness calibration** before any real Phase 1 run.

## 3. Cheapest falsifier per phase

| Phase | Cheapest experiment | Most expensive | Expected info gain | P(terminate here) |
|---|---|---|---|---|
| 0 | Desk: published norm set meets §5 *and* shows nonzero conditional MI on existing data | Commission new cross-ling norm collection | High | 0.4–0.6 |
| 1 | Existing public norm+semantic data → estimate `I(Y;E\|phonology)` upper bound (no new data) | Full S1/S2 human study (N≥120) | High | 0.6–0.75 (cond.) |
| 2 | Re-analyze existing order-sensitive corpora for order effects beyond phonotactics | New behavioral order-effect study | Medium | 0.4–0.6 |
| 3 | Fit cheapest non-additive `F`, probe | Full nested `F`-ladder model selection | Medium | 0.3–0.5 |
| 4 | Linear DBP decoder vs baselines | Full transformation-field decoder | Low–Medium | 0.3 |
| 5 | — | Cross-language / cross-modal | Low | n/a |

The single cheapest decisive test — the Phase-0/1 **upper bound on existing data** — is
currently **not a named milestone**. That is the roadmap's biggest efficiency miss.

## 4. Mathematical completeness

**Must be specified before implementation:** the **gauge group** of `(d, s₀, {Mσ}, {uᵢ})`
(else Phase 2 is ill-posed); **`d`**; the **`E → Mσ` map**; the **aggregation `A`** (additive
choice pre-judges the theory); **`Y`** operationalization and the **`I(·)` estimators**
(finite-N bias control); a **finite pre-registered `F`-ladder** (to make "family exhausted"
decidable).

**Can remain abstract:** decoders `D` (until Phase 4); latent geometry of `S` (until `F`
chosen); Phase-5 partitions.

**Hand-waved definitional gap:** the relationship between `E`-derived operators and
behavior-estimated operators (Phase 1 vs Phase 2 test different objects).

## 5. Failure analysis

| Phase fails | What is learned | Terminates? |
|---|---|---|
| 0 (no defensible `E`) | Theory cannot be tested non-circularly | **Whole program** — cheap, clean kill |
| 1 atomic null | Essences carry no *additive* signal beyond phonology — **does NOT falsify emergent L2** | Terminate **only** if substrate-necessity is pre-accepted as a *resource* rule; else trigger the order test |
| 2 operators don't validate | No order structure, or Symbol-U operators ≠ behavior; ambiguous given G4-NOT-VALIDATED | Terminates the operator-substrate branch; emergence-`F` may survive — roadmap's "terminal" is too strong given gauge gaps |
| 3 (every `F` fails) | Order-dependent representation carries no info beyond baselines | Terminates **L2** *iff* family was finite + pre-registered; as written (infinite), terminates nothing |
| 4 (every decoder fails) | No readout exposes `z` | Terminates **only the decoder branch** — the unfalsifiability hatch; L2 survives |
| 5 | Sanskrit not privileged | Refinement only |

Termination mass is *claimed* early but *leaks late*: Phases 3–4 can fail forever without
killing L2 unless a stopping rule is added.

## 6. Missing milestones (risk-reducing only, ranked)

1. **Synthetic harness calibration / null simulation** — HIGH value, near-zero cost, runnable
   in-sandbox (numpy). Planted signal must be detected; pure null must return ⊥; false-positive
   rate and minimum detectable effect recorded. Without it, every real ⊥ is uninterpretable and
   every positive is suspect. **Precedes any real Phase 1.**
2. **Information-theoretic upper bound on existing public data** — HIGH value, desk cost,
   terminal-capable. Doubles as the Phase-0 source search.
3. **Gauge / identifiability analysis** — HIGH value, before Phase 2; makes operator validation
   well-posed.
4. **Minimal order-effect existence test** — MEDIUM-HIGH; merge into Phase 1; neutralizes the
   substrate-necessity type-II error.
5. **Pre-registered finite `F`-ladder + decoder stopping rule** — HIGH value, before Phase 3;
   converts Phases 3–4 from unfalsifiable to falsifiable.
6. **Ablation / sensitivity** — MEDIUM; how conclusions move with `d`, the `E` values, the
   aggregation. Small budget once past Phase 1.

Observability is largely subsumed by the gauge analysis. Comparative/cross-modal upper bounds
belong in Phase 5.

## 7. Research efficiency

- **Minimum-cost? No** — it skips the cheapest falsifier (desk upper bound) and understates
  Phase 1 cost (E sourcing + Y data + probe calibration hidden inside "one harness module").
- **Shorten:** merge Phase 0 sourcing with the Phase 1 atomic test into one desk step ("find a
  norm set that meets §5 *and* shows nonzero conditional MI").
- **Postpone:** the human order-effect study (Phase 2) is correctly gated behind 0/1; also gate
  it behind synthetic-harness power confirmation.
- **Conditionally remove:** Phases 4–5 should be tagged "do not fund until L2 shows recoverable
  info with a pre-registered finite `F`-ladder".
- **Merge:** Phase 0 + cheap half of Phase 1; cheap half of Phase 2 (order-effect existence)
  forward into Phase 1.

## 8. Final evaluation

**Revised dependency graph (logical, not just cost-ordered):**
```
Phase 0′  Desk upper bound on EXISTING data  ──┐  (terminal: conditional MI ≈ 0 → STOP)
          + §5 source search (merged)          │
                    │ source found & MI>0       │
                    ▼                            │
Phase 0.5 Synthetic harness calibration ────────┘  (gate: probe power & FPR known, else STOP)
                    │
                    ▼
Phase 1′  Atomic E-test  ⊕  minimal order-effect existence test   (run together)
                    │   ├─ atomic & order both null → STOP (clean)
                    │   ├─ atomic null, order positive → continue to operator/order branch
                    │   ├─ atomic positive, order null → continue additive/essence branch only
                    │   └─ both positive → strongest continuation
                    ▼
Phase 2   Gauge/identifiability analysis  →  operator estimation  →  G1–G4
                    ▼
Phase 3   PRE-REGISTERED FINITE F-ladder  (gate: beats all baselines, else reject family → STOP)
                    ▼
Phase 4   Decoders  (stopping rule: K F×D failures → reject L2)
                    ▼
Phase 5   Comparative (only if z non-trivially recoverable)
```

**Critical path:** Phase 0′ → 0.5 → 1′. Everything decisive happens here, in-sandbox, with no
new human data.

**Expected stopping points (descending mass):** Phase 0′ upper bound ≈ 0; Phase 1′ atomic+order
null; Phase 0 no §5 source; Phase 2 operators don't validate (G4).

**Highest-risk assumptions:** substrate-necessity; `Y`=lexical meaning is the theory's
observable; a sound-symbolism source beats phonology at all; operators identifiable/gauge-
fixable; `F`-family finite/pre-registered.

**Highest-value experiments:** synthetic null/power calibration; existing-data conditional-MI
upper bound; merged atomic+order test.

**Survival probabilities (subjective, evidence-conditioned):**

| Phase | P(survive \| reached) |
|---|---|
| 0 — defensible §5 source exists | 0.40–0.55 |
| 1 — atomic (incl. order) beats phonology+baselines | 0.10–0.20 |
| 2 — operators validate non-circularly (incl. G4) | 0.20–0.35 |
| 3 — some pre-registered `F` beats baselines | 0.20–0.30 |
| 4 — a decoder beats baselines non-circularly | 0.30 |
| **Unconditional reach-validation** | **~1–3%** |

**Recommendation — next six months (no human studies, no `F`, no decoders):**
1. **Months 1–2, desk:** information-theoretic upper bound on existing public sound-symbolism +
   semantic datasets — any conditional MI beyond phonology? Pre-register the ⊥ threshold.
   Executes Phase-0 §5 source search and a free atomic falsifier. Most likely: terminate here.
2. **Months 1–2, in-sandbox (numpy):** build and calibrate the synthetic validation harness —
   planted-signal power and null false-positive rate; record minimum detectable effect.
3. **Pre-commit now** to the substrate-necessity question: does atomic null **terminate**
   (resource rule, stated as such) or **trigger** the order test (logical rule)? Stop calling an
   atomic null a logical falsification of L2.
4. **Before any Phase 2 spend:** complete gauge/identifiability analysis; reconcile `E`-route vs
   behavior-route operators. Confront G4's likely NOT-VALIDATED inheritance.
5. **Before any Phase 3 spend:** pre-register a finite `F`-ladder and a decoder stopping rule.

**Verdict:** A good falsification program with the right instincts but three structural defects
— a mislabeled atomic gate (resource decision as logic), a missing cheaper desk falsifier, and a
late-phase unfalsifiability shield. Fix those and the fastest path to a decision is ~3 months of
desk + synthetic work, most probably ending in an honest early termination — the program
succeeding, not failing.

---

> **structure, not validated meaning.**
