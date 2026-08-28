"""Single source of truth for the ugence-agentic-proposer distribution version.

0.2.0 is the additive S2 public-surface release implementing OD-7, OD-8, OD-9 and
OD-10 (``docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md``). It adds seven names to the
curated surface — ``DomainEvaluationOutcome``, ``DomainEvaluationProvider``,
``DomainEvaluationRequest``, ``DomainEvaluationResponse``,
``DomainEvaluationProviderError``, ``verify_domain_evaluation`` and
``verify_deterministic_selection`` — taking ``public_api.json`` from thirty-nine to
forty-six, and removes C7's and C9's structural ceilings in the same change set that
introduces every replacement field, coupling validator, vocabulary member, protocol,
identity mirror, equation term and replay function (OD-7 part 8).

0.1.0 froze the S1-only surface: the eight canonical contracts, the two nested public
shapes, ten ratified enums, the five builders, the two equation functions, the two
identity functions, the three verifiers, the two exceptions this package defined, and
the four ratified constants. That surface remains exported unchanged; 0.2.0 removes no
name from it. See ``CHANGELOG.md`` for what this release implements and what remains
deferred to a later ruling — substantive multi-candidate ranking above all.
"""
__version__ = "0.2.0"
