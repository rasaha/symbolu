"""Noise taxonomy implementation (Phase 3). 25 controlled perturbations of a SignalBundle, each
with a severity in [0,1] and a `detectable` flag: DETECTABLE perturbations lower a meta-signal
(confidence / calibration / freshness / conflict / provenance) so an uncertainty-propagating gate
can respond; SILENT ones flip a value while leaving confidence high, so any gate is fooled. This
detectable/silent split is the crux of the study.

Deterministic: perturbations are pure functions of (bundle, severity). Which items get perturbed is
chosen deterministically by the dataset, not here.
"""
from __future__ import annotations

import copy
from dataclasses import replace
from typing import Callable, Dict, Tuple

from assertion_gate_robustness.signals import SignalBundle, RISK_ORDER

_RISK = ["low", "medium", "high", "critical"]


def _clone(b: SignalBundle) -> SignalBundle:
    return copy.deepcopy(b)


def _shift_risk(rc: str, delta: int) -> str:
    i = max(0, min(3, RISK_ORDER[rc] + delta))
    return _RISK[i]


# Each perturbation: (fn, detectable). fn(bundle, severity) -> new bundle.

def p_grounding_fp(b, s):  # falsely raise support (silent overclaim of support)
    b = _clone(b); b.grounding.support = min(1.0, b.grounding.support + s * 0.7); return b

def p_grounding_fn(b, s):  # falsely lower support
    b = _clone(b); b.grounding.support = max(0.0, b.grounding.support - s * 0.7); return b

def p_entail_fp(b, s):     # flip toward 'supports' falsely
    b = _clone(b)
    if s > 0.25 and b.entailment.label != "supports":
        b.entailment.label = "supports"; b.entailment.confidence = max(b.entailment.confidence, 0.8)
    return b

def p_entail_fn(b, s):     # flip away from 'supports' falsely
    b = _clone(b)
    if s > 0.25 and b.entailment.label == "supports":
        b.entailment.label = "neutral"
    return b

def p_risk_under(b, s):    # underclassify risk (dangerous)
    b = _clone(b)
    if s > 0.2:
        b.risk_class = _shift_risk(b.risk_class, -1 if s < 0.5 else -2)
    return b

def p_risk_over(b, s):     # overclassify risk (over-blocking)
    b = _clone(b)
    if s > 0.2:
        b.risk_class = _shift_risk(b.risk_class, 1 if s < 0.5 else 2)
    return b

def p_stale(b, s):         # stale evidence (DETECTABLE via freshness)
    b = _clone(b); b.evidence.age_days = b.evidence.required_recency_days * (1 + s * 5); return b

def p_irrelevant(b, s):    # irrelevant retrieval: support up but adequacy down (DETECTABLE via adequacy)
    b = _clone(b); b.grounding.support = min(1.0, b.grounding.support + s * 0.4)
    b.evidence.adequacy = max(0.0, b.evidence.adequacy - s * 0.7); return b

def p_partial(b, s):       # partial evidence (DETECTABLE via adequacy)
    b = _clone(b); b.evidence.adequacy = max(0.0, b.evidence.adequacy - s * 0.6); return b

def p_contradict(b, s):    # contradictory evidence (DETECTABLE via conflict)
    b = _clone(b); b.evidence.conflict = "major" if s > 0.4 else "minor"; return b

def p_authority(b, s):     # source-authority mismatch (DETECTABLE via authority)
    b = _clone(b); b.evidence.authority = "unauthorized" if s > 0.4 else "unknown"; return b

def p_no_provenance(b, s): # missing provenance (DETECTABLE)
    b = _clone(b)
    if s > 0.3: b.evidence.provenance_present = False
    return b

def p_miscalibrated(b, s): # confidence miscalibration: high confidence, low calibration (SILENT-ish)
    b = _clone(b); b.grounding.confidence = min(1.0, b.grounding.confidence + s * 0.3)
    b.grounding_calibration = max(0.0, b.grounding_calibration - s * 0.6); return b

