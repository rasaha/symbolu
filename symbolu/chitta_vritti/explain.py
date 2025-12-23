"""Human-readable explainability logging for Chitta-Vṛtti.

Provides detailed explanations for:
- Why coherence was reduced or preserved
- Which layer pairs contributed most to fractures
- Dominant vṛtti and its meaning
- Score penalties and their causes
"""

from typing import Optional
from symbolu.chitta_vritti.types import ChittaVrittiResult, OptimizedConfig
from symbolu.chitta_vritti.coupling import get_coupling_explanation, PRIMARY_COUPLINGS
from symbolu.chitta_vritti.score import get_active_penalties, interpret_score


# Vṛtti descriptions
VRITTI_DESCRIPTIONS = {
    "pramana": "valid cognition (layers agree, low uncertainty)",
    "viparyaya": "misperception (layers contradict each other)",
    "vikalpa": "conceptual branching (multiple interpretations)",
    "smrti": "memory persistence (state unchanged despite input)",
    "nidra": "dormancy (missing or weak signals)",
}

# Layer pair descriptions
LAYER_PAIR_DESCRIPTIONS = {
    ("phonemic", "semantic"): "phonemic-semantic",
    ("phonemic", "structural"): "phonemic-structural",
    ("phonemic", "temporal"): "phonemic-temporal",
    ("semantic", "phonemic"): "phonemic-semantic",
    ("semantic", "structural"): "semantic-structural",
    ("semantic", "temporal"): "semantic-temporal",
    ("structural", "phonemic"): "phonemic-structural",
    ("structural", "semantic"): "semantic-structural",
    ("structural", "temporal"): "structural-temporal",
    ("temporal", "phonemic"): "phonemic-temporal",
    ("temporal", "semantic"): "semantic-temporal",
    ("temporal", "structural"): "structural-temporal",
}


def generate_explanation(
    result: ChittaVrittiResult,
    config: OptimizedConfig
) -> str:
    """Generate comprehensive human-readable explanation.

    Args:
        result: Chitta-Vṛtti computation result
        config: Configuration used

    Returns:
        Multi-line explanation string
    """
    lines = []

    # Header
    lines.append(f"=== Chitta-Vṛtti Analysis ===")
    lines.append("")

    # Overall status
    score_interp = interpret_score(result.score)
    lines.append(f"Score: {result.score:.2f} - {score_interp}")
    lines.append(f"Coherence: {result.coherence:.2f}")
    lines.append("")

    # Dominant vṛtti
    dominant = result.dominant_vritti
    desc = VRITTI_DESCRIPTIONS.get(dominant, dominant)
    lines.append(f"Dominant Mode: {dominant} ({desc})")
    lines.append(f"  → {get_coupling_explanation(dominant)}")
    lines.append("")

    # Vṛtti distribution
    lines.append("Vṛtti Distribution:")
    for mode, value in sorted(result.vritti.items(), key=lambda x: -x[1]):
        bar = "█" * int(value * 20)
        lines.append(f"  {mode:12} {value:.3f} {bar}")
    lines.append("")

    # Fracture analysis
    if result.fractures:
        lines.append("Fracture Profile:")
        sorted_fractures = sorted(
            result.fractures.items(), key=lambda x: -x[1]
        )
        for pair, fracture in sorted_fractures:
            pair_name = LAYER_PAIR_DESCRIPTIONS.get(pair, f"{pair[0]}-{pair[1]}")
            level = "HIGH" if fracture > 0.5 else "MED" if fracture > 0.3 else "LOW"
            lines.append(f"  {pair_name:25} {fracture:.3f} [{level}]")

        if result.primary_fracture:
            pf = result.primary_fracture
            pf_name = LAYER_PAIR_DESCRIPTIONS.get(pf, f"{pf[0]}-{pf[1]}")
            lines.append(f"  Primary fracture: {pf_name}")
    else:
        lines.append("Fracture Profile: (not computed - fast path)")
    lines.append("")

    # Penalties
    active = get_active_penalties(result.vritti, config)
    if active:
        lines.append("Active Penalties:")
        for mode in active:
            penalty = getattr(config, f"penalty_{mode}")
            threshold = getattr(config, f"{mode}_activation_threshold")
            lines.append(
                f"  {mode}: -{penalty:.2f} (threshold {threshold:.2f} exceeded)"
            )
    else:
        lines.append("Active Penalties: None")
    lines.append("")

    # Fast path indicator
    if result.fast_path_used:
        lines.append("Note: Fast path used (low entropy, all layers present)")

    return "\n".join(lines)


def generate_brief_explanation(result: ChittaVrittiResult) -> str:
    """Generate one-line brief explanation.

    Args:
        result: Chitta-Vṛtti computation result

    Returns:
        Brief explanation string
    """
    dominant = result.dominant_vritti
    desc = VRITTI_DESCRIPTIONS.get(dominant, dominant)

    if result.primary_fracture:
        pf = result.primary_fracture
        pf_name = LAYER_PAIR_DESCRIPTIONS.get(pf, f"{pf[0]}-{pf[1]}")
        fracture_info = f", primary fracture: {pf_name}"
    else:
        fracture_info = ""

    return (
        f"Score {result.score:.2f}, coherence {result.coherence:.2f}, "
        f"dominant: {dominant} ({desc}){fracture_info}"
    )


def explain_coherence_drop(
    result: ChittaVrittiResult,
    threshold: float = 0.7
) -> Optional[str]:
    """Explain why coherence dropped below threshold.

    Args:
        result: Chitta-Vṛtti computation result
        threshold: Coherence threshold

    Returns:
        Explanation string, or None if coherence is above threshold
    """
    if result.coherence >= threshold:
        return None

    lines = [f"Coherence ({result.coherence:.2f}) below threshold ({threshold:.2f}):"]

    # Find high fractures
    high_fractures = [
        (pair, frac) for pair, frac in result.fractures.items()
        if frac > 0.4
    ]

    if high_fractures:
        for pair, frac in sorted(high_fractures, key=lambda x: -x[1]):
            pair_name = LAYER_PAIR_DESCRIPTIONS.get(pair, f"{pair[0]}-{pair[1]}")
            lines.append(f"  - {pair_name} layers disagree (fracture {frac:.2f})")
    else:
        lines.append("  - Multiple moderate fractures across layers")

    # Check for viparyaya
    if result.vritti.get("viparyaya", 0) > 0.2:
        lines.append(
            f"  - Viparyaya active ({result.vritti['viparyaya']:.2f}): "
            "confident opposition detected"
        )

    return "\n".join(lines)


def explain_vritti_activation(vritti: dict[str, float]) -> str:
    """Explain current vṛtti activations.

    Args:
        vritti: Vṛtti distribution

    Returns:
        Explanation string
    """
    lines = ["Vṛtti Activation Analysis:"]

    # Sort by activation
    sorted_vritti = sorted(vritti.items(), key=lambda x: -x[1])

    for mode, value in sorted_vritti:
        desc = VRITTI_DESCRIPTIONS.get(mode, mode)
        if value > 0.4:
            level = "DOMINANT"
        elif value > 0.2:
            level = "ACTIVE"
        elif value > 0.1:
            level = "PRESENT"
        else:
            level = "MINIMAL"

        lines.append(f"  {mode}: {value:.3f} [{level}] - {desc}")

    return "\n".join(lines)
