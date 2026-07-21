"""
TAP-E2 query cases with graded gold and expected retrieval gaps.

Each case carries a request text (run through the FROZEN TAP-E1 layer to obtain an
IntentRecord, demonstrating the E1->E2 interface), plus author-assigned gold:
  * relevant     — fully relevant evidence units (graded 2)
  * partial      — partially relevant units (graded 1)
  * distractors  — tempting-but-wrong units (graded 0)
  * expected_gaps— gap types a correct pipeline should surface for this query
Ground truth supports MULTIPLE acceptable retrieval sets: relevant ∪ (any subset of
partial) all count as correct evidence; only distractors are penalized.

Splits: dev (development) and eval (HIDDEN / content-hash locked).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import stable_hash
from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import GapType

SPLITS = ("dev", "eval")


@dataclass(frozen=True)
class QueryCase:
    query_id: str
    split: str
    request_text: str
    relevant: Tuple[str, ...]
    partial: Tuple[str, ...]
    distractors: Tuple[str, ...]
    authoritative_required: bool
    expected_gaps: Tuple[GapType, ...]
    conflict_expected: bool
    missing_evidence: bool
    family: str

    def public_dict(self) -> Dict[str, object]:
        return {"query_id": self.query_id, "split": self.split,
                "request_text": self.request_text}

    def relevance(self, unit_id: str) -> int:
        if unit_id in self.relevant:
            return 2
        if unit_id in self.partial:
            return 1
        return 0


_Q: List[QueryCase] = []


def _q(qid, split, text, family, *, relevant=(), partial=(), distractors=(),
       auth=True, gaps=(), conflict=False, missing=False):
    _Q.append(QueryCase(qid, split, text, tuple(relevant), tuple(partial),
                        tuple(distractors), auth, tuple(gaps), conflict, missing, family))


# =========================================================================== #
# DEV                                                                         #
# =========================================================================== #

_q("E2D01", "dev", "How long do we retain customer data after an account is closed?",
   "retention", relevant=["POL-RET-2025#u1"],
   partial=["POL-RET-2025#u2", "REG-GDPR#u1"],
   distractors=["POL-RET-2021#u1", "SCRATCH-NOTES#u1"])
_q("E2D02", "dev", "What is required to grant a user administrator access?",
   "access", relevant=["SOP-ACCESS#u1"], partial=["REG-SEC-STD#u2"],
   distractors=["SOP-ACCESS#u3"])
_q("E2D03", "dev", "What is the API rate limit?",
   "api", relevant=["API-DOC#u1"], partial=["API-DOC#u2"],
   distractors=["SCRATCH-NOTES#u2"], auth=False)
_q("E2D04", "dev", "How much notice is needed to terminate the vendor agreement?",
   "contract", relevant=["CONTRACT-VENDOR#u1"], distractors=[])
_q("E2D05", "dev", "How is data at rest protected?",
   "encryption", relevant=["SPEC-ENCRYPT#u1"], partial=["SPEC-ENCRYPT#u2"], auth=False)
_q("E2D06", "dev", "How quickly must a postmortem be published after an incident?",
   "incident", relevant=["MAN-INCIDENT#u1"], distractors=["MAN-INCIDENT#u2"], auth=False)
_q("E2D07", "dev", "How long are production database backups kept?",
   "backup", relevant=["SOP-BACKUP#u1"], partial=["SOP-BACKUP#u2"])
_q("E2D08", "dev", "How are failed webhook deliveries handled?",
   "api", relevant=["API-DOC#u4"], auth=False)
_q("E2D09", "dev", "How long are audit logs retained?",
   "audit", relevant=["POL-AUDIT#u1"], partial=["POL-AUDIT#u2"])
_q("E2D10", "dev", "When must the vendor report a data breach?",
   "contract", relevant=["CONTRACT-VENDOR#u3"], partial=["REG-GDPR#u2"])
# --- gap-targeted (dev) ---
_q("E2D11", "dev", "What is the minimum password length we require?",
   "conflict", relevant=["POL-PW-2025#u1", "REG-SEC-STD#u1"],
   gaps=[GapType.CONFLICTING_SOURCES], conflict=True)
_q("E2D12", "dev", "What is our policy on cryptocurrency payments?",
   "missing", relevant=[], gaps=[GapType.INSUFFICIENT_EVIDENCE], missing=True)
_q("E2D13", "dev", "What does our official policy say the approved production deployment strategy is?",
   "no_authority", relevant=[], partial=["DESIGN-DEPLOY#u1"],
   distractors=["DESIGN-DEPLOY#u2"], gaps=[GapType.NO_AUTHORITATIVE_SOURCE])
_q("E2D14", "dev", "How must passwords be rotated?",
   "access", relevant=["POL-PW-2025#u2"])
_q("E2D15", "dev", "Is multi-factor authentication required for remote access?",
   "access", relevant=["REG-SEC-STD#u2"], partial=["SOP-ACCESS#u1"])
_q("E2D16", "dev", "What happens when API requests exceed the allowed rate?",
   "api", relevant=["API-DOC#u2"], partial=["API-DOC#u1"], auth=False)
_q("E2D17", "dev", "What is the default request timeout for the API?",
   "api", relevant=["API-DOC#u3"], auth=False)
_q("E2D18", "dev", "How often are access reviews performed for privileged accounts?",
   "access", relevant=["SOP-ACCESS#u2"])

# =========================================================================== #
# EVAL (HIDDEN, content-hash locked)                                          #
# =========================================================================== #

_q("E2E01", "eval", "After an account closes, how long is personal information stored?",
   "retention", relevant=["POL-RET-2025#u1"],
   partial=["POL-RET-2025#u2", "REG-GDPR#u1"],
   distractors=["POL-RET-2021#u1", "SCRATCH-NOTES#u1"])
_q("E2E02", "eval", "What approvals are needed before someone gets admin privileges?",
   "access", relevant=["SOP-ACCESS#u1"], partial=["REG-SEC-STD#u2"])
_q("E2E03", "eval", "How many requests per minute can a client make to the API?",
   "api", relevant=["API-DOC#u1"], partial=["API-DOC#u2"],
   distractors=["SCRATCH-NOTES#u2"], auth=False)
_q("E2E04", "eval", "What is the vendor's cap on liability?",
   "contract", relevant=["CONTRACT-VENDOR#u2"])
_q("E2E05", "eval", "What encryption protects information while it is transmitted?",
   "encryption", relevant=["SPEC-ENCRYPT#u2"], partial=["SPEC-ENCRYPT#u1"], auth=False)
_q("E2E06", "eval", "When a severity-1 incident occurs, how fast must on-call respond?",
   "incident", relevant=["MAN-INCIDENT#u2"], distractors=["MAN-INCIDENT#u1"], auth=False)
_q("E2E07", "eval", "How frequently is backup restore tested?",
   "backup", relevant=["SOP-BACKUP#u2"], partial=["SOP-BACKUP#u1"])
_q("E2E08", "eval", "What must happen to personal data once it is no longer needed?",
   "retention", relevant=["REG-GDPR#u1"], partial=["POL-RET-2025#u2"])
_q("E2E09", "eval", "What character length must account passwords meet?",
   "conflict", relevant=["POL-PW-2025#u1", "REG-SEC-STD#u1"],
   gaps=[GapType.CONFLICTING_SOURCES], conflict=True)
_q("E2E10", "eval", "What is our data residency requirement for EU customers?",
   "missing", relevant=[], gaps=[GapType.INSUFFICIENT_EVIDENCE], missing=True)
_q("E2E11", "eval", "How long are contractor accounts kept active without use?",
   "access", relevant=["SOP-ACCESS#u3"])
_q("E2E12", "eval", "What are the data subject's rights regarding deletion?",
   "retention", relevant=["REG-GDPR#u2"], partial=["POL-RET-2025#u2"])


ALL_QUERIES: Tuple[QueryCase, ...] = tuple(_Q)


def queries_for_split(split: str) -> Tuple[QueryCase, ...]:
    return tuple(q for q in ALL_QUERIES if q.split == split)


def eval_lock() -> Dict[str, object]:
    payload = [q.public_dict() for q in queries_for_split("eval")]
    return {"n_eval": len(payload), "eval_inputs_hash": stable_hash(payload)}


def manifest() -> Dict[str, object]:
    dist: Dict[str, int] = {}
    fam: Dict[str, int] = {}
    for q in ALL_QUERIES:
        dist[q.split] = dist.get(q.split, 0) + 1
        fam[q.family] = fam.get(q.family, 0) + 1
    return {"n_queries": len(ALL_QUERIES), "split_distribution": dist,
            "family_distribution": fam, "eval_lock": eval_lock()}
