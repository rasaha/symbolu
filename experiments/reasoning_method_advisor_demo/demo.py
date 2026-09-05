"""RESEARCH-ONLY developer demonstration of the Slice 2 Reasoning Method Advisor.

Lives under ``experiments/`` so it cannot be mistaken for a production API.
It calls the real ``ugence_reasoning_method_advisor.advise`` and reproduces
none of its rules: the only things defined here are (a) the seven-method
research catalog and the versioned research rule set ``rules.research.v0``
as DATA (the same transcription the package's own test fixture carries),
(b) STRICT JSON loaders for a developer-supplied typed task profile and an
optional governed task-class fixture, and (c) two presentations of the
advisory the advisor returns: machine-readable JSON and a concise explanation.

Phase 3 intake ruling (owner, 2026-09-02): developers author the typed profile
directly, one-to-one with the ratified profile fields and structural-signal
tokens; the profile is DEVELOPER_REPORTED; nothing here infers, combines,
defaults or alters a value; and the developer must see and explicitly
confirm the canonical profile before it is submitted. The loader therefore
requires every profile field to be present with its exact type and refuses
unknown keys, and the CLI prints the canonical profile and advises only
when ``--confirm-profile`` is given (bundled examples are pre-confirmed
fixtures and are echoed the same way).

Presentation never changes the advisory: the JSON is a field-for-field
rendering of the ``ReasoningMethodAdvisory`` object, the explanation is
derived from that same object, and ``advisory_digest`` is the object's own
digest. No quality prediction, benchmark claim, cost ranking or production
recommendation is made anywhere here; every advisory is ``RESEARCH_ONLY`` with
``evidence_status = COMPARISON_EVIDENCE_ABSENT``.

Run:
    python -m experiments.reasoning_method_advisor_demo.demo --example 1 [--json|--text|--both]
    python -m experiments.reasoning_method_advisor_demo.demo --profile profile.json \
        [--task-class task_class.json] --advised-at 2026-09-02T12:00:00Z --confirm-profile
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from ugence_reasoning_method_advisor.api import (
    ADVISORY_REQUEST_SCHEMA_VERSION,
    RULE_SET_SCHEMA_VERSION,
    Predicate,
    PredicateKind,
    ReasoningMethodAdvisory,
    ReasoningMethodAdvisoryRequest,
    Rule,
    RuleKind,
    RuleSet,
    advise,
)
from ugence_reasoning_method_governance.api import (
    CATALOG_SCHEMA_VERSION,
    PROFILE_SCHEMA_VERSION,
    TASK_CLASS_SCHEMA_VERSION,
    AggregationRef,
    ComparisonPolicy,
    ConsequenceClass,
    EvidenceAdmissionRef,
    ImplementationEvidence,
    ImplementationEvidenceKind,
    ImplementationStatus,
    ReasoningMethodCatalog,
    ReasoningMethodEntry,
    ResourceDimension,
    SufficiencyKind,
    SufficiencyRule,
    TaskClassIdentity,
    TaskProfile,
    TaskReversibility,
)
from ugence_uvi_policy_contracts.api import ComparisonOperator, GovernedThreshold

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"
DEMO_ISSUER = "experiments:reasoning-method-advisor-demo"
# One fixed instant for the bundled examples so their digests are reproducible.
EXAMPLE_INSTANT = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)

# --------------------------------------------------------------------------- research data
# Seven WorkflowType members with their evidence refs (slice 1 spec §2, 2026-09-02).
_CLASS_LINES = {
    "linear_chain": 291, "tree_of_thought": 396, "iterative_refinement": 523, "debate": 657,
    "map_reduce": 774, "socratic_progressive": 898, "metacognitive": 1011,
}
# Transcription of WorkflowSelector.SIGNAL_MAP (agentic/agentic_framework/reasoning_workflows.py:1177-1188).
# Research provenance for where each rule came from; NOT evidence that the routing is correct.
SIGNAL_MAP_TRANSCRIPTION: Mapping[str, str] = {
    "comparison_request": "map_reduce",
    "causal_reasoning": "linear_chain",
    "ambiguity_detected": "tree_of_thought",
    "creative_synthesis": "iterative_refinement",
    "conditional_logic": "debate",
    "temporal_reasoning": "linear_chain",
    "abstract_concept": "tree_of_thought",
    "meta_reasoning": "linear_chain",
    "multi_part_question": "map_reduce",
    "domain_expertise": "linear_chain",
}
PROVENANCE_REF = "agentic/agentic_framework/reasoning_workflows.py:1177-1188"
RATIONALE = "transcribed from the experimental WorkflowSelector mapping; provenance only"


def research_catalog(issued_at: datetime = EXAMPLE_INSTANT) -> ReasoningMethodCatalog:
    def entry(method_id: str) -> ReasoningMethodEntry:
        evidence = (
            ImplementationEvidence(ImplementationEvidenceKind.CONCRETE_CLASS_REGISTERED, f"agentic/agentic_framework/reasoning_workflows.py:{_CLASS_LINES[method_id]}", issued_at),
            ImplementationEvidence(ImplementationEvidenceKind.STUB_EXECUTION_COMPLETED, "session:2026-09-02:stub-execution", issued_at),
            ImplementationEvidence(ImplementationEvidenceKind.UNIT_TESTS_PRESENT, "agentic/agentic_framework/tests/test_reasoning_workflows.py", issued_at),
        )
        return ReasoningMethodEntry(method_id, "1", method_id.replace("_", " ").title(), evidence, (), (), f"agentic.reasoning_workflows.WorkflowType.{method_id.upper()}")

    entries = tuple(sorted((entry(m) for m in _CLASS_LINES), key=lambda e: e.sort_key))
    return ReasoningMethodCatalog(CATALOG_SCHEMA_VERSION, "cat.rm", "1", entries, DEMO_ISSUER, issued_at)


def research_rules_v0(issued_at: datetime = EXAMPLE_INSTANT) -> RuleSet:
    rules = tuple(
        sorted(
            (
                Rule(f"research.signal.{token}", "0", RuleKind.SUPPORT, Predicate(PredicateKind.STRUCTURAL_TOKEN_PRESENT, (token,)), (method,), PROVENANCE_REF, RATIONALE)
                for token, method in SIGNAL_MAP_TRANSCRIPTION.items()
            ),
            key=lambda r: r.rule_id,
        )
    )
    admissibility = Predicate(PredicateKind.IMPLEMENTATION_STATUS_IN, (ImplementationStatus.EXECUTABLE_TESTED.value,))
    return RuleSet(RULE_SET_SCHEMA_VERSION, "rules.research", "0", admissibility, rules, PROVENANCE_REF, DEMO_ISSUER, issued_at)


# --------------------------------------------------------------------------- JSON loaders
# The canonical profile document: exactly these keys, one-to-one with TaskProfile's
# developer-authored fields (schema_version, policy_refs, declared_by, declared_at and
# assertion_basis are fixed by the contract, not authored here).
PROFILE_STRING_FIELDS = ("profile_id", "domain_ref", "intended_outcome_ref", "population_ref")
PROFILE_ENUM_FIELDS = {"consequence_class": ConsequenceClass, "reversibility": TaskReversibility}
PROFILE_LIST_FIELDS = ("evidence_requirement_refs", "tool_requirement_refs", "structural_characteristics")
PROFILE_FIELDS = frozenset(PROFILE_STRING_FIELDS) | frozenset(PROFILE_ENUM_FIELDS) | frozenset(PROFILE_LIST_FIELDS)


class ProfileDocumentError(ValueError):
    """The developer's profile document is not the canonical shape. Nothing is inferred to repair it."""


