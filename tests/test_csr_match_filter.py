"""CPU tests for the C×R×S MATCH-filter wrapper (scripts/cg_wrapper_ablation/csr_match_filter/).

Asserts the conceptual contract: phonemes never grant meaning, S is a firewall that overrides high
C/R, C rejects impossible domains, the doctor example frames medicine primary + fruit rejected, the
prompt frame carries primary/secondary/rejected, traces serialise, and NO governance/generation code
is touched. numpy only; no torch/checkpoint.
"""

import json
import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

pytest.importorskip("numpy", reason="numpy required for the match-filter")
import numpy as np  # noqa: E402

from csr_match_filter import (  # noqa: E402
    CSRMatchDecision,
    CSRMatchFilterWrapper,
    CSRMatchTrace,
    CSRThresholds,
    DEFAULT_THRESHOLDS,
    SemanticCoherenceAdapter,
    build_prompt_frame,
    build_trace,
    compute_12d_profile,
    decide,
    score_match,
)

DOMAINS = ["medicine", "care", "authority", "law", "service", "commerce", "fruit"]


# --- the phonemic boundary: sound never grants meaning --------------------------------------------

def test_phoneme_profile_not_treated_as_semantic_truth():
    # 'doctor' realizes medicine strongly via sound (high C and R) ...
    s = score_match("doctor", "medicine")
    assert s.C >= DEFAULT_THRESHOLDS.reject_C and s.R > 0.5
    # ... but if external (non-phonemic) meaning disagrees, S vetoes regardless of C/R.
    low_S = SemanticCoherenceAdapter(curated={("doctor", "medicine"): 0.05}, use_curated=True)
    s2 = score_match("doctor", "medicine", adapter=low_S)
    assert s2.C >= DEFAULT_THRESHOLDS.reject_C          # C did NOT fail
    assert s2.decision == CSRMatchDecision.REJECT_SEMANTIC.value  # S firewall fired


def test_s_veto_overrides_high_cr():
    assert decide(match=0.5, C=0.9, S=0.1) == CSRMatchDecision.REJECT_SEMANTIC
    assert decide(match=0.5, C=0.9, S=0.9) != CSRMatchDecision.REJECT_SEMANTIC


def test_c_veto_rejects_impossible_domain():
    # a profile lighting fruit's BLOCKED lanes (Reasoning/Agency/Purpose) and dark on required ones,
    # with S forced high — C must still reject_ontological (C checked before S).
    vec = np.full(12, 0.1)
    for layer in ("Reasoning", "Agency", "Purpose"):
        vec[["Potential", "Identity", "Execution", "Structure", "Cognition", "Agency", "Reasoning",
             "Purpose", "Witness", "Unifying", "Integration", "Absolving"].index(layer)] = 1.0
    high_S = SemanticCoherenceAdapter(curated={("widget", "fruit"): 0.9}, use_curated=True)
    s = score_match("widget", "fruit", adapter=high_S, term_vec=vec)
    assert s.S >= DEFAULT_THRESHOLDS.reject_S           # S did NOT fail
    assert s.decision == CSRMatchDecision.REJECT_ONTOLOGICAL.value


# --- the doctor example ---------------------------------------------------------------------------

def test_doctor_medicine_primary_fruit_rejected():
    trace = build_trace("Is a doctor a healer or an authority figure?", ["doctor"], DOMAINS)
    assert "medicine" in trace.primary_domains
    assert "fruit" in trace.rejected_domains
    # medicine must out-rank authority, and authority is never primary
    by_dom = {s.domain: s for s in trace.scores}
    assert by_dom["medicine"].match > by_dom["authority"].match
    assert by_dom["authority"].decision != CSRMatchDecision.PRIMARY.value


def test_fruit_rejected_by_semantic_firewall_not_by_suppressing_phonemes():
    # the phoneme profile for doctor still has nonzero realization toward fruit (R>0): rejection is
    # semantic, not a phoneme blackout.
    s = score_match("doctor", "fruit")
    assert s.R > 0.0
    assert s.decision in (CSRMatchDecision.REJECT_SEMANTIC.value,
                          CSRMatchDecision.REJECT_ONTOLOGICAL.value)


# --- frame + trace --------------------------------------------------------------------------------

def test_prompt_frame_contains_primary_secondary_rejected():
    trace = build_trace("q", ["doctor"], DOMAINS)
    frame = build_prompt_frame(trace)
    for section in ("Primary domains:", "Secondary domains:", "Rejected domains:"):
        assert section in frame
    assert "medicine" in frame and "fruit" in frame


def test_trace_serialises_to_json_roundtrip():
    trace = build_trace("q", ["doctor"], DOMAINS)
    text = trace.to_json()
    parsed = json.loads(text)            # valid JSON
    assert parsed["primary_domains"] == trace.primary_domains
    back = CSRMatchTrace.from_json(text)  # round-trips back to dataclasses
    assert back.scores[0].domain == trace.scores[0].domain
    assert back.rejected_domains == trace.rejected_domains


def test_thresholds_match_spec_defaults():
    t = CSRThresholds()
    assert (t.reject_C, t.reject_S, t.primary_match, t.secondary_match,
            t.rewrite_if_answer_alignment_below) == (0.20, 0.20, 0.60, 0.30, 0.40)


def test_wrapper_without_llm_returns_frame_only():
    w = CSRMatchFilterWrapper(llm=None, domains=DOMAINS)
    out = w.answer("Is a doctor a healer or an authority figure?", terms=["doctor"])
    assert out["answer"] is None and "medicine" in out["csr_trace"].primary_domains
    assert "medicine" in out["filtered_domains"]


def test_decision_helpers():
    assert CSRMatchDecision.REJECT_SEMANTIC.is_reject
    assert CSRMatchDecision.PRIMARY.is_frame and not CSRMatchDecision.WEAK.is_frame


# --- guardrails: no governance / no generation-injection code touched -----------------------------

def test_no_governance_or_generation_imports():
    forbidden = ("mistral_wrapper", "unified.train", "model_factory", "governance", "jepa",
                 "trust", "shadow", "parity", "lm_head", "phase_adapter")
    pkg = _ABL / "csr_match_filter"
    for py in pkg.glob("*.py"):
        for ln in py.read_text().splitlines():
            st = ln.strip()
            if st.startswith(("import ", "from ")):
                low = st.lower()
                assert not any(f in low for f in forbidden), f"{py.name}: forbidden import -> {st}"


def test_module_does_not_access_logits_or_state_injection():
    # no code path reads logits or mutates generation hidden state (interpretability/control only)
    pkg = _ABL / "csr_match_filter"
    for py in pkg.glob("*.py"):
        src = py.read_text()
        # allow the words in docstrings/comments, but no attribute access like `.logits`/`.lm_head(`
        assert ".logits" not in src and ".lm_head(" not in src
        assert "adapted_hidden" not in src and "use_guna_bias" not in src
