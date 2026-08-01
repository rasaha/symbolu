"""Account-takeover historical-replay contract + deterministic runner (§13-§16).

A versioned replay-input schema for ONE narrow account-takeover workflow, a
data-quality report that fails visibly on inadequate evidence, and a deterministic
runner that reconstructs assembly state and produces advisory StoryGraph findings +
review-ready explanations. Synthetic/sanitized fixtures only — it never fabricates
enterprise results, and all enterprise accuracy metrics stay NOT RUN.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..canonical import digest
from ..legitimate import Authorization
from ..storygraph import ObservedEvent
from .. import storyverdict as V
from . import compiler as C

REPLAY_CONTRACT = {
    "version": "ctd.storyreplay/1.0.0",
    "narrow_target": "account-takeover-and-transfer (financial ontology)",
    "record_kinds": ["event", "proposal", "approval", "provider_availability",
                     "identity_snapshot", "execution_receipt"],
    "guarantees": [
        "preserve source_event_id and event_time",
        "reject records without a tenant (no cross-tenant mixing)",
        "deterministic output; no wall-clock/randomness",
        "report unmapped/rejected records; never silently absent",
        "fail visibly when required evidence quality is inadequate",
        "never fabricate enterprise results",
    ],
}

REPLAY_RECORD_FIELDS = (
    "tenant", "source_system", "source_event_id", "record_kind",
    "canonical_event_type", "event_time", "ingestion_time", "source_ordering",
    "workflow_id",
)


def validate_record(rec: dict) -> list:
    errs = []
    for f in REPLAY_RECORD_FIELDS:
        if f not in rec:
            errs.append(f"record {rec.get('source_event_id','?')}: missing '{f}'")
    if rec.get("record_kind") not in REPLAY_CONTRACT["record_kinds"]:
        errs.append(f"record {rec.get('source_event_id','?')}: unknown record_kind "
                    f"{rec.get('record_kind')!r}")
    return errs


def _entities(rec: dict) -> dict:
    e = {}
    for k in ("account", "device", "beneficiary", "destination", "amount"):
        if rec.get(k) is not None:
            e[k] = str(rec[k])
    return e


def _fragment_map(pack: dict) -> dict:
    """canonical_event_type -> fragment_id, from the pack's event mappings + nodes."""
    m = {em["canonical_event_type"]: em["fragment_id"]
         for em in pack.get("event_mappings", [])}
    return m


def data_quality_report(pack: dict, records: list) -> dict:
    """Deterministic pre-replay data-quality report (§14). Fails visibly."""
    frag_map = _fragment_map(pack)
    total = len(records)
    rejected = normalized = unknown_type = unresolved_actor = 0
    unresolved_acct = duplicates = redaction_fail = ordering_conflicts = 0
    missing_fields = 0
    tenants: set = set()
    seen_dedup: dict = {}
    seen_order: dict = {}
    for rec in records:
        if validate_record(rec):
            missing_fields += 1
            rejected += 1
            continue
        if not rec.get("tenant"):
            rejected += 1
            continue
        tenants.add(rec["tenant"])
        if rec["record_kind"] in ("event", "proposal") and \
                rec.get("canonical_event_type") not in frag_map:
            unknown_type += 1
            rejected += 1
            continue
        if rec["record_kind"] in ("event", "proposal") and not rec.get("actor"):
            unresolved_actor += 1
        if rec["record_kind"] in ("event", "proposal") and not rec.get("account"):
            unresolved_acct += 1
        if rec.get("redaction_status") == "FAILED":
            redaction_fail += 1
        dk = (rec["tenant"], rec.get("dedup_identity") or rec["source_event_id"])
        if dk in seen_dedup:
            duplicates += 1
        seen_dedup[dk] = 1
        ok = (rec["tenant"], rec["workflow_id"], rec["source_ordering"])
        if ok in seen_order and seen_order[ok] != rec["source_event_id"]:
            ordering_conflicts += 1
        seen_order[ok] = rec["source_event_id"]
        normalized += 1
    # replay readiness fails visibly on inadequate evidence quality
    ready = (rejected == 0 and redaction_fail == 0 and ordering_conflicts == 0
             and unknown_type == 0)
    return {
        "evidence_label": "Measured — synthetic replay fixture",
        "contract_version": REPLAY_CONTRACT["version"],
        "records_received": total, "records_normalized": normalized,
        "records_rejected": rejected, "missing_required_fields": missing_fields,
        "unknown_event_types": unknown_type, "unresolved_actors": unresolved_actor,
        "unresolved_accounts": unresolved_acct, "duplicate_records": duplicates,
        "ordering_conflicts": ordering_conflicts, "redaction_failures": redaction_fail,
        "distinct_tenants": len(tenants),
        "replay_ready": ready,
        "readiness_note": ("ready" if ready else
                           "NOT READY — rejected/unknown/redaction/ordering issues "
                           "must be resolved before replay"),
    }


@dataclass
class ReplayFinding:
    tenant: str
    workflow_id: str
    category: str
    signal: str
    consequence: str
    completes: bool
    context_status: str
    explanation: str
    finding_digest: str

    def to_dict(self) -> dict:
        return self.__dict__


