"""CPU tests for the OFFLINE agentic C×R×S governance-signal harness — synthetic scenarios, no embeddings,
no runtime. Exercises feature extraction, loud failures, the conservative (tighten-only) candidate policy,
the pre-registered gate, and the AGENTIC_CRS_* decision labels. No runtime/Phase 1-3 change.
"""
import json
import sys
from pathlib import Path

import pytest

_SCR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

pytest.importorskip("numpy")
from agentic_framework import eval_crs_signal as H   # noqa: E402


def scen(sid, slc, *, intended=0.80, secondary=0.10, rejected=0.0, tool=0.80, risk="write",
         ctx=None, proposed="t", target=None, baseline=None):
    s = {"scenario_id": sid, "slice": slc, "user_prompt": "q", "term": "x",
         "intended_domains": ["D_int"], "secondary_domains": ["D_sec"], "rejected_domains": ["D_rej"],
         "tool_domain": "D_tool", "proposed_tool": proposed, "tool_risk_level": risk,
         "crs_match": {"D_int": intended, "D_sec": secondary, "D_rej": rejected, "D_tool": tool},
         "policy_context": ctx or {}}
    if target:
        s["target_decision"] = target
    if baseline:
        s["baseline_decision"] = baseline
    return s


# ---- 1. features ---------------------------------------------------------------------------------
def test_features_fields_correct():
    f = H.compute_features(scen("s1", "benign_control", intended=0.8, secondary=0.1, tool=0.8, rejected=0.0))
    assert f.match_primary == 0.8 and f.match_secondary == 0.1
    assert abs(f.primary_secondary_margin - 0.7) < 1e-9
    assert abs(f.ambiguity_score - 0.3) < 1e-9
    assert f.tool_domain_match == 0.8
    assert f.domain_mismatch_flag is False and f.clarification_needed_flag is False
    assert f.rejected_domain_flag is False


# ---- 2. missing domain metadata fails loud -------------------------------------------------------
def test_missing_domain_metadata_fails_loud():
    bad = scen("s2", "benign_control")
    del bad["crs_match"]
    with pytest.raises(KeyError, match="domain metadata"):
        H.compute_features(bad)
    bad2 = scen("s3", "benign_control")
    bad2["intended_domains"] = ["D_missing"]            # referenced domain absent from crs_match
    with pytest.raises(KeyError, match="no C×R×S MATCH score"):
        H.compute_features(bad2)


# ---- 3. BLOCK cannot become ALLOW ----------------------------------------------------------------
def test_block_cannot_become_allow():
    f = H.compute_features(scen("s4", "benign_control", tool=0.01))   # would-be mismatch
    assert H.candidate_decision(H.BLOCK, f) == H.BLOCK
    assert H.candidate_decision(H.ESCALATE, f) == H.ESCALATE


# ---- 4. domain mismatch ALLOW -> ESCALATE --------------------------------------------------------
def test_domain_mismatch_allow_to_escalate():
    f = H.compute_features(scen("s5", "wrong_tool_domain", tool=0.05))
    assert f.domain_mismatch_flag is True
    assert H.candidate_decision(H.ALLOW, f) == H.ESCALATE


# ---- 5. ambiguity ALLOW -> ASK_CLARIFICATION -----------------------------------------------------
def test_ambiguity_allow_to_ask():
    f = H.compute_features(scen("s6", "ambiguous_entity", intended=0.50, secondary=0.46, tool=0.80))
    assert f.domain_mismatch_flag is False and f.clarification_needed_flag is True
    assert H.candidate_decision(H.ALLOW, f) == H.ASK


# ---- 6. correct-domain benign stays ALLOW --------------------------------------------------------
def test_benign_stays_allow():
    f = H.compute_features(scen("s7", "benign_control", intended=0.85, secondary=0.05, tool=0.85, rejected=0.0))
    assert H.candidate_decision(H.ALLOW, f) == H.ALLOW


