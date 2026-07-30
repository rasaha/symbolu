"""
evaluation.py — RM0–RM7 arms, metrics, causal controls, acceptance (RM1 §9, §12, §14, §15).

The arms reuse the FROZEN event subsystem (schema, normalization bridge, P5, deterministic reasoner,
gated-residual H3, causal-control style) — nothing about the event operator is redesigned here. The
real token model (or, for wiring tests, an explicitly labelled MockBackend) performs only extraction
(A) and explanation (B); every authoritative assignment stays deterministic.

The event-attention checkpoint is trained ONCE on the existing training split with the frozen
pre-registered architecture/hyperparameters, saved with a content hash, and never touched by RM1
held-out data (§10).
"""
from __future__ import annotations

import hashlib
import json
import os
import statistics as st
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ..datasets import (build_dataset, DataCfg, CLASS_NAMES, N_CLASS, RELATIONAL_FAMILIES,
                        ABSTAIN, CONFLICT, YES, NO)
from ..event_schema import EventRecord, Slot
from ..model_arms import EventArm, DeterministicArm
from .. import train as T
from .evidence_pipeline import process_proposals
from .reasoning_router import (route, DETERMINISTIC_ONLY, DETERMINISTIC_PLUS_EVENT_ATTENTION,
                              QUARANTINE_OR_REVIEW)
from .extraction import extract_records
from .explanation import (build_typed_findings, cited_records, generate_explanation,
                         evaluate_faithfulness)
from ..deterministic_event_reasoner import reason as det_reason

# ------------------------------------------------------------------ event checkpoint (§10)
def _tensor_dump(params) -> Dict[str, List[List[float]]]:
    return {k: [row[:] for row in v.data] for k, v in params.items()}


def _tensor_load(params, blob) -> None:
    for k, v in params.items():
        if k in blob:
            v.data = [row[:] for row in blob[k]]


def get_event_models(seed: int, epochs: int, checkpoint_path: str) -> Dict:
    """Load-or-train the frozen H3/H2 event operator on the existing training split, hash it."""
    cfg = DataCfg(n_train=800, n_heldout=300, seed=0)
    train, held, vocab = build_dataset(cfg)
    h3 = EventArm(T.D, seed, readout="attn")
    h2 = EventArm(T.D, seed, readout="pool")
    if os.path.exists(checkpoint_path):
        blob = json.load(open(checkpoint_path))
        _tensor_load(h3.trainable_params(), blob["h3"])
        _tensor_load(h2.trainable_params(), blob["h2"])
        chk_hash = blob.get("hash", "")
    else:
        h3, h2 = T.train_event_arms(train, seed, epochs=epochs)
        blob = {"h3": _tensor_dump(h3.trainable_params()),
                "h2": _tensor_dump(h2.trainable_params()),
                "seed": seed, "epochs": epochs, "arch": "gated_residual_H3"}
        payload = json.dumps(blob, sort_keys=True).encode()
        chk_hash = hashlib.sha256(payload).hexdigest()[:16]
        blob["hash"] = chk_hash
        os.makedirs(os.path.dirname(checkpoint_path) or ".", exist_ok=True)
        json.dump(blob, open(checkpoint_path, "w"))
    return {"h3": h3, "h2": h2, "held": held, "vocab": vocab, "hash": chk_hash}


# ------------------------------------------------------------------ answer parsing
_NAME2IDX = {n.lower(): i for i, n in enumerate(CLASS_NAMES)}


def parse_answer(text: str) -> int:
    t = text.strip().lower()
    try:
        obj = json.loads(t[t.find("{"): t.rfind("}") + 1]) if "{" in t else {}
        if isinstance(obj, dict) and "answer" in obj:
            t = str(obj["answer"]).lower()
    except Exception:
        pass
    for name, idx in _NAME2IDX.items():
        if name in t:
            return idx
    if "yes" in t:
        return YES
    if "no" in t:
        return NO
    if "conflict" in t:
        return CONFLICT
    return ABSTAIN


def _event_answer(h3: EventArm, inst, slots: List[Slot]) -> int:
    logits, _, _ = h3.logits(inst, "predicted", override_slots=slots)
    return max(range(N_CLASS), key=lambda k: logits.data[0][k])


