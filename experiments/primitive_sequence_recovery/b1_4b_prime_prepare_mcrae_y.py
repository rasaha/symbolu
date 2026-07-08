#!/usr/bin/env python3
"""B1.4b′ — McRae Y-preparation + freeze-manifest draft (Terms-compliant, NO run).

Builds the DERIVED B1.4b′ McRae artifacts specified in
`B1_4B_PRIME_MCRAE_FREEZE_PACKAGE_PLAN.md`:
  - concept preprocessing (case, pre-declared `_(sense)` tag-strip, Stage A′ decomposition,
    homograph exclusion, `cloak`/`clock` false-collision exclusion),
  - a binary McRae concept×feature Y matrix (PRIVATE, untracked),
  - a tracked exclusion artifact + a freeze-manifest draft of hashes.

TERMS OF USE: the McRae norms may be used for non-commercial research/education WITH citation;
redistribution is NOT granted. Therefore the RAW McRae files and the DERIVED Y matrix / full
concept list / feature list are written ONLY to a PRIVATE (git-ignored) directory and are NEVER
committed. Only hashes, counts, config, and the small (already-public) exclusion list are
tracked.

This module trains NO decoder, runs NO F-3 semantic scoring, compares NO baselines, and declares
NO semantic result. Stage A′ is imported READ-ONLY. Frozen Stage A is untouched.

Usage (operator supplies the private McRae files):
  python3 b1_4b_prime_prepare_mcrae_y.py --source-dir <dir-with-CONCS_brm.txt etc> \
      [--private-out frozen/private_mcrae] [--tracked-out frozen]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage_a_prime_coverage as A   # READ-ONLY

LABELS = (
    "B1_4B_PRIME_Y_PREP_READY",
    "B1_4B_PRIME_Y_PREP_FAIL_TERMS",
    "B1_4B_PRIME_Y_PREP_FAIL_COVERAGE",
    "B1_4B_PRIME_Y_PREP_FAIL_COLLISION",
    "B1_4B_PRIME_Y_PREP_INCONCLUSIVE",
)

# raw-data filename patterns that must NEVER be tracked in git (Terms of Use)
RAW_PATTERNS = ("CONCS_brm", "CONCS_FEATS", "FEATS_brm", "cos_matrix", "mcrae_y_matrix",
                "concept_list_full", "feature_list_full")

# pre-declared preprocessing config (frozen BEFORE any run)
PREP_CONFIG = {
    "case": "lower",
    "tag_strip_rule": r"_?\([^)]*\)$",          # remove a trailing _(sense) disambiguation tag
    "min_prod_freq": 5,                          # McRae >=5/30 inclusion (already applied in source)
    "exclude_taxonomic": True,                   # drop superordinate/taxonomic category features
    "min_concepts_per_feature": 5,               # sparse-feature pruning (within retained concepts)
    "absence_is_zero": True,
    "homograph_rule": "exclude_all_collapsed_members",
    "false_collision_rule": "exclude_all_collapsed_members",
    "stage_a_prime_track": "A_PRIME_EN",
    "min_retained_concepts": 100,
}

# spec stubs pinned for later phases (hashed as version anchors; NOT executed here)
F3_FEATURE_SPEC = {
    "layer": "L2", "features": ["adjacent_commutator_mean", "adjacent_commutator_max",
    "ordered_vs_reversed_noncommutativity"], "excluded": ["state_norm", "magnitude", "energy"],
    "reversal_symmetry_invariant": True, "oriented_extension": "requires_separate_prereg",
    "stage_a_prime_module": "stage_a_prime_coverage.py",
}
BASELINE_SPEC = {"baselines": ["plain_phonological", "phonological_similarity", "bag_of_phonemes",
    "shuffled_order", "random_relabel_operators", "length_frequency", "sentiment_lexicon",
    "chance_null"], "capacity": "matched_to_f3"}
DECODER_METRIC_SPEC = {"decoder": "regularized_linear_first_pass", "cv": "concept_level_kfold",
    "capacity_parity": True, "primary_endpoint": "delta_vs_phonology",
    "co_primary": "delta_vs_bag_shuffle_random", "correction": "holm",
    "labels": ["L1_L2_L3_ATTRIBUTE_SIGNAL", "F_COLLAPSES_TO_PHONOLOGY", "BAG_OR_SHUFFLE_EXPLAINS",
    "RANDOM_RELABEL_EXPLAINS", "SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS", "Y_NOT_INDEPENDENT",
    "DECODER_LEAKAGE_INVALID", "NULL_RETURN_BOTTOM", "INCONCLUSIVE"]}


# ---------- hashing helpers ----------
def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha_text(s: str) -> str:
    return _sha_bytes(s.encode("utf-8"))


def _sha_json(obj) -> str:
    return _sha_text(json.dumps(obj, sort_keys=True, separators=(",", ":")))


def _sha_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- source resolution (canonical name, tolerant of upload-hash prefixes) ----------
def _resolve(source_dir: pathlib.Path, canonical: str) -> pathlib.Path:
    cands = [p for p in source_dir.iterdir() if p.name == canonical or p.name.endswith("-" + canonical)]
    if not cands:
        raise FileNotFoundError(f"{canonical} not found in {source_dir}")
    return sorted(cands)[0]


def _base(concept: str) -> str:
    return re.sub(PREP_CONFIG["tag_strip_rule"], "", concept.strip().lower()).strip("_")


# ---------- core preparation ----------
def prepare(source_dir: pathlib.Path, private_out: pathlib.Path, tracked_out: pathlib.Path,
            write: bool = True) -> dict:
    concs = _resolve(source_dir, "CONCS_brm.txt")
    cfeat = _resolve(source_dir, "CONCS_FEATS_concstats_brm.txt")
    feats = _resolve(source_dir, "FEATS_brm.txt")
    terms = _resolve(source_dir, "ReadMe_Terms_of_Use.txt")
    readme = _resolve(source_dir, "READ_ME.txt")

    import csv
    concepts = [r["Concept"].strip() for r in csv.DictReader(open(concs, newline=""), delimiter="\t")
                if r.get("Concept")]

    # Stage A′ decomposition of tag-stripped concepts -> sequence per concept
    seq = {}
    nondecomp = []
    for c in concepts:
        r = A.normalize(_base(c), PREP_CONFIG["stage_a_prime_track"])
        if r["flag"] != "full":
            nondecomp.append(c)
        seq[c] = tuple(r["phonemes"])

    # collision detection: group concepts by identical Stage A′ sequence
    groups = {}
    for c in concepts:
        groups.setdefault(seq[c], []).append(c)
    homograph_excl, false_collision_excl = [], []
    for s, members in groups.items():
        if len(members) < 2:
            continue
        bases = {_base(m) for m in members}
        if len(bases) == 1:            # same base word -> homograph sense-pair
            homograph_excl.extend(members)
        else:                          # different base words mapped identically -> G2P false collision
            false_collision_excl.extend(members)

    excluded = set(homograph_excl) | set(false_collision_excl) | set(nondecomp)
    retained = [c for c in concepts if c not in excluded]

    # ---- build binary concept×feature Y over retained concepts (PRIVATE) ----
    rows = list(csv.DictReader(open(cfeat, newline=""), delimiter="\t"))
    retained_set = set(retained)
    # candidate (concept, feature) presence: prod_freq >= threshold, optional non-taxonomic
    pres = {}   # concept -> set(features)
    for r in rows:
        c = r["Concept"].strip()
        if c not in retained_set:
            continue
        try:
            pf = int(r["Prod_Freq"]) if r["Prod_Freq"] else 0
        except ValueError:
            pf = 0
        if pf < PREP_CONFIG["min_prod_freq"]:
            continue
        if PREP_CONFIG["exclude_taxonomic"] and (r.get("BR_Label", "").strip() == "taxonomic"):
            continue
        pres.setdefault(c, set()).add(r["Feature"].strip())

    # feature pruning: keep features present in >= k retained concepts
    fcount = {}
    for c, fs in pres.items():
        for f in fs:
            fcount[f] = fcount.get(f, 0) + 1
    kept_feats = sorted(f for f, n in fcount.items() if n >= PREP_CONFIG["min_concepts_per_feature"])
    fidx = {f: i for i, f in enumerate(kept_feats)}
    retained = sorted(retained)            # deterministic order
    Y = np.zeros((len(retained), len(kept_feats)), dtype=np.int8)
    for ci, c in enumerate(retained):
        for f in pres.get(c, ()):
            j = fidx.get(f)
            if j is not None:
                Y[ci, j] = 1

    # ---- hashes ----
    concept_list_sha = _sha_text("\n".join(retained))
    feature_list_sha = _sha_text("\n".join(kept_feats))
    y_matrix_sha = _sha_bytes(Y.tobytes() + concept_list_sha.encode() + feature_list_sha.encode())
    prep_cfg_sha = _sha_json(PREP_CONFIG)

    exclusions = {
        "artifact": "b1_4b_prime_mcrae_exclusions",
        "note": "Concept labels only (already public). NO McRae feature values.",
        "homograph_sense_pairs_excluded": sorted(homograph_excl),
        "false_collision_excluded": sorted(false_collision_excl),
        "non_decomposable_excluded": sorted(nondecomp),
        "reason_codes": {
            "HOMOGRAPH_COLLAPSE": "same base word -> identical Stage A′ sequence -> identical F-3",
            "G2P_FALSE_COLLISION": "distinct words mapped identically by coverage-oriented A_PRIME_EN G2P",
            "NON_DECOMPOSABLE": "did not fully decompose under Stage A′ after tag-strip",
        },
        "counts": {"total_concepts": len(concepts), "excluded": len(excluded),
                   "retained": len(retained)},
    }
    exclusions_sha = _sha_json(exclusions)

    manifest = {
        "artifact": "b1_4b_prime_mcrae_y_prep_manifest",
        "status": "DRAFT_Y_PREP_ONLY_NO_RUN",
        "provenance": {
            "source": "McRae, Cree, Seidenberg & McNorgan (2005), Behavior Research Methods 37(4):547-559",
            "archive": "Psychonomic Society Web Archive (operator-provided private files)",
            "terms_of_use": "non-commercial research/education WITH citation; rights remain with authors; "
                            "redistribution NOT granted; raw data NOT committed",
        },
        "private_source_file_sha256": {
            "CONCS_brm.txt": _sha_file(concs),
            "CONCS_FEATS_concstats_brm.txt": _sha_file(cfeat),
            "FEATS_brm.txt": _sha_file(feats),
            "READ_ME.txt": _sha_file(readme),
            "ReadMe_Terms_of_Use.txt": _sha_file(terms),
        },
        "derived_concept_list_sha256": concept_list_sha,
        "attribute_list_sha256": feature_list_sha,
        "y_matrix_sha256": y_matrix_sha,
        "y_matrix_shape": list(Y.shape),
        "y_preprocessing_config": PREP_CONFIG,
        "y_preprocessing_config_sha256": prep_cfg_sha,
        "exclusion_list_sha256": exclusions_sha,
        "stage_a_prime_module_sha256": _sha_file(HERE / "stage_a_prime_coverage.py"),
        "f3_feature_spec": F3_FEATURE_SPEC,
        "f3_feature_spec_sha256": _sha_json(F3_FEATURE_SPEC),
        "baseline_spec": BASELINE_SPEC,
        "baseline_spec_sha256": _sha_json(BASELINE_SPEC),
        "decoder_metric_config": DECODER_METRIC_SPEC,
        "decoder_metric_config_sha256": _sha_json(DECODER_METRIC_SPEC),
        "counts": {"total_concepts": len(concepts), "retained_concepts": len(retained),
                   "attribute_features": len(kept_feats)},
        "no_run_guarantees": {"decoder_trained": False, "f3_scored": False,
                              "baselines_compared": False, "evidence_freeze": False},
    }

    # ---- write PRIVATE (untracked) derived artifacts + TRACKED (non-raw) artifacts ----
    if write:
        private_out.mkdir(parents=True, exist_ok=True)
        (private_out / "concept_list_full.txt").write_text("\n".join(retained) + "\n")
        (private_out / "feature_list_full.txt").write_text("\n".join(kept_feats) + "\n")
        np.savez_compressed(private_out / "mcrae_y_matrix.npz",
                            Y=Y, concepts=np.array(retained), features=np.array(kept_feats))
        tracked_out.mkdir(parents=True, exist_ok=True)
        (tracked_out / "b1_4b_prime_mcrae_exclusions.json").write_text(
            json.dumps(exclusions, indent=2) + "\n")
        manifest["manifest_self_sha256"] = _sha_json({k: v for k, v in manifest.items()})
        (tracked_out / "b1_4b_prime_mcrae_y_prep_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n")
    else:
        manifest["manifest_self_sha256"] = _sha_json({k: v for k, v in manifest.items()})

    # ---- validation + terminal label ----
    checks = {
        "retained_ge_100": len(retained) >= PREP_CONFIG["min_retained_concepts"],
        "all_retained_fully_decompose": all(
            A.normalize(_base(c), PREP_CONFIG["stage_a_prime_track"])["flag"] == "full"
            for c in retained),
        "retained_sequences_unique": len({seq[c] for c in retained}) == len(retained),
        "cloak_clock_excluded": ("cloak" in excluded or "clock" in excluded) and
                                not ({"cloak", "clock"} & retained_set),
        "feature_dim_positive": len(kept_feats) > 0,
    }
    if all(checks.values()):
        label = "B1_4B_PRIME_Y_PREP_READY"
    elif not checks["retained_ge_100"]:
        label = "B1_4B_PRIME_Y_PREP_FAIL_COVERAGE"
    elif not (checks["retained_sequences_unique"] and checks["cloak_clock_excluded"]):
        label = "B1_4B_PRIME_Y_PREP_FAIL_COLLISION"
    else:
        label = "B1_4B_PRIME_Y_PREP_INCONCLUSIVE"

    return {"label": label, "checks": checks, "manifest": manifest, "exclusions": exclusions,
            "retained": len(retained), "features": len(kept_feats),
            "excluded": {"homograph": sorted(homograph_excl),
                         "false_collision": sorted(false_collision_excl),
                         "non_decomposable": sorted(nondecomp)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", required=True)
    ap.add_argument("--private-out", default=str(HERE / "frozen" / "private_mcrae"))
    ap.add_argument("--tracked-out", default=str(HERE / "frozen"))
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    res = prepare(pathlib.Path(a.source_dir), pathlib.Path(a.private_out),
                  pathlib.Path(a.tracked_out), write=not a.no_write)
    print("LABEL:", res["label"])
    print("retained concepts:", res["retained"], " attribute features:", res["features"])
    print("checks:", json.dumps(res["checks"]))
    print("excluded homographs:", res["excluded"]["homograph"])
    print("excluded false-collision:", res["excluded"]["false_collision"])
    print("NOTE: private Y artifacts written untracked; only hashes/config/exclusions are tracked.")
    print("No decoder trained, no F-3 scored, no baselines compared, no evidence freeze.")
    return 0 if res["label"] == "B1_4B_PRIME_Y_PREP_READY" else 1


if __name__ == "__main__":
    sys.exit(main())
