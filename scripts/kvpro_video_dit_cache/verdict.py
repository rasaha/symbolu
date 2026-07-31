"""Video-DiT cache-compression feasibility — DETERMINISTIC VERDICT LOGIC (pre-registered).

Implements the frozen go/no-go gates G1..G6 (plan §10/§11) and maps gate outcomes to exactly one of the
enumerated verdicts. The thresholds here are PRE-REGISTERED: they are frozen with a content hash and
must be set from a CALIBRATION phase (baseline run-to-run variance) BEFORE protected-compression results
are seen — never tuned afterward. `assert_gates_frozen` enforces that the thresholds in force match the
recorded freeze hash, so accidental post-hoc edits are caught by a unit test.

Honesty boundary baked into the logic: G1 (materiality), G4 (systems value), and G6 (strong-baseline
Pareto) require **GPU profiling / end-to-end generation** — they cannot be decided from CPU tensor
analysis. When those inputs are absent, the verdict function returns a REPRESENTATION-ONLY verdict and
never claims a systems result. A CPU harness cannot establish whether the workload is capacity-,
bandwidth-, communication-, or compute-bound.
"""
from __future__ import annotations

import hashlib
import json

# --------------------------------------------------------------------------- #
# FROZEN, PRE-REGISTERED THRESHOLDS.
#
# These are DEFAULT pre-registration values. The real study MUST overwrite them from the calibration
# phase (baseline quality noise, metric noise, profiling variance) and RE-FREEZE (recompute FROZEN_SHA256)
# BEFORE evaluating any protected-compression variant. Editing a threshold without updating FROZEN_SHA256
# makes assert_gates_frozen fail — that is the guard against silently moving the goalposts.
# --------------------------------------------------------------------------- #
FROZEN_GATES = {
    # G1 cache materiality (capacity side is CPU-modelable; bound-ness is GPU-only).
    "g1_min_cache_residency_frac_of_hbm": 0.10,   # persistent cache >=10% of a plausible HBM budget
    "g1_min_cache_bytes": 1_000_000_000,          # ...or >=1 GB persistent residency, whichever triggers
    # G2 net compression AFTER all overheads (scales, protected values, index, gate meta).
    "g2_min_net_density_x": 1.30,                 # >=1.30x net density to be worth the machinery
    # G3 quality margin — reconstruction fidelity of the cache object (tensor proxy; NOT output video).
    "g3_max_cache_rel_l2": 0.05,                  # compressed-cache rel-L2 vs FP cache <= 5% (calibrate!)
    "g3_min_cache_cosine": 0.995,                 # ...and cosine >= 0.995 (calibrate!)
    # G4 systems value — GPU-only; at least one real system outcome improves without unacceptable regress.
    "g4_min_systems_improvement_frac": 0.10,      # >=10% improvement in >=1 systems metric
    "g4_max_latency_regression_frac": 0.10,       # and end-to-end latency regression <= 10%
    # G5 protected-method value — protected must beat uniform low-bit at equal bits.
    "g5_min_protected_vs_uniform_err_ratio": 1.30,  # uniform_err / protected_err >= 1.30
    # G6 strong-baseline Pareto — GPU-only; improve the memory-quality-latency frontier vs a strong method.
    "g6_min_pareto_improvement_frac": 0.05,
}

# Recompute with: python -c "import verdict,json,hashlib;print(hashlib.sha256(json.dumps(verdict.FROZEN_GATES,sort_keys=True,separators=(',',':')).encode()).hexdigest())"
FROZEN_SHA256 = "PLACEHOLDER_SET_ON_FREEZE"

VERDICTS = (
    "STOP — cache not material",
    "STOP — cache material but not compressible",
    "STOP — uniform compression already sufficient",
    "STOP — protected compression fails quality",
    "STOP — compression overhead erases systems benefit",
    "CONTINUE — representation feasibility only",
    "CONTINUE — systems feasibility demonstrated",
    "CONTINUE — differentiated result requiring prior-art and patent review",
)


