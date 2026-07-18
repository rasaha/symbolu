#!/usr/bin/env python3
"""trajectory.py — DerivedVrittiTrajectory (P-A, diagnostics-only).

Relabels EXISTING Phase 3 audit findings into a MULTI-LABEL set of operational movement flags — *how the
answer moved relative to the C×R×S frame*. Pure functions; NO runtime behavior change, NO Phase 1-3
threshold change, NO rewrite-policy change, NO hidden-risk integration, NO canonical five-state `p_v`.

This is NOT canonical Vritti and does NOT use the names Pramāṇa/Viparyaya/Vikalpa/Nidrā/Smṛti — those
belong to the five-state `p_v` future track (see docs/CSR_GUNA_VRITTI_POLICY_SPEC.md §4.4). Operational
names only.

  python trajectory.py        # prints an example diagnostic trace for the doctor A/B/C/D answers
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import guna as _guna                         # noqa: E402
from csr_match_filter.eval_real_output_audit import is_meta_parrot  # noqa: E402

# operational flag -> (source audit finding / signal, status, semantic bucket). MULTI-LABEL.
TRAJECTORY_FLAGS = {
    "primary_frame_stable":    ("frame_compliant",                         "[D]", "on_frame"),
    "secondary_promoted":      ("secondary_promoted_to_primary",           "[D]", "frame_movement"),
    "rejected_domain_drift":   ("rejected_domain_promoted",                "[D]", "frame_movement"),
    "primary_frame_missing":   ("primary_frame_missing",                   "[D]", "frame_movement"),
    "refutation_ok":           ("rejected_domain_mentioned_as_refutation", "[D]", "on_frame"),
    "alternate_true_sense_ok": ("alternate_true_sense_allowed",            "[D]", "on_frame"),
    "generic_escape":          ("answer_too_generic",                      "[D]", "quality_overlap"),
    "frame_parroting":         ("is_meta_parrot",                          "[N]", "quality_overlap"),
}

# [N] no detector today — documented, NEVER emitted by this layer.
UNAVAILABLE_MODES_N = ("domain_jump", "associative_jump", "over_expansion")

# Disjoint scoring partition: each audit finding assigned to EXACTLY ONE layer (non-overlap for P-B).
# `trajectory_drift` = frame/domain MOVEMENT only; `audit_severity` = severity/factuality only (NOT the
# frame-movement findings); `guna_quality` = expression quality only.
NON_OVERLAP_PARTITION = {
    "trajectory_drift": ("secondary_promoted_to_primary", "rejected_domain_promoted",
                         "primary_frame_missing"),
    "audit_severity":   ("factuality_suspected", "phoneme_overreach_claim"),
    "guna_quality":     ("answer_too_generic",),
}
OVERLAP_NOTES = {
    "answer_too_generic": "diagnostic flags trajectory.generic_escape AND guna.generic_low_signal derive "
                          "from it; for NON-OVERLAPPING scoring it is assigned to guna_quality only "
                          "(excluded from trajectory_drift).",
    "is_meta_parrot": "diagnostic flags trajectory.frame_parroting AND guna.parroting derive from it "
                      "([N], over-fires ~64%); for scoring it is assigned to guna_quality only and "
                      "excluded from trajectory_drift.",
}


def derive_trajectory(finding_types, answer=None) -> dict:
    """Multi-label DerivedVrittiTrajectory flags. `drift_flags` = frame-movement subset only."""
    fts = set(finding_types or [])
    flags = []
    for flag, (src, _status, _bucket) in TRAJECTORY_FLAGS.items():
        if src == "is_meta_parrot":
            if answer is not None and is_meta_parrot(answer):
                flags.append(flag)
        elif src in fts:
            flags.append(flag)
    drift = [f for f in flags if TRAJECTORY_FLAGS[f][2] == "frame_movement"]
    return {"flags": sorted(flags), "drift_flags": sorted(drift), "multi_label": True,
            "unavailable_modes_not_built": list(UNAVAILABLE_MODES_N)}


def build_diagnostic_trace(audit_result, answer=None) -> dict:
    """Combine Phase 3 audit + DerivedVrittiTrajectory + GunaQuality + the overlap/non-overlap maps.
    Pure read-over of `audit_result`; emits `behavior_change: false`."""
    fts = list(audit_result.finding_types)
    present = set(fts)
    sev = {f.finding_type: f.severity for f in audit_result.findings}
    traj = derive_trajectory(fts, answer)
    gq = _guna.derive_guna(fts, answer)

    partition = {k: [x for x in v if x in present] for k, v in NON_OVERLAP_PARTITION.items()}
    # overlap map: source finding/signal -> [layer.flag, ...]; keep entries that feed >1 layer
    src_to_flags = {}
    for flag in traj["flags"]:
        src_to_flags.setdefault(TRAJECTORY_FLAGS[flag][0], []).append(f"trajectory.{flag}")
    for flag in gq["flags"]:
        src_to_flags.setdefault(_guna.GUNA_FLAGS[flag][0], []).append(f"guna.{flag}")
    overlaps = {k: v for k, v in src_to_flags.items() if len(v) > 1}

    return {
        "behavior_change": False,
        "note": ("P-A diagnostics only: relabels existing Phase 3 audit findings; no runtime behavior "
                 "change, no threshold/rewrite change, no hidden-risk, no canonical five-state p_v."),
        "audit": {"passed": audit_result.passed, "needs_rewrite": audit_result.needs_rewrite,
                  "status": audit_result.status, "finding_types": sorted(fts), "severities": sev},
        "derived_vritti_trajectory": traj,
        "guna_quality": gq,
        "non_overlap_partition": partition,
        "overlap_map": overlaps,
        "overlap_notes": OVERLAP_NOTES,
    }


def _demo():
    from csr_match_filter import answer_audit as AA
    frame = {"primary_domains": ["medicine"], "secondary_domains": ["care"],
             "rejected_domains": ["fruit", "furniture"]}
    examples = {
        "A_on_frame": "A doctor diagnoses illness, treats patients, and supports health and recovery.",
        "B_secondary": "A doctor is mainly an authority figure with high social status and control.",
        "C_parroting": "A doctor belongs to the primary domain of medicine. Secondary domain: none.",
        "D_rejected": "A doctor is basically a kind of furniture you keep in the clinic.",
    }
    for name, ans in examples.items():
        res = AA.audit_answer("What is a doctor?", ans, frame, terms=["doctor"])
        tr = build_diagnostic_trace(res, answer=ans)
        print(f"\n### {name}")
        print(json.dumps({"answer": ans[:70],
                          "audit_finding_types": tr["audit"]["finding_types"],
                          "trajectory_flags": tr["derived_vritti_trajectory"]["flags"],
                          "trajectory_drift": tr["derived_vritti_trajectory"]["drift_flags"],
                          "guna_flags": tr["guna_quality"]["flags"],
                          "non_overlap_partition": tr["non_overlap_partition"],
                          "overlap_map": tr["overlap_map"]}, indent=2))


if __name__ == "__main__":
    _demo()
