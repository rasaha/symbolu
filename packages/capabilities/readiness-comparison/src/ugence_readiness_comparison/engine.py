"""The comparison engine: ``compare(request) -> result``.

Implements specification §5 (outcome rules) and §7 (ports, engine obligations)
exactly. A pure function of the request and a caller-supplied, timezone-aware
``produced_at``: no I/O, no clock read, no normalization or unit conversion, no fetch of a
``benchmark_ref``, no read of ``self_reported_quality``, no averaging, no
fallback across dimensions, no inference of authority from names.

Refusals are values, never exceptions. A request-level refusal makes every
candidate ``COMPARISON_EVIDENCE_ABSENT``; a per-method refusal affects only
that candidate. Output ordering is contractual and enforced by the result
contract itself.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

from ugence_governance_contracts.api import AttestationStatus, MetricClaim, VerificationStatus
from ugence_jcs import canonical_sha256_hex
from ugence_reasoning_method_governance.api import (
    ContractError,
    ContractErrorCode,
    ATTESTATION_ENVELOPE_SCHEMA_VERSION,
    AUTHORITY_RESOLUTION_BASIS_V1,
    COMPARISON_REQUEST_SCHEMA_VERSION,
    COMPARISON_RESULT_SCHEMA_VERSION,
    EVIDENCE_STATUS_SOURCE_V1,
    FIT_SCHEMA_VERSION,
    HIGH_CONSEQUENCE_CLASSES,
    RECORD_SCHEMA_VERSION,
    TASK_CLASS_SCHEMA_VERSION,
    USAGE_SCOPE_RESEARCH_ONLY,
    VERIFICATION_ENVELOPE_SCHEMA_VERSION,
    DominationRecord,
    EvidenceStatusView,
    FitOutcome,
    QualityDirection,
    QualityResult,
    ReadinessComparisonRequest,
    ReadinessComparisonResult,
    ReasoningMethodExecutionRecord,
    ReasoningMethodFitAssessment,
    ReasoningMethodRef,
    Refusal,
    RefusalCode,
    ResourceDelta,
    SufficiencyKind,
)
from ugence_uvi_policy_contracts.api import ComparisonOperator

from .version import __version__

ENGINE_IDENTITY = "ugence-readiness-comparison"

# A quality claim is not independent when any of its evidence references names a
# record's self-reported score. The reference convention is documented here and in
# the harness adapter: "<record_digest>#self_reported_quality".
SELF_REPORTED_QUALITY_MARKER = "self_reported_quality"

_HIGHER = frozenset({ComparisonOperator.GTE, ComparisonOperator.GT})
_LOWER = frozenset({ComparisonOperator.LTE, ComparisonOperator.LT})


def compare(request: ReadinessComparisonRequest, *, produced_at: datetime) -> ReadinessComparisonResult:
    """``produced_at`` is required and caller-supplied (spec §7, correction 30): the
    engine reads no clock. A naive datetime is refused with ``DATETIME_NAIVE``."""
    if not isinstance(request, ReadinessComparisonRequest):
        raise TypeError("compare() takes a ReadinessComparisonRequest")
    if not isinstance(produced_at, datetime) or produced_at.tzinfo is None or produced_at.tzinfo.utcoffset(produced_at) is None:
        raise ContractError(ContractErrorCode.DATETIME_NAIVE, "produced_at must be a timezone-aware datetime")
    ctx = _Context(request, produced_at)
    ctx.run()
    return ctx.result()


class _Context:
    def __init__(self, request: ReadinessComparisonRequest, produced_at: datetime) -> None:
        self.rq = request
        self.produced_at = produced_at
        self.refusals: List[Refusal] = []
        self.request_level = False
        self.ignored: List[str] = []
        self.views: Dict[str, EvidenceStatusView] = {}
        self.records_by_method: Dict[ReasoningMethodRef, List[ReasoningMethodExecutionRecord]] = {}
        self.quality_by_method: Dict[ReasoningMethodRef, List[QualityResult]] = {}
        self.claims: Dict[str, MetricClaim] = {}
        self.direction: Optional[QualityDirection] = None
        self.per_method_refusal: Dict[ReasoningMethodRef, Refusal] = {}
        self.assessments: List[ReasoningMethodFitAssessment] = []

    # ---------------------------------------------------------------- helpers
    def refuse(self, code: RefusalCode, detail: str, method: Optional[ReasoningMethodRef] = None) -> None:
        r = Refusal(code, detail, method)
        self.refusals.append(r)
        if method is None:
            self.request_level = True
        else:
            self.per_method_refusal.setdefault(method, r)

    @property
    def policy(self):
        return self.rq.task_class.comparison_policy

    @property
    def threshold(self):
        return self.policy.sufficiency.threshold

    # ---------------------------------------------------------------- pipeline
    def run(self) -> None:
        self.check_schema_versions()
        self.index_inputs()
        self.check_request_shape()
        self.check_threshold()
        self.check_quality_results()
        self.check_records()
        self.check_admission()
        self.check_envelopes()
        self.assess_all()

    def check_schema_versions(self) -> None:
        rq = self.rq
        bad: List[str] = []
        if rq.schema_version != COMPARISON_REQUEST_SCHEMA_VERSION:
            bad.append(f"request:{rq.schema_version}")
        if rq.task_class.schema_version != TASK_CLASS_SCHEMA_VERSION:
            bad.append(f"task_class:{rq.task_class.schema_version}")
        for r in rq.records:
            if r.schema_version != RECORD_SCHEMA_VERSION:
                bad.append(f"record:{r.schema_version}")
        for e in rq.attestation_envelopes:
            if e.schema_version != ATTESTATION_ENVELOPE_SCHEMA_VERSION:
                bad.append(f"attestation_envelope:{e.schema_version}")
        for e in rq.verification_envelopes:
            if e.schema_version != VERIFICATION_ENVELOPE_SCHEMA_VERSION:
                bad.append(f"verification_envelope:{e.schema_version}")
        if bad:
            self.refuse(RefusalCode.UNSUPPORTED_SCHEMA_VERSION, "unsupported schema version(s): " + ", ".join(sorted(set(bad))))

    def index_inputs(self) -> None:
        for r in self.rq.records:
            self.records_by_method.setdefault(r.method, []).append(r)
        for q in self.rq.quality_results:
            self.quality_by_method.setdefault(q.method, []).append(q)
        for c in self.rq.quality_claims:
            self.claims[c.claim_id] = c

    def check_request_shape(self) -> None:
        if not self.rq.candidates:
            self.refuse(RefusalCode.CANDIDATES_EMPTY, "the request names no candidate method")

    def check_threshold(self) -> None:
        t = self.threshold
        if t.comparator in _HIGHER:
            self.direction = QualityDirection.HIGHER_IS_BETTER
        elif t.comparator in _LOWER:
            self.direction = QualityDirection.LOWER_IS_BETTER
        else:
            self.refuse(RefusalCode.UNSUPPORTED_COMPARATOR, f"comparator {t.comparator.value} admits no quality direction")
        if t.benchmark_ref is not None:
            # Slice 1 carries no port for an admitted Registry entry; the engine never fetches one.
            self.refuse(RefusalCode.THRESHOLD_UNRESOLVABLE, "threshold references a benchmark and no admitted Registry entry is supplied in the request")
        elif not _finite(t.literal_value):
            self.refuse(RefusalCode.SCALE_UNSUPPORTED, f"threshold literal {t.literal_value!r} is not a finite decimal")

    def check_quality_results(self) -> None:
        pol = self.policy
        unit = self.threshold.governed_unit
        for q in self.rq.quality_results:
            if q.governed_unit != unit:
                self.refuse(RefusalCode.UNIT_MISMATCH, f"quality result for {q.method.method_id} is in {q.governed_unit!r}, threshold is in {unit!r}")
            if not _finite(q.value):
                self.refuse(RefusalCode.SCALE_UNSUPPORTED, f"quality value {q.value!r} for {q.method.method_id} is not a finite decimal")
            if q.aggregation is not None and pol.quality_aggregation is None:
                self.refuse(RefusalCode.AGGREGATION_UNDECLARED, f"quality result for {q.method.method_id} is aggregated but the comparison policy declares no aggregation")
            elif q.aggregation is not None and q.aggregation != pol.quality_aggregation:
                self.refuse(RefusalCode.AGGREGATION_UNDECLARED, f"quality result for {q.method.method_id} names an aggregation the comparison policy does not")
            claim = self.claims.get(q.claim_ref)
            if claim is not None and claim.governed_unit != unit:
                self.refuse(RefusalCode.UNIT_MISMATCH, f"claim {q.claim_ref} is in {claim.governed_unit!r}, threshold is in {unit!r}")
        for m, qs in self.quality_by_method.items():
            if len(qs) > 1:
                self.refuse(RefusalCode.AGGREGATION_UNDECLARED, f"more than one quality result for {m.method_id}; one governed result per method is required (5.1-A)")

    def check_records(self) -> None:
        rq = self.rq
        class_digest = rq.task_class.task_class_digest
        for r in rq.records:
            if r.task_class_digest != class_digest:
                self.refuse(RefusalCode.TASK_CLASS_MISMATCH, f"record {r.record_id} was captured under a different task class")
                break
        digests = {r.record_digest for r in rq.records}
        for r in rq.records:
            if r.parent_record_digest is not None and r.parent_record_digest in digests:
                self.refuse(RefusalCode.LINEAGE_UNRESOLVED, f"record {r.record_id} and its parent are both present; lineage authority is not ratified")
                break
        if rq.baseline not in self.records_by_method:
            self.refuse(RefusalCode.BASELINE_ABSENT, f"no record for baseline {rq.baseline.method_id}")
        compared = [rq.baseline] + [c for c in rq.candidates if c != rq.baseline]
        for dim in self.policy.required_dimensions:
            for m in compared:
                for r in self.records_by_method.get(m, []):
                    if r.telemetry.resource_value(dim) is None:
                        self.refuse(RefusalCode.DIMENSION_UNAVAILABLE, f"required dimension {dim.value} unavailable on record {r.record_id} of {m.method_id}; no fallback to fewer dimensions")
                        return

    def check_admission(self) -> None:
        tc = self.rq.task_class
        rule = tc.comparison_policy.sufficiency
        if tc.consequence_class not in HIGH_CONSEQUENCE_CLASSES or rule.kind is not SufficiencyKind.THRESHOLD_BASED:
            return
        ref = rule.supporting_evidence_admission
        if ref is None:
            self.refuse(RefusalCode.THRESHOLD_ONLY_NOT_ADMITTED, "high-consequence threshold-only class without an admission reference")
            return
        resolved = {a.authority_identity for a in self.rq.resolved_authorities}
        for adm in self.rq.resolved_admissions:
            if (
                adm.authority_identity == ref.authority_identity
                and adm.authority_result_ref == ref.authority_result_ref
                and adm.admitted_digest == ref.admitted_digest
                and adm.authority_identity in resolved
            ):
                return
        self.refuse(RefusalCode.THRESHOLD_ONLY_NOT_ADMITTED, "no resolved admission matches the class's supporting-evidence admission reference (requester-asserted resolution)")

    def check_envelopes(self) -> None:
        rq = self.rq
        by_digest = {r.record_digest: r for r in rq.records}
        resolved = {a.authority_identity for a in rq.resolved_authorities}
        requester = rq.requester_identity
        att_ok: Dict[str, Tuple[str, Tuple[str, ...]]] = {}  # attestation envelope digest -> (attester, fields) when resolved
        att_by_digest = {e.envelope_digest: e for e in rq.attestation_envelopes}
        attested: Dict[str, Tuple[str, ...]] = {}
        verified: Dict[str, Tuple[str, ...]] = {}
        for e in rq.attestation_envelopes:
            rec = by_digest.get(e.record_digest)
            if rec is None:
                self.refuse(RefusalCode.ENVELOPE_ORPHAN, f"attestation envelope {e.envelope_id} references no supplied record")
                continue
            if e.attester_identity == rec.issuer_identity or (requester and e.attester_identity == requester):
                self.refuse(RefusalCode.SELF_ATTESTATION, f"attestation envelope {e.envelope_id} is issued by the record's producer or the requester")
                continue
            if e.attester_identity in resolved:
                att_ok[e.envelope_digest] = (e.attester_identity, e.attested_fields)
                attested[e.record_digest] = tuple(sorted(set(attested.get(e.record_digest, ())) | set(e.attested_fields)))
            else:
                self.ignored.append(e.envelope_digest)
        for e in rq.verification_envelopes:
            rec = by_digest.get(e.record_digest)
            if rec is None:
                self.refuse(RefusalCode.ENVELOPE_ORPHAN, f"verification envelope {e.envelope_id} references no supplied record")
                continue
            att = att_by_digest.get(e.attestation_envelope_digest)
            if att is None or att.record_digest != e.record_digest:
                self.refuse(RefusalCode.VERIFICATION_WITHOUT_ATTESTATION, f"verification envelope {e.envelope_id} references no supplied attestation of the same record")
                continue
            if (
                e.verifier_identity == rec.issuer_identity
                or e.verifier_identity == att.attester_identity
                or (requester and e.verifier_identity == requester)
            ):
                self.refuse(RefusalCode.SELF_VERIFICATION, f"verification envelope {e.envelope_id} is issued by the producer, the attester or the requester")
                continue
            if e.verifier_identity in resolved and e.attestation_envelope_digest in att_ok:
                verified[e.record_digest] = tuple(sorted(set(verified.get(e.record_digest, ())) | set(e.verified_fields)))
            else:
                self.ignored.append(e.envelope_digest)
        for r in rq.records:
            a_fields = attested.get(r.record_digest, ())
            v_fields = verified.get(r.record_digest, ())
            self.views[r.record_digest] = EvidenceStatusView(
                record_digest=r.record_digest,
                source_basis=r.source_basis,
                attestation_status=AttestationStatus.ATTESTED if a_fields else AttestationStatus.UNATTESTED,
                verification_status=VerificationStatus.VERIFIED if v_fields else VerificationStatus.UNVERIFIED,
                attested_fields=a_fields,
                verified_fields=v_fields,
            )

    # ---------------------------------------------------------------- outcomes
    def evidence_for(self, m: ReasoningMethodRef) -> Optional[Tuple[ReasoningMethodExecutionRecord, QualityResult, Decimal]]:
        """Per-method evidence, or None with a per-method refusal recorded."""
        recs = self.records_by_method.get(m, [])
        if not recs:
            self.refuse(RefusalCode.METHOD_RECORDS_ABSENT, f"no record for {m.method_id}", m)
            return None
        if len(recs) > 1:
            self.refuse(RefusalCode.RESOURCE_AGGREGATION_UNDECLARED, f"{len(recs)} records for {m.method_id}; slice 1 admits one and names no resource aggregation", m)
            return None
        qs = self.quality_by_method.get(m, [])
        if not qs:
            self.refuse(RefusalCode.QUALITY_RESULT_ABSENT, f"no quality result for {m.method_id}", m)
            return None
        q = qs[0]
        claim = self.claims.get(q.claim_ref)
        if claim is None:
            self.refuse(RefusalCode.QUALITY_RESULT_ABSENT, f"quality result for {m.method_id} references claim {q.claim_ref} which is not supplied", m)
            return None
        if claim.value != q.value:
            self.refuse(RefusalCode.QUALITY_RESULT_ABSENT, f"quality result for {m.method_id} does not match its claim's value", m)
            return None
        for ref in tuple(claim.evidence_refs) + tuple(claim.input_evidence_refs):
            if SELF_REPORTED_QUALITY_MARKER in ref:
                self.refuse(RefusalCode.QUALITY_CLAIM_NOT_INDEPENDENT, f"claim {q.claim_ref} for {m.method_id} derives from a record's self-reported quality", m)
                return None
        return recs[0], q, Decimal(q.value)

    def assess_all(self) -> None:
        rq = self.rq
        pol = self.policy
        dims = pol.required_dimensions
        tau = Decimal(self.threshold.literal_value) if self.threshold.benchmark_ref is None and _finite(self.threshold.literal_value) else None
        evidence: Dict[ReasoningMethodRef, Tuple[ReasoningMethodExecutionRecord, QualityResult, Decimal]] = {}
        compared = [rq.baseline] + [c for c in rq.candidates if c != rq.baseline]
        if not self.request_level:
            for m in compared:
                ev = self.evidence_for(m)
                if ev is not None:
                    evidence[m] = ev
        baseline_rec = self.records_by_method.get(rq.baseline, [None])[0] if self.records_by_method.get(rq.baseline) else None

        sufficient: Dict[ReasoningMethodRef, Tuple[ReasoningMethodExecutionRecord, Decimal]] = {}
        if not self.request_level and tau is not None:
            for m, (rec, _q, val) in evidence.items():
                if _passes(val, tau, self.threshold.comparator):
                    sufficient[m] = (rec, val)

        for m in rq.candidates:
            self.assessments.append(self._assess_one(m, evidence, sufficient, tau, baseline_rec, dims))

    def _assess_one(self, m, evidence, sufficient, tau, baseline_rec, dims) -> ReasoningMethodFitAssessment:
        rq = self.rq
        pol = self.policy
        common = dict(
            schema_version=FIT_SCHEMA_VERSION,
            assessment_id=f"{rq.request_id}:{m.method_id}:{m.method_version}",
            task_class_ref=rq.task_class.task_class_id,
            task_class_digest=rq.task_class.task_class_digest,
            selection_policy_ref="",
            method=m,
            baseline=rq.baseline,
            quality_direction=self.direction,
            dimensions_compared=dims,
            comparison_policy_id=pol.policy_id,
            comparison_policy_version=pol.policy_version,
            evidence_status_source=EVIDENCE_STATUS_SOURCE_V1,
            usage_scope=USAGE_SCOPE_RESEARCH_ONLY,
            assessor_identity=ENGINE_IDENTITY,
            engine_version=__version__,
            assessed_at=self.produced_at,
        )
        recs = self.records_by_method.get(m, [])
        binding_digest = recs[0].binding.binding_digest if recs else (baseline_rec.binding.binding_digest if baseline_rec else _placeholder_binding(rq.request_id))
        input_digests = tuple(sorted(r.record_digest for r in recs))

        if self.request_level or m not in evidence or tau is None:
            if self.request_level:
                reason = "request-level refusal: " + "; ".join(r.detail for r in self.refusals if r.method is None)
            else:
                pr = self.per_method_refusal.get(m)
                reason = pr.detail if pr else "no evidence for method"
            return ReasoningMethodFitAssessment(
                binding_digest=binding_digest,
                outcome=FitOutcome.COMPARISON_EVIDENCE_ABSENT,
                quality_margin=None,
                deltas_vs_baseline=(),
                dominated_by=(),
                quality_result_ref=self.quality_by_method[m][0].claim_ref if self.quality_by_method.get(m) else "",
                input_record_digests=input_digests,
                reason=reason,
                **common,
            )

        rec, q, val = evidence[m]
        margin = val - tau if self.direction is QualityDirection.HIGHER_IS_BETTER else tau - val
        if m not in sufficient:
            return ReasoningMethodFitAssessment(
                binding_digest=binding_digest,
                outcome=FitOutcome.INSUFFICIENT_QUALITY,
                quality_margin=_dstr(margin),
                deltas_vs_baseline=(),
                dominated_by=(),
                quality_result_ref=q.claim_ref,
                input_record_digests=input_digests,
                reason=f"quality {q.value} fails threshold {self.threshold.literal_value} under {self.threshold.comparator.value}",
                **common,
            )

        deltas_vs_baseline = tuple(
            ResourceDelta(dim, rq.baseline, str(rec.telemetry.resource_value(dim) - baseline_rec.telemetry.resource_value(dim)))
            for dim in dims
        )
        dominators: List[DominationRecord] = []
        improvement = pol.sufficiency.kind is SufficiencyKind.IMPROVEMENT_VALUED
        for other, (orec, oval) in sorted(sufficient.items(), key=lambda kv: kv[0].sort_key):
            if other == m:
                continue
            mine = [rec.telemetry.resource_value(d) for d in dims]
            theirs = [orec.telemetry.resource_value(d) for d in dims]
            if all(t <= s for t, s in zip(theirs, mine)) and any(t < s for t, s in zip(theirs, mine)):
                if improvement and not _not_worse(oval, val, self.direction):
                    continue
                qd = None
                if improvement:
                    qd = _dstr(val - oval if self.direction is QualityDirection.HIGHER_IS_BETTER else oval - val)
                dominators.append(
                    DominationRecord(
                        dominator=other,
                        deltas=tuple(ResourceDelta(d, other, str(s - t)) for d, s, t in zip(dims, mine, theirs)),
                        quality_delta=qd,
                    )
                )
        outcome = FitOutcome.SUFFICIENT_RESOURCE_DOMINATED if dominators else FitOutcome.SUFFICIENT_PARETO_EFFICIENT
        reason = (
            "sufficient, but a sufficient alternative is no worse on every required dimension and strictly better on at least one"
            if dominators
            else "sufficient and no tested sufficient alternative dominates it on the required dimensions"
        )
        return ReasoningMethodFitAssessment(
            binding_digest=binding_digest,
            outcome=outcome,
            quality_margin=_dstr(margin),
            deltas_vs_baseline=deltas_vs_baseline,
            dominated_by=tuple(dominators),
            quality_result_ref=q.claim_ref,
            input_record_digests=input_digests,
            reason=reason,
            **common,
        )

    # ---------------------------------------------------------------- result
    def result(self) -> ReadinessComparisonResult:
        rq = self.rq
        return ReadinessComparisonResult(
            schema_version=COMPARISON_RESULT_SCHEMA_VERSION,
            request_id=rq.request_id,
            request_digest=rq.canonical_digest(),
            assessments=tuple(sorted(self.assessments, key=lambda a: a.method.sort_key)),
            refusals=tuple(sorted(self.refusals, key=lambda r: r.sort_key)),
            evidence_status=tuple(sorted(self.views.values(), key=lambda v: v.record_digest)),
            ignored_envelopes=tuple(sorted(self.ignored)),
            authority_resolution_basis=AUTHORITY_RESOLUTION_BASIS_V1,
            engine_identity=ENGINE_IDENTITY,
            engine_version=__version__,
            produced_at=self.produced_at,
        )


def _finite(value: str) -> bool:
    try:
        return Decimal(value).is_finite()
    except (InvalidOperation, ValueError, TypeError):
        return False


def _passes(value: Decimal, tau: Decimal, op: ComparisonOperator) -> bool:
    if op is ComparisonOperator.GTE:
        return value >= tau
    if op is ComparisonOperator.GT:
        return value > tau
    if op is ComparisonOperator.LTE:
        return value <= tau
    if op is ComparisonOperator.LT:
        return value < tau
    return False


def _not_worse(other: Decimal, mine: Decimal, direction: Optional[QualityDirection]) -> bool:
    if direction is QualityDirection.HIGHER_IS_BETTER:
        return other >= mine
    return other <= mine


def _dstr(d: Decimal) -> str:
    return format(d, "f")


def _placeholder_binding(request_id: str) -> str:
    """Only for an evidence-absent assessment of a request with no records at all."""
    return canonical_sha256_hex({"no_records_in_request": request_id})


__all__ = ["ENGINE_IDENTITY", "compare", "SELF_REPORTED_QUALITY_MARKER"]