def p_correlated(b, s):    # correlated failure: grounding+entailment both wrong same way (SILENT)
    b = _clone(b); b.grounding.support = min(1.0, b.grounding.support + s * 0.6)
    if s > 0.25: b.entailment.label = "supports"; b.entailment.confidence = 0.85
    return b  # confidence stays HIGH -> undetectable

def p_disagree(b, s):      # independent disagreement: grounding high, entailment contradicts (DETECTABLE)
    b = _clone(b); b.grounding.support = min(1.0, b.grounding.support + s * 0.3)
    if s > 0.25: b.entailment.label = "contradicts"; b.entailment.confidence = 0.6
    return b

def p_decomp_error(b, s):  # claim decomposition error -> adequacy drop + minor conflict (DETECTABLE)
    b = _clone(b); b.evidence.adequacy = max(0.0, b.evidence.adequacy - s * 0.4)
    if s > 0.4: b.evidence.conflict = "minor"
    return b

def p_multiclaim(b, s):    # multi-claim contamination -> adequacy down, entailment confidence down
    b = _clone(b); b.evidence.adequacy = max(0.0, b.evidence.adequacy - s * 0.3)
    b.entailment.confidence = max(0.0, b.entailment.confidence - s * 0.4); return b

def p_missing_as_negative(b, s):  # missing evidence represented as contradiction (SILENT, dangerous)
    b = _clone(b)
    if s > 0.3: b.entailment.label = "contradicts"; b.entailment.confidence = 0.8
    b.grounding.support = max(0.0, b.grounding.support - s * 0.5); return b

def p_domain_mis(b, s):    # domain misclassification -> risk shift (like risk noise)
    return p_risk_under(b, s)

def p_adversarial(b, s):   # adversarially phrased -> falsely high support+entailment, high conf (SILENT)
    b = _clone(b); b.grounding.support = min(1.0, b.grounding.support + s * 0.8)
    b.entailment.label = "supports"; b.entailment.confidence = min(1.0, 0.7 + s * 0.3); return b

def p_narrower(b, s):      # evidence supports only a narrower claim (DETECTABLE via adequacy)
    b = _clone(b); b.evidence.adequacy = max(0.0, b.evidence.adequacy - s * 0.5); return b

def p_population(b, s):    # supports population not individual (DETECTABLE via adequacy/scope)
    b = _clone(b); b.evidence.adequacy = max(0.0, b.evidence.adequacy - s * 0.55); return b

def p_none(b, s):          # no perturbation (clean)
    return _clone(b)


# registry: name -> (fn, detectable)
PERTURBATIONS: Dict[str, Tuple[Callable, bool]] = {
    "clean": (p_none, True),
    "grounding_fp": (p_grounding_fp, False),
    "grounding_fn": (p_grounding_fn, False),
    "entail_fp": (p_entail_fp, False),
    "entail_fn": (p_entail_fn, False),
    "risk_under": (p_risk_under, False),
    "risk_over": (p_risk_over, False),
    "stale": (p_stale, True),
    "irrelevant": (p_irrelevant, True),
    "partial": (p_partial, True),
    "contradict": (p_contradict, True),
    "authority": (p_authority, True),
    "no_provenance": (p_no_provenance, True),
    "miscalibrated": (p_miscalibrated, True),
    "correlated": (p_correlated, False),
    "disagree": (p_disagree, True),
    "decomp_error": (p_decomp_error, True),
    "multiclaim": (p_multiclaim, True),
    "missing_as_negative": (p_missing_as_negative, False),
    "domain_mis": (p_domain_mis, False),
    "adversarial": (p_adversarial, False),
    "narrower": (p_narrower, True),
    "population": (p_population, True),
}

SILENT = [k for k, (_, det) in PERTURBATIONS.items() if not det and k != "clean"]
DETECTABLE = [k for k, (_, det) in PERTURBATIONS.items() if det and k != "clean"]


def apply(name: str, bundle: SignalBundle, severity: float) -> SignalBundle:
    fn, _ = PERTURBATIONS[name]
    return fn(bundle, severity)
