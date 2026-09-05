"""The execution key: canonical, retry-stable, unique per authorized action, receipt-free."""

from __future__ import annotations

import hashlib
import json

import pytest

from ugence_governance_contracts.api import IdempotencyScope

from ugence_execution_reservation import EXECUTION_KEY_PREFIX, ContractViolation, ExecutionKey

from _fixtures import ACTFP, AUTHZ, OPERATION, TARGET, TENANT, key


def test_serialization_is_domain_separated_sha256_with_the_design_prefix():
    k = key()
    payload = json.dumps({"tenant_id": TENANT, "authorization_ref": AUTHZ,
                          "authorized_action_fingerprint": ACTFP, "target_ref": TARGET,
                          "operation": OPERATION}, sort_keys=True, separators=(",", ":"))
    preimage = f"execution_reservation\x1fexec_key\x1fv1\x1f{payload}"
    assert k.serialized == EXECUTION_KEY_PREFIX + hashlib.sha256(preimage.encode()).hexdigest()
    assert k.serialized.startswith("exec_key.v1:") and len(k.serialized) == len("exec_key.v1:") + 64


def test_stable_across_retries_and_across_reissued_receipts():
    # The receipt ref is not part of the key: same action → same key, always.
    assert key().serialized == key().serialized
    assert ExecutionKey(**{"tenant_id": " acme ", "authorization_ref": AUTHZ,
                           "authorized_action_fingerprint": ACTFP, "target_ref": TARGET,
                           "operation": OPERATION}).serialized == key().serialized


@pytest.mark.parametrize("kw", [{"tenant": "other"}, {"authz": "authz-2"}, {"fp": "FP-2"},
                                {"target": "target-2"}, {"operation": "merge"}])
def test_any_coordinate_change_yields_a_distinct_key(kw):
    assert key(**kw).serialized != key().serialized


@pytest.mark.parametrize("field", ["tenant_id", "authorization_ref", "authorized_action_fingerprint",
                                   "target_ref", "operation"])
def test_every_coordinate_is_required(field):
    kw = dict(tenant_id=TENANT, authorization_ref=AUTHZ, authorized_action_fingerprint=ACTFP,
              target_ref=TARGET, operation=OPERATION)
    kw[field] = "  "
    with pytest.raises(ContractViolation):
        ExecutionKey(**kw)


def test_neutral_projection_is_global_scope_partitioned_by_tenant():
    ik = key().to_idempotency_key()
    assert ik.scope is IdempotencyScope.GLOBAL
    assert ik.partition == TENANT and ik.key == key().serialized
    assert ik.actor == "" and ik.target_resource == ""
    assert key().neutral_idempotency_digest() == ik.canonical_digest()
    assert key(tenant="other").neutral_idempotency_digest() != key().neutral_idempotency_digest()
