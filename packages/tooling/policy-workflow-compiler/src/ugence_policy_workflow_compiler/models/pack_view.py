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

from .policy_pack import PolicyPack


def canonical_pack_view(pack: PolicyPack) -> Dict[str, Any]:
    """Return the status-independent logical view of ``pack``.

    The lifecycle ``status`` is excluded so a pack keeps one identity across the
    ``APPROVED -> COMPILED`` transition: reproducibility is about content, not
    lifecycle position.

    The returned mapping is a fresh ``dict`` each call, so a caller may add its own
    framing keys (as the release payload does) without affecting any other caller.
    """
    data = pack.model_dump(mode="python")
    data.pop("status", None)
    return data


__all__ = ["canonical_pack_view"]