def _sort_key(rec):
    return (str(rec.get("event_time", "")), int(rec.get("source_ordering", 0)),
            str(rec.get("source_event_id", "")))


def run_replay(pack: dict, records: list, *, now=None) -> dict:
    """Deterministic replay over sanitized fixtures. Advisory findings only."""
    bundle = C.compile_pack(pack)                 # validates the pack first
    frag_map = _fragment_map(pack)
    dq = data_quality_report(pack, records)

    # group valid records by (tenant, workflow)
    groups: dict = {}
    for rec in sorted(records, key=_sort_key):
        if validate_record(rec) or not rec.get("tenant"):
            continue
        groups.setdefault((rec["tenant"], rec["workflow_id"]), []).append(rec)

    findings, per_case = [], []
    for (tenant, wf), recs in sorted(groups.items()):
        assembly, proposal, auths, facts, pos = [], None, [], {}, 0
        for rec in recs:
            kind = rec["record_kind"]
            if kind in ("event", "proposal"):
                frag = frag_map.get(rec["canonical_event_type"])
                if frag is None:
                    continue
                pos += 1
                oe = ObservedEvent(fragment_id=frag, event_id=rec["source_event_id"],
                                   position=int(rec.get("source_ordering", pos)),
                                   epoch=None, actor=str(rec.get("actor", "")),
                                   entities=_entities(rec))
                if kind == "proposal":
                    proposal = oe
                else:
                    assembly.append(oe)
            elif kind == "approval":
                auths.append(Authorization(
                    tag=rec.get("tag", ""), valid=bool(rec.get("valid", True)),
                    covered_operations=frozenset(rec.get("covered_operations", [])),
                    account=str(rec.get("account", "")),
                    device=str(rec.get("device", "")),
                    beneficiary=str(rec.get("beneficiary", "")),
                    destination=str(rec.get("destination", "")),
                    amount_cap=rec.get("amount_cap"),
                    expires_at=rec.get("expires_at")))
            elif kind == "provider_availability":
                if rec.get("state") == "UNAVAILABLE":
                    facts["provider_unavailable"] = True
                elif rec.get("state") == "STALE":
                    facts["context_stale"] = True
                elif rec.get("state") == "CONFLICTING":
                    facts["context_conflicting"] = True
        if proposal is None:
            continue
        legit = list(bundle.legitimate_stories)
        r = V.evaluate_proposed_action(assembly, proposal, bundle.graph,
                                       legitimate_stories=legit, authorizations=auths,
                                       facts=facts, now=now)
        consequence = bundle.consequence_map.get(r.category, "OBSERVE")
        expl = (f"[{consequence}] {r.category}: {r.explanation} "
                f"(context: {r.context_status})")
        fd = digest({"tenant": tenant, "wf": wf, "cat": r.category,
                     "verdict": r.verdict_digest}, domain="CTD-REPLAY-FINDING")
        f = ReplayFinding(
            tenant=tenant, workflow_id=wf, category=r.category, signal=r.signal,
            consequence=consequence,
            completes=r.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY,
            context_status=r.context_status, explanation=expl, finding_digest=fd)
        findings.append(f)
        per_case.append(f.to_dict())

    report_digest = digest({"pack": bundle.bundle_digest,
                            "findings": [f.finding_digest for f in findings],
                            "dq": dq}, domain="CTD-REPLAY-REPORT")
    return {
        "policy_ref": bundle.policy_ref, "bundle_digest": bundle.bundle_digest,
        "data_quality": dq, "n_workflows": len(groups),
        "findings": per_case, "report_digest": report_digest,
        "metrics": replay_metrics(findings, dq),
    }


def replay_metrics(findings: list, dq: dict) -> dict:
    """Structural + operational replay metrics. Enterprise-accuracy metrics stay
    NOT RUN / REQUIRES ENTERPRISE DATA — this runs on synthetic fixtures only."""
    n = len(findings)
    completes = sum(1 for f in findings if f.completes)
    escalate = sum(1 for f in findings if f.signal == "ESCALATE")
    ctx_req = sum(1 for f in findings
                  if f.category == V.ADDITIONAL_CONTEXT_REQUIRED)
    return {
        "evidence_label": "Measured — synthetic replay fixture",
        "workflows_evaluated": n,
        "exact_completion_findings": completes,
        "escalate_findings": escalate,
        "additional_context_required_findings": ctx_req,
        "unavailable_findings": sum(1 for f in findings if f.signal == "UNAVAILABLE"),
        "data_quality_ready": dq["replay_ready"],
        "enterprise_metrics": {
            "unauthorized_action_detection_rate": "REQUIRES ENTERPRISE DATA",
            "benign_review_burden": "REQUIRES ENTERPRISE DATA",
            "operator_agreement_rate": "REQUIRES ENTERPRISE DATA",
            "false_hold_rate": "REQUIRES ENTERPRISE DATA",
            "runtime_per_event_ms": "NOT RUN",
            "replay_throughput": "NOT RUN",
        },
    }
