"""Manifest loader + schema validator + readiness gate for Primitive-Sequence Recovery.

Validates frozen artifacts against the JSON Schemas in ./schemas/ (dependency-free
subset validator), verifies sha256 hashes against the manifest, checks referential
integrity across artifacts, and decides READY vs NOT_READY. This module ONLY validates —
it computes no scores, loads no embeddings, calls no network/LLM, and reads no real data
unless a caller points it at a frozen directory. Stage A is not imported.

READY (per REAL_INPUT_FREEZE_PLAN.md / SCHEMA_SPECIFICATION.md) requires: all required
files present; schemas valid; hashes match; >=3 realizations; independence declared for
every realization pair; realization atom_content total over the assignment atoms; word
IDs referenced by meanings/distractors exist; distractor candidates exist; realizer
deterministic and offline; and manifest.status == "READY".
"""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

REQUIRED_ARTIFACTS = {
    "assignment": "assignment.json",
    "word_list": "word_list.json",
    "meaning_reference": "meaning_reference.json",
    "distractors": "distractors.json",
    "realizer": "realizer.json",
    "run_params": "run_params.json",
}
# manifest hash field -> artifact filename
_HASH_FIELDS = {
    "assignment_hash": "assignment.json",
    "word_hash": "word_list.json",
    "meaning_hash": "meaning_reference.json",
    "distractor_hash": "distractors.json",
    "realizer_hash": "realizer.json",
    "scramble_seed_hash": "run_params.json",
}
_FORBIDDEN_ASSIGNMENT_KEYS = ("glosses", "gloss", "polarity", "coordinates", "vectors",
                              "embeddings", "operators", "phonetics", "realization",
                              "content", "meaning", "meanings")


# --------------------------------------------------------------------- io ------
def load_json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_schema(name: str) -> dict:
    return load_json(SCHEMA_DIR / name)


# ----------------------------------------- dependency-free JSON-schema subset --
_PY = {"object": dict, "array": list, "string": str, "integer": int,
       "number": (int, float), "boolean": bool, "null": type(None)}


def _type_ok(value, t) -> bool:
    if isinstance(t, list):
        return any(_type_ok(value, tt) for tt in t)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "boolean":
        return isinstance(value, bool)
    py = _PY.get(t)
    return isinstance(value, py) if py is not None else True


def _validate(value, schema, path, errors):
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in {schema['enum']}")
    if "type" in schema and not _type_ok(value, schema["type"]):
        errors.append(f"{path}: type {schema['type']} violated by {type(value).__name__}")
        return
    if "minimum" in schema and isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if schema.get("uniqueItems") and len(value) != len({json.dumps(v, sort_keys=True) for v in value}):
            errors.append(f"{path}: items not unique")
        if "items" in schema:
            for i, item in enumerate(value):
                _validate(item, schema["items"], f"{path}[{i}]", errors)
    if isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required '{req}'")
        props = schema.get("properties", {})
        addl = schema.get("additionalProperties", True)
        for k, v in value.items():
            if k in props:
                _validate(v, props[k], f"{path}.{k}", errors)
            elif addl is False:
                errors.append(f"{path}: unexpected property '{k}'")
            elif isinstance(addl, dict):
                _validate(v, addl, f"{path}.{k}", errors)


def validate_schema(record, schema) -> dict:
    errors: list[str] = []
    _validate(record, schema, "$", errors)
    return {"valid": not errors, "errors": errors}


# ------------------------------------------------- per-artifact validators -----
def validate_assignment(record) -> dict:
    r = validate_schema(record, _load_schema("assignment.schema.json"))
    errors = list(r["errors"])
    # forbidden top-level semantic keys (defence-in-depth beyond additionalProperties)
    for k in record:
        if k.lower() in _FORBIDDEN_ASSIGNMENT_KEYS:
            errors.append(f"assignment: forbidden semantic field '{k}' (must be semantics-free)")
    varnas, atoms = record.get("varnas", []), record.get("atoms", [])
    if len(set(varnas)) != len(varnas):
        errors.append("assignment: duplicate varṇa IDs")
    if len(set(atoms)) != len(atoms):
        errors.append("assignment: duplicate atom IDs")
    tau = record.get("tau", {})
    for v in varnas:
        if v not in tau:
            errors.append(f"assignment: tau not total (missing varṇa '{v}')")
    atomset = set(atoms)
    for v, a in tau.items():
        if v not in varnas:
            errors.append(f"assignment: tau references unknown varṇa '{v}'")
        if a not in atomset:
            errors.append(f"assignment: tau references unknown atom '{a}'")
    return {"valid": not errors, "errors": errors}


def validate_realization(record) -> dict:
    return validate_schema(record, _load_schema("realization.schema.json"))


