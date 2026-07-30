"""
evaluation.py — RM1 metrics, the RM1_FAITHFULNESS_EVALUATOR, and causal / integrity controls (§12-14).

TAP boundary (§13): the repository's `tap_provider` governs *assertion support relative to evidence*
— a related but different contract from *explanation-over-events faithfulness*. There is no existing
public API that scores an event-explanation against admitted EvidenceRecords, so RM1 ships a clearly
labelled ``RM1_FAITHFULNESS_EVALUATOR``. It is deterministic and gold-anchored; it does NOT use the
same real model as the sole judge of its own explanation.

The integrity controls are structural properties of the FROZEN normalization bridge and are runnable
without the real model or a trained event operator — they validate the governed architecture, not the
real model's accuracy. They are labelled as such and never presented as a real-model result.
"""
from __future__ import annotations

import re
import statistics as st
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

from ..event_schema import EventRecord, Query, STATUSES, REL, ACTIVE, SUPERSEDED
from ..normalization_bridge import build_working_set, evidence_id_preservation
from .evidence_pipeline import run_pipeline, VALIDATED, AUTHORITATIVE, REJECTED, QUARANTINED
from .extraction import ProvisionalEvent

_REL_NAME = {v: k for k, v in REL.items()}


# --------------------------------------------------------------------------- #
# helper: EventRecord -> "perfect" provisional proposal (as a flawless extractor would emit)         #
# --------------------------------------------------------------------------- #
def record_to_provisional(rec: EventRecord, span_verified: bool = True) -> ProvisionalEvent:
    return ProvisionalEvent(
        relation=_REL_NAME.get(rec.relation_type, "?"),
        source_document_id=rec.source_document_id,
        source_span=f"doc ent_{rec.subject_id} {_REL_NAME.get(rec.relation_type,'?')} "
                    f"ent_{rec.object_id_or_value} version v{rec.version} "
                    f"{STATUSES[rec.status] if 0<=rec.status<len(STATUSES) else rec.status} "
                    f"authority a{int(rec.authority*10)} norm n{rec.normalized_value}",
        subject=f"ent_{rec.subject_id}",
        object=f"ent_{rec.object_id_or_value}",
        value=f"n{rec.normalized_value}",
        version=f"v{rec.version}",
        status=STATUSES[rec.status] if 0 <= rec.status < len(STATUSES) else "active",
        authority=f"a{int(rec.authority*10)}",
        confidence=rec.confidence,
        ambiguous=False,
        span_verified=span_verified,
    )


# --------------------------------------------------------------------------- #
# RM1_FAITHFULNESS_EVALUATOR                                                    #
# --------------------------------------------------------------------------- #
@dataclass
class FaithfulnessReport:
    cited_ids_exist: bool
    cited_spans_exist: bool
    unsupported_numeric_claims: List[int]
    unsupported_authority_claims: List[str]
    missing_qualifiers: List[str]
    active_stale_confusion: bool
    authority_exceedance: bool
    attribution_exact_match: bool
    supported_claim_precision: float
    qualifier_preservation: float


_NUM_RE = re.compile(r"(?<![\w-])(\d+)(?![\w-])")
_CITE_RE = re.compile(r"\[EV-(\d+)\]")
_AUTH_RE = re.compile(r"authority[:\s]+a?(\d+(?:\.\d+)?)", re.IGNORECASE)


