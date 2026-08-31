"""The generic, policy-family-agnostic authority core.

Nothing in this subpackage imports, names, or branches on any policy family.
Family semantics arrive exclusively through a registered
:class:`~ugence_policy_authority.core.adapters.PolicyFamilyAdapter`, so a second
policy family is added by registering a second adapter — with no change to
issuance, signing, registry, resolution, or revocation code.

An automated AST test (``tests/packaging/test_core_adapter_boundary.py``)
enforces this boundary.
"""
