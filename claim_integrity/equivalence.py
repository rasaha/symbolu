"""Semantic preservation, per dimension (Phase 11). Compares a produced claim against a gold claim and
reports preservation on EACH semantic dimension separately - never one aggregate similarity score.
This is deliberate: lexical/embedding similarity is HIGH exactly on the dangerous pairs ("may cause X"
vs "causes X"; "no evidence that X" vs "X is false"), so a single similarity number would call them
equivalent. The per-dimension check catches the flip the similarity score hides.
"""
from __future__ import annotations

from typing import Any, Dict

from . import detect

# high-severity dimensions: a mismatch here is MATERIAL drift (meaning changed), regardless of overlap
MATERIAL_DIMENSIONS = ("polarity", "modality", "uncertainty", "numeric", "ranges",
                       "causal_direction", "attribution", "evidence_status_language",
                       "conditions", "exceptions", "temporal_scope", "jurisdiction",
                       "population", "normative_status")


def _norm(dims: Dict[str, Any], key: str):
    return dims.get(key)


def preservation(gold_claim: Dict[str, Any], produced_text: str) -> Dict[str, Any]:
    """Per-dimension preservation between one gold claim and one produced claim string."""
    gtext = gold_claim["text"]
    gd = detect.detect_dimensions(gtext)
    pd = detect.detect_dimensions(produced_text)

    per_dim: Dict[str, bool] = {}
    # lexical dims: compare detector outputs
    for key in ("polarity", "modality", "uncertainty", "causal_direction", "attribution",
                "normative_status", "conditions", "exceptions", "temporal_scope", "jurisdiction",
                "numeric", "ranges", "evidence_status_language"):
        per_dim[key] = (_norm(gd, key) == _norm(pd, key))

    # structural dims: compare against the gold field via substring of the produced text
    gtl = produced_text.lower()
    pop = (gold_claim.get("population") or "").lower()
    per_dim["population"] = (not pop) or (pop in gtl)
    # propositional core: subject+main predicate survived (rough: both share >=2 content tokens)
    per_dim["propositional"] = _proposition_match(gtext, produced_text)

    material_ok = all(per_dim.get(d, True) for d in MATERIAL_DIMENSIONS if d in per_dim)
    return {
        "per_dimension": per_dim,
        "material_preserved": material_ok and per_dim["propositional"],
        "changed_dimensions": [d for d, ok in per_dim.items() if not ok],
    }


_STOP = {"the", "a", "an", "is", "are", "was", "were", "in", "for", "of", "to", "by", "it", "that",
         "and", "or", "but", "with", "as", "on", "be"}


def _content_tokens(text: str):
    return {w.strip(".,").lower() for w in text.split() if w.strip(".,").lower() not in _STOP}


def _proposition_match(a: str, b: str) -> bool:
    ta, tb = _content_tokens(a), _content_tokens(b)
    if not ta:
        return not tb
    return len(ta & tb) / len(ta) >= 0.5


# ---- traps: pairs a similarity score would wrongly accept (used in the protocol + tests) ----------
SIMILARITY_TRAPS = (
    ("the drug may cause harm.", "the drug causes harm.", "modality"),
    ("there is no evidence that the drug harms patients.", "the drug is false for patients.", "evidence_status_language"),
    ("the drug does not prevent infection.", "the drug prevents infection.", "polarity"),
    ("the drug is associated with better outcomes.", "the drug causes better outcomes.", "causal_direction"),
    ("according to one review, the drug improves outcomes.", "the drug improves outcomes.", "attribution"),
    ("the drug lowers risk by 10 to 20 percent.", "the drug lowers risk by 15 percent.", "ranges"),
    ("the drug should be considered.", "the drug is used.", "normative_status"),
)