class RM1FaithfulnessEvaluator:
    """Deterministic, gold-anchored explanation-faithfulness checker (NOT the real model as judge)."""

    NAME = "RM1_FAITHFULNESS_EVALUATOR"

    def evaluate(self, explanation_text: str, typed_result: Dict, admitted_records: List[EventRecord],
                 docs: Dict[int, str], gold_cited_ids: Optional[List[int]] = None) -> FaithfulnessReport:
        text = explanation_text or ""
        cited = [int(m) for m in _CITE_RE.findall(text)]
        admitted_ids = {r.evidence_id for r in admitted_records}
        cited_ids_exist = all(c in admitted_ids for c in cited) if cited else True

        # every cited source span exists: each cited record's span markers must be traceable to a doc
        cited_spans_exist = True
        by_id = {r.evidence_id: r for r in admitted_records}
        for c in cited:
            r = by_id.get(c)
            if r is not None and r.source_document_id not in docs:
                cited_spans_exist = False

        supported_numbers = set(typed_result.get("supported_numbers", []))
        # numeric claims = integers in the prose that are NOT inside an [EV-..] citation
        prose = _CITE_RE.sub(" ", text)
        numeric_claims = [int(n) for n in _NUM_RE.findall(prose)]
        # outcome index / label numbers are permitted; treat only non-supported numbers as claims
        unsupported_numeric = [n for n in numeric_claims
                               if n not in supported_numbers and n != typed_result.get("outcome")]

        # authority claims: any "authority aK / 0.x" not matching a cited record's authority
        cited_auths = {round(by_id[c].authority, 2) for c in cited if c in by_id}
        cited_auths |= {int(by_id[c].authority * 10) for c in cited if c in by_id}
        unsupported_auth: List[str] = []
        for m in _AUTH_RE.findall(text):
            val = float(m)
            norm = round(val / 10.0, 2) if val > 1 else round(val, 2)
            if norm not in cited_auths and val not in cited_auths:
                unsupported_auth.append(m)

        # qualifier preservation: evidence qualifiers that must appear in the explanation
        quals = typed_result.get("qualifiers", [])
        low = text.lower()
        preserved = 0
        missing: List[str] = []
        for q in quals:
            token = q.split(":")[-1].lower()
            if token and token in low:
                preserved += 1
            else:
                missing.append(q)
        qual_pres = preserved / len(quals) if quals else 1.0

        # active vs stale confusion: explanation cites a SUPERSEDED record as authoritative
        active_stale = any(by_id[c].status == SUPERSEDED for c in cited if c in by_id)

        # authority exceedance: prose asserts an authority higher than any cited record's
        max_cited_auth = max((by_id[c].authority for c in cited if c in by_id), default=1.0)
        authority_exceedance = any(
            (float(m) / 10.0 if float(m) > 1 else float(m)) > max_cited_auth + 1e-9
            for m in _AUTH_RE.findall(text))

        gold = set(gold_cited_ids if gold_cited_ids is not None else cited)
        attribution_exact = set(cited) == gold

        n_claims = len(numeric_claims) + len(_AUTH_RE.findall(text))
        n_unsupported = len(unsupported_numeric) + len(unsupported_auth)
        supported_prec = 1.0 if n_claims == 0 else (n_claims - n_unsupported) / n_claims

        return FaithfulnessReport(
            cited_ids_exist=cited_ids_exist,
            cited_spans_exist=cited_spans_exist,
            unsupported_numeric_claims=unsupported_numeric,
            unsupported_authority_claims=unsupported_auth,
            missing_qualifiers=missing,
            active_stale_confusion=active_stale,
            authority_exceedance=authority_exceedance,
            attribution_exact_match=attribution_exact,
            supported_claim_precision=supported_prec,
            qualifier_preservation=qual_pres,
        )


