# B1.4b′ — Screening-Run Operator Commands + Executed Status

**Status:** Command document **+ executed run record** (docs-only). The gated **screening** run was executed on
the real McRae `Y` under explicit session authorization. **Screening mode only — `L1_L2_L3_ATTRIBUTE_SIGNAL`
disabled by construction.** No full evidence-certification run. **No raw McRae data / private Y / declaration /
run output committed.** Original B1.4b remains blocked. Track B remains blocked. **Structure, not validated
meaning.**

Driver commit `f788ea2`; scorer `92fbae9`; Y-prep `23968c4`; Stage A′ harness `8d4b097`.

---

## 1. Purpose

Document the exact screening-run command sequence and record the executed outcome. Screening mode compares the
candidate `A_F3_REAL` (Stage A′ operator-interaction features) against phonology/order/relabel controls to
predict the independent McRae attribute `Y`. It **cannot** emit a positive; the sentiment baseline `H` is a
pending source, so "beats all baselines" cannot be established.

## 2. Exact command sequence

```bash
# 1. checkout + verify commits
git checkout claude/symbolu-adversarial-eval-zevb4h && git pull
for c in f788ea2 92fbae9 23968c4 8d4b097; do git merge-base --is-ancestor $c HEAD && echo "OK $c"; done
cd experiments/primitive_sequence_recovery
python3 -c "import numpy; print(numpy.__version__)"          # CPU-only; no GPU/RunPod

# 3. regenerate private Y from the licensed McRae files (private dir)
python3 b1_4b_prime_prepare_mcrae_y.py --source-dir <PRIVATE_MCRAE_DIR>

# 5. tests
python3 test_run_b1_4b_prime_screening.py     # 10/10
python3 test_b1_4b_prime_scorer.py            # 17/17
python3 test_stage_a_prime_coverage.py        # 11/11
python3 test_b1_4b_prime_prepare_mcrae_y.py   # 7/7

# 6. manifest hash -> declaration (operator; untracked)
MAN=frozen/b1_4b_prime_mcrae_y_prep_manifest.json
MAN_SHA=$(python3 -c "import hashlib;print(hashlib.sha256(open('$MAN','rb').read()).hexdigest())")

# 8. gated screening run
mkdir -p run_out
python3 run_b1_4b_prime_screening.py --mode screening \
    --source-dir <PRIVATE_MCRAE_DIR> \
    --private-dir frozen/private_mcrae \
    --manifest   frozen/b1_4b_prime_mcrae_y_prep_manifest.json \
    --decl       frozen/private_mcrae/b1_4b_prime_EVIDENCE_FREEZE_DECLARED.json \
    --out        run_out/b1_4b_prime_screening_report.json
```

## 3. Private McRae file placement

`<PRIVATE_MCRAE_DIR>` (outside git) holds the licensed files: `CONCS_brm.txt`,
`CONCS_FEATS_concstats_brm.txt`, `FEATS_brm.txt`, `READ_ME.txt`, `ReadMe_Terms_of_Use.txt`. Never `git add`.

## 4. Y-prep command

`python3 b1_4b_prime_prepare_mcrae_y.py --source-dir <PRIVATE_MCRAE_DIR>` → `B1_4B_PRIME_Y_PREP_READY`,
retained **521**, features **242**, private Y written to git-ignored `frozen/private_mcrae/`.

## 5. Hash / manifest verification

The regenerated manifest was **byte-identical** to the committed one (derived concept-list / attribute-list /
`y_matrix_sha256` reproduce). `y_matrix_shape = [521, 242]`.

## 6. Test sweep (executed)

`10/10` · `17/17` · `11/11` · `7/7` — all green.

## 7. Evidence-freeze declaration schema (operator; **untracked**)

Path: `frozen/private_mcrae/b1_4b_prime_EVIDENCE_FREEZE_DECLARED.json`

```json
{
  "artifact": "b1_4b_prime_EVIDENCE_FREEZE_DECLARED",
  "evidence_freeze_declared": true,
  "mode": "screening",
  "manifest_sha256": "<sha256 of frozen/b1_4b_prime_mcrae_y_prep_manifest.json>",
  "declared_by": "<operator>",
  "declared_at_utc": "<YYYY-MM-DDTHH:MM:SSZ>",
  "attestation": "Screening run only; SIGNAL disabled; sentiment baseline pending; no positive claim."
}
```
For this executed run `manifest_sha256 = e6ab56291dcb9611580efb2d76526165ff4b41eaab8a4fa170302376c81c7069`.
The file is git-ignored and was **not** committed.

