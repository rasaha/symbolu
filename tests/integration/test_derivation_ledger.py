import hashlib
from derivation_ledger import (
    DerivationStep,
    DerivationLedger,
    DerivationLedgerError,
    create_genesis_step,
    append_step,
    verify_ledger,
    replay_hash_chain,
)


def make_hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def test_genesis_ledger_is_valid():
    output_hash = make_hash("output_0")
    ledger = create_genesis_step("phase_1", output_hash)
    assert verify_ledger(ledger) is True
    assert len(ledger.steps) == 1
    assert ledger.steps[0].phase_id == "phase_1"
    assert ledger.steps[0].rule_id == "GENESIS"
    assert ledger.steps[0].match_key == "GENESIS"
    assert ledger.steps[0].output_hash == output_hash


def test_append_preserves_continuity():
    output_0 = make_hash("output_0")
    ledger = create_genesis_step("phase_1", output_0)
    output_1 = make_hash("output_1")
    step = DerivationStep(
        phase_id="phase_2",
        rule_id="rule_a",
        match_key="key_a",
        input_hash=output_0,
        output_hash=output_1
    )
    ledger = append_step(ledger, step)
    assert verify_ledger(ledger) is True
    assert len(ledger.steps) == 2
    assert ledger.steps[1].input_hash == ledger.steps[0].output_hash


def test_tampering_breaks_verification():
    output_0 = make_hash("output_0")
    ledger = create_genesis_step("phase_1", output_0)
    tampered_step = DerivationStep(
        phase_id="phase_1",
        rule_id="GENESIS",
        match_key="GENESIS",
        input_hash=ledger.steps[0].input_hash,
        output_hash=make_hash("tampered")
    )
    tampered_ledger = DerivationLedger(
        steps=(tampered_step,),
        ledger_hash=ledger.ledger_hash
    )
    assert verify_ledger(tampered_ledger) is False


def test_reordering_steps_fails():
    output_0 = make_hash("output_0")
    ledger = create_genesis_step("phase_1", output_0)
    output_1 = make_hash("output_1")
    step_1 = DerivationStep(
        phase_id="phase_2",
        rule_id="rule_a",
        match_key="key_a",
        input_hash=output_0,
        output_hash=output_1
    )
    ledger = append_step(ledger, step_1)
    output_2 = make_hash("output_2")
    step_2 = DerivationStep(
        phase_id="phase_3",
        rule_id="rule_b",
        match_key="key_b",
        input_hash=output_1,
        output_hash=output_2
    )
    ledger = append_step(ledger, step_2)
    reordered_steps = (ledger.steps[0], ledger.steps[2], ledger.steps[1])
    reordered_ledger = DerivationLedger(
        steps=reordered_steps,
        ledger_hash=ledger.ledger_hash
    )
    assert verify_ledger(reordered_ledger) is False


def test_replay_hash_equals_ledger_hash():
    output_0 = make_hash("output_0")
    ledger = create_genesis_step("phase_1", output_0)
    output_1 = make_hash("output_1")
    step = DerivationStep(
        phase_id="phase_2",
        rule_id="rule_a",
        match_key="key_a",
        input_hash=output_0,
        output_hash=output_1
    )
    ledger = append_step(ledger, step)
    replayed = replay_hash_chain(ledger)
    assert replayed == ledger.ledger_hash


def test_determinism_across_100_runs():
    output_0 = make_hash("output_0")
    first_ledger = create_genesis_step("phase_1", output_0)
    first_hash = first_ledger.ledger_hash
    for _ in range(99):
        ledger = create_genesis_step("phase_1", output_0)
        assert ledger.ledger_hash == first_hash
        assert replay_hash_chain(ledger) == first_hash


def test_empty_ledger_is_rejected():
    empty_ledger = DerivationLedger(steps=(), ledger_hash=make_hash("empty"))
    raised = False
    try:
        verify_ledger(empty_ledger)
    except DerivationLedgerError:
        raised = True
    assert raised is True


def test_missing_phase_id_rejected():
    output_0 = make_hash("output_0")
    raised = False
    try:
        create_genesis_step("", output_0)
    except DerivationLedgerError:
        raised = True
    assert raised is True


def test_free_form_text_not_allowed():
    output_0 = make_hash("output_0")
    ledger = create_genesis_step("phase_1", output_0)
    output_1 = make_hash("output_1")
    raised = False
    try:
        step = DerivationStep(
            phase_id="phase\nwith\nnewlines",
            rule_id="rule_a",
            match_key="key_a",
            input_hash=output_0,
            output_hash=output_1
        )
        append_step(ledger, step)
    except DerivationLedgerError:
        raised = True
    assert raised is True
    raised = False
    try:
        step = DerivationStep(
            phase_id="phase_2",
            rule_id="rule|with|pipes",
            match_key="key_a",
            input_hash=output_0,
            output_hash=output_1
        )
        append_step(ledger, step)
    except DerivationLedgerError:
        raised = True
    assert raised is True
    raised = False
    try:
        step = DerivationStep(
            phase_id="phase_2",
            rule_id="rule_a",
            match_key="key(with)parens",
            input_hash=output_0,
            output_hash=output_1
        )
        append_step(ledger, step)
    except DerivationLedgerError:
        raised = True
    assert raised is True


def test_hash_mismatch_fails_immediately():
    output_0 = make_hash("output_0")
    ledger = create_genesis_step("phase_1", output_0)
    wrong_input = make_hash("wrong")
    output_1 = make_hash("output_1")
    step = DerivationStep(
        phase_id="phase_2",
        rule_id="rule_a",
        match_key="key_a",
        input_hash=wrong_input,
        output_hash=output_1
    )
    raised = False
    try:
        append_step(ledger, step)
    except DerivationLedgerError:
        raised = True
    assert raised is True


if __name__ == "__main__":
    test_genesis_ledger_is_valid()
    test_append_preserves_continuity()
    test_tampering_breaks_verification()
    test_reordering_steps_fails()
    test_replay_hash_equals_ledger_hash()
    test_determinism_across_100_runs()
    test_empty_ledger_is_rejected()
    test_missing_phase_id_rejected()
    test_free_form_text_not_allowed()
    test_hash_mismatch_fails_immediately()
