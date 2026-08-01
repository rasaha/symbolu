"""Expanded deterministic adversarial story corpus + splits (§12, §13).

A substantially larger, hand-authored corpus for the *single* account-takeover
slice — still no new domains, no learned scoring, no probabilistic inference. Every
case is deterministic (variation comes from an integer index, never randomness) and
carries the expected structural outcome so the harness can measure separation under
the corrected (matcher/2.0.0) partial-match semantics.

Splits (dev / calibration / final) are assigned by a deterministic digest of the
case id so the *final* split can be run exactly once under a frozen configuration.

Metrics carry strict evidence labels: encoded-pattern structural separation on a
hand-built corpus — NOT fraud-detection accuracy on real traffic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from composite_threat_detector import financial as F
from composite_threat_detector import storyverdict as V
from composite_threat_detector.storygraph import MATCHER_SEMANTICS_VERSION
from composite_threat_detector.canonical import digest
from composite_threat_detector.legitimate import Authorization
from composite_threat_detector.stories import (
    ACCOUNT_RECOVERY_STORY, ACCOUNT_TAKEOVER_TRANSFER as ATO,
    BANK_ASSISTED_TRANSFER_STORY,
)
from composite_threat_detector.storygraph import ObservedEvent

WC = V.WOULD_COMPLETE_PROHIBITED_CAPABILITY
SPLITS = ("dev", "calibration", "final")


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------
def _oe(frag, eid, pos, *, actor="u1", **ent):
    return ObservedEvent(fragment_id=frag, event_id=eid, position=pos, epoch=None,
                         actor=actor, entities=dict(ent))


def _ent(v):
    """Deterministic entity family for variant v."""
    return {"account": f"acct-{v}", "device": f"dev-{v}",
            "beneficiary": f"bob-{v}", "actor": f"u-{v}", "amount": str(9000 + v * 250)}


def _recovery(v, *, valid=True, account=None):
    e = _ent(v)
    return Authorization(tag="customer_account_recovery", valid=valid,
                         covered_operations=frozenset({"PASSWORD_RESET",
                                                       "DEVICE_REGISTER"}),
                         account=account or e["account"])


def _bank_assisted(v, *, expires_at=None, amount_cap=1_000_000.0):
    e = _ent(v)
    return Authorization(tag="bank_assisted_transaction", valid=True,
                         covered_operations=frozenset({"TRANSFER", "BENEFICIARY_ADD"}),
                         account=e["account"], beneficiary=e["beneficiary"],
                         destination="", amount_cap=amount_cap, expires_at=expires_at)


@dataclass(frozen=True)
class Case:
    case_id: str
    family: str
    label: str                       # HARMFUL | BENIGN
    assembly: tuple
    proposed: object
    authorizations: tuple = ()
    legitimate_stories: tuple = ()
    expect_would_complete: bool = False
    now: float | None = None
    note: str = ""


def _clean_assembly(v, *, base=1, gap=1):
    e = _ent(v)
    return [
        _oe(F.CRED_RESET, f"reset-{v}", base, actor=e["actor"], account=e["account"]),
        _oe(F.DEVICE_NEW, f"device-{v}", base + gap, actor=e["actor"],
            account=e["account"], device=e["device"]),
        _oe(F.BENEFICIARY_ADD, f"benef-{v}", base + 2 * gap, actor=e["actor"],
            account=e["account"], beneficiary=e["beneficiary"]),
    ]


def _transfer(v, *, pos=99, **over):
    e = _ent(v)
    ent = {"account": e["account"], "beneficiary": e["beneficiary"],
           "device": e["device"], "amount": e["amount"]}
    ent.update(over)
    return _oe(F.TRANSFER, f"xfer-{v}", pos, actor=e["actor"], **ent)


# ---------------------------------------------------------------------------
# BENIGN families (§12) — none may reach WOULD_COMPLETE
# ---------------------------------------------------------------------------
def _benign(v):
    e = _ent(v)
    out = []

    out.append(Case(f"B_pwreset_{v}", "ordinary_password_reset", "BENIGN",
                    (_oe(F.CRED_RESET, f"reset-{v}", 1, account=e["account"]),),
                    _oe(F.DEVICE_NEW, f"device-{v}", 2, account=e["account"],
                        device=e["device"]),
                    note="password reset then a new device; no beneficiary/transfer"))

    out.append(Case(f"B_lostphone_{v}", "lost_phone_replacement", "BENIGN",
                    tuple(_clean_assembly(v)[:2]),
                    _oe(F.LIMIT_UP, f"limit-{v}", 5, account=e["account"]),
                    note="reset+device, proposed action is a limit bump"))

    out.append(Case(f"B_reinstall_{v}", "mobile_app_reinstall", "BENIGN",
                    (_oe(F.DEVICE_NEW, f"device-{v}", 1, account=e["account"],
                         device=e["device"]),),
                    _oe(F.DEVICE_NEW, f"device2-{v}", 2, account=e["account"],
                        device=e["device"]),
                    note="app reinstall re-enrolls the same device"))

    out.append(Case(f"B_dupdevice_{v}", "duplicate_device_enrollment", "BENIGN",
                    (_oe(F.DEVICE_NEW, f"device-{v}", 1, account=e["account"],
                         device=e["device"]),
                     _oe(F.DEVICE_NEW, f"device2-{v}", 2, account=e["account"],
                         device=e["device"])),
                    _oe(F.LIMIT_UP, f"limit-{v}", 3, account=e["account"]),
                    note="duplicate device enrollment"))

    # recovery workflow: reset+device covered by a verified recovery; the proposed
    # action re-registers a device the recovery also covers.
    out.append(Case(f"B_recovery_{v}", "account_recovery_workflow", "BENIGN",
                    tuple(_clean_assembly(v)[:2]),
                    _oe(F.DEVICE_NEW, f"device2-{v}", 5, account=e["account"],
                        device=e["device"]),
                    authorizations=(_recovery(v),),
                    legitimate_stories=(ACCOUNT_RECOVERY_STORY,),
                    note="verified recovery covers reset+device (+re-registration)"))

    # beneficiary setup + transfer, both covered by a verified bank authorization;
    # no unexplained credential reset / new device.
    out.append(Case(f"B_bankbenef_{v}", "bank_assisted_beneficiary_setup", "BENIGN",
                    (_oe(F.BENEFICIARY_ADD, f"benef-{v}", 1, account=e["account"],
                         beneficiary=e["beneficiary"]),),
                    _transfer(v),
                    authorizations=(_bank_assisted(v),),
                    legitimate_stories=(BANK_ASSISTED_TRANSFER_STORY,),
                    note="verified bank transaction covers beneficiary + transfer"))

    out.append(Case(f"B_family_{v}", "family_beneficiary_addition", "BENIGN",
                    (_oe(F.BENEFICIARY_ADD, f"benef-{v}", 1, account=e["account"],
                         beneficiary=e["beneficiary"]),),
                    _transfer(v),
                    authorizations=(_bank_assisted(v),),
                    legitimate_stories=(BANK_ASSISTED_TRANSFER_STORY,),
                    note="family beneficiary + transfer, verified"))

    # full setup that is fully explained: recovery covers reset+device, bank
    # authorization covers beneficiary+transfer.
    out.append(Case(f"B_property_{v}", "property_purchase_transfer", "BENIGN",
                    tuple(_clean_assembly(v)),
                    _transfer(v),
                    authorizations=(_recovery(v), _bank_assisted(v)),
                    legitimate_stories=(ACCOUNT_RECOVERY_STORY,
                                        BANK_ASSISTED_TRANSFER_STORY),
                    note="reset/device covered by recovery; beneficiary/transfer by bank"))

    out.append(Case(f"B_medical_{v}", "medical_emergency_transfer", "BENIGN",
                    tuple(_clean_assembly(v)),
                    _transfer(v),
                    authorizations=(_recovery(v), _bank_assisted(v)),
                    legitimate_stories=(ACCOUNT_RECOVERY_STORY,
                                        BANK_ASSISTED_TRANSFER_STORY),
                    note="urgent but fully explained transfer"))

    out.append(Case(f"B_profilemig_{v}", "customer_profile_migration", "BENIGN",
                    tuple(_clean_assembly(v)),
                    _oe(F.LIMIT_UP, f"limit-{v}", 9, account=e["account"]),
                    note="profile migration; no verified context, no completion => OBSERVE"))

    out.append(Case(f"B_benefrecreate_{v}", "beneficiary_recreation_migration",
                    "BENIGN",
                    (_oe(F.BENEFICIARY_ADD, f"benef-{v}", 1, account=e["account"],
                         beneficiary=e["beneficiary"]),),
                    _transfer(v),
                    authorizations=(_bank_assisted(v),),
                    legitimate_stories=(BANK_ASSISTED_TRANSFER_STORY,),
                    note="beneficiary recreated after migration; transfer covered"))

    out.append(Case(f"B_fraudreset_{v}", "fraud_response_credential_reset", "BENIGN",
                    (_oe(F.CRED_RESET, f"reset-{v}", 1, account=e["account"]),),
                    _oe(F.DEVICE_NEW, f"device-{v}", 2, account=e["account"],
                        device=e["device"]),
                    authorizations=(_recovery(v),),
                    legitimate_stories=(ACCOUNT_RECOVERY_STORY,),
                    note="bank-initiated reset in response to suspected fraud"))

    out.append(Case(f"B_abandoned_{v}", "abandoned_recovery_workflow", "BENIGN",
                    tuple(_clean_assembly(v)[:2]),
                    _oe(F.LIMIT_UP, f"limit-{v}", 4, account=e["account"]),
                    note="recovery started then abandoned; no verified context, no xfer"))

    # delayed ingestion: correct coordinates, fully covered.
    out.append(Case(f"B_delayed_{v}", "delayed_event_ingestion", "BENIGN",
                    tuple(_clean_assembly(v, gap=3)),
                    _transfer(v),
                    authorizations=(_recovery(v), _bank_assisted(v)),
                    legitimate_stories=(ACCOUNT_RECOVERY_STORY,
                                        BANK_ASSISTED_TRANSFER_STORY),
                    note="delayed ingestion; fully covered"))

    # interleaved unrelated administration on a different account (noise)
    noise = [_oe(F.CRED_RESET, f"noise-reset-{v}", 1, account=f"other-{v}"),
             _oe(F.DEVICE_NEW, f"noise-dev-{v}", 2, account=f"other-{v}",
                 device=f"otherdev-{v}")]
    out.append(Case(f"B_interleaved_{v}", "interleaved_unrelated_admin", "BENIGN",
                    tuple(_clean_assembly(v) + noise),
                    _transfer(v),
                    authorizations=(_recovery(v), _bank_assisted(v)),
                    legitimate_stories=(ACCOUNT_RECOVERY_STORY,
                                        BANK_ASSISTED_TRANSFER_STORY),
                    note="unrelated account admin interleaved; assembly fully covered"))

    out.append(Case(f"B_accessibility_{v}", "employee_assisted_accessibility",
                    "BENIGN",
                    tuple(_clean_assembly(v)[:2]),
                    _oe(F.DEVICE_NEW, f"device2-{v}", 5, account=e["account"],
                        device=e["device"]),
                    authorizations=(_recovery(v),),
                    legitimate_stories=(ACCOUNT_RECOVERY_STORY,),
                    note="employee-assisted accessibility recovery, covered"))

    # customer changes instructions midway: two beneficiaries, transfer to the
    # second, fully covered (recovery for setup + bank scoped to carol).
    ba2 = Authorization(tag="bank_assisted_transaction", valid=True,
                        covered_operations=frozenset({"TRANSFER", "BENEFICIARY_ADD"}),
                        account=e["account"], beneficiary=f"carol-{v}",
                        amount_cap=1_000_000.0)
    out.append(Case(f"B_midway_{v}", "customer_changes_instructions_midway", "BENIGN",
                    tuple(_clean_assembly(v) + [
                        _oe(F.BENEFICIARY_ADD, f"benef2-{v}", 4, account=e["account"],
                            beneficiary=f"carol-{v}")]),
                    _transfer(v, beneficiary=f"carol-{v}"),
                    authorizations=(_recovery(v), ba2),
                    legitimate_stories=(ACCOUNT_RECOVERY_STORY,
                                        BANK_ASSISTED_TRANSFER_STORY),
                    note="instructions changed to carol; transfer to carol covered"))

    out.append(Case(f"B_multibenef_{v}", "multiple_legitimate_beneficiaries",
                    "BENIGN",
                    tuple(_clean_assembly(v) + [
                        _oe(F.BENEFICIARY_ADD, f"benef2-{v}", 4, account=e["account"],
                            beneficiary=f"carol-{v}")]),
                    _transfer(v),
                    authorizations=(_recovery(v), _bank_assisted(v)),
                    legitimate_stories=(ACCOUNT_RECOVERY_STORY,
                                        BANK_ASSISTED_TRANSFER_STORY),
                    note="several legitimate beneficiaries; transfer to bob covered"))

    # transfer proposed from a pre-existing device (no DEVICE_NEW enrollment node);
    # the missing device node alone prevents completion, with no verified context.
    out.append(Case(f"B_preexistdev_{v}", "transfer_from_preexisting_device",
                    "BENIGN",
                    (_oe(F.BENEFICIARY_ADD, f"benef-{v}", 2, account=e["account"],
                         beneficiary=e["beneficiary"]),),
                    _transfer(v),
                    note="no new-device enrollment => device node absent, no completion"))

    out.append(Case(f"B_limitnoxfer_{v}", "limit_increase_no_transfer", "BENIGN",
                    tuple(_clean_assembly(v) + [
                        _oe(F.LIMIT_UP, f"limit-{v}", 4, account=e["account"])]),
                    _oe(F.LIMIT_UP, f"limit2-{v}", 5, account=e["account"]),
                    note="limit increase with no subsequent transfer; no verified context"))

    return out


# ---------------------------------------------------------------------------
# HARMFUL / evasive families (§12)
# ---------------------------------------------------------------------------
def _harmful(v):
    e = _ent(v)
    out = []

    out.append(Case(f"H_exact_{v}", "exact_completion", "HARMFUL",
                    tuple(_clean_assembly(v)), _transfer(v),
                    expect_would_complete=True, note="exact account-takeover"))

    # cross-session: same entities, different actor ids per step, spread positions
    cross = [
        _oe(F.CRED_RESET, f"reset-{v}", 1, actor=f"s1-{v}", account=e["account"]),
        _oe(F.DEVICE_NEW, f"device-{v}", 2, actor=f"s2-{v}", account=e["account"],
            device=e["device"]),
        _oe(F.BENEFICIARY_ADD, f"benef-{v}", 3, actor=f"s3-{v}", account=e["account"],
            beneficiary=e["beneficiary"])]
    out.append(Case(f"H_crosssession_{v}", "cross_session_completion", "HARMFUL",
                    tuple(cross), _transfer(v, pos=10),
                    expect_would_complete=True, note="completion across sessions"))

    out.append(Case(f"H_multiactor_{v}", "multi_actor_completion", "HARMFUL",
                    tuple(cross), _transfer(v, pos=10),
                    expect_would_complete=True, note="different actors per step"))

    # long-and-slow but within the 1000-unit window
    slow = [
        _oe(F.CRED_RESET, f"reset-{v}", 1, account=e["account"]),
        _oe(F.DEVICE_NEW, f"device-{v}", 300, account=e["account"], device=e["device"]),
        _oe(F.BENEFICIARY_ADD, f"benef-{v}", 600, account=e["account"],
            beneficiary=e["beneficiary"])]
    out.append(Case(f"H_slow_{v}", "long_and_slow_completion", "HARMFUL",
                    tuple(slow), _transfer(v, pos=900),
                    expect_would_complete=True, note="spread but within window"))

    out.append(Case(f"H_split_{v}", "split_transfer_completion", "HARMFUL",
                    tuple(_clean_assembly(v)),
                    _transfer(v, amount=str(int(e["amount"]) // 2)),
                    expect_would_complete=True, note="partial-amount transfer completes"))

    out.append(Case(f"H_multibenef_{v}", "multiple_proposed_beneficiaries", "HARMFUL",
                    tuple(_clean_assembly(v) + [
                        _oe(F.BENEFICIARY_ADD, f"benef2-{v}", 4, account=e["account"],
                            beneficiary=f"eve-{v}")]),
                    _transfer(v),
                    expect_would_complete=True,
                    note="matcher binds the beneficiary node matching the transfer"))

    # device rotation: two enrollments, transfer from the second
    rot = _clean_assembly(v) + [
        _oe(F.DEVICE_NEW, f"device2-{v}", 4, account=e["account"], device=f"dev2-{v}")]
    out.append(Case(f"H_devrotate_{v}", "device_rotation_before_transfer", "HARMFUL",
                    tuple(rot), _transfer(v, device=f"dev2-{v}"),
                    expect_would_complete=True, note="transfer from the rotated device"))

    out.append(Case(f"H_decoyapproval_{v}", "wrong_approval_decoy", "HARMFUL",
                    tuple(_clean_assembly(v)), _transfer(v),
                    authorizations=(_recovery(v),),
                    legitimate_stories=(ACCOUNT_RECOVERY_STORY,),
                    expect_would_complete=True,
                    note="recovery approval covers reset/device, NOT the transfer"))

    out.append(Case(f"H_expiredapproval_{v}", "approval_after_compromise", "HARMFUL",
                    tuple(_clean_assembly(v)), _transfer(v),
                    authorizations=(_bank_assisted(v, expires_at=50.0),),
                    legitimate_stories=(BANK_ASSISTED_TRANSFER_STORY,),
                    now=100.0, expect_would_complete=True,
                    note="bank authorization expired before the transfer"))

    # duplicate / retry storm: duplicated reset+device events
    storm = _clean_assembly(v) + [
        _oe(F.CRED_RESET, f"reset-dup-{v}", 1, account=e["account"]),
        _oe(F.DEVICE_NEW, f"device-dup-{v}", 2, account=e["account"],
            device=e["device"])]
    out.append(Case(f"H_storm_{v}", "duplicate_retry_storm", "HARMFUL",
                    tuple(storm), _transfer(v),
                    expect_would_complete=True, note="dedup/multiplicity, still completes"))

    # out-of-order ingestion but correct coordinates => still completes
    jumbled = [
        _oe(F.BENEFICIARY_ADD, f"benef-{v}", 3, account=e["account"],
            beneficiary=e["beneficiary"]),
        _oe(F.CRED_RESET, f"reset-{v}", 1, account=e["account"]),
        _oe(F.DEVICE_NEW, f"device-{v}", 2, account=e["account"], device=e["device"])]
    out.append(Case(f"H_jumbled_{v}", "out_of_order_ingestion", "HARMFUL",
                    tuple(jumbled), _transfer(v, pos=10),
                    expect_would_complete=True,
                    note="ingested out of order; coordinates preserve true order"))

    # --- evasions that must NOT complete ---------------------------------
    out.append(Case(f"E_wrongbenef_{v}", "evasion_wrong_beneficiary", "HARMFUL",
                    tuple(_clean_assembly(v)), _transfer(v, beneficiary=f"eve-{v}"),
                    expect_would_complete=False, note="transfer to a different party"))

    out.append(Case(f"E_wrongdevice_{v}", "evasion_wrong_device", "HARMFUL",
                    tuple(_clean_assembly(v)), _transfer(v, device=f"evil-{v}"),
                    expect_would_complete=False, note="transfer from a non-enrolled device"))

    out.append(Case(f"E_outwindow_{v}", "evasion_outside_window", "HARMFUL",
                    (_oe(F.CRED_RESET, f"reset-{v}", 1, account=e["account"]),
                     _oe(F.DEVICE_NEW, f"device-{v}", 2000, account=e["account"],
                         device=e["device"]),
                     _oe(F.BENEFICIARY_ADD, f"benef-{v}", 2001, account=e["account"],
                         beneficiary=e["beneficiary"])),
                    _transfer(v, pos=2002),
                    expect_would_complete=False, note="reset far outside the window"))

    # conflicting identity evidence: two devices, transfer device matches neither
    out.append(Case(f"E_conflictid_{v}", "conflicting_identity_evidence", "HARMFUL",
                    tuple(_clean_assembly(v) + [
                        _oe(F.DEVICE_NEW, f"device2-{v}", 4, account=e["account"],
                            device=f"dev2-{v}")]),
                    _transfer(v, device=f"ghost-{v}"),
                    expect_would_complete=False,
                    note="transfer device matches no enrolled device"))

    # unknown / unencoded sequence: events that do not map to the ATO fragments
    out.append(Case(f"U_unknown_{v}", "unknown_unencoded_sequence", "HARMFUL",
                    (_oe("UNMAPPED_OP_A", f"u1-{v}", 1, account=e["account"]),
                     _oe("UNMAPPED_OP_B", f"u2-{v}", 2, account=e["account"])),
                    _oe("UNMAPPED_OP_C", f"u3-{v}", 3, account=e["account"]),
                    expect_would_complete=False,
                    note="genuinely novel sequence matches nothing; stays undetected"))

    return out


def build_corpus(variants=(0, 1, 2)) -> list[Case]:
    cases = []
    for v in variants:
        cases.extend(_benign(v))
        cases.extend(_harmful(v))
    return cases


CORPUS = build_corpus()


def split_of(case_id: str) -> str:
    """Deterministic split assignment from a digest of the case id (§13)."""
    h = digest(case_id, domain="CTD-SPLIT-ASSIGN").split(":", 1)[1]
    return SPLITS[int(h[:8], 16) % len(SPLITS)]


def cases_for_split(split: str, cases=CORPUS) -> list[Case]:
    return [c for c in cases if split_of(c.case_id) == split]


def corpus_hashes(cases=CORPUS) -> dict:
    per_split = {}
    for sp in SPLITS:
        ids = sorted(c.case_id for c in cases if split_of(c.case_id) == sp)
        per_split[sp] = digest(ids, domain="CTD-STORYCORPUS2")
    per_split["corpus"] = digest(sorted(c.case_id for c in cases),
                                 domain="CTD-STORYCORPUS2")
    return per_split


# ---------------------------------------------------------------------------
# Deterministic metrics harness (§14) + pre-registered acceptance gates (§15)
# ---------------------------------------------------------------------------
# Pre-registered BEFORE the frozen final run (calibrated on the calibration split).
# These are experimental development thresholds for ONE synthetic account-takeover
# StoryGraph — NOT universal fraud-detection standards.
PREREGISTERED_GATES = {
    "preregistered": True,
    "min_encoded_completion_detection_rate": 1.00,   # every true assembly completes
    "max_benign_false_completion_rate": 0.00,        # no benign look-alike completes
    "max_evasion_false_completion_rate": 0.00,       # no evasion completes
    "max_benign_escalate_rate": 0.10,                # the corrected-defect gate
    "max_benign_threat_consistent_rate": 0.00,       # the ORIGINAL defect category
    "min_witness_minimality_pass_rate": 1.00,             # canonical completions
    "min_duplicate_witness_nonminimal_correct_rate": 1.00,  # honest non-minimal report
    "min_deterministic_replay_pass_rate": 1.00,
    "min_non_mutation_pass_rate": 1.00,
}


def _has_equiv_dup(c: Case) -> bool:
    """True if the assembly contains two equivalent events (same fragment + same
    account/device/beneficiary) — such a case legitimately yields a NON-minimal
    witness (a duplicate can substitute for a removed witness element)."""
    seen = set()
    for e in c.assembly:
        key = (e.fragment_id, e.entities.get("account"), e.entities.get("device"),
               e.entities.get("beneficiary"))
        if key in seen:
            return True
        seen.add(key)
    return False


def _run(c: Case):
    return V.evaluate_proposed_action(
        list(c.assembly), c.proposed, ATO,
        legitimate_stories=list(c.legitimate_stories),
        authorizations=list(c.authorizations), now=c.now)


def _rate(num, den):
    return (num / den) if den else None


def evaluate_corpus(cases=CORPUS) -> dict:
    """Deterministic structural-separation + advisory + integrity metrics (§14)."""
    from composite_threat_detector import story_match
    benign = [c for c in cases if c.label == "BENIGN"]
    harmful = [c for c in cases if c.label == "HARMFUL"]
    true_completions = [c for c in harmful if c.expect_would_complete]
    non_completions = [c for c in harmful if not c.expect_would_complete]

    per_case, replay_ok, nonmut_ok = [], 0, 0
    # canonical minimality: cases with NO equivalent duplicate event must be strictly
    # minimal; cases WITH an equivalent duplicate must correctly report non-minimal.
    canon_minimal_ok = canon_minimal_total = 0
    dup_nonminimal_ok = dup_total = 0
    esc_count = observe_count = unavail_count = 0
    benign_esc = benign_tc = benign_false_complete = 0
    tp_hits = evasion_leaks = 0
    # aggregate edge-state counts across all matches
    edge_state_totals = {"SATISFIED": 0, "FAILED": 0, "NOT_EVALUABLE": 0,
                         "AMBIGUOUS": 0}
    dim_fail = {"entity_consistency": 0, "ordering_consistency": 0,
                "timing_consistency": 0}
    binding_counts, witness_sizes = [], []

    for c in cases:
        n_before = len(c.assembly)
        r1 = _run(c)
        r2 = _run(c)
        if r1.verdict_digest == r2.verdict_digest:
            replay_ok += 1
        if len(c.assembly) == n_before:          # input list not mutated
            nonmut_ok += 1

        completes = r1.category == WC
        if r1.signal == "ESCALATE":
            esc_count += 1
        elif r1.signal == "OBSERVE":
            observe_count += 1
        elif r1.signal == "UNAVAILABLE":
            unavail_count += 1

        if c.label == "BENIGN":
            if r1.signal == "ESCALATE":
                benign_esc += 1
            if r1.category == V.THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT:
                benign_tc += 1
            if completes:
                benign_false_complete += 1
        else:
            if c.expect_would_complete and completes:
                tp_hits += 1
            if not c.expect_would_complete and completes:
                evasion_leaks += 1

        if completes:
            w = r1.completion_witness
            if w:
                witness_sizes.append(len(w.get("witness_events", {})) + 1)
            has_dup = _has_equiv_dup(c)
            if has_dup:
                dup_total += 1
                # a duplicate-bearing completion must correctly report NON-minimal
                if w and not w.get("minimality_verified"):
                    dup_nonminimal_ok += 1
            else:
                canon_minimal_total += 1
                if w and w.get("minimality_verified"):
                    canon_minimal_ok += 1

        # structural aggregates from the hypothetical after-state match
        m = story_match(ATO, list(c.assembly) + [_rebase(c)])
        binding_counts.append(m.multiple_optimal_bindings)
        for er in m.edge_results:
            if er["kind"] == "COVERED_BY_AUTHORIZATION":
                continue
            edge_state_totals[er["state"]] = edge_state_totals.get(er["state"], 0) + 1
        dr = m.dimension_results
        for k in dim_fail:
            if dr.get(k, {}).get("status") == "FAILED":
                dim_fail[k] += 1

        per_case.append({"case_id": c.case_id, "family": c.family, "label": c.label,
                         "split": split_of(c.case_id),
                         "expect_would_complete": c.expect_would_complete,
                         "category": r1.category, "signal": r1.signal,
                         "completes": completes})

    n = len(cases)
    total_edges = sum(edge_state_totals.values()) or 1
    metrics = {
        "evidence_label": "encoded-pattern structural separation + advisory/integrity "
                          "metrics on a hand-built corpus for ONE account-takeover "
                          "StoryGraph; NOT fraud-detection accuracy on real traffic",
        "matcher_semantics": MATCHER_SEMANTICS_VERSION,
        "n_cases": n, "n_benign": len(benign), "n_harmful": len(harmful),
        "n_true_completions": len(true_completions),
        "n_evasions_and_unknown": len(non_completions),
        # completion metrics
        "encoded_completion_detection_rate": _rate(tp_hits, len(true_completions)),
        "missed_encoded_completion_rate":
            _rate(len(true_completions) - tp_hits, len(true_completions)),
        "benign_false_completion_rate": _rate(benign_false_complete, len(benign)),
        "evasion_false_completion_rate": _rate(evasion_leaks, len(non_completions)),
        # advisory-signal metrics
        "benign_escalate_rate": _rate(benign_esc, len(benign)),
        "benign_threat_consistent_rate": _rate(benign_tc, len(benign)),
        "harmful_partial_escalate_rate":
            _rate(sum(1 for pc in per_case if pc["label"] == "HARMFUL"
                      and not pc["completes"] and pc["signal"] == "ESCALATE"),
                  len(non_completions)),
        "observe_rate": _rate(observe_count, n),
        "escalate_rate": _rate(esc_count, n),
        "unavailable_rate": _rate(unavail_count, n),
        # structural metrics
        "edge_state_totals": edge_state_totals,
        "not_evaluable_edge_rate": round(
            edge_state_totals["NOT_EVALUABLE"] / total_edges, 4),
        "ambiguous_edge_rate": round(edge_state_totals["AMBIGUOUS"] / total_edges, 4),
        "dimension_failed_counts": dim_fail,
        # canonical (no equivalent-duplicate) completions must be strictly minimal
        "witness_minimality_pass_rate": _rate(canon_minimal_ok, canon_minimal_total),
        # duplicate-bearing completions must correctly REPORT non-minimal (honest)
        "duplicate_witness_nonminimal_correct_rate": _rate(dup_nonminimal_ok, dup_total),
        "n_duplicate_completions": dup_total,
        "deterministic_replay_pass_rate": _rate(replay_ok, n),
        "non_mutation_pass_rate": _rate(nonmut_ok, n),
        # operational (measured on synthetic corpus)
        "mean_candidate_bindings": round(sum(binding_counts) / n, 3),
        "p95_candidate_bindings": sorted(binding_counts)[int(0.95 * (n - 1))],
        "mean_witness_size": (round(sum(witness_sizes) / len(witness_sizes), 3)
                              if witness_sizes else None),
        "measured_escalations_per_1000_cases": round(1000 * esc_count / n, 2),
        "not_run": ["duplicate_review_rate (needs a live review queue)",
                    "alerts_per_1000_events on real traffic",
                    "review_items_per_tenant_day on real traffic"],
        "per_case": per_case,
    }
    return metrics


def _rebase(c: Case):
    """The hypothetical proposed event, rebased past the assembly (mirrors the
    engine's non-mutating insertion) so structural aggregates use the same view."""
    import dataclasses
    if c.assembly and c.proposed.epoch is None:
        return dataclasses.replace(
            c.proposed, position=max(e.position for e in c.assembly) + 1)
    return c.proposed


def check_gates(metrics=None, gates=PREREGISTERED_GATES) -> dict:
    """Evaluate the pre-registered acceptance gates against measured metrics (§15)."""
    m = metrics or evaluate_corpus()
    checks = []

    def le(name, key, bound):
        v = m.get(key)
        checks.append({"gate": name, "metric": key, "value": v, "bound": bound,
                       "direction": "<=", "pass": v is not None and v <= bound})

    def ge(name, key, bound):
        v = m.get(key)
        checks.append({"gate": name, "metric": key, "value": v, "bound": bound,
                       "direction": ">=", "pass": v is not None and v >= bound})

    ge("encoded completion", "encoded_completion_detection_rate",
       gates["min_encoded_completion_detection_rate"])
    le("benign false completion", "benign_false_completion_rate",
       gates["max_benign_false_completion_rate"])
    le("evasion false completion", "evasion_false_completion_rate",
       gates["max_evasion_false_completion_rate"])
    le("benign escalate", "benign_escalate_rate", gates["max_benign_escalate_rate"])
    le("benign threat-consistent (defect)", "benign_threat_consistent_rate",
       gates["max_benign_threat_consistent_rate"])
    ge("witness minimality (canonical)", "witness_minimality_pass_rate",
       gates["min_witness_minimality_pass_rate"])
    ge("duplicate witness non-minimal reported", "duplicate_witness_nonminimal_correct_rate",
       gates["min_duplicate_witness_nonminimal_correct_rate"])
    ge("deterministic replay", "deterministic_replay_pass_rate",
       gates["min_deterministic_replay_pass_rate"])
    ge("non-mutation", "non_mutation_pass_rate", gates["min_non_mutation_pass_rate"])
    return {"all_pass": all(c["pass"] for c in checks), "checks": checks}


def run_final_split(frozen: dict) -> dict:
    """Run the UNTOUCHED final split exactly once under a frozen configuration (§13).

    Refuses (via ``freeze.require_frozen``) if any frozen input changed — the corpus,
    the graph, the matcher semantics, the partial-escalation policy, or the gates.
    Returns the final-split metrics + the pre-registered gate result.
    """
    from evaluation import freeze
    freeze.require_frozen(frozen, official=True)   # raises on any drift
    final_cases = cases_for_split("final")
    metrics = evaluate_corpus(final_cases)
    metrics["split"] = "final"
    gate_result = check_gates(metrics)
    return {"metrics": metrics, "gates": gate_result,
            "freeze_digest": frozen.get("freeze_digest")}
