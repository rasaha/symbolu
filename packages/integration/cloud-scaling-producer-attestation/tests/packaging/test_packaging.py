"""Packaging, public-API parity and distribution-boundary properties.

The wheel is what a deployment actually installs, so every claim about the source tree has
to hold there too. These properties check the manifest, the layout and the boundary; the
isolated-install verifier (``scripts/verify_isolated_install.py``) proves the same
behaviour digest-for-digest inside a genuinely offline installation.
"""

from __future__ import annotations

import json
import pathlib
import zipfile

import pytest

import ugence_cloud_scaling_producer_attestation as pkg

#: Property category: this module's default is declared in ``tests/conftest.py``
#: (``MODULE_PROPERTY_CATEGORY``), and a test that departs from it carries its own
#: ``@pytest.mark.<category>``, which wins. ``tests/test_property_ledger.py`` counts
#: the resolved categories, so the adversarial-to-happy ratio is machine-checked
#: rather than claimed.

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
PROJECT = PKG_DIR.parents[1]
PYPROJECT = PROJECT / "pyproject.toml"
PUBLIC_API = PROJECT / "public_api.json"


def test_the_distribution_is_named_and_versioned_exactly_as_ratified():
    """K-1: the ratified distribution name, namespace and version."""

    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'name = "ugence-cloud-scaling-producer-attestation"' in text
    assert PKG_DIR.name == "ugence_cloud_scaling_producer_attestation"
    assert pkg.__version__ == "0.2.0"


def test_the_public_api_manifest_equals_the_live_package_surface():
    """K-2: ``public_api.json`` is asserted against the surface, not merely shipped."""

    manifest = json.loads(PUBLIC_API.read_text(encoding="utf-8"))
    assert manifest["distribution"] == "ugence-cloud-scaling-producer-attestation"
    assert manifest["namespace"] == "ugence_cloud_scaling_producer_attestation"
    assert manifest["package_version"] == pkg.__version__
    assert sorted(manifest["symbols"]) == sorted(pkg.__all__)


def test_every_exported_symbol_resolves():
    """K-3: no export names something that is not there."""

    for symbol in pkg.__all__:
        assert hasattr(pkg, symbol), symbol


def test_the_public_api_has_no_duplicate_entries():
    """K-4: a duplicated export would make the manifest count silently wrong."""

    assert len(pkg.__all__) == len(set(pkg.__all__))


def test_py_typed_is_present_and_declared():
    """K-5: the package ships type information, and says so in the manifest."""

    assert (PKG_DIR / "py.typed").exists()
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'ugence_cloud_scaling_producer_attestation = ["py.typed"]' in text
    assert "Typing :: Typed" in text


def test_the_src_layout_is_used():
    """K-6: ``src/`` layout, so an accidental repo-root import cannot shadow the install."""

    assert PKG_DIR.parent.name == "src"
    assert 'where = ["src"]' in PYPROJECT.read_text(encoding="utf-8")


def test_no_test_or_conftest_module_lives_inside_the_package_tree():
    """K-7: nothing under ``src/`` can leak test material into the wheel."""

    for path in PKG_DIR.rglob("*"):
        assert path.name != "conftest.py", path
        assert not path.name.startswith("test_"), path
        assert path.name not in ("tests", "fixtures") or not path.is_dir(), path


def test_the_readme_and_changelog_exist():
    """K-8: the deliverable includes both, and the README states what is granted."""

    readme = PROJECT / "README.md"
    changelog = PROJECT / "CHANGELOG.md"
    assert readme.exists() and changelog.exists()
    assert "grants nothing" in readme.read_text(encoding="utf-8").lower()


def test_the_guard_inventory_is_published():
    """K-9: the guard inventory and its classification are published, not merely computed.

    The gate-removal sweep itself runs through the shared engine
    (``scripts/cloud_scaling/guard_sweep.py producer-attestation``) and its results are CI
    artifacts; what the package publishes is the checked-in inventory a reviewer diffs —
    every decision point with its shape, and every site's SCORED/EXCLUDED classification.
    """

    inventory = PROJECT / "GUARD_INVENTORY.md"
    classification = PROJECT / "guard_classification.json"
    assert inventory.exists() and classification.exists()
    text = classification.read_text(encoding="utf-8")
    assert '"SCORED"' in text and '"EXCLUDED"' in text


