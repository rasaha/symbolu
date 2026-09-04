"""No dataclass field, persisted record or handle in this package can carry secret material (D-5)."""

from __future__ import annotations

import ast
import dataclasses
import inspect
import pathlib

import pytest

import ugence_cloud_scaling_credential_broker as pkg
from ugence_cloud_scaling_credential_broker import (
    FORBIDDEN_FIELD_NAMES,
    CredentialBrokerContractError,
    CredentialGrant,
    CredentialRequest,
    RoleStatement,
)

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
SOURCES = sorted(PKG_DIR.rglob("*.py"))


def _dataclasses():
    for name in dir(pkg):
        obj = getattr(pkg, name)
        if inspect.isclass(obj) and dataclasses.is_dataclass(obj):
            yield obj
    for module_file in SOURCES:
        module = __import__(f"{pkg.__name__}.{module_file.stem}", fromlist=["*"]) if module_file.stem != "__init__" else pkg
        for name in dir(module):
            obj = getattr(module, name)
            if inspect.isclass(obj) and dataclasses.is_dataclass(obj) and obj.__module__.startswith(pkg.__name__):
                yield obj


def test_no_dataclass_field_is_named_for_secret_material():
    offenders = []
    for cls in set(_dataclasses()):
        for f in dataclasses.fields(cls):
            lowered = f.name.lower()
            if lowered in FORBIDDEN_FIELD_NAMES or any(w in lowered for w in ("secret", "token", "password", "private_key")):
                if not (cls is CredentialRequest and f.name == "minting_token"):
                    offenders.append(f"{cls.__name__}.{f.name}")
    assert offenders == []


def test_no_dataclass_field_can_hold_bytes():
    offenders = [f"{cls.__name__}.{f.name}" for cls in set(_dataclasses())
                 for f in dataclasses.fields(cls) if f.type in ("bytes", bytes, "bytearray")]
    assert offenders == []


def test_the_grant_persists_only_a_handle_reference_and_bound_facts():
    names = {f.name for f in dataclasses.fields(CredentialGrant)}
    assert names == {"grant_id", "tenant_id", "request_digest", "handle_ref", "role", "validity",
                     "broker_authority_id", "credential_profile", "disposition"}


@pytest.mark.parametrize("handle", ["", " x", "a b", "x" * 129, "line\nbreak", "eyJhbGciOi...=="])
def test_a_handle_that_could_carry_material_is_refused(world, handle):
    out = world.seam().materialize(__import__("_broker_fixtures").materialization_request(world))
    with pytest.raises(CredentialBrokerContractError):
        dataclasses.replace(out.grant, handle_ref=handle)


def test_no_source_reads_an_environment_variable_file_or_network():
    banned_calls = {"getenv", "environ", "open", "read_text", "urlopen", "connect", "system", "popen", "run"}
    offenders = []
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name in banned_calls:
                    offenders.append(f"{path.name}: {name}()")
    assert offenders == []


def test_the_minting_token_is_not_exported():
    assert "_MINT_TOKEN" not in pkg.__all__ and not hasattr(pkg, "_MINT_TOKEN")
    from ugence_cloud_scaling_credential_broker import request as request_module
    assert "_MINT_TOKEN" not in request_module.__all__
