"""Assert the P3E audit records use only canonical container-gate identifiers.

The canonical set and the deprecated aliases are defined by
``docs/audits/ugence_governance_studio_p3e/CONTAINER_GATE_DEFINITION.json``.
This check keeps the audit records from drifting back to a noncanonical spelling
(``C16-image``, ``C17-image``) or inventing an identifier outside the ratified
set, which is what produced the discrepancy this definition closes.

Exits 0 on conformance, 1 on any violation. Reads only; changes nothing.
"""
from __future__ import annotations

import json
import re
import sys

DEFINITION = "docs/audits/ugence_governance_studio_p3e/CONTAINER_GATE_DEFINITION.json"
RECORDS = [
    "docs/audits/ugence_governance_studio_p3e/CONTAINER_RUNTIME_CAPABILITY.json",
    "docs/audits/ugence_governance_studio_p3e/CONTAINER_COMPLETION_LIVE_STATE.json",
    "docs/audits/ugence_governance_studio_p3e/BASE_IMAGE_MIRROR_DECISION.json",
    # The ratified successor family must not name a historical identifier either:
    # a stray C-number there would silently reintroduce the correspondence that
    # both families' records explicitly disclaim.
    "docs/audits/ugence_governance_studio_p3e/CONTAINER_GATE_FAMILY.json",
]
# A gate identifier: C followed by digits, optionally a '-suffix' spelling.
_IDENT = re.compile(r"^C\d+(?:-[a-z]+)?$")


# Fields that exist to quote a superseded list verbatim. A deprecated alias is
# allowed inside these and nowhere else, so provenance stays readable without
# letting a noncanonical spelling back into live data.
HISTORICAL_KEYS = frozenset({
    "lists_as_recorded",
    "historical_lists_as_recorded",
    "previous_blocked_gates",
    "previous_not_executed",
})


def _walk(node, path="$", historical=False):
    """Yield (identifier, json_path, inside_historical_field) for the whole tree.

    The historical flag is positional and inherited down the subtree: an alias is
    excused by *where* it sits, never by appearing in a historical field
    elsewhere in the same document.
    """
    if isinstance(node, str):
        if _IDENT.match(node):
            yield node, path, historical
    elif isinstance(node, dict):
        for k, v in node.items():
            child = historical or k in HISTORICAL_KEYS
            if _IDENT.match(k):
                yield k, f"{path}.{k}", historical
            yield from _walk(v, f"{path}.{k}", child)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]", historical)


def main(definition: str = DEFINITION, records: list[str] | None = None) -> int:
    records = list(records or RECORDS)
    d = json.load(open(definition))
    canonical = set(d["canonical_identifiers"])
    aliases = {k: v["canonical"] for k, v in d["deprecated_aliases"].items()}

    fail: list[str] = []
    for path in records:
        doc = json.load(open(path))
        # The definition's own alias table and the record that quotes the historical
        # lists verbatim for traceability are allowed to name deprecated spellings;
        # every other occurrence is drift.
        allow_aliases = doc.get("schema") == "p3e-container-gate-definition.v1"

        for ident, where, historical in _walk(doc):
            if ident in canonical:
                continue
            if ident in aliases:
                if allow_aliases or historical:
                    continue
                fail.append(
                    f"{path}: uses deprecated alias '{ident}' at {where}; the "
                    f"canonical identifier is '{aliases[ident]}'"
                )
            else:
                fail.append(
                    f"{path}: uses '{ident}' at {where}, which is neither a "
                    f"canonical identifier nor a declared alias"
                )

    if fail:
        print("BLOCKING: P3E audit records use noncanonical gate identifiers.", file=sys.stderr)
        for f in fail:
            print("  FAIL " + f, file=sys.stderr)
        print(
            f"\nThe canonical set and the declared aliases are defined in {definition}.\n"
            "Use the canonical identifier, or extend the definition by owner ratification.",
            file=sys.stderr,
        )
        return 1

    print(
        f"gate identifiers conform ({len(canonical)} canonical, "
        f"{len(aliases)} deprecated alias(es), {len(records)} record(s) checked)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFINITION,
                  sys.argv[2:] or None))
