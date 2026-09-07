"""What a converter never does (CV-1, CV-4, CV-5), asserted on source and output.

- offline: no network, process, dynamic-import, YAML or archive module is imported
  anywhere in the package;
- draft only: the emitted pack is DRAFT and the compiler refuses to compile it;
- the claim: no report text ever says equivalent, governed, approved or validated,
  and the composer's reserved word SEMANTICALLY_EQUIVALENT never appears;
- the preview passes the Bring Your Workflow gate's own rules (no credential-shaped
  key with a value, no remote reference) and the composer's adapter accepts it;
- the fixtures themselves carry no secret.
"""
from __future__ import annotations

import ast
import json
import os
import re

import pytest

from conftest import FIXTURES, PACKAGE
from ugence_workflow_converters.api import CLAIM, convert, version_info

SRC = os.path.join(PACKAGE, "src", "ugence_workflow_converters")
FORBIDDEN_MODULES = {
    "socket", "http", "urllib", "urllib3", "requests", "httpx", "aiohttp", "websocket", "ftplib", "smtplib",
    "subprocess", "os.system", "multiprocessing", "importlib", "yaml", "ruamel", "zipfile", "tarfile", "pickle",
    "marshal", "shelve", "langgraph", "crewai", "autogen", "langchain", "openai", "anthropic",
}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}


def _sources():
    for root, _dirs, files in os.walk(SRC):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path, encoding="utf-8") as fh:
                    yield path, fh.read()


def _bytes(name: str) -> bytes:
    with open(os.path.join(FIXTURES, name), "rb") as fh:
        return fh.read()


def test_the_package_imports_no_network_process_dynamic_import_yaml_or_archive_module():
    for path, text in _sources():
        tree = ast.parse(text)
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                top = name.split(".")[0]
                assert top not in FORBIDDEN_MODULES and name not in FORBIDDEN_MODULES, f"{path} imports {name}"
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in FORBIDDEN_CALLS, f"{path} calls {node.func.id}"


def test_the_only_first_party_dependency_is_the_compiler():
    for path, text in _sources():
        for m in re.finditer(r"^\s*(?:from|import)\s+(ugence_[a-z_]+)", text, re.M):
            assert m.group(1) in ("ugence_policy_workflow_compiler", "ugence_workflow_converters"), f"{path}: {m.group(1)}"


FIXTURE_BY_FORMAT = [("n8n", "order_review.n8n.json"), ("bpmn-2.0", "purchase_approval.bpmn")]


@pytest.mark.parametrize("fmt, name", FIXTURE_BY_FORMAT)
def test_the_pack_is_draft_and_the_compiler_refuses_to_compile_it(fmt, name):
    from ugence_policy_workflow_compiler.api import GovernedWorkflowCompiler
    from ugence_policy_workflow_compiler.models.policy_pack import IllegalLifecycleTransition
    outcome = convert(fmt, _bytes(name))
    assert outcome.pack.status.value == "DRAFT"
    with pytest.raises(IllegalLifecycleTransition):
        GovernedWorkflowCompiler().compile(outcome.pack, None, require_approval=False)
    result = GovernedWorkflowCompiler().compile(outcome.pack, None)
    assert result.success is False
    assert any(d.code == "APPROVAL_REQUIRED" for d in result.validation_report.diagnostics)


FORBIDDEN_CLAIM_WORDS = re.compile(r"\b(equivalent|equivalence|governed|approved|validated|executable|certified)\b", re.I)
ALLOWED_NEGATIONS = re.compile(r"(no claim of|not equivalent|not governed|not approved|not validated|never|unapproved|is not)", re.I)


