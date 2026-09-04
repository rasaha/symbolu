"""This package holds no credential and builds no backend (ADR 5D, D-3 and 5X D-5)."""

from __future__ import annotations

import ast
import dataclasses
import inspect
import pathlib

import ugence_cloud_scaling_bounded_execution as pkg

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
SOURCES = sorted(PKG_DIR.rglob("*.py"))
FORBIDDEN = {"secret", "token", "password", "kubeconfig", "private_key", "access_key", "credential", "handle_ref"}


def test_no_dataclass_field_can_carry_credential_material():
    offenders = []
    for name in dir(pkg):
        obj = getattr(pkg, name)
        if inspect.isclass(obj) and dataclasses.is_dataclass(obj) and obj.__module__.startswith(pkg.__name__):
            for f in dataclasses.fields(obj):
                if any(w in f.name.lower() for w in FORBIDDEN) or f.type in ("bytes", bytes):
                    offenders.append(f"{obj.__name__}.{f.name}")
    assert offenders == []


def test_no_source_names_the_kubernetes_backend_or_a_client_constructor():
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for banned in ("KubernetesScalingExecutor", "k8s_executor", "kubernetes.client", "AppsV1Api", "load_kube_config"):
            assert banned not in text, (path.name, banned)


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


def test_the_grant_handle_never_reaches_the_executor(world):
    """The operations authorization the seam mints carries the grant *id* as nonce and key id,
    never the handle reference."""

    from _execution_fixtures import dispatch_request
    out = world.seam().dispatch(dispatch_request(world))
    events = getattr(world.audit, "events", [])
    for event in events:
        assert world.grant.handle_ref not in repr(event.to_dict() if hasattr(event, "to_dict") else event)
    assert out.record is not None and world.grant.handle_ref not in repr(out.record)
