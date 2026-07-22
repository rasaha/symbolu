"""Feature-group and experimental-arm definitions.

Groups are addressed by name prefix: A:: confidence, B:: entailment, C:: grounding, and
S::/R::/E::/T:: for the four SCC hypotheses.
"""

from __future__ import annotations

from typing import Dict, List

TERMS = ["S", "R", "E", "T"]


def names(pool: Dict, prefix: str) -> List[str]:
    return [k for k in pool if k.startswith(prefix) and k not in ("label_failure", "correct")]


def group_names(pool: Dict) -> Dict[str, List[str]]:
    return {
        "A": names(pool, "A::"), "B": names(pool, "B::"), "C": names(pool, "C::"),
        "S": names(pool, "S::"), "R": names(pool, "R::"), "E": names(pool, "E::"),
        "T": names(pool, "T::"),
    }


def arm_definitions(pool: Dict) -> Dict[str, List[str]]:
    g = group_names(pool)
    base_cg = g["A"] + g["C"]
    return {
        "1_confidence": g["A"],
        "2_conf_entail": g["A"] + g["B"],
        "3_conf_ground": g["A"] + g["C"],
        "4_cg_S": base_cg + g["S"],
        "5_cg_R": base_cg + g["R"],
        "6_cg_E": base_cg + g["E"],
        "7_cg_T": base_cg + g["T"],
        "8_intrinsic_SRT": g["S"] + g["R"] + g["T"],           # coherence-only (no evidence/grounding)
        "8b_conf_SRT": g["A"] + g["S"] + g["R"] + g["T"],      # confidence + intrinsic coherence
        "9_full_scc": g["S"] + g["R"] + g["E"] + g["T"],
        "9b_cg_full_scc": base_cg + g["S"] + g["R"] + g["E"] + g["T"],
    }


# bases used for the incremental (DeLong) tests of each SCC term
def bases(pool: Dict) -> Dict[str, List[str]]:
    g = group_names(pool)
    return {
        "over_confidence": g["A"],
        "over_conf_entail": g["A"] + g["B"],           # intrinsic bar (no symbolic evidence lookup)
        "over_conf_entail_ground": g["A"] + g["B"] + g["C"],
    }
