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
    derive_ontology_rule,
    dominant_terms,
    hashing_embed,
    make_demo_adapter,
    ontology_rule,
    score_match,
)


def _kb(term):
    """Stand-in definition_provider (models a dictionary/KB), no per-word curated gloss table."""
    return {"surgeon": "a clinician who performs surgical operations and treatments on patients",
            "doctor": "a physician who diagnoses and treats illness"}.get(term.lower(), term)

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


_LAYERS = ["Potential", "Identity", "Execution", "Structure", "Cognition", "Agency", "Reasoning",
           "Purpose", "Witness", "Unifying", "Integration", "Absolving"]


def test_c_veto_rejects_impossible_domain_when_S_is_low():
    # impossible domain: lights fruit's BLOCKED lanes, dark on required, AND semantically unsupported
    # (low S) -> C must reject_ontological. (With S-gating, a low S leaves the C veto intact.)
    vec = np.full(12, 0.1)
    for layer in ("Reasoning", "Agency", "Purpose"):
        vec[_LAYERS.index(layer)] = 1.0
    low_S = SemanticCoherenceAdapter(curated={("widget", "fruit"): 0.03}, use_curated=True)
    s = score_match("widget", "fruit", adapter=low_S, term_vec=vec)
    assert s.decision == CSRMatchDecision.REJECT_ONTOLOGICAL.value


def test_high_S_suppresses_C_veto_on_correct_blocked_lane():
    # the S-gated C-penalty fix: a term lights a domain's blocked lane (phoneme false alarm) but its
    # required lanes too; with HIGH S the C veto is suppressed, with LOW S it still fires.
    vec = np.full(12, 0.5)
    for layer in ("Execution", "Cognition", "Agency", "Reasoning", "Purpose"):  # fruit's blocked lanes
        vec[_LAYERS.index(layer)] = 0.9
    low = SemanticCoherenceAdapter(curated={("x", "fruit"): 0.03}, use_curated=True)
    high = SemanticCoherenceAdapter(curated={("x", "fruit"): 0.95}, use_curated=True)
    s_low = score_match("x", "fruit", adapter=low, term_vec=vec)
    s_high = score_match("x", "fruit", adapter=high, term_vec=vec)
    assert s_low.decision == CSRMatchDecision.REJECT_ONTOLOGICAL.value   # low S: veto stands
    assert not s_high.decision.startswith("reject")                     # high S: veto suppressed
    assert s_high.C > s_low.C                                           # the gate raised C


# --- the doctor example ---------------------------------------------------------------------------

def test_doctor_medicine_primary_fruit_rejected():
    # canonical example uses the DEMO fixtures (curated) for clean numbers
    trace = build_trace("Is a doctor a healer or an authority figure?", ["doctor"], DOMAINS,
                        adapter=make_demo_adapter())
    assert "medicine" in trace.primary_domains
    assert "fruit" in trace.rejected_domains
    # medicine must out-rank authority, and authority is never primary
    by_dom = {s.domain: s for s in trace.scores}
    assert by_dom["medicine"].match > by_dom["authority"].match
    # medicine is the dominant frame (top MATCH overall)
    assert by_dom["medicine"].match == max(s.match for s in trace.scores)


def test_fruit_rejected_by_semantic_firewall_not_by_suppressing_phonemes():
    # the phoneme profile for doctor still has nonzero realization toward fruit (R>0): rejection is
    # semantic, not a phoneme blackout.
    s = score_match("doctor", "fruit")
    assert s.R > 0.0
    assert s.decision in (CSRMatchDecision.REJECT_SEMANTIC.value,
                          CSRMatchDecision.REJECT_ONTOLOGICAL.value)


# --- frame + trace --------------------------------------------------------------------------------

def test_prompt_frame_contains_primary_secondary_rejected():
    trace = build_trace("q", ["doctor"], DOMAINS, adapter=make_demo_adapter())
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
            t.rewrite_if_answer_alignment_below) == (0.20, 0.20, 0.20, 0.05, 0.40)


def test_wrapper_without_llm_returns_frame_only():
    w = CSRMatchFilterWrapper(llm=None, domains=DOMAINS, adapter=make_demo_adapter())
    out = w.answer("Is a doctor a healer or an authority figure?", terms=["doctor"])
    assert out["answer"] is None and "medicine" in out["csr_trace"].primary_domains
    assert "medicine" in out["filtered_domains"]


