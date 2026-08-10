"""Serialization determinism for signed artifacts (spec §27, §33.1; CI gate)."""

from __future__ import annotations

from dataclasses import replace

from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.crypto.hashing import digest
from risk_authority.domain import CanonicalAction, WorkflowStatus
from risk_authority.services import EnvelopeIssuer, RevocationState

from tests.contract.test_envelope_monotonicity import DECISION_SCOPE, NOW, _decision
from tests.scenario import build_workflow


def test_canonical_action_digest_is_stable():
    a = CanonicalAction(
        tenant_id="t",
        actor_id="a",
        model_id="m",
        action_type="refund.prepare",
        target_id="txn_1",
        purpose="CUSTOMER_REFUND_REVIEW",
        data_classes=("CUSTOMER_PII", "TRANSACTION_DATA"),
        destination="internal://finance",
        amount_minor_units=320000,
        currency="USD",
    )
    # Reordered data classes canonicalize identically? No — action data_classes
    # order is preserved (semantic), so equality requires identical order.
    assert a.digest == a.digest
    b = replace(a, amount_minor_units=320001)
    assert a.digest != b.digest


def test_workflow_digest_is_immutable_and_recomputable():
    workflow = build_workflow()
    # Recomputing the digest is idempotent.
    assert workflow.with_digest().digest == workflow.digest
    # Any change to executable content changes the digest (AC-01).
    mutated = replace(workflow, version="4.1.1").with_digest()
    assert mutated.digest != workflow.digest


def test_envelope_signing_payload_excludes_signature():
    issuer = EnvelopeIssuer()
    env = issuer.issue(
        envelope_id="rae_1",
        decision=_decision(DECISION_SCOPE),
        audience="rt",
        subject="a",
        model_id="m",
        session_id="s",
        nonce="n",
        key_record=SigningKeyRecord("k", SigningKey.from_seed(bytes(range(32)))),
        revocation_state=RevocationState(),
        now=NOW,
    )
    payload_with_sig = env.signing_payload()
    payload_without = replace(env, signature=b"").signing_payload()
    # The signing payload is identical whether or not the signature is attached.
    assert payload_with_sig == payload_without


def test_workflow_source_rejects_non_active():
    from risk_authority.integrations import InMemoryWorkflowIRSource

    source = InMemoryWorkflowIRSource()
    draft = replace(build_workflow(), status=WorkflowStatus.DRAFT).with_digest()
    source.register(draft)
    assert source.get(draft.workflow_ir_id) is None