def test_no_third_party_runtime_dependency_is_added():
    """K-10: the Ed25519 backends arrive transitively as TEV's own declared requirements."""

    block = (
        PYPROJECT.read_text(encoding="utf-8")
        .split("dependencies = [", 1)[1]
        .split("]", 1)[0]
    )
    for line in block.strip().splitlines():
        entry = line.strip().strip('",')
        if not entry:
            continue
        assert entry.startswith("ugence-"), entry


@pytest.mark.skipif(
    not (PROJECT / "dist").exists(), reason="no wheel built in this working tree"
)

def test_the_built_wheel_contains_no_tests_and_carries_py_typed():
    """K-11: the wheel's contents, when one has been built."""

    wheels = sorted((PROJECT / "dist").glob("*.whl"))
    if not wheels:
        pytest.skip("no wheel built")
    names = zipfile.ZipFile(wheels[-1]).namelist()
    top = {n.split("/")[0] for n in names}
    assert top <= {
        "ugence_cloud_scaling_producer_attestation",
        f"ugence_cloud_scaling_producer_attestation-{pkg.__version__}.dist-info",
    }, sorted(top)
    for name in names:
        base = name.split("/")[-1]
        assert base != "conftest.py", name
        assert not base.startswith("test_"), name
        assert "/tests/" not in name, name
    assert any(n.endswith("py.typed") for n in names)


@pytest.mark.skipif(
    not (PROJECT / "dist").exists(), reason="no wheel built in this working tree"
)
def test_the_built_wheel_exports_exactly_the_manifest_api():
    """K-12: source/wheel public-API parity, read out of the wheel itself.

    Parses ``__all__`` from the wheel's own ``__init__.py`` rather than importing it, so
    the comparison is against the bytes that ship. The isolated-install verifier proves the
    same for a genuinely offline *installed* runtime, and additionally proves digest parity;
    this is the cheap check that runs on every suite invocation.
    """

    import ast

    wheels = sorted((PROJECT / "dist").glob("*.whl"))
    if not wheels:
        pytest.skip("no wheel built")
    with zipfile.ZipFile(wheels[-1]) as archive:
        source = archive.read(
            "ugence_cloud_scaling_producer_attestation/__init__.py"
        ).decode("utf-8")
    tree = ast.parse(source)
    exported = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(target, "id", None) == "__all__" for target in node.targets
        ):
            exported = [element.value for element in node.value.elts]
    assert exported is not None, "the wheel's __init__ declares no __all__"

    manifest = json.loads(PUBLIC_API.read_text(encoding="utf-8"))
    assert sorted(exported) == sorted(manifest["symbols"]), (
        "the built wheel's public API differs from public_api.json"
    )
    assert sorted(exported) == sorted(pkg.__all__), (
        "the built wheel's public API differs from the source tree's"
    )


@pytest.mark.skipif(
    not (PROJECT / "dist").exists(), reason="no sdist built in this working tree"
)
def test_the_sdist_carries_the_suite_and_the_wheel_does_not():
    """K-13: the two artifacts differ deliberately, and each in the right direction.

    An sdist is a source distribution: shipping the suite in it is correct, and is how a
    downstream consumer re-runs the adversarial properties against their own build. A wheel
    is an installation artifact: shipping test material in it would put fixtures, a
    reference signer's test seed and a ``conftest`` on the import path of every deployment.

    This is a **shape** assertion and claims only shape. That some path matches ``/tests/``
    does not mean the shipped payload collects, let alone runs — an earlier revision
    satisfied this assertion while shipping a payload that failed at collection because no
    ``conftest.py`` or fixture helper was in the archive at all. The claim in the sentence
    above, that a consumer can re-run the properties, is established by
    ``tests/packaging/test_sdist_payload.py``, which extracts the sdist outside the
    repository and runs it against installed distributions in a fresh virtualenv.
    """

    import tarfile

    sdists = sorted((PROJECT / "dist").glob("*.tar.gz"))
    wheels = sorted((PROJECT / "dist").glob("*.whl"))
    if not sdists or not wheels:
        pytest.skip("no distribution artifacts built")

    sdist_names = tarfile.open(sdists[-1]).getnames()
    assert any("/tests/" in name for name in sdist_names), (
        "the sdist omits the suite; a consumer cannot re-run the adversarial properties"
    )
    wheel_names = zipfile.ZipFile(wheels[-1]).namelist()
    assert not any("/tests/" in name for name in wheel_names)