## 8. Screening-run command

See §2 step 8. The driver verified the freeze gate, built Stage A′ records for the 521 concepts, wired McRae
`KF` as the `G` frequency covariate (sentiment absent → `H` pending), scored all arms at matched capacity, and
emitted a screening terminal label.

## 9. Output paths

| Path | Tracked? |
|---|---|
| `run_out/b1_4b_prime_screening_report.json` | **No** (git-ignored) — derived scores/counts only |
| `frozen/private_mcrae/mcrae_y_matrix.npz` | **No** (git-ignored) |
| `frozen/private_mcrae/b1_4b_prime_EVIDENCE_FREEZE_DECLARED.json` | **No** (git-ignored) |

## 10. Interpretation rules

- Report the label verbatim; do not upgrade a null.
- `NULL_RETURN_BOTTOM` = no arm predicts `Y` above chance.
- `F_COLLAPSES_TO_PHONOLOGY` = phonology matches/beats `A_F3_REAL` (both above chance).
- `INCONCLUSIVE_SCREENING_POSITIVE_NEEDS_FULL_BASELINES` = `A` led the present controls, but **not** a signal.
- `L1_L2_L3_ATTRIBUTE_SIGNAL` is **impossible** here.

## 11. No-positive-claim warning

Screening mode cannot and did not claim `L1_L2_L3_ATTRIBUTE_SIGNAL`, `ONTOLOGICAL_SIGNAL`, or any semantic
success.

## 12. Terms-of-Use / no-raw-data warning

McRae norms used under non-commercial research/education terms with citation (McRae, Cree, Seidenberg &
McNorgan, 2005 + Psychonomic Web Archive norms). Raw files, the private Y, the declaration, and the run report
are **not** committed. This document holds only **derived scores/counts**.

## 13. Final executed status

**EXECUTED — screening mode. Terminal label: `NULL_RETURN_BOTTOM`.**

Arm CV scores (real McRae `Y`, 521 concepts × 242 features; concept-level 4-fold ridge; `strong` threshold =
chance+margin = 0.35):

| Arm | Role | CV score |
|---|---|---|
| **A_F3_REAL** | candidate (F-3 interaction) | **0.0522** |
| B_PHONOLOGY_PLAIN | primary control | 0.0548 |
| C_PHONOLOGY_SIMILARITY | control | 0.0535 |
| D_BAG_OF_PHONEMES | co-primary control | 0.0492 |
| E_SHUFFLED_ORDER_F3 | co-primary control | 0.0511 |
| F_RANDOM_RELABEL_F3 | co-primary control | 0.0583 |
| G_LENGTH_FREQUENCY | control (KF wired) | 0.0483 |
| I_NULL_CHANCE | null | 0.0690 |
| H_SENTIMENT_LEXICON | control | **BASELINE_PENDING_SOURCE** |

**Reading (as-is, no spin):** every arm sits at ~0.05 CV correlation — **all at chance** (≪ 0.35). No
representation, including the candidate `A_F3_REAL` **and** the phonology baselines, linearly predicts the
independent McRae attribute norms above chance under concept-level cross-validation. The candidate F-3 (0.0522)
is not distinguishable from phonology (0.0548) or from any control; all are null. This is a **flat null** —
even stronger than the anticipated `F_COLLAPSES_TO_PHONOLOGY` (which would require phonology to carry signal and
beat F-3). It is consistent with, and reinforces, the standing negative priors (B1.1 `RANDOM_OR_SCRAMBLED_MATCHES`;
scrambled ≈ real ~0.967; sound-over-meaning). **`H_SENTIMENT_LEXICON` remained pending; positive signal was
disabled and none was claimable; no raw data was committed.**

Confirmations:
- Screening executed: **yes**; full evidence-certification: **no**.
- Positive signal possible: **no** (disabled by construction; result was not even positive-leaning).
- Semantic success claimed: **no**.
- Raw McRae data / private Y / declaration / run report committed: **no**.
- Frozen Stage A / Stage A′ / scorer / driver modified: **no**.
- Original B1.4b and Track B: **blocked**.

---

> B1.4b′ screening commands documented and screening run executed in screening mode only. Positive signal
> disabled. No full evidence-certification run performed. No raw McRae data committed. Original B1.4b remains
> blocked. Track B remains blocked. Structure, not validated meaning.
