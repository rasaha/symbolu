"""The composition root (ADR §3): one process, every seam wired explicitly.

    THIS ROOT WIRES. IT DECIDES NOTHING. Every refusal below happens before a socket
    opens or a database is touched, and every refusal names the rule it applies.

``preflight`` applies rulings CR-3 and CR-4 without connecting to anything:
in production mode an identity port is mandatory, a fixture identity or eligibility
adapter is refused, an in-memory store or a non-authoritative bundle is refused, a
public bind or a plain-HTTP listener is refused. ``compose`` then opens the stores,
launches DBOS, builds the runtime host over the governed hook and the approval-bound
source, and hands the review service its four seams plus the linkage appender and the
identity port. The result carries no secret but the two DSNs already inside the
datasource, and renders none.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Protocol, runtime_checkable

import sqlalchemy as sa

from ugence_agent_runtime.config import AgentRuntimeConfig
from ugence_agent_runtime.providers.registry import ProviderRegistry
from ugence_agent_runtime.runtime.engine import AgentRuntime
from ugence_agent_runtime_governance import GovernedExecutionHook
from ugence_approval_workflow import SqliteApprovalWorkflowStore, StaticApproverEligibility
from ugence_approver_identity_jwt import AdapterConfig, JwtApproverIdentityAdapter
from ugence_authority_directory import DirectoryApproverEligibility, SqliteAuthorityDirectory
from ugence_control_plane_root import STORE_REF, AuditLedger
from ugence_durable_execution import wall_clock
from ugence_durable_execution.engine.dbos_engine import DbosExecutionAdapter, DbosRuntimeHost
from ugence_durable_execution.postgres.bundle import PostgresStoreBundle
from ugence_governed_review import ApprovalBoundInputSource, build_review_ledger
from ugence_governed_review_service import (
    DbosRunReader,
    LedgerLinkageIndex,
    LinkageAppender,
    ReviewService,
    TenantMode,
    build_app,
)

from .config import WorkerConfig, WorkerConfigError
from .version import DEPLOYMENT_NAME, MATURITY
from .workload import Workload

__all__ = [
    "PostureRefused",
    "WorkerClock",
    "WallClock",
    "Worker",
    "STORE_FILES",
    "preflight",
    "build_identity_port",
    "compose",
]

#: The three SQLite stores, by file name under ``data_dir`` (ADR §3).
STORE_FILES = {
    "directory": "authority-directory.sqlite3",
    "approvals": "approvals.sqlite3",
    "audit": "audit-ledger.sqlite3",
}


class PostureRefused(Exception):
    """A composition input the production posture forbids (CR-3, CR-4)."""

    code = "WORKER_POSTURE_REFUSED"


@runtime_checkable
class WorkerClock(Protocol):
    """One clock for the whole process: the durable engine takes ``epoch``, every
    store and the service take ``datetime``. Both must agree."""

    def epoch(self) -> float: ...

    def datetime(self) -> datetime: ...


class WallClock:
    """The durable-execution package's wall clock, read once per call, in both shapes."""

    def epoch(self) -> float:
        return wall_clock()

    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.epoch(), tz=timezone.utc)


@dataclass
class Worker:
    """Everything ``compose`` wired, so a test or a server can reach each seam."""

    config: WorkerConfig
    service: ReviewService
    app: Any
    adapter: DbosExecutionAdapter
    reader: DbosRunReader
    ledger: SqliteApprovalWorkflowStore
    directory: SqliteAuthorityDirectory
    audit: AuditLedger
    datasource: Any
    bundle: Any
    identity_port: Optional[Any]
    workload: Any
    maturity: str = MATURITY
    _closers: list = field(default_factory=list, repr=False)

    def close(self) -> None:
        for closer in reversed(self._closers):
            try:
                closer()
            except Exception:  # noqa: BLE001 - shutdown is best effort, in order
                pass
        self._closers.clear()


def _is_fixture(obj: Any) -> bool:
    return bool(getattr(obj, "NON_PRODUCTION", False)) \
        or str(getattr(obj, "maturity", "")).upper() == "FIXTURE_ONLY"


def preflight(config: WorkerConfig, *, identity_port: Any = None, eligibility: Any = None,
              bundle: Any = None) -> None:
    """Refuse, before any connection, everything the posture forbids.

    Raises ``WorkerConfigError`` for an invalid configuration and ``PostureRefused``
    for a composition input production must not accept. In test mode every input is
    accepted and the mode is named on the worker.
    """

    errors = config.validate()
    if errors:
        raise WorkerConfigError("; ".join(errors))
    if not config.is_production:
        return
    if identity_port is None and not config.identity_configured:
        raise PostureRefused("an identity port is mandatory in production (CR-3)")
    if identity_port is not None and _is_fixture(identity_port):
        raise PostureRefused("a fixture identity adapter is refused in production (CR-4)")
    if eligibility is not None and (isinstance(eligibility, StaticApproverEligibility)
                                    or _is_fixture(eligibility)):
        raise PostureRefused("a fixture eligibility adapter is refused in production (CR-4); "
                             "eligibility comes from the authority directory")
    if bundle is not None and not getattr(bundle, "is_production_authoritative", False):
        raise PostureRefused("a non-authoritative store bundle is refused in production (CR-4)")


