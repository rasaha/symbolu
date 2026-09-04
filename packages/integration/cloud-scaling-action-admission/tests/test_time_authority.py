"""This package reads no clock. Asserted over source imports and AST call expressions."""

from __future__ import annotations

import ast
import inspect
import pathlib

import ugence_cloud_scaling_action_admission as pkg
from ugence_cloud_scaling_action_admission import CapacityActionGate, CloudScalingActionAdmission

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
SOURCES = sorted(PKG_DIR.rglob("*.py"))
CLOCK_CALLS = {"now", "utcnow", "today", "time", "monotonic", "perf_counter", "fromtimestamp"}
CLOCK_MODULES = {"time", "calendar"}


def test_no_module_imports_a_clock_source():
    offenders = []
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                offenders += [f"{path.name}: import {a.name}" for a in node.names
                              if a.name.split(".")[0] in CLOCK_MODULES]
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in CLOCK_MODULES:
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


def test_the_gate_takes_its_instant_from_the_seam_and_the_root_takes_none():
    params = inspect.signature(CapacityActionGate.authorize).parameters
    assert params["now"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["now"].default is inspect.Parameter.empty
    assert "now" not in inspect.signature(CloudScalingActionAdmission.admit).parameters
    for factory in (CloudScalingActionAdmission.production, CloudScalingActionAdmission.reference):
        assert inspect.signature(factory).parameters["clock"].default is inspect.Parameter.empty
