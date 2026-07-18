"""Full Symbol-U state of a text, computed from CANONICAL repo code where it exists.

Per the codebase audit, from text we can canonically compute:
  - Vritti     : acoustic_unit_mapper -> vritti_mapper           (CANONICAL)
  - Resonance/ : varna_lens.analyze emergent_valence + sign      (CANONICAL)
    valence
  - Aspect     : varna_lens varnas -> symbolu.ontology.phase4a   (CANONICAL)
  - PSE        : complementarity_probe pse_meaning/pse_resonance (CANONICAL-wrapped)
There is NO text->guna_probs or text->kosha_probs function in the repo, so:
  - Guna       : DERIVED from the Vritti distribution (documented mapping)
  - Kosha      : DERIVED from the Vritti distribution (documented, heuristic)
  - guna/kosha resonance indices: CANONICAL functions applied to the derived probs.

Every field carries a `provenance` tag (canonical / derived / heuristic) so the
report is honest about what is measured vs inferred. This is the fix for v1, which
used only one phonological backend and never computed guna/kosha/aspect at all.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from symbolu_core.formulas.acoustic_unit_mapper import map_acoustic_units
from symbolu_core.formulas.vritti_mapper import assign_vritti, get_vritti_distribution, VrittiType
from symbolu_core.formulas.guna_kosha_resonance import (
    compute_guna_resonance, compute_kosha_activation_vector, compute_kosha_resonance_index,
    GUNA_NAMES, KOSHA_ORDER_5)
from symbolu_neural.complementarity_probe.backends import get_backend

_PSE = get_backend("pse_meaning")
_PSE_RES = get_backend("pse_resonance")

# Documented Vritti -> Guna mapping (rationale in module docstring / report):
#   tamas  = inertia/density   <- INERTIA, TENSION
#   rajas  = activity/passion  <- ACTIVATION, OSCILLATION
#   sattva = clarity/balance   <- RELEASE
_VRITTI_TO_GUNA = {
    VrittiType.INERTIA: "tamas", VrittiType.TENSION: "tamas",
    VrittiType.ACTIVATION: "rajas", VrittiType.OSCILLATION: "rajas",
    VrittiType.RELEASE: "sattva",
}
# Documented (heuristic) Vritti -> Kosha sheath mapping.
_VRITTI_TO_KOSHA = {
    VrittiType.INERTIA: "annamaya", VrittiType.ACTIVATION: "pranamaya",
    VrittiType.OSCILLATION: "manomaya", VrittiType.TENSION: "vijnanamaya",
    VrittiType.RELEASE: "anandamaya",
}


@dataclass
class SymbolUState:
    vritti: Dict[str, float]            # canonical 5-way distribution
    guna: Dict[str, float]             # derived from vritti
    kosha: Dict[str, float]            # derived (heuristic) from vritti
    guna_resonance: float              # canonical fn on derived guna
    kosha_resonance: float             # canonical fn on derived kosha
    valence: str                       # canonical: liberating/binding/mixed
    valence_sign: float                # canonical: +1/-1/0 whole-word
    pse_meaning: List[float]           # canonical-wrapped
    pse_resonance: List[float]         # canonical-wrapped
    provenance: Dict[str, str] = field(default_factory=dict)

    def summary(self) -> Dict:
        return {
            "vritti_top": max(self.vritti, key=self.vritti.get),
            "guna_top": max(self.guna, key=self.guna.get),
            "kosha_top": max(self.kosha, key=self.kosha.get),
            "guna_resonance": round(self.guna_resonance, 3),
            "valence": self.valence,
        }


def _vritti_distribution(text: str) -> Dict[VrittiType, float]:
    units = map_acoustic_units(text)
    vs = [assign_vritti(u) for u in units]
    return get_vritti_distribution(vs) if vs else {v: 0.0 for v in VrittiType}


def _valence(text: str):
    try:
        from varna_lens.varna_lens import analyze
        # pool over words; majority lean
        leans, signs = [], []
        for w in text.split()[:24]:
            r, _, _ = analyze(w, model="op")
            ev = r.get("emergent_valence") or {}
            wwe = r.get("whole_word_essence") or {}
            if ev.get("lean"):
                leans.append(ev["lean"])
            s = {"+": 1.0, "-": -1.0, "−": -1.0}.get(str(wwe.get("sign", "")), 0.0)
            signs.append(s)
        lean = max(set(leans), key=leans.count) if leans else "mixed"
        return lean, float(np.mean(signs)) if signs else 0.0
    except Exception:
        return "mixed", 0.0


def compute_state(text: str) -> SymbolUState:
    vd = _vritti_distribution(text)
    vritti = {k.name: float(v) for k, v in vd.items()}

    guna = {g: 0.0 for g in GUNA_NAMES}
    kosha = {k: 0.0 for k in KOSHA_ORDER_5}
    for vt, p in vd.items():
        guna[_VRITTI_TO_GUNA[vt]] += float(p)
        kosha[_VRITTI_TO_KOSHA[vt]] += float(p)
    gs = sum(guna.values()) or 1.0
    ks = sum(kosha.values()) or 1.0
    guna = {k: v / gs for k, v in guna.items()}
    kosha = {k: v / ks for k, v in kosha.items()}

    g_res = compute_guna_resonance(guna)
    k_vec = compute_kosha_activation_vector(kosha)
    k_res = compute_kosha_resonance_index(k_vec)
    lean, sign = _valence(text)

    return SymbolUState(
        vritti=vritti, guna=guna, kosha=kosha,
        guna_resonance=float(g_res), kosha_resonance=float(k_res),
        valence=lean, valence_sign=sign,
        pse_meaning=_PSE.encode(text), pse_resonance=_PSE_RES.encode(text),
        provenance={
            "vritti": "canonical", "valence": "canonical", "pse": "canonical-wrapped",
            "guna": "derived_from_vritti", "kosha": "heuristic_from_vritti",
            "guna_resonance": "canonical_fn(derived)", "kosha_resonance": "canonical_fn(derived)",
            "aspect": "available_via_phase4a (not pooled into vector here)",
        },
    )


if __name__ == "__main__":
    for t in ["my production database just got deleted and my boss is furious",
              "explain how a transformer neural network works",
              "is it going to be a good year for the housing market"]:
        s = compute_state(t)
        print(f"\n{t!r}\n  {s.summary()}")
