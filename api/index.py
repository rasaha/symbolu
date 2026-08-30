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

# Model and agent SDKs the P3E boundary forbids. Kept in step with
# deployment/governance-studio/tests/test_egress.py::BANNED_SDKS, which asserts none
# is *imported* at runtime. That check cannot see a package that is merely installed,
# and the repository-root requirements.txt declares two of these, so if the platform
# installs the wrong requirements file the SDKs would sit in the bundle and the SBOM
# one import away while the runtime test stayed green. This guard closes that gap by
# refusing to build at all when one is present.
BANNED_MODEL_SDKS = ["openai", "anthropic", "google.generativeai", "cohere",
                     "boto3", "litellm", "mistralai", "vertexai"]


def assert_no_model_sdk_installed(banned=None):
    """Fail closed if a forbidden SDK is importable in this environment.

    Uses find_spec rather than import: presence is the violation, and executing a
    third-party module to detect it would defeat the point.
    """
    import importlib.util

    found = []
    for name in (banned if banned is not None else BANNED_MODEL_SDKS):
        top = name.split(".")[0]
        try:
            if importlib.util.find_spec(top) is not None:
                found.append(name)
        except (ImportError, ValueError):
            continue
    if found:
        raise RuntimeError(
            "MODEL_SDK_BOUNDARY_FAILED: forbidden SDK(s) present in the deployment "
            f"environment: {sorted(set(found))}. The Governance Studio deployment must "
            "not carry model or agent SDKs. The most likely cause is the platform "
            "installing the repository-root requirements.txt instead of "
            "api/requirements.txt; diagnose the build log rather than suppressing this."
        )


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
    # Before anything else: the deployment must not carry model or agent SDKs.
    assert_no_model_sdk_installed()

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
