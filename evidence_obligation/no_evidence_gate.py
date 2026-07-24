"""Phase 13 - The narrow NO_FACTUAL_EVIDENCE_GATE class + its safety validation.

A deliberately narrow, safe class for genuinely non-factual content. The pilot blocker: ANY high-risk
factual claim assigned NO_FACTUAL_EVIDENCE_GATE. This module both defines eligibility and validates that
the reference classifier never assigns the no-gate class to a high-risk or factual claim.

Deterministic, read-only.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from evidence_obligation import schema as s, classifier, dataset

# eligible non-factual content
_ELIGIBLE = re.compile(
    r"\b(i\s+prefer|my\s+favorite|in\s+my\s+opinion|i\s+think|we\s+believe|suppose|hypothetically|"
    r"imagine\s+if|for\s+example|e\.g\.|please\s+format|use\s+bold|as\s+a\s+heading|arguably)\b", re.I)
# content that is factual/consequential despite superficial low-evidence framing
_FACTUAL_LEAK = re.compile(
    r"\b(cure|patient|secure|vulnerab|guarantee|100\s*%|production|payment|access|financial|legal|"
    r"medical|regulat|uptime|latency|complies|is\s+compliant|prevents|eliminates)\w*", re.I)


def eligible_for_no_gate(text: str, risk_tier: str) -> bool:
    """Narrow eligibility: explicitly non-assertive/opinion/hypothetical content, low risk, no factual
    leak. Fail-closed."""
    if risk_tier in ("high", "critical"):
        return False
    if _FACTUAL_LEAK.search(text or ""):
        return False
    return bool(_ELIGIBLE.search(text or ""))


def validate() -> Dict[str, Any]:
    """Verify the reference classifier never assigns NO_FACTUAL_EVIDENCE_GATE to a high-risk or
    factual-leak claim across all partitions. blocker=True iff any such assignment exists."""
    violations: List[Dict[str, str]] = []
    no_gate_total = 0
    checked = 0
    for part in ("DEVELOPMENT", "HELD_OUT_NATURAL", "ADVERSARIAL_OBLIGATION"):
        for it in dataset.load_partition(part):
            checked += 1
            o = classifier.classify(it)
            if o.evidence_obligation_type == s.NO_FACTUAL_EVIDENCE_GATE:
                no_gate_total += 1
                unsafe = it.get("risk_tier") in ("high", "critical") or \
                    bool(_FACTUAL_LEAK.search(it.get("text", "")))
                if unsafe:
                    violations.append({"artifact_id": it["artifact_id"], "partition": part,
                                       "risk": it.get("risk_tier"), "text": it.get("text", "")[:80]})
    return {
        "checked": checked,
        "no_gate_assignments": no_gate_total,
        "high_risk_or_factual_no_gate_violations": len(violations),
        "blocker": len(violations) > 0,           # PILOT BLOCKER if any high-risk factual got no-gate
        "violations": violations[:10],
    }


if __name__ == "__main__":
    m = validate()
    print(f"no-gate assignments: {m['no_gate_assignments']} / {m['checked']}")
    print(f"high-risk/factual no-gate violations: {m['high_risk_or_factual_no_gate_violations']}")
    print(f"PILOT BLOCKER: {m['blocker']}")
