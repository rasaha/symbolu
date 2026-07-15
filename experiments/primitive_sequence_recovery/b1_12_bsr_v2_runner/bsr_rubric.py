#!/usr/bin/env python3
"""Frozen BSR rubric, aggregation, verdicts, validation, and agreement — pure functions.

Frozen constants mirror B1_12_BSR_VERDICT_AND_ROLE_STABILITY_FREEZE.md (pre-run amendment) and the controlling
preregistration VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md. No model calls here; fully deterministic and unit-tested.
"""
from __future__ import annotations
import re, statistics

BSR_SCALE = (0, 25, 50, 75, 100)

RELATIONSHIP_TYPES = (
    "embodiment", "constitutive_property", "characteristic_expression",
    "implication", "natural_consequence", "generation",
    "opposition", "resolution", "regulation", "containment",
)
_COMPAT_GROUPS = (
    {"embodiment", "constitutive_property", "characteristic_expression"},
    {"implication", "natural_consequence", "generation"},
    {"opposition", "resolution"},
    {"regulation", "containment"},
)

# ---- controlled-vocabulary canonicalization (orthographic typos ONLY; never semantic remapping) ----
def _lev(a, b):
    """Levenshtein edit distance (iterative, O(len(a)*len(b)))."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

def canonicalize_relationship(rel):
    """Map an orthographic variant of a relationship token to its exact taxonomy form.

    Coerces ONLY when the intent is unambiguous: (a) exact match, (b) case/separator normalization
    lands on a taxonomy token, or (c) exactly one taxonomy token is the unique nearest within edit
    distance <=2 of the normalized string. Anything ambiguous or semantically distinct returns
    (None, False) so the caller rejects it as invented_relationship. Returns (canonical|None, coerced).
    """
    if rel in RELATIONSHIP_TYPES:
        return rel, False
    if not isinstance(rel, str):
        return None, False
    norm = re.sub(r"[^a-z]+", "_", rel.strip().lower()).strip("_")
    if norm in RELATIONSHIP_TYPES:
        return norm, True
    if not norm:
        return None, False
    ranked = sorted(((t, _lev(norm, t)) for t in RELATIONSHIP_TYPES), key=lambda x: x[1])
    best_d = ranked[0][1]
    nearest = [t for t, d in ranked if d == best_d]
    if best_d <= 2 and len(nearest) == 1:
        return nearest[0], True
    return None, False

# ---- component aggregation & word verdict (mechanical; combined never changes verdict) ----
def aggregate(scores):
    """scores: list[int] in BSR_SCALE. Returns dict(mean,min,counts)."""
    assert scores, "no component scores"
    assert all(s in BSR_SCALE for s in scores), f"score outside BSR_SCALE: {scores}"
    return {
        "mean": round(sum(scores) / len(scores), 2),
        "min": min(scores),
        "n": len(scores),
        "counts": {str(v): scores.count(v) for v in BSR_SCALE},
        "weak_components_le_25": sum(1 for s in scores if s <= 25),
    }

def word_verdict(mean, min_):
    if mean >= 75 and min_ >= 50:
        return "STRONG_RESONANCE"
    if mean >= 50:
        return "MODERATE_RESONANCE"
    if mean >= 30:
        return "WEAK_RESONANCE"
    if mean >= 15:
        return "MINIMAL_RESONANCE"
    return "NO_RESONANCE"

_VERDICT_BAND = {"NO_RESONANCE": 0, "MINIMAL_RESONANCE": 1, "WEAK_RESONANCE": 2,
                 "MODERATE_RESONANCE": 3, "STRONG_RESONANCE": 4}

def holistic_only(combined_reconciliation, mean):
    return bool(combined_reconciliation is not None and combined_reconciliation >= 75 and mean < 50)

# ---- validation of raw model outputs (reject/retry reasons; never for unfavorable score) ----
def validate_author(obj, occ_indices):
    """Author (profile+evidence). Returns (ok, reason)."""
    if not isinstance(obj, dict):
        return False, "malformed_json"
    if not str(obj.get("profile", "")).strip():
        return False, "missing_field:profile"
    comps = obj.get("components")
    if not isinstance(comps, list) or len(comps) != len(occ_indices):
        return False, "missing_field:components"
    for c in comps:
        if not isinstance(c, dict):
            return False, "malformed_json"
        if c.get("occurrence_index") not in occ_indices:
            return False, "missing_field:occurrence_index"
        if not str(c.get("supporting_evidence", "")).strip():
            return False, "missing_evidence:supporting"
        if not str(c.get("opposing_evidence", "")).strip():
            return False, "missing_evidence:opposing"
        rel = c.get("proposed_relationship")
        if rel not in RELATIONSHIP_TYPES:
            return False, "invented_relationship"
    return True, ""

def validate_judge(obj, occ_indices):
    """V2 independent judge: ONE model produces profile + per-occurrence evidence, relationship, and DBR score in a
    single blind judgment (no author/scorer split). Returns (ok, reason). Never rejects for an unfavorable score."""
    if not isinstance(obj, dict):
        return False, "malformed_json"
    if not str(obj.get("profile", "")).strip():
        return False, "missing_field:profile"
    comps = obj.get("components")
    if not isinstance(comps, list) or len(comps) != len(occ_indices):
        return False, "missing_field:components"
    for c in comps:
        if not isinstance(c, dict):
            return False, "malformed_json"
        if c.get("occurrence_index") not in occ_indices:
            return False, "missing_field:occurrence_index"
        if not str(c.get("supporting_evidence", "")).strip():
            return False, "missing_evidence:supporting"
        if not str(c.get("opposing_evidence", "")).strip():
            return False, "missing_evidence:opposing"
        if c.get("relationship") not in RELATIONSHIP_TYPES:
            return False, "invented_relationship"
        if c.get("dbr_score") not in BSR_SCALE:
            return False, "invalid_score"
        if not str(c.get("adjudication", "")).strip():
            return False, "missing_evidence:adjudication"
    return True, ""

def validate_scorer(obj, occ_indices, frozen_glosses):
    """Scorer (final relationship + score + adjudication + combined). Returns (ok, reason)."""
    if not isinstance(obj, dict):
        return False, "malformed_json"
    comps = obj.get("components")
    if not isinstance(comps, list) or len(comps) != len(occ_indices):
        return False, "missing_field:components"
    for c in comps:
        if not isinstance(c, dict):
            return False, "malformed_json"
        oi = c.get("occurrence_index")
        if oi not in occ_indices:
            return False, "missing_field:occurrence_index"
        if c.get("bsr_score") not in BSR_SCALE:
            return False, "invalid_score"
        if c.get("final_relationship") not in RELATIONSHIP_TYPES:
            return False, "invented_relationship"
        if not str(c.get("adjudication", "")).strip():
            return False, "missing_evidence:adjudication"
        # the scorer must not modify the frozen gloss it was given
        if oi in frozen_glosses and "mapping_gloss" in c and c["mapping_gloss"] != frozen_glosses[oi]:
            return False, "modified_mapping_gloss"
    cr = obj.get("combined_reconciliation")
    if cr is not None and not (isinstance(cr, (int, float)) and 0 <= cr <= 100):
        return False, "invalid_combined"
    return True, ""

# ---- agreement (mechanical, cross-run) ----
_WORD = re.compile(r"[a-zā-ˑぁ-ヿ\w]+", re.UNICODE)
def _content_tokens(text):
    stop = {"the", "a", "an", "of", "to", "and", "or", "is", "its", "it", "in", "on", "that", "which",
            "as", "with", "for", "meaning", "ordinary", "stable", "word", "bare"}
    return {t for t in re.findall(r"[^\W\d_]+", str(text).lower(), re.UNICODE) if t not in stop and len(t) > 2}

def profile_similarity(a, b):
    ta, tb = _content_tokens(a), _content_tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)

def profile_agreement_label(sim):
    return "same" if sim >= 0.60 else "minor_difference" if sim >= 0.30 else "material_difference"

def relationship_agreement(rel_a, rel_b):
    if rel_a == rel_b:
        return "exact"
    for g in _COMPAT_GROUPS:
        if rel_a in g and rel_b in g:
            return "compatible"
    return "incompatible"

def score_step_agreement(sa, sb):
    d = abs(sa - sb)
    return {"exact": d == 0, "within_one_step": d <= 25, "abs_diff": d, "ge50": d >= 50}

def cross_run_word_indeterminate(verdict_a, verdict_b, mean_a, mean_b):
    band_gap = abs(_VERDICT_BAND[verdict_a] - _VERDICT_BAND[verdict_b])
    return band_gap >= 2 or abs(mean_a - mean_b) >= 50

def role_dependence(exact_verdict_agree, one_step_component_agree, n_material_profile_disagree,
                    signed_mean_component_diff, invalid=False):
    """All fractions in [0,1]; signed_mean_component_diff = mean(A-B) over components."""
    if invalid:
        return "RUN_INVALID"
    systematic = abs(signed_mean_component_diff) >= 15
    if (exact_verdict_agree >= 0.80 and one_step_component_agree >= 0.80
            and n_material_profile_disagree <= 2 and not systematic):
        return "ROLE_STABLE"
    if exact_verdict_agree < 0.60 or one_step_component_agree < 0.60 or systematic:
        return "SIGNIFICANT_ROLE_DEPENDENCE"
    return "MINOR_ROLE_DEPENDENCE"
