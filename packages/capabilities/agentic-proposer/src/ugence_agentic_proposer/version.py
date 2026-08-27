"""Single source of truth for the ugence-agentic-proposer distribution version.

0.1.0 freezes the S1 public-API snapshot (I6, I8):
``docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md``'s full H3 surface — the eight
canonical contracts, the two nested public shapes, all ten ratified enums, the five
builders, the two equation functions, the two identity functions, the three
verifiers, the one exception this package defines, and the four ratified
constants — is now the exported, drift-tested public API (``public_api.json``,
``tests/test_public_api.py``). See ``CHANGELOG.md`` for what is frozen at this
version and what remains deferred to S2 (Part J).
"""
__version__ = "0.1.0"