def validate_word_list(record) -> dict:
    r = validate_schema(record, _load_schema("word_list.schema.json"))
    errors = list(r["errors"])
    ids = [w.get("word_id") for w in record.get("words", [])]
    if len(set(ids)) != len(ids):
        errors.append("word_list: duplicate word_id")
    return {"valid": not errors, "errors": errors}


def validate_meaning_reference(record) -> dict:
    return validate_schema(record, _load_schema("meaning_reference.schema.json"))


def validate_distractors(record) -> dict:
    return validate_schema(record, _load_schema("distractors.schema.json"))


def validate_realizer(record) -> dict:
    r = validate_schema(record, _load_schema("realizer.schema.json"))
    errors = list(r["errors"])
    # design invariants that must hold even for an unimplemented, frozen realizer
    if record.get("deterministic") is not True:
        errors.append("realizer: deterministic must be true")
    if record.get("offline_only") is not True:
        errors.append("realizer: offline_only must be true")
    return {"valid": not errors, "errors": errors}


def validate_run_params(record) -> dict:
    return validate_schema(record, _load_schema("run_params.schema.json"))


def validate_manifest(record) -> dict:
    return validate_schema(record, _load_schema("manifest.schema.json"))


# --------------------------------------------------- realization discovery -----
def _realization_files(frozen_dir: Path):
    return sorted(frozen_dir.glob("realization_*.json"))


# ------------------------------------------------------------- hash verify -----
def verify_hashes(manifest, frozen_dir) -> dict:
    frozen_dir = Path(frozen_dir)
    mismatches, missing = [], []
    for field, fname in _HASH_FIELDS.items():
        if field not in manifest:
            continue
        fp = frozen_dir / fname
        if not fp.exists():
            missing.append(fname)
            continue
        if sha256_file(fp) != manifest[field]:
            mismatches.append(fname)
    # realizations
    rhashes = manifest.get("realization_hashes", {})
    for rf in _realization_files(frozen_dir):
        try:
            rid = load_json(rf).get("realization_id")
        except Exception:
            mismatches.append(rf.name)
            continue
        if rid not in rhashes:
            missing.append(f"realization_hashes[{rid}]")
        elif sha256_file(rf) != rhashes[rid]:
            mismatches.append(rf.name)
    return {"ok": not mismatches and not missing, "mismatches": mismatches, "missing": missing}


# -------------------------------------------------- referential integrity ------
def check_referential_integrity(assignment, realizations, word_list, meanings, distractors) -> dict:
    reasons = []
    atoms = set(assignment.get("atoms", []))
    rids = [r.get("realization_id") for r in realizations]

    for r in realizations:
        content_atoms = set(r.get("atom_content", {}).keys())
        for a in atoms - content_atoms:
            reasons.append(f"realization '{r.get('realization_id')}' missing atom '{a}'")
        for a in content_atoms - atoms:
            reasons.append(f"realization '{r.get('realization_id')}' unknown atom '{a}'")

    word_ids = {w.get("word_id") for w in word_list.get("words", [])}
    excluded = {w.get("word_id") for w in word_list.get("words", []) if w.get("exclude_flag")}

    meaning_words = set()
    for m in meanings.get("meanings", []):
        wid = m.get("word_id")
        meaning_words.add(wid)
        if wid not in word_ids:
            reasons.append(f"meaning references unknown word '{wid}'")
        rr = m.get("realization_specific_reference", {})
        for rid in rids:
            if rid not in rr:
                reasons.append(f"meaning '{wid}' missing realization reference '{rid}'")
    for wid in word_ids - excluded:
        if wid not in meaning_words:
            reasons.append(f"word '{wid}' has no meaning")

    for wid, cands in distractors.get("assignments", {}).items():
        if wid not in word_ids:
            reasons.append(f"distractors reference unknown word '{wid}'")
        for c in cands:
            if c not in word_ids:
                reasons.append(f"distractor candidate '{c}' unknown (word '{wid}')")

    return {"ok": not reasons, "reasons": reasons}


def _independence_ok(manifest, realizations) -> bool:
    rids = [r.get("realization_id") for r in realizations]
    basis = manifest.get("independence_basis", {})
    keys = set(basis.keys())
    for a, b in itertools.combinations(sorted(rids), 2):
        if f"{a}|{b}" not in keys and f"{b}|{a}" not in keys:
            return False
    return len(rids) >= 2


# ------------------------------------------------------------- readiness -------
def _result(status, reasons, **kw):
    base = {"status": status, "reasons": reasons, "hashes_ok": False, "schema_ok": False,
            "references_ok": False, "realization_count": 0,
            "realization_independence_ok": False}
    base.update(kw)
    return base


