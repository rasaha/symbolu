"""CPU tests for the Phase 3 real-output audit comparison harness (eval_real_output_audit.py).

These exercise the MEASUREMENT-only mapping fixes on a SYNTHETIC robustness-trace fixture (no GPU, no
saved real traces required): category-union mapping (secondary->spp|rdp, factuality->fs|generic),
refutation-not-a-leak rescue, the serialized manual/audit-correct disagreement section, the
meta-parroting detector + Phase 4 label docs, the MEASUREMENT_CORRECTED decision, and guards that the
frozen Phase 1 thresholds and Phase 3 audit rules are untouched.
"""

import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

pytest.importorskip("numpy", reason="numpy required")

from csr_match_filter import answer_audit as AA                 # noqa: E402
from csr_match_filter import eval_real_output_audit as RO        # noqa: E402
from csr_match_filter import CSRThresholds                        # noqa: E402

_PHASE4_DOC = Path(__file__).resolve().parent.parent / "docs" / \
    "CSR_MATCH_FILTER_PHASE4_HIDDEN_STATE_PROBE.md"


def _rubric(primary_ok=True, rej_avoid=True, sec_promoted=False, phon=False, fact_ok=True):
    return {"primary_frame_correct": primary_ok, "rejected_domain_avoidance": rej_avoid,
            "secondary_promoted": sec_promoted, "phoneme_overreach": phon,
            "factuality_preserved": fact_ok, "clarity_score": 1.0, "must_include_recall": 1.0,
            "must_not_violation_rate": 0.0, "secondary_handling_correct": primary_ok}


def _row(id_, query, answer, rubric, primary, rejected, alt=None, false_claims=None, sec=None):
    ex = {"id": id_, "query": query, "category": "t", "expected_primary": primary,
          "expected_secondary": sec or [], "expected_rejected": rejected,
          "expected_secondary_true_senses": alt or [], "false_claims": false_claims or []}
    trace_row = {"id": id_, "category": "t", "answers": {"framed": answer},
                 "scores": {"framed": rubric}}
    return ex, trace_row


def _run(cases):
    by_id = {c[0]["id"]: c[0] for c in cases}
    rows = [c[1] for c in cases]
    return RO.run_arm(rows, by_id, "framed")


# --- Fix 1: category-union mapping ---------------------------------------------------------------

def test_secondary_promoted_maps_to_spp_or_rdp():
    # rubric flags secondary_promoted; the audit reports it as rejected_domain_promoted (primary
    # absent). Union mapping must count this as caught, not a miss.
    ex, tr = _row("t_rdp", "What is a doctor?",
                  "A doctor is basically about business, market, and trade above all.",
                  _rubric(primary_ok=False, rej_avoid=False, sec_promoted=True),
                  primary=["medicine"], rejected=["commerce"])
    per = _run([(ex, tr)])
    assert "rejected_domain_promoted" in per[0]["ft"]
    assert per[0]["audit"]["secondary_promoted"] is True            # union credited
    conf = RO.confusion(per)
    assert conf["secondary_promoted"]["tp"] == 1 and conf["secondary_promoted"]["fn"] == 0


def test_factuality_maps_to_factuality_or_generic():
    # rubric flags factuality failure on a short meta-stub; the audit reports answer_too_generic.
    ex, tr = _row("t_fact", "What is a doctor?", "Primary domain: medicine",
                  _rubric(primary_ok=False, fact_ok=False), primary=["medicine"], rejected=["commerce"])
    per = _run([(ex, tr)])
    assert "answer_too_generic" in per[0]["ft"]
    assert per[0]["audit"]["factuality_suspected"] is True          # union credited
    conf = RO.confusion(per)
    assert conf["factuality_suspected"]["tp"] == 1 and conf["factuality_suspected"]["fn"] == 0


# --- Fix 1b: refutation is not a leak ------------------------------------------------------------

def test_refutation_is_not_counted_as_rejected_leak():
    ex, tr = _row("t_ref", "Is a doctor furniture?",
                  "A doctor is not furniture; a doctor provides treatment, healing, and clinical care.",
                  _rubric(rej_avoid=False),                          # rubric over-flags a leak
                  primary=["medicine"], rejected=["furniture"])
    per = _run([(ex, tr)])
    assert "rejected_domain_mentioned_as_refutation" in per[0]["ft"]
    assert per[0]["audit"]["rejected_leak"] is False
    conf = RO.confusion(per)
    # rescued out of FN, surfaced under rubric_overflag_refutation
    assert conf["rejected_leak"]["fn"] == 0
    assert len(conf["rejected_leak"]["rubric_overflag_refutation"]) == 1


# --- Fix 2: manual/audit-correct disagreement section --------------------------------------------

def test_manual_disagreements_serialized_for_present_ids():
    ex, tr = _row("rej_009", "Is a farmer furniture?",
                  "A farmer is not furniture; a farmer involves treatment.",   # text irrelevant here
                  _rubric(rej_avoid=False), primary=["medicine"], rejected=["furniture"])
    per = _run([(ex, tr)])
    md = RO.manual_disagreements(per)
    assert "rej_009" in md and md["rej_009"]["manual_verdict"] == "audit_correct"
    assert "close_004" not in md                                    # only ids present in the run


