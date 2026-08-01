"""Witness canonicalization under duplicates (§6-§8) + mandatory-edge fail-closed
completion semantics (§9, §10). Verification phase (matcher/2.0.0, tiebreak/2.0.0).
"""

from __future__ import annotations

import pytest

from ugence_storygraph import (
    ACCOUNT_TAKEOVER_TRANSFER as ATO, ObservedEvent, completion_witness,
    evaluate_proposed_action, story_match, storyverdict,
)
from ugence_storygraph import financial as F
from ugence_storygraph.storygraph import (
    EDGE_AMBIGUOUS, EDGE_FAILED, EDGE_NOT_EVALUABLE, EDGE_SATISFIED,
)

V = storyverdict


def oe(frag, eid, pos, actor="u1", **ent):
    return ObservedEvent(frag, eid, pos, None, actor, dict(ent))


def _base():
    return [oe(F.CRED_RESET, "reset", 1, account="a1"),
            oe(F.DEVICE_NEW, "device", 2, account="a1", device="d1"),
            oe(F.BENEFICIARY_ADD, "benef", 3, account="a1", beneficiary="bob")]


def _prop(**over):
    ent = {"account": "a1", "beneficiary": "bob", "device": "d1", "amount": "9000"}
    ent.update(over)
    return oe(F.TRANSFER, "xfer", 99, **ent)


def _w(assembly, proposed=None):
    return completion_witness(ATO, assembly, proposed or _prop())


# ===========================================================================
# §6-§8  witness canonicalization + strict minimality
# ===========================================================================
def test_tie_break_version_is_2():
    assert V.TIE_BREAK_RULE_VERSION == "ctd.witness.tiebreak/2.0.0"
    w = _w(_base())
    assert w.tie_break_rule_version == "ctd.witness.tiebreak/2.0.0"


def test_clean_witness_is_minimal_no_exclusions():
    w = _w(_base())
    assert w.minimality_verified is True
    assert w.excluded_equivalent_events == []
    assert set(w.canonical_witness) == {"reset", "device", "benef", "xfer"}


def test_one_duplicate_reset_canonicalized():
    asm = _base() + [oe(F.CRED_RESET, "reset-2", 1, account="a1")]
    w = _w(asm)
    assert w.minimality_verified is True
    assert "reset-2" in w.excluded_equivalent_events
    assert sorted(w.equivalence_classes["reset"]) == ["reset", "reset-2"]


def test_multiple_duplicate_resets_canonicalized():
    asm = _base() + [oe(F.CRED_RESET, f"reset-{i}", 1, account="a1") for i in range(3)]
    w = _w(asm)
    assert w.minimality_verified is True
    assert len([e for e in w.excluded_equivalent_events if e.startswith("reset-")]) == 3


def test_duplicate_device_enrollments_canonicalized():
    asm = _base() + [oe(F.DEVICE_NEW, "device-2", 2, account="a1", device="d1")]
    w = _w(asm)
    assert w.minimality_verified is True
    assert "device-2" in w.excluded_equivalent_events


def test_duplicate_beneficiary_additions_canonicalized():
    asm = _base() + [oe(F.BENEFICIARY_ADD, "benef-2", 3, account="a1", beneficiary="bob")]
    w = _w(asm)
    assert w.minimality_verified is True
    assert "benef-2" in w.excluded_equivalent_events


def test_retries_with_different_record_ids_are_equivalent():
    # a retry carries a different transport record id but the same business event;
    # record id is NOT part of the semantic key, so the retry collapses.
    asm = _base() + [oe(F.CRED_RESET, "reset-retry", 1, account="a1",
                        source_record_id="rec-999")]
    w = _w(asm)
    assert w.minimality_verified is True
    assert "reset-retry" in w.excluded_equivalent_events


def test_conflicting_payload_events_are_not_collapsed():
    # same account but a materially different amount => distinct, never collapsed.
    asm = [oe(F.CRED_RESET, "reset", 1, account="a1"),
           oe(F.DEVICE_NEW, "device", 2, account="a1", device="d1"),
           oe(F.BENEFICIARY_ADD, "b1", 3, account="a1", beneficiary="bob", amount="100"),
           oe(F.BENEFICIARY_ADD, "b2", 3, account="a1", beneficiary="bob", amount="200")]
    w = _w(asm)
    # b1/b2 differ materially -> not both excluded as a duplicate of each other
    assert not ({"b1", "b2"} <= set(w.excluded_equivalent_events))


def test_duplicate_proposed_action_already_complete():
    # an equivalent transfer already in the assembly means the pattern completed
    # BEFORE the hypothetical proposal => no new completion witness.
    asm = _base() + [oe(F.TRANSFER, "xfer-prior", 4, account="a1", beneficiary="bob",
                        device="d1", amount="9000")]
    assert _w(asm, _prop()) is None


