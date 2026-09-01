"""Documentation-drift gate for the readiness / governed-value explainer.

``docs/AGENT_READINESS_AND_ROI_PLAIN_ENGLISH.md`` quotes live output from two
packages: the Stage 1 verdict from ``assess_readiness``
(``ugence-agent-value-readiness``) and the Stage 2 money figures from
``score_case`` (``governed-value``). Both are transcribed from real runs, so
both rot silently when either package changes.

This gate rebuilds each worked example and compares the document against what
the code now produces. The document supplies the **inputs** — every rupee figure
in the Stage 2 tables is parsed out and fed to the kernel — so an edit that
changes an input without updating the stated result fails here too, not only a
change in package behaviour.

Every failure names the document line that has gone stale.

The Stage 1 gate and condition verifiers are the test-only stubs from
``packages/capabilities/agent-value-readiness/tests/orchestration/``. That is
deliberate and is what the document itself says: the distribution ships no gate
or condition verifier, and the absence of any allow-all verifier is the trust
boundary. This gate therefore pins the classification logic and the
orchestration boundary, not the independent establishment of a gate status.
"""

from __future__ import annotations

import re
import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "AGENT_READINESS_AND_ROI_PLAIN_ENGLISH.md"
DOC_REL = DOC_PATH.relative_to(REPO_ROOT)