def _texts(value, path="$"):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _texts(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _texts(v, f"{path}[{i}]")


@pytest.mark.parametrize("fmt, name", FIXTURE_BY_FORMAT)
def test_no_report_pack_or_preview_text_makes_a_forbidden_claim(fmt, name):
    outcome = convert(fmt, _bytes(name))
    for document in (outcome.report.as_document(), outcome.pack_document, outcome.preview):
        dumped = json.dumps(document)
        assert "SEMANTICALLY_EQUIVALENT" not in dumped
        for path, text in _texts(document):
            for sentence in re.split(r"[.;]\s+", text):
                if FORBIDDEN_CLAIM_WORDS.search(sentence):
                    assert ALLOWED_NEGATIONS.search(sentence), f"{path}: {sentence!r}"
    assert CLAIM in json.dumps(outcome.report.as_document())
    assert outcome.report.conversion_state.value in ("STRUCTURALLY_TRANSLATED", "PARTIAL")


def test_version_info_is_honest_about_what_exists():
    info = version_info()
    assert info.implemented_formats == ("n8n", "bpmn-2.0")
    assert info.next_format == ""
    assert info.deferred_formats == ("langgraph", "crewai", "autogen")
    assert info.maturity["semantic_equivalence_claimed"] is False
    assert info.maturity["governance_or_approval_conferred"] is False
    assert info.maturity["offline_only"] is True
    assert info.maturity["bpmn_converter_implemented"] is True
    for name in ("langgraph", "crewai", "autogen"):
        assert info.maturity[f"{name}_converter_implemented"] is False


# The Bring Your Workflow gate's own rules (apps/ugence-governance-studio/frontend/src/features/bring/gate.ts).
GATE_CREDENTIAL_KEY = re.compile(r"(secret|password|passwd|token|api[_-]?key|private[_-]?key|authorization|bearer|credential)", re.I)
GATE_REMOTE = re.compile(r"^\s*(https?|ftp|ftps|file|ws|wss|s3|gs|git|ssh)://", re.I)


@pytest.mark.parametrize("fmt, name", FIXTURE_BY_FORMAT)
def test_the_preview_passes_the_bring_your_workflow_gate_rules_and_declares_v1(fmt, name):
    outcome = convert(fmt, _bytes(name))
    preview = outcome.preview
    assert preview is not None
    assert preview["preview"]["status"] == "PREVIEW_UNAPPROVED"
    assert preview["workflow_ir"]["ir_version"] == "workflow_ir.v1"
    assert "manifest" not in preview and "release_metadata" not in preview
    stack = [(preview, None)]
    while stack:
        value, key = stack.pop()
        if isinstance(value, str):
            assert not (key and GATE_CREDENTIAL_KEY.search(key) and value.strip()), key
            assert not GATE_REMOTE.match(value), value
        elif isinstance(value, dict):
            stack.extend((v, k) for k, v in value.items())
        elif isinstance(value, list):
            stack.extend((v, None) for v in value)
    assert len(json.dumps(preview).encode()) < 1024 * 1024


@pytest.mark.parametrize("fmt, name", FIXTURE_BY_FORMAT)
def test_the_composer_adapts_the_preview_when_it_is_installed(fmt, name):
    awc = pytest.importorskip("ugence_agent_workforce_composer.api")
    outcome = convert(fmt, _bytes(name))
    envelope = awc.adapt_workflow(outcome.preview, contract_version="workflow_ir.v1")
    assert envelope.ok is True
    assert envelope.adapter_mode == "V1_FROZEN"
    dispositions = envelope.adaptation_result.node_dispositions
    assert len(dispositions) == len(outcome.preview["workflow_ir"]["nodes"])


def test_the_fixtures_carry_no_secret_and_the_leaky_ones_are_the_exception():
    import xml.etree.ElementTree as ET
    from ugence_workflow_converters.intake import scan_secrets, scan_xml_secrets
    from ugence_workflow_converters.report import ConversionRefused
    for name in sorted(os.listdir(FIXTURES)):
        data = _bytes(name)
        if name.endswith(".json"):
            scan = lambda: scan_secrets(json.loads(data))  # noqa: E731
        elif name == "doctype.bpmn":
            continue  # refused before parsing; its content is the purchase fixture's
        else:
            scan = lambda: scan_xml_secrets(ET.fromstring(data.decode("utf-8")))  # noqa: E731
        if name.startswith("embedded_secret."):
            with pytest.raises(ConversionRefused):
                scan()
        else:
            scan()
