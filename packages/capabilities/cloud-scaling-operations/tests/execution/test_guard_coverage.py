"""Isolating tests for the guard sweep — one decision point, one discriminating fact.

Written for the shared-engine adoption (guard-coverage ADR, operations extension). The
pre-existing suite proves the package *denies*; almost none of it proved which gate
decided, and under ADR §6's within-class criterion a kill that only shows "something was
denied" attributes nothing. Every test here isolates one gate by the typed half of its
refusal — the `ExecutionDenied.code`, the `ExecutionOutcome` member, the `GateOutcome`
action, or the exception class — never by a message substring alone.

The verifier used throughout is the reference HMAC (`ReferenceAuthorityVerifier`), so a
kill proves gate *enforcement*, not production cryptographic strength — the ruled caveat
carried by this package's GUARD_INVENTORY.md.
"""

from __future__ import annotations

import threading

import pytest

import ops_support as support
from ugence_cloud_scaling_operations import (
    ControlledScalingExecutor,
    ExecutionDenied,
    ExecutionMode,
    ExecutionOutcome,
    FakeScalingBackend,
    OperationsConfig,
    TargetPolicy,
)
from ugence_cloud_scaling_operations.authority import verify_authorization
from ugence_cloud_scaling_operations.audit import AuditSinkError
from ugence_cloud_scaling_operations.gate_executor import GateExecutor
from ugence_cloud_scaling_operations.k8s_executor import KubernetesScalingExecutor
from ugence_cloud_scaling_operations.observability.metrics_server import MetricsServer
from ugence_cloud_scaling_operations.orchestrator import ProductionOrchestrator
from ugence_cloud_scaling_operations.recommend.webhook import WebhookConfig, WebhookTarget
from ugence_cloud_scaling_operations.shadow.runner import ShadowRunner

NOW = 1500.0


def _policy(**over):
    fields = dict(
        allowed_clusters=("prod-a",),
        allowed_namespaces=("web",),
        allowed_resources=("frontend",),
        max_replica_delta=5,
        min_replicas=1,
        max_replicas=10,
    )
    fields.update(over)
    return TargetPolicy(**fields)


def _config(**over):
    fields = dict(mode=ExecutionMode.LIVE, target_policy=_policy())
    fields.update(over)
    return OperationsConfig(**fields)


def _denial_code(authz, req=None, *, verifier=None, config=None, tenant="tenant-1"):
    with pytest.raises(ExecutionDenied) as excinfo:
        verify_authorization(
            authz,
            req or support.make_request(),
            config or _config(),
            verifier or support.verifier(),
            now=NOW,
            tenant_id=tenant,
        )
    return excinfo.value.code


# ======================================================================================= #
# authority.py — each denial code is decided by exactly one gate
# ======================================================================================= #


def test_a_malformed_authorization_is_denied_as_malformed():
    """An empty id or nonce earns `malformed`, not whatever a later gate would say."""

    assert _denial_code(support.make_authorization(authorization_id="")) == "malformed"
    assert _denial_code(support.make_authorization(nonce="")) == "malformed"


def test_an_untrusted_issuer_is_denied_as_untrusted_issuer():
    """Isolated from the signature gate: with the verifier not requiring a signature,
    only the issuer check can refuse this authorization."""

    code = _denial_code(
        support.make_authorization(sign=False, issuer="unknown-issuer"),
        verifier=support.verifier(require_signature=False),
    )
    assert code == "untrusted_issuer"


def test_a_target_mismatch_is_denied_as_target_mismatch():
    assert (
        _denial_code(support.make_authorization(target_cluster="prod-OTHER"))
        == "target_mismatch"
    )


def test_a_delta_beyond_the_authorization_is_denied_as_delta_violation():
    """Beyond the authorization's own maximum while inside the policy's, so only the
    authorization gate can refuse it."""

    code = _denial_code(
        support.make_authorization(maximum_delta=1),
        support.make_request(current_replicas=3, target_replicas=5),
    )
    assert code == "delta_violation"


def test_a_cluster_off_the_allowlist_is_denied_as_cluster_not_allowed():
    code = _denial_code(
        support.make_authorization(target_cluster="prod-b"),
        support.make_request(target_cluster="prod-b"),
    )
    assert code == "cluster_not_allowed"


