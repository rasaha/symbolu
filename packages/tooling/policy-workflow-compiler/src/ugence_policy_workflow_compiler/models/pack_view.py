"""The single canonical logical view of a policy pack.

Two digests are computed over a pack, in two different modules:

* :func:`ugence_policy_workflow_compiler.approval.records.compute_pack_digest` —
  what a :class:`HumanApprovalRecord` binds to.
* ``compiler.release._pack_logical`` — the pack's contribution to a compiled
  release's structural digest.

Both must mean *exactly* the same thing by "the pack's logical content". They were
previously two independent implementations that happened to agree, each dropping
``status`` on its own. Any future divergence between them — for example a schema
gate that one learns and the other does not — would silently invalidate every
approval bound to every existing pack, and would surface much later as an
"approval digest does not match the pack" refusal far from its cause.

This module is that one definition. Nothing else may reconstruct it.
"""

from __future__ import annotations

from typing import Any, Dict

from .common import SCHEMA_VERSION_V2
from .policy_pack import PolicyPack

#: Pack fields that exist only in ``policy_pack.v2``. They are excluded from a v1
#: pack's canonical view so that every ``policy_pack.v1`` digest — and therefore
#: every approval bound to one — is byte-identical to what it was before v2 existed.
#:
#: This is an explicit, reviewable list rather than "prune whatever is empty":
#: pruning by emptiness would silently drop a declared-but-empty value, and adding a
#: future field would change v1 digests the moment someone forgot this file.
V2_ONLY_PACK_FIELDS = frozenset({"semantic_declarations", "authoritative_source"})


def canonical_pack_view(pack: PolicyPack) -> Dict[str, Any]:
    """Return the status-independent, schema-gated logical view of ``pack``.

    The lifecycle ``status`` is excluded so a pack keeps one identity across the
    ``APPROVED -> COMPILED`` transition: reproducibility is about content, not
    lifecycle position.

    ``policy_pack.v2`` fields are included only for a v2 pack. A v1 pack that
    declares them is **refused** by validation (``V2_FIELD_IN_V1_PACK``) rather than
    quietly pruned here — a field that is present, reviewed, approved and then
    silently excluded from the digest is worse than one either accepted or rejected.
    The pruning below is therefore only ever reached for a v1 pack that carries
    nothing to prune; it exists so the v1 canonical bytes are identical by
    construction rather than by the absence of a caller mistake.

    The returned mapping is a fresh ``dict`` each call, so a caller may add its own
    framing keys (as the release payload does) without affecting any other caller.
    """
    data = pack.model_dump(mode="python")
    data.pop("status", None)
    if pack.schema_version != SCHEMA_VERSION_V2:
        for field in V2_ONLY_PACK_FIELDS:
            data.pop(field, None)
    return data


__all__ = ["canonical_pack_view", "V2_ONLY_PACK_FIELDS"]