def check_readiness(frozen_dir) -> dict:
    frozen_dir = Path(frozen_dir)
    reasons: list[str] = []

    man_path = frozen_dir / "manifest.json"
    if not man_path.exists():
        return _result("NOT_READY", ["manifest.json missing"])
    try:
        manifest = load_json(man_path)
    except Exception as e:  # noqa: BLE001
        return _result("NOT_READY", [f"manifest.json unreadable: {e}"])

    schema_ok = True

    vm = validate_manifest(manifest)
    if not vm["valid"]:
        schema_ok = False
        reasons += [f"manifest schema: {e}" for e in vm["errors"]]

    # required files present
    for name, fname in REQUIRED_ARTIFACTS.items():
        if not (frozen_dir / fname).exists():
            reasons.append(f"missing artifact: {fname}")

    # load + schema-validate each present artifact
    loaded = {}
    validators = {
        "assignment": ("assignment.json", validate_assignment),
        "word_list": ("word_list.json", validate_word_list),
        "meaning_reference": ("meaning_reference.json", validate_meaning_reference),
        "distractors": ("distractors.json", validate_distractors),
        "realizer": ("realizer.json", validate_realizer),
        "run_params": ("run_params.json", validate_run_params),
    }
    for key, (fname, fn) in validators.items():
        fp = frozen_dir / fname
        if not fp.exists():
            continue
        try:
            rec = load_json(fp)
        except Exception as e:  # noqa: BLE001
            schema_ok = False
            reasons.append(f"{fname} unreadable: {e}")
            continue
        loaded[key] = rec
        res = fn(rec)
        if not res["valid"]:
            schema_ok = False
            reasons += [f"{fname}: {e}" for e in res["errors"]]

    # realizations
    rfiles = _realization_files(frozen_dir)
    realizations = []
    for rf in rfiles:
        try:
            rec = load_json(rf)
        except Exception as e:  # noqa: BLE001
            schema_ok = False
            reasons.append(f"{rf.name} unreadable: {e}")
            continue
        realizations.append(rec)
        res = validate_realization(rec)
        if not res["valid"]:
            schema_ok = False
            reasons += [f"{rf.name}: {e}" for e in res["errors"]]
    realization_count = len(realizations)
    if realization_count < 3:
        reasons.append(f"fewer than 3 realizations (found {realization_count})")

    # hashes
    hv = verify_hashes(manifest, frozen_dir)
    hashes_ok = hv["ok"]
    if hv["missing"]:
        reasons.append(f"hash: missing {hv['missing']}")
    if hv["mismatches"]:
        reasons.append(f"hash: mismatch {hv['mismatches']}")

    # referential integrity (only if the core artifacts loaded)
    references_ok = False
    if all(k in loaded for k in ("assignment", "word_list", "meaning_reference", "distractors")):
        ri = check_referential_integrity(loaded["assignment"], realizations,
                                         loaded["word_list"], loaded["meaning_reference"],
                                         loaded["distractors"])
        references_ok = ri["ok"]
        reasons += ri["reasons"]
    else:
        reasons.append("referential integrity: core artifacts missing")

    # independence
    independence_ok = _independence_ok(manifest, realizations) if realizations else False
    if not independence_ok:
        reasons.append("realization independence not declared for all pairs")

    # execution readiness: READY must never depend on an implicit/absent model. A frozen
    # but unimplemented realizer (or a disabled run) is a hard block, independent of hashes.
    rz = loaded.get("realizer")
    if rz is not None:
        if rz.get("status") != "IMPLEMENTED":
            reasons.append("realizer status is not IMPLEMENTED")
        if rz.get("execution_allowed") is not True:
            reasons.append("realizer execution_allowed is not true")
        if rz.get("implementation_present") is not True:
            reasons.append("realizer implementation_present is not true")
        if not rz.get("model_asset"):
            reasons.append("realizer model_asset missing (no implicit model permitted)")
        if not rz.get("model_sha256"):
            reasons.append("realizer model_sha256 missing (asset must be pinned)")
        # a concept realization requires an implemented concept resolver
        concept_needed = any(r.get("language") == "concept"
                             or r.get("meaning_encoder", {}).get("kind") in ("synset_id", "qid")
                             for r in realizations)
        if concept_needed and (not rz.get("concept_resolver")
                               or rz.get("concept_resolver_status") != "IMPLEMENTED"):
            reasons.append("concept resolver not implemented (required by concept realization)")
    rp = loaded.get("run_params")
    if rp is not None and rp.get("run_enabled") is not True:
        reasons.append("run_params run_enabled is not true")

    declared_ready = manifest.get("status") == "READY"
    if not declared_ready:
        reasons.append("manifest.status is not READY")

    ready = (schema_ok and hashes_ok and references_ok and independence_ok
             and realization_count >= 3 and declared_ready and not reasons)
    status = "READY" if ready else "NOT_READY"
    return _result(status, reasons, hashes_ok=hashes_ok, schema_ok=schema_ok,
                   references_ok=references_ok, realization_count=realization_count,
                   realization_independence_ok=independence_ok)
