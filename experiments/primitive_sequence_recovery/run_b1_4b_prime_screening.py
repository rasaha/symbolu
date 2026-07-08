#!/usr/bin/env python3
"""B1.4b′ — phonology-primary SCREENING-run driver (gated). Mock-testable; refuses real scoring
without an operator EVIDENCE_FREEZE declaration.

SCREENING MODE: positive `L1_L2_L3_ATTRIBUTE_SIGNAL` is DISABLED by construction. This run can
only return F_COLLAPSES_TO_PHONOLOGY / BAG_OR_SHUFFLE_EXPLAINS / RANDOM_RELABEL_EXPLAINS /
NULL_RETURN_BOTTOM / INCONCLUSIVE / INCONCLUSIVE_SCREENING_POSITIVE_NEEDS_FULL_BASELINES, plus
validity-failure labels. It CANNOT certify a positive — the sentiment/lexicon baseline (H) is a
pending source, so "beats all baselines" cannot be established here.

FREEZE GATE: the driver refuses to score the real McRae data unless
`b1_4b_prime_EVIDENCE_FREEZE_DECLARED.json` exists with `evidence_freeze_declared: true`,
`mode: "screening"`, a matching freeze-manifest hash, matching private-source-file hashes, and a
matching private-Y hash. The assistant NEVER creates that declaration; the operator does.

TERMS OF USE: raw McRae data / private Y are read from a git-ignored private dir and are NEVER
committed; the report contains only derived scores/counts (no feature names/values). Stage A′ is
imported READ-ONLY; frozen Stage A is untouched.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage_a_prime_coverage as A            # READ-ONLY
import b1_4b_prime_scorer as S                # arm registry + decoder
import b1_4b_prime_prepare_mcrae_y as PREP    # hashing + tag-strip + source resolver (no run)

MODE = "screening"
POSITIVE_SCREENING_LABEL = "INCONCLUSIVE_SCREENING_POSITIVE_NEEDS_FULL_BASELINES"
SCREENING_ALLOWED = (
    "F_COLLAPSES_TO_PHONOLOGY", "BAG_OR_SHUFFLE_EXPLAINS", "RANDOM_RELABEL_EXPLAINS",
    "NULL_RETURN_BOTTOM", "INCONCLUSIVE", POSITIVE_SCREENING_LABEL,
    "Y_NOT_INDEPENDENT", "DECODER_LEAKAGE_INVALID",
)
FORBIDDEN_IN_SCREENING = ("L1_L2_L3_ATTRIBUTE_SIGNAL", "ONTOLOGICAL_SIGNAL")
DECL_NAME = "b1_4b_prime_EVIDENCE_FREEZE_DECLARED.json"


# =====================================================================================
# freeze gate
# =====================================================================================
def verify_freeze_gate(source_dir: pathlib.Path, private_dir: pathlib.Path,
                       manifest_path: pathlib.Path, decl_path: pathlib.Path):
    reasons = []
    if not decl_path.exists():
        return False, ["no EVIDENCE_FREEZE_DECLARED file"]
    decl = json.loads(decl_path.read_text())
    if decl.get("evidence_freeze_declared") is not True:
        reasons.append("evidence_freeze_declared != true")
    if decl.get("mode") != MODE:
        reasons.append(f"declaration mode != {MODE}")
    if not manifest_path.exists():
        return False, ["freeze manifest missing"]
    if decl.get("manifest_sha256") != PREP._sha_file(manifest_path):
        reasons.append("manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text())
    for name, exp in manifest.get("private_source_file_sha256", {}).items():
        try:
            p = PREP._resolve(source_dir, name)
        except FileNotFoundError:
            reasons.append(f"source missing: {name}"); continue
        if PREP._sha_file(p) != exp:
            reasons.append(f"source hash mismatch: {name}")
    npz = private_dir / "mcrae_y_matrix.npz"
    if not npz.exists():
        reasons.append("private Y matrix missing")
    else:
        z = np.load(npz, allow_pickle=True)
        Y = z["Y"]
        concepts = [c if isinstance(c, str) else c.decode() for c in z["concepts"]]
        feats = [f if isinstance(f, str) else f.decode() for f in z["features"]]
        c_sha = PREP._sha_text("\n".join(concepts))
        f_sha = PREP._sha_text("\n".join(feats))
        y_sha = PREP._sha_bytes(Y.tobytes() + c_sha.encode() + f_sha.encode())
        if y_sha != manifest.get("y_matrix_sha256"):
            reasons.append("private Y hash mismatch")
    return (len(reasons) == 0), reasons


# =====================================================================================
# records (real path): concept labels -> Stage A′ phonemes + covariates (frequency wired from
# McRae KF; sentiment intentionally absent -> H pending)
# =====================================================================================
def _kf_map(source_dir: pathlib.Path):
    try:
        concs = PREP._resolve(source_dir, "CONCS_brm.txt")
    except FileNotFoundError:
        return {}
    m = {}
    for r in csv.DictReader(open(concs, newline=""), delimiter="\t"):
        c = (r.get("Concept") or "").strip().lower()
        try:
            m[c] = float(r.get("KF") or "nan")
        except ValueError:
            pass
    return m


def build_records(concepts, source_dir: pathlib.Path):
    kf = _kf_map(source_dir)
    recs = []
    for c in concepts:
        base = PREP._base(c)
        ph = A.normalize(base, "A_PRIME_EN")["phonemes"]
        covars = {}
        f = kf.get(c.lower())
        if f is not None and np.isfinite(f):
            covars["freq"] = f
        recs.append({"phonemes": ph, "covars": covars})   # NO sentiment -> H stays pending
    return recs


# =====================================================================================
# screening decision: SIGNAL disabled by construction
# =====================================================================================
def screening_decide(arm_scores, flags=None):
    lab = S.decide_label_arms(arm_scores, flags)
    if lab == "L1_L2_L3_ATTRIBUTE_SIGNAL":
        return POSITIVE_SCREENING_LABEL          # A led, but positive cannot be certified in screening
    assert lab not in FORBIDDEN_IN_SCREENING
    return lab


def build_report(manifest_path, arm_scores, pending_arms, label, n_concepts, n_features):
    return {
        "artifact": "b1_4b_prime_screening_run_report",
        "mode": MODE,
        "screening_warning": "SIGNAL disabled by construction; positive certification impossible in screening mode.",
        "no_positive_claim": "This run cannot and does not claim L1_L2_L3_ATTRIBUTE_SIGNAL, ONTOLOGICAL_SIGNAL, or any semantic success.",
        "terms_of_use": "McRae norms: non-commercial research/education WITH citation; raw data NOT committed; report holds derived scores/counts only.",
        "citation": "McRae, Cree, Seidenberg & McNorgan (2005), Behavior Research Methods 37(4):547-559 + Psychonomic Web Archive norms.",
        "freeze_manifest_sha256": PREP._sha_file(manifest_path),
        "n_concepts": int(n_concepts),
        "n_features": int(n_features),
        "arm_scores": arm_scores,
        "pending_arms": pending_arms,
        "terminal_label": label,
        "allowed_screening_labels": list(SCREENING_ALLOWED),
        "raw_mcrae_data_in_report": False,
    }


def run_screening(source_dir, private_dir, manifest_path, decl_path, out_path=None, flags=None):
    """Gated real screening run. Refuses (SystemExit) unless the freeze gate passes."""
    ok, reasons = verify_freeze_gate(pathlib.Path(source_dir), pathlib.Path(private_dir),
                                     pathlib.Path(manifest_path), pathlib.Path(decl_path))
    if not ok:
        raise SystemExit("REFUSED: freeze gate failed -> " + "; ".join(reasons))
    z = np.load(pathlib.Path(private_dir) / "mcrae_y_matrix.npz", allow_pickle=True)
    Y = z["Y"].astype(float)
    concepts = [c if isinstance(c, str) else c.decode() for c in z["concepts"]]
    records = build_records(concepts, pathlib.Path(source_dir))
    arm_scores, pending_arms = S.score_arms(records, Y)
    label = screening_decide(arm_scores, flags)
    report = build_report(pathlib.Path(manifest_path), arm_scores, pending_arms, label,
                          len(concepts), Y.shape[1])
    if out_path:
        pathlib.Path(out_path).write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="screening")
    ap.add_argument("--source-dir", required=True)
    ap.add_argument("--private-dir", default=str(HERE / "frozen" / "private_mcrae"))
    ap.add_argument("--manifest", default=str(HERE / "frozen" / "b1_4b_prime_mcrae_y_prep_manifest.json"))
    ap.add_argument("--decl", default=str(HERE / "frozen" / "private_mcrae" / DECL_NAME))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.mode != MODE:
        raise SystemExit(f"REFUSED: this driver only runs --mode {MODE} (SIGNAL disabled).")
    report = run_screening(a.source_dir, a.private_dir, a.manifest, a.decl, a.out)
    print("SCREENING TERMINAL LABEL:", report["terminal_label"])
    print("arm_scores:", json.dumps(report["arm_scores"]))
    print("pending_arms:", json.dumps(report["pending_arms"]))
    print("SIGNAL disabled in screening mode. No positive/semantic claim. Track B blocked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
