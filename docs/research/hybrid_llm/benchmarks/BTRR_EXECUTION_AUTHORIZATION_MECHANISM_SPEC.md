# BTRR Execution-Authorization Mechanism — Proposal Spec (DRAFT, not approved)

**Status: `BTRR_EXEC_AUTH_MECHANISM_SPEC_DRAFT`.** This document is a *reviewable proposal only*. It
authorizes nothing, contains no token, signs no record, and changes no code. Adopting it is a separate,
owner-approved implementation task. Until then, execution stays `BTRR_EXECUTION_NOT_AUTHORIZED` and every
reserved seed remains fail-closed.

Provenance it must bind to: original preregistration `626a897a…` · Amendment 001 `9e6168f9…` ·
Amendment 002 `a84cc8ee…` · corrected implementation `e4dace0e…`. Preserved regardless of outcome:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `E1_TEMPORAL_TRANSFER_PARTIAL`, `KDA_VALIDATION_BLOCKED`.

## 1. Problem
`experiments/relational_reasoning_bounded_context/execution.py` ships `_AUTHORIZATION_TOKENS = {}` (empty)
by design, so `guard_seed` raises for every reserved seed. There is intentionally **no** way to authorize a
run. To ever produce scientific evidence (smoke → dev → final), a *legitimate* unlock path is required —
one that is auditable, fail-closed by default, non-bypassable, and impossible to trigger casually.

## 2. Design goals (acceptance criteria)
1. **Fail-closed default** — absent/invalid authorization ⇒ raise, exactly as today.
2. **Two-key** — a run needs BOTH an owner action recorded in git AND an operator secret supplied at
   runtime; neither alone suffices.
3. **No repo-resident live token** — the repository stores only a *hash*; the usable token never lands in
   git.
4. **Role isolation** — authorizing `smoke` must not authorize `development` or `final`; each role is
   signed independently.
5. **Protocol binding** — an authorization is valid only against the exact frozen protocol it was signed
   for; changing gates/config invalidates it (no "authorize, then quietly retune").
6. **No bypass flag** — no `authorized=True` parameter, no env var that flips the guard open, no way for a
   caller to self-authorize.
7. **Auditable** — who authorized, when, which role/seeds, against which protocol digest — all in git
   history.

## 3. Mechanism
Two artifacts, both required at guard time:

**(a) A committed, owner-signed authorization record** (new file, e.g.
`docs/research/hybrid_llm/benchmarks/BTRR_EXECUTION_AUTHORIZATION_RECORD.json`). Per role it carries:
`authorized` (bool), `authorized_by`, `date`, `scope_seeds`, `token_sha256` (hash of the plaintext token,
**not** the token), `protocol_lock_digest` (binds to the frozen protocol — reuse
`manifest.config_digest()`), and optional `expires_at`. "Signing" = the owner commits this file; the git
commit is the audit trail. Example shape (values are placeholders — no real hash is proposed here):

```json
{
  "schema": "btrr/execution_authorization_record/v1",
  "roles": {
    "smoke":       {"authorized": true,  "authorized_by": "<owner>", "date": "<iso8601>",
                    "scope_seeds": [8100], "token_sha256": "<sha256-of-plaintext>",
                    "protocol_lock_digest": "<manifest.config_digest()>", "expires_at": null},
    "development": {"authorized": false},
    "final":       {"authorized": false}
  }
}
```

**(b) An operator-supplied plaintext token** delivered out-of-band (secure channel, not git) and provided
at run time via env var `BTRR_EXEC_TOKEN` or the existing `authorization_token=` parameter. The owner
generates it, commits only its `sha256`, and hands the plaintext to whoever runs the pod.

### Guard algorithm (replaces the empty-registry lookup; same raise-before-any-side-effect contract)
```
guard_seed(seed, token=None):
    role = RESERVED_SEED_ROLES.get(seed)
    if role is None:                      return granted("non_reserved")   # fixtures / non-reserved
    record = load_signed_record()         # None if file absent
    if record is None:                    raise ExecutionNotAuthorized      # fail-closed default
    e = record.roles.get(role)
    if e is None or not e.authorized:     raise ExecutionNotAuthorized      # role not signed
    if seed not in e.scope_seeds:         raise ExecutionNotAuthorized
    if e.protocol_lock_digest != manifest.config_digest():
                                          raise ExecutionNotAuthorized      # protocol drifted since signing
    if e.expires_at and now() > e.expires_at:
                                          raise ExecutionNotAuthorized      # expired
    supplied = token or env("BTRR_EXEC_TOKEN")
    if supplied is None:                  raise ExecutionNotAuthorized      # operator key missing
    if sha256(supplied) != e.token_sha256:raise ExecutionNotAuthorized      # operator key wrong
    return granted(role)
```
`assert_generation_allowed` and every primitive stay wired to `guard_seed` unchanged, so the two-key check
runs at every scientific primitive (F1). No new public surface; the only behavioral change is *how*
`expected` is derived (from the signed record, gated by the operator secret) instead of a hardcoded map.

## 4. What stays unchanged
Gates, generator distributions, metrics, verdict precedence, single-checkpoint invariant, R1–R12
semantics, the frozen protocol/amendments, and the fail-closed *contract* of `guard_seed`. Fixture seeds
`883000–883004` remain ungated. `EXECUTION_AUTHORIZATION.md` stays the human-readable sign-off page; the
new JSON is its machine-readable counterpart.

## 5. Tests the implementation must add (fixtures/mocks only)
Absent record ⇒ raises · role `authorized:false` ⇒ raises · seed outside `scope_seeds` ⇒ raises ·
`protocol_lock_digest` mismatch ⇒ raises · expired ⇒ raises · missing operator token ⇒ raises · wrong
operator token ⇒ raises · **smoke authorized ⇒ dev/final still raise** · correct record + correct token on
a *fixture* role ⇒ granted (never exercised on a reserved seed in tests).

## 6. Threat model — what this prevents
Casual/accidental runs (needs a committed signed record *and* an out-of-band secret) · a token leaking via
the repo (only a hash is committed) · a caller self-authorizing (no bypass flag) · authorize-then-retune
(protocol digest binding) · scope creep from one approval (per-role, per-seed scoping) · a stale blanket
grant (optional expiry).

## 7. Owner decisions (max 5)
1. **Token delivery** — env var `BTRR_EXEC_TOKEN` + committed hash (recommended), or an external secrets
   manager.
2. **Protocol binding** — bind each authorization to `manifest.config_digest()` so gate/config changes
   revoke it (recommended: yes).
3. **Final approval bar** — should `final` require a second signer or a stricter review than `smoke`?
4. **Expiry** — should `final` auto-revoke after one run (e.g. `expires_at`, or a one-shot nonce)?
5. **Sequencing** — confirm the run order smoke → development → final, with dev results marked
   inadmissible as evidence.

## 8. Explicit non-goals
This spec does **not** sign any record, generate or commit any token/hash, modify `execution.py`, run any
seed, or unlock execution. It is a proposal for review. Implementing it is a separate task that itself
must not sign or run anything — signing/execution is a distinct, deliberate owner action taken only after
this mechanism is approved and merged.
