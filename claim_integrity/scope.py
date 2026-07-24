"""Scope preservation (Phase 13). Conditions, exceptions, temporal, jurisdiction, population - and
whether each remained attached to the CORRECT claim (not merely present somewhere). Deterministic.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

_COND = re.compile(r"\b(if|only if|unless|provided that|when)\b", re.I)
_EXC = re.compile(r"\b(except|unless|other than)\b", re.I)
_TEMP = re.compile(r"\b(as of|before|after|in \d{4}|until|current|was)\b", re.I)
_JURIS = re.compile(r"\bin (the )?(eu|us|uk|california|this jurisdiction|the state|the company)\b", re.I)


def _present(rx, text): return bool(rx.search(text))


def scope_flags(text: str) -> Dict[str, bool]:
    return {"conditions": _present(_COND, text), "exceptions": _present(_EXC, text),
            "temporal": _present(_TEMP, text), "jurisdiction": _present(_JURIS, text)}


def preserved(gold_claim: Dict[str, Any], produced_text: str) -> Dict[str, Any]:
    """Per-scope-dimension preservation for one gold claim vs its aligned produced claim."""
    gf = scope_flags(gold_claim["text"])
    pf = scope_flags(produced_text)
    per = {k: (gf[k] == pf[k]) for k in gf}
    pop = (gold_claim.get("population") or "").lower()
    per["population"] = (not pop) or (pop in produced_text.lower())
    return {"per_scope": per, "all_ok": all(per.values()),
            "lost": [k for k, ok in per.items() if not ok]}
