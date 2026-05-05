"""Tests for the CycloneDX SBOM generator (``safety_case.sbom``).

Pinned contracts:

* The generated dict conforms structurally to CycloneDX 1.5
  (``bomFormat``, ``specVersion``, ``components`` keys present).
* The on-disk snapshot ``safety_case/SBOM.cdx.json`` is byte-
  identical to ``write_cyclonedx_bom(generate_cyclonedx_bom())``.
  A drift means either (a) a dependency was added without
  refreshing the snapshot, or (b) the snapshot was hand-edited.
* Components are sorted deterministically (sorted by name +
  version) so the on-disk JSON is stable across runs.
* :class:`SBOMComponent` validates required fields and rejects
  unknown component types.
* SPDX compound expressions (containing AND/OR/WITH) render
  under the CycloneDX ``expression`` key, NOT ``license.id``.
* The runtime auto-discovery includes numpy with a real version.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import symbolu_robotics.bcvf_autonomous as bcvf
from symbolu_robotics.bcvf_autonomous.safety_case.sbom import (
    SBOMComponent,
    generate_cyclonedx_bom,
    runtime_components,
    write_cyclonedx_bom,
)
from symbolu_robotics.bcvf_autonomous.safety_case.sbom.generator import (
    CYCLONEDX_SPEC_VERSION,
    render_cyclonedx_bom_text,
)


SBOM_SNAPSHOT_PATH = (
    Path(bcvf.__file__).parent / "safety_case" / "SBOM.cdx.json"
)


# --------------------------------------------------------------------------- #
# Spec / format
# --------------------------------------------------------------------------- #


def test_cyclonedx_spec_version_is_1_5():
    assert CYCLONEDX_SPEC_VERSION == "1.5"


def test_generated_bom_has_required_top_level_keys():
    bom = generate_cyclonedx_bom()
    for key in ("bomFormat", "specVersion", "components", "metadata", "version"):
        assert key in bom, f"missing CycloneDX top-level key: {key!r}"
    assert bom["bomFormat"] == "CycloneDX"
    assert bom["specVersion"] == "1.5"


def test_generated_bom_metadata_lists_the_generator_tool():
    """CycloneDX 1.5 metadata.tools must name the tool that
    produced the BOM — auditors trace the manifest origin."""
    bom = generate_cyclonedx_bom()
    tools = bom["metadata"]["tools"]
    assert isinstance(tools, list) and len(tools) >= 1
    assert any(
        t["name"] == "bcvf_autonomous.safety_case.sbom" for t in tools
    )


def test_generated_bom_metadata_component_names_the_package():
    bom = generate_cyclonedx_bom()
    primary = bom["metadata"]["component"]
    assert primary["type"] == "library"
    assert primary["name"] == "symbolu_robotics.bcvf_autonomous"


# --------------------------------------------------------------------------- #
# Auto-discovery
# --------------------------------------------------------------------------- #


def test_runtime_components_includes_numpy():
    components = runtime_components()
    names = [c.name for c in components]
    assert "numpy" in names, (
        "runtime_components() must enumerate numpy — it's the "
        "autonomy module's load-bearing dependency"
    )


def test_runtime_components_resolve_versions_via_metadata():
    components = runtime_components()
    for c in components:
        assert c.version  # non-empty
        # importlib.metadata returns numeric versions; spot-check
        # that we got a structured version, not a literal "?".
        assert c.version[0].isdigit()


def test_runtime_components_emit_purls():
    components = runtime_components()
    for c in components:
        assert c.purl is not None
        assert c.purl.startswith("pkg:pypi/")


# --------------------------------------------------------------------------- #
# Determinism + snapshot parity
# --------------------------------------------------------------------------- #


def test_generated_bom_is_deterministic():
    """Same inputs in, same dict out — snapshot parity depends on
    deterministic generation."""
    a = generate_cyclonedx_bom()
    b = generate_cyclonedx_bom()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_components_are_sorted_by_name_and_version():
    """A future contributor adding a dep should not need to know
    insertion order — the manifest is sorted."""
    components = [
        SBOMComponent(name="zlib", version="1.0", licenses=("MIT",)),
        SBOMComponent(name="abc", version="2.0", licenses=("MIT",)),
        SBOMComponent(name="abc", version="1.0", licenses=("MIT",)),
    ]
    bom = generate_cyclonedx_bom(components=components)
    names = [c["name"] for c in bom["components"]]
    versions = [c["version"] for c in bom["components"]]
    assert names == ["abc", "abc", "zlib"]
    # Two abc entries — sorted by version too.
    assert versions[:2] == ["1.0", "2.0"]


def test_snapshot_file_exists():
    assert SBOM_SNAPSHOT_PATH.exists(), (
        f"missing SBOM snapshot at {SBOM_SNAPSHOT_PATH}. "
        "Re-render via safety_case.sbom.write_cyclonedx_bom()."
    )


def test_snapshot_matches_rendered_bom():
    """The on-disk snapshot must be byte-identical to
    ``write_cyclonedx_bom(generate_cyclonedx_bom())``. A drift
    means a dep was added without refreshing the snapshot."""
    bom = generate_cyclonedx_bom()
    rendered = render_cyclonedx_bom_text(bom)
    on_disk = SBOM_SNAPSHOT_PATH.read_text(encoding="utf-8")
    assert on_disk == rendered, (
        "SBOM.cdx.json is out of sync with generate_cyclonedx_bom(). "
        "Re-render via safety_case.sbom.write_cyclonedx_bom() and "
        "commit the refreshed snapshot."
    )


# --------------------------------------------------------------------------- #
# SBOMComponent validation
# --------------------------------------------------------------------------- #


def test_sbom_component_rejects_empty_name():
    with pytest.raises(ValueError, match="name"):
        SBOMComponent(name="", version="1.0")


def test_sbom_component_rejects_empty_version():
    with pytest.raises(ValueError, match="version"):
        SBOMComponent(name="numpy", version="")


def test_sbom_component_rejects_unknown_type():
    """CycloneDX 1.5 defines a fixed set of component types. A
    typo'd type fails loud rather than silently emitting a
    non-validating manifest."""
    with pytest.raises(ValueError, match="type"):
        SBOMComponent(
            name="numpy", version="1.0", type="BUNDLE_OF_JOY"
        )


# --------------------------------------------------------------------------- #
# License rendering
# --------------------------------------------------------------------------- #


def test_single_token_license_renders_under_id():
    c = SBOMComponent(name="x", version="1", licenses=("MIT",))
    cdx = c.to_cyclonedx()
    assert cdx["licenses"] == [{"license": {"id": "MIT"}}]


def test_compound_spdx_expression_renders_under_expression():
    """SPDX compound expressions (AND/OR/WITH) MUST render under
    the CycloneDX ``expression`` field — using ``license.id`` for
    a compound expression fails CycloneDX schema validation."""
    c = SBOMComponent(
        name="x", version="1",
        licenses=("BSD-3-Clause AND MIT",),
    )
    cdx = c.to_cyclonedx()
    assert cdx["licenses"] == [
        {"expression": "BSD-3-Clause AND MIT"}
    ]


def test_no_license_with_textual_description_falls_through_to_name():
    c = SBOMComponent(
        name="x", version="1",
        licenses=(),
        description="proprietary, see LICENSE.txt",
    )
    cdx = c.to_cyclonedx()
    assert cdx["licenses"] == [
        {"license": {"name": "proprietary, see LICENSE.txt"}}
    ]


# --------------------------------------------------------------------------- #
# Writer
# --------------------------------------------------------------------------- #


def test_write_cyclonedx_bom_round_trips(tmp_path):
    """Writing then re-reading must produce a structurally
    equivalent dict."""
    out = tmp_path / "out.cdx.json"
    bom = generate_cyclonedx_bom(components=[
        SBOMComponent(name="numpy", version="1.0", licenses=("BSD-3-Clause",)),
    ])
    write_cyclonedx_bom(bom, out)
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n")  # trailing newline for diff-friendly snapshots
    parsed = json.loads(text)
    assert parsed["components"][0]["name"] == "numpy"


def test_render_text_uses_sorted_keys_and_two_space_indent():
    bom = generate_cyclonedx_bom()
    text = render_cyclonedx_bom_text(bom)
    # Sanity: the output is human-readable JSON.
    parsed = json.loads(text)
    assert parsed == bom
    # First component key should be sorted alphabetically — i.e.
    # `bomFormat` comes before `components` in the JSON ordering.
    assert text.index('"bomFormat"') < text.index('"components"')


# --------------------------------------------------------------------------- #
# Audit-fix regression pins (post-v0.7.x critical-audit pass)
# --------------------------------------------------------------------------- #


def test_audit_fix_empty_license_string_is_rejected_at_construction():
    """Audit Finding 4: an empty / whitespace-only license string
    used to render as ``{"license": {"id": ""}}`` — schema-invalid
    CycloneDX 1.5. Now rejected at SBOMComponent construction so
    the manifest can't be built with an invalid license entry."""
    with pytest.raises(ValueError, match="non-empty"):
        SBOMComponent(name="x", version="1", licenses=("",))
    with pytest.raises(ValueError, match="non-empty"):
        SBOMComponent(name="x", version="1", licenses=("   ",))
    with pytest.raises(ValueError, match="non-empty"):
        SBOMComponent(name="x", version="1", licenses=("MIT", ""))


