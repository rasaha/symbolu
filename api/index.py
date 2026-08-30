"""Vercel entrypoint for the Governance Studio (frontend + backend, one ASGI app).

Every request — SPA, assets and API — is routed here by ``vercel.json`` so the
deployment access gate applies to all of them, exactly as it does in the
container. Nothing is served by the CDN ahead of authentication.

TLS is terminated by Vercel, so this process holds no certificate. The
configuration therefore runs in ``platform`` termination mode, which does not
drop the HTTPS requirement but moves its enforcement to a per-request check on
the forwarded protocol. See ``ForwardedProtoGuardMiddleware``.

The local packages are put on ``sys.path`` rather than pip-installed: they are
pure Python, and this avoids editable installs in a serverless build.

Required environment variables (set in the Vercel project, never committed):
    UGENCE_STUDIO_USERNAME        operator username
    UGENCE_STUDIO_PASSWORD_HASH   Argon2id hash from generate_password_hash
    UGENCE_STUDIO_ALLOWED_HOSTS   comma-separated deployment hostnames
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for _rel in (
    "deployment/governance-studio/src",
    "apps/ugence-governance-studio/backend/src",
    "packages/capabilities/agent-workforce-composer/src",
    "packages/tooling/policy-workflow-compiler/src",
):
    _p = os.path.join(_ROOT, _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from governance_studio_deployment.app import build_app  # noqa: E402
from governance_studio_deployment.config import DeploymentConfig  # noqa: E402
from governance_studio_deployment.synthetic import (  # noqa: E402
    SyntheticManifest,
    verify_bundle,
)

FRONTEND_DIR = os.path.join(_ROOT, "apps/ugence-governance-studio/frontend/dist")
SCENARIOS_ROOT = os.path.join(_ROOT, "apps/ugence-governance-studio/demo_data")
MANIFEST = os.path.join(_ROOT, "deployment/governance-studio/synthetic-scenarios-manifest.json")


def _build():
    config = DeploymentConfig.from_env(
        mode="production",
        # Vercel terminates TLS and sets x-forwarded-proto; the guard enforces it.
        tls_termination="platform",
        trusted_proxy=True,
        tls_cert_file="",
        tls_key_file="",
        frontend_dir=FRONTEND_DIR,
        scenarios_root=SCENARIOS_ROOT,
        manifest_path=MANIFEST,
    )
    errors = config.validate()
    if errors:
        # Fail closed and loudly, without echoing any secret value.
        raise RuntimeError("DEPLOYMENT_CONFIG_INVALID: " + "; ".join(errors))

    # Synthetic-data boundary: the same fail-closed check the container performs at
    # startup. A tampered, missing or extra fixture must not be servable.
    drift = verify_bundle(SyntheticManifest.load(MANIFEST), SCENARIOS_ROOT)
    if drift:
        raise RuntimeError("SYNTHETIC_DATA_BOUNDARY_FAILED: " + "; ".join(map(str, drift)))

    return build_app(config)


app = _build()
