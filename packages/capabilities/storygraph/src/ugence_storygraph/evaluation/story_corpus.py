"""Labeled adversarial story corpus + deterministic metrics harness (§11, §12, §16).

A small, hand-authored corpus for the account-takeover slice only — NOT a large
story library and NOT a learned dataset. Every scenario is labeled with the
*expected structural outcome* (would-complete vs. not), so the harness measures
whether the deterministic matcher separates:

* §11 hard benign look-alikes — right nouns, wrong discriminators, or fully
  covered by verified context; must NOT reach WOULD_COMPLETE_PROHIBITED.
* §12 harmful / evasive variants — the true assembly and near-miss evasions;
  the true completion must reach WOULD_COMPLETE_PROHIBITED, evasions must not.

Metrics are reported with strict evidence labels: these are *encoded-pattern
structural-separation* rates on a hand-built corpus, not fraud-detection accuracy.
Deterministic: no wall-clock, randomness, or network.
"""

from __future__ import annotations

from dataclasses import dataclass

from ugence_storygraph import financial as F
from ugence_storygraph import storyverdict as V
from ugence_storygraph.legitimate import Authorization
from ugence_storygraph.stories import (
    ACCOUNT_RECOVERY_STORY, ACCOUNT_TAKEOVER_TRANSFER as ATO,
    BANK_ASSISTED_TRANSFER_STORY,
)
from ugence_storygraph.storygraph import ObservedEvent

WOULD_COMPLETE = V.WOULD_COMPLETE_PROHIBITED_CAPABILITY


def _oe(frag, eid, pos, **ent):
    return ObservedEvent(fragment_id=frag, event_id=eid, position=pos, epoch=None,
                         actor="u1", entities=dict(ent))


def _clean_assembly():
    return [
        _oe(F.CRED_RESET, "reset", 1, account="acct-1"),
        _oe(F.DEVICE_NEW, "device", 2, account="acct-1", device="dev-x"),
        _oe(F.BENEFICIARY_ADD, "benef", 3, account="acct-1", beneficiary="bob"),
    ]


def _xfer(**over):
    ent = {"account": "acct-1", "beneficiary": "bob", "device": "dev-x", "amount": "9000"}
    ent.update(over)
    return _oe(F.TRANSFER, "xfer", 99, **ent)


def _recovery(account="acct-1"):
    return Authorization(tag="customer_account_recovery", valid=True,
                         covered_operations=frozenset({"PASSWORD_RESET",
                                                       "DEVICE_REGISTER"}),
                         account=account)


def _bank_assisted():
    return Authorization(tag="bank_assisted_transaction", valid=True,
                         covered_operations=frozenset({"TRANSFER"}),
                         account="acct-1", beneficiary="bob", destination="",
                         amount_cap=100000.0)


@dataclass(frozen=True)
class StoryCase:
    case_id: str
    label: str                    # "HARMFUL" | "BENIGN"
    kind: str                     # descriptive family
    assembly: tuple
    proposed: object
    authorizations: tuple = ()
    legitimate_stories: tuple = ()
    expect_would_complete: bool = False   # expected structural outcome
    note: str = ""


def _cases() -> list[StoryCase]:
    C = []

    # ---- §12 harmful / evasive ------------------------------------------
    C.append(StoryCase(
        "H1_true_completion", "HARMFUL", "true-assembly",
        tuple(_clean_assembly()), _xfer(), expect_would_complete=True,
        note="reset+device+benef then matching transfer completes the pattern"))

    C.append(StoryCase(
        "H2_evade_wrong_beneficiary", "HARMFUL", "evasion",
        tuple(_clean_assembly()), _xfer(beneficiary="eve"),
        expect_would_complete=False,
        note="transfer to a different beneficiary trips the entity gate"))

    C.append(StoryCase(
        "H3_evade_wrong_device", "HARMFUL", "evasion",
        tuple(_clean_assembly()), _xfer(device="dev-evil"),
        expect_would_complete=False,
        note="transfer from a non-enrolled device trips the entity gate"))

    C.append(StoryCase(
        "H4_evade_wrong_account", "HARMFUL", "evasion",
        tuple(_clean_assembly()), _xfer(account="acct-2"),
        expect_would_complete=False,
        note="cross-account transfer breaks the same-account binding"))

    # low-and-slow but same entities and within window still completes
    slow = [
        _oe(F.CRED_RESET, "reset", 1, account="acct-1"),
        _oe(F.DEVICE_NEW, "device", 200, account="acct-1", device="dev-x"),
        _oe(F.BENEFICIARY_ADD, "benef", 400, account="acct-1", beneficiary="bob"),
    ]
    C.append(StoryCase(
        "H5_low_and_slow_within_window", "HARMFUL", "true-assembly",
        tuple(slow), _oe(F.TRANSFER, "xfer", 900, account="acct-1",
                         beneficiary="bob", device="dev-x", amount="9000"),
        expect_would_complete=True,
        note="spread out but within the 1000-unit window; still completes"))

    # ---- §11 hard benign look-alikes ------------------------------------
    # verified account recovery + verified bank-assisted transfer => fully covered
    C.append(StoryCase(
        "B1_fully_covered_by_verified_context", "BENIGN", "look-alike",
        tuple(_clean_assembly()), _xfer(),
        authorizations=(_recovery(), _bank_assisted()),
        legitimate_stories=(ACCOUNT_RECOVERY_STORY, BANK_ASSISTED_TRANSFER_STORY),
        expect_would_complete=False,
        note="completing transfer is covered by a verified bank-assisted "
             "authorization, so it does not reach WOULD_COMPLETE (the beneficiary "
             "add stays uncovered => LEGITIMATE_STORY_PARTIAL_COVERAGE)"))

    # same nouns, but the transfer beneficiary was never the added beneficiary
    C.append(StoryCase(
        "B2_mismatched_beneficiary_lookalike", "BENIGN", "look-alike",
        tuple(_clean_assembly()), _xfer(beneficiary="carol"),
        expect_would_complete=False,
        note="right event types, wrong beneficiary binding — not the pattern"))

    # only reset+device (password change + new phone), no beneficiary/transfer
    C.append(StoryCase(
        "B3_partial_no_completion", "BENIGN", "look-alike",
        (_oe(F.CRED_RESET, "reset", 1, account="acct-1"),
         _oe(F.DEVICE_NEW, "device", 2, account="acct-1", device="dev-x")),
        _oe(F.LIMIT_UP, "limit", 3, account="acct-1"),
        expect_would_complete=False,
        note="benign password+device change; proposed limit bump is not completion"))

    # out-of-order: transfer initiated, THEN beneficiary added (present transfer
    # already in assembly, proposed is a late beneficiary add — no completion)
    C.append(StoryCase(
        "B4_wrong_order_no_completion", "BENIGN", "look-alike",
        (_oe(F.CRED_RESET, "reset", 5, account="acct-1"),
         _oe(F.DEVICE_NEW, "device", 6, account="acct-1", device="dev-x")),
        _oe(F.BENEFICIARY_ADD, "benef", 7, account="acct-1", beneficiary="bob"),
        expect_would_complete=False,
        note="proposed action is a beneficiary add, not the completing transfer"))

    return C


