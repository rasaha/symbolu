#!/usr/bin/env python3
"""
Aggregation, verdict classification, and Markdown/JSON reporting.

Verdict vocabulary (deliberately conservative — prefer a failed verdict to an
optimistic one):
  * VALIDATED           — no unsafe handovers; complete decisive/defeater/
                          precedence recall; coverage detection perfect; fails
                          closed on every should-refuse case.
  * PARTIALLY VALIDATED — some safety properties hold, others do not.
  * FALSIFIED           — the sovereign layer accepts incomplete packets often
                          enough, or misses decisive evidence badly enough, that
                          the null hypothesis stands: it cannot reliably produce
                          complete evidence packets.
"""

from __future__ import annotations

import json

from .harness import CaseResult
from .metrics import Aggregate, Frac


def aggregate(results: list[CaseResult]) -> Aggregate:
    agg = Aggregate(n_cases=len(results))
    for r in results:
        agg.critical_evidence_recall = agg.critical_evidence_recall.merge(Frac(num=r.decisive[0], den=r.decisive[1]))
        agg.defeater_recall = agg.defeater_recall.merge(Frac(num=r.defeater[0], den=r.defeater[1]))
        agg.definition_recall = agg.definition_recall.merge(Frac(num=r.definition[0], den=r.definition[1]))
        agg.precedence_recall = agg.precedence_recall.merge(Frac(num=r.precedence[0], den=r.precedence[1]))
        agg.unsupported_claim = agg.unsupported_claim.merge(Frac(num=r.unsupported[0], den=r.unsupported[1]))
        agg.packet_sufficiency = agg.packet_sufficiency.merge(Frac(num=int(r.packet_sufficient), den=1))
        agg.coverage_completeness = agg.coverage_completeness.merge(Frac(num=int(r.coverage_ok), den=1))
        agg.routing_accuracy = agg.routing_accuracy.merge(Frac(num=int(r.routing_correct), den=1))
        if r.decisive_missing:
            agg.unsafe_handover = agg.unsafe_handover.merge(Frac(num=int(r.unsafe_handover), den=1))
        if r.should_refuse:
            agg.fail_closed = agg.fail_closed.merge(Frac(num=int(r.refused), den=1))
    return agg


def _pct(f: Frac) -> str:
    v = f.value
    return "n/a" if v is None else f"{v * 100:.1f}% ({f.num}/{f.den})"


def classify(aug: Aggregate) -> tuple[str, list[str]]:
    reasons: list[str] = []
    unsafe = aug.unsafe_handover.value
    cer = aug.critical_evidence_recall.value
    dfr = aug.defeater_recall.value
    fc = aug.fail_closed.value
    cov = aug.coverage_completeness.value

    perfect = (
        (unsafe in (None, 0.0))
        and (cer in (None, 1.0))
        and (dfr in (None, 1.0))
        and (fc in (None, 1.0))
        and (cov in (None, 1.0))
    )
    if perfect:
        return "VALIDATED", ["no unsafe handovers; complete recall; fails closed on all should-refuse cases"]

    if unsafe and unsafe > 0:
        reasons.append(f"Unsafe Handover Rate = {_pct(aug.unsafe_handover)} (must be 0 — architecture must fail closed)")
    if fc is not None and fc < 1.0:
        reasons.append(f"Fail-closed rate = {_pct(aug.fail_closed)} (accepted packets it should have refused)")
    if dfr is not None and dfr < 1.0:
        reasons.append(f"Defeater Recall = {_pct(aug.defeater_recall)} (missed exceptions/overrides are critical)")
    if cer is not None and cer < 1.0:
        reasons.append(f"Critical Evidence Recall = {_pct(aug.critical_evidence_recall)}")
    if cov is not None and cov < 1.0:
        reasons.append(f"Coverage Completeness = {_pct(aug.coverage_completeness)}")

    severe = ((unsafe or 0) >= 0.5) or ((cer if cer is not None else 1) < 0.75) or ((fc if fc is not None else 1) < 0.5)
    label = "FALSIFIED" if severe else "PARTIALLY VALIDATED"
    return label, reasons