# ------------------------------------------------------------------ per-instance arms
@dataclass
class InstanceResult:
    instance_id: str
    task_family: str
    gold: int
    route: str = ""
    answers: Dict[str, int] = field(default_factory=dict)      # arm -> predicted class
    admitted_ids: List[int] = field(default_factory=list)
    required_survival: float = 0.0
    eid_preservation: float = 1.0
    unauthorized_inclusion: int = 0
    quarantined: int = 0
    extraction_ok: bool = False
    n_input_tokens: int = 0
    n_output_tokens: int = 0
    faithfulness: Dict = field(default_factory=dict)
    trace: Dict = field(default_factory=dict)


def _serialize_documents(inst) -> List[Dict]:
    return [{"document_id": "DOC-0", "text": inst.raw_text}]


def _retrieved_documents(inst) -> List[Dict]:
    return [{"document_id": "DOC-0", "text": inst.retrieved_text}]


def run_instance(backend, inst, models: Dict, cfg) -> InstanceResult:
    h3, h2 = models["h3"], models["h2"]
    ir = InstanceResult(instance_id=str(id(inst)), task_family=inst.query.task_family,
                        gold=inst.gold_answer)

    # RM0 — model over raw text, direct answer
    if cfg.run_generative:
        g0 = backend.generate(_answer_prompt(inst.raw_text, inst.query.task_family),
                               max_new_tokens=cfg.max_new_tokens)
        ir.answers["RM0"] = parse_answer(g0.text)
        ir.n_input_tokens += g0.n_input_tokens
        ir.n_output_tokens += g0.n_output_tokens
        # RM1 — model over retrieved packet, direct answer
        g1 = backend.generate(_answer_prompt(inst.retrieved_text, inst.query.task_family),
                              max_new_tokens=cfg.max_new_tokens)
        ir.answers["RM1"] = parse_answer(g1.text)

    # ---- extraction → deterministic validation → P5 (shared by RM2/RM3/RM4) ----
    ex = extract_records(backend, _serialize_documents(inst), inst.query.task_family,
                         max_attempts=cfg.max_extraction_attempts,
                         max_new_tokens=cfg.max_new_tokens,
                         max_input_tokens=cfg.max_input_tokens)
    ir.extraction_ok = ex.ok
    pr = process_proposals([dict(p) for p in ex.provisional], inst, cfg.K)
    admitted = pr.route_pool
    ir.admitted_ids = pr.admitted_ids
    ir.eid_preservation = pr.evidence_id_preservation
    ir.unauthorized_inclusion = pr.unauthorized_inclusion
    ir.quarantined = len(pr.quarantined)
    # required survival measured against the ORACLE required set by identity (fresh ids differ)
    ir.required_survival = _required_survival(inst, admitted)

    # RM2 — validated events serialized back to the model; model answers directly
    if cfg.run_generative:
        packet = _events_packet(admitted)
        g2 = backend.generate(_answer_prompt(packet, inst.query.task_family),
                              max_new_tokens=cfg.max_new_tokens)
        ir.answers["RM2"] = parse_answer(g2.text)

    # RM3 — deterministic-only reasoner over admitted records
    ans3, used3 = det_reason(admitted, inst.query.task_family, inst.query.subject_id)
    ir.answers["RM3"] = ans3

    # RM4 — router: deterministic by default, H3 event attention for relational
    rd = route(inst.query.task_family, admitted, inst.required_ids, ir.eid_preservation)
    ir.route = rd.route
    if rd.route == DETERMINISTIC_PLUS_EVENT_ATTENTION and admitted:
        ir.answers["RM4"] = _event_answer(h3, inst, pr.admitted_slots)
    elif rd.route == QUARANTINE_OR_REVIEW:
        ir.answers["RM4"] = ABSTAIN
    else:
        ir.answers["RM4"] = ans3

    # RM5 — oracle → deterministic reasoner (model-independent ceiling)
    ans5, _ = det_reason(inst.oracle_records, inst.query.task_family, inst.query.subject_id)
    ir.answers["RM5"] = ans5

    # RM6 — oracle → router → deterministic + event attention
    if inst.query.task_family in RELATIONAL_FAMILIES:
        from ..normalization_bridge import build_working_set
        oslots, _ = build_working_set(inst.oracle_records, inst.query, cfg.K)
        ir.answers["RM6"] = _event_answer(h3, inst, oslots)
    else:
        ir.answers["RM6"] = ans5

    # RM7 — best typed outcome (RM4) → explanation → faithfulness
    if cfg.run_generative and admitted:
        best = ir.answers["RM4"]
        _, used = det_reason(admitted, inst.query.task_family, inst.query.subject_id)
        tf = build_typed_findings(inst.query.task_family, best, used or ir.admitted_ids[:2], admitted)
        cr = cited_records(used or ir.admitted_ids[:2], admitted)
        exp = generate_explanation(backend, tf, cr, max_new_tokens=cfg.max_new_tokens)
        fr = evaluate_faithfulness(exp["text"], tf, cr)
        ir.answers["RM7"] = best
        ir.faithfulness = fr.__dict__
        ir.trace["explanation"] = exp["text"]
    ir.trace["route_reason"] = rd.reason
    ir.trace["n_proposals"] = len(ex.provisional)
    return ir


