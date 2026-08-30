"""Single source of truth for the ugence-agentic-proposer distribution version.

0.3.1 is a patch release: **one failure class changed, no public name added, removed
or renamed** — the curated surface stays at fifty-one and ``public_api.json``'s
``symbols`` map is byte-identical to ``0.3.0``'s. It implements §10 step 7 of
``docs/architecture/S2B_STRATEGY_PERMISSION_POLICY_FAMILY_AND_RESOLVER_DESIGN.md``,
authorized by ``S2B-PF-G=B`` in
``docs/architecture/ADR_UGENCE_S2B_STRATEGY_PERMISSION_FAMILY_RATIFICATION.md`` as a
**separate** change set, never bundled with the two new integration packages.

`0.3.0` disclosed that ``_resolve_strategy_policy`` guarded the resolver **call** but
not the resolver's **answer**: a resolver returning a structurally alien object raised
``AttributeError`` from whichever ratified field was read first, outside H2 entirely.
The guard now spans the whole ratified response shape — the echo and the three fields
the permission test and the advisory stamping go on to read — so a response **missing
any ratified field** is refused as ``CrossContractViolationError``, with the original
error preserved as ``__cause__``. `S2B-S1-Q8=A` is untouched: **no new exception
type**, and H2 stays at five classes.

`[G]` **What the guard establishes is field PRESENCE, not field shape**, and the
difference is stated here rather than left to be discovered. A response carrying every
ratified field but a type-alien value in one of them still escapes H2 downstream — a
``permitted_strategies`` of ``5`` reaches the membership test and raises ``TypeError``
— as does an attribute that answers the guard and then raises on a later read, since
the callers re-read the response outside it. `[R]` These are a **different garbage
class** from the one `0.3.0` disclosed and `S2B-PF-G=B` ruled on, and closing them
would exceed that authorization; whether to close them is a new owner decision, not a
defect in this one.

`[R]` **The compatibility change, stated rather than implied.** A caller that
previously caught ``AttributeError`` around a builder call to detect a malformed
resolver answer no longer sees one from this path; it sees an H2 class. Nothing else
in the builders is newly caught, and a complete duck-typed response still constructs —
`S2B-S1-Q9=A` ratifies a Protocol, and this release does not narrow it to a nominal
type test.

`[G]` **Nothing else about the `0.3.0` disclosure changes.** Execution end to end
remains outside this package. `S2B-PF-G=B` authorizes this hardening and nothing
adjacent to it, so the four present-tense sites at design `§8.1` were **not** touched
by this release; they were corrected afterwards, under the separate owner ruling
`STALE_SITES=ALL_FOUR`, which is why the `0.3.0` block below now reads as a record of
that release rather than as a current fact.

0.3.0 is the S2-B Reasoning Strategy Permission release. It adds five names to the
curated surface — ``ReasoningStrategy``, ``StrategyPolicyResolver``,
``StrategyPolicyRequest``, ``StrategyPolicyResponse`` and
``verify_strategy_permission`` — taking ``public_api.json`` from forty-six to
fifty-one, in the **same change set** as the vocabulary, the four new contract fields,
the retyped ``ProposerProcessRecord.declared_strategy``, the changed builder
signatures, the replay function and the tests (`S2B-S1-Q7=A`, on the I8 ordering OD-7
part 8 established: never ahead of the code and tests it describes).

`[G]` **Execution was blocked at this release, and this release did not unblock
it**: no strategy-permission policy family was registered with Policy Authority when
`0.3.0` shipped. The ``StrategyPolicyResolver`` protocol is injected and this package
implements no resolver, on the ``DomainEvaluationProvider`` precedent, so at `0.3.0`
the capability was implemented and testable against a stub but could not run end to
end. **That statement is scoped to `0.3.0` and is no longer current**: the family
package and the concrete resolver landed afterwards, outside this distribution, as
`§10` steps 2–4 of
``docs/architecture/S2B_STRATEGY_PERMISSION_POLICY_FAMILY_AND_RESOLVER_DESIGN.md``.
This package still implements no resolver and registers nothing, which was never the
blocker and has not changed.

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
__version__ = "0.3.1"
