"""Build corpus items from compact specs, and load the full corpus.

A spec selects an action-type core (core.CORES), optionally duplicates a critical
span into a redundancy set, appends realistic filler, and attaches provenance +
split + domain metadata. Anti-leakage: each spec's ``template_family`` is unique
to one split (distinct target/service per split), and the leakage test also checks
content hashes.
"""

from __future__ import annotations

from . import core
from .builders import REDUNDANT, filler, item, span
from .schema import HELDOUT


def build_from_spec(spec: dict):
    action_type = spec["action_type"]
    base, crit, lp = core.CORES[action_type](spec["target"], para=(spec["split"] == HELDOUT))
    units = list(crit)

    # optional redundancy: duplicate the first contrib-bearing critical span
    if spec.get("redundant"):
        src = next((u for u in crit if u.contrib and u.redundancy_set is None), None)
        if src is not None:
            rid = f"{src.id}_dup"
            units = [
                (u.__class__(**{**u.__dict__, "redundancy_set": "dup_set", "expected": REDUNDANT})
                 if u.id == src.id else u)
                for u in units
            ]
            units.append(src.__class__(**{**src.__dict__, "id": rid,
                                          "text": "Reconfirmed: " + src.text,
                                          "redundancy_set": "dup_set", "expected": REDUNDANT}))

    units.extend(filler(spec["item_id"], spec.get("fillers", ("justify", "history", "logs"))))
    return item(
        item_id=spec["item_id"], partition=spec["partition"], split=spec["split"],
        domain=spec["domain"], action_type=action_type,
        structure_family=spec["structure_family"], base=base, units=units,
        provenance=spec["provenance"], template_family=spec["template_family"],
        linked_pairs=lp)


def load_all():
    from .public import scenarios as pub
    from .authored import scenarios as auth
    items = [build_from_spec(s) for s in pub.SPECS] + [build_from_spec(s) for s in auth.SPECS]
    _validate(items)
    return items


def _validate(items):
    ids = [it.item_id for it in items]
    assert len(ids) == len(set(ids)), "duplicate item_id"
