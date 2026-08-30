"""Drift coverage for the ratified base-image pin guard.

`BASE_IMAGE_MIRROR_DECISION.json` claimed this guard "was exercised against ten
drift scenarios ... blocks all nine drift cases". That was true of an ad-hoc run
and false of the repository: only the conforming-tree case was ever committed, so
nothing would catch a regression in the guard itself. These tests commit the nine
negative cases so the claim describes durable coverage.

Each case mutates a throwaway copy of the three inputs. Nothing here touches the
real `base-images.json`, `Dockerfile` or ratification record, and no gate is
executed or marked passed.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil

import pytest

from depaths import REPO

CI = os.path.join(REPO, "deployment", "governance-studio", "ci")
RECORD = os.path.join(REPO, "docs", "audits", "ugence_governance_studio_p3e",
                      "BASE_IMAGE_MIRROR_DECISION.json")
PINS = os.path.join(REPO, "deployment", "governance-studio", "base-images.json")
DOCKERFILE = os.path.join(REPO, "deployment", "governance-studio", "Dockerfile")

NODE = "sha256:f32b81066cde10a75dbac96646099533316d94bac4150c55da1636e1f0ffdc46"


@pytest.fixture(scope="module")
def guard():
    spec = importlib.util.spec_from_file_location(
        "verify_ratified_pins", os.path.join(CI, "verify_ratified_pins.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def tree(tmp_path):
    """A throwaway copy of the guard's three inputs."""
    for src, name in ((RECORD, "record.json"), (PINS, "pins.json"), (DOCKERFILE, "Dockerfile")):
        shutil.copy(src, tmp_path / name)
    return tmp_path


def _run(guard, tree):
    return guard.main(str(tree / "record.json"), str(tree / "pins.json"), str(tree / "Dockerfile"))


def _edit_json(path, fn):
    d = json.load(open(path, encoding="utf-8"))
    fn(d)
    json.dump(d, open(path, "w", encoding="utf-8"), indent=2)


def _edit_text(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert old in s, old
    open(path, "w", encoding="utf-8").write(s.replace(old, new))


# --- positive control ---------------------------------------------------------

def test_conforming_tree_passes(guard, tree):
    assert _run(guard, tree) == 0


# --- the nine drift cases -----------------------------------------------------

def test_base_images_repinned(guard, tree):
    _edit_json(tree / "pins.json",
               lambda d: d["base_images"][0].__setitem__("manifest_digest", "sha256:" + "0" * 64))
    assert _run(guard, tree) == 1


def test_dockerfile_repinned(guard, tree):
    _edit_text(tree / "Dockerfile", "@" + NODE, "@sha256:" + "1" * 64)
    assert _run(guard, tree) == 1


def test_dockerfile_from_unpinned(guard, tree):
    _edit_text(tree / "Dockerfile", "node:22-bookworm-slim@" + NODE, "node:22-bookworm-slim")
    assert _run(guard, tree) == 1


def test_base_image_substituted_in_dockerfile(guard, tree):
    _edit_text(tree / "Dockerfile", "node:22-bookworm-slim@", "alpine:22-bookworm-slim@")
    assert _run(guard, tree) == 1


def test_extra_unratified_image_added(guard, tree):
    def add(d):
        e = dict(d["base_images"][0]); e["repository"] = "library/busybox"; e["role"] = "extra"
        d["base_images"].append(e)
    _edit_json(tree / "pins.json", add)
    assert _run(guard, tree) == 1


def test_ratified_image_dropped(guard, tree):
    _edit_json(tree / "pins.json", lambda d: d.__setitem__(
        "base_images", [e for e in d["base_images"] if "node" not in e["repository"]]))
    assert _run(guard, tree) == 1


def test_amd64_child_digest_tampered(guard, tree):
    _edit_json(tree / "pins.json", lambda d: d["base_images"][0].__setitem__(
        "amd64_manifest_digest", "sha256:" + "2" * 64))
    assert _run(guard, tree) == 1


def test_ratification_record_digest_tampered(guard, tree):
    """Editing the record alone desynchronises it from the pins and is caught."""
    _edit_json(tree / "record.json", lambda d: d["authoritative_digests"]["images"][0].__setitem__(
        "manifest_digest", "sha256:" + "3" * 64))
    assert _run(guard, tree) == 1


def test_ratified_stage_list_altered(guard, tree):
    _edit_json(tree / "record.json", lambda d: d["authoritative_digests"]["images"][1].__setitem__(
        "dockerfile_stages", ["backend"]))
    assert _run(guard, tree) == 1


# --- the property the guard exists to enforce ---------------------------------

def test_a_repin_passes_only_when_the_record_is_edited_too(guard, tree):
    """The two-key property: pins and record must move together, by design.

    This is what makes a re-pin require owner re-ratification rather than a quiet
    edit — changing either side alone fails.
    """
    new = "sha256:" + "4" * 64
    _edit_json(tree / "pins.json",
               lambda d: d["base_images"][0].__setitem__("manifest_digest", new))
    assert _run(guard, tree) == 1                      # pins alone: refused
    _edit_text(tree / "Dockerfile", "@" + NODE, "@" + new)
    assert _run(guard, tree) == 1                      # pins + Dockerfile: still refused
    _edit_json(tree / "record.json", lambda d: d["authoritative_digests"]["images"][0].__setitem__(
        "manifest_digest", new))
    assert _run(guard, tree) == 0                      # only with the record edited
