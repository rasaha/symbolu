"""v3 Symbol-U state — full state with Aspect, and an honest policy/diagnostic split.

Fixes vs v2:
- ASPECT is computed (varna_lens varnas -> symbolu.ontology.phase4a.lookup), as an
  aspect_balance scalar in [-1, 1] (sublimate-leaning .. distortion-leaning).
- Vritti->Guna mapping makes ALL THREE gunas reachable (v2's sattva was unreachable).
- No silent valence fallback: failures are COUNTED and surfaced (state.warnings).
- Fields are split into POLICY-DRIVING (vritti, guna, kosha, aspect_balance,
  guna_resonance, valence) and DIAGNOSTIC-ONLY (kosha_resonance, valence_sign,
  pse_meaning, pse_resonance) — the report claims only what is actually wired.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from symbolu_core.formulas.acoustic_unit_mapper import map_acoustic_units
from symbolu_core.formulas.vritti_mapper import assign_vritti, get_vritti_distribution, VrittiType
from symbolu_core.formulas.guna_kosha_resonance import (
    compute_guna_resonance, compute_kosha_activation_vector, compute_kosha_resonance_index,
    GUNA_NAMES, KOSHA_ORDER_5)
from symbolu_neural.complementarity_probe.backends import get_backend

_PSE = get_backend("pse_meaning")
_PSE_RES = get_backend("pse_resonance")
_ASPECT_LAYER = "O5_COGNITION"

# v3 Vritti->Guna: sattva <- RELEASE+OSCILLATION (light/flowing), rajas <- ACTIVATION+
# TENSION (active/driving), tamas <- INERTIA. All three reachable (empirically verified).
_VRITTI_TO_GUNA = {
    VrittiType.RELEASE: "sattva", VrittiType.OSCILLATION: "sattva",
    VrittiType.ACTIVATION: "rajas", VrittiType.TENSION: "rajas",
    VrittiType.INERTIA: "tamas",
}
_VRITTI_TO_KOSHA = {
    VrittiType.INERTIA: "annamaya", VrittiType.ACTIVATION: "pranamaya",
    VrittiType.OSCILLATION: "manomaya", VrittiType.TENSION: "vijnanamaya",
    VrittiType.RELEASE: "anandamaya",
}

POLICY_DRIVING = ["vritti", "guna", "kosha", "aspect_balance", "guna_resonance", "valence"]
DIAGNOSTIC_ONLY = ["kosha_resonance", "valence_sign", "pse_meaning", "pse_resonance"]


@dataclass
class SymbolUState:
    vritti: Dict[str, float]
    guna: Dict[str, float]
    kosha: Dict[str, float]
    aspect_balance: float          # [-1,1] : +sublimate-leaning, -distortion-leaning
    guna_resonance: float
    kosha_resonance: float
    valence: str
    valence_sign: float
    pse_meaning: List[float]
    pse_resonance: List[float]
    warnings: List[str] = field(default_factory=list)
    provenance: Dict[str, str] = field(default_factory=dict)

    def summary(self) -> Dict:
        return {"vritti_top": max(self.vritti, key=self.vritti.get),
                "guna_top": max(self.guna, key=self.guna.get),
                "kosha_top": max(self.kosha, key=self.kosha.get),
                "aspect_balance": round(self.aspect_balance, 3),
                "guna_resonance": round(self.guna_resonance, 3),
                "valence": self.valence}


def _vritti_distribution(text: str) -> Dict[VrittiType, float]:
    units = map_acoustic_units(text)
    vs = [assign_vritti(u) for u in units]
    return get_vritti_distribution(vs) if vs else {v: 0.0 for v in VrittiType}


def _aspect_balance(text: str, warnings: List[str]) -> float:
    try:
        from varna_lens.varna_lens import analyze
        from symbolu.ontology.phase4a.lookup import lookup_interaction
    except Exception as e:
        warnings.append(f"aspect_import_failed:{type(e).__name__}")
        return 0.0
    sub = dist = n = 0
    for w in text.split()[:24]:
        try:
            r, _, _ = analyze(w, model="op")
        except Exception:
            warnings.append("aspect_analyze_failed")
            continue
        for it in (r or {}).get("sequence", []):
            if it.get("type") != "C":
                continue
            try:
                inter = lookup_interaction(it["key"], _ASPECT_LAYER)
            except Exception:
                continue
            n += 1
            if str(inter.sublimate_vector) == "upward":
                sub += 1
            if str(inter.distortion_vector) == "downward":
                dist += 1
    return (sub - dist) / n if n else 0.0


def _valence(text: str, warnings: List[str]):
    try:
        from varna_lens.varna_lens import analyze
    except Exception as e:
        warnings.append(f"valence_import_failed:{type(e).__name__}")
        return "mixed", 0.0
    leans, signs, fails = [], [], 0
    for w in text.split()[:24]:
        try:
            r, _, _ = analyze(w, model="op")
        except Exception:
            fails += 1
            continue
        r = r or {}
        ev = r.get("emergent_valence") or {}
        wwe = r.get("whole_word_essence") or {}
        if ev.get("lean"):
            leans.append(ev["lean"])
        signs.append({"+": 1.0, "-": -1.0, "−": -1.0}.get(str(wwe.get("sign", "")), 0.0))
    if fails:
        warnings.append(f"valence_word_failures:{fails}")
    lean = max(set(leans), key=leans.count) if leans else "mixed"
    return lean, (sum(signs) / len(signs) if signs else 0.0)


def compute_state(text: str) -> SymbolUState:
    warnings: List[str] = []
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
    lean, sign = _valence(text, warnings)
    return SymbolUState(
        vritti=vritti, guna=guna, kosha=kosha,
        aspect_balance=_aspect_balance(text, warnings),
        guna_resonance=float(compute_guna_resonance(guna)),
        kosha_resonance=float(compute_kosha_resonance_index(compute_kosha_activation_vector(kosha))),
        valence=lean, valence_sign=sign,
        pse_meaning=_PSE.encode(text), pse_resonance=_PSE_RES.encode(text),
        warnings=warnings,
        provenance={"vritti": "canonical", "valence": "canonical", "aspect_balance": "canonical(phase4a)",
                    "guna": "derived_from_vritti", "kosha": "heuristic_from_vritti",
                    "guna_resonance": "canonical_fn(derived)",
                    "pse_meaning": "diagnostic_only", "pse_resonance": "diagnostic_only",
                    "kosha_resonance": "diagnostic_only", "valence_sign": "diagnostic_only"})


if __name__ == "__main__":
    for t in ["my production database just got deleted and my boss is furious",
              "explain how a transformer neural network works",
              "should I quit my stable job to pursue my dream"]:
        print(f"\n{t!r}\n  {compute_state(t).summary()}")
