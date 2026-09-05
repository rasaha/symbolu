"""A one-instance DBOS + Agent Runtime host, small enough to run from a subprocess.

The crash rows must kill a *real* process, so this harness is invoked as
``python tests/_dbos_harness.py <app_url> <sys_url> <scenario> <instance_id>`` and the
parent process asserts on what PostgreSQL actually kept. A mocked crash would prove
nothing about what was rolled back, which is the only thing those rows are about.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Callable, Dict, Optional

import sqlalchemy as sa

from ugence_agent_runtime.config import AgentRuntimeConfig
from ugence_agent_runtime.governance.interfaces import (
    GovernanceDisposition,
    GovernanceEvaluation,
)
from ugence_agent_runtime.models.task import TaskDefinition
from ugence_agent_runtime.models.workflow import WorkflowDefinition
from ugence_agent_runtime.providers.interfaces import ToolInvocation, ToolResult
from ugence_agent_runtime.providers.registry import ProviderRegistry
from ugence_agent_runtime.runtime.engine import AgentRuntime

from ugence_durable_execution.clock import wall_clock
from ugence_durable_execution.engine.dbos_engine import (
    DbosExecutionAdapter,
    DbosRuntimeHost,
)
from ugence_durable_execution.postgres.bundle import PostgresStoreBundle

WORKFLOW_ID = "wf-matrix"
#: A three-task chain, for the bounded-resume row: one durable step may advance at most
#: one task of it.
WORKFLOW_ID_CHAIN = "wf-matrix-chain"
DEFINITION_DIGEST = "digest-v1"

PROVIDER_CALLS_DDL = """
CREATE TABLE IF NOT EXISTS provider_calls (
    id              bigserial PRIMARY KEY,
    idempotency_key text NOT NULL,
    operation       text NOT NULL
)
"""


class RecordingProvider:
    """Records every invocation, keyed by the runtime's own idempotency key.

    Writes on its OWN connection and commits immediately — deliberately. A provider
    call is an effect *outside* the runtime's transaction, exactly like a real external
    system, so its record must survive a rollback of the runtime's tables. That is what
    makes ADR §8 row 3 (effect happened, durable record did not) observable at all.
    """

    provider_id = "recorder"
    version = "1.0.0"

    def __init__(self, url: str, kill_after: bool = False) -> None:
        self._engine = sa.create_engine(url)
        self._kill_after = kill_after

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        with self._engine.begin() as c:
            c.execute(
                sa.text(
                    "INSERT INTO provider_calls (idempotency_key, operation) "
                    "VALUES (:k, :o)"
                ),
                {"k": invocation.idempotency_key or "", "o": invocation.operation},
            )
        if self._kill_after:
            # The effect has landed and is committed on its own connection; the
            # runtime's transaction has NOT committed. Die exactly here.
            os.kill(os.getpid(), 9)
        return ToolResult(
            provider_id=self.provider_id, operation=invocation.operation, ok=True,
            output={"recorded": True},
        )


class KillBeforeProvider(RecordingProvider):
    """Dies before recording anything — the crash-before-effect case (row 1/2)."""

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        os.kill(os.getpid(), 9)
        raise AssertionError("unreachable")


def build_definition(workflow_id: str = WORKFLOW_ID) -> WorkflowDefinition:
    if workflow_id == WORKFLOW_ID_CHAIN:
        return WorkflowDefinition(
            workflow_id=workflow_id,
            tasks=tuple(
                TaskDefinition(
                    task_id=f"t{i}",
                    operation="do",
                    provider_id="recorder",
                    consequential=True,
                    arguments={"n": i},
                    depends_on=(f"t{i - 1}",) if i > 1 else (),
                )
                for i in (1, 2, 3)
            ),
        )
    return WorkflowDefinition(
        workflow_id=workflow_id,
        tasks=(
            TaskDefinition(
                task_id="t1",
                operation="do",
                provider_id="recorder",
                consequential=True,
                arguments={"n": 1},
            ),
        ),
    )


def make_datasource(app_url: str):
    from dbos import SQLAlchemyDatasource

    return SQLAlchemyDatasource.create(database_url=app_url)


def launch_dbos(app_url: str, sys_url: str, name: str = "ude-matrix"):
    from dbos import DBOS, DBOSConfig

    DBOS(
        config=DBOSConfig(
            name=name,
            system_database_url=sys_url,
            application_database_url=app_url,
            run_admin_server=False,
            enable_otlp=False,
            log_level="CRITICAL",
        )
    )
    return DBOS


def build_host(
    *,
    app_url: str,
    provider: Any,
    hook: Any,
    clock: Callable[[], float] = wall_clock,
    authority_recheck: Optional[Callable] = None,
) -> DbosRuntimeHost:
    registry = ProviderRegistry()
    registry.register(provider)

    def build_engine(bundle: Any, definition_digest: str, instance_id: str) -> AgentRuntime:
        config = AgentRuntimeConfig(
            runtime_id="ude-matrix",
            id_generator=lambda: instance_id,
            governance_hook=hook,
            provider_registry=registry,
            checkpoint_store=bundle.checkpoint_store,
            state_store=bundle.state_store,
            event_store=bundle.event_store,
            clock=clock,
            authority_recheck=authority_recheck,
        )
        return AgentRuntime(config)

    return DbosRuntimeHost(
        build_engine=build_engine,
        definition_for=lambda wid: build_definition(wid),
        clock=clock,
    )


def wire(
    *,
    app_url: str,
    sys_url: str,
    provider: Any,
    hook: Any,
    clock: Callable[[], float] = wall_clock,
    authority_recheck: Optional[Callable] = None,
    worker_id: str = "worker-1",
    definition_digest: str = DEFINITION_DIGEST,
):
    """Full wiring: DBOS launched, schema created, adapter ready."""
    ds = make_datasource(app_url)
    dbos = launch_dbos(app_url, sys_url)
    ds.run_migrations()

    engine = sa.create_engine(app_url)
    with engine.begin() as c:
        c.execute(sa.text(PROVIDER_CALLS_DDL))

    bundle = PostgresStoreBundle(
        ds.sql_session, engine_id="dbos", definition_digest=definition_digest
    )
    host = build_host(
        app_url=app_url, provider=provider, hook=hook,
        clock=clock, authority_recheck=authority_recheck,
    )
    adapter = DbosExecutionAdapter(
        datasource=ds, host=host, bundle=bundle, worker_id=worker_id,
        definition_digest=definition_digest,
    )
    adapter.create_schema(engine)
    dbos.launch()
    return ds, dbos, adapter, bundle


# --------------------------------------------------------------------------- #
# subprocess entry point — used by the crash rows
# --------------------------------------------------------------------------- #
def _main() -> int:
    app_url, sys_url, scenario, instance_id = sys.argv[1:5]

    if scenario == "kill_before_provider":
        provider: Any = KillBeforeProvider(app_url)
    elif scenario == "kill_after_provider":
        provider = RecordingProvider(app_url, kill_after=True)
    else:
        provider = RecordingProvider(app_url)

    # The RecordingHook persists every evaluation, so the parent process can compare
    # what was proposed before a SIGKILL with what is proposed after recovery. An
    # in-memory hook would tell the crash rows nothing.
    import _hooks

    tag = os.environ.get("UDE_PROCESS_TAG", "child")

    # UDE_HOOK selects which governance hook drives the crash rows. The matrix was first
    # proven with the recording test hook; "production" re-runs the same rows against the
    # real GovernedExecutionHook composing through the ratified engine.
    if os.environ.get("UDE_HOOK") == "production":
        import _production

        hook: Any = _production.clearing_hook(app_url)
    else:
        hook = _hooks.RecordingHook(app_url, process_tag=tag)

    ds, dbos, adapter, bundle = wire(
        app_url=app_url, sys_url=sys_url, provider=provider, hook=hook,
    )
    adapter.start(
        workflow_id=WORKFLOW_ID, definition_digest=DEFINITION_DIGEST,
        instance_id=instance_id, correlation_id="corr-1", inputs={},
    )

    if scenario == "prepare_only":
        print("PREPARED")
        return 0

    if scenario == "advance_only":
        outcome = adapter.advance(instance_id=instance_id, attempt_token="outage")
        print(f"OUTCOME progressed={outcome.progressed}")
        return 0

    if scenario == "recover":
        # Agent Runtime restores a recovered instance as PAUSED and never auto-runs it
        # ("recovered as PAUSED, requiring explicit continuation"). So a retry after a
        # crash is deliberately two steps: an explicit resume, then an advance that
        # re-crosses the governance boundary from the beginning.
        first = adapter.advance(instance_id=instance_id, attempt_token="recover-probe")
        print(f"AFTER_RECOVERY progressed={first.progressed} "
              f"awaiting_external={first.awaiting_external} reason={first.stop_reason}")
        adapter.resume(instance_id=instance_id)

    outcome = adapter.advance(instance_id=instance_id, attempt_token="attempt-1")
    print(f"OUTCOME progressed={outcome.progressed} terminal={outcome.terminal}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