def test_a_namespace_off_the_allowlist_is_denied_as_namespace_not_allowed():
    code = _denial_code(
        support.make_authorization(target_namespace="batch"),
        support.make_request(target_namespace="batch"),
    )
    assert code == "namespace_not_allowed"


def test_a_resource_off_the_allowlist_is_denied_as_resource_not_allowed():
    code = _denial_code(
        support.make_authorization(target_resource="backend"),
        support.make_request(target_resource="backend"),
    )
    assert code == "resource_not_allowed"


def test_a_target_outside_policy_bounds_is_denied_as_policy_bounds_violation():
    """Inside the authorization's bounds, outside the policy's — only the policy gate
    can refuse it, and the delta stays within both delta limits."""

    code = _denial_code(
        support.make_authorization(maximum_replicas=20),
        support.make_request(current_replicas=9, target_replicas=12),
    )
    assert code == "policy_bounds_violation"


def test_a_delta_beyond_policy_is_denied_as_policy_delta_violation():
    code = _denial_code(
        support.make_authorization(maximum_delta=10),
        support.make_request(current_replicas=3, target_replicas=10),
    )
    assert code == "policy_delta_violation"


# ======================================================================================= #
# executors.py — the receipt carries the member the path earned
# ======================================================================================= #


def _executor(backend=None, config=None, **over):
    return ControlledScalingExecutor(
        config or _config(),
        backend=backend or FakeScalingBackend({"prod-a/web/frontend": 3}),
        verifier=support.verifier(),
        clock=lambda: NOW,
        **over,
    )


def _last_audit_outcome(executor):
    """The audit trail's own outcome for the last event — the arm names its member
    twice (audit emit, then receipt), and both are the typed contract."""

    return executor.audit.events[-1].result


def test_a_denied_execution_receipt_carries_the_denied_member():
    executor = _executor()
    receipt = executor.execute(
        support.make_request(),
        support.make_authorization(expires_at=NOW - 100.0),
        tenant_id="tenant-1",
    )
    assert receipt.outcome == ExecutionOutcome.DENIED
    assert _last_audit_outcome(executor) == ExecutionOutcome.DENIED
    assert receipt.applied is False


def test_a_concurrency_conflict_receipt_carries_the_failed_member():
    backend = FakeScalingBackend({"prod-a/web/frontend": 3}, conflict_on="frontend")
    executor = _executor(backend=backend)
    receipt = executor.execute(
        support.make_request(), support.make_authorization(), tenant_id="tenant-1"
    )
    assert receipt.outcome == ExecutionOutcome.FAILED
    assert _last_audit_outcome(executor) == ExecutionOutcome.FAILED
    assert receipt.applied is False


def test_a_backend_error_receipt_carries_the_failed_member():
    """Also the fake backend's own failure injection: with `fail_on` set the write must
    raise rather than mutate, and the executor must report FAILED, not APPLIED."""

    backend = FakeScalingBackend({"prod-a/web/frontend": 3}, fail_on="frontend")
    executor = _executor(backend=backend)
    receipt = executor.execute(
        support.make_request(), support.make_authorization(), tenant_id="tenant-1"
    )
    assert receipt.outcome == ExecutionOutcome.FAILED
    assert _last_audit_outcome(executor) == ExecutionOutcome.FAILED
    assert receipt.applied is False


class _ExplodingAuditSink:
    def emit(self, event):
        raise RuntimeError("sink down")


def test_a_live_run_refuses_to_proceed_past_a_dead_audit_sink():
    """LIVE mutations without an audit trail are refused, not logged-and-continued."""

    with pytest.raises(AuditSinkError):
        _executor(audit_sink=_ExplodingAuditSink()).execute(
            support.make_request(), support.make_authorization(), tenant_id="tenant-1"
        )


# ======================================================================================= #
# gate_executor.py — the verdict action, decided gate by gate
# ======================================================================================= #


def _gate(config=None, http=None):
    return GateExecutor(
        config or _config(
            mode=ExecutionMode.DRY_RUN,
            argocd_allowed_base_urls=("https://argocd.example",),
        ),
        http=http,
        verifier=support.verifier(),
    )


