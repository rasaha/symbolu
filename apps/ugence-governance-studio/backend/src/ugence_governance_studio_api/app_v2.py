"""Application factory for the additive ``governance_studio.api.v2`` contract (GAS-4).

**Why this is a separate application.** ``canonical_openapi_bytes()`` regenerates the
v1 document from ``create_app`` and ``test_freeze.py`` asserts it is byte-identical to
the committed ``contracts/openapi.json``. Adding v2 routers to that application would
change those bytes and break the freeze — so v2 is built by its own factory and
serialized to its own document. v1 is not touched, re-versioned or deprecated by v2
existing; the two are generated independently and frozen independently.

``create_combined_app`` mounts both for serving, and is deliberately NOT what either
canonical document is generated from.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI

from .api.v2 import ROUTERS
from .api.v2.deps import V2Context
from .app import (
    MediaTypeMiddleware,
    RequestIdMiddleware,
    _openapi_metadata,
    create_app,
)
from .clients.console import ConsoleClient
from .clients.review import ReviewServiceClient
from .errors import install_error_handlers
from .security.middleware import (
    BodySizeLimitMiddleware,
    RateLimitSeamMiddleware,
    SecurityHeadersMiddleware,
)
from .services.studio_v2 import (
    ClearanceExportService,
    DeploymentStatusService,
    AuthorityService,
    ConstitutionService,
    ObserveService,
    PolicyService,
    PublishService,
    RegistryService,
    DeclarationService,
    VendorDeclarationService,
    WorkflowDraftService,
    ReviewRelayService,
    StartRunService,
    LedgerObserveService,
    SimulateService,
)
from .settings import ApiSettings
from .version import API_V2_CONTRACT_VERSION

__all__ = ["create_v2_app", "create_combined_app", "build_studio_context"]

_V2_TITLE = "Ugence Governed Agent Studio API v2"
_V2_SUMMARY = (
    "Additive Governed Agent Studio surface over the Ugence governance packages. "
    "Thin orchestration only; synthetic and fixture data; planning and observation "
    "only. No route issues, activates, revokes, grants, authorizes, clears or "
    "executes."
)


def build_studio_context(
    *,
    activation_root: Any = None,
    policy_registry: Any = None,
    decision_store: Any = None,
    policy_identities: tuple = (),
    governance_hook: Any = None,
    provider_registry: Any = None,
    hook_is_permissive: bool = False,
    console_base_url: Optional[str] = None,
    review_service_base_url: Optional[str] = None,
    system_registry: Any = None,
    registered_by: str = "",
    system_classification_vocabulary: Any = None,
    data_use_declarations: Any = None,
    recorded_by: str = "",
    data_classification_vocabulary: Any = None,
    data_use_purpose_vocabulary: Any = None,
    vendor_declarations: Any = None,
    vendor_posture_vocabulary: Any = None,
    workflow_drafts: Any = None,
    received_clearances: Any = None,
    deployment_report: Any = None,
) -> V2Context:
    """Wire the six services from whatever this deployment actually has.

    Every dependency is optional and defaults to absent. A service handed nothing
    reports itself unavailable and names the gap; none of them substitutes a stub. That
    is the difference between a screen that says "no trust root is configured" and one
    that shows a green tick over an ephemeral key.

    **The four vocabulary parameters follow the same rule, and have to.** Since the
    record packages took their vocabulary bindings (``VV-A`` to ``VV-E``, authorized by
    ``PUB-2``), a governed label on a new record must name the published vocabulary it
    was written against — and ``PUB-2`` forbids defaulting an absent reference to the
    current one. So a deployment that has not said which taxonomy its administrators
    record against cannot record, and the seam says exactly that rather than stamping a
    vocabulary nobody chose. Each is the *package's own* ``VocabularyBinding``: four
    identical types, because ``VV-A`` put the binding on the record precisely so no new
    neutral type entered ``governance-contracts``.

    The alternative — carrying the vocabulary in each request payload — was not taken:
    the v2 contract is frozen, and a new required request field would break every
    existing client to record a fact that belongs to the deployment rather than to the
    call. Whether an administrator should be able to override it per request is a
    product question, not settled here.
    """
    console = ConsoleClient(console_base_url) if console_base_url else None
    review = ReviewServiceClient(review_service_base_url) if review_service_base_url else None
    return V2Context(
        constitution=ConstitutionService(activation_root=activation_root),
        policy=PolicyService(),
        authority=AuthorityService(
            registry=policy_registry,
            decision_store=decision_store,
            identities=policy_identities,
        ),
        simulate=SimulateService(
            governance_hook=governance_hook,
            provider_registry=provider_registry,
            hook_is_permissive=hook_is_permissive,
        ),
        publish=PublishService(console=console),
        observe=ObserveService(console=console),
        review=ReviewRelayService(review=review),
        registry=RegistryService(
            registry=system_registry, registered_by=registered_by,
            classification_vocabulary=system_classification_vocabulary),
        data_use=DeclarationService(
            declarations=data_use_declarations, recorded_by=recorded_by,
            classification_vocabulary=data_classification_vocabulary,
            purpose_vocabulary=data_use_purpose_vocabulary),
        vendor=VendorDeclarationService(
            declarations=vendor_declarations, recorded_by=recorded_by,
            posture_vocabulary=vendor_posture_vocabulary),
        # Bring Your Workflow phase 3A (authority-plane ADR §24): the tenant-bound
        # drafts file, and the system registry a draft may link to by reference plus
        # digest — the same registry seam 5 handed, never a second one.
        workflow_drafts=WorkflowDraftService(
            drafts=workflow_drafts, recorded_by=recorded_by, registry=system_registry),
        clearance_export=ClearanceExportService(
            source=received_clearances,
            tenant_id=getattr(received_clearances, "tenant_id", "")),
        start_run=StartRunService(review=review),
        ledger_observe=LedgerObserveService(review=review),
        # MA-2 as amended (MS-2): the startup integrity report, handed once. A dict,
        # not a package: no SD-1 entry is involved and no file is read.
        deployment_status=DeploymentStatusService(report=deployment_report),
    )


def create_v2_app(
    settings: Optional[ApiSettings] = None,
    *,
    studio: Optional[V2Context] = None,
) -> FastAPI:
    """The v2 application. Independent of the v1 one, by design."""
    settings = settings or ApiSettings.from_env()

    app = FastAPI(
        title=_V2_TITLE,
        version=API_V2_CONTRACT_VERSION,
        summary=_V2_SUMMARY,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url="/redoc" if settings.enable_docs else None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
        servers=[],  # host-free, exactly as v1
    )
    app.state.settings = settings
    app.state.studio = studio if studio is not None else build_studio_context()

    for router in ROUTERS:
        app.include_router(router)

    install_error_handlers(app)

    app.add_middleware(MediaTypeMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, max_request_bytes=settings.max_request_bytes)
    app.add_middleware(RateLimitSeamMiddleware, enabled=settings.enable_rate_limit)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)

    app.description = (
        f"{_V2_SUMMARY}\n\n"
        f"- API contract: {API_V2_CONTRACT_VERSION}\n"
        f"- Frozen companion contract: governance_studio.api.v1 (unchanged)\n"
        f"- Screens: Registration, Constitution, Policy, Authority, Simulate, Publish, Observe, Review; "
        f"Bring Your Workflow drafts (phase 3A)"
    )
    app.openapi_version = "3.1.0"
    return app


def create_combined_app(
    settings: Optional[ApiSettings] = None,
    *,
    studio: Optional[V2Context] = None,
) -> FastAPI:
    """Serve v1 and v2 together.

    For running the product only. Neither canonical OpenAPI document is generated from
    this application, so mounting cannot perturb either frozen contract.
    """
    settings = settings or ApiSettings.from_env()
    root = create_app(settings)
    v2 = create_v2_app(settings, studio=studio)
    # Mounted at the root, after every v1 route, so the v2 paths keep the spelling the
    # contract and the frontend client use (``/api/v2/...``): a mount under a prefix
    # would serve them at ``/<prefix>/api/v2/...``, which nothing calls. v1 routes are
    # matched first; only what v1 does not serve reaches v2.
    root.mount("/", v2)
    return root
