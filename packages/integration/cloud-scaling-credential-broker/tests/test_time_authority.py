"""This package reads no clock. Asserted over source imports and AST call expressions."""

from __future__ import annotations

import ast
import inspect
import pathlib

import ugence_cloud_scaling_credential_broker as pkg
from ugence_cloud_scaling_credential_broker import CredentialBrokerSeam, CredentialRequestMinter

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
SOURCES = sorted(PKG_DIR.rglob("*.py"))
CLOCK_CALLS = {"now", "utcnow", "today", "time", "monotonic", "perf_counter", "fromtimestamp"}
CLOCK_MODULES = {"time", "calendar"}


def test_no_module_imports_a_clock_source():
    offenders = []
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                offenders += [f"{path.name}: import {a.name}" for a in node.names if a.name.split(".")[0] in CLOCK_MODULES]
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in CLOCK_MODULES:
                offenders.append(f"{path.name}: from {node.module}")
    assert offenders == []


def test_no_ast_call_expression_reads_a_wall_clock():
    offenders = []
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name in CLOCK_CALLS:
                    offenders.append(f"{path.name}: {name}()")
    assert offenders == []


def test_the_seam_reads_its_clock_once_and_the_minter_takes_instants_from_it():
    src = inspect.getsource(CredentialBrokerSeam.materialize)
    calls = [n for n in ast.walk(ast.parse(inspect.getsource(CredentialBrokerSeam)))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "_clock"]
    assert len(calls) == 1 and "self._clock()" in src
    params = inspect.signature(CredentialRequestMinter.mint).parameters
    assert params["issued_at"].default is inspect.Parameter.empty
    assert params["not_after"].default is inspect.Parameter.empty
    for factory in (CredentialBrokerSeam.production, CredentialBrokerSeam.reference):
        assert inspect.signature(factory).parameters["clock"].default is inspect.Parameter.empty