def build_report(
    gates: list[CaseResult], augmented: list[CaseResult]
) -> dict:
    agg_g = aggregate(gates)
    agg_a = aggregate(augmented)
    label, reasons = classify(agg_a)

    # recurring failure modes: cases unsafe under augmented
    unsafe_cases = sorted({r.case_id for r in augmented if r.unsafe_handover})
    missed_defeaters = sorted({r.case_id for r in augmented if r.defeater[1] and r.defeater[0] < r.defeater[1]})
    missed_defs = sorted({r.case_id for r in augmented if r.definition[1] and r.definition[0] < r.definition[1]})

    return {
        "meta": {"synthetic": True, "n_gates_runs": len(gates), "n_augmented_runs": len(augmented)},
        "verdict": label,
        "verdict_reasons": reasons,
        "metrics": {
            "gates_only": _agg_dict(agg_g),
            "augmented": _agg_dict(agg_a),
        },
        "key_finding_unsafe_handover": {
            "gates_only": _pct(agg_g.unsafe_handover),
            "augmented": _pct(agg_a.unsafe_handover),
        },
        "recurring_failures": {
            "unsafe_under_augmented": unsafe_cases,
            "missed_defeaters": missed_defeaters,
            "missed_definitions": missed_defs,
        },
        "per_case": [_case_dict(r) for r in augmented],
    }


def _agg_dict(a: Aggregate) -> dict:
    return {
        "critical_evidence_recall": _pct(a.critical_evidence_recall),
        "defeater_recall": _pct(a.defeater_recall),
        "definition_recall": _pct(a.definition_recall),
        "precedence_recall": _pct(a.precedence_recall),
        "packet_sufficiency": _pct(a.packet_sufficiency),
        "unsafe_handover_rate": _pct(a.unsafe_handover),
        "unsupported_claim_rate": _pct(a.unsupported_claim),
        "coverage_completeness": _pct(a.coverage_completeness),
        "routing_accuracy": _pct(a.routing_accuracy),
        "fail_closed_rate": _pct(a.fail_closed),
    }


def _case_dict(r: CaseResult) -> dict:
    return {
        "case_id": r.case_id, "injector": r.injector, "failure_mode": r.failure_mode,
        "decision": r.system_decision, "expected": r.expected_routing,
        "decisive": f"{r.decisive[0]}/{r.decisive[1]}",
        "defeater": f"{r.defeater[0]}/{r.defeater[1]}",
        "definition": f"{r.definition[0]}/{r.definition[1]}",
        "precedence": f"{r.precedence[0]}/{r.precedence[1]}",
        "decisive_missing": r.decisive_missing, "accepted": r.accepted,
        "unsafe": r.unsafe_handover, "sufficient": r.packet_sufficient,
        "coverage_ok": r.coverage_ok, "blocked_by": r.blocked_by,
    }


LIMITATIONS = [
    "All corpora are SYNTHETIC and small; results bound the framework's behaviour, not real-world efficacy.",
    "The extractor under test is the frozen deterministic keyword/sentence extractor, NOT a neural HybridPhaseTransformer. Its failures are the baseline's, not necessarily the architecture's ceiling.",
    "Definitional-conflict omissions are measured (definition_recall) but NOT independently blocked by any validator — the contradiction search keys on defeater language, not on conflicting definitions.",
    "Numeric prose-vs-table conflicts (conflicting_tables) are not automatically detected; both spans may be present while the resolver silently picks one.",
    "'Packet sufficiency' is computed with the deterministic resolver as the downstream reasoner and is therefore bounded by that resolver's capability, not a frontier model's.",
    "Token-reduction / private-data-retention claims are demonstrated on synthetic corpora only.",
]

NEXT_PHASE = [
    "Replace the deterministic extractor with a HybridPhaseTransformer-backed extractor implementing ExtractorProtocol, and re-run this identical framework to get the first neural numbers.",
    "Add a DefinitionConflictValidator that detects multiple governing definitions of the same defined term and blocks handover.",
    "Add a numeric-conflict validator for prose-vs-table disagreements.",
    "Source a small REAL (non-synthetic) contract set under NDA to replace at least the control corpora and measure real Critical Evidence Recall.",
    "Calibrate an abstention/confidence threshold so the extractor itself proposes REFUSE, rather than relying solely on downstream validators.",
]