def test_multiple_genuinely_distinct_eligible_is_not_a_duplicate():
    # two beneficiary events share the beneficiary the transfer pays but differ on a
    # material field (device) => genuinely distinct, a real multiplicity (NOT a
    # duplicate). Reported honestly, not silently canonicalized.
    asm = [oe(F.CRED_RESET, "reset", 1, account="a1"),
           oe(F.DEVICE_NEW, "device", 2, account="a1", device="d1"),
           oe(F.BENEFICIARY_ADD, "benefA", 3, account="a1", beneficiary="bob", device="dx"),
           oe(F.BENEFICIARY_ADD, "benefB", 3, account="a1", beneficiary="bob", device="dy")]
    m = story_match(ATO, asm + [oe(F.TRANSFER, "xfer", 4, account="a1",
                                   beneficiary="bob", device="d1", amount="9000")])
    assert m.multiple_optimal_bindings >= 2            # a real multiplicity
    w = _w(asm)
    # not collapsed as duplicates; the competing candidate is not excluded
    assert "benefB" not in w.excluded_equivalent_events


def test_removal_proofs_are_class_level():
    asm = _base() + [oe(F.CRED_RESET, "reset-2", 1, account="a1")]
    w = _w(asm)
    reset_proof = next(p for p in w.removal_proofs if p["removed_event"] == "reset")
    assert sorted(reset_proof["removed_class"]) == ["reset", "reset-2"]
    assert reset_proof["broke_completion"] is True


def test_witness_digest_stable_under_duplicate_reordering():
    a = _w(_base() + [oe(F.CRED_RESET, "reset-2", 1, account="a1")])
    b = _w([oe(F.CRED_RESET, "reset-2", 1, account="a1")] + _base())
    assert a.certificate_digest == b.certificate_digest


# ===========================================================================
# §9/§10  mandatory-edge fail-closed completion
# ===========================================================================
def _full(**over):
    return _base() + [_prop(**over).__class__(F.TRANSFER, "xfer", 4, None, "u1",
                                              {**_prop(**over).entities})]


def test_mandatory_satisfied_completes():
    m = story_match(ATO, _full())
    assert m.mandatory_unsatisfied is False
    assert m.is_complete() and m.completion_blockers() == []


def test_mandatory_failed_blocks_completion():
    m = story_match(ATO, _full(beneficiary="eve"))   # benef-xfer SAME_ENTITY FAILED
    benef = next(r for r in m.mandatory_edge_states()
                 if r["kind"] == "SAME_ENTITY" and r["dim"] == "beneficiary")
    assert benef["state"] == EDGE_FAILED
    assert not m.is_complete()


def test_mandatory_not_evaluable_blocks_completion():
    # transfer present but beneficiary entity absent => SAME_ENTITY NOT_EVALUABLE
    ev = _base() + [oe(F.TRANSFER, "xfer", 4, account="a1", device="d1", amount="9000")]
    m = story_match(ATO, ev)
    benef = next(r for r in m.mandatory_edge_states()
                 if r["kind"] == "SAME_ENTITY" and r["dim"] == "beneficiary")
    assert benef["state"] == EDGE_NOT_EVALUABLE
    assert m.mandatory_unsatisfied and not m.is_complete()
    assert "mandatory_edge_not_positively_satisfied" in m.completion_blockers()


def test_mandatory_ambiguous_blocks_completion():
    ev = [oe(F.CRED_RESET, "reset", 5, account="a1"),
          oe(F.DEVICE_NEW, "device", 5, account="a1", device="d1"),
          oe(F.BENEFICIARY_ADD, "benef", 5, account="a1", beneficiary="bob"),
          oe(F.TRANSFER, "xfer", 5, account="a1", beneficiary="bob", device="d1",
             amount="9000")]
    m = story_match(ATO, ev)
    assert any(r["state"] == EDGE_AMBIGUOUS for r in m.mandatory_edge_states())
    assert not m.is_complete()


def test_optional_edge_absence_does_not_block_completion():
    # the optional 'limit' node is absent => order(limit,xfer) is NOT_EVALUABLE, but
    # optional => completion still holds.
    m = story_match(ATO, _full())
    assert "limit" not in m.binding                  # optional node absent
    assert m.is_complete()


def test_no_weight_compensates_unsatisfied_mandatory_edge():
    # full coverage + perfect timing, but wrong account on the transfer.
    m = story_match(ATO, _full(account="a2"))
    assert m.risk.coverage == 1.0
    assert not m.is_complete()                        # weights cannot buy completion
