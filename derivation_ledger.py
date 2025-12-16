from dataclasses import dataclass
from typing import Tuple
import hashlib


class DerivationLedgerError(Exception):
    pass


@dataclass(frozen=True)
class DerivationStep:
    phase_id: str
    rule_id: str
    match_key: str
    input_hash: str
    output_hash: str


@dataclass(frozen=True)
class DerivationLedger:
    steps: Tuple[DerivationStep, ...]
    ledger_hash: str


def _validate_field(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise DerivationLedgerError(f"{field_name} must be str")
    if len(value) == 0:
        raise DerivationLedgerError(f"{field_name} must not be empty")
    for char in value:
        if char in ('\n', '\r', '\t', '|', '(', ')'):
            raise DerivationLedgerError(f"{field_name} contains forbidden character")


def _validate_hash_field(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise DerivationLedgerError(f"{field_name} must be str")
    if len(value) != 64:
        raise DerivationLedgerError(f"{field_name} must be 64 hex characters")
    for char in value:
        if char not in '0123456789abcdef':
            raise DerivationLedgerError(f"{field_name} must be lowercase hex")


def _validate_step(step: DerivationStep) -> None:
    if not isinstance(step, DerivationStep):
        raise DerivationLedgerError("step must be DerivationStep")
    _validate_field(step.phase_id, "phase_id")
    _validate_field(step.rule_id, "rule_id")
    _validate_field(step.match_key, "match_key")
    _validate_hash_field(step.input_hash, "input_hash")
    _validate_hash_field(step.output_hash, "output_hash")


def _serialize_step(step: DerivationStep) -> str:
    return (
        "(" +
        step.phase_id + "|" +
        step.rule_id + "|" +
        step.match_key + "|" +
        step.input_hash + "|" +
        step.output_hash +
        ")"
    )


def _serialize_steps(steps: Tuple[DerivationStep, ...]) -> str:
    parts = []
    for step in steps:
        parts.append(_serialize_step(step))
    return "".join(parts)


def _compute_ledger_hash(steps: Tuple[DerivationStep, ...]) -> str:
    serialized = _serialize_steps(steps)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def create_genesis_step(
    phase_id: str,
    output_hash: str
) -> DerivationLedger:
    _validate_field(phase_id, "phase_id")
    _validate_hash_field(output_hash, "output_hash")
    genesis_input = hashlib.sha256(b"GENESIS").hexdigest()
    step = DerivationStep(
        phase_id=phase_id,
        rule_id="GENESIS",
        match_key="GENESIS",
        input_hash=genesis_input,
        output_hash=output_hash
    )
    steps = (step,)
    ledger_hash = _compute_ledger_hash(steps)
    return DerivationLedger(steps=steps, ledger_hash=ledger_hash)


def append_step(
    ledger: DerivationLedger,
    step: DerivationStep
) -> DerivationLedger:
    if not isinstance(ledger, DerivationLedger):
        raise DerivationLedgerError("ledger must be DerivationLedger")
    if len(ledger.steps) == 0:
        raise DerivationLedgerError("ledger must not be empty")
    _validate_step(step)
    last_step = ledger.steps[-1]
    if step.input_hash != last_step.output_hash:
        raise DerivationLedgerError("hash continuity violation")
    new_steps = ledger.steps + (step,)
    new_hash = _compute_ledger_hash(new_steps)
    return DerivationLedger(steps=new_steps, ledger_hash=new_hash)


def verify_ledger(ledger: DerivationLedger) -> bool:
    if not isinstance(ledger, DerivationLedger):
        raise DerivationLedgerError("ledger must be DerivationLedger")
    if len(ledger.steps) == 0:
        raise DerivationLedgerError("ledger must not be empty")
    for step in ledger.steps:
        _validate_step(step)
    genesis_input = hashlib.sha256(b"GENESIS").hexdigest()
    first_step = ledger.steps[0]
    if first_step.input_hash != genesis_input:
        return False
    if first_step.rule_id != "GENESIS":
        return False
    if first_step.match_key != "GENESIS":
        return False
    for i in range(1, len(ledger.steps)):
        if ledger.steps[i].input_hash != ledger.steps[i - 1].output_hash:
            return False
    computed_hash = _compute_ledger_hash(ledger.steps)
    if computed_hash != ledger.ledger_hash:
        return False
    return True


def replay_hash_chain(ledger: DerivationLedger) -> str:
    if not isinstance(ledger, DerivationLedger):
        raise DerivationLedgerError("ledger must be DerivationLedger")
    if len(ledger.steps) == 0:
        raise DerivationLedgerError("ledger must not be empty")
    for step in ledger.steps:
        _validate_step(step)
    return _compute_ledger_hash(ledger.steps)