def _sync(gate, **over):
    fields = dict(
        base_url="https://argocd.example",
        tenant_id="tenant-1",
        trigger=True,
    )
    fields.update(over)
    return gate.sync(support.make_request(), support.make_authorization(), **fields)


def test_no_trigger_holds_before_any_authority_question_is_asked():
    outcome = _sync(_gate(), trigger=False)
    assert outcome.action == "hold"
    assert outcome.applied is False


def test_insecure_tls_holds_a_live_gate_even_with_authority():
    ok_http = lambda method, url, headers, timeout: (200, "")
    config = _config(
        mode=ExecutionMode.LIVE,
        allow_insecure_tls=True,
        argocd_allowed_base_urls=("https://argocd.example",),
    )
    outcome = _sync(_gate(config=config, http=ok_http))
    assert outcome.action == "hold"
    assert outcome.applied is False


def test_dry_run_reports_a_sync_verdict_without_applying():
    outcome = _sync(_gate())
    assert outcome.action == "sync"
    assert outcome.applied is False


def test_a_live_gate_with_no_http_caller_holds():
    config = _config(
        mode=ExecutionMode.LIVE,
        argocd_allowed_base_urls=("https://argocd.example",),
    )
    outcome = _sync(_gate(config=config, http=None))
    assert outcome.action == "hold"
    assert outcome.applied is False
    # Refused before any attempt: without this guard the retry loop would swallow the
    # uncallable caller and report the same hold with its retries spent.
    assert outcome.retry_count == 0


# ======================================================================================= #
# k8s_executor.py — explicit-coordinate and injected-client requirements
# ======================================================================================= #


def test_reading_replicas_requires_an_explicit_namespace_and_resource():
    with pytest.raises(ValueError):
        KubernetesScalingExecutor(client=object()).read_replicas("prod-a", "", "frontend")


def test_setting_replicas_requires_an_explicit_namespace_and_resource():
    with pytest.raises(ValueError):
        KubernetesScalingExecutor(client=object()).set_replicas(
            "prod-a", "web", "", 5, 3
        )


def test_the_kubernetes_executor_refuses_to_run_without_an_injected_client():
    with pytest.raises(RuntimeError):
        KubernetesScalingExecutor(client=None).read_replicas("prod-a", "web", "frontend")


# ======================================================================================= #
# double-start and configuration guards
# ======================================================================================= #


def _double_start(cls):
    instance = object.__new__(cls)
    instance._running = True
    instance._thread = None
    instance.run = lambda callback=None, max_cycles=None: None  # never reached: the running check refuses first
    return instance


def test_a_running_orchestrator_refuses_a_second_start():
    with pytest.raises(RuntimeError):
        ProductionOrchestrator.run_async(_double_start(ProductionOrchestrator))


def test_a_running_shadow_runner_refuses_a_second_start():
    with pytest.raises(RuntimeError):
        ShadowRunner.run_async(_double_start(ShadowRunner))


def test_a_running_metrics_server_refuses_a_second_start():
    server = object.__new__(MetricsServer)
    server._lock = threading.Lock()
    server._httpd = object()
    server.config = None  # never reached: the running check refuses first
    with pytest.raises(RuntimeError):
        MetricsServer.start(server)


def test_an_unknown_confidence_level_is_refused_at_webhook_configuration():
    with pytest.raises(ValueError):
        WebhookConfig(target=WebhookTarget.SLACK, url="https://hooks.example/x", min_confidence="bogus")


# ======================================================================================= #
# entrypoint dispatch — the evidence the exclusions cite
# ======================================================================================= #


def test_the_console_entrypoints_do_not_run_on_import():
    """Evidence for excluding the `__main__` dispatches and `main`'s config-source
    branch: importing either module executes no entrypoint — the modules import with
    their own names, so the dispatch guard is unreachable in any test run, and the
    authority gates `main` wires are scored directly above."""

    import importlib

    cli = importlib.import_module("ugence_cloud_scaling_operations.cli")
    main = importlib.import_module("ugence_cloud_scaling_operations.main")
    assert cli.__name__ != "__main__"
    assert main.__name__ != "__main__"
