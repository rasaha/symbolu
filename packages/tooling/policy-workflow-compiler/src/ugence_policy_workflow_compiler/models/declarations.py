"""Source-declared semantics and authoritative-source linkage (`policy_pack.v2`).

These objects exist because a source policy can state governance facts the compiler
must never infer: that a workflow touches customer PII, that a node needs write
permission, that an action needs a particular tool, or that a contract must be a
specific version. The compiler preserves what is declared and leaves the rest
unresolved — it never defaults a governance claim into existence.

They are carried in a **sidecar** collection rather than as fields on the twenty
object models, and they are excluded from a `policy_pack.v1` pack's canonical view,
so every existing v1 digest and approval is unaffected. See
:mod:`ugence_policy_workflow_compiler.models.pack_view`.
"""

from __future__ import annotations

from typing import Optional, Tuple

from pydantic import Field

from .common import CompilerModel, ObjectType, PolicyObject


class DeclaredContractRef(CompilerModel):
    """A typed reference to a data contract, with the version the policy requires."""

    contract_id: str = Field(..., min_length=1)
    #: The contract version the source policy requires. Empty means the policy
    #: declared an id without a version — recorded as declared, never invented.
    contract_data_version: str = ""


class SemanticDeclaration(PolicyObject):
    """One source-declared semantic statement about one policy object.

    The declaration names its subject rather than living on it, so the twenty v1
    object models are untouched. Validation resolves every ``subject_object_id`` and
    rejects duplicates: which of two declarations governs one object is not a
    question the compiler may answer.
    """

    object_type: ObjectType = ObjectType.SEMANTIC_DECLARATION
    #: The object this declaration is about. Must resolve within the same pack.
    subject_object_id: str = Field(..., min_length=1)
    #: e.g. "this workflow may access customer PII".
    data_classification_refs: Tuple[str, ...] = ()
    #: Permission *intent* declared by the policy — never a granted permission.
    permission_intent_refs: Tuple[str, ...] = ()
    #: e.g. "this action requires Salesforce".
    required_tool_refs: Tuple[str, ...] = ()
    input_contract_refs: Tuple[DeclaredContractRef, ...] = ()
    output_contract_refs: Tuple[DeclaredContractRef, ...] = ()


class AuthoritativeSourceRef(CompilerModel):
    """The exact Policy Authority issuance this pack was compiled from (PA/PWC-X1).

    Carried as plain strings. This package never imports Policy Authority and never
    verifies a signature, key trust or revocation state — it attests **carriage, not
    authenticity**. Establishing that the issuance is genuine and current belongs to
    Policy Authority and to the composition root that derives this reference from a
    ``RESOLVED`` resolution.
    """

    # -- identity linkage --
    policy_family: str = Field(..., min_length=1)
    policy_id: str = Field(..., min_length=1)
    policy_version: str = Field(..., min_length=1)
    content_digest: str = Field(..., min_length=1)
    scope: str = Field(..., min_length=1)
    tenant_id: str = ""
    record_id: str = Field(..., min_length=1)
    policy_body_digest: str = Field(..., min_length=1)
    # -- evidence snapshot --
    issuing_authority_id: str = ""
    key_id: str = ""
    signature_alg: str = ""
    signature_b64: str = ""
    approving_authority_id: str = ""
    approval_ref: str = ""
    approval_digest: str = ""
    issued_at: str = ""
    authority_protocol: str = ""
    authority_protocol_version: str = ""
    # -- resolution context --
    resolved_as_of: str = ""
    #: True when the resolution described the past. A historical answer never
    #: implies current validity.
    historical: bool = False


__all__ = ["DeclaredContractRef", "SemanticDeclaration", "AuthoritativeSourceRef"]
