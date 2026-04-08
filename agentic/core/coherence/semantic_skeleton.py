"""
Semantic Skeleton - Multi-turn semantic structure tracking.

Builds simplified semantic signatures for each turn and tracks stability
across conversation history.
"""

from typing import List, Dict


def build_semantic_signature(
    fusion_output: Dict,
    dha_output: Dict,
) -> Dict:
    """
    Build a simplified semantic skeleton for a turn.

    Captures only structure, not wording:
    - Presence of symbolic/practical/mirror layers
    - Presence of DHA insights/alignments/conflicts
    - Section and structure counts

    Args:
        fusion_output: Output from Fusion engine
        dha_output: Output from DHA engine

    Returns:
        Semantic signature dict with structural flags and counts
    """
    signature = {
        "has_symbolic": False,
        "has_practical": False,
        "has_mirror": False,
        "has_dha_insight": False,
        "has_dha_alignment": False,
        "has_dha_conflict": False,
        "section_count": 0,
    }

    # Check fusion layers
    if fusion_output:
        layers = fusion_output.get("layers", {})

        signature["has_symbolic"] = bool(layers.get("symbolic"))
        signature["has_practical"] = bool(layers.get("practical"))
        signature["has_mirror"] = bool(layers.get("mirror"))

        # Count sections in fusion output
        if "sections" in fusion_output:
            signature["section_count"] = len(fusion_output["sections"])

    # Check DHA markers
    if dha_output:
        signature["has_dha_insight"] = bool(dha_output.get("insight"))
        signature["has_dha_alignment"] = bool(dha_output.get("alignment_marker"))
        signature["has_dha_conflict"] = bool(dha_output.get("conflict_marker"))

        # If DHA has its own section count, add to total
        if "sections" in dha_output:
            signature["section_count"] += len(dha_output["sections"])

    return signature


def compute_semantic_stability(skeleton_history: List[Dict]) -> float:
    """
    Compute semantic stability score from skeleton history.

    Stability is high when skeleton structure remains consistent across turns.
    Compares each skeleton to previous one and counts structural changes.

    Args:
        skeleton_history: List of semantic signature dicts

    Returns:
        Stability score 0.0-1.0 (higher = more stable)
    """
    if not skeleton_history or len(skeleton_history) < 2:
        return 1.0  # No history = perfectly stable

    total_flips = 0
    num_comparisons = len(skeleton_history) - 1

    # Boolean flags to check for flips
    bool_flags = [
        "has_symbolic",
        "has_practical",
        "has_mirror",
        "has_dha_insight",
        "has_dha_alignment",
        "has_dha_conflict",
    ]
    num_flags = len(bool_flags)

    # Compare each adjacent pair of skeletons
    for i in range(1, len(skeleton_history)):
        prev = skeleton_history[i - 1]
        curr = skeleton_history[i]

        # Count boolean flag flips
        for flag in bool_flags:
            prev_val = prev.get(flag, False)
            curr_val = curr.get(flag, False)

            if prev_val != curr_val:
                total_flips += 1

    # Compute change rate
    if num_comparisons > 0 and num_flags > 0:
        max_possible_flips = num_comparisons * num_flags
        change_rate = total_flips / max_possible_flips
    else:
        change_rate = 0.0

    # Stability is inverse of change rate
    stability = 1.0 - change_rate

    return max(0.0, min(1.0, stability))


def compute_section_count_stability(skeleton_history: List[Dict]) -> float:
    """
    Compute stability based on section count variance.

    Lower variance in section counts = higher stability.

    Args:
        skeleton_history: List of semantic signature dicts

    Returns:
        Stability score 0.0-1.0 (higher = more stable)
    """
    if not skeleton_history or len(skeleton_history) < 2:
        return 1.0

    section_counts = [s.get("section_count", 0) for s in skeleton_history]

    # Compute variance
    mean_count = sum(section_counts) / len(section_counts)
    variance = sum((c - mean_count) ** 2 for c in section_counts) / len(section_counts)

    # Normalize variance to 0-1 stability score
    # Higher variance = lower stability
    # Use sigmoid-like transformation
    if variance == 0:
        return 1.0

    # Map variance to stability (heuristic: variance > 4 is high instability)
    stability = 1.0 / (1.0 + variance / 4.0)

    return max(0.0, min(1.0, stability))
