"""answer_audit.py — Phase 3 answer-audit / post-check layer.

Audits whether an answer COMPLIES with the frozen C×R×S frame selected in Phase 1. This is a
DETECTOR / CLASSIFIER / EXPLAINER, not an automatic rewriter: it emits structured findings (what kind
of frame-violation, how severe, which domain, the textual evidence, a plain-language explanation) and
only RECOMMENDS a rewrite on a small set of high-confidence failure modes.

Phase 3 adds NO new ontology layers. It re-uses the same deterministic, negation-aware detectors that
were validated in Phase 2 / 2B (`rubric.asserted_domains`, `mentioned_domains`,
`has_phoneme_overreach`, `forbidden_rate`), so the audit and the eval rubric agree by construction.
No Bhava/Guna/vrittis/JEPA, no hidden states, no logits, no governance. The frozen Phase 1 scorer
(thresholds 0.20/0.05, grouped-R, S-gated C/R) and the Phase 2 framed prompt are imported read-only
and NOT modified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import rubric as RB
from .match import dominant_terms

# --- finding taxonomy + severity ------------------------------------------------------------------

FINDING_TYPES = (
    "frame_compliant",
    "primary_frame_missing",
    "secondary_promoted_to_primary",
    "rejected_domain_promoted",
    "rejected_domain_mentioned_as_refutation",
    "alternate_true_sense_allowed",
    "phoneme_overreach_claim",
    "factuality_suspected",
    "answer_too_generic",
)

# severity -> confidence that *something* is wrong
_SEV_CONF = {"info": 0.2, "warning": 0.5, "error": 0.8, "critical": 0.9}
_FAIL_SEVERITIES = {"error", "critical"}   # a finding at/above this severity flips `passed` to False


@dataclass
class AnswerAuditFinding:
    finding_type: str
    severity: str                  # info | warning | error | critical
    domain: Optional[str]
    evidence: str
    explanation: str

    @property
    def confidence(self) -> float:
        return _SEV_CONF.get(self.severity, 0.2)

    def to_dict(self) -> Dict:
        return {"finding_type": self.finding_type, "severity": self.severity, "domain": self.domain,
                "evidence": self.evidence, "explanation": self.explanation,
                "confidence": self.confidence}


@dataclass
class AnswerAuditResult:
    answer_id: str
    passed: bool
    needs_rewrite: bool
    confidence: float
    findings: List[AnswerAuditFinding] = field(default_factory=list)
    summary: str = ""
    status: str = "audit_pass"      # audit_pass | audit_warn | audit_rewrite_recommended

    @property
    def finding_types(self) -> List[str]:
        return [f.finding_type for f in self.findings]

    def to_dict(self) -> Dict:
        return {"answer_id": self.answer_id, "passed": self.passed, "needs_rewrite": self.needs_rewrite,
                "confidence": round(self.confidence, 3), "status": self.status, "summary": self.summary,
                "findings": [f.to_dict() for f in self.findings]}


# --- trace extraction (accepts a CSRMatchTrace or a plain dict fixture) ----------------------------

def _trace_domains(csr_trace) -> Dict[str, List[str]]:
    def g(name):
        if isinstance(csr_trace, dict):
            return list(csr_trace.get(name) or [])
        return list(getattr(csr_trace, name, []) or [])
    return {"primary": g("primary_domains"), "secondary": g("secondary_domains"),
            "rejected": g("rejected_domains")}


def _snippet(answer: str, max_len: int = 120) -> str:
    a = " ".join((answer or "").split())
    return a if len(a) <= max_len else a[: max_len - 1] + "…"


# --- term-aware domain detection (Phase-3 sense-awareness; does NOT modify rubric.py) --------------
# A bare polysemous term ("python", "virus", "apple") does NOT by itself commit to a sense — several
# terms are literally registry keywords of one of their senses. So when deciding whether a DOMAIN is
# asserted, we ignore the queried term's own tokens and require *corroborating* domain vocabulary.
# This re-uses rubric's negation-aware sentence/token machinery so it stays aligned with the rubric.

def _term_toks(terms: List[str]) -> set:
    out: set = set()
    for t in terms or []:
        out |= RB._toks(t)
    return out


def _dom_kw(domain: str, term_toks: set) -> set:
    return RB._domain_terms(domain) - term_toks


def _asserted(answer: str, domains: List[str], term_toks: set) -> set:
    """Domains positively asserted via corroborating (non-term) vocabulary in a non-negated clause."""
    out: set = set()
    for s in RB._SENT.findall(answer or ""):
        if RB._NEG_CUE.search(s):
            continue
        st = RB._toks(s)
        for d in domains:
            if st & _dom_kw(d, term_toks):
                out.add(d)
    return out


def _mentioned(answer: str, domains: List[str], term_toks: set) -> set:
    toks = RB._toks(answer)
    return {d for d in domains if toks & _dom_kw(d, term_toks)}


# --- the audit engine -----------------------------------------------------------------------------

def audit_answer(query: str, answer: str, csr_trace, rubric: Optional[Dict] = None,
                 terms: Optional[List[str]] = None,
                 alternate_true_senses: Optional[List[str]] = None,
                 false_claims: Optional[List[str]] = None,
                 answer_id: str = "") -> AnswerAuditResult:
    """Audit `answer` against the frozen C×R×S frame in `csr_trace`. Deterministic; needs no LLM.

    Returns an AnswerAuditResult with structured findings. `passed` is False iff any finding has
    severity error/critical; `confidence` is the max finding confidence.
    """
    answer = answer or ""
    dom = _trace_domains(csr_trace)
    primary, secondary, rejected = dom["primary"], dom["secondary"], dom["rejected"]
    alt_true = list(alternate_true_senses or [])
    false_claims = list(false_claims or [])
    # subject term only (the single most-dominant term): a bare polysemous SUBJECT does not commit to
    # a sense, but domain words the question itself names (e.g. "...in commerce?") must stay detectable.
    terms = terms or (dominant_terms(query)[:1] if query else []) or []

    toks = RB._toks(answer)
    words = answer.split()
    term_present = (not terms) or any(RB._toks(t) & toks for t in terms)

    findings: List[AnswerAuditFinding] = []

    # 0) too-generic / non-answer short-circuits frame analysis: we cannot judge a frame we can't see.
    if len(words) < 5 or not term_present:
        findings.append(AnswerAuditFinding(
            "answer_too_generic", "warning", None, _snippet(answer),
            "Answer is empty, too short, or never mentions the queried term — no frame to audit."))
        return _finalize(answer_id, findings)

    # detectors (negation-aware + term-aware: an item only counts if positively asserted via
    # corroborating non-term vocabulary, not refuted/mentioned, and not via the bare polysemous term)
    term_toks = _term_toks(terms)
    prim_asserted = _asserted(answer, primary, term_toks)
    sec_asserted = _asserted(answer, secondary, term_toks)
    alt_asserted = _asserted(answer, alt_true, term_toks)
    rej_asserted = _asserted(answer, rejected, term_toks)           # leaks
    rej_mentioned = _mentioned(answer, rejected, term_toks)
    rej_refuted = rej_mentioned - rej_asserted                      # named only to deny it
    overreach = RB.has_phoneme_overreach(answer)
    false_viol = RB.forbidden_rate(answer, false_claims) > 0.0

    primary_present = bool(prim_asserted)
    rejected_leak = bool(rej_asserted)
    nonprimary_promoted = (bool(alt_asserted) or bool(sec_asserted)) and not primary_present

    # 1) phoneme-overreach — the one hard C×R×S taboo (assertion that sound proves meaning)
    if overreach:
        findings.append(AnswerAuditFinding(
            "phoneme_overreach_claim", "critical", None, _snippet(answer),
            "Answer asserts that sound/phonemes PROVE meaning — the C×R×S firewall forbids this."))

    # 2) rejected-domain handling
    if rejected_leak:
        sev = "error" if primary_present else "critical"
        ev = ", ".join(sorted(rej_asserted))
        why = ("an irrelevant rejected domain is asserted as the answer frame while the primary is "
               "absent" if not primary_present else
               "a rejected domain is asserted alongside the primary frame (a leak)")
        findings.append(AnswerAuditFinding(
            "rejected_domain_promoted", sev, sorted(rej_asserted)[0], ev,
            f"Rejected domain(s) {ev} positively asserted — {why}."))
    for d in sorted(rej_refuted):                                   # refutation is NOT a leak (info)
        findings.append(AnswerAuditFinding(
            "rejected_domain_mentioned_as_refutation", "info", d, d,
            f"Rejected domain '{d}' is named only to refute it — not a leak."))

    # 3) primary-frame presence
    if not primary_present:
        findings.append(AnswerAuditFinding(
            "primary_frame_missing", "error", (primary[0] if primary else None),
            _snippet(answer),
            f"The primary domain(s) {primary or '(none)'} are never positively asserted."))

    # 4) promotion of a non-primary sense to the lead (only meaningful when primary is absent)
    if nonprimary_promoted:
        promoted = sorted(alt_asserted | sec_asserted)
        findings.append(AnswerAuditFinding(
            "secondary_promoted_to_primary", "error", (promoted[0] if promoted else None),
            ", ".join(promoted),
            f"Non-primary sense(s) {', '.join(promoted)} lead the answer while the primary is absent."))
    elif alt_asserted and primary_present:                         # alt sense alongside primary: OK
        for d in sorted(alt_asserted):
            findings.append(AnswerAuditFinding(
                "alternate_true_sense_allowed", "info", d, d,
                f"Alternate true sense '{d}' is mentioned alongside the asserted primary — allowed."))

    # 5) factuality (independent of frame compliance; a registered false claim positively asserted)
    if false_viol:
        findings.append(AnswerAuditFinding(
            "factuality_suspected", "error", None, _snippet(answer),
            "A registered false claim appears to be positively asserted (suspected factual error)."))

    # 6) frame_compliant iff the answer leads with the primary and has no frame violation/overreach
    if (primary_present and not rejected_leak and not nonprimary_promoted
            and not overreach and not false_viol):
        findings.insert(0, AnswerAuditFinding(
            "frame_compliant", "info", (primary[0] if primary else None),
            _snippet(answer),
            "Primary frame asserted; no rejected leak, promotion, overreach, or false claim."))

    return _finalize(answer_id, findings)


def _finalize(answer_id: str, findings: List[AnswerAuditFinding]) -> AnswerAuditResult:
    passed = not any(f.severity in _FAIL_SEVERITIES for f in findings)
    confidence = max((f.confidence for f in findings), default=0.0)
    res = AnswerAuditResult(answer_id=answer_id, passed=passed, needs_rewrite=False,
                            confidence=confidence, findings=findings)
    res.needs_rewrite = should_rewrite(res)
    res.status = ("audit_rewrite_recommended" if res.needs_rewrite
                  else ("audit_pass" if passed else "audit_warn"))
    res.summary = _summarize(res)
    return res


def _summarize(res: AnswerAuditResult) -> str:
    if not res.findings:
        return "no findings"
    types = []
    for f in res.findings:                                         # de-dup, keep order
        if f.finding_type not in types:
            types.append(f.finding_type)
    tail = "; rewrite recommended" if res.needs_rewrite else ("; passed" if res.passed else "; warn")
    return ", ".join(types) + tail


# --- conservative rewrite policy ------------------------------------------------------------------

def should_rewrite(res: AnswerAuditResult) -> bool:
    """Recommend a rewrite ONLY on high-confidence frame failures. Biased toward NOT rewriting.

    True iff: a critical rejected_domain_promoted, OR a critical phoneme_overreach_claim, OR a
    primary_frame_missing with confidence >= 0.75, OR a secondary_promoted_to_primary with
    confidence >= 0.75. Everything else (alternate_true_sense_allowed, refutation, factuality on its
    own, answer_too_generic) is flagged but NOT rewritten.
    """
    for f in res.findings:
        if f.finding_type == "rejected_domain_promoted" and f.severity == "critical":
            return True
        if f.finding_type == "phoneme_overreach_claim" and f.severity == "critical":
            return True
        if f.finding_type == "primary_frame_missing" and f.confidence >= 0.75:
            return True
        if f.finding_type == "secondary_promoted_to_primary" and f.confidence >= 0.75:
            return True
    return False


# --- optional rewrite prompt (only consulted under --rewrite-mode suggest/auto) --------------------

def build_rewrite_prompt(query: str, answer: str, csr_trace, audit_result: AnswerAuditResult) -> str:
    """Build a minimal correction prompt that names the specific findings to fix and re-states the
    frame. This is a NEW Phase 3 artifact — it does NOT edit the frozen Phase 2 framed prompt."""
    dom = _trace_domains(csr_trace)

    def fmt(xs):
        return ", ".join(xs) if xs else "(none)"

    problems = [f"- {f.finding_type} ({f.severity}): {f.explanation}"
                for f in audit_result.findings if f.severity in _FAIL_SEVERITIES]
    tag = f"[[id:{audit_result.answer_id}]]\n" if audit_result.answer_id else ""
    return (
        f"{tag}Rewrite the answer so it stays inside the selected C×R×S semantic frame.\n"
        f"Primary domains: {fmt(dom['primary'])}\n"
        f"Secondary domains (mention only if useful): {fmt(dom['secondary'])}\n"
        f"Rejected domains (do NOT frame the answer around these): {fmt(dom['rejected'])}\n"
        "Problems to fix:\n" + ("\n".join(problems) if problems else "- (none)") + "\n"
        "Lead with the primary domain. Do not claim phonemes alone prove meaning. "
        "Preserve factual correctness.\n\n"
        f"User question:\n{query}\n\nOriginal answer:\n{answer}\n")
