"""Static advisory-boundary gates over the packaged source.

Proves — by parsing every packaged module — that the steering core contains no provider
execution: no provider SDK imports, no network client imports, no socket/subprocess use,
no environment-credential discovery, and no live client instantiation.
"""

from __future__ import annotations

import ast
import os
import re

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src",
                                    "ugence_llm_steering_controller"))

# Provider SDKs / network libraries / execution infrastructure that must never be imported.
FORBIDDEN_IMPORTS = {
    "openai", "anthropic", "boto3", "botocore", "google", "vertexai", "cohere",
    "mistralai", "requests", "httpx", "urllib3", "aiohttp", "socket", "http",
    "urllib", "subprocess", "asyncio", "threading", "multiprocessing", "ssl",
    # Sibling Ugence packages that would break the leaf boundary.
    "governance_studio", "decision_governance", "actiongate", "agent_runtime",
    "hybrid_llm", "ai_hiring", "control_plane", "model_selection_pilot",
    "model_selection_experiment",
}

# Credential / network *usage* patterns that must not appear in source text.
# (Bare credential tokens like "api_key" are intentionally NOT scanned here: registry.py
# legitimately contains them as the secret-key patterns it fails closed on. Credential
# prohibition is proven by the absence of environment access below plus the registry
# secret-rejection tests.)
FORBIDDEN_TEXT = [
    r"os\.environ", r"os\.getenv", r"getenv\(",
    r"\.connect\(", r"\.bind\(", r"socket\.socket", r"subprocess\.", r"Popen",
    r"requests\.(get|post|put|request|Session)", r"httpx\.", r"http\.client",
    r"boto3", r"openai\.", r"anthropic\.",
]


def _py_files():
    for root, _dirs, files in os.walk(_SRC):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


def test_no_forbidden_imports_anywhere():
    violations = []
    for path in _py_files():
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module.split(".")[0]]
            for m in mods:
                if m in FORBIDDEN_IMPORTS:
                    violations.append(f"{os.path.basename(path)}: import {m}")
    assert not violations, violations


def test_no_credential_or_network_text_in_source():
    violations = []
    patterns = [re.compile(p) for p in FORBIDDEN_TEXT]
    for path in _py_files():
        text = open(path, encoding="utf-8").read()
        for pat in patterns:
            if pat.search(text):
                violations.append(f"{os.path.basename(path)}: matches /{pat.pattern}/")
    assert not violations, violations


def test_authority_manifest_is_advisory_none():
    import json
    manifest = json.load(open(os.path.join(_SRC, "..", "..", "module_manifest.json"), encoding="utf-8"))
    assert manifest["authority_class"] == "ADVISORY"
    assert manifest["execution_capability"] == "NONE"
    assert manifest["provider_invocation_capability"] == "NONE"
    assert manifest["credential_access"] == "NONE"
    assert manifest["routing_decision_is_authority"] is False
    assert manifest["live_provider_calls_enabled_by_default"] is False


def test_cli_advises_recommendation_only():
    text = open(os.path.join(_SRC, "cli.py"), encoding="utf-8").read()
    assert "ROUTING RECOMMENDATION ONLY" in text
    assert "NO PROVIDER REQUEST WAS EXECUTED" in text
    # No live-invocation subcommand.
    assert "invoke" not in text.lower().replace("invocation", "")