def test_manual_correct_excluded_from_true_misses():
    # rej_009 flagged by rubric as leak, audit says refutation; must NOT appear as a true miss
    ex, tr = _row("rej_009", "Is a farmer furniture?",
                  "A farmer is not furniture; a farmer provides treatment and clinical healing.",
                  _rubric(rej_avoid=False), primary=["medicine"], rejected=["furniture"])
    em = RO.extra_metrics(_run([(ex, tr)]))
    assert all(m["id"] != "rej_009" for m in em["remaining_true_misses"])


# --- meta-parroting detector + Phase 4 docs ------------------------------------------------------

def test_meta_parrot_detector():
    assert RO.is_meta_parrot("The term 'apple' belongs to the primary domain of fruit.")
    assert RO.is_meta_parrot("Primary domain: medicine / Secondary domain: none")
    assert RO.is_meta_parrot("The term bank belongs to the domain of finance.")
    assert not RO.is_meta_parrot("A doctor heals patients and treats illness in a clinic.")


def test_meta_parrot_reported_and_excluded_from_true_misses():
    ex, tr = _row("poly_x", "What is apple?",
                  "The term 'apple' belongs to the primary domain of fruit.",
                  _rubric(primary_ok=False, sec_promoted=True), primary=["fruit"],
                  rejected=["commerce"], alt=["technology"])
    per = _run([(ex, tr)])
    assert per[0]["meta_parrot"] is True
    em = RO.extra_metrics(per)
    assert em["meta_parroting_n"] == 1
    assert all(m["id"] != "poly_x" for m in em["remaining_true_misses"])


def test_phase4_doc_has_meta_parroting_labels():
    txt = _PHASE4_DOC.read_text()
    assert "meta_parroting" in txt or "meta-parroting" in txt
    assert "frame_echo" in txt or "frame_label_parroting" in txt


# --- decision label, incl. MEASUREMENT_CORRECTED -------------------------------------------------

def _conf(tp, fn):
    base = {c: {"tp": 0, "fn": 0} for c in RO.CATS}
    base["off_frame"] = {"tp": tp, "fn": fn}
    return base


def test_decide_measurement_corrected_and_pass():
    # recall 0.80 + safe -> PASS
    assert RO.decide(True, _conf(8, 2),
                     {"false_rewrite_rate": 0.0, "missed_critical_failure_rate": 0.0,
                      "remaining_true_misses": []})[0] == "PHASE3_REAL_OUTPUT_AUDIT_PASS"
    # recall 0.5 but safe and remaining true misses <=3 -> MEASUREMENT_CORRECTED
    assert RO.decide(True, _conf(5, 5),
                     {"false_rewrite_rate": 0.0, "missed_critical_failure_rate": 0.0,
                      "remaining_true_misses": [{"id": "x"}]})[0] == \
        "PHASE3_REAL_OUTPUT_AUDIT_MEASUREMENT_CORRECTED"
    # missed critical -> NEEDS_TUNING (not safe)
    assert RO.decide(True, _conf(5, 5),
                     {"false_rewrite_rate": 0.0, "missed_critical_failure_rate": 0.5,
                      "remaining_true_misses": [{"id": "x"}] * 6})[0] == \
        "PHASE3_REAL_OUTPUT_AUDIT_NEEDS_TUNING"
    # stub provenance gate
    assert RO.decide(False, _conf(8, 2),
                     {"false_rewrite_rate": 0.0, "missed_critical_failure_rate": 0.0,
                      "remaining_true_misses": []})[0] == \
        "PHASE3_REAL_OUTPUT_AUDIT_BLOCKED_NO_REAL_TRACES"


# --- harness loads robustness JSON schema --------------------------------------------------------

def test_iter_traces_reads_robustness_schema():
    blob = {"meta": {}, "backends": {"mistral": {"production_valid": True}},
            "traces": {"mistral": [{"id": "a", "answers": {"framed": "x"}, "scores": {"framed": {}}}]}}
    got = list(RO._iter_traces(blob))
    assert got and got[0][0] == "mistral" and got[0][1] is True and len(got[0][2]) == 1


# --- guards: frozen scorer + audit rules unchanged -----------------------------------------------

def test_phase1_thresholds_unchanged():
    thr = CSRThresholds()
    assert thr.primary_match == 0.20 and thr.secondary_match == 0.05


def test_audit_rules_unchanged():
    # taxonomy + severity->confidence map are the frozen Phase 3 contract
    assert set(AA.FINDING_TYPES) == {
        "frame_compliant", "primary_frame_missing", "secondary_promoted_to_primary",
        "rejected_domain_promoted", "rejected_domain_mentioned_as_refutation",
        "alternate_true_sense_allowed", "phoneme_overreach_claim", "factuality_suspected",
        "answer_too_generic"}
    assert AA._SEV_CONF == {"info": 0.2, "warning": 0.5, "error": 0.8, "critical": 0.9}
    # a canonical compliant answer still audits as compliant + passed
    res = AA.audit_answer("What is a doctor?",
                          "A doctor primarily involves medicine, clinical, and cure here.",
                          {"primary_domains": ["medicine"], "secondary_domains": [],
                           "rejected_domains": ["commerce"]})
    assert set(res.finding_types) == {"frame_compliant"} and res.passed and not res.needs_rewrite
