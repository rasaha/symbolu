"""Shared lexical dimension detector (Phase 8 support). Deterministic, stdlib-only. Reads a claim
string and reports which semantic dimensions are lexically present. Used to measure preservation: if a
method's text transform drops "generally" or "not", the detector no longer finds the hedge/negation on
the produced claim, so the drift is a real consequence of the transform - not an assumption.

This is intentionally a SIMPLE lexical detector (the kind a cheap method could use). The reference
component (Phase 9) does better by preserving/re-attaching from the source span rather than re-detecting.
"""
from __future__ import annotations

import re
from typing import Any, Dict

_HEDGES = ("generally", "sometimes", "typically", "often", "may", "might", "can", "likely",
           "approximately", "in some cases")
_MODALS = {"may": "permission", "might": "possibility", "can": "permission",
           "must": "obligation", "should": "obligation", "shall": "obligation"}


def detect_dimensions(text: str) -> Dict[str, Any]:
    t = text.lower()
    dims: Dict[str, Any] = {}
    dims["uncertainty"] = "hedged" if any(h in t for h in _HEDGES) else "none"
    dims["polarity"] = "negated" if re.search(r"\b(not|no|never|cannot|does not|doesn't)\b", t) else "affirmative"
    mod = "none"
    for w, m in _MODALS.items():
        if re.search(rf"\b{w}\b", t):
            mod = m; break
    dims["modality"] = mod
    dims["conditions"] = bool(re.search(r"\b(if|only if|provided that|when)\b", t))
    dims["exceptions"] = bool(re.search(r"\b(except|unless|other than)\b", t))
    dims["temporal_scope"] = bool(re.search(r"\b(as of|before|after|in \d{4}|until|current)\b", t))
    dims["jurisdiction"] = bool(re.search(r"\bin (the )?(eu|us|uk|california|this jurisdiction|the state|the company)\b", t))
    dims["numeric"] = bool(re.search(r"\d", t))
    dims["ranges"] = bool(re.search(r"\d+\s*(to|-|–)\s*\d+|\b(at least|at most|no more than|up to|between)\b", t))
    dims["attribution"] = "attributed" if re.search(r"\b(according to|reportedly|source|claims that|says that)\b", t) else "direct"
    dims["evidence_status_language"] = bool(re.search(r"\b(no evidence|not approved|not established|not recommended)\b", t))
    dims["causal_direction"] = ("causal" if re.search(r"\b(causes|caused|leads to|results in)\b", t)
                                else ("correlational" if re.search(r"\b(associated with|linked to|correlated with)\b", t)
                                      else "none"))
    dims["normative_status"] = "normative" if re.search(r"\b(should|ought|must|recommended|advise)\b", t) else "descriptive"
    dims["population"] = bool(re.search(r"\bin (patients|adults|children|investors|corporations|firms|households|families|users|clients|contractors|operators|technicians|servers|hosts|teams|working groups|the )", t))
    return dims


# which detector key carries each gold `fragile_dimension`
FRAGILE_TO_DETECTOR = {
    "uncertainty": "uncertainty", "polarity": "polarity", "modality": "modality",
    "conditions": "conditions", "exceptions": "exceptions", "population": "population",
    "temporal_scope": "temporal_scope", "jurisdiction": "jurisdiction", "ranges": "ranges",
    "causal_direction": "causal_direction", "attribution": "attribution",
    "evidence_status_language": "evidence_status_language", "normative_status": "normative_status",
    "scope": "exceptions", "reference": "population",
}
