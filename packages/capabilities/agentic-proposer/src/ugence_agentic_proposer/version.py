"""Single source of truth for the ugence-agentic-proposer distribution version.

0.3.0 is the S2-B Reasoning Strategy Permission release. It adds five names to the
curated surface — ``ReasoningStrategy``, ``StrategyPolicyResolver``,
``StrategyPolicyRequest``, ``StrategyPolicyResponse`` and
``verify_strategy_permission`` — taking ``public_api.json`` from forty-six to
fifty-one, in the **same change set** as the vocabulary, the four new contract fields,
the retyped ``ProposerProcessRecord.declared_strategy``, the changed builder
signatures, the replay function and the tests (`S2B-S1-Q7=A`, on the I8 ordering OD-7
part 8 established: never ahead of the code and tests it describes).

`[G]` **Execution remains blocked, and this release does not unblock it**: no
strategy-permission policy family is registered with Policy Authority. The
``StrategyPolicyResolver`` protocol is injected and this package implements no
resolver, on the ``DomainEvaluationProvider`` precedent, so the capability is
implemented and testable against a stub but cannot run end to end today.

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
__version__ = "0.3.0"
