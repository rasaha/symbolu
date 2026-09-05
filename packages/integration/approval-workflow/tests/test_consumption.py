"""``GRANTED -> CONSUMED``, exactly once: the key, the refusals, and the neutral
projection onto the governance-contracts idempotency family."""

from __future__ import annotations

import pytest

from ugence_governance_contracts.api import (
    IdempotencyDisposition,
    IdempotencyKey,
    IdempotencyScope,
)

from ugence_approval_workflow import (
    APPROVAL_KEY_PREFIX,
    ApprovalState,
    ConsumptionKey,
    ConsumptionResult,
    ContractViolation,
    ReviewDecision,
    consumption_id_for,
)

from _fixtures import (
    AFTER_WINDOW,
    APPROVER,
    DIGEST,
    OTHER_DIGEST,
    REQUESTER,
    ROLE,
    T0,
    T1,
    T2,
    granted,
    memory_store,
    sqlite_store,
    subject,
    window,
)

CONSUMER = "decision_case:case_1/review_task:rev_1"


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    s = memory_store() if request.param == "memory" else sqlite_store(tmp_path)
    yield s
    s.close()


# --------------------------------------------------------------------------- #
# The key
# --------------------------------------------------------------------------- #
def test_the_consumption_key_is_canonical_and_serialized_as_ratified():
    key = ConsumptionKey(tenant_id="t", approval_id="apr_1", subject_digest=DIGEST,
                         consumer_ref=CONSUMER)
    assert key.serialized.startswith(APPROVAL_KEY_PREFIX)
    assert len(key.serialized) == len(APPROVAL_KEY_PREFIX) + 64
    same = ConsumptionKey(tenant_id="t", approval_id="apr_1", subject_digest=DIGEST,
                          consumer_ref=CONSUMER)
    assert key.serialized == same.serialized and consumption_id_for(key) == consumption_id_for(same)
    for changed in (
        ConsumptionKey("t2", "apr_1", DIGEST, CONSUMER),
        ConsumptionKey("t", "apr_2", DIGEST, CONSUMER),
        ConsumptionKey("t", "apr_1", OTHER_DIGEST, CONSUMER),
        ConsumptionKey("t", "apr_1", DIGEST, "other-consumer"),
    ):
        assert changed.serialized != key.serialized
    with pytest.raises(ContractViolation):
        ConsumptionKey(tenant_id="t", approval_id="apr_1", subject_digest=DIGEST, consumer_ref=" ")


def test_the_key_projects_neutrally_onto_the_idempotency_family():
    key = ConsumptionKey(tenant_id="t", approval_id="apr_1", subject_digest=DIGEST,
                         consumer_ref=CONSUMER)
    projected = key.to_idempotency_key()
    assert projected == IdempotencyKey(key=key.serialized, scope=IdempotencyScope.GLOBAL,
                                       partition="t")
    assert key.neutral_idempotency_digest() == projected.canonical_digest()


# --------------------------------------------------------------------------- #
# Exactly once
# --------------------------------------------------------------------------- #
def test_a_granted_approval_is_consumed_exactly_once(store):
    record = granted(store)
    first = store.consume(record.approval_id, consumer_ref=CONSUMER,
                          subject_digest=record.subject_digest, as_of=T2)
    assert first.is_consumed and first.result is ConsumptionResult.CONSUMED_FIRST
    assert store.get_approval(record.approval_id).state is ApprovalState.CONSUMED
    assert store.get_approval(record.approval_id).consumer_ref == CONSUMER

    second = store.consume(record.approval_id, consumer_ref=CONSUMER,
                           subject_digest=record.subject_digest, as_of=T2)
    assert not second.is_consumed and second.result is ConsumptionResult.ALREADY_CONSUMED
    assert second.holder == first.consumption_id


def test_a_different_consumer_cannot_consume_the_same_approval(store):
    record = granted(store)
    assert store.consume(record.approval_id, consumer_ref=CONSUMER,
                         subject_digest=record.subject_digest, as_of=T2).is_consumed
    other = store.consume(record.approval_id, consumer_ref="decision_case:case_2",
                          subject_digest=record.subject_digest, as_of=T2)
    assert other.result is ConsumptionResult.ALREADY_CONSUMED and not other.is_consumed


def test_the_outcome_projects_to_an_idempotency_resolution(store):
    record = granted(store)
    first = store.consume(record.approval_id, consumer_ref=CONSUMER,
                          subject_digest=record.subject_digest, as_of=T2)
    assert first.resolution.disposition is IdempotencyDisposition.FIRST
    assert first.resolution.key == first.key.to_idempotency_key()

    second = store.consume(record.approval_id, consumer_ref=CONSUMER,
                           subject_digest=record.subject_digest, as_of=T2)
    assert second.resolution.disposition is IdempotencyDisposition.DUPLICATE
    assert second.resolution.duplicate_of == first.consumption_id


# --------------------------------------------------------------------------- #
# Refusals — never resolutions
# --------------------------------------------------------------------------- #
def test_an_ungranted_approval_is_not_consumable(store):
    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    outcome = store.consume(record.approval_id, consumer_ref=CONSUMER,
                            subject_digest=record.subject_digest, as_of=T0)
    assert outcome.result is ConsumptionResult.NOT_GRANTED and outcome.resolution is None
    assert store.get_approval(record.approval_id).state is ApprovalState.REQUESTED

    store.present_for_decision(record.approval_id, as_of=T0)
    store.decide(record.approval_id, approver=APPROVER, decision=ReviewDecision.REJECT, as_of=T1)
    rejected = store.consume(record.approval_id, consumer_ref=CONSUMER,
                             subject_digest=record.subject_digest, as_of=T2)
    assert rejected.result is ConsumptionResult.NOT_GRANTED and rejected.resolution is None


def test_a_lapsed_grant_is_refused_not_consumed(store):
    record = granted(store)
    outcome = store.consume(record.approval_id, consumer_ref=CONSUMER,
                            subject_digest=record.subject_digest, as_of=AFTER_WINDOW)
    assert outcome.result is ConsumptionResult.EXPIRED_APPROVAL and outcome.resolution is None
    assert store.get_approval(record.approval_id).state is ApprovalState.GRANTED


def test_a_changed_subject_can_never_consume_a_standing_approval(store):
    record = granted(store)
    outcome = store.consume(record.approval_id, consumer_ref=CONSUMER,
                            subject_digest=OTHER_DIGEST, as_of=T2)
    assert outcome.result is ConsumptionResult.SUBJECT_MISMATCH and outcome.resolution is None
    assert store.get_approval(record.approval_id).state is ApprovalState.GRANTED


def test_an_unknown_approval_is_refused(store):
    outcome = store.consume("apr_nope", consumer_ref=CONSUMER, subject_digest=DIGEST, as_of=T2)
    assert outcome.result is ConsumptionResult.NOT_GRANTED and outcome.resolution is None


def test_consumption_is_recorded_in_the_event_ledger(store):
    record = granted(store)
    store.consume(record.approval_id, consumer_ref=CONSUMER,
                  subject_digest=record.subject_digest, as_of=T2)
    events = store.approval_events(record.approval_id)
    assert [e.event_type for e in events][-1] is ApprovalState.CONSUMED
    assert [e.sequence for e in events] == list(range(len(events)))