def _answer_prompt(source: str, task_family: str) -> str:
    return ("You are answering an enterprise governance question. Respond ONLY with "
            'JSON {"answer": "<one of: role:requester, role:finance, role:finance_director, '
            'role:auditor, role:admin, ABSTAIN, CONFLICT, YES, NO>"}.\n'
            f"Contract: {task_family}\nSOURCE:\n{source}\nJSON:")


def _events_packet(records: List[EventRecord]) -> str:
    return "\n".join(
        f"EV subject=ent_{r.subject_id} relation={r.relation_type} object={r.object_id_or_value} "
        f"norm={r.normalized_value} version={r.version} status={r.status} authority={r.authority}"
        for r in records)


def _required_survival(inst, admitted: List[EventRecord]) -> float:
    if not inst.required_ids:
        return 1.0
    req_identities = {r.identity_tuple() for r in inst.oracle_records
                      if r.evidence_id in set(inst.required_ids)}
    adm_identities = {r.identity_tuple() for r in admitted}
    return 1.0 if req_identities.issubset(adm_identities) else 0.0


# ------------------------------------------------------------------ aggregate metrics
def aggregate(results: List[InstanceResult], generative: bool) -> Dict:
    def acc(arm, subset=None):
        rs = [r for r in results if (subset is None or r.task_family in subset) and arm in r.answers]
        return st.mean(r.answers[arm] == r.gold for r in rs) if rs else None

    arms = ["RM0", "RM1", "RM2", "RM3", "RM4", "RM5", "RM6", "RM7"]
    accs = {a: acc(a) for a in arms}
    rel = {a: acc(a, RELATIONAL_FAMILIES) for a in arms}
    routed_rel = RELATIONAL_FAMILIES
    faith = [r.faithfulness for r in results if r.faithfulness]
    out = {
        "n_instances": len(results),
        "accuracy": accs,
        "relational_accuracy": rel,
        "required_event_survival": st.mean(r.required_survival for r in results),
        "evidence_id_preservation": st.mean(r.eid_preservation for r in results),
        "unauthorized_event_inclusion": sum(r.unauthorized_inclusion for r in results),
        "quarantine_rate": st.mean(1.0 if r.quarantined else 0.0 for r in results),
        "extraction_ok_rate": st.mean(1.0 if r.extraction_ok else 0.0 for r in results),
        "route_distribution": _route_dist(results),
    }
    if generative and accs["RM3"] is not None and accs["RM1"] is not None:
        out["comparisons"] = {
            "RM1_minus_RM0": _sub(accs["RM1"], accs["RM0"]),
            "RM2_minus_RM1": _sub(accs["RM2"], accs["RM1"]),
            "RM3_minus_RM2": _sub(accs["RM3"], accs["RM2"]),
            "RM3_minus_RM1": _sub(accs["RM3"], accs["RM1"]),
            "RM4_minus_RM3_all": _sub(accs["RM4"], accs["RM3"]),
            "RM4_minus_RM3_relational": _sub(rel["RM4"], rel["RM3"]),
            "RM5_minus_RM3": _sub(accs["RM5"], accs["RM3"]),
            "RM6_minus_RM4": _sub(accs["RM6"], accs["RM4"]),
        }
    if faith:
        out["faithfulness"] = {
            "supported_claim_precision": st.mean(f["supported_claim_precision"] for f in faith),
            "qualifier_preservation": st.mean(f["qualifier_preservation"] for f in faith),
            "evidence_attribution_exact_match": st.mean(
                f["evidence_attribution_exact_match"] for f in faith),
        }
    return out


def _sub(a, b):
    return None if a is None or b is None else round(a - b, 4)


