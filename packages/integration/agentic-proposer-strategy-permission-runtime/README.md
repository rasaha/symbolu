# `ugence-agentic-proposer-strategy-permission-runtime`

The concrete Agentic Proposer `StrategyPolicyResolver`, backed by the shared
Ugence Policy Authority.

## Why this exists

The Agentic Proposer owns the resolver protocol, the request and response shapes,
the call and the six-check replay — and owns no policy, issues none, and holds no
registry. The Policy Authority issues, signs, registers, resolves and revokes
policy — and knows nothing about reasoning strategies. Neither may import the
other, and both bar it by test.

This distribution is the one component that speaks to both. With the
strategy-permission family package, it is what makes Reasoning Strategy Permission
run end to end.

## What it does

Given a `StrategyPolicyRequest`, it:

1. maps `(tenant_id, strategy_policy_ref)` to one exact `PolicyCoordinate`
   through an injected, immutable, defensively copied mapping;
2. pre-checks that the coordinate's scope and tenant agree with the request;
3. calls `resolve_policy` with the caller's `as_of`, an approval verifier, a
   request-derived expected tenant, and deny-always historical resolution;
4. accepts **only** a resolution — every other outcome raises;
5. checks the resolved artifact's exact type, and that the reference it is
   *signed* as answering to is the reference the request carried;
6. maps the permitted tokens onto `ReasoningStrategy` members, order preserved;
7. returns the four ratified response fields.

## The two things most easily got wrong

**The reference binding is signed, not merely configured.** An injected mapping
alone would leave the reference-to-policy binding as unsigned deployment state.
So the policy carries its own `strategy_policy_ref` inside the digest the
authority signed, and this resolver requires exact equality. The caller's value
never becomes authoritative — it must *match* a value the issuing authority
signed. Configuration locates the policy; the authority states which reference it
answers to.

**The expected tenant is derived from the request, never read off the
coordinate.** The authority compares `coordinate.tenant_id` against the value it
is handed, so passing the coordinate's own value would make that comparison
vacuous for *every* coordinate. This resolver passes the request's tenant for a
`TENANT`-scope coordinate and the canonical global component for a `GLOBAL` one —
in both branches a value the coordinate did not supply. It also pre-checks scope
and tenant itself, so the two checks are redundant rather than co-dependent.

`expected_reference_tenant_id` checks the reference's declared tenant identity,
never caller entitlement. **This resolver performs no caller authorization and
claims none.**

## Fail closed, with no degraded answer

| Condition | Raises |
|---|---|
| Unknown `(tenant, ref)` | `UnknownStrategyPolicyReferenceError` |
| Scope/tenant disagreement | `StrategyPolicyTenantScopeError` |
| Any non-resolution from the authority | `StrategyPolicyUnresolvedError`, cause on `.reason` |
| Resolved artifact is not exactly this family's | `StrategyPolicyArtifactError` |
| Signed reference ≠ the request's | `StrategyPolicyReferenceBindingError` |
| A stored token outside the vocabulary | `StrategyPolicyVocabularyError` |

The single organising rule is that a response is produced **only** when the
authority answered with a resolution. That covers the authority's whole reason
enumeration by construction rather than by this package remembering to enumerate
it.

### The reason token discipline

A `PolicyResolutionReason` reaches a caller through `.reason` and **through
nothing else** — never interpolated into a message. This is not cosmetic. The
Agentic Proposer's refusal guard uppercases text and tests substring containment,
and its reserved authority vocabulary contains `EXPIRED`, `UNSUPPORTED` and
`SUPPORTED`: the reason `EXPIRED` is a reserved term verbatim, and
`SUPERSESSION_REFERENCE_UNSUPPORTED` contains two of them. Interpolating the
authority's own reason into a message would make this package emit reserved
authority vocabulary without anyone choosing to.

## What it deliberately does not do

| Not done | Why |
|---|---|
| Authorize anything | Permission grants no compute, tools, evidence access or consequential execution. That stays with Risk Authority, ActionGate and Decision Authority. |
| Let `case_ref` select | It is correlation and audit context. Letting it select would be per-invocation authorization; permission is role-level. |
| Read a clock | `as_of` is the caller's, passed through verbatim. |
| Accept a historical answer | Historical resolution stays at deny-always. |
| Default an approval verifier | One is required at construction. Without it, an approval withdrawn after issuance would still resolve. |
| Set a `verified` boolean | A boolean a resolver sets is the resolver asserting its own trustworthiness. A response existing at all is the evidence. |
| Open a socket, touch storage, load a plugin | The reachable coordinate set is injected configuration, not something this package resolves for itself. |

## What a successful call proves — and what it does not

Under the configured trust roots, at the caller's explicit `as_of`: the artifact
was signed by an authorized, entitled, un-revoked key over exactly this canonical
body; approval evidence verified and still verifies; the lifecycle and effective
period admit it; and no verified revocation applies.

