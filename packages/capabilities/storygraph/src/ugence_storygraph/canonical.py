"""Deterministic canonicalization + digest (stdlib only).

The composite-threat detector must be *reproducible*: the same stream of events
must always yield the same findings and the same finding digests, on any machine,
in any process. That property is what lets a finding be replayed, pinned in a
test, and hash-chained into an audit log alongside the gate's own records.

We deliberately avoid a dependency on the reference gate's JCS module so this
package stays self-contained; the canonical form here is the standard
"sorted-keys, tight-separators UTF-8 JSON" form, which is sufficient for the
detector's own artifacts (it never needs byte-parity with the gate's action
hash — findings are *bound to* an action's identity, they do not recompute it).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_bytes(value: Any) -> bytes:
    """Canonical UTF-8 JSON: sorted keys, no insignificant whitespace.

    Rejects NaN/Infinity (``allow_nan=False``) so a finding can never carry a
    non-reproducible float.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any, *, domain: str = "CTD") -> str:
    """Domain-separated SHA-256 hex digest of a canonical value.

    ``domain`` is length-prefixed so digests computed for different purposes
    (findings, ledgers, ontology versions) never collide across domains.
    """
    dom = domain.encode("utf-8")
    frame = len(dom).to_bytes(4, "big") + dom + canonical_bytes(value)
    return "sha-256:" + hashlib.sha256(frame).hexdigest()
