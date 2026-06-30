"""B0 frozen-manifest loader, hash verifier, and readiness gate.

Loads `frozen/b0_frozen_artifacts.json`, recomputes and checks every pinned
sha256 BEFORE any run, validates a run record against `run_manifest_schema.json`,
and decides readiness. The readiness gate enforces the pre-registration:

  - the PRIMARY verdict-setting encoding is **T_embed** (embedding); the
    categorical encoding **T_cat** is sensitivity-only and can never be primary;
  - if the T_embed model is not frozen (status != "enabled" or no weights sha256),
    the gate is NOT_READY → the runner must refuse with NOT_RUN;
  - any pinned-hash mismatch is NOT_READY.

This module loads and verifies. It does NOT compute T-vs-P alignment, does NOT
emit a verdict, and makes no semantic claim. Stage A is untouched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

# repo root = .../experiments/varna_phonetic_alignment/manifest.py -> parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]
FROZEN_DIR = Path(__file__).resolve().parent / "frozen"
MANIFEST_PATH = FROZEN_DIR / "b0_frozen_artifacts.json"
SCHEMA_PATH = FROZEN_DIR / "run_manifest_schema.json"

# The PRIMARY, verdict-setting T-encoding (pre-reg §12). Frozen here so no caller
# can silently promote the categorical sensitivity encoding to primary.
PRIMARY_ENCODING = "embedding"
SENSITIVITY_ENCODING = "categorical"


# --------------------------------------------------------------- loading ------
def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_manifest(path: Path | str = MANIFEST_PATH) -> dict:
    """Load the §17 frozen-artifact manifest (raises on missing/invalid JSON)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_schema(path: Path | str = SCHEMA_PATH) -> dict:
    """Load the run-manifest JSON schema."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------- hash verify ----
def _pinned_paths(manifest: dict) -> dict[str, str]:
    """Collect {logical_name: (path, pinned_sha256)} from the manifest."""
    out = {}
    dd = manifest.get("design_doc")
    if dd:
        out["design_doc"] = (dd["path"], dd["sha256"])
    for name, rec in manifest.get("artifacts", {}).items():
        out[name] = (rec["path"], rec["sha256"])
    return out


def verify_hashes(manifest: dict, root: Path | str = REPO_ROOT) -> dict:
    """Recompute sha256 of every pinned artifact and compare to the manifest.

    Returns {ok, checked:{name:{path,expected,actual,match}}, mismatches:[names],
    missing:[names]}. A missing file or any mismatch => ok False.
    """
    root = Path(root)
    checked, mismatches, missing = {}, [], []
    for name, (rel, expected) in _pinned_paths(manifest).items():
        fp = root / rel
        if not fp.exists():
            missing.append(name)
            checked[name] = {"path": rel, "expected": expected, "actual": None, "match": False}
            continue
        actual = _sha256(fp)
        match = (actual == expected)
        checked[name] = {"path": rel, "expected": expected, "actual": actual, "match": match}
        if not match:
            mismatches.append(name)
    return {"ok": (not mismatches and not missing),
            "checked": checked, "mismatches": mismatches, "missing": missing}


# ------------------------------------------------------- embedding / encoding -
def embedding_frozen(manifest: dict) -> bool:
    """True iff the PRIMARY T_embed model is actually frozen (enabled + weights sha256)."""
    emb = manifest.get("embedding_model_T_embed", {})
    return (emb.get("status") == "enabled"
            and emb.get("enabled") is True
            and isinstance(emb.get("weights_sha256"), str)
            and len(emb.get("weights_sha256")) > 0)


def primary_encoding(manifest: dict | None = None) -> str:
    """The verdict-setting encoding is always 'embedding' (categorical is sensitivity)."""
    return PRIMARY_ENCODING


# ----------------------------------------------------------- readiness gate ---
# artifacts whose freeze is REQUIRED before any run (primary pipeline)
REQUIRED_ARTIFACTS = ("lexicon_wordformation", "iast_ipa_map", "feature_table",
                      "decision_rule", "run_manifest_schema")


def check_readiness(manifest: dict | None = None, root: Path | str = REPO_ROOT) -> dict:
    """Decide whether B0 may run. Pure gate — computes NO alignment.

    Returns {ready, reasons[], hashes, embedding_frozen, feature_source,
    primary_encoding}. `ready` is True only if every pinned hash matches AND the
    T_embed model is frozen AND all required artifacts are present.
    """
    if manifest is None:
        manifest = load_manifest()
    reasons = []
    hashes = verify_hashes(manifest, root)
    if not hashes["ok"]:
        if hashes["missing"]:
            reasons.append(f"missing artifacts: {hashes['missing']}")
        if hashes["mismatches"]:
            reasons.append(f"sha256 mismatch: {hashes['mismatches']}")

    present = set(manifest.get("artifacts", {}).keys())
    absent = [a for a in REQUIRED_ARTIFACTS if a not in present]
    if absent:
        reasons.append(f"required artifacts not pinned in manifest: {absent}")

    emb_ok = embedding_frozen(manifest)
    if not emb_ok:
        reasons.append("T_embed (primary §12 encoding) not frozen — categorical "
                       "T_cat is sensitivity-only and cannot substitute as primary")

    return {"ready": (hashes["ok"] and emb_ok and not absent),
            "reasons": reasons,
            "hashes": hashes,
            "embedding_frozen": emb_ok,
            "feature_source": manifest.get("feature_library", {}).get("primary_source"),
            "primary_encoding": primary_encoding(manifest)}


# --------------------------------- minimal dependency-free schema validation --
def validate_record(record: dict, schema: dict | None = None) -> dict:
    """Validate a run-record against the (subset of) JSON Schema we use.

    Supports: type(object/array/string/integer), required, const, enum, minimum,
    additionalProperties:false, properties, items. Returns {valid, errors[]}.
    No network, no third-party dependency. Used only when a run record exists —
    this module never fabricates one.
    """
    if schema is None:
        schema = load_schema()
    errors: list[str] = []
    _validate(record, schema, "$", errors)
    return {"valid": not errors, "errors": errors}


_TYPES = {"object": dict, "array": list, "string": str,
          "integer": int, "number": (int, float), "boolean": bool, "null": type(None)}


def _type_ok(value, t) -> bool:
    if isinstance(t, list):
        return any(_type_ok(value, tt) for tt in t)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "boolean":
        return isinstance(value, bool)
    py = _TYPES.get(t)
    return isinstance(value, py) if py is not None else True


def _validate(value, schema, path, errors):
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']}")
    if "type" in schema and not _type_ok(value, schema["type"]):
        errors.append(f"{path}: type {schema['type']} violated by {type(value).__name__}")
        return  # further checks assume the type held
    if "minimum" in schema and isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
    if isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required '{req}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = [k for k in value if k not in props]
            if extra:
                errors.append(f"{path}: unexpected properties {extra}")
        for k, v in value.items():
            if k in props:
                _validate(v, props[k], f"{path}.{k}", errors)
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            _validate(item, schema["items"], f"{path}[{i}]", errors)
