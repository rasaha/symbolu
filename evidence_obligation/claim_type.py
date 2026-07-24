"""Phase 9 - Claim-type classifier (component under test).

Classifies an artifact's dominant claim family from text signals. This is the COMPONENT's own
classifier - distinct from the independent ground-truth rubric (ground_truth.py). Deterministic,
fail-closed: an unrecognized claim defaults to process_description (a contextual, non-low-external family
that still qualifies rather than clean-allows).
"""
from __future__ import annotations

import re
from typing import List, Tuple

from evidence_obligation import taxonomy

# ordered detectors: first match wins. High-consequence families are checked first so a disguised
# high-risk claim cannot fall through to a low-burden family.
_DETECTORS: List[Tuple[str, re.Pattern]] = [
    ("medical", re.compile(r"\b(patient|clinical|diagnos|dosage|therap|symptom|prescrib|treatment|cure)\w*", re.I)),
    ("financial", re.compile(r"\b(invest|portfolio|revenue|valuation|trading|roi\b|profit|financial\s+risk)\w*", re.I)),
    ("legal_interpretation", re.compile(r"\b(liable|lawful|statute|jurisdiction|legally|gdpr|hipaa|regulat)\w*", re.I)),
    ("action_proposal", re.compile(r"\b(deploy|delete|grant\s+access|revoke|transfer|shut\s+down|restart|rotate\s+key)\w*", re.I)),
    ("permission", re.compile(r"\b(permission|is\s+allowed\s+to|may\s+access|is\s+authorized|entitled\s+to)\b", re.I)),
    ("prohibition", re.compile(r"\b(must\s+not|shall\s+not|prohibited|forbidden|is\s+not\s+permitted)\b", re.I)),
    ("requirement", re.compile(r"\b(must\s+|shall\s+|is\s+required|mandatory|required\s+to)\b", re.I)),
    ("measured_performance", re.compile(r"\b(latency|throughput|p95|p99|requests\s+per\s+second|uptime|benchmark|reliab)\w*", re.I)),
    ("model_quality", re.compile(r"\b(accuracy|f1|precision|recall|model\s+quality|eval\s+score)\b", re.I)),
    ("attribution", re.compile(r"\b(according\s+to|as\s+stated\s+by|per\s+the|cited\s+in|quoted)\b", re.I)),
    ("mathematical", re.compile(r"\b(equals|computed\s+as|derivation|theorem|big-?o|complexity\s+is|proof)\b", re.I)),
    ("api_behavior", re.compile(r"\b(endpoint|request\s+body|response\s+code|api\s+returns|http\s+status)\b", re.I)),
    ("code_behavior", re.compile(r"\b(function|method|returns?\b|parameter|argument|this\s+class|the\s+module)\b", re.I)),
    ("current_fact", re.compile(r"\b(currently|as\s+of\s+now|at\s+present|active\s+incident|now\s+running)\b", re.I)),
    ("historical_fact", re.compile(r"\b(in\s+\d{4}|previously|historically|was\s+released|used\s+to)\b", re.I)),
    ("scientific", re.compile(r"\b(hypothesis|experiment|statistically|empirical|study\s+found)\b", re.I)),
    ("causal", re.compile(r"\b(causes?|because\s+of|leads?\s+to|results?\s+in|due\s+to)\b", re.I)),
    ("prediction", re.compile(r"\b(will\s+likely|expected\s+to|forecast|we\s+predict|projected)\b", re.I)),
    ("unsupported_marketing", re.compile(r"\b(best-in-class|world-?class|industry-leading|revolutionary|cutting-edge)\b", re.I)),
    ("internal_policy", re.compile(r"\b(policy|procedure|standard|guideline|our\s+rule)\b", re.I)),
    ("recommendation", re.compile(r"\b(should|recommend|suggest|advise|we\s+propose|consider\s+using)\b", re.I)),
    ("subjective_opinion", re.compile(r"\b(i\s+think|in\s+my\s+opinion|we\s+believe|arguably|feels?\s+like)\b", re.I)),
    ("user_preference", re.compile(r"\b(i\s+prefer|my\s+favorite|i\s+like|we\s+prefer)\b", re.I)),
    ("hypothetical", re.compile(r"\b(suppose|hypothetically|imagine\s+if|what\s+if|for\s+the\s+sake\s+of)\b", re.I)),
    ("uncertainty", re.compile(r"\b(maybe|possibly|might\s+be|unclear|not\s+sure|todo|fixme)\b", re.I)),
    ("implementation_plan", re.compile(r"\b(we\s+will\s+build|roadmap|planned|next\s+step\s+is|to\s+be\s+implemented)\b", re.I)),
    ("design_rationale", re.compile(r"\b(we\s+chose|the\s+rationale|trade-?off|design\s+decision|because\s+it\s+is\s+simpler)\b", re.I)),
    ("status_report", re.compile(r"\b(status\s+is|currently\s+running|deployed\s+to|is\s+live|operational\s+status)\b", re.I)),
    ("process_description", re.compile(r"\b(this\s+section|the\s+following|describes|overview|for\s+example)\b", re.I)),
]


def classify_claim_type(text: str) -> Tuple[str, List[str]]:
    """Return (claim_family, reason_codes). Fail-closed to process_description."""
    t = text or ""
    for fam, rx in _DETECTORS:
        if rx.search(t):
            return fam, [f"CT.{fam.upper()}"]
    return "process_description", ["CT.DEFAULT"]