def gates_hash(gates: dict) -> str:
    return hashlib.sha256(json.dumps(gates, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def freeze(gates: dict) -> str:
    """Return the freeze hash for a gate set. Call this ONCE after calibration, paste the result into
    FROZEN_SHA256, and do not edit thresholds afterward without re-freezing (which a reviewer will see)."""
    return gates_hash(gates)


def assert_gates_frozen(gates: dict = FROZEN_GATES, expected: str = None) -> None:
    """Raise if `gates` do not match the recorded freeze hash. Skipped only while the placeholder is in
    place (pre-registration not yet frozen), which the study README flags as a required pre-run step."""
    expected = expected if expected is not None else FROZEN_SHA256
    if expected == "PLACEHOLDER_SET_ON_FREEZE":
        raise AssertionError(
            "Gates not yet frozen: run verdict.freeze(FROZEN_GATES), paste into FROZEN_SHA256 after the "
            "calibration phase and BEFORE evaluating protected compression (pre-registration discipline)."
        )
    actual = gates_hash(gates)
    if actual != expected:
        raise AssertionError(
            f"Gate thresholds changed after freeze (hash {actual[:12]} != frozen {expected[:12]}). "
            "Post-hoc threshold tuning is not allowed — re-run calibration and re-freeze transparently."
        )


def decide(evidence: dict, gates: dict = FROZEN_GATES) -> dict:
    """Map measured evidence to exactly one verdict.

    `evidence` fields (missing systems fields => representation-only path):
      REQUIRED (CPU, Stage A):
        cache_bytes                 : persistent cache residency (bytes)      [Measured — CPU / Modeled]
        net_density_x               : net density after overheads (G2)        [Measured — CPU]
        cache_rel_l2, cache_cosine  : compressed-cache fidelity (G3 proxy)    [Measured — CPU]
        uniform_vs_protected_err_ratio : uniform_err/protected_err (G5)       [Measured — CPU]
      OPTIONAL (GPU, Stage B):
        cache_residency_frac_of_hbm : G1 bound-ness signal                    [Measured — GPU]
        systems_improvement_frac    : best systems-metric gain (G4)           [Measured — GPU/e2e]
        latency_regression_frac     : e2e latency regression (G4)             [Measured — e2e]
        pareto_improvement_frac     : vs strong baseline (G6)                 [Measured — e2e]
    Returns {verdict, gates:{g1..g6}, rationale, systems_evaluated}.
    """
    g = gates
    res = {}

    # ---- G1 materiality: capacity side CPU-modelable; TRUE bound-ness needs GPU ----
    cap_material = evidence.get("cache_bytes", 0) >= g["g1_min_cache_bytes"]
    hbm_frac = evidence.get("cache_residency_frac_of_hbm")
    hbm_material = (hbm_frac is not None) and (hbm_frac >= g["g1_min_cache_residency_frac_of_hbm"])
    g1 = bool(cap_material or hbm_material)
    res["g1_materiality"] = g1

    # ---- G2 net compression (CPU) ----
    g2 = evidence.get("net_density_x", 0) >= g["g2_min_net_density_x"]
    res["g2_net_compression"] = bool(g2)

    # ---- G3 quality proxy (CPU tensor fidelity; NOT output video) ----
    g3 = (evidence.get("cache_rel_l2", 1.0) <= g["g3_max_cache_rel_l2"]) and (
        evidence.get("cache_cosine", 0.0) >= g["g3_min_cache_cosine"]
    )
    res["g3_quality_proxy"] = bool(g3)

    # ---- G5 protected vs uniform (CPU) ----
    g5 = evidence.get("uniform_vs_protected_err_ratio", 0) >= g["g5_min_protected_vs_uniform_err_ratio"]
    res["g5_protected_value"] = bool(g5)

    # ---- G4 / G6 systems (GPU/e2e only) ----
    systems_evaluated = all(
        k in evidence for k in ("systems_improvement_frac", "latency_regression_frac", "pareto_improvement_frac")
    )
    if systems_evaluated:
        g4 = (evidence["systems_improvement_frac"] >= g["g4_min_systems_improvement_frac"]) and (
            evidence["latency_regression_frac"] <= g["g4_max_latency_regression_frac"]
        )
        g6 = evidence["pareto_improvement_frac"] >= g["g6_min_pareto_improvement_frac"]
        res["g4_systems_value"] = bool(g4)
        res["g6_strong_baseline"] = bool(g6)
    else:
        g4 = g6 = None
        res["g4_systems_value"] = "REQUIRES GPU"
        res["g6_strong_baseline"] = "REQUIRES GPU"

    # ---- deterministic verdict resolution (ordered stops first) ----
    if not g1 and hbm_frac is not None:
        verdict = VERDICTS[0]  # STOP — cache not material  (only assertable once bound-ness is measured)
        rationale = "Cache residency below materiality floor and GPU bound-ness signal did not clear G1."
    elif not g2:
        verdict = VERDICTS[1]  # STOP — cache material but not compressible
        rationale = "Net density after overheads is below the G2 floor: compression not worth the machinery."
    elif not g3:
        verdict = VERDICTS[3]  # STOP — protected compression fails quality
        rationale = "Compressed-cache reconstruction fidelity fails the frozen G3 margin (tensor proxy)."
    elif not g5:
        # protection adds nothing over uniform: is uniform itself good enough?
        if g3:
            verdict = VERDICTS[2]  # STOP — uniform compression already sufficient
            rationale = "Uniform low-bit already meets G2+G3; protection adds no value (G5 fails). Stop the protected branch."
        else:
            verdict = VERDICTS[3]
            rationale = "Protection adds no value and quality fails."
    elif not systems_evaluated:
        verdict = VERDICTS[5]  # CONTINUE — representation feasibility only
        rationale = ("Representation gates pass (G2 net density, G3 fidelity proxy, G5 protection value). "
                     "Systems gates G1-bound-ness/G4/G6 REQUIRE GPU and are not yet measured.")
    elif systems_evaluated and not g4:
        verdict = VERDICTS[4]  # STOP — compression overhead erases systems benefit
        rationale = "GPU/e2e: no systems metric improves within the latency-regression bound (G4 fails)."
    elif systems_evaluated and g4 and not g6:
        verdict = VERDICTS[6]  # CONTINUE — systems feasibility demonstrated
        rationale = "GPU/e2e systems value shown (G4), but does not beat the strong baseline's Pareto frontier (G6)."
    elif systems_evaluated and g4 and g6:
        verdict = VERDICTS[7]  # CONTINUE — differentiated result requiring prior-art and patent review
        rationale = ("All gates pass including strong-baseline Pareto (G6). A differentiated result — now "
                     "requires professional prior-art and patent review before any novelty/commercial claim.")
    else:
        verdict = VERDICTS[5]
        rationale = "Default representation-only outcome."

    return {
        "verdict": verdict,
        "gates": res,
        "systems_evaluated": systems_evaluated,
        "rationale": rationale,
        "gate_thresholds": gates,
        "note": "G1 bound-ness, G4, G6 require GPU/e2e evidence; CPU alone yields at most 'representation feasibility only'.",
    }
