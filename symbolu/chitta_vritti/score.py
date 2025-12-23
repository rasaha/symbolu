"""Threshold-driven score composition.

Computes the overall readiness score from coherence and vṛtti distribution.
Uses step-function penalties (threshold-driven) rather than proportional
penalties for interpretability and drift resistance.

Design principle: Penalties apply only when vṛtti values exceed their
activation thresholds, not proportionally across the whole range.
"""

from symbolu.chitta_vritti.types import OptimizedConfig


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def compute_score(
    coherence: float,
    vritti: dict[str, float],
    config: OptimizedConfig
) -> float:
    """Compute overall readiness score using threshold-driven penalties.

    The score starts at coherence and is reduced by penalties when
    vṛtti values exceed their activation thresholds.

    Penalty logic (step functions):
    - Viparyaya > threshold → apply penalty_viparyaya
    - Vikalpa > threshold → apply penalty_vikalpa
    - Smṛti > threshold → apply penalty_smrti
    - Nidrā > threshold → apply penalty_nidra

    Args:
        coherence: Aggregate coherence [0,1]
        vritti: Normalized vṛtti distribution
        config: Threshold configuration

    Returns:
        Overall readiness score [0,1]
    """
    score = coherence

    # Threshold-driven penalties (step functions)
    # Penalty applies in FULL when threshold crossed, not proportionally

    if vritti.get("viparyaya", 0.0) > config.viparyaya_activation_threshold:
        score -= config.penalty_viparyaya

    if vritti.get("vikalpa", 0.0) > config.vikalpa_activation_threshold:
        score -= config.penalty_vikalpa

    if vritti.get("smrti", 0.0) > config.smrti_activation_threshold:
        score -= config.penalty_smrti

    if vritti.get("nidra", 0.0) > config.nidra_activation_threshold:
        score -= config.penalty_nidra

    return clamp(score)


def get_active_penalties(
    vritti: dict[str, float],
    config: OptimizedConfig
) -> list[str]:
    """Get list of vṛtti modes that triggered penalties.

    Args:
        vritti: Normalized vṛtti distribution
        config: Threshold configuration

    Returns:
        List of mode names that exceeded their thresholds
    """
    active = []

    if vritti.get("viparyaya", 0.0) > config.viparyaya_activation_threshold:
        active.append("viparyaya")

    if vritti.get("vikalpa", 0.0) > config.vikalpa_activation_threshold:
        active.append("vikalpa")

    if vritti.get("smrti", 0.0) > config.smrti_activation_threshold:
        active.append("smrti")

    if vritti.get("nidra", 0.0) > config.nidra_activation_threshold:
        active.append("nidra")

    return active


def compute_penalty_breakdown(
    vritti: dict[str, float],
    config: OptimizedConfig
) -> dict[str, float]:
    """Compute breakdown of penalties applied.

    Args:
        vritti: Normalized vṛtti distribution
        config: Threshold configuration

    Returns:
        Dict mapping mode name → penalty applied (0 if not triggered)
    """
    breakdown = {
        "viparyaya": 0.0,
        "vikalpa": 0.0,
        "smrti": 0.0,
        "nidra": 0.0,
    }

    if vritti.get("viparyaya", 0.0) > config.viparyaya_activation_threshold:
        breakdown["viparyaya"] = config.penalty_viparyaya

    if vritti.get("vikalpa", 0.0) > config.vikalpa_activation_threshold:
        breakdown["vikalpa"] = config.penalty_vikalpa

    if vritti.get("smrti", 0.0) > config.smrti_activation_threshold:
        breakdown["smrti"] = config.penalty_smrti

    if vritti.get("nidra", 0.0) > config.nidra_activation_threshold:
        breakdown["nidra"] = config.penalty_nidra

    return breakdown


def interpret_score(score: float) -> str:
    """Get human-readable interpretation of score.

    Args:
        score: Readiness score [0,1]

    Returns:
        Interpretation string
    """
    if score >= 0.9:
        return "Excellent - high coherence, stable interpretation"
    elif score >= 0.7:
        return "Good - minor concerns, interpretation reliable"
    elif score >= 0.5:
        return "Moderate - some instability, proceed with caution"
    elif score >= 0.3:
        return "Poor - significant issues, interpretation unreliable"
    else:
        return "Critical - major problems, interpretation not recommended"