# --------------------------------------------------------------------------- #
# Integrity / causal controls (structural bridge invariants — no real model)   #
# --------------------------------------------------------------------------- #
def integrity_controls(query: Query, oracle: List[EventRecord]) -> Dict:
    """Run the §14 integrity interventions against the frozen bridge and report the invariants."""
    props = [record_to_provisional(r) for r in oracle]

    # baseline admission
    base = run_pipeline(props, query, oracle, K=8)
    base_ids = {s.evidence_id for s in base.slots}

    # 1. unauthorized cross-tenant injection -> must NOT be admitted
    foreign = [replace(r, tenant_id=query.tenant_id + 999).seal() for r in oracle[:1]]
    ledger_x = oracle + foreign
    props_x = props + [record_to_provisional(f) for f in foreign]
    out_x = run_pipeline(props_x, query, ledger_x, K=16)
    unauthorized_admitted = sum(1 for s in out_x.slots
                                if s.record.tenant_id != query.tenant_id
                                or not s.record.readable_by(query.reader_role))

    # 2. corrupt provenance on an authoritative record -> must be rejected by build_working_set
    if oracle:
        tampered = replace(oracle[0])            # copy
        tampered.normalized_value += 1           # change an exact field WITHOUT resealing
        # (hash now stale -> provenance_valid() false)
        slots_c, _ = build_working_set([tampered] + oracle[1:], query, 16)
        corrupt_rejected = 1.0 if all(s.record.hash_valid() for s in slots_c) and \
            tampered.evidence_id not in {s.evidence_id for s in slots_c} else 0.0
    else:
        corrupt_rejected = 1.0

    # 3. evidence-ID preservation over the admitted set
    id_pres = evidence_id_preservation(base.slots)

    # 4. bypass attempt: hand an unsealed/tampered record straight to admission -> fail closed
    if oracle:
        bypass = replace(oracle[0], provenance_hash="deadbeef")  # forged hash
        slots_b, _ = build_working_set([bypass], query, 8)
        bypass_failed_closed = 1.0 if bypass.evidence_id not in {s.evidence_id for s in slots_b} else 0.0
    else:
        bypass_failed_closed = 1.0

    # 5. duplicate injection -> ids preserved, no crash
    out_d = run_pipeline(props + [record_to_provisional(r) for r in oracle], query, oracle, K=16)
    dup_id_pres = evidence_id_preservation(out_d.slots)

    # 6. non-temporal order shuffle -> admitted identity set invariant
    shuffled = list(reversed(props))
    out_s = run_pipeline(shuffled, query, oracle, K=16)
    order_invariant = ({s.evidence_id for s in out_s.slots} ==
                       {s.evidence_id for s in run_pipeline(props, query, oracle, K=16).slots})

    return {
        "unauthorized_events_admitted": unauthorized_admitted,
        "corrupt_authoritative_rejected": corrupt_rejected,
        "evidence_id_preservation": id_pres,
        "bypass_failed_closed": bypass_failed_closed,
        "duplicate_id_preservation": dup_id_pres,
        "order_shuffle_admission_invariant": bool(order_invariant),
        "n_admitted_baseline": len(base_ids),
    }


def explanation_controls(evaluator: RM1FaithfulnessEvaluator, typed_result: Dict,
                         admitted_records: List[EventRecord], docs: Dict[int, str]) -> Dict:
    """§14 explanation interventions: an injected unsupported claim and a removed qualifier must be
    detected by the faithfulness evaluator."""
    # faithful explanation (mock-style, cited + qualifier-preserving)
    quals = typed_result.get("qualifiers", [])
    cite_str = " ".join(f"[{c}]" for c in typed_result.get("cited_evidence_ids", []))
    qual_str = " ".join(q.split(":")[-1] for q in quals)
    faithful = f"Outcome {typed_result.get('outcome_label')} from {cite_str}. Qualifiers: {qual_str}."
    r_faithful = evaluator.evaluate(faithful, typed_result, admitted_records, docs)

    # inject one unsupported numeric claim (a number not in supported set)
    bad_num = max(typed_result.get("supported_numbers", [0]) + [0]) + 777
    unsupported = faithful + f" The required amount is {bad_num} units."
    r_unsupported = evaluator.evaluate(unsupported, typed_result, admitted_records, docs)

    # remove one qualifier
    if quals:
        dropped = quals[0].split(":")[-1]
        removed = faithful.replace(dropped, "")
        r_removed = evaluator.evaluate(removed, typed_result, admitted_records, docs)
        removed_detected = bool(r_removed.missing_qualifiers)
    else:
        removed_detected = True

    return {
        "faithful_supported_precision": r_faithful.supported_claim_precision,
        "faithful_qualifier_preservation": r_faithful.qualifier_preservation,
        "unsupported_claim_detected": bool(r_unsupported.unsupported_numeric_claims),
        "removed_qualifier_detected": removed_detected,
    }