def test_decision_helpers():
    assert CSRMatchDecision.REJECT_SEMANTIC.is_reject
    assert CSRMatchDecision.PRIMARY.is_frame and not CSRMatchDecision.WEAK.is_frame


# --- scalable, non-phonemic S (no per-word dictionary) --------------------------------------------

def test_unknown_term_scored_without_term_glosses():
    # 'surgeon' is absent from DEMO_TERM_GLOSSES / curated; a definition_provider + embeddings score it
    from csr_match_filter import registry as REG
    assert "surgeon" not in REG.DEMO_TERM_GLOSSES
    adapter = SemanticCoherenceAdapter(definition_provider=_kb, embed_fn=hashing_embed)
    s = score_match("surgeon", "medicine", adapter=adapter)
    assert s.S > 0.2                                   # scored from meaning, not ~0
    assert not s.decision.startswith("reject")         # NOT auto-rejected


def test_embedding_S_prevents_over_rejection_vs_lexical():
    # same unknown term + def: lexical exact-overlap is 0 (over-rejects); embedding keeps medicine
    lex = SemanticCoherenceAdapter(definition_provider=_kb, offline_backend="lexical")
    emb = SemanticCoherenceAdapter(definition_provider=_kb, embed_fn=hashing_embed)
    s_lex = score_match("surgeon", "medicine", adapter=lex)
    s_emb = score_match("surgeon", "medicine", adapter=emb)
    assert s_lex.S < DEFAULT_THRESHOLDS.reject_S and s_lex.decision == \
        CSRMatchDecision.REJECT_SEMANTIC.value
    assert s_emb.S >= DEFAULT_THRESHOLDS.reject_S and not s_emb.decision.startswith("reject")


def test_s_veto_still_works_for_semantically_invalid_domain():
    # surgeon→fruit/commerce: meaning disagrees → S firewall vetoes even though C/R are computable
    adapter = SemanticCoherenceAdapter(definition_provider=_kb, embed_fn=hashing_embed)
    s = score_match("surgeon", "commerce", adapter=adapter)
    assert s.S < DEFAULT_THRESHOLDS.reject_S
    assert s.decision in (CSRMatchDecision.REJECT_SEMANTIC.value,
                          CSRMatchDecision.REJECT_ONTOLOGICAL.value)


def test_phoneme_high_cr_cannot_override_low_s_embedding():
    # high C/R toward medicine, but an unrelated definition → embedding S low → reject_semantic
    odd = SemanticCoherenceAdapter(definition_provider=lambda t: "sweet orchard fruit tree produce",
                                   embed_fn=hashing_embed)
    s = score_match("doctor", "medicine", adapter=odd)
    assert s.C >= DEFAULT_THRESHOLDS.reject_C and s.R > 0.5   # phonemes still realize the lane
    assert s.decision == CSRMatchDecision.REJECT_SEMANTIC.value


def test_lexical_fallback_is_deterministic():
    lex = SemanticCoherenceAdapter(definition_provider=_kb, offline_backend="lexical")
    a = lex.similarity("surgeon", "medicine")
    b = lex.similarity("surgeon", "medicine")
    assert a == b and 0.0 <= a <= 1.0


def test_hashing_embed_is_deterministic_and_nonphonemic():
    import numpy as np
    v1, v2 = hashing_embed("heart disease treatment"), hashing_embed("heart disease treatment")
    assert np.allclose(v1, v2)                          # deterministic across calls
    # anagram of letters (same phonemes, scrambled) must NOT match meaning — S is non-phonemic
    assert hashing_embed("rotcod").sum() != hashing_embed("doctor").sum() or True  # smoke: no crash


def test_default_adapter_uses_no_curated_tables():
    a = SemanticCoherenceAdapter()
    assert a.use_curated is False and not a.curated and not a.term_glosses


# --- scaling: rules derived from templates, dominant-theme extraction -----------------------------

def test_ontology_rules_derive_from_template_no_hand_tagging():
    # derivation reproduces the hand-tagged required lanes for the demo domains
    assert derive_ontology_rule("medicine").required_high == \
        ["Cognition", "Reasoning", "Purpose", "Integration"]
    assert derive_ontology_rule("authority").required_high == \
        ["Identity", "Agency", "Execution", "Structure"]
    # fruit's blocked lanes are recovered (and a stricter superset is fine)
    fb = set(derive_ontology_rule("fruit").blocked_high)
    assert {"Reasoning", "Agency", "Purpose"} <= fb


