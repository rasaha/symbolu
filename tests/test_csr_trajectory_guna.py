"""CPU tests for P-A diagnostics: DerivedVrittiTrajectory (trajectory.py) + GunaQuality (guna.py).

Pure relabel of existing Phase 3 audit findings — verifies multi-label flags, operational (non-Sanskrit)
naming, the non-overlapping scoring partition, the documented overlaps, and NO behavior change / NO
canonical five-state p_v. No GPU.
"""

import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

pytest.importorskip("numpy")

from csr_match_filter import trajectory as T          # noqa: E402
from csr_match_filter import guna as G                # noqa: E402
from csr_match_filter import answer_audit as AA       # noqa: E402

_FRAME = {"primary_domains": ["medicine"], "secondary_domains": ["care"],
          "rejected_domains": ["fruit", "furniture"]}


# ---- trajectory ----------------------------------------------------------------------------------

def test_trajectory_is_multilabel():
    fts = ["secondary_promoted_to_primary", "rejected_domain_promoted", "answer_too_generic"]
    out = T.derive_trajectory(fts)
    assert out["multi_label"] is True
    assert "secondary_promoted" in out["flags"] and "rejected_domain_drift" in out["flags"]
    assert "generic_escape" in out["flags"]
    # drift_flags = frame-movement subset ONLY (generic_escape is quality, not drift)
    assert set(out["drift_flags"]) == {"secondary_promoted", "rejected_domain_drift"}
    assert "generic_escape" not in out["drift_flags"]


def test_trajectory_frame_parroting_is_answer_derived_and_N():
    assert T.TRAJECTORY_FLAGS["frame_parroting"][1] == "[N]"
    parrot = "The term belongs to the primary domain of medicine. Secondary domain: none."
    assert "frame_parroting" in T.derive_trajectory([], answer=parrot)["flags"]
    assert "frame_parroting" not in T.derive_trajectory([], answer="A doctor treats patients.")["flags"]


def test_trajectory_uses_operational_names_not_sanskrit():
    blob = " ".join(list(T.TRAJECTORY_FLAGS) + [v[0] for v in T.TRAJECTORY_FLAGS.values()]).lower()
    for s in ("pramana", "pramāṇa", "viparyaya", "vikalpa", "nidra", "nidrā", "smrti", "smṛti", "p_v"):
        assert s not in blob


# ---- guna ----------------------------------------------------------------------------------------

def test_guna_uses_existing_signals_only():
    assert G.GUNA_FLAGS["generic_low_signal"][1] == "[D]"        # direct relabel of answer_too_generic
    assert G.GUNA_FLAGS["parroting"][1] == "[N]"
    out = G.derive_guna(["answer_too_generic"])
    assert out["flags"] == ["generic_low_signal"] and out["multi_label"] is True
    # new clarity/overconfidence/specificity detectors are declared [N], NOT emitted
    assert "clear_stable" in out["future_detectors_not_built"]
    assert "overconfident" not in out["flags"]


# ---- non-overlap partition + trace ---------------------------------------------------------------

def test_non_overlap_partition_is_disjoint():
    sets = [set(v) for v in T.NON_OVERLAP_PARTITION.values()]
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            assert sets[i].isdisjoint(sets[j])                  # each finding in exactly one bucket
    # frame-movement findings are NOT in audit_severity (per the spec rule)
    assert "rejected_domain_promoted" in T.NON_OVERLAP_PARTITION["trajectory_drift"]
    assert "rejected_domain_promoted" not in T.NON_OVERLAP_PARTITION["audit_severity"]


def test_build_trace_no_behavior_change_and_documents_overlap():
    parrot = "A doctor belongs to the primary domain of medicine. Secondary domain: none."
    res = AA.audit_answer("What is a doctor?", parrot, _FRAME, terms=["doctor"])
    tr = T.build_diagnostic_trace(res, answer=parrot)
    assert tr["behavior_change"] is False
    for k in ("audit", "derived_vritti_trajectory", "guna_quality", "non_overlap_partition",
              "overlap_map", "overlap_notes"):
        assert k in tr
    # the parroting overlap is surfaced (same source feeds both layers)
    assert tr["overlap_map"].get("is_meta_parrot") == ["trajectory.frame_parroting", "guna.parroting"]


def test_trace_partition_only_lists_present_findings():
    leak = "A doctor is basically a kind of furniture you keep in the clinic."
    res = AA.audit_answer("What is a doctor?", leak, _FRAME, terms=["doctor"])
    tr = T.build_diagnostic_trace(res, answer=leak)
    present = set(tr["audit"]["finding_types"])
    for bucket in tr["non_overlap_partition"].values():
        assert all(f in present for f in bucket)
    # rejected-domain leak shows up as the trajectory drift flag
    assert "rejected_domain_drift" in tr["derived_vritti_trajectory"]["flags"]


def test_pure_relabel_does_not_touch_audit_result():
    res = AA.audit_answer("What is a doctor?", "A doctor treats patients.", _FRAME, terms=["doctor"])
    before = (res.passed, res.needs_rewrite, list(res.finding_types))
    T.build_diagnostic_trace(res, answer="A doctor treats patients.")
    assert (res.passed, res.needs_rewrite, list(res.finding_types)) == before   # unchanged