def build_identity_port(config: WorkerConfig, clock: WorkerClock) -> Optional[JwtApproverIdentityAdapter]:
    """The AI-C adapter from configuration, or None when no issuer is configured
    (test mode only; production has already refused that in ``preflight``)."""

    if not config.identity_configured:
        return None
    adapter_config = AdapterConfig(
        issuer=config.identity_issuer, audience=config.identity_audience,
        jwks_url=config.identity_jwks_url,
        tenant_claim=config.identity_tenant_claim or None,
        actor_type_claim=config.identity_actor_type_claim or None,
        human_actor_type_value=config.identity_human_actor_value or None,
        production=config.is_production,
    )
    return JwtApproverIdentityAdapter(adapter_config, clock=clock.datetime)


def compose(config: WorkerConfig, *, clock: WorkerClock, workload: Workload,
            identity_port: Any = None, eligibility: Any = None, bundle: Any = None,
            dbos_name: str = DEPLOYMENT_NAME) -> Worker:
    """Wire the worker. Order: refusals, stores, engine, hook and host, adapter,
    reader and appender, identity, service, app."""

    preflight(config, identity_port=identity_port, eligibility=eligibility, bundle=bundle)
    if not isinstance(clock, WorkerClock):
        raise WorkerConfigError("clock must provide epoch() and datetime()")
    if not isinstance(workload, Workload):
        raise WorkerConfigError("workload must provide definition_for, providers and upstream_source")
    production = config.is_production
    closers: list = []

    # -- the three SQLite stores on the durable volume ---------------------------------
    paths = {k: os.path.join(config.data_dir, v) for k, v in STORE_FILES.items()}
    directory = SqliteAuthorityDirectory(paths["directory"], production_mode=production)
    closers.append(directory.close)
    if eligibility is None:
        ledger = build_review_ledger(paths["approvals"], directory, production_mode=production)
        listing = DirectoryApproverEligibility(directory)
    else:
        # Test mode only (preflight refused it in production): a caller-supplied port.
        ledger = SqliteApprovalWorkflowStore(paths["approvals"], eligibility,
                                             production_mode=production)
        listing = eligibility
    closers.append(ledger.close)
    audit = AuditLedger(paths["audit"])
    index = LedgerLinkageIndex(paths["audit"], store_ref=STORE_REF)

    # -- the durable engine -------------------------------------------------------------
    from dbos import DBOS, DBOSConfig, SQLAlchemyDatasource

    datasource = SQLAlchemyDatasource.create(database_url=config.app_database_url)
    DBOS(config=DBOSConfig(
        name=dbos_name, system_database_url=config.system_database_url,
        application_database_url=config.app_database_url,
        run_admin_server=False, enable_otlp=False, log_level="CRITICAL",
    ))
    closers.append(DBOS.destroy)
    datasource.run_migrations()
    bundle = bundle or PostgresStoreBundle(datasource.sql_session, engine_id=DEPLOYMENT_NAME,
                                           definition_digest=config.definition_digest)

    # -- the governed hook over the approval-bound source ----------------------------------
    source = ApprovalBoundInputSource(
        upstream=workload.upstream_source(clock.datetime), ledger=ledger,
        tenant_id=config.tenant_id, required_role=config.required_role,
        clock=clock.datetime, requester_ref=config.requester_ref,
    )
    hook = GovernedExecutionHook(source=source, source_version=DEPLOYMENT_NAME)

    registry = ProviderRegistry()
    for provider in workload.providers():
        registry.register(provider)

    def build_engine(store_bundle: Any, definition_digest: str, instance_id: str) -> AgentRuntime:
        return AgentRuntime(AgentRuntimeConfig(
            runtime_id=config.worker_id, id_generator=lambda: instance_id,
            governance_hook=hook, provider_registry=registry,
            checkpoint_store=store_bundle.checkpoint_store, state_store=store_bundle.state_store,
            event_store=store_bundle.event_store, clock=clock.epoch,
        ))

    host = DbosRuntimeHost(build_engine=build_engine, definition_for=workload.definition_for,
                           clock=clock.epoch)
    adapter = DbosExecutionAdapter(
        datasource=datasource, host=host, bundle=bundle, worker_id=config.worker_id,
        definition_digest=config.definition_digest, production_mode=production,
    )
    engine = sa.create_engine(config.app_database_url)
    try:
        adapter.create_schema(engine)
    finally:
        engine.dispose()
    DBOS.launch()

    # -- the review service's seams -----------------------------------------------------
    reader = DbosRunReader(datasource=datasource, bundle=bundle)
    appender = LinkageAppender(ledger=audit, index=index, reader=reader, approvals=ledger,
                               tenant_id=config.tenant_id, recorded_by=DEPLOYMENT_NAME)
    port = identity_port if identity_port is not None else build_identity_port(config, clock)
    service = ReviewService(
        ledger=ledger, adapter=adapter, reader=reader, tenant_id=config.tenant_id,
        clock=clock.datetime, eligibility=listing, linkage_appender=appender,
        identity_port=port, tenant_mode=TenantMode.SINGLE_TENANT, production=production,
    )
    return Worker(config=config, service=service, app=build_app(service), adapter=adapter,
                  reader=reader, ledger=ledger, directory=directory, audit=audit,
                  datasource=datasource, bundle=bundle, identity_port=port, workload=workload,
                  _closers=closers)
