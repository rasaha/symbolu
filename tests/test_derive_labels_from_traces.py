"""CPU tests for the rubric->audit trace adapter + audit-derived label prevalence/usability reporting.
No hidden-state probe, no training, no GPU, no LEARNS_SIGNAL claim."""
import sys
from pathlib import Path

_SCR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

from conscious_generation_training import derive_labels_from_traces as T   # noqa: E402


# ---- rubric_v2 -> audit fields ------------------------------------------------------------------
def test_rubric_to_audit_factuality_drives_viparyaya_finding():
    aud = T.rubric_to_audit({"primary_frame_correct": 1, "rejected_domain_avoidance": 1,
                             "factuality_preserved": 0})
    assert "factuality_suspected" in aud["expected_findings"] and aud["expected_needs_rewrite"] is True
    ok = T.rubric_to_audit({"primary_frame_correct": 1, "rejected_domain_avoidance": 1,
                            "factuality_preserved": 1})
    assert ok["expected_findings"] == ["frame_compliant"] and ok["expected_needs_rewrite"] is False


def test_rubric_to_audit_frame_and_generic():
    aud = T.rubric_to_audit({"primary_frame_correct": 0, "rejected_domain_avoidance": 0,
                             "factuality_preserved": 1, "answer_clarity_proxy": 0.2})
    assert "primary_frame_missing" in aud["expected_findings"]
    assert "rejected_domain_promoted" in aud["expected_findings"]
    assert "answer_too_generic" in aud["expected_findings"]
    assert "frame_compliant" not in aud["expected_findings"]


# ---- adapters: robustness {traces} and four-arm list --------------------------------------------
def test_rows_from_robustness_one_row_per_arm():
    blob = {"traces": {"doctor": {"answers": {"framed": "A doctor treats illness in patients with care daily."},
                                  "scores": {"framed": {"primary_frame_correct": 1,
                                                        "rejected_domain_avoidance": 1,
                                                        "factuality_preserved": 0}}}}}
    rows = T.rows_from_robustness(blob, {"doctor": {"query": "What is a doctor?"}}, None)
    assert len(rows) == 1 and rows[0]["arm"] == "framed" and rows[0]["query"] == "What is a doctor?"
    assert "factuality_suspected" in rows[0]["expected_findings"]


def test_rows_from_four_arm_multiarm():
    per = [{"id": "q1", "query": "What is a doctor?",
            "answers": {"A": "ans a here long enough text okay", "C": "ans c here long enough text okay"},
            "scores": {"A": {"factuality_preserved": 1, "primary_frame_correct": 1,
                             "rejected_domain_avoidance": 1},
                       "C": {"factuality_preserved": 0, "primary_frame_correct": 1,
                             "rejected_domain_avoidance": 1}}}]
    rows = T.rows_from_four_arm(per, None)
    assert {r["arm"] for r in rows} == {"A", "C"}
    c = next(r for r in rows if r["arm"] == "C")
    assert "factuality_suspected" in c["expected_findings"]


# ---- end-to-end: prevalence + gate --------------------------------------------------------------
def _four_arm_fixture(n_each=12):
    """n_each factuality-failing (->viparyaya) + n_each clean (->pramana); surface-matched answers so the
    classes are NOT separable by surface features (viparyaya should come back NOT confounded)."""
    per = []
    for i in range(n_each):
        per.append({"id": f"good{i}", "query": "q?",
                    "answers": {"C": "A doctor is a medical professional who treats illness in patients with care."},
                    "scores": {"C": {"primary_frame_correct": 1, "rejected_domain_avoidance": 1,
                                     "factuality_preserved": 1}}})
        per.append({"id": f"bad{i}", "query": "q?",
                    "answers": {"C": "A doctor is a medical professional who treats illness in patients with harm."},
                    "scores": {"C": {"primary_frame_correct": 1, "rejected_domain_avoidance": 1,
                                     "factuality_preserved": 0}}})
    return per


def test_end_to_end_prevalence_and_usable_when_not_surface_separable():
    rows = T.rows_from_four_arm(_four_arm_fixture(12), None)
    labelled = [T.derive_row(r) for r in rows]
    rep = T.usability_report(labelled)
    vip = rep["vritti"]["VIPARYAYA"]
    assert vip["prevalence_pos"] == 12 and vip["prevalence_neg"] == 12     # enough prevalence
    # surface-matched classes -> AUROC near 0.5 -> not confounded -> usable-weak candidate
    assert vip["confounded"] is False
    assert rep["viparyaya_decision"] == "AUDIT_VIPARYAYA_USABLE_WEAK_CANDIDATE"
    assert "vritti:VIPARYAYA" in rep["any_usable_weak"]
    assert "NO LEARNS_SIGNAL" in rep["note"]


def test_low_prevalence_blocks_with_degenerate_label():
    rows = T.rows_from_four_arm(_four_arm_fixture(2), None)              # only 2 viparyaya
    rep = T.usability_report([T.derive_row(r) for r in rows])
    assert rep["vritti"]["VIPARYAYA"]["prevalence_pos"] == 2
    assert rep["viparyaya_decision"] == "AUDIT_VIPARYAYA_DEGENERATE_PREVALENCE"
    assert rep["vritti"]["VIPARYAYA"]["gate"] == "LABELS_DEGENERATE_PREVALENCE"


def test_guna_dims_4_6_masked_in_report():
    rep = T.usability_report([T.derive_row(r) for r in T.rows_from_four_arm(_four_arm_fixture(3), None)])
    for dim in (T.GUNA_NAMES[3], T.GUNA_NAMES[4], T.GUNA_NAMES[5]):
        assert rep["guna"][dim].get("masked") is True


def test_markdown_renders():
    rep = T.usability_report([T.derive_row(r) for r in T.rows_from_four_arm(_four_arm_fixture(10), None)])
    md = T.to_markdown(rep, "robustness_eval_v2.json")
    assert "VIPARYAYA decision" in md and "surface F1" in md
