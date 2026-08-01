"""Dependency-free validator for the ActionGate policy schema library.

Implements the subset of JSON Schema draft 2020-12 used by these schemas — enough
to validate policy packages and business rules without the optional ``jsonschema``
dependency. If ``jsonschema`` IS installed, ``validate_with_jsonschema`` uses it as
an independent cross-check. Supports cross-file ``$ref`` resolution across the
sibling ``*.schema.json`` files.

CLI:
    python3 validate.py examples/prod_database_delete.policy.json
    python3 validate.py --package examples/prod_database_delete.package.json
"""

from __future__ import annotations

import json
import os
import re
import sys

SCHEMA_DIR = os.path.dirname(os.path.abspath(__file__))

_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool, "null": type(None),
}


def load_registry(schema_dir: str = SCHEMA_DIR) -> dict:
    """Load every *.schema.json, indexed by bare filename (used for $ref bases)."""
    reg = {}
    for name in sorted(os.listdir(schema_dir)):
        if name.endswith(".schema.json"):
            with open(os.path.join(schema_dir, name)) as fh:
                reg[name] = json.load(fh)
    return reg


def _match_type(value, t: str) -> bool:
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[t])


def _resolve(ref: str, current_doc: dict, registry: dict):
    base, _, pointer = ref.partition("#")
    doc = registry[base] if base else current_doc
    node = doc
    for token in [p for p in pointer.split("/") if p != ""]:
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[token]
    return node, doc


def validate(instance, schema, registry: dict, current_doc=None, path="$") -> list:
    """Return a list of human-readable validation errors ([] means valid)."""
    if current_doc is None:
        current_doc = schema
    errs: list = []
    if schema is True or schema == {}:
        return errs
    if schema is False:
        return [f"{path}: schema is false (nothing valid)"]

    if "$ref" in schema:
        target, doc = _resolve(schema["$ref"], current_doc, registry)
        return validate(instance, target, registry, doc, path)

    for combinator in ("allOf",):
        if combinator in schema:
            for sub in schema[combinator]:
                errs += validate(instance, sub, registry, current_doc, path)

    for combinator in ("oneOf", "anyOf"):
        if combinator in schema:
            passes = sum(
                not validate(instance, sub, registry, current_doc, path)
                for sub in schema[combinator])
            if combinator == "oneOf" and passes != 1:
                errs.append(f"{path}: matched {passes} of oneOf (need exactly 1)")
            if combinator == "anyOf" and passes < 1:
                errs.append(f"{path}: matched none of anyOf (need >=1)")

    if "type" in schema:
        types = schema["type"]
        types = [types] if isinstance(types, str) else types
        if not any(_match_type(instance, t) for t in types):
            errs.append(f"{path}: expected type {types}, got {type(instance).__name__}")
            return errs

    if "const" in schema and instance != schema["const"]:
        errs.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} not in enum {schema['enum']}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errs.append(f"{path}: string shorter than minLength {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errs.append(f"{path}: {instance!r} does not match pattern {schema['pattern']}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append(f"{path}: {instance} < minimum {schema['minimum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errs.append(f"{path}: array shorter than minItems {schema['minItems']}")
        if "items" in schema:
            for i, item in enumerate(instance):
                errs += validate(item, schema["items"], registry, current_doc,
                                 f"{path}[{i}]")

    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in instance:
                errs.append(f"{path}: missing required property '{req}'")
        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            errs.append(f"{path}: fewer than minProperties {schema['minProperties']}")
        addl = schema.get("additionalProperties", True)
        for key, val in instance.items():
            if key in props:
                errs += validate(val, props[key], registry, current_doc,
                                 f"{path}.{key}")
            elif addl is False:
                errs.append(f"{path}: additional property '{key}' not allowed")
            elif isinstance(addl, dict):
                errs += validate(val, addl, registry, current_doc, f"{path}.{key}")
    return errs


def validate_file(instance_path: str, *, package: bool = False) -> list:
    registry = load_registry()
    schema_name = ("policy_package.schema.json" if package
                   else "actiongate_policy.schema.json")
    with open(instance_path) as fh:
        instance = json.load(fh)
    return validate(instance, registry[schema_name], registry,
                    registry[schema_name])


def validate_with_jsonschema(instance_path: str, *, package: bool = False):
    """Optional independent cross-check when jsonschema is installed."""
    try:
        import jsonschema
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except Exception:
        return None
    reg = load_registry()
    resources = [(v.get("$id", k), Resource.from_contents(v)) for k, v in reg.items()]
    registry = Registry().with_resources(
        [(k, r) for k, r in resources]).with_resources(
        [(k, r) for k, r in [(k, Resource.from_contents(reg[k])) for k in reg]])
    schema_name = ("policy_package.schema.json" if package
                   else "actiongate_policy.schema.json")
    with open(instance_path) as fh:
        instance = json.load(fh)
    validator = Draft202012Validator(reg[schema_name], registry=registry)
    return [e.message for e in validator.iter_errors(instance)]


def main(argv) -> int:
    package = "--package" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print("usage: validate.py [--package] <instance.json>")
        return 2
    errors = validate_file(args[0], package=package)
    if errors:
        print(f"INVALID: {args[0]}")
        for e in errors:
            print("  -", e)
        return 1
    print(f"VALID: {args[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