def render_markdown(report: dict) -> str:
    m = report["metrics"]
    L = []
    L.append("# Hybrid Handover — Enterprise Readiness Evaluation\n")
    L.append("> **SYNTHETIC EVALUATION.** All corpora are synthetic. This measures whether the "
             "sovereign hybrid layer can reliably produce *complete* evidence packets. It prioritises "
             "evidence completeness over generated-answer quality, and attempts to *falsify* the design.\n")
    L.append(f"## Verdict: **{report['verdict']}**\n")
    if report["verdict_reasons"]:
        L.append("Preventing a stronger verdict:\n")
        for r in report["verdict_reasons"]:
            L.append(f"- {r}")
        L.append("")

    L.append("## Key finding — does independent validation reduce unsafe handovers?\n")
    L.append("| Configuration | Unsafe Handover Rate (P(accept \\| decisive missing)) |")
    L.append("|---|---|")
    L.append(f"| Frozen gates only | {report['key_finding_unsafe_handover']['gates_only']} |")
    L.append(f"| Gates + independent validators | {report['key_finding_unsafe_handover']['augmented']} |")
    L.append("")

    L.append("## Primary enterprise-readiness metrics (augmented config)\n")
    a = m["augmented"]
    L.append("| Metric | Value |")
    L.append("|---|---|")
    L.append(f"| Critical Evidence Recall | {a['critical_evidence_recall']} |")
    L.append(f"| Defeater Recall | {a['defeater_recall']} |")
    L.append(f"| Definition Recall | {a['definition_recall']} |")
    L.append(f"| Precedence Recall | {a['precedence_recall']} |")
    L.append(f"| Packet Sufficiency Rate | {a['packet_sufficiency']} |")
    L.append(f"| **Unsafe Handover Rate** | **{a['unsafe_handover_rate']}** |")
    L.append(f"| Unsupported Claim Rate | {a['unsupported_claim_rate']} |")
    L.append(f"| Coverage Completeness | {a['coverage_completeness']} |")
    L.append(f"| Routing Accuracy | {a['routing_accuracy']} |")
    L.append(f"| Fail-closed Rate (should-refuse cases) | {a['fail_closed_rate']} |")
    L.append("")

    L.append("## Recurring failure modes\n")
    rf = report["recurring_failures"]
    L.append(f"- Unsafe under augmented validation: `{rf['unsafe_under_augmented'] or 'none'}`")
    L.append(f"- Missed defeaters (exceptions/overrides): `{rf['missed_defeaters'] or 'none'}`")
    L.append(f"- Missed definitions: `{rf['missed_definitions'] or 'none'}`")
    L.append("")

    L.append("## Per-case results (augmented)\n")
    L.append("| Case | Injector | Decision | Exp | Dec | Def | Defn | Prec | Missing | Unsafe | Suff | Cov |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in report["per_case"]:
        L.append(
            f"| {c['case_id']} | {c['injector']} | {c['decision']} | {c['expected']} | "
            f"{c['decisive']} | {c['defeater']} | {c['definition']} | {c['precedence']} | "
            f"{'Y' if c['decisive_missing'] else '.'} | {'**Y**' if c['unsafe'] else '.'} | "
            f"{'Y' if c['sufficient'] else '.'} | {'Y' if c['coverage_ok'] else '.'} |"
        )
    L.append("")

    L.append("## Enterprise positioning — what is / is NOT supported by these results\n")
    L.append("| Claim | Supported by this run? |")
    L.append("|---|---|")
    ur_g = report['key_finding_unsafe_handover']['gates_only']
    ur_a = report['key_finding_unsafe_handover']['augmented']
    L.append(f"| Evidence-grounded escalation (fails closed) | **No** — nonzero unsafe handover ({ur_a} augmented, {ur_g} gates-only) |")
    L.append("| Reduced long-context frontier token usage | Demonstrated only on synthetic corpora (see handover demo); not a real-world measurement |")
    L.append("| Private data stays in perimeter (redaction) | Mechanically enforced + tested, on synthetic data |")
    L.append("| Auditability | Yes — every decision, gate, and validator finding is recorded |")
    L.append("| Reduced unsupported generation | Partial — unsupported-claim rate measured; not zero |")
    L.append("")

    L.append("## Known limitations\n")
    for x in LIMITATIONS:
        L.append(f"- {x}")
    L.append("")
    L.append("## Recommended next research phase\n")
    for x in NEXT_PHASE:
        L.append(f"- {x}")
    L.append("")
    return "\n".join(L)


def render_json(report: dict) -> str:
    return json.dumps(report, indent=2)