def _str_tuple(value: Any, name: str) -> Tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ProfileDocumentError(f"{name} must be a JSON array of strings")
    return tuple(value)


def _str(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ProfileDocumentError(f"{name} must be a JSON string, got {type(value).__name__}")
    return value


def load_profile(data: Mapping[str, Any]) -> TaskProfile:
    """A developer-supplied TYPED profile. Every field must be present with its exact type;
    unknown keys are refused; no value is defaulted, coerced, combined or inferred."""
    if not isinstance(data, Mapping):
        raise ProfileDocumentError("profile must be a JSON object")
    missing = sorted(PROFILE_FIELDS - set(data))
    unknown = sorted(set(data) - PROFILE_FIELDS)
    if missing or unknown:
        raise ProfileDocumentError(f"profile fields missing: {missing or '-'}; unknown: {unknown or '-'}")
    for name, enum_cls in PROFILE_ENUM_FIELDS.items():
        _str(data[name], name)
        if data[name] not in {m.value for m in enum_cls}:
            raise ProfileDocumentError(f"{name} must be one of {sorted(m.value for m in enum_cls)}")
    return TaskProfile(
        PROFILE_SCHEMA_VERSION,
        _str(data["profile_id"], "profile_id"),
        _str(data["domain_ref"], "domain_ref"),
        _str(data["intended_outcome_ref"], "intended_outcome_ref"),
        ConsequenceClass(data["consequence_class"]),
        TaskReversibility(data["reversibility"]),
        _str_tuple(data["evidence_requirement_refs"], "evidence_requirement_refs"),
        _str_tuple(data["tool_requirement_refs"], "tool_requirement_refs"),
        _str_tuple(data["structural_characteristics"], "structural_characteristics"),
        _str(data["population_ref"], "population_ref"),
    )


def canonical_profile_json(profile: TaskProfile) -> str:
    """The canonical profile as the contract holds it, shown to the developer for confirmation."""
    return json.dumps(to_jsonable(profile), indent=2, ensure_ascii=False)


def load_task_class(data: Mapping[str, Any]) -> TaskClassIdentity:
    """An optional governed task-class FIXTURE (research-only), including its comparison policy."""
    pol = data["comparison_policy"]
    thr = pol["threshold"]
    admission = pol.get("evidence_admission")
    rule = SufficiencyRule(
        str(pol["sufficiency_rule_id"]), str(pol["sufficiency_rule_version"]), SufficiencyKind(pol["sufficiency_kind"]),
        GovernedThreshold(str(thr["threshold_id"]), str(thr["unit"]), ComparisonOperator(thr["comparator"]), str(thr["literal"])),
        EvidenceAdmissionRef(str(admission["authority_ref"]), str(admission["result_ref"]), str(admission["admitted_digest"])) if admission else None,
    )
    agg = pol.get("quality_aggregation")
    policy = ComparisonPolicy(
        str(pol["policy_id"]), str(pol["policy_version"]), rule,
        tuple(ResourceDimension(d) for d in pol["resource_dimensions"]),
        AggregationRef(str(agg["aggregation_id"]), str(agg["aggregation_version"]), str(agg["calculation_ref"])) if agg else None,
    )
    return TaskClassIdentity(
        TASK_CLASS_SCHEMA_VERSION, str(data["task_class_id"]), str(data["domain_ref"]), str(data["intended_outcome_ref"]),
        ConsequenceClass(data["consequence_class"]), TaskReversibility(data["reversibility"]),
        _str_tuple(data["evidence_requirement_refs"], "evidence_requirement_refs"),
        _str_tuple(data["tool_requirement_refs"], "tool_requirement_refs"),
        _str_tuple(data["structural_characteristics"], "structural_characteristics"),
        str(data["population_ref"]), str(data["benchmark_set_ref"]), str(data["benchmark_set_digest"]), policy,
    )


def parse_instant(text: str) -> datetime:
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("advised_at must carry a UTC offset (e.g. 2026-09-02T12:00:00Z)")
    return value


# --------------------------------------------------------------------------- the call
def run_demo(profile: Mapping[str, Any], task_class: Optional[Mapping[str, Any]], *, advised_at: datetime, request_id: str = "demo.request") -> ReasoningMethodAdvisory:
    """Build the request from the developer's JSON and call the real advisor."""
    request = ReasoningMethodAdvisoryRequest(
        ADVISORY_REQUEST_SCHEMA_VERSION, request_id, load_profile(profile),
        load_task_class(task_class) if task_class is not None else None,
        research_catalog(), research_rules_v0(), DEMO_ISSUER,
    )
    return advise(request, advised_at=advised_at)


# --------------------------------------------------------------------------- presentation
def to_jsonable(value: Any) -> Any:
    """Field-for-field rendering of the advisory object. Enums by value, datetimes as ISO 8601
    UTC, tuples as arrays, nested dataclasses as objects. Adds nothing and drops nothing."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (tuple, list)):
        return [to_jsonable(v) for v in value]
    raise TypeError(f"unexpected value in advisory: {type(value).__name__}")


def advisory_json(advisory: ReasoningMethodAdvisory, *, indent: Optional[int] = 2, sort_keys: bool = False) -> str:
    return json.dumps(to_jsonable(advisory), indent=indent, sort_keys=sort_keys, ensure_ascii=False)


def _reasons(outcomes) -> str:
    return "; ".join(f"{o.rule_id}@{o.rule_version} [{o.rule_kind.value}] matched {list(o.matched_tokens) or '-'}: {o.rationale_statement}" for o in outcomes)


def explain(advisory: ReasoningMethodAdvisory) -> str:
    """Concise explanation derived only from the advisory object. States what qualifies and
    why, never how well anything performs, costs, or ranks."""
    a = advisory
    lines = [
        f"RESEARCH-ONLY ADVISORY {a.advisory_id} (usage_scope={a.usage_scope}, evidence_status={a.evidence_status})",
        f"classification={a.classification.value}; eligibility={a.eligibility.value}; task_class_digest={a.task_class_digest or 'none'}",
        f"catalog={a.catalog.catalog_id}@{a.catalog.catalog_version}; rule_set={a.rule_set.rule_set_id}@{a.rule_set.rule_set_version} ({a.rule_set.rule_set_digest[:12]}...)",
    ]
    if a.classification.value == "UNCLASSIFIED_EXPLORATORY":
        lines.append("This request declares no governed task class: the advice is exploratory only, ineligible for benchmark comparison, configuration binding or any production authority.")
    lines.append("No comparison evidence was consulted; nothing here predicts quality, cost, latency or outcome.")
    if a.primary is not None:
        lines.append(f"PRIMARY: {a.primary.method_id}@{a.primary.method_version} (basis={a.primary_basis}: it is the only method that qualifies)")
    else:
        lines.append(f"NO PRIMARY: {a.no_primary_reason.value}")
    lines.append(f"QUALIFYING ({len(a.qualifying)}):" if a.qualifying else "QUALIFYING (0): none")
    for q in a.qualifying:
        lines.append(f"  - {q.method.method_id}@{q.method.method_version} [{q.label.value}] because {_reasons(q.inclusion_reasons)}")
    if a.trade_offs:
        lines.append("ALTERNATIVES (no ordering; trade-offs are set differences, not preferences):")
        for t in a.trade_offs:
            reasons = _reasons(t.distinguishing_reasons) or "no distinguishing rule"
            refs = ", ".join(t.distinguishing_requirement_refs) or "no distinguishing requirement refs"
            lines.append(f"  - {t.method.method_id}: {reasons}; {refs}")
    lines.append(f"EXCLUDED ({len(a.excluded)}):")
    for e in a.excluded:
        lines.append(f"  - {e.method.method_id}@{e.method.method_version} [{e.label.value}] because {_reasons(e.exclusion_reasons)}")
    lines.append(f"advisor={a.advisor_identity}@{a.advisor_version}; advised_at={to_jsonable(a.advised_at)}")
    lines.append(f"advisory_digest={a.advisory_digest}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- examples
EXAMPLES: Dict[int, Tuple[str, str, Optional[str]]] = {
    1: ("one qualifying method (primary)", "profile_1_single.json", "task_class_support.json"),
    2: ("multiple qualifying methods, no primary", "profile_2_multiple.json", "task_class_support.json"),
    3: ("no qualifying method", "profile_3_none.json", "task_class_support.json"),
    4: ("unclassified exploratory request (profile only)", "profile_4_unclassified.json", None),
}


def load_example(number: int) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    _, profile_file, class_file = EXAMPLES[number]
    profile = json.loads((EXAMPLES_DIR / profile_file).read_text(encoding="utf-8"))
    task_class = json.loads((EXAMPLES_DIR / class_file).read_text(encoding="utf-8")) if class_file else None
    return profile, task_class


def run_example(number: int) -> ReasoningMethodAdvisory:
    profile, task_class = load_example(number)
    return run_demo(profile, task_class, advised_at=EXAMPLE_INSTANT, request_id=f"demo.example.{number}")


# --------------------------------------------------------------------------- CLI
def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description="RESEARCH-ONLY Reasoning Method Advisor demo (experiments/, not a production API)")
    p.add_argument("--example", type=int, choices=sorted(EXAMPLES), help="run a bundled deterministic example")
    p.add_argument("--profile", type=Path, help="developer-supplied typed task profile (JSON)")
    p.add_argument("--task-class", type=Path, help="optional governed task-class fixture (JSON)")
    p.add_argument("--advised-at", help="required with --profile: ISO 8601 instant with offset; the demo reads no clock")
    p.add_argument("--confirm-profile", action="store_true", help="required with --profile: the developer has reviewed the canonical profile printed by a prior run and confirms it as DEVELOPER_REPORTED")
    p.add_argument("--json", action="store_true", help="print machine-readable JSON only")
    p.add_argument("--text", action="store_true", help="print the explanation only")
    args = p.parse_args(argv)
    show_json, show_text = (True, True) if not (args.json or args.text) else (args.json, args.text)
    if args.example is not None:
        profile_doc, task_class = load_example(args.example)
        advisory = run_example(args.example)
        heading = f"# example {args.example}: {EXAMPLES[args.example][0]}"
    elif args.profile is not None:
        if not args.advised_at:
            p.error("--advised-at is required with --profile (the demo reads no clock)")
        profile_doc = json.loads(args.profile.read_text(encoding="utf-8"))
        task_class = json.loads(args.task_class.read_text(encoding="utf-8")) if args.task_class else None
        canonical = load_profile(profile_doc)
        if not args.confirm_profile:
            print("# canonical profile (DEVELOPER_REPORTED). Review it, then re-run with --confirm-profile to submit it to the advisor.")
            print(canonical_profile_json(canonical))
            return 3
        advisory = run_demo(profile_doc, task_class, advised_at=parse_instant(args.advised_at))
        heading = f"# profile {args.profile} (confirmed canonical profile)"
    else:
        p.error("give --example N or --profile FILE")
        return 2
    if show_text:
        print(heading)
        print("# canonical profile (DEVELOPER_REPORTED):")
        print(canonical_profile_json(load_profile(profile_doc)))
        print(explain(advisory))
    if show_json:
        if show_text:
            print()
        print(advisory_json(advisory))
    return 0


if __name__ == "__main__":
    sys.exit(main())