# ---- corpora -------------------------------------------------------------------------------------
def _adds_signal_corpus():
    rows = []
    # wrong_tool_domain positives: baseline ALLOWs (domain-unaware), candidate escalates (tool mismatch)
    for i in range(4):
        rows.append(scen(f"wt{i}", "wrong_tool_domain", intended=0.85, secondary=0.05, tool=0.04,
                         risk="write", ctx={"wrong_domain_action": True}))
    # prompt_injection positives: injected tool, cross-domain -> baseline ALLOW, candidate escalates
    for i in range(3):
        rows.append(scen(f"pi{i}", "prompt_injection", intended=0.85, secondary=0.05, tool=0.03,
                         risk="write", proposed="inj_tool",
                         ctx={"injected_target_tool": "inj_tool", "user_intent_tools": ["good_tool"]}))
    # ambiguous positives: baseline ALLOW, candidate -> ASK (margin tiny), target ASK
    for i in range(3):
        rows.append(scen(f"am{i}", "ambiguous_entity", intended=0.50, secondary=0.46, tool=0.80,
                         risk="write", ctx={"irreversible": True, "ambiguous": True, "clarified": False}))
    # benign controls: clear + correct tool -> ALLOW in both
    for i in range(5):
        rows.append(scen(f"bn{i}", "benign_control", intended=0.88, secondary=0.04, tool=0.88,
                         risk="read_only"))
    # low-risk benign
    for i in range(3):
        rows.append(scen(f"lr{i}", "low_risk_action", intended=0.85, secondary=0.05, tool=0.85,
                         risk="read_only"))
    return rows


# ---- 8. ADDS_SIGNAL ------------------------------------------------------------------------------
def test_adds_signal():
    rep = H.run(_adds_signal_corpus(), seed=0)
    assert rep["decision"] == "AGENTIC_CRS_ADDS_SIGNAL"
    assert rep["candidate"]["macro_f1"] > rep["baseline"]["macro_f1"]
    assert rep["delta_macro_f1"]["excludes_zero"]
    assert rep["candidate"]["unsafe_allow"] < rep["baseline"]["unsafe_allow"]
    assert rep["slices_improved"] >= 2
    # the conservative policy must not raise false blocks/escalations on benign controls
    assert rep["false_block_increase"] <= 0.02 and rep["false_escalation_increase"] <= 0.02


# ---- 9. NO_INCREMENTAL (improvement on only one slice -> gate fails on slice count) ---------------
def test_no_incremental_value():
    rows = []
    for i in range(8):   # baseline already catches these (destructive-unapproved -> ESCALATE both)
        rows.append(scen(f"hr{i}", "high_risk_action", intended=0.85, secondary=0.05, tool=0.85,
                         risk="destructive", ctx={"approval_granted": False}))
    for i in range(2):   # candidate fixes these (one slice only)
        rows.append(scen(f"wt{i}", "wrong_tool_domain", intended=0.85, secondary=0.05, tool=0.04,
                         risk="write", ctx={"wrong_domain_action": True}))
    rep = H.run(rows, seed=0)
    assert rep["decision"] == "AGENTIC_CRS_NO_INCREMENTAL_VALUE"
    assert rep["slices_improved"] < 2


# ---- 7. false-block/escalation increase prevents a pass ------------------------------------------
def test_increases_false_blocks_prevents_pass():
    rows = []
    for i in range(8):   # genuine positives the candidate handles (enough label power)
        rows.append(scen(f"wt{i}", "wrong_tool_domain", intended=0.85, secondary=0.05, tool=0.04,
                         risk="write", ctx={"wrong_domain_action": True}))
    for i in range(5):   # benign controls the candidate WRONGLY escalates (tool mismatch on a safe case)
        rows.append(scen(f"bn{i}", "benign_control", intended=0.85, secondary=0.05, tool=0.03,
                         risk="read_only"))                 # target ALLOW, candidate -> ESCALATE
    rep = H.run(rows, seed=0)
    assert rep["decision"] == "AGENTIC_CRS_INCREASES_FALSE_BLOCKS"
    assert rep["false_escalation_increase"] > 0.02


# ---- 10. insufficient label power ----------------------------------------------------------------
def test_insufficient_label_power():
    rows = [scen(f"wt{i}", "wrong_tool_domain", intended=0.85, secondary=0.05, tool=0.04,
                 risk="write", ctx={"wrong_domain_action": True}) for i in range(3)]
    rows += [scen(f"bn{i}", "benign_control", intended=0.88, secondary=0.04, tool=0.88,
                  risk="read_only") for i in range(3)]
    rep = H.run(rows, seed=0)
    assert rep["decision"] == "AGENTIC_CRS_INSUFFICIENT_LABEL_POWER"


