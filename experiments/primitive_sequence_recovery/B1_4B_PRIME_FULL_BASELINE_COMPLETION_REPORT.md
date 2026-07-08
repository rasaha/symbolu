# B1.4b′ — Full-Baseline Completion Report

**Status:** Methodological-closure step (docs + adapter). **Not a signal rescue.** No real full-baseline
evidence run. No new evidence freeze. No decoder trained/scored on real McRae Y for a full-baseline run.
**The prior screening result remains `NULL_RETURN_BOTTOM` and is not reinterpreted.** Original B1.4b remains
blocked. Track B remains blocked. **Structure, not validated meaning.**

Prior run: `880ad1a`. Scorer/adapter update: this commit.

---

## 1. Purpose

Complete the missing covariate/baseline handling so a *future* full-baseline B1.4b′ closure run can include the
entire baseline suite. This is **cleanup after a flat null**, not an attempt to find signal. The screening run
already returned a flat null across every arm; completing the suite only makes the eventual package
methodologically complete — it cannot and will not turn a null into a positive.

## 2. Current null result (recorded, unchanged)

Screening terminal label: **`NULL_RETURN_BOTTOM`**. Arm scores (real McRae Y, 521×242, concept-level CV):
`A_F3_REAL 0.0522`, `B_PHONOLOGY_PLAIN 0.0548`, `C 0.0535`, `D 0.0492`, `E 0.0511`, `F 0.0583`, `G 0.0483`,
`I 0.0690`; `H` pending. **All at chance.** This result stands as-is.

## 3. `G_LENGTH_FREQUENCY` status — ✅ WIRED

- **KF and BNC are present** in the private McRae `CONCS_brm.txt` (columns `KF`, `BNC`, plus `Familiarity`,
  `Length_Phonemes`, `Length_Syllables`) — verified.
- **Normalization:** frequency = `log1p(KF)` (BNC fallback if KF missing); syllable length attached as a
  secondary covariate. Implemented in `b1_4b_prime_covariates.build_records` (adapter).
- **Missing values:** none expected over the 521 retained concepts (all present in CONCS); a missing KF falls
  back to BNC, and a concept with neither simply omits `freq` (would surface, not silently default).
- **Fully wired:** yes. The screening run already scored `G_LENGTH_FREQUENCY` (0.0483) using McRae `KF`; the
  adapter makes this the canonical, testable path. **Not a blocker.**

## 4. `H_SENTIMENT_LEXICON` status — ⛔ PENDING SOURCE

- **Approved sentiment/affect source available?** **No.** Checked: none in the operator uploads, none in the
  repo (the only `vad` matches are unrelated Vivado TCL scripts), and outbound fetch is blocked (403). McRae
  itself provides **no** sentiment.
- **Source name/version/license/provenance:** none — nothing to record.
- **Coverage over the 521 concepts:** 0 (no source).
- **Normalization / missing-value rules:** defined in the adapter for *when* a source arrives (word→value
  loader for Warriner VAD `V.Mean.Sum` / NRC-VAD `valence` / a generic `word,value` file; lowercase match on
  the tag-stripped concept; concepts not covered simply omit `sentiment`), but **inactive** with no source.
- **Decision:** `H_SENTIMENT_LEXICON_PENDING_SOURCE`. **No sentiment scores were fabricated.**

**Exactly what is needed to unblock H:** an operator-provided, **license-clear** affect lexicon —
**Warriner et al. (2013) VAD** (valence column `V.Mean.Sum`) or **NRC-VAD** (valence) — placed at a private
path and passed via `--sentiment` to the future full-baseline driver. The adapter will then attach sentiment to
covered concepts; full coverage of the 521 concepts activates `H`.

## 5. Full-baseline mode

Implemented in `b1_4b_prime_scorer.py`:

- **All arms active** only when every required baseline (including `H_SENTIMENT_LEXICON`) is present.
- **`L1_L2_L3_ATTRIBUTE_SIGNAL` is possible ONLY in full-baseline mode** (`score_run_full_baseline`) — and only
  when the suite is complete. Screening mode still cannot emit it.
- **Full-baseline mode is BLOCKED if `H` is pending:** `full_baseline_readiness()` returns
  `B1_4B_PRIME_FULL_BASELINES_BLOCKED_H_SENTIMENT`, and `score_run_full_baseline()` emits **no label** (and
  never a positive) while blocked — it directs the operator to screening mode instead.
- **No real full-baseline run is performed here.**

## 6. Tests (added/updated)

In `test_b1_4b_prime_scorer.py` (now 23/23):

- `G` present when the frequency covariate is supplied; not pending.
- full-baseline **blocked without sentiment** (H pending → no label, `signal_possible=False`).
- full-baseline **ready with sentiment** (synthetic-covariate path) → `SIGNAL` reachable *only* there.
- `H` remains **visibly pending** when no source is supplied.
- **screening mode still works** with `H` pending.
- covariate adapter wires KF/BNC frequency and **strictly** loads a supplied sentiment lexicon (returns `None`
  for a missing/absent source — no fabrication).
- guard: no covariate/lexicon/raw files are tracked.
- no real evidence run occurs in any test.

## 7. Readiness label

**`B1_4B_PRIME_FULL_BASELINES_BLOCKED_H_SENTIMENT`.**

`G_LENGTH_FREQUENCY` is wired (KF/BNC in hand). `H_SENTIMENT_LEXICON` has no approved source, so the full
baseline suite is incomplete and full-baseline mode is blocked. (Not `..._READY`: H unsourced. Not
`..._BLOCKED_G_FREQUENCY`: G is wired. Not `..._INCONCLUSIVE`: the blocker is specific.)

## 8. Validation (run)

- Scorer tests **23/23**; screening-driver tests **10/10**; Y-prep tests **7/7**; Stage A′ tests **11/11**.
- Raw McRae / private Y / lexicon files: **untracked** (verified).
- Frozen Stage A / `symbolu_neural` and Stage A′ code: **untouched** (verified).

## 9. Final report

- **Files modified/created:** `b1_4b_prime_scorer.py` (full-baseline mode + readiness),
  `test_b1_4b_prime_scorer.py` (+6 tests → 23), `b1_4b_prime_covariates.py` (new versioned adapter), this
  report.
- **Baseline readiness label:** `B1_4B_PRIME_FULL_BASELINES_BLOCKED_H_SENTIMENT`.
- **Test results:** 23/23 · 10/10 · 7/7 · 11/11.
- **Source/provenance status:** `G` = McRae KF/BNC (in hand); `H` = **no approved source** (Warriner/NRC
  needed, operator-provided, license-clear).
- **No real full-baseline evidence run performed.** No new evidence freeze.
- **No raw McRae data / private Y / lexicon committed.**
- **Prior `NULL_RETURN_BOTTOM` not reinterpreted;** no semantic success, no `L1_L2_L3_ATTRIBUTE_SIGNAL`, no
  `ONTOLOGICAL_SIGNAL`.
- **Original B1.4b and Track B remain blocked.**

---

> B1.4b′ full-baseline completion step finished. Prior screening result remains NULL_RETURN_BOTTOM. No real
> full-baseline evidence run performed. No semantic success claimed. Original B1.4b remains blocked. Track B
> remains blocked. Structure, not validated meaning.