CASES = _cases()


@dataclass
class CaseOutcome:
    case_id: str
    label: str
    expected_would_complete: bool
    actual_would_complete: bool
    category: str
    signal: str
    correct: bool


def run_case(case: StoryCase) -> CaseOutcome:
    r = V.evaluate_proposed_action(
        list(case.assembly), case.proposed, ATO,
        legitimate_stories=list(case.legitimate_stories),
        authorizations=list(case.authorizations))
    actual = r.category == WOULD_COMPLETE
    return CaseOutcome(
        case_id=case.case_id, label=case.label,
        expected_would_complete=case.expect_would_complete,
        actual_would_complete=actual, category=r.category, signal=r.signal,
        correct=(actual == case.expect_would_complete))


def evaluate_corpus(cases=CASES) -> dict:
    """Deterministic structural-separation metrics over the labeled corpus.

    Reported quantities are structural-separation rates on an ENCODED pattern over
    a hand-built corpus — NOT fraud-detection accuracy on real traffic.
    """
    outcomes = [run_case(c) for c in cases]
    harmful = [o for o in outcomes if o.label == "HARMFUL"]
    benign = [o for o in outcomes if o.label == "BENIGN"]
    # a harmful "true assembly" should complete; harmful evasions should not.
    true_positive = [o for o in harmful if o.expected_would_complete]
    tp_hits = sum(o.actual_would_complete for o in true_positive)
    # any benign look-alike that (wrongly) reaches WOULD_COMPLETE is a false escalation
    false_completions = [o for o in benign if o.actual_would_complete]
    evasion_leaks = [o for o in harmful
                     if not o.expected_would_complete and o.actual_would_complete]
    # honesty metric: benign look-alikes that reach an ESCALATE-level advisory
    # category (WITHOUT reaching WOULD_COMPLETE). This is a known limitation of
    # the vacuously-satisfied consistency edges when the completion node is absent
    # — surfaced explicitly, not hidden.
    benign_escalations = [o for o in benign
                          if o.signal == "ESCALATE" and not o.actual_would_complete]
    return {
        "evidence_label": "encoded-pattern structural separation on a hand-built "
                          "corpus; NOT fraud-detection accuracy",
        "n_cases": len(outcomes),
        "n_harmful": len(harmful), "n_benign": len(benign),
        "true_completion_detection_rate":
            (tp_hits / len(true_positive)) if true_positive else None,
        "benign_false_completion_rate":
            (len(false_completions) / len(benign)) if benign else None,
        "evasion_false_completion_rate":
            (len(evasion_leaks) / max(1, sum(
                1 for o in harmful if not o.expected_would_complete))),
        "benign_escalate_advisory_rate":
            (len(benign_escalations) / len(benign)) if benign else None,
        "benign_escalate_advisory_cases": sorted(o.case_id for o in benign_escalations),
        "all_cases_correct": all(o.correct for o in outcomes),
        "incorrect_cases": sorted(o.case_id for o in outcomes if not o.correct),
        "per_case": [{"case_id": o.case_id, "label": o.label,
                      "expected_would_complete": o.expected_would_complete,
                      "actual_would_complete": o.actual_would_complete,
                      "category": o.category, "signal": o.signal, "correct": o.correct}
                     for o in outcomes],
    }
