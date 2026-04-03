"""
Persona Drift Monitor - Track persona stability across conversation turns.

Monitors drift in:
- Domain transitions (identity/therapy/spiritual vs unrelated domains)
- Bhava state jumps (distant bhava transitions)
- Bhava direction oscillations (up/down/up/down patterns)
- Mapper arc_mode transitions (identity/deep_context vs none)
"""

from typing import List, Dict


def compute_persona_drift(
    domain_history: List[str],
    mapper_profile_history: List[Dict],
    bhava_id_history: List[int],
    bhava_direction_history: List[str],
) -> float:
    """
    Compute persona drift score from conversation histories.

    Persona drift is high when:
    - Frequent domain flips between identity/therapy/spiritual and unrelated domains
    - Bhava ID swings across distant bhavas frequently
    - Bhava direction oscillates (up/down/up/down) in short windows
    - Mapper arc_mode flips between identity/deep_context and none often

    Args:
        domain_history: List of domain strings per turn
        mapper_profile_history: List of mapper profile dicts per turn
        bhava_id_history: List of bhava IDs per turn
        bhava_direction_history: List of bhava directions per turn

    Returns:
        Drift score 0.0-1.0 (higher = more drift)
    """
    if not domain_history or len(domain_history) < 2:
        return 0.0

    # Component 1: Domain instability
    domain_instability = _compute_domain_instability(domain_history)

    # Component 2: Bhava instability
    bhava_instability = _compute_bhava_instability(
        bhava_id_history, bhava_direction_history
    )

    # Component 3: Arc mode instability
    arc_mode_instability = _compute_arc_mode_instability(mapper_profile_history)

    # Weighted sum
    drift = (
        0.4 * domain_instability
        + 0.3 * bhava_instability
        + 0.3 * arc_mode_instability
    )

    return max(0.0, min(1.0, drift))


def _compute_domain_instability(domain_history: List[str]) -> float:
    """
    Compute domain instability: fraction of adjacent turns where domain changes.

    Args:
        domain_history: List of domain strings

    Returns:
        Instability score 0.0-1.0
    """
    if len(domain_history) < 2:
        return 0.0

    changes = 0
    for i in range(1, len(domain_history)):
        if domain_history[i] != domain_history[i - 1]:
            changes += 1

    return changes / (len(domain_history) - 1)


def _compute_bhava_instability(
    bhava_id_history: List[int],
    bhava_direction_history: List[str],
) -> float:
    """
    Compute bhava instability from ID jumps and direction oscillations.

    Args:
        bhava_id_history: List of bhava IDs
        bhava_direction_history: List of bhava directions

    Returns:
        Instability score 0.0-1.0
    """
    if not bhava_id_history or len(bhava_id_history) < 2:
        return 0.0

    # Count big jumps in bhava ID (|delta| >= 3)
    big_jumps = 0
    for i in range(1, len(bhava_id_history)):
        delta = abs(bhava_id_history[i] - bhava_id_history[i - 1])
        if delta >= 3:
            big_jumps += 1

    jump_instability = big_jumps / (len(bhava_id_history) - 1)

    # Count direction oscillations (consecutive changes)
    direction_oscillations = 0.0
    if len(bhava_direction_history) >= 3:
        for i in range(2, len(bhava_direction_history)):
            prev_prev = bhava_direction_history[i - 2]
            prev = bhava_direction_history[i - 1]
            curr = bhava_direction_history[i]

            # Oscillation: up -> down -> up or down -> up -> down
            if (
                (prev_prev != prev and prev != curr and prev_prev == curr)
                and prev_prev != "stable"
                and curr != "stable"
            ):
                direction_oscillations += 1

        direction_instability = direction_oscillations / (len(bhava_direction_history) - 2)
    else:
        direction_instability = 0.0

    # Combine jump and direction instability
    return 0.6 * jump_instability + 0.4 * direction_instability


def _compute_arc_mode_instability(mapper_profile_history: List[Dict]) -> float:
    """
    Compute arc_mode instability: fraction of turns where arc_mode changes.

    Args:
        mapper_profile_history: List of mapper profile dicts

    Returns:
        Instability score 0.0-1.0
    """
    if not mapper_profile_history or len(mapper_profile_history) < 2:
        return 0.0

    changes = 0
    for i in range(1, len(mapper_profile_history)):
        prev_mode = mapper_profile_history[i - 1].get("arc_mode", "none")
        curr_mode = mapper_profile_history[i].get("arc_mode", "none")

        if prev_mode != curr_mode:
            changes += 1

    return changes / (len(mapper_profile_history) - 1)
