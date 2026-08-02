"""Acceptance tests 26-31: CER (cer.v1) and ActionGate shadow behavior."""
from __future__ import annotations

import pytest

from cg_helpers import T0, drive_to_shadow_complete, make_payload, revision_of
from ugence_code_governance import (
    CodeGovernanceService,
    MergeMethod,
    PreparedMergeAction,
)
from ugence_code_governance.governance.actiongate_adapter import ActionGateShadowAdapter
from ugence_code_governance.governance.prepared_action import PreparedMergeAction as PMA


def _change(service, **kw):
    return service.ingest_change_event(make_payload(**kw), tenant_id="acme",
                                       captured_at=T0, delivery_id=kw.get("head_sha", "d"))


# 26. CER uses canonical cer.v1
def test_cer_is_canonical_v1(service: CodeGovernanceService):
    change = _change(service)
    rid = drive_to_shadow_complete(service, change)
    cer_id = service.get_workflow("acme", rid).cer_id
    # the kernel bound a real cer.v1 record
    cer = service._kernel._cer.get_cer(cer_id)
    assert cer.schema_version == "cer.v1"
    assert cer.content_hash


# 27. exact SHA values remain in requested parameters / product envelope
def test_exact_sha_values_in_requested_parameters(service: CodeGovernanceService):
    change = _change(service)
    rid = drive_to_shadow_complete(service, change)
    action = service._scratch[("acme", rid)]["prepared_action"]
    params = action.requested_parameters
    assert params["head_sha"] == change.head_sha
    assert params["base_sha"] == change.base_sha
    assert params["merge_method"] == "squash"


# 28. prepared action fingerprint changes with head/base/method
def test_prepared_action_fingerprint_sensitivity():
    import dataclasses
    base = PMA(tenant_id="acme", repository="acme/widgets", pull_request_number=42,
              base_sha="b", head_sha="h", merge_method=MergeMethod.SQUASH,
              target_branch="main", change_fingerprint="cf", decision_record_id="d",
              cer_id="c", cer_content_hash="hash", policy_refs=("p:v1",))
    assert dataclasses.replace(base, head_sha="h2").fingerprint != base.fingerprint
    assert dataclasses.replace(base, base_sha="b2").fingerprint != base.fingerprint
    assert dataclasses.replace(base, merge_method=MergeMethod.MERGE).fingerprint != base.fingerprint


# 29. ActionGate denial remains denial
def test_actiongate_denial_remains_denial(service: CodeGovernanceService):
    from actiongate_provider.api import ActionGateEngine, build_actiongate_provider
    engine = ActionGateEngine(denied=frozenset({"merge_pull_request"}))
    provider = build_actiongate_provider(engine=engine)
    provider.initialize()
    service._actiongate = ActionGateShadowAdapter(provider=provider)
    change = _change(service)
    rid = drive_to_shadow_complete(service, change)
    shadow_eval = service._scratch[("acme", rid)]["shadow_eval"]
    assert shadow_eval.outcome == "DENIED"
    assert not shadow_eval.would_authorize


# 30. ActionGate result is recorded as shadow only
def test_actiongate_result_is_shadow_only(service: CodeGovernanceService):
    change = _change(service)
    rid = drive_to_shadow_complete(service, change)
    shadow_eval = service._scratch[("acme", rid)]["shadow_eval"]
    assert shadow_eval.mode.value == "SHADOW_ONLY"
    chain = service.get_governance_chain("acme", service.get_workflow("acme", rid).chain_id)
    assert chain.workflow_mode.value == "SHADOW"
    assert chain.execution_status.value == "DISABLED"


# 31. no execution method can be invoked
def test_no_execution_method_exists(service: CodeGovernanceService):
    assert service.execution_status() == "DISABLED"
    # the product surface exposes no merge/execute/dispatch method
    for forbidden in ("merge", "execute", "dispatch", "approve_merge", "perform_merge"):
        assert not hasattr(service, forbidden)
