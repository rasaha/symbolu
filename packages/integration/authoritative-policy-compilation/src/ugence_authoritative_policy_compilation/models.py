"""What the root returns. Data only — it holds no authority and no key material."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ugence_policy_workflow_compiler.api import AuthoritativeSourceRef, PolicyPack


@dataclass(frozen=True)
class AuthoritativeCompilationDraft:
    """A pack built from a verified resolution, ready for human approval.

    Ruling CR-1: this root never accepts or brokers an approval. It returns the
    pack and the digest a reviewer must approve; the caller obtains that approval
    and compiles. Putting the root on the path between a reviewer and the artifact
    they approve is the seam the no-self-approval rule exists to protect.
    """

    #: The policy_pack.v2 pack, carrying the DERIVED authoritative source.
    pack: PolicyPack
    #: The structural digest a HumanApprovalRecord must bind to.
    pack_digest: str
    #: The reference derived from the resolution — never authored by a caller.
    authoritative_source: AuthoritativeSourceRef
    #: The resolution this draft came from, carried for audit. Opaque here.
    resolution: Any = None


__all__ = ["AuthoritativeCompilationDraft"]