# The readiness orchestration fixtures are that package's own test helpers.
_READINESS_TESTS = (
    REPO_ROOT / "packages" / "capabilities" / "agent-value-readiness" / "tests"
)
for _p in (_READINESS_TESTS, _READINESS_TESTS / "orchestration"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# --------------------------------------------------------------------------- #
# Document parsing — every claim carries the line number it came from
# --------------------------------------------------------------------------- #
class Claim:
    """One value the document asserts, with its 1-indexed source line."""

    __slots__ = ("value", "line", "raw")

    def __init__(self, value, line: int, raw: str):
        self.value = value
        self.line = line
        self.raw = raw.strip()

    def where(self) -> str:
        return f"{DOC_REL}:{self.line}  ->  {self.raw!r}"


def _lines() -> list[str]:
    if not DOC_PATH.is_file():
        raise AssertionError(f"{DOC_REL} is missing; the drift gate has nothing to check")
    return DOC_PATH.read_text(encoding="utf-8").splitlines()


def _labelled(lines, label, *, start=0, end=None):
    """First ``label   value`` line in a fenced block. Returns a :class:`Claim`."""
    pattern = re.compile(rf"^\s*{re.escape(label)}\s{{2,}}(\S.*?)\s*$")
    for i, raw in enumerate(lines[start:end], start=start):
        m = pattern.match(raw)
        if m:
            return Claim(m.group(1).strip(), i + 1, raw)
    raise AssertionError(
        f"{DOC_REL}: no `{label}` line found in the expected block; "
        "the worked example's shape changed — update this gate deliberately"
    )


def _code_list(lines, label, *, start=0, end=None):
    """A ``label`` line plus its continuation lines, e.g. reason/advisory codes."""
    first = _labelled(lines, label, start=start, end=end)
    codes = [Claim(first.value, first.line, first.raw)]
    indent_only = re.compile(r"^\s{4,}([A-Z][A-Z0-9_]+)\s*$")
    for i in range(first.line, len(lines)):
        m = indent_only.match(lines[i])
        if not m:
            break
        codes.append(Claim(m.group(1), i + 1, lines[i]))
    return codes


def _rupees(text: str) -> list[Decimal]:
    return [Decimal(x) for x in re.findall(r"₹([\d]+(?:\.[\d]+)?)", text)]


def _row(lines, needle, *, start=0, end=None):
    """The first table row containing ``needle``."""
    for i, raw in enumerate(lines[start:end], start=start):
        if needle in raw and raw.lstrip().startswith("|"):
            return i + 1, raw
    raise AssertionError(
        f"{DOC_REL}: no table row containing {needle!r}; "
        "the worked example's shape changed — update this gate deliberately"
    )


def _row_amount(lines, needle, *, start=0, end=None):
    """The LAST rupee amount on the row — the row's own total."""
    line_no, raw = _row(lines, needle, start=start, end=end)
    amounts = _rupees(raw)
    if not amounts:
        raise AssertionError(f"{DOC_REL}:{line_no}: row {needle!r} states no ₹ amount")
    return Claim(amounts[-1], line_no, raw)


def _section(lines, heading) -> int:
    for i, raw in enumerate(lines):
        if raw.strip() == heading:
            return i
    raise AssertionError(f"{DOC_REL}: heading {heading!r} not found")


LAKH_PAISE = 100_000 * 100  # one lakh rupees, in paise


def _to_paise(lakh: Decimal) -> int:
    return int(lakh * LAKH_PAISE)


# --------------------------------------------------------------------------- #
# Stage 1 — the readiness assessment
# --------------------------------------------------------------------------- #
def _run_stage_one(target=None, *, conditions=None, gates=None, condition_verifier=...):
    from _orchestration_fixtures import (  # noqa: E402
        CONDITIONAL,
        MANDATORY,
        PROD,
        StubConditionVerifier,
        StubGateVerifier,
        condition,
        gate,
        gate_result,
        issued_resolver,
        readiness_policy,
        request,
    )
    from ugence_agent_value_readiness.api import GateStatus, assess_readiness
    from ugence_uvi_policy_contracts.api import GateCategory

    target = PROD if target is None else target
    policy = readiness_policy(
        [
            gate("accuracy", MANDATORY, category=GateCategory.QUALITY),
            gate("security", MANDATORY, category=GateCategory.SECURITY),
            gate("human-escalation", CONDITIONAL, compensable=True,
                 category=GateCategory.SAFETY),
            gate("regional-language", CONDITIONAL, compensable=True,
                 category=GateCategory.QUALITY),
        ],
        policy_id="support-agent-readiness",
    )
    if gates is None:
        gates = [
            gate_result(policy, "accuracy", GateStatus.PASS, target=target),
            gate_result(policy, "security", GateStatus.PASS, target=target),
            gate_result(policy, "human-escalation", GateStatus.FAIL, target=target),
            gate_result(policy, "regional-language", GateStatus.FAIL, target=target),
        ]
    else:
        gates = [gate_result(policy, gid, st, target=target) for gid, st in gates]
    if conditions is None:
        conditions = [
            condition("cond-escalation-desk", "human-escalation"),
            condition("cond-english-only-rollout", "regional-language"),
        ]
    verifier = (
        StubConditionVerifier() if condition_verifier is ... else condition_verifier
    )
    return assess_readiness(
        request(policy=policy, gate_results=gates, conditions=conditions, target=target),
        policy_resolver=issued_resolver(policy),
        gate_verifier=StubGateVerifier(),
        condition_verifier=verifier,
    )


# --------------------------------------------------------------------------- #
# Stage 2 — the governed-value calculation, built from the document's figures
# --------------------------------------------------------------------------- #
_COST_FIELDS = {
    "inference": "inference",
    "retries": "retries",
    "evals": "evals",
    "monitoring": "monitoring",
    "human-in-loop review": "human_in_loop_review",
    "incident remediation": "incident_remediation",
    "model migration": "model_migration",
}


def _documented_stage_two_inputs(lines):
    """Parse every Stage 2 input figure the document states."""
    start = _section(lines, "### Stage 2 — three months later: governed value")
    end = _section(lines, "### What connects the two stages")

    inputs = {
        "labor_displaced": _row_amount(lines, "Labour displaced", start=start, end=end),
        "throughput_gained": _row_amount(lines, "Throughput gained", start=start, end=end),
        "loss_avoided": _row_amount(lines, "Loss avoided", start=start, end=end),
        "total_benefit": _row_amount(lines, "**Total benefit**", start=start, end=end),
        "actual_losses": _row_amount(lines, "Actual losses incurred", start=start, end=end),
        "cost_to_serve": _row_amount(lines, "Cost to serve —", start=start, end=end),
    }

    # The seven cost components are itemized inline on the cost-to-serve row.
    cost_line_no, cost_raw = _row(lines, "Cost to serve —", start=start, end=end)
    components = {}
    for label, field in _COST_FIELDS.items():
        m = re.search(rf"{re.escape(label)}\s*₹([\d.]+)", cost_raw)
        if m is None:
            raise AssertionError(
                f"{DOC_REL}:{cost_line_no}: cost-to-serve row no longer itemizes "
                f"{label!r}; a TCO component vanished from the document"
            )
        components[field] = Claim(Decimal(m.group(1)), cost_line_no, cost_raw)
    inputs["cost_components"] = components

    # Expected-loss items: probability, magnitude, expected value.
    items = []
    for needle in ("Wrongful refund", "Regulatory complaint"):
        line_no, raw = _row(lines, needle, start=start, end=end)
        prob = re.search(r"\|\s*(0\.\d+)\s*\|", raw)
        amounts = _rupees(raw)
        if prob is None or len(amounts) != 2:
            raise AssertionError(
                f"{DOC_REL}:{line_no}: expected-loss row {needle!r} no longer reads "
                "as `| item | probability | magnitude | expected loss |`"
            )
        items.append(
            {
                "label": needle,
                "probability": Claim(Decimal(prob.group(1)), line_no, raw),
                "magnitude": Claim(amounts[0], line_no, raw),
                "expected": Claim(amounts[1], line_no, raw),
            }
        )
    inputs["expected_loss_items"] = items
    inputs["residual_expected_loss"] = _row_amount(
        lines, "**Residual expected loss**", start=start, end=end
    )

    # Investment is stated in prose as a sum ending in the total. The sentence
    # wraps, so join the whole paragraph before reading its amounts.
    inv_line_no = inv_raw = None
    for i, raw in enumerate(lines[start:end], start=start):
        if "amortized cost-to-serve" in raw and "₹" in raw:
            para = []
            for j in range(i, min(i + 6, end)):
                if not lines[j].strip():
                    break
                para.append(lines[j].strip())
            inv_line_no, inv_raw = i + 1, " ".join(para)
            break
    if inv_raw is None:
        raise AssertionError(
            f"{DOC_REL}: the investment sentence (capex + build + integration + "
            "amortized cost-to-serve) is gone; update this gate deliberately"
        )
    inv_amounts = _rupees(inv_raw)
    if len(inv_amounts) != 5:
        raise AssertionError(
            f"{DOC_REL}:{inv_line_no}: expected four investment components and a "
            f"total on this line, found {len(inv_amounts)} ₹ amounts"
        )
    inputs["investment"] = {
        "capital_expenditure": Claim(inv_amounts[0], inv_line_no, inv_raw),
        "one_time_build": Claim(inv_amounts[1], inv_line_no, inv_raw),
        "integration": Claim(inv_amounts[2], inv_line_no, inv_raw),
        "amortized_cost_to_serve": Claim(inv_amounts[3], inv_line_no, inv_raw),
    }
    inputs["total_investment"] = Claim(inv_amounts[4], inv_line_no, inv_raw)
    inputs["_span"] = (start, end)
    return inputs


def _build_case(inputs):
    from governed_value.domain.attribution import AttributionEvidence
    from governed_value.domain.case import AgentValueCase
    from governed_value.domain.cost import CostToServe
    from governed_value.domain.enums import (
        ConfidenceClass,
        DomainKind,
        OutcomeClass,
        ValueSource,
    )
    from governed_value.domain.expected_loss import ExpectedLoss, ExpectedLossItem
    from governed_value.domain.investment import TotalInvestment
    from governed_value.domain.modifiers import DomainProfile, GeographyProfile
    from governed_value.domain.money import Money
    from governed_value.domain.value import ReportedValue

    cur = "INR"

    def money(claim_or_dec) -> Money:
        raw = getattr(claim_or_dec, "value", claim_or_dec)
        return Money(_to_paise(raw), cur)

    return AgentValueCase(
        tenant_id="acme-in",
        agent_id="support-agent-1",
        domain=DomainProfile(
            kind=DomainKind.SUPPORT,
            natural_unit="ticket",
            dominant_source=ValueSource.LABOR_DISPLACED,
        ),
        geography=GeographyProfile(label="IN", currency=cur),
        outcome=OutcomeClass.DETERMINISTIC_AUTOMATION,
        benefit=ReportedValue(
            labor_displaced=money(inputs["labor_displaced"]),
            throughput_gained=money(inputs["throughput_gained"]),
            loss_avoided=money(inputs["loss_avoided"]),
        ),
        actual_losses=money(inputs["actual_losses"]),
        residual_expected_loss=ExpectedLoss(
            currency=cur,
            items=tuple(
                ExpectedLossItem(
                    it["label"], it["probability"].value, money(it["magnitude"])
                )
                for it in inputs["expected_loss_items"]
            ),
        ),
        cost=CostToServe(
            currency=cur,
            **{f: money(c) for f, c in inputs["cost_components"].items()},
        ),
        investment=TotalInvestment(
            currency=cur, **{f: money(c) for f, c in inputs["investment"].items()}
        ),
        attribution=AttributionEvidence(
            baseline_captured=True, holdout_or_staged=False, concurrent_changes=0
        ),
        reported_confidence=ConfidenceClass.MEDIUM,
    )


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #
class ReadinessDocDriftTest(unittest.TestCase):
    """The document must still say what the packages actually produce."""

    @classmethod
    def setUpClass(cls):
        cls.lines = _lines()

    # -- Stage 1 ---------------------------------------------------------- #
    def _stage_one_span(self):
        start = _section(self.lines, "### Stage 1 — before deployment: readiness")
        end = _section(self.lines, "### Stage 2 — three months later: governed value")
        return start, end

    def test_stage_one_verdict_matches_assess_readiness(self):
        start, end = self._stage_one_span()
        outcome = _run_stage_one()
        trace = outcome.evaluation.trace

        for label, actual in (
            ("status", outcome.status.name),
            ("classification", trace.classification.name),
            ("rule_id", str(trace.rule_id)),
            ("authorizes_deployment", str(outcome.authorizes_deployment)),
            ("orchestrator_version", outcome.trace.orchestrator_version),
            ("formula_version", outcome.trace.evaluator_formula_version),
        ):
            claim = _labelled(self.lines, label, start=start, end=end)
            self.assertEqual(
                claim.value,
                actual,
                f"\nSTALE DOCUMENTATION at {claim.where()}\n"
                f"  document says `{label}` is {claim.value!r}\n"
                f"  assess_readiness now returns {actual!r}\n"
                f"  fix the document, not this assertion.",
            )

    def test_stage_one_reason_and_advisory_codes_match(self):
        start, end = self._stage_one_span()
        trace = _run_stage_one().evaluation.trace

        for label, actual_codes in (
            ("reason_codes", [str(c) for c in trace.reason_codes]),
            ("advisory_codes", [str(c) for c in trace.advisory_codes]),
        ):
            claims = _code_list(self.lines, label, start=start, end=end)
            documented = [c.value for c in claims]
            first, last = claims[0].line, claims[-1].line
            self.assertEqual(
                documented,
                actual_codes,
                f"\nSTALE DOCUMENTATION at {DOC_REL}:{first}-{last} (`{label}`)\n"
                f"  document lists : {documented}\n"
                f"  evaluator emits: {actual_codes}\n"
                f"  missing from the document: "
                f"{[c for c in actual_codes if c not in documented]}\n"
                f"  no longer emitted        : "
                f"{[c for c in documented if c not in actual_codes]}\n"
                f"  fix the document, not this assertion.",
            )

    def test_stage_one_variant_table_rules_match(self):
        """Each row of the verdict/rule table must still be what the code returns."""
        from _orchestration_fixtures import PILOT, PROD
        from ugence_agent_value_readiness.api import GateStatus

        start, end = self._stage_one_span()
        all_pass = [
            ("accuracy", GateStatus.PASS),
            ("security", GateStatus.PASS),
            ("human-escalation", GateStatus.PASS),
            ("regional-language", GateStatus.PASS),
        ]
        mandatory_fail = [
            ("accuracy", GateStatus.FAIL),
            ("security", GateStatus.PASS),
            ("human-escalation", GateStatus.FAIL),
            ("regional-language", GateStatus.FAIL),
        ]
        variants = (
            ("(as above)", {}),
            ("Conditions omitted", {"conditions": []}),
            ("`condition_verifier=None`", {"condition_verifier": None}),
            ("Mandatory `accuracy` fails", {"gates": mandatory_fail}),
            ("All four gates pass", {"gates": all_pass, "conditions": []}),
            ("`PILOT` target", {"target": PILOT}),
        )
        for needle, kwargs in variants:
            with self.subTest(variant=needle):
                kwargs.setdefault("target", PROD)
                trace = _run_stage_one(**kwargs).evaluation.trace
                line_no, raw = _row(self.lines, needle, start=start, end=end)
                cells = [c.strip() for c in raw.strip().strip("|").split("|")]
                self.assertGreaterEqual(len(cells), 3, f"{DOC_REL}:{line_no}: short row")
                stated_verdict = cells[1].strip("`")
                rule_cell = re.search(r"`([^`]+)`", cells[2])
                self.assertIsNotNone(
                    rule_cell,
                    f"{DOC_REL}:{line_no}: rule cell states no `RULE` token",
                )
                stated_rule = rule_cell.group(1).split("—")[0].strip()
                actual_rule_short = str(trace.rule_id).split("_")[1]  # GV3RB_R7_... -> R7
                self.assertEqual(
                    stated_verdict,
                    trace.classification.name,
                    f"\nSTALE DOCUMENTATION at {DOC_REL}:{line_no}\n  {raw.strip()}\n"
                    f"  document says the verdict is {stated_verdict!r}\n"
                    f"  assess_readiness returns {trace.classification.name!r}\n"
                    f"  fix the document, not this assertion.",
                )
                self.assertEqual(
                    stated_rule,
                    actual_rule_short,
                    f"\nSTALE DOCUMENTATION at {DOC_REL}:{line_no}\n  {raw.strip()}\n"
                    f"  document says rule {stated_rule!r}\n"
                    f"  assess_readiness applied {actual_rule_short!r} "
                    f"(full id {trace.rule_id})\n"
                    f"  fix the document, not this assertion.",
                )

    def test_stage_one_states_its_verifier_limit(self):
        """The stub-verifier caveat must survive; without it the example overclaims."""
        start, end = self._stage_one_span()
        body = " ".join(" ".join(self.lines[start:end]).replace(">", " ").split())
        for needle in (
            "StubGateVerifier",
            "StubConditionVerifier",
            "ships no real ones",
            "GV3RB_ADV_GATE_STATUS_STRUCTURALLY_SUPPLIED",
        ):
            self.assertIn(
                needle,
                body,
                f"\n{DOC_REL}: Stage 1 no longer states that its gate/condition "
                f"verifiers are test-only stubs (missing {needle!r}).\n"
                "  Without that caveat the worked example claims gate statuses were "
                "independently verified, which the package does not do.",
            )

    # -- Stage 2 ---------------------------------------------------------- #
    def test_stage_two_money_and_roi_match_score_case(self):
        from governed_value.services.scorer import score_case

        inputs = _documented_stage_two_inputs(self.lines)
        start, end = inputs["_span"]
        result = score_case(_build_case(inputs))

        def lakh(money) -> Decimal:
            return Decimal(money.minor_units) / LAKH_PAISE

        # Documented component totals must equal what the kernel derives from
        # the very components the document lists.
        for key, actual in (
            ("total_benefit", lakh(result.total_benefit)),
            ("cost_to_serve", lakh(result.cost_to_serve)),
            ("residual_expected_loss", lakh(result.residual_expected_loss)),
            ("total_investment", lakh(result.total_investment)),
        ):
            claim = inputs[key]
            self.assertEqual(
                claim.value,
                actual,
                f"\nSTALE DOCUMENTATION at {claim.where()}\n"
                f"  document states a total of ₹{claim.value} lakh\n"
                f"  the components it lists actually sum to ₹{actual} lakh\n"
                f"  fix the document, not this assertion.",
            )

        # Each expected-loss row must state probability x magnitude correctly.
        for item in inputs["expected_loss_items"]:
            expected = (item["probability"].value * item["magnitude"].value)
            self.assertEqual(
                item["expected"].value,
                expected,
                f"\nSTALE DOCUMENTATION at {item['expected'].where()}\n"
                f"  document states an expected loss of ₹{item['expected'].value} lakh\n"
                f"  {item['probability'].value} x ₹{item['magnitude'].value} lakh "
                f"= ₹{expected} lakh\n"
                f"  fix the document, not this assertion.",
            )

        # The headline block.
        for label, actual in (
            ("ReportedNGV", lakh(result.reported_net_governed_value)),
            ("RiskAdjustedNGV", lakh(result.risk_adjusted_net_governed_value)),
        ):
            line_no, raw = _row_line(self.lines, label, start, end)
            stated = _rupees(raw)
            self.assertTrue(stated, f"{DOC_REL}:{line_no}: `{label}` states no ₹ amount")
            self.assertEqual(
                stated[-1],
                actual,
                f"\nSTALE DOCUMENTATION at {DOC_REL}:{line_no}\n  {raw.strip()}\n"
                f"  document states ₹{stated[-1]} lakh\n"
                f"  score_case computes ₹{actual} lakh\n"
                f"  fix the document, not this assertion.",
            )

        for label, actual in (
            ("ReportedROI", result.reported_roi),
            ("RiskAdjustedROI", result.risk_adjusted_roi),
        ):
            line_no, raw = _row_line(self.lines, label, start, end)
            # The line reads `X = a / b = ratio`; the ratio is the LAST value.
            ratios = re.findall(r"=\s*(-?[\d.]+)", raw)
            self.assertTrue(
                ratios, f"{DOC_REL}:{line_no}: `{label}` line states no ratio"
            )
            stated = Decimal(ratios[-1])
            self.assertEqual(
                stated,
                actual,
                f"\nSTALE DOCUMENTATION at {DOC_REL}:{line_no}\n  {raw.strip()}\n"
                f"  document states {label} = {stated}\n"
                f"  score_case computes {actual}\n"
                f"  fix the document, not this assertion.",
            )

    def test_stage_two_classification_axes_match(self):
        from governed_value.services.scorer import score_case

        inputs = _documented_stage_two_inputs(self.lines)
        start, end = inputs["_span"]
        result = score_case(_build_case(inputs))

        for label, actual in (
            ("stage", result.stage.name),
            ("evidence", result.evidence_status.name),
            ("authority", result.authority_status.name),
            ("scorability", result.scorability.name),
            ("method", result.measurement_method.name),
            ("confidence", result.reported_confidence.name),
        ):
            line_no, raw = _row_line(self.lines, label, start, end)
            m = re.search(r"=\s*([A-Z_]+)", raw)
            self.assertIsNotNone(
                m, f"{DOC_REL}:{line_no}: `{label}` line states no value"
            )
            self.assertEqual(
                m.group(1),
                actual,
                f"\nSTALE DOCUMENTATION at {DOC_REL}:{line_no}\n  {raw.strip()}\n"
                f"  document states {label} = {m.group(1)}\n"
                f"  score_case returns {actual}\n"
                f"  fix the document, not this assertion.",
            )

    def test_missing_baseline_still_suppresses_the_headline(self):
        """The document's central warning must remain true of the code."""
        import dataclasses

        from governed_value.domain.attribution import AttributionEvidence
        from governed_value.domain.enums import Scorability
        from governed_value.services.scorer import score_case

        inputs = _documented_stage_two_inputs(self.lines)
        case = dataclasses.replace(
            _build_case(inputs),
            attribution=AttributionEvidence(baseline_captured=False),
        )
        result = score_case(case)

        heading = _section(self.lines, "### The trap: no baseline, no headline")
        self.assertIs(
            result.scorability,
            Scorability.NOT_SCORABLE,
            f"\nSTALE DOCUMENTATION at {DOC_REL}:{heading + 1}\n"
            f"  the section claims a missing baseline yields NOT_SCORABLE;\n"
            f"  score_case now returns {result.scorability.name}.",
        )
        for label, value in (
            ("ReportedROI", result.reported_roi),
            ("RiskAdjustedROI", result.risk_adjusted_roi),
        ):
            self.assertIsNone(
                value,
                f"\nSTALE DOCUMENTATION at {DOC_REL}:{heading + 1}\n"
                f"  the section claims {label} is suppressed to None without a "
                f"baseline;\n  score_case now returns {value!r}.",
            )

    def test_document_still_states_the_two_modules_are_unconnected(self):
        """The separation claim is the document's thesis; prove it structurally."""
        readiness_src = (
            REPO_ROOT / "packages" / "capabilities" / "agent-value-readiness" / "src"
        )
        value_src = REPO_ROOT / "packages" / "governed-value" / "src"

        for label, root, foreign in (
            ("agent-value-readiness", readiness_src, "governed_value"),
            ("governed-value", value_src, "ugence_agent_value_readiness"),
        ):
            for path in root.rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                for i, raw in enumerate(text.splitlines(), start=1):
                    stripped = raw.strip()
                    if not (
                        stripped.startswith("import ") or stripped.startswith("from ")
                    ):
                        continue
                    self.assertNotIn(
                        foreign,
                        stripped,
                        f"\n{DOC_REL} claims no code path connects the two modules, "
                        f"but\n  {path.relative_to(REPO_ROOT)}:{i}\n  {stripped}\n"
                        f"  imports {foreign} into {label}. Either the claim is now "
                        f"false and the document must change, or the import is a "
                        f"boundary violation.",
                    )


def _row_line(lines, label, start, end):
    """A ``label ... = value`` line inside a fenced result block."""
    pattern = re.compile(rf"^\s*{re.escape(label)}\b.*=")
    for i, raw in enumerate(lines[start:end], start=start):
        if pattern.match(raw):
            return i + 1, raw
    raise AssertionError(
        f"{DOC_REL}: no `{label} = ...` line in the Stage 2 result block; "
        "the worked example's shape changed — update this gate deliberately"
    )


if __name__ == "__main__":
    unittest.main()