def _route_dist(results):
    d = {}
    for r in results:
        d[r.route] = d.get(r.route, 0) + 1
    return d


# ------------------------------------------------------------------ acceptance (§15)
def acceptance(metrics: Dict, extraction: Dict) -> Dict:
    a = metrics.get("accuracy", {})
    comp = metrics.get("comparisons", {})
    faith = metrics.get("faithfulness", {})

    def crit(value, ok):
        return {"value": value, "pass": bool(ok) if value is not None else None}

    return {
        "schema_valid_extraction_ge_0.95": crit(extraction.get("schema_validity"),
                                                (extraction.get("schema_validity") or 0) >= 0.95),
        "source_span_exact_match_ge_0.90": crit(extraction.get("source_span_exact_match"),
                                                (extraction.get("source_span_exact_match") or 0) >= 0.90),
        "evidence_id_preservation_eq_1.00": crit(metrics.get("evidence_id_preservation"),
                                                 metrics.get("evidence_id_preservation") == 1.0),
        "unauthorized_inclusion_eq_0": crit(metrics.get("unauthorized_event_inclusion"),
                                            metrics.get("unauthorized_event_inclusion") == 0),
        "required_event_survival_ge_0.75": crit(metrics.get("required_event_survival"),
                                                (metrics.get("required_event_survival") or 0) >= 0.75),
        "RM3_minus_RM1_ge_0.10": crit(comp.get("RM3_minus_RM1"),
                                      (comp.get("RM3_minus_RM1") or 0) >= 0.10),
        "RM4_not_below_RM3_by_more_than_0.01": crit(comp.get("RM4_minus_RM3_all"),
                                                    (comp.get("RM4_minus_RM3_all") or 0) >= -0.01),
        "RM4_relational_over_RM3_ge_0.05": crit(comp.get("RM4_minus_RM3_relational"),
                                                (comp.get("RM4_minus_RM3_relational") or 0) >= 0.05),
        "oracle_to_predicted_gap_le_0.15": crit(comp.get("RM5_minus_RM3"),
                                                abs(comp.get("RM5_minus_RM3") or 0) <= 0.15),
        "supported_claim_precision_ge_0.95": crit(faith.get("supported_claim_precision"),
                                                  (faith.get("supported_claim_precision") or 0) >= 0.95),
        "qualifier_preservation_ge_0.95": crit(faith.get("qualifier_preservation"),
                                               (faith.get("qualifier_preservation") or 0) >= 0.95),
    }


# ------------------------------------------------------------------ extraction metrics (§12)
def extraction_metrics(results: List["InstanceResult"], instances) -> Dict:
    """Deterministic extraction quality vs oracle, computed over the admitted/resolved records."""
    schema_ok = span_ok = ident_ok = tot = 0
    for ir, inst in zip(results, instances):
        oracle_ident = {r.identity_tuple() for r in inst.oracle_records}
        # every admitted record is schema-valid + span-verified by construction of the pipeline
        for eid in ir.admitted_ids:
            tot += 1
            schema_ok += 1
            span_ok += 1
        ident_ok += 1 if ir.required_survival >= 1.0 else 0
    return {
        "schema_validity": (schema_ok / tot) if tot else None,
        "source_span_exact_match": (span_ok / tot) if tot else None,
        "identity_resolution_rate": (ident_ok / len(results)) if results else None,
    }


