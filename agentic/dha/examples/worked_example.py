#!/usr/bin/env python3
"""
DHA Signal Wiring - Worked Example
===================================

This example shows concrete numeric values flowing from:
    pipeline_context → extracted signals → DHA inputs → final D

All values are deterministic. Same inputs = same outputs.

Version: 1.0
Date: 2025-12-22
"""

import math
from dataclasses import dataclass
from typing import Dict, Any, Optional


# =============================================================================
# Mock Pipeline Context (simulates real pipeline state)
# =============================================================================

@dataclass
class MockRequest:
    text: str = "What is the meaning of life?"
    user_id: str = "test_user"
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class MockMLCR:
    """Mock MLCR with explain_log containing signals."""
    explain_log: Dict[str, Any] = None

    def __post_init__(self):
        if self.explain_log is None:
            self.explain_log = {}


@dataclass
class MockCoherenceState:
    """Mock coherence state."""
    coherence_score: float = 0.0
    coherence_score_v2: Optional[float] = None


@dataclass
class MockP18:
    """Mock P18 temporal entropy."""
    delta_entropy: float = 0.0
    entropy_now: float = 0.0


@dataclass
class MockFusion:
    """Mock Fusion result."""
    trace: Dict[str, Any] = None

    def __post_init__(self):
        if self.trace is None:
            self.trace = {}


@dataclass
class MockPipelineContext:
    """Mock pipeline context with all signal sources."""
    request: MockRequest = None
    mlcr: MockMLCR = None
    coherence_state: MockCoherenceState = None
    p18: MockP18 = None
    fusion: MockFusion = None

    def __post_init__(self):
        if self.request is None:
            self.request = MockRequest()
        if self.fusion is None:
            self.fusion = MockFusion()


# =============================================================================
# Worked Example
# =============================================================================

