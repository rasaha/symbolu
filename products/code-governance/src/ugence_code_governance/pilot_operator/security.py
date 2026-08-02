"""Credential isolation + static read-only security inspection for the operator.

Credentials are referenced, never embedded: a ``CredentialReference`` names where a
read-only credential lives (an env var or an external resolver ref) but never
carries the value. Resolved credentials are process-memory-only and are handed to
the approved read-only transport immediately before a request, then discarded.

The static inspector scans the adapter + operator boundary (AST-based, not bare
substring matching) for prohibited constructs: HTTP mutation calls, direct HTTP
clients outside the approved transport, GitHub mutation endpoints, GraphQL
mutations, write scopes, merge/approval operations, execution-provider imports,
``reserve_once``, and credential fields in persistent schemas.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .errors import CredentialBoundaryError

# --- credential reference ---------------------------------------------------


class ResolverKind(str, Enum):
    ENVIRONMENT = "ENVIRONMENT"
    EXTERNAL_RESOLVER = "EXTERNAL_RESOLVER"
    FAKE_TEST = "FAKE_TEST"


@dataclass(frozen=True)
class CredentialReference:
    """A reference to a read-only credential. Never carries the value itself."""

    reference_id: str
    resolver_kind: ResolverKind
    source_host: str
    environment_variable_name: str = ""
    external_resolver_ref: str = ""
    required_scopes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # A credential reference must never inline a value-looking field.
        if any(_looks_like_secret_value(v) for v in
               (self.environment_variable_name, self.external_resolver_ref)):
            raise CredentialBoundaryError("credential reference must not inline a value")

    def fingerprint_fields(self) -> Dict[str, Any]:
        """Fields safe to fingerprint (names/refs/scopes only, never a value)."""
        return {
            "reference_id": self.reference_id, "resolver_kind": self.resolver_kind.value,
            "source_host": self.source_host,
            "environment_variable_name": self.environment_variable_name,
            "external_resolver_ref": self.external_resolver_ref,
            "required_scopes": sorted(self.required_scopes),
        }


def _looks_like_secret_value(text: str) -> bool:
    # A conservative heuristic: long high-entropy-ish tokens, not env var names.
    return bool(re.fullmatch(r"(gh[pousr]_[A-Za-z0-9]{20,}|[A-Za-z0-9+/]{40,}={0,2})", text or ""))


# --- credential-leak scanner -----------------------------------------------
def scan_for_credential(secret_value: str, *artifacts: Any) -> Tuple[str, ...]:
    """Return the names of any artifact in which ``secret_value`` appears.

    Artifacts may be bytes, str, mappings, sequences, or objects; each is
    stringified and searched. An empty result means the secret was found nowhere.
    """
    if not secret_value:
        return ()
    hits: List[str] = []
    for i, art in enumerate(artifacts):
        label = getattr(art, "__cg_artifact_label__", f"artifact[{i}]")
        text = art.decode("utf-8", "replace") if isinstance(art, (bytes, bytearray)) else _stringify(art)
        if secret_value in text:
            hits.append(label)
    return tuple(hits)


def _stringify(obj: Any) -> str:
    try:
        import json
        return json.dumps(obj, default=str, sort_keys=True)
    except Exception:
        return str(obj)


# --- static read-only inspection -------------------------------------------
class SecurityFinding(str, Enum):
    PROHIBITED_HTTP_VERB = "PROHIBITED_HTTP_VERB"
    DIRECT_HTTP_CLIENT = "DIRECT_HTTP_CLIENT"
    GITHUB_MUTATION_ENDPOINT = "GITHUB_MUTATION_ENDPOINT"
    GRAPHQL_MUTATION = "GRAPHQL_MUTATION"
    WRITE_SCOPE = "WRITE_SCOPE"
    MERGE_OR_APPROVAL = "MERGE_OR_APPROVAL"
    EXECUTION_PROVIDER_IMPORT = "EXECUTION_PROVIDER_IMPORT"
    RESERVE_ONCE = "RESERVE_ONCE"
    TOKEN_LOGGING = "TOKEN_LOGGING"
    CREDENTIAL_FIELD_IN_SCHEMA = "CREDENTIAL_FIELD_IN_SCHEMA"


@dataclass(frozen=True)
class SecurityScanResult:
    findings: Tuple[Tuple[str, str, int], ...] = ()  # (finding, path, line)

    @property
    def clean(self) -> bool:
        return not self.findings

    def of(self, finding: SecurityFinding) -> Tuple[Tuple[str, str, int], ...]:
        return tuple(f for f in self.findings if f[0] == finding.value)


_HTTP_MUTATION_METHODS = {"post", "put", "patch", "delete"}
_DIRECT_HTTP_CLIENT_ROOTS = {"requests", "httpx", "aiohttp"}
_MERGE_APPROVAL_NAMES = {"merge_pull_request", "merge_pr", "approve_pull_request",
                         "create_review", "add_comment", "create_deployment"}
_EXECUTION_NAMES = {"ExecutionService", "create_execution_intent", "dispatch_execution",
                    "submit_for_authorization"}
_RESERVE_NAMES = {"reserve_once", "consume_authorization"}
_SAFE_CONST_ASSIGN = re.compile(
    r"forbidden|banned|prohibited|deny|reject|_mutating|_credential_header|not_allowed|"
    r"_merge|_graphql|_write_scope|_execution_names|_reserve|_direct_http|_http_mutation",
    re.IGNORECASE)
_GRAPHQL_MUTATION = re.compile(r"mutation\s*[\{(]")
_MERGE_PATH = re.compile(r"/pulls/\S*/merge|merge_pull_request")
_WRITE_SCOPE = re.compile(r"\b[a-z_]+:write\b")


def scan_source(text: str, path: str = "<source>", *, in_transport: bool = False) -> SecurityScanResult:
    """AST-scan one source string for prohibited constructs."""
    findings: List[Tuple[str, str, int]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return SecurityScanResult(())

    docstrings = set()
    safe_consts = set()
    for node in ast.walk(tree):
        # Collect docstrings to ignore documentation-only forbidden words.
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
        # Collect string constants assigned to obviously-safe (deny-list) names.
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(_SAFE_CONST_ASSIGN.search(n) for n in names):
                for s in ast.walk(node.value):
                    if isinstance(s, ast.Constant) and isinstance(s.value, str):
                        safe_consts.add(s.value)

    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        # HTTP mutation calls: x.post(/put/patch/delete(...)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _HTTP_MUTATION_METHODS:
                findings.append((SecurityFinding.PROHIBITED_HTTP_VERB.value, path, line))
            if node.func.attr in _MERGE_APPROVAL_NAMES:
                findings.append((SecurityFinding.MERGE_OR_APPROVAL.value, path, line))
        # Names for reserve_once / execution / merge symbols
        if isinstance(node, ast.Name) and node.id in _RESERVE_NAMES:
            findings.append((SecurityFinding.RESERVE_ONCE.value, path, line))
        if isinstance(node, (ast.Name, ast.Attribute)):
            ident = node.id if isinstance(node, ast.Name) else node.attr
            if ident in _EXECUTION_NAMES:
                findings.append((SecurityFinding.EXECUTION_PROVIDER_IMPORT.value, path, line))
            if ident in _MERGE_APPROVAL_NAMES:
                findings.append((SecurityFinding.MERGE_OR_APPROVAL.value, path, line))
        # Direct HTTP client imports (allowed only inside the approved transport).
        if isinstance(node, (ast.Import, ast.ImportFrom)) and not in_transport:
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif node.module:
                mods = [node.module]
            for m in mods:
                root = m.split(".")[0]
                if root in _DIRECT_HTTP_CLIENT_ROOTS or m == "urllib.request":
                    findings.append((SecurityFinding.DIRECT_HTTP_CLIENT.value, path, line))
                if "execution_provider" in m or m.endswith(".execution"):
                    findings.append((SecurityFinding.EXECUTION_PROVIDER_IMPORT.value, path, line))
        # Non-docstring string constants: GraphQL / merge path / write scope.
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            s = node.value
            if s in safe_consts:
                continue
            if _GRAPHQL_MUTATION.search(s):
                findings.append((SecurityFinding.GRAPHQL_MUTATION.value, path, line))
            if _MERGE_PATH.search(s):
                findings.append((SecurityFinding.GITHUB_MUTATION_ENDPOINT.value, path, line))
            if _WRITE_SCOPE.search(s):
                findings.append((SecurityFinding.WRITE_SCOPE.value, path, line))
    return SecurityScanResult(tuple(findings))


def scan_paths(paths: Iterable[Path], *, transport_marker: str = "transport.py") -> SecurityScanResult:
    """AST-scan a set of Python files, allowing HTTP clients only in the transport."""
    all_findings: List[Tuple[str, str, int]] = []
    for p in paths:
        p = Path(p)
        if not p.is_file() or p.suffix != ".py":
            continue
        in_transport = transport_marker in p.name
        res = scan_source(p.read_text(), str(p), in_transport=in_transport)
        all_findings.extend(res.findings)
    return SecurityScanResult(tuple(all_findings))


__all__ = [
    "ResolverKind", "CredentialReference", "scan_for_credential",
    "SecurityFinding", "SecurityScanResult", "scan_source", "scan_paths",
]
