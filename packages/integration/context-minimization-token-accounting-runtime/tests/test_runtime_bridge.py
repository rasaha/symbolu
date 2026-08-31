"""End-to-end: a real AgentRuntime drives the bridge, which records CM token accounting.

Uses deterministic bounded advancement (prepare -> register -> advance) — no sleep-based
concurrency, no wall clock.
"""

from __future__ import annotations

from ugence_agent_runtime.api import (
    AgentRuntimeConfig,
    TaskDefinition,
    WorkflowDefinition,
    create_runtime,
    register_provider,
)
from ugence_agent_runtime.governance.hooks import AllowAllGovernanceHook
from ugence_agent_runtime.governance.interfaces import GovernanceDisposition
from ugence_agent_runtime.models.workflow import WorkflowStatus

from ugence_context_minimization.api import (
    AttemptStatus,
    InMemoryTokenAccountingSink,
    UsageAvailability,
    aggregate_logical_request_usage,
    prepare_api_call_measurement,
)

from ugence_cm_token_accounting_runtime import (
    MappingUsageNormalizer,
    RuntimeTokenAccountingBridge,
)

from support_itg import (
    VENDOR_FIELD_MAP,
    FlakyUsageProvider,
    UsageProvider,
    sample_minimization_result,
)


def _wf(*tasks):
    return WorkflowDefinition(workflow_id="wf", tasks=tuple(tasks))


def _normalizer():
    return MappingUsageNormalizer(VENDOR_FIELD_MAP, schema_name="vendor.v1",
                                  adapter_id="ad", adapter_version="1")


def _runtime_with_bridge(provider, bridge, hook=None, **cfg):
    cfg.setdefault("governance_hook", hook or AllowAllGovernanceHook())
    rt = create_runtime(AgentRuntimeConfig(attempt_observer=bridge, **cfg))
    register_provider(rt, provider)
    return rt


def _drive(rt, instance_id):
    for _ in range(50):
        outcome = rt.advance_workflow(instance_id)
        if outcome.terminal:
            break
    return rt.instance(instance_id)


def test_end_to_end_success_records_available_usage():
    sink = InMemoryTokenAccountingSink()
    bridge = RuntimeTokenAccountingBridge(sink, normalizer=_normalizer())
    rt = _runtime_with_bridge(UsageProvider("vendor"), bridge)

    inst = rt.prepare_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="vendor")))
    prep = prepare_api_call_measurement(
        minimization_result=sample_minimization_result(),
        logical_request_id="lr-1", provider_id="vendor", model_id="m1",
    )
    bridge.register(prep, instance_id=inst.instance_id, task_id="t")

    inst = _drive(rt, inst.instance_id)
    assert inst.status is WorkflowStatus.COMPLETED
    assert len(sink.records) == 1
    rec = sink.records[0]
    assert rec.status is AttemptStatus.SUCCEEDED
    assert rec.usage_availability is UsageAvailability.AVAILABLE
    assert rec.provider_usage.input_tokens == 2337
    assert rec.provider_usage.output_tokens == 428
    # measurement A is linked from the minimization result
    assert rec.context_tokens_before == prep.context_tokens_before


def test_end_to_end_retries_recorded_as_distinct_records():
    sink = InMemoryTokenAccountingSink()
    bridge = RuntimeTokenAccountingBridge(sink, normalizer=_normalizer())
    # Fails twice (raises, no usage), succeeds on the 3rd with usage; max_attempts=3.
    rt = _runtime_with_bridge(FlakyUsageProvider("vendor", fail_times=2), bridge)

    inst = rt.prepare_workflow(_wf(
        TaskDefinition(task_id="t", operation="op", provider_id="vendor", max_attempts=3)
    ))
    prep = prepare_api_call_measurement(
        minimization_result=sample_minimization_result(),
        logical_request_id="lr-1", provider_id="vendor",
    )
    bridge.register(prep, instance_id=inst.instance_id, task_id="t")
    inst = _drive(rt, inst.instance_id)

    assert inst.status is WorkflowStatus.COMPLETED
    assert len(sink.records) == 3  # three attempts -> three records, not collapsed
    assert [r.attempt_number for r in sink.records] == [1, 2, 3]
    # first two failed with unknown usage; the third succeeded with usage
    assert sink.records[0].usage_availability is not UsageAvailability.AVAILABLE
    assert sink.records[2].usage_availability is UsageAvailability.AVAILABLE

    summary = aggregate_logical_request_usage(sink.records)
    assert summary.attempt_count == 3
    assert summary.attempts_usage_unknown == 2
    assert summary.complete is False  # gaps -> not claimed zero
    # only the successful attempt's usage is summed
    assert summary.provider_input_tokens == 2337


class BlockHook:
    """A minimal governance hook that always BLOCKs (no provider invocation)."""

    def evaluate(self, proposal, evaluation_time):
        from ugence_agent_runtime.governance.interfaces import GovernanceEvaluation

        return GovernanceEvaluation(
            disposition=GovernanceDisposition.BLOCK,
            proposal_fingerprint=proposal.fingerprint,
            reason_codes=("TEST_BLOCK",),
            evaluation_reference="ref",
            correlation_reference=proposal.correlation_id,
        )


def test_governance_block_produces_no_record():
    sink = InMemoryTokenAccountingSink()
    bridge = RuntimeTokenAccountingBridge(sink, normalizer=_normalizer())
    rt = _runtime_with_bridge(UsageProvider("vendor"), bridge, hook=BlockHook())

    inst = rt.prepare_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="vendor")))
    prep = prepare_api_call_measurement(
        minimization_result=sample_minimization_result(),
        logical_request_id="lr-1", provider_id="vendor",
    )
    bridge.register(prep, instance_id=inst.instance_id, task_id="t")
    inst = _drive(rt, inst.instance_id)

    assert inst.status is WorkflowStatus.FAILED
    assert sink.records == ()  # provider never invoked -> no record
    assert bridge.skipped_attempts == 0  # not even an attempt was observed


def test_unregistered_attempt_is_skipped_and_counted():
    sink = InMemoryTokenAccountingSink()
    bridge = RuntimeTokenAccountingBridge(sink, normalizer=_normalizer())
    rt = _runtime_with_bridge(UsageProvider("vendor"), bridge)
    # Deliberately do NOT register a prepared measurement.
    inst = rt.prepare_workflow(_wf(TaskDefinition(task_id="t", operation="op", provider_id="vendor")))
    inst = _drive(rt, inst.instance_id)
    assert inst.status is WorkflowStatus.COMPLETED
    assert sink.records == ()
    assert bridge.skipped_attempts == 1  # the gap is visible, not silently zero