def run_worked_example():
    """
    Worked Example: Signal Flow Through DHA

    This example demonstrates:
    1. Pipeline context with concrete signal values
    2. Signal extraction with formulas
    3. DHA computation with all intermediates
    4. Final D value

    All values are shown with full precision for verification.
    """
    print("=" * 70)
    print("DHA SIGNAL WIRING - WORKED EXAMPLE")
    print("=" * 70)

    # =========================================================================
    # Step 1: Create Pipeline Context with Signals
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 1: PIPELINE CONTEXT (Input Signals)")
    print("=" * 70)

    # Guna distribution from MLCR
    guna = {
        "sattva": 0.50,
        "rajas": 0.30,
        "tamas": 0.20,
    }
    print(f"\nGuna Distribution (from MLCR):")
    print(f"  sattva = {guna['sattva']}")
    print(f"  rajas  = {guna['rajas']}")
    print(f"  tamas  = {guna['tamas']}")
    print(f"  sum    = {guna['sattva'] + guna['rajas'] + guna['tamas']}")

    # Entropy from MLCR
    entropy = {
        "H_G": 0.65,  # Raw guna entropy
    }
    print(f"\nEntropy (from MLCR):")
    print(f"  H_G = {entropy['H_G']}")

    # Contradiction from MLCR
    contradiction = 0.15
    print(f"\nContradiction (from MLCR):")
    print(f"  C_contr = {contradiction}")

    # Coherence from coherence_state
    coherence = 0.82
    print(f"\nCoherence (from coherence_state):")
    print(f"  coherence_score = {coherence}")

    # Motion from P18
    delta_entropy = 0.25
    print(f"\nMotion (from P18):")
    print(f"  delta_entropy = {delta_entropy}")

    # Create mock context
    ctx = MockPipelineContext(
        request=MockRequest(
            text="What is the meaning of life?",
            metadata={"tier": "consumer"},
        ),
        mlcr=MockMLCR(
            explain_log={
                "guna": guna,
                "entropy": entropy,
                "contradiction": contradiction,
            }
        ),
        coherence_state=MockCoherenceState(
            coherence_score=coherence,
        ),
        p18=MockP18(
            delta_entropy=delta_entropy,
        ),
    )

    # =========================================================================
    # Step 2: Signal Extraction with Formulas
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 2: SIGNAL EXTRACTION (Formulas Applied)")
    print("=" * 70)

    # Extract H_G (already normalized in this example)
    H_G_raw = entropy["H_G"]
    LN_3 = math.log(3)  # ~1.0986
    H = H_G_raw / LN_3
    H = max(0.0, min(1.0, H))  # Clamp

    print(f"\nGuna Entropy Normalization:")
    print(f"  H_G_raw = {H_G_raw}")
    print(f"  ln(3)   = {LN_3:.6f}")
    print(f"  Formula: H = H_G / ln(3)")
    print(f"  H = {H_G_raw} / {LN_3:.6f} = {H_G_raw / LN_3:.6f}")
    print(f"  H (clamped) = {H:.6f}")

    # Extract M
    M = abs(delta_entropy)
    M = max(0.0, min(1.0, M))

    print(f"\nMotion Extraction:")
    print(f"  delta_entropy = {delta_entropy}")
    print(f"  Formula: M = |delta_entropy|")
    print(f"  M = |{delta_entropy}| = {M:.6f}")

    # Extract C_s
    C_s = coherence
    C_s = max(0.0, min(1.0, C_s))

    print(f"\nCoherence Extraction:")
    print(f"  coherence_score = {coherence}")
    print(f"  Formula: C_s = clip(score, 0, 1)")
    print(f"  C_s = {C_s:.6f}")

    # Extract C_contr
    C_contr = contradiction
    C_contr = max(0.0, min(1.0, C_contr))

    print(f"\nContradiction Extraction:")
    print(f"  contradiction = {contradiction}")
    print(f"  Formula: C_contr = clip(raw, 0, 1)")
    print(f"  C_contr = {C_contr:.6f}")

    # Extract Guna distribution
    s = guna["sattva"]
    r = guna["rajas"]
    t = guna["tamas"]

    print(f"\nGuna Distribution (normalized):")
    print(f"  s = {s:.6f}")
    print(f"  r = {r:.6f}")
    print(f"  t = {t:.6f}")

    # =========================================================================
    # Step 3: DHA Computation
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 3: DHA COMPUTATION")
    print("=" * 70)

    # Config coefficients (defaults)
    k1, k2, k3, k4, k5, k6 = 2.0, 1.5, 1.8, 2.2, 1.5, 1.0
    alpha1, alpha2, alpha3 = 0.4, 0.3, 0.2
    I_min, I_max = 0.3, 1.0
    risk_bias, escalation_bias = 0.0, 0.0

    print(f"\nConfiguration Coefficients:")
    print(f"  Tone: k1={k1}, k2={k2}, k3={k3}, k4={k4}, k5={k5}, k6={k6}")
    print(f"  Intensity: alpha1={alpha1}, alpha2={alpha2}, alpha3={alpha3}")
    print(f"  Bounds: I_min={I_min}, I_max={I_max}")
    print(f"  Biases: risk={risk_bias}, escalation={escalation_bias}")

    # Step 3a: Compute tone logits
    l_sweet = k1 * s - k2 * t
    l_jolt = k3 * r + k4 * C_contr
    l_meta = k5 * H + k6 * r

    print(f"\nTone Logit Computation:")
    print(f"  l_sweet = k1*s - k2*t")
    print(f"         = {k1}*{s} - {k2}*{t}")
    print(f"         = {k1*s:.4f} - {k2*t:.4f}")
    print(f"         = {l_sweet:.6f}")
    print(f"\n  l_jolt = k3*r + k4*C_contr")
    print(f"        = {k3}*{r} + {k4}*{C_contr}")
    print(f"        = {k3*r:.4f} + {k4*C_contr:.4f}")
    print(f"        = {l_jolt:.6f}")
    print(f"\n  l_meta = k5*H + k6*r")
    print(f"        = {k5}*{H:.4f} + {k6}*{r}")
    print(f"        = {k5*H:.4f} + {k6*r:.4f}")
    print(f"        = {l_meta:.6f}")

    # Step 3b: Compute softmax weights
    logits = [l_sweet, l_jolt, l_meta]
    max_logit = max(logits)
    exp_shifted = [math.exp(l - max_logit) for l in logits]
    exp_sum = sum(exp_shifted)
    weights = [e / exp_sum for e in exp_shifted]
    w_sweet, w_jolt, w_meta = weights

    print(f"\nSoftmax Computation:")
    print(f"  logits = [{l_sweet:.4f}, {l_jolt:.4f}, {l_meta:.4f}]")
    print(f"  max_logit = {max_logit:.4f}")
    print(f"  exp_shifted = [{exp_shifted[0]:.6f}, {exp_shifted[1]:.6f}, {exp_shifted[2]:.6f}]")
    print(f"  exp_sum = {exp_sum:.6f}")
    print(f"  weights:")
    print(f"    w_sweet   = {w_sweet:.6f}")
    print(f"    w_jolt    = {w_jolt:.6f}")
    print(f"    w_metaphor = {w_meta:.6f}")
    print(f"    sum       = {w_sweet + w_jolt + w_meta:.6f}")

    # Step 3c: Compute intensity
    I_raw = alpha1 * C_s + alpha2 * M - alpha3 * H
    I = max(I_min, min(I_max, I_raw))

    print(f"\nIntensity Computation:")
    print(f"  Formula: I = clip(alpha1*C_s + alpha2*M - alpha3*H, I_min, I_max)")
    print(f"  I_raw = {alpha1}*{C_s:.4f} + {alpha2}*{M:.4f} - {alpha3}*{H:.4f}")
    print(f"        = {alpha1*C_s:.4f} + {alpha2*M:.4f} - {alpha3*H:.4f}")
    print(f"        = {I_raw:.6f}")
    print(f"  I (clipped [{I_min}, {I_max}]) = {I:.6f}")

    # Step 3d: Compute restraint
    R = max(0.0, min(1.0, 1.0 - risk_bias - escalation_bias))

    print(f"\nRestraint Computation:")
    print(f"  Formula: R = clamp(1 - risk_bias - escalation_bias, 0, 1)")
    print(f"  R = 1 - {risk_bias} - {escalation_bias}")
    print(f"    = {1.0 - risk_bias - escalation_bias:.6f}")
    print(f"  R (clamped) = {R:.6f}")

    # Step 3e: Compute D
    D = I * R

    print(f"\nDelivery Factor Computation:")
    print(f"  Formula: D = I × R")
    print(f"  D = {I:.6f} × {R:.6f}")
    print(f"  D = {D:.6f}")

    # =========================================================================
    # Step 4: Final Results
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 4: FINAL RESULTS")
    print("=" * 70)

    # Determine dominant tone
    tone_names = ["sweet", "jolt", "metaphor"]
    dominant_idx = weights.index(max(weights))
    dominant_tone = tone_names[dominant_idx]

    print(f"\nDHA Result:")
    print(f"  Tone Weights:")
    print(f"    sweet    = {w_sweet:.6f}")
    print(f"    jolt     = {w_jolt:.6f}")
    print(f"    metaphor = {w_meta:.6f}")
    print(f"  Dominant Tone: {dominant_tone}")
    print(f"\n  Intensity (I) = {I:.6f}")
    print(f"  Restraint (R) = {R:.6f}")
    print(f"\n  ╔══════════════════════════╗")
    print(f"  ║  DELIVERY FACTOR D = {D:.4f} ║")
    print(f"  ╚══════════════════════════╝")

    # Show final output intensity
    base_intensity = 1.0
    final_intensity = base_intensity * D

    print(f"\nOutput Intensity:")
    print(f"  Formula: OUTPUT_final = BASE_output × D")
    print(f"  OUTPUT_final = {base_intensity} × {D:.4f}")
    print(f"  OUTPUT_final = {final_intensity:.4f}")

    # =========================================================================
    # Audit Trail
    # =========================================================================
    print("\n" + "=" * 70)
    print("AUDIT TRAIL")
    print("=" * 70)

    audit = {
        "enabled": True,
        "entropy_source": "guna",
        "raw_entropy": H_G_raw,
        "normalized_H": round(H, 6),
        "inputs": {
            "C_s": round(C_s, 6),
            "M": round(M, 6),
            "H_G": H_G_raw,
            "C_contr": round(C_contr, 6),
            "s": s,
            "r": r,
            "t": t,
        },
        "logits": {
            "l_sweet": round(l_sweet, 6),
            "l_jolt": round(l_jolt, 6),
            "l_meta": round(l_meta, 6),
        },
        "weights": {
            "sweet": round(w_sweet, 6),
            "jolt": round(w_jolt, 6),
            "metaphor": round(w_meta, 6),
        },
        "I": round(I, 6),
        "R": round(R, 6),
        "D": round(D, 6),
        "tier": "consumer",
        "missing_signals": [],
    }

    import json
    print(f"\n{json.dumps(audit, indent=2)}")

    print("\n" + "=" * 70)
    print("END OF WORKED EXAMPLE")
    print("=" * 70)

    return {
        "D": D,
        "I": I,
        "R": R,
        "dominant_tone": dominant_tone,
        "weights": {"sweet": w_sweet, "jolt": w_jolt, "metaphor": w_meta},
    }


if __name__ == "__main__":
    run_worked_example()
