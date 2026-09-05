"""Import boundary, the clock-free rule, the declared dependency set, the naming
prohibitions, and the structural inability to run a probe, hold a corpus, score a
finding, admit evidence, evaluate a control, persist or call a network — asserted
over source, AST and metadata.

These are the rulings AE-1 to AE-5 made mechanical.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
import tomllib

import ugence_agent_assurance_evidence as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED_FIRST_PARTY = {"ugence_agent_assurance_evidence", "ugence_governance_contracts"}
FORBIDDEN = {
    # the three consumers the rulings name: Risk Authority, TAP, the evidence runtime
    "risk_authority", "ugence_risk_authority_runtime", "ugence_risk_authority_evidence_runtime",
    "ugence_tap_provider", "tap_provider", "ugence_governance_provider_framework",
    "governance_providers", "truth_assurance_pipeline",
    # neighbours whose nouns this package must not duplicate
    "ugence_ai_system_registry", "ugence_data_use_admission", "ugence_vendor_dependency",
    "ugence_agent_runtime", "ugence_approval_workflow", "ugence_authority_directory",
    "ugence_decision_authority", "decision_governance", "ugence_policy_authority",
    "ugence_model_selection", "ugence_benchmark_registry", "ugence_storygraph",
    "ugence_incident_response", "ugence_actiongate_provider", "ugence_trusted_evidence_authority",
    # anything a runner, corpus, scorer, store or connector would need
    "sqlite3", "sqlalchemy", "psycopg", "redis", "pydantic", "requests", "httpx",
    "aiohttp", "boto3", "kubernetes", "azure", "google", "openai", "anthropic",
    "fastapi", "cryptography", "nacl", "OpenSSL", "ldap3", "jwt", "socket", "ssl",
    "urllib", "http", "asyncio", "subprocess", "multiprocessing", "threading",
    "concurrent", "random", "re", "numpy", "torch",
}


def _roots(path: pathlib.Path) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _identifiers(path: pathlib.Path) -> set[str]:
    """Every name and string literal the *code* uses, with docstrings excluded.

    Prose is allowed to name what the package refuses to do — the code is not.
    """

    tree = ast.parse(path.read_text(), filename=str(path))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings:
            names.add(node.value)
    return names


def _segments() -> set[str]:
    """Whole word segments of every code identifier, so "supersession" is not read
    as "session" and "assurance" is not read as "assure"."""

    return {seg for src in SOURCES for name in _identifiers(src)
            for seg in re.split(r"[^a-z0-9]+", re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower())}


# --------------------------------------------------------------------------- #
# Import boundary and declared dependencies
# --------------------------------------------------------------------------- #
def test_source_imports_only_stdlib_and_governance_contracts():
    for src in SOURCES:
        roots = _roots(src)
        strays = roots - STDLIB - ALLOWED_FIRST_PARTY - {"__future__"}
        assert not strays, (src.name, strays)
        assert not (roots & FORBIDDEN), (src.name, roots & FORBIDDEN)


def test_pyproject_declares_the_ratified_dependency_set():
    data = tomllib.loads((DIST / "pyproject.toml").read_text())
    assert data["project"]["name"] == "ugence-agent-assurance-evidence"
    assert data["project"]["dependencies"] == ["ugence-governance-contracts>=0.8.0"]
    joined = " ".join(data["project"]["dependencies"]).lower()
    for forbidden in ("risk-authority", "risk_authority", "evidence-runtime", "tap",
                      "provider-framework", "trusted-evidence", "ai-system-registry",
                      "data-use-admission", "vendor-dependency", "agent-runtime",
                      "approval-workflow", "authority-directory", "decision-authority",
                      "policy-authority", "model-selection", "benchmark-registry",
                      "pydantic", "sqlalchemy", "requests", "httpx", "numpy", "torch"):
        assert forbidden not in joined, forbidden
    assert pkg.__version__ == "0.1.0"


def test_no_clock_is_read_anywhere():
    """Every instant is a caller input, so a finding lapses without a sweeper."""

    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                assert name not in ("now", "utcnow", "today", "time", "monotonic",
                                    "perf_counter", "uuid4", "uuid1", "urandom",
                                    "random"), (src.name, name)
                if name == "astimezone":
                    assert node.args, f"{src.name}: zero-argument astimezone infers the local zone"


# --------------------------------------------------------------------------- #
# Naming (AE-1); mints no identity, no reference and no vocabulary (AE-2, AE-3, AE-5)
# --------------------------------------------------------------------------- #
def test_no_exported_type_is_an_authority_runner_probe_or_engine():
    for name in pkg.__all__:
        for noun in ("Authority", "Runner", "Probe", "Engine", "Adversarial", "Scorer",
                     "Corpus", "Admission", "Evaluator"):
            assert noun not in name, (name, noun)
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.ClassDef):
                for noun in ("Authority", "Runner", "Probe", "Engine", "Adversarial", "Scorer",
                             "Corpus", "Admission", "Evaluator"):
                    assert noun not in node.name, (src.name, node.name, noun)


def test_the_package_defines_no_identity_reference_or_label_of_its_own():
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.ClassDef):
                assert "SystemBinding" not in node.name, (src.name, node.name)
                assert not node.name.endswith("Reference"), (src.name, node.name)
                assert not node.name.endswith("Label"), (src.name, node.name)
                assert "Provenance" not in node.name and "Status" not in node.name, node.name
    from ugence_governance_contracts.contracts import assurance_finding as gc_label
    from ugence_governance_contracts.contracts import evidence as gc_evidence
    from ugence_governance_contracts.contracts import system_identity as gc_identity

    assert pkg.AssessedSystemBinding is gc_identity.AssessedSystemBinding
    assert pkg.SystemBindingAuthenticityStatus is gc_identity.SystemBindingAuthenticityStatus
    assert pkg.EvidenceReference is gc_evidence.EvidenceReference
    assert pkg.AssuranceFindingLabel is gc_label.AssuranceFindingLabel


# --------------------------------------------------------------------------- #
# Contracts only: structurally unable to run, probe, score, admit, evaluate,
# persist, call a network or decide
# --------------------------------------------------------------------------- #
def test_no_surface_can_run_score_admit_evaluate_or_decide():
    forbidden = {"run", "execute", "probe", "attack", "score", "grade", "rate", "rank",
                 "admit", "evaluate", "assess", "decide", "approve", "reject", "authorize",
                 "verify", "resolve", "fetch", "cite", "submit", "gate", "promote", "attest",
                 "sign", "revoke", "sync", "push", "save", "store", "commit", "upsert",
                 "delete", "connect", "send", "call", "register"}
    for name in pkg.__all__:
        value = getattr(pkg, name)
        if isinstance(value, type):
            methods = {n for n in dir(value) if not n.startswith("_")}
            assert not methods & forbidden, (name, methods & forbidden)
        assert name.lower() not in forbidden, name
    assert pkg.ENFORCEMENT_ENABLED is False
    assert pkg.MATURITY == "REFERENCE_GRADE_CONTRACT_ONLY"


def test_the_code_names_none_of_the_things_it_refuses_to_do():
    """AE-2, AE-3, AE-4 and the contracts-only posture, held over code identifiers.

    Docstrings may say "probe" or "admit" to state what the package refuses; the
    code may not, because a function that could do it would have to name it.
    """

    segments = _segments()
    for word in (
        # probing, corpora, attacks, scoring (a probe runner's vocabulary)
        "probe", "probes", "attack", "corpus", "corpora", "payload", "prompt", "jailbreak",
        "inject", "injection", "exploit", "fuzz", "score", "severity", "cvss", "grade",
        "rank", "weight",
        # admission, control evaluation, citation (the two AE-4 routes, both external)
        "admit", "admission", "control", "evaluate", "evaluation", "cite",
        "citation", "submit", "coverage", "assertion",
        # verification (AE-3): the label implies none
        "verify", "verified", "verification", "unverified",
        # persistence, transport, connectors
        "sqlite", "connect", "connection", "session", "http", "https", "url", "endpoint",
        "client", "socket", "gateway", "proxy",
        # a competing evidence identity (AE-2)
        "provenance", "source_identity", "issuer_ref", "collection_method",
    ):
        assert word not in segments, word
    module_names = {src.stem for src in SOURCES}
    for banned in ("memory", "sqlite", "store", "adapter", "connector", "client", "runner",
                   "probe", "corpus", "scorer", "engine", "harness", "attack"):
        assert banned not in module_names, banned


def test_no_field_duplicates_the_evidence_reference_or_could_carry_a_corpus():
    """The declaration carries the reference whole and copies nothing out of it.
    Pinned by field set."""

    import dataclasses

    names = [f.name for f in dataclasses.fields(pkg.AssuranceFindingDeclaration)]
    assert names == ["declaration_id", "tenant_id", "binding", "evidence", "finding",
                     "exercise_ref", "validity", "supersedes", "declared_by", "correlation_id",
                     "notes"]
    for forbidden in ("evidence_id", "content_digest", "provenance_ref", "provenance",
                      "evidence_kind", "created_at", "subject_id", "payload", "corpus", "prompt",
                      "transcript", "score", "severity", "status", "verification_status"):
        assert forbidden not in names, forbidden


def test_the_declaration_cannot_be_mutated_after_construction():
    import dataclasses

    import pytest

    from _fixtures import declaration

    d = declaration()
    assert dataclasses.is_dataclass(d) and d.__dataclass_params__.frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.exercise_ref = "exercise://other"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.finding = pkg.AssuranceFindingLabel("no-finding")  # type: ignore[misc]
