"""Ugence Model Egress Custody (GCP) — the production-form Secret Manager adapter.

    THIS DISTRIBUTION HOLDS NO CREDENTIAL AND NO PROVIDER KEY, AND MAKES NO MODEL
    VENDOR CALL. It reads one pinned Google Secret Manager version through an injected
    client, and the only place the real Google client is constructed is
    :func:`build_google_secret_manager_client`, called from the deployment composition
    root. Importing this package imports no Google SDK and opens no connection.

Dependency direction (one-way):

    ugence-model-egress-unit
        ▲
    ugence-model-egress-custody-gcp (this package)
        ▲
    deployment/meu-validation-job (the composition root that builds the real client)

The unit never imports this package, which is how it keeps its "no Google SDK, no
socket-capable import" boundary while a commissioned deployment still gets a real one.
"""

from __future__ import annotations

from .adapter import ProductionFormSecretManagerCustodyAdapter
from .client import (
    AccessedSecretVersion,
    GoogleClientUnavailable,
    SecretManagerClient,
    build_google_secret_manager_client,
)
from .config import FORBIDDEN_CONFIG_KEYS, ConfigRefused, CustodyConfig, refuse_credential_material
from .designation import (
    AcceptedDesignation,
    DesignationRefused,
    check_designation_accepted,
    designation_attestation_refusal,
    designation_completeness_refusal,
)
from .errors import SANITIZED_UNKNOWN, sanitize_exception_type
from .identity import (
    PRODUCTION_FORM_IDENTITY_SOURCES,
    RUNTIME_IDENTITY_SOURCES,
    IdentityRefused,
    RuntimeIdentityAssertion,
    check_production_identity,
)
from .resource import ResourceRefused, SecretVersionResource, parse_secret_version
from .version import (
    LIVE_VENDOR_EGRESS,
    MATURITY,
    PERMITTED_SECRET_MANAGER_METHOD,
    PRODUCTION_FORM_ADAPTER_NAME,
    __version__,
)

__all__ = [
    "__version__",
    "MATURITY",
    "LIVE_VENDOR_EGRESS",
    "PRODUCTION_FORM_ADAPTER_NAME",
    "PERMITTED_SECRET_MANAGER_METHOD",
    "ProductionFormSecretManagerCustodyAdapter",
    "AccessedSecretVersion",
    "SecretManagerClient",
    "GoogleClientUnavailable",
    "build_google_secret_manager_client",
    "CustodyConfig",
    "ConfigRefused",
    "FORBIDDEN_CONFIG_KEYS",
    "refuse_credential_material",
    "AcceptedDesignation",
    "DesignationRefused",
    "check_designation_accepted",
    "designation_completeness_refusal",
    "designation_attestation_refusal",
    "RuntimeIdentityAssertion",
    "IdentityRefused",
    "check_production_identity",
    "RUNTIME_IDENTITY_SOURCES",
    "PRODUCTION_FORM_IDENTITY_SOURCES",
    "SecretVersionResource",
    "ResourceRefused",
    "parse_secret_version",
    "SANITIZED_UNKNOWN",
    "sanitize_exception_type",
]
