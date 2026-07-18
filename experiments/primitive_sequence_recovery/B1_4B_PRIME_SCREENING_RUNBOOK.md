# B1.4b′ — Phonology-Primary Screening Run — Operator Runbook

**Status:** Operator runbook (docs-only). **Nothing here is executed by the assistant.** No evidence freeze is
declared, no decoder is trained on real McRae Y, and no real run is performed by the assistant.
**Screening mode: `L1_L2_L3_ATTRIBUTE_SIGNAL` is disabled by construction.** Raw McRae data / private Y are
**never committed**. Original B1.4b remains blocked. Track B remains blocked. **Structure, not validated
meaning.**

Driver: `run_b1_4b_prime_screening.py` · mock tests: `test_run_b1_4b_prime_screening.py` (**10/10 PASS**).

---

## 0. What this run is (and is not)

- **Is:** a phonology-primary *screening* run — the candidate `A_F3_REAL` (Stage A′ operator-interaction
  features) competes against phonology/order/relabel controls to predict the McRae `Y`.
- **Is NOT:** a positive-certification run. The sentiment/lexicon baseline `H_SENTIMENT_LEXICON` has no approved
  source, so "beats all baselines" cannot be established. **The driver cannot emit
  `L1_L2_L3_ATTRIBUTE_SIGNAL`.**
- **No GPU / no RunPod required** — the scorer is numpy ridge regression (521×242). Any CPU host with the
  licensed McRae files works; RunPod is optional (clean isolated environment only).

Allowed terminal labels: `F_COLLAPSES_TO_PHONOLOGY`, `BAG_OR_SHUFFLE_EXPLAINS`, `RANDOM_RELABEL_EXPLAINS`,
`NULL_RETURN_BOTTOM`, `INCONCLUSIVE`, `INCONCLUSIVE_SCREENING_POSITIVE_NEEDS_FULL_BASELINES`, plus
`Y_NOT_INDEPENDENT` / `DECODER_LEAKAGE_INVALID`.

---

## 1. Host prep

```bash
git clone <repo-url> symbolu && cd symbolu
git checkout claude/symbolu-adversarial-eval-zevb4h
cd experiments/primitive_sequence_recovery
python3 -c "import numpy; print('numpy', numpy.__version__)"      # CPU-only; no torch needed
```

## 2. Place the licensed McRae files (PRIVATE — never committed)

Download the McRae (2005) norms under their Terms of Use and place the tab-delimited files in a **private**
directory (outside git, or under the git-ignored `frozen/private_mcrae/`):
`CONCS_brm.txt`, `CONCS_FEATS_concstats_brm.txt`, `FEATS_brm.txt`, `READ_ME.txt`, `ReadMe_Terms_of_Use.txt`.
**Do not `git add` them.**

## 3. Regenerate the private Y + verify hashes match the manifest

```bash
python3 b1_4b_prime_prepare_mcrae_y.py --source-dir <PRIVATE_MCRAE_DIR>
# writes frozen/private_mcrae/mcrae_y_matrix.npz (git-ignored) + tracked manifest/exclusions.
# Confirm the manifest y_matrix_sha256 / private_source_file_sha256 match the committed manifest:
git diff --stat experiments/primitive_sequence_recovery/frozen/b1_4b_prime_mcrae_y_prep_manifest.json
# (no change = the hashes reproduce; drift => STOP and investigate)
```

## 4. Green mock tests (no model, no real scoring)

```bash
python3 test_run_b1_4b_prime_screening.py            # expect 10/10 PASS
python3 test_b1_4b_prime_scorer.py                   # expect 17/17 PASS
python3 test_stage_a_prime_coverage.py               # expect 11/11 PASS
python3 test_b1_4b_prime_prepare_mcrae_y.py          # expect 7/7 PASS
```
Any failure → **STOP**.

## 5. Create the EVIDENCE_FREEZE declaration (OPERATOR — the assistant never creates this)

Create `frozen/private_mcrae/b1_4b_prime_EVIDENCE_FREEZE_DECLARED.json` (git-ignored):

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
Compute the manifest hash with:
```bash
python3 -c "import hashlib;print(hashlib.sha256(open('frozen/b1_4b_prime_mcrae_y_prep_manifest.json','rb').read()).hexdigest())"
```
The driver **refuses** until this file exists and every hash matches.

## 6. Run the screening driver (gated)

```bash
mkdir -p run_out
python3 run_b1_4b_prime_screening.py --mode screening \
    --source-dir <PRIVATE_MCRAE_DIR> \
    --private-dir frozen/private_mcrae \
    --manifest   frozen/b1_4b_prime_mcrae_y_prep_manifest.json \
    --decl       frozen/private_mcrae/b1_4b_prime_EVIDENCE_FREEZE_DECLARED.json \
    --out        run_out/b1_4b_prime_screening_report.json
```
- The driver verifies the freeze gate, builds Stage A′ records for the 521 concepts, wires McRae `KF` as the
  `G` frequency covariate (sentiment intentionally absent → `H` pending), scores all arms at matched capacity,
  and emits a **screening** terminal label.
- **`run_out/` is a private output** — do not commit the report if it embeds anything beyond derived
  scores/counts (the report is designed to hold only derived values, but keep run outputs out of git by
  default).

## 7. Read the result — report it as-is

```bash
python3 -c "import json;r=json.load(open('run_out/b1_4b_prime_screening_report.json'));\
print('LABEL',r['terminal_label']);print('A_F3_REAL',r['arm_scores']['A_F3_REAL'],'B_PHONOLOGY_PLAIN',r['arm_scores']['B_PHONOLOGY_PLAIN']);\
print('pending',r['pending_arms'])"
```
- Report the label verbatim. **Do not upgrade a null.** A `F_COLLAPSES_TO_PHONOLOGY` (the expected outcome) is
  an acceptable, informative result. `INCONCLUSIVE_SCREENING_POSITIVE_NEEDS_FULL_BASELINES` means A led the
  controls present, but a positive **cannot** be claimed without the full baseline suite (sentiment) — it is
  **not** `L1_L2_L3_ATTRIBUTE_SIGNAL`.

## 8. Guardrails

- SIGNAL disabled in screening mode; no `ONTOLOGICAL_SIGNAL`; no semantic-success claim.
- Raw McRae files, the private Y, and the declaration file are **never committed**.
- Frozen Stage A / Stage A′ / scorer must be unchanged (hash-pinned); any change spawns a new versioned study.
- The expected honest outcome remains **`F_COLLAPSES_TO_PHONOLOGY → ⊥`** (phonology-derived substrate;
  homographs reinforce the ceiling).

---

> B1.4b′ screening-run runbook (docs-only). SIGNAL disabled in screening mode. No real McRae evidence run
> performed by the assistant. No evidence freeze declared. No raw McRae data committed. Original B1.4b remains
> blocked. Track B remains blocked. Structure, not validated meaning.