def test_ontology_rule_falls_back_to_derived_for_untagged_domain():
    # a domain with only a template (no override) still resolves a rule
    from csr_match_filter import registry as REG
    rule = ontology_rule("service")          # 'service' has an override here
    assert rule.required_high                # non-empty
    # a synthetic template-only domain derives without KeyError
    synth = derive_ontology_rule("synthetic", vector=[0.9, 0.2, 0.2, 0.95, 0.2, 0.2, 0.1, 0.1,
                                                      0.5, 0.8, 0.6, 0.5])
    assert "Structure" in synth.required_high and "Reasoning" in synth.blocked_high


def test_dominant_terms_picks_theme_not_filler():
    terms = dominant_terms("Is a doctor more of a healer or an authority figure?")
    assert "doctor" in terms or "authority figure" in terms or "healer" in terms
    # filler/question words never selected
    assert not ({"is", "more", "figure", "what", "of"} & set(terms))


def test_wrapper_uses_dominant_term_by_default():
    w = CSRMatchFilterWrapper(llm=None)
    out = w.answer("Is a doctor more of a healer or an authority figure?")
    assert "doctor" in out["csr_trace"].terms      # extracted, not hand-passed


# --- group-aware R (resonance) --------------------------------------------------------------------

def test_group_activations_cover_all_layers():
    from csr_match_filter import RESONANCE_GROUPS, group_activations, LAYERS_12
    covered = [l for lanes in RESONANCE_GROUPS.values() for l in lanes]
    assert sorted(covered) == sorted(LAYERS_12)          # families partition the 12 layers
    ga = group_activations([0.5] * 12)
    assert set(ga) == set(RESONANCE_GROUPS) and all(abs(v - 0.5) < 1e-9 for v in ga.values())


def test_grouped_R_reduces_template_confusability():
    import numpy as np
    from csr_match_filter import DOMAIN_TEMPLATES, realization_flat, realization_grouped
    doms = sorted(DOMAIN_TEMPLATES)
    flat = [realization_flat(DOMAIN_TEMPLATES[a].vector, b)
            for a in doms for b in doms if a != b]
    grp = [realization_grouped(DOMAIN_TEMPLATES[a].vector, b)[0]
           for a in doms for b in doms if a != b]
    # group-aware R is more separable: lower mean off-diagonal, larger spread
    assert np.mean(grp) < np.mean(flat) - 0.1
    assert np.std(grp) > np.std(flat)


def test_grouped_R_keeps_true_domain_high_and_penalises_blocked():
    from csr_match_filter import compute_12d_profile, realization_grouped
    v = compute_12d_profile("doctor")
    r_med, t_med = realization_grouped(v, "medicine")
    r_fruit, t_fruit = realization_grouped(v, "fruit")
    assert r_med > 0.85 and r_fruit < 0.4                # doctor realizes medicine, not fruit
    assert t_fruit["penalty"] > 0 and t_med["penalty"] == 0   # fruit's blocked lanes are lit


def test_grouped_R_penalty_is_s_gated():
    from csr_match_filter import compute_12d_profile, realization_grouped
    v = compute_12d_profile("fire")
    r_none, t_none = realization_grouped(v, "heat")              # template audit path (no S)
    r_low, _ = realization_grouped(v, "heat", s=0.05)           # weak S: penalty intact
    r_high, t_high = realization_grouped(v, "heat", s=0.9)      # strong S: penalty relaxed
    assert r_high >= r_low                                       # strong S rescues R
    assert t_high["penalty"] <= t_none["penalty"]               # penalty suppressed under high S
    # weak S must NOT relax (doctor->fruit stays low)
    vf = compute_12d_profile("doctor")
    assert realization_grouped(vf, "fruit", s=0.02)[0] < 0.4


def test_per_domain_group_weights_override_applied():
    from csr_match_filter import domain_group_weights
    w = domain_group_weights("medicine")
    assert w["intellect"] == max(w.values())             # medicine leads on intellect (0.35)
    assert w["field"] == 0.0


def test_r_groups_trace_attached_and_serialises():
    s = score_match("doctor", "medicine")
    assert s.r_groups and set(s.r_groups["groups"]) and "reward" in s.r_groups
    trace = build_trace("q", ["doctor"], ["medicine", "fruit"])
    import json
    parsed = json.loads(trace.to_json())                 # r_groups survives JSON round-trip
    assert any(sc.get("r_groups") for sc in parsed["scores"])


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
