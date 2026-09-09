"""The curated public API is a committed artifact, not whatever ``api.py`` happens to hold.

This package calls ``ModelAuthority`` "the binding external contract". A binding contract
whose shape can change without anyone noticing is not one, so the shape is snapshotted and
compared: adding, removing or reshaping an exported name fails here until the snapshot is
regenerated deliberately.
"""

from __future__ import annotations

import json
import pathlib
import sys

import ugence_model_selection.api as api

ROOT = pathlib.Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "artifacts" / "public_api.json"

sys.path.insert(0, str(ROOT / "scripts"))
import public_api_snapshot  # noqa: E402


def test_the_public_api_matches_its_committed_snapshot():
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    current = public_api_snapshot.snapshot()

    added = sorted(set(current["fingerprints"]) - set(committed["fingerprints"]))
    removed = sorted(set(committed["fingerprints"]) - set(current["fingerprints"]))
    changed = sorted(
        name for name in set(current["fingerprints"]) & set(committed["fingerprints"])
        if current["fingerprints"][name] != committed["fingerprints"][name])

    assert not (added or removed or changed), (
        "the public API no longer matches artifacts/public_api.json.\n"
        f"  added:   {added}\n  removed: {removed}\n  changed: {changed}\n"
        "Regenerate deliberately:\n"
        "  PYTHONPATH=src python scripts/public_api_snapshot.py > artifacts/public_api.json")


def test_every_exported_name_actually_resolves():
    """``__all__`` may not promise a name the module does not have."""
    missing = [name for name in api.__all__ if not hasattr(api, name)]
    assert not missing, missing


def test_the_export_list_has_no_duplicates():
    assert len(api.__all__) == len(set(api.__all__))


def test_the_snapshot_count_matches_the_export_list():
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert committed["count"] == len(api.__all__) == len(committed["fingerprints"])


def test_the_deprecated_selection_aliases_are_the_authority_objects():
    """The README calls these compatibility aliases; identity is what makes that true.

    A copy would drift. These must be the same objects, so a consumer holding the old
    name and one holding the new name cannot observe different behaviour.
    """
    assert api.ModelSelector is api.ModelAuthority
    assert api.ModelSelectionService is api.ModelAuthorityService
    assert api.ModelAuthorizationPolicy is api.PolicyWeights
