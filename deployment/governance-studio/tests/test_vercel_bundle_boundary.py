"""The serverless bundle must not carry model or agent SDKs.

`test_egress.py` asserts no banned SDK is *imported* at runtime. It cannot see a
package that is merely installed — and the repository-root `requirements.txt`
declares two of them (`anthropic`, `google-generativeai`). If the platform builds
the function from that file instead of `api/requirements.txt`, those SDKs would
sit in the bundle and the SBOM, one import away, while the runtime test stayed
green.

These tests close that gap: the declared dependency set must name none of them,
and the entrypoint must refuse to build when one is present.

Nothing here deploys, and no P3E-CTR gate is executed or marked passed.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

import pytest

from depaths import REPO

API_DIR = os.path.join(REPO, "api")
REQUIREMENTS = os.path.join(API_DIR, "requirements.txt")
VERCELIGNORE = os.path.join(REPO, ".vercelignore")


@pytest.fixture(scope="module")
def entrypoint():
    """Load api/index.py without executing its module-level app build."""
    src = open(os.path.join(API_DIR, "index.py"), encoding="utf-8").read()
    src = src.replace("\napp = _build()\n", "\n")
    module = {"__name__": "vercel_entrypoint_under_test", "__file__": os.path.join(API_DIR, "index.py")}
    exec(compile(src, "api/index.py", "exec"), module)
    return module


@pytest.fixture(scope="module")
def banned_from_egress_suite():
    """The list the runtime egress test enforces, read from that test itself."""
    from test_egress import BANNED_SDKS

    return list(BANNED_SDKS)


def test_declared_dependencies_name_no_model_sdk():
    """api/requirements.txt is the manifest the function should be built from."""
    declared = [ln.split("#")[0].strip().lower()
                for ln in open(REQUIREMENTS, encoding="utf-8") if ln.split("#")[0].strip()]
    for banned in ("openai", "anthropic", "google-generativeai", "cohere",
                   "boto3", "litellm", "mistralai", "vertexai"):
        assert not any(d.startswith(banned) for d in declared), banned


def test_root_requirements_still_declares_the_sdks_this_guard_exists_for():
    """If this ever stops being true the guard is still correct, but the risk it
    was written for is gone — and the reader deserves to know which."""
    root = open(os.path.join(REPO, "requirements.txt"), encoding="utf-8").read().lower()
    assert "anthropic" in root and "google-generativeai" in root, (
        "the repository-root requirements no longer declares model SDKs; revisit "
        "the rationale recorded in api/index.py")


def test_entrypoint_guard_covers_every_sdk_the_egress_suite_bans(entrypoint,
                                                                 banned_from_egress_suite):
    """The two lists must not drift apart."""
    assert set(banned_from_egress_suite) <= set(entrypoint["BANNED_MODEL_SDKS"])


def test_guard_passes_when_no_sdk_is_present(entrypoint):
    assert entrypoint["assert_no_model_sdk_installed"]() is None


def test_guard_refuses_to_build_when_an_sdk_is_present(entrypoint, tmp_path):
    """Plant a module named like a banned SDK and require a fail-closed refusal."""
    (tmp_path / "anthropic").mkdir()
    (tmp_path / "anthropic" / "__init__.py").write_text("raise AssertionError('must not import')")
    sys.path.insert(0, str(tmp_path))
    importlib.invalidate_caches()
    try:
        with pytest.raises(RuntimeError) as excinfo:
            entrypoint["assert_no_model_sdk_installed"]()
        assert "MODEL_SDK_BOUNDARY_FAILED" in str(excinfo.value)
        assert "anthropic" in str(excinfo.value)
        # detection must not execute the module
        assert "anthropic" not in sys.modules
    finally:
        sys.path.remove(str(tmp_path))
        importlib.invalidate_caches()


def test_build_context_allowlist_keeps_what_the_function_needs_and_drops_the_rest(tmp_path):
    """.vercelignore is an allowlist; verify it with real gitignore matching."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(open(VERCELIGNORE, encoding="utf-8").read())

    keep = ["vercel.json", "api/index.py", "api/requirements.txt", "requirements.txt",
            "apps/ugence-governance-studio/frontend/package.json",
            "apps/ugence-governance-studio/demo_data/procurement/scenario_manifest.json",
            "apps/ugence-governance-studio/contracts/openapi.json",
            "apps/ugence-governance-studio/backend/src/ugence_governance_studio_api/app.py",
            "deployment/governance-studio/src/governance_studio_deployment/app.py",
            "deployment/governance-studio/synthetic-scenarios-manifest.json",
            "packages/capabilities/agent-workforce-composer/src/x.py",
            "packages/tooling/policy-workflow-compiler/src/x.py"]
    drop = ["experiments/a.py", "Project_documentation/b.md", "symbolu/c.py",
            "agentic/d.py", "docs/e.md", "tests/f.py", "train.py", "coverage.json",
            "apps/ugence-governance-studio/frontend/node_modules/x/y.js",
            "api/__pycache__/index.cpython-311.pyc"]

    def ignored(path):
        return subprocess.run(["git", "-C", str(tmp_path), "check-ignore", "-q",
                               "--no-index", path]).returncode == 0

    for p in keep:
        assert not ignored(p), f"required by the function but excluded: {p}"
    for p in drop:
        assert ignored(p), f"not needed but would be uploaded: {p}"


def test_root_requirements_stays_in_the_build_context():
    """Deliberate: excluding it would settle the dependency question by omission.

    It must remain visible so the preview build log shows which requirements file
    the platform actually selects, per the owner's stop-and-diagnose rule.
    """
    text = open(VERCELIGNORE, encoding="utf-8").read()
    assert "!requirements.txt" in text
    prose = " ".join(ln.lstrip("#").strip() for ln in text.splitlines()
                     if ln.startswith("#"))
    assert "would silently decide the dependency question by omission" in prose
