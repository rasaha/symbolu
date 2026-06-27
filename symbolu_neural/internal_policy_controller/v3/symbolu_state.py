"""v3 Symbol-U state — separates DYNAMIC STATE from CLASSICAL VRITTI (+ full state).

TERMINOLOGY FIX (this update): v3 previously called the 5-state DYNAMIC/MOTION
system "vritti". That is NOT the classical Yoga/Patañjali vrittis. They are now two
separate fields:

  dynamic_state   : inertia/activation/oscillation/tension/release  (motion system,
                    canonical: symbolu_core.formulas.vritti_mapper.VrittiType)
                    -> ENERGY/DELIVERY policy.
  classical_vritti: pramana/viparyaya/vikalpa/smrti/nidra  (Patañjali, canonical
                    SCHEMA: symbolu_core.presentation.signals.VrittiDistribution)
                    -> COGNITIVE/EPISTEMIC policy.

PROVENANCE: the classical-vritti *schema* (names/order/meanings) is canonical; its
*values* are a `derived_bridge` from dynamic_state + valence + aspect + resonance —
because the canonical computation (ChittaVrittiResult / chitta_vritti) is part of
the neural Sovereign system, not a torch-free deterministic text mapper. We do NOT
pretend the bridged values are canonical.

Other fixes retained: Aspect via phase4a; reachable guna; no silent valence
fallback; POLICY-DRIVING vs DIAGNOSTIC-ONLY split.
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

# Canonical names/order.
DYNAMIC_STATES = [v.name for v in VrittiType]          # INERTIA/ACTIVATION/OSCILLATION/TENSION/RELEASE
CLASSICAL_VRITTI = ["pramana", "viparyaya", "vikalpa", "smrti", "nidra"]  # presentation.signals.VrittiDistribution

# dynamic_state -> Guna / Kosha (sattva reachable; see prior audit).
_DYN_TO_GUNA = {
    VrittiType.RELEASE: "sattva", VrittiType.OSCILLATION: "sattva",
    VrittiType.ACTIVATION: "rajas", VrittiType.TENSION: "rajas",
    VrittiType.INERTIA: "tamas",
}
_DYN_TO_KOSHA = {
    VrittiType.INERTIA: "annamaya", VrittiType.ACTIVATION: "pranamaya",
    VrittiType.OSCILLATION: "manomaya", VrittiType.TENSION: "vijnanamaya",
    VrittiType.RELEASE: "anandamaya",
}

POLICY_DRIVING = ["classical_vritti", "dynamic_state", "guna", "kosha",
                  "aspect_balance", "guna_resonance", "valence"]
DIAGNOSTIC_ONLY = ["kosha_resonance", "valence_sign", "pse_meaning", "pse_resonance"]


@dataclass
class SymbolUState:
    dynamic_state: Dict[str, float]      # motion system (was 'vritti') -> delivery policy
    classical_vritti: Dict[str, float]   # Patañjali 5 (derived_bridge) -> cognitive policy
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
        return {"dynamic_state_top": max(self.dynamic_state, key=self.dynamic_state.get),
                "classical_vritti_top": max(self.classical_vritti, key=self.classical_vritti.get),
                "guna_top": max(self.guna, key=self.guna.get),
                "kosha_top": max(self.kosha, key=self.kosha.get),
                "aspect_balance": round(self.aspect_balance, 3),
                "guna_resonance": round(self.guna_resonance, 3),
                "valence": self.valence}


def _dynamic_distribution(text: str) -> Dict[VrittiType, float]:
    units = map_acoustic_units(text)
    vs = [assign_vritti(u) for u in units]
    return get_vritti_distribution(vs) if vs else {v: 0.0 for v in VrittiType}


def _classical_vritti_bridge(dyn: Dict[VrittiType, float], valence: str,
                             aspect_balance: float, guna_resonance: float) -> Dict[str, float]:
    """DERIVED BRIDGE (provisional, NOT canonical computation) from dynamic_state +
    valence + aspect + resonance to the 5 classical Patañjali vrittis. Documented
    rationale per mode (canonical meanings from presentation.signals.VrittiDistribution):
      pramana   (valid cognition)      <- clarity: RELEASE motion + high aspect (+liberating)
      viparyaya (misperception/error)  <- TENSION (distortion) + binding valence
      vikalpa   (conceptual branching) <- OSCILLATION (fluctuation) + mixed valence
      smrti     (memory/retention)     <- ACTIVATION (active recall) + low aspect
      nidra     (dormancy/absence)     <- INERTIA (dullness) + low coherence (1-resonance)
    Modulated by valence/aspect/resonance so it is NOT a pure relabel of dynamic_state
    (the relabel/shuffle controls test whether it adds anything beyond that)."""
    d = {v.name: dyn.get(v, 0.0) for v in VrittiType}
    ab = max(aspect_balance, 0.0)
    # each classical vritti primarily tracks a distinct dynamic state (so it inherits
    # dynamic_state's coverage) + a light epistemic modulation. Small aspect coef on
    # pramana so it does not swamp the others.
    scores = {
        "pramana":   d["RELEASE"] + 0.20 * ab + (0.20 if valence == "liberating" else 0.0),
        "viparyaya": d["TENSION"] + (0.25 if valence == "binding" else 0.0),
        "vikalpa":   d["OSCILLATION"] + (0.20 if valence == "mixed" else 0.0),
        "smrti":     d["ACTIVATION"],
        "nidra":     d["INERTIA"] + 0.30 * (1.0 - guna_resonance),
    }
    tot = sum(scores.values()) or 1.0
    return {k: scores[k] / tot for k in CLASSICAL_VRITTI}


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
    vd = _dynamic_distribution(text)
    dynamic_state = {k.name: float(v) for k, v in vd.items()}
    guna = {g: 0.0 for g in GUNA_NAMES}
    kosha = {k: 0.0 for k in KOSHA_ORDER_5}
    for vt, p in vd.items():
        guna[_DYN_TO_GUNA[vt]] += float(p)
        kosha[_DYN_TO_KOSHA[vt]] += float(p)
    gs = sum(guna.values()) or 1.0
    ks = sum(kosha.values()) or 1.0
    guna = {k: v / gs for k, v in guna.items()}
    kosha = {k: v / ks for k, v in kosha.items()}
    lean, sign = _valence(text, warnings)
    aspect = _aspect_balance(text, warnings)
    g_res = float(compute_guna_resonance(guna))
    classical = _classical_vritti_bridge(vd, lean, aspect, g_res)
    return SymbolUState(
        dynamic_state=dynamic_state, classical_vritti=classical, guna=guna, kosha=kosha,
        aspect_balance=aspect, guna_resonance=g_res,
        kosha_resonance=float(compute_kosha_resonance_index(compute_kosha_activation_vector(kosha))),
        valence=lean, valence_sign=sign,
        pse_meaning=_PSE.encode(text), pse_resonance=_PSE_RES.encode(text),
        warnings=warnings,
        provenance={"dynamic_state": "canonical(vritti_mapper)", "valence": "canonical",
                    "aspect_balance": "canonical(phase4a)",
                    "classical_vritti": "derived_bridge(schema=presentation.signals.VrittiDistribution)",
                    "guna": "derived_from_dynamic_state", "kosha": "heuristic_from_dynamic_state",
                    "guna_resonance": "canonical_fn(derived)",
                    "pse_meaning": "diagnostic_only", "pse_resonance": "diagnostic_only",
                    "kosha_resonance": "diagnostic_only", "valence_sign": "diagnostic_only"})


if __name__ == "__main__":
    for t in ["my production database just got deleted and my boss is furious",
              "explain how a transformer neural network works",
              "should I quit my stable job to pursue my dream"]:
        print(f"\n{t!r}\n  {compute_state(t).summary()}")
