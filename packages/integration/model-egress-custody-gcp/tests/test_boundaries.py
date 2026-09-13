"""What this distribution may import, what it may say, and where it may live.

A package can assert what it imports; it cannot assert what imports it. The
repository-wide direction is checked by ``scripts/check_package_import_boundaries.py``;
what is checked here is the property that gate cannot see: that the Google SDK is
reachable from exactly one function, and that the unit is still free of it.
"""

from __future__ import annotations

import ast
import pathlib
import typing

import pytest

import ugence_model_egress_custody_gcp as pkg
import ugence_model_egress_unit as meu
from ugence_model_egress_custody_gcp import SecretManagerClient
from ugence_model_egress_custody_gcp.client import build_google_secret_manager_client

SRC = pathlib.Path(pkg.__file__).resolve().parent
SOURCES = sorted(SRC.rglob("*.py"))
UNIT_SRC = pathlib.Path(meu.__file__).resolve().parent

#: Anything that can reach a network or a vendor. ``google`` is permitted in this
#: distribution, but only inside one function: see the test below.
NETWORK_ROOTS = frozenset({"http", "httpx", "requests", "urllib", "urllib3", "socket", "ssl",
                           "asyncio", "aiohttp", "websockets", "grpc", "ftplib", "smtplib",
                           "subprocess", "openai", "anthropic", "boto3", "litellm", "langchain"})


def _module_scope_imports(path: pathlib.Path) -> set:
    """Import roots bound at module scope. A function-local import is not one."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    inside_a_function = {inner for node in ast.walk(tree)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                         for inner in ast.walk(node)}
    roots = set()
    for node in ast.walk(tree):
        if node in inside_a_function:
            continue
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_module_imports_a_network_or_vendor_root_at_module_scope(path):
    roots = _module_scope_imports(path)
    assert not roots & NETWORK_ROOTS, sorted(roots & NETWORK_ROOTS)
    assert "google" not in roots, (
        f"{path.name} imports a Google SDK at module scope; the SDK is reachable from "
        f"build_google_secret_manager_client() and nowhere else")


def test_the_google_sdk_is_imported_inside_exactly_one_function():
    text = (SRC / "client.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    importers = [node.name for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and any(isinstance(inner, (ast.Import, ast.ImportFrom))
                         and "google" in (getattr(inner, "module", "") or
                                          " ".join(a.name for a in inner.names))
                         for inner in ast.walk(node))]
    assert importers == ["build_google_secret_manager_client"], importers
    others = [p for p in SOURCES if p.name != "client.py" and "google" in p.read_text(encoding="utf-8")
              and "from google" in p.read_text(encoding="utf-8")]
    assert others == [], [p.name for p in others]


def test_importing_this_package_loads_no_google_sdk():
    import sys
    assert not [m for m in sys.modules if m == "google" or m.startswith("google.")], (
        "importing this distribution pulled in a Google SDK")


def test_the_client_protocol_carries_exactly_one_method_so_listing_is_not_expressible():
    methods = {name for name in dir(SecretManagerClient)
               if not name.startswith("_") and callable(getattr(SecretManagerClient, name, None))}
    assert methods == {"access_secret_version"}, methods
    assert typing.runtime_checkable(SecretManagerClient) is SecretManagerClient


def test_the_real_client_builder_is_never_called_by_this_package():
    """It is the deployment composition root's call. Nothing here invokes it, so no test
    and no import can reach Google by accident."""

    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        calls = text.count("build_google_secret_manager_client(")
        if path.name in ("client.py", "__init__.py"):
            continue
        assert calls == 0, f"{path.name} calls the real client builder"
    assert callable(build_google_secret_manager_client)


# --- the unit is still free of all of it ----------------------------------------------

@pytest.mark.parametrize("path", sorted(UNIT_SRC.rglob("*.py")), ids=lambda p: p.name)
def test_the_core_unit_still_has_no_google_sdk_or_socket_capable_import(path):
    roots = _module_scope_imports(path)
    assert "google" not in roots, f"the unit's {path.name} imports a Google SDK"
    forbidden = roots & (NETWORK_ROOTS | {"google"})
    assert not forbidden, f"the unit's {path.name} imports {sorted(forbidden)}"


def test_the_unit_does_not_import_this_distribution():
    for path in UNIT_SRC.rglob("*.py"):
        assert "ugence_model_egress_custody_gcp" not in path.read_text(encoding="utf-8"), path.name


def test_this_distribution_is_the_only_one_that_names_the_google_secret_manager_sdk():
    """Packaged only here: no other first-party distribution declares or imports it."""

    repo = pathlib.Path(__file__).resolve().parents[4]
    offenders = []
    for pyproject in sorted((repo / "packages").rglob("pyproject.toml")):
        if pyproject.parent.name == "model-egress-custody-gcp":
            continue
        if "google-cloud-secret-manager" in pyproject.read_text(encoding="utf-8"):
            offenders.append(pyproject.relative_to(repo).as_posix())
    assert offenders == [], offenders


# --- what the package may say ---------------------------------------------------------

def test_the_adapter_name_is_exactly_the_one_lp8_requires():
    assert pkg.PRODUCTION_FORM_ADAPTER_NAME == meu.PRODUCTION_FORM_CUSTODY_ADAPTER
    assert pkg.ProductionFormSecretManagerCustodyAdapter.adapter_name == meu.PRODUCTION_FORM_CUSTODY_ADAPTER


def test_the_declared_posture():
    assert pkg.LIVE_VENDOR_EGRESS is False
    assert pkg.PERMITTED_SECRET_MANAGER_METHOD == "AccessSecretVersion"
    assert meu.COMMISSIONING_STATUS == "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS"


def test_no_module_carries_a_credential_shape():
    from synthetic_shapes import _join
    families = (_join("sk", "-", "proj", "-"), _join("sk", "-", "svcacct", "-"), _join("AI", "za"),
                _join("BEGIN", " PRIVATE", " KEY"), _join("ya", "29", "."))
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for family in families:
            assert family not in text, (path.name, "carries a credential prefix family")