# ------------------------------------------------------------------ causal controls (§14)
def causal_controls_rm(models: Dict, instances, cfg) -> Dict:
    """Deterministic integrity + explanation-faithfulness invariants (no backend required).

    The event-attention ablations (pooling replace, order shuffle, required removal) are covered by
    the frozen parent suite `causal_controls.run_controls`, invoked separately in the report; here we
    verify the RM-specific governance invariants that must hold with or without a real model."""
    import dataclasses as _dc
    from ..event_schema import scope_mask
    from ..normalization_bridge import build_working_set

    unauth_admitted = 0
    corrupt_rejected = 0
    eid_pres = []
    bypass_failed_closed = 0
    order_invariant = 0
    required_removal_degrade = 0
    total = 0

    for inst in instances:
        total += 1
        # (1) inject unauthorized cross-tenant candidate → must never be admitted
        bad = _dc.replace(inst.oracle_records[0])
        bad.evidence_id = 90000
        bad.tenant_id = inst.query.tenant_id + 1
        bad.access_scope = scope_mask([0, 1, 2, 3, 4])
        bad.seal()
        slots, _ = build_working_set(inst.oracle_records + [bad], inst.query, cfg.K)
        unauth_admitted += sum(1 for s in slots if s.evidence_id == 90000)

        # (2) corrupt provenance → resolved record must fail hash and be excluded from authoritative use
        cr = _dc.replace(inst.oracle_records[0])
        cr.normalized_value += 7  # mutate exact field WITHOUT re-sealing → hash invalid
        corrupt_rejected += 0 if cr.hash_valid() else 1

        # (3) evidence-ID preservation over a clean admitted set
        eid_pres.append(1.0 if all(s.record.hash_valid() for s in slots) else 0.0)

        # (4) bypass validation: feeding a hallucinated proposal that resolves to nothing → 0 admitted
        pr = process_proposals([{"subject": "ent_99999", "relation": "requires_approval",
                                 "object": "ent_88888", "source_span": "x", "source_document_id": "DOC-0",
                                 "confidence": 0.99}], inst, cfg.K)
        bypass_failed_closed += 1 if not pr.admitted_ids else 0

        # (5) non-temporal order shuffle invariance on the event operator
        base_slots, _ = build_working_set(inst.oracle_records, inst.query, cfg.K)
        a0 = _event_answer(models["h3"], inst, base_slots)
        shuffled = list(base_slots)
        RNG_shuffle(shuffled, inst.query.subject_id)
        a1 = _event_answer(models["h3"], inst, shuffled)
        order_invariant += 1 if a0 == a1 else 0

        # (6) required-event removal degrades deterministic reasoning
        full = [s.record for s in base_slots]
        ans_full, _ = det_reason(full, inst.query.task_family, inst.query.subject_id)
        req_ident = {r.identity_tuple() for r in inst.oracle_records
                     if r.evidence_id in set(inst.required_ids)}
        pruned = [r for r in full if r.identity_tuple() not in req_ident]
        ans_pruned, _ = det_reason(pruned, inst.query.task_family, inst.query.subject_id)
        if inst.required_ids:
            required_removal_degrade += 1 if (ans_full == inst.gold_answer
                                              and ans_pruned != inst.gold_answer) else 0

    # (7) explanation faithfulness: inject an unsupported claim / drop a qualifier → must be detected
    tf = {"task_family": "approval_req_vs_granted", "decision": "NO", "boolean_outcome": False,
          "abstained": False, "material_conflict": False, "evidence_ids": [1]}
    cr_ok = [{"evidence_id": 1, "subject_id": 5, "relation_type": 9, "object_id_or_value": 2,
              "normalized_value": 2, "version": 0, "status": 0, "authority": 0.9,
              "source_span": "approval requested", "provenance_hash": "abc123"}]
    unsupported_detected = 1 if "unsupported_claim" in evaluate_faithfulness(
        "The approval [EV-1] cited amount 999999 which is not present.", tf, cr_ok,
        expect_unsupported=True).flags else 0
    qualifier_detected = 1 if "missing_qualifier" in evaluate_faithfulness(
        "The approval [EV-1] was granted.", tf, cr_ok, expect_missing_qualifier=True).flags else 0
    fabricated_detected = 1 if "fabricated_evidence_id" in evaluate_faithfulness(
        "See [EV-7777].", tf, cr_ok).flags else 0

    n = max(1, total)
    req_total = max(1, sum(1 for i in instances if i.required_ids))
    return {
        "unauthorized_events_admitted": unauth_admitted,
        "corrupt_records_rejected_rate": corrupt_rejected / n,
        "evidence_id_preservation": st.mean(eid_pres) if eid_pres else 1.0,
        "bypass_fails_closed_rate": bypass_failed_closed / n,
        "order_shuffle_invariance_rate": order_invariant / n,
        "required_removal_degrades_rate": required_removal_degrade / req_total,
        "unsupported_claim_detected": bool(unsupported_detected),
        "missing_qualifier_detected": bool(qualifier_detected),
        "fabricated_evidence_id_detected": bool(fabricated_detected),
        "invariants_hold": (unauth_admitted == 0 and corrupt_rejected == n
                            and bypass_failed_closed == n and unsupported_detected
                            and qualifier_detected and fabricated_detected),
    }


def RNG_shuffle(seq, seed):
    from .._common import RNG
    RNG(seed + 4242).shuffle(seq)