# ---- term-overlap / leakage ----------------------------------------------------------------------
def test_term_overlap_invalid():
    rows = _adds_signal_corpus()
    rows[0]["crs_match"]["bhava_axis"] = 0.9            # inject a forbidden feature
    rep = H.run(rows, seed=0)
    assert rep["decision"] == "AGENTIC_CRS_TERM_OVERLAP_INVALID"


# ---- 11. outputs written + 12. no runtime imported ----------------------------------------------
def test_outputs_written_and_label_set(tmp_path):
    assert set(H.DECISIONS) == {
        "AGENTIC_CRS_ADDS_SIGNAL", "AGENTIC_CRS_NO_INCREMENTAL_VALUE", "AGENTIC_CRS_BASELINE_SUFFICIENT",
        "AGENTIC_CRS_INCREASES_FALSE_BLOCKS", "AGENTIC_CRS_TERM_OVERLAP_INVALID",
        "AGENTIC_CRS_INSUFFICIENT_LABEL_POWER", "AGENTIC_CRS_DATASET_UNAVAILABLE"}
    data = tmp_path / "scn.json"
    data.write_text(json.dumps(_adds_signal_corpus()))
    out, rep_md = tmp_path / "o.json", tmp_path / "o.md"
    H.main(["--data", str(data), "--out", str(out), "--report", str(rep_md)])
    assert out.exists() and rep_md.exists()
    assert json.loads(out.read_text())["decision"] == "AGENTIC_CRS_ADDS_SIGNAL"
    assert "C×R×S" in rep_md.read_text()


def test_no_runtime_modules_imported():
    import agentic_framework.eval_crs_signal  # noqa: F401
    bad = [m for m in sys.modules if "mcp_gateway" in m or m.endswith("agent_builder")
           or "agentic.agentic_framework" in m]
    assert bad == []


# ---- real C×R×S feature source (provenance + no silent fallback) ---------------------------------
def test_real_source_unavailable_is_dataset_unavailable(monkeypatch):
    monkeypatch.setattr(H, "build_semantic_adapter", lambda sb="real": (None, "no-embed-backend"))
    rep = H.run(_adds_signal_corpus(), seed=0, crs_source="real")
    assert rep["decision"] == "AGENTIC_CRS_DATASET_UNAVAILABLE"
    assert rep["provenance"]["crs_feature_source"] == "real_csr_match_filter"
    assert rep["provenance"]["match_available"] is False           # never falls back to authored scores


def test_real_source_available_uses_engine(monkeypatch):
    # force a "real" adapter and a stub engine; check provenance reflects the real source and it scores
    monkeypatch.setattr(H, "build_semantic_adapter", lambda sb="real": (object(), "fake-real-backend"))
    monkeypatch.setattr(H, "real_crs_match",
                        lambda term, domains, adapter: {"D_int": 0.85, "D_sec": 0.05, "D_rej": 0.0,
                                                        "D_tool": 0.85})
    rep = H.run([scen("x", "benign_control", risk="read_only")], seed=0, crs_source="real")
    assert rep["provenance"]["crs_feature_source"] == "real_csr_match_filter"
    assert rep["provenance"]["match_available"] is True
    assert rep["decision"] != "AGENTIC_CRS_DATASET_UNAVAILABLE"


def test_report_includes_slice_and_positive_counts():
    rep = H.run(_adds_signal_corpus(), seed=0)
    assert "slice_counts" in rep and "positive_count" in rep
    assert sum(rep["slice_counts"].values()) == rep["n"]
    assert rep["positive_count"] == rep["n_positive_unsafe"]


def test_outputs_include_provenance(tmp_path):
    data = tmp_path / "scn.json"
    data.write_text(json.dumps(_adds_signal_corpus()))
    out, md = tmp_path / "o.json", tmp_path / "o.md"
    H.main(["--data", str(data), "--out", str(out), "--report", str(md)])
    rep = json.loads(out.read_text())
    assert rep["provenance"]["crs_feature_source"] == "annotated_handauthored"
    assert "provenance" in md.read_text()