It proves nothing about whether the permitted set is wise, correct or lawful. It
establishes nothing about private reasoning. It does not prove that any declared
procedure was *executed*. It creates no compute authorization and no execution
authority. And it cannot establish that this resolver is honest — the reference
echo is a correlation check, and a resolver that wished to mislead would echo back
what it was handed while resolving something else.

## Wiring

```python
from ugence_agentic_proposer_strategy_permission_runtime import (
    build_strategy_policy_resolver,
)

resolver = build_strategy_policy_resolver(
    reference_map={("tenant-1", "policy-authority/strategy-permission/reconciliation"):
                   coordinate},
    registry=registry,
    signature_verifier=key_ring,
    approval_verifier=approval_verifier,   # required; no default is supplied
    adapters=adapters,                     # the family adapter is registered for you
)
```

Trust anchors, the registry and the approval verifier remain the composition
root's to choose. The helper supplies none of them and no default for any of
them: an unconfigured deployment must fail to construct, never quietly resolve
against nobody's approval.

## Owner rulings recorded against this package

Two questions were put to the owner during review of the change set that
introduced this distribution, and answered `SURFACE=B ROLE_LOOKUP=A`.

**`SURFACE=B` — the curated surface is exactly the ratified three.** An earlier
draft also exported `with_strategy_permission_adapter` and
`HISTORICAL_RESOLUTION`. The ratified surface is §8's delta table, whose runtime
row names the resolver, its error family and **a** composition helper — singular,
where the same table uses plurals for the family package's categories — and no
constant in any row. Both names are now internal: not in `__all__`, and not
re-exported from the package at all, since a name sitting outside `__all__` while
still resolving on the package would look like surface without being it. Each
lives in the module that owns it, and `build_strategy_policy_resolver` is the
supported way to reach the first. No behaviour changed.

**`ROLE_LOOKUP=A` — the role lookup is an acknowledged, test-tree-only
exemption.** The ratified end-to-end proof must construct a role contract,
because the proposer's own builder and its replay both take one; the proposer's
repository-wide scan reads raw file text and refuses the role-projection
substrings everywhere outside that capability; and editing the proposer is barred.
The fixture module therefore looks the class up by an assembled name.

That is an accommodation of the guard, not a defeat of it: nothing about the role
projection escapes here — no field is re-declared and no semantics duplicated —
one class is looked up and handed straight back to the proposer's own builder.

**Owner rider: the exemption is strictly test-tree-only.** Four guards in
`tests/test_import_boundary.py` enforce that, and each answers a different
question, because no one of them answers all three:

| Guard | What it establishes |
|---|---|
| The source imports exactly `ReasoningStrategy`, `StrategyPolicyRequest` and `StrategyPolicyResponse` from the proposer, and never by star-import | It **cannot construct** a role, nor type-check one: it cannot name the type |
| Every parameter the source declares is a closed, enumerated set | It **cannot handle** a role — which a name scan cannot establish, since a role could arrive through a parameter called anything |
| No defined name, referenced name, attribute or message literal in the source contains `role` | It never **names** one |
| The fixture module still performs the lookup | The exemption is **actually exercised**, so it cannot stand unused after its reason has gone |

Both of the first two were mutation-tested when they were written — a parameter
added to the resolver and the role contract imported into the source each make
the corresponding guard fail — so they are known to bite rather than assumed to.

`[G]` Recorded for whoever reads this next: a raw-text scan is weaker than it
looks — string assembly steps around it, and that is now demonstrated in-tree.

`[R]` **Any strengthening of the Agentic Proposer's raw-text scan is deferred to a
separately authorized Agentic Proposer change set and is not authorized here.**
That includes `S2B-PF-G=B`'s `0.3.1` boundary hardening, which authorizes the
resolver-boundary change and nothing adjacent to it.

## Tests

```
python -m pytest packages/integration/agentic-proposer-strategy-permission-runtime/tests -q
```

- `test_resolution.py` — mapping exactness, request-derived tenant, `case_ref`,
  `as_of`, and the fail-closed matrix, all against the real authority.
- `test_end_to_end.py` — a real policy, a real resolver, a real advisory, and the
  six-check replay with each check failing independently.
- `test_import_boundary.py` — what this distribution may import, measured.
- `test_no_authority_claimed.py` — no compute claim, no lifecycle authority, no
  reserved term in any name or message, and the reason-token discipline.

## Distribution verification

```
python packages/integration/agentic-proposer-strategy-permission-runtime/verify_agentic_proposer_strategy_permission_runtime_distribution.py
```

Builds the wheel, installs it into a clean venv with no monorepo path, and
exercises the resolver against a genuinely issued and signed policy there.