def test_audit_fix_legacy_license_field_is_resolved():
    """Audit Finding 5: ``_resolve_license`` used to only read
    ``License-Expression`` (PEP 639); packages that ship only the
    legacy ``License:`` PEP 314 field would silently emit a row
    with no license, breaking the procurement-gate manifest.

    pyyaml is a real-world example: it ships ``License: MIT`` in
    its metadata and no License-Expression. Verify the legacy
    field is now consulted as a fallback.
    """
    from symbolu_robotics.bcvf_autonomous.safety_case.sbom.generator import (
        _resolve_license,
    )
    # pyyaml is a runtime test dependency we know is installed.
    licenses = _resolve_license("pyyaml")
    assert licenses, (
        "_resolve_license should fall back to the legacy License: "
        "field when License-Expression is absent — pyyaml ships "
        "only the legacy field"
    )
    # The legacy field's value is "MIT" for pyyaml.
    assert any("MIT" in lic for lic in licenses)


def test_audit_fix_resolve_license_prefers_curated_map_over_legacy():
    """The resolution order is: License-Expression → curated map
    → legacy License. A maintainer override in the curated map
    must beat the free-form legacy field — this is how a package
    with a non-standard License: value still gets a clean SPDX
    id in the manifest."""
    from unittest import mock
    from symbolu_robotics.bcvf_autonomous.safety_case.sbom import generator
    fake_meta = {"License-Expression": None, "License": "Free-form text"}
    with mock.patch.object(
        generator.importlib.metadata, "metadata", return_value=fake_meta
    ), mock.patch.object(
        generator, "_KNOWN_LICENSES", {"pkg": ("Apache-2.0",)}
    ):
        assert generator._resolve_license("pkg") == ("Apache-2.0",)


def test_spdx_with_expression_renders_under_expression_field():
    """Audit Finding 9 (coverage gap): a single license with an
    SPDX exception (e.g. ``Apache-2.0 WITH LLVM-exception``)
    contains ``WITH`` and is therefore an SPDX expression — must
    render under the CycloneDX ``expression`` key, not
    ``license.id``. Real ecosystem patterns: LLVM, OpenJDK."""
    c = SBOMComponent(
        name="x", version="1",
        licenses=("Apache-2.0 WITH LLVM-exception",),
    )
    cdx = c.to_cyclonedx()
    assert cdx["licenses"] == [
        {"expression": "Apache-2.0 WITH LLVM-exception"}
    ]


def test_spdx_compound_or_expression_renders_under_expression():
    """Single OR (without surrounding parens) — also a compound."""
    c = SBOMComponent(
        name="x", version="1",
        licenses=("BSD-3-Clause OR MIT",),
    )
    cdx = c.to_cyclonedx()
    assert cdx["licenses"] == [{"expression": "BSD-3-Clause OR MIT"}]
