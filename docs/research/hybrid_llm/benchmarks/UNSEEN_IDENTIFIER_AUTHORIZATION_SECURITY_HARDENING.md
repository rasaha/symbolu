# Unseen-identifier authorization security hardening

Fix-forward hardening that closes two authorization-forgery defects found **after** PR #1375 merged
(default `e30b0efa`). Scope: `execution.py` + `cli.py` + security tests + integrity CI + this note.
No scientific behavior, seed role, model recipe, shortcut, metric, gate, CLI command name, output
schema, or execution sequence is changed. Standing invariants preserved:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`KDA_VALIDATION_BLOCKED`.

## Defects closed

- **`AUTHORIZATION_PROVENANCE_FORGEABLE`** — previously a self-consistent JSON artifact with
  `approved: true`, a caller-chosen 40-hex commit string, and recomputed digests was accepted with no
  check against the committed tree. A fabricated artifact could authorize smoke seed 9070.
- **`AUTHORIZATION_CONTEXT_FORGEABLE`** — previously a caller could construct `AuthorizationContext`
  directly (or copy/replace/pickle one) and pass it to `active_authorization`, satisfying the
  primitive guard for seed 9070 without ever calling the validated `authorize()` path.

## Repository authority root (provenance)

Scientific authorization is now proven against **local Git** (no network). For every scientific
state the validation path establishes:

1. the record's `authorization_document_commit` is a real **commit** object (`git cat-file -t`);
2. it is **reachable from the authoritative-default reference** (merged), i.e. an ancestor of the
   configured default ref — not merely on an unmerged feature branch;
3. it **descends from** the authorized implementation merge `e30b0efa` (chronology);
4. the authorization document lives at the single **allow-listed path**
   `docs/research/hybrid_llm/benchmarks/UNSEEN_IDENTIFIER_EXECUTION_AUTHORIZATION.json` in that
   commit (no traversal, no arbitrary path);
5. the **committed bytes** are read from Git and their SHA-256 matches the record's bound digest;
6. every authoritative value — approval, state, cohort, permitted seeds, commits, model hashes,
   parameter count, scope — is taken from the **committed document**, never from a caller-supplied
   duplicate; the committed document's `implementation_commit` must itself descend from `e30b0efa`;
7. the committed document is parsed with **duplicate-key rejection** and **strict** schema
   (`unseen-id-exec-authorization/1`); any `expiry` field fails closed (no trusted clock).

The **authoritative-default reference** comes from frozen configuration
(`AUTHORITATIVE_DEFAULT_REF`), an operator environment override (`UNSEEN_ID_AUTHORITATIVE_REF`), or
the explicit `--authority-ref` / `--repo-dir` CLI flags — **never** from the artifact being
validated. Git is invoked with argument lists (no `shell=True`), validated 40-hex object ids, an
allow-listed document path, and timeouts, returning deterministic failures.

## Non-forgeable capability

`AuthorizationContext` cannot be constructed through public APIs (construction requires a
module-private mint key), and — independently — `active_authorization` accepts **only the exact
object identity minted by a successful `authorize()`** (a module-private minted-identity registry).
A copied, `dataclasses.replace`-d, deep-copied, pickled, `object.__new__`-ed, or hand-built object is
rejected. The capability is bound to one exact seed/cohort/state/scope/document-commit invocation,
activated only inside `active_authorization` (registered on entry, removed on normal exit and on
exception), never persisted across processes, and empty between CLI invocations. The CLI still
executes exactly one explicit seed.

## Threat model (honest)

These protections stop bypass through **supported/public APIs and ordinary object construction**.
Code with arbitrary interpreter access — reassigning module-private globals, reaching into
`execution` internals, or monkeypatching Git — is **outside** this capability boundary. No
cryptographic guarantee against a malicious process controlling the interpreter is claimed.

## Present-day denial preserved

No approved scientific authorization document exists at the allow-listed path in the repository, so:
every scientific/reserved seed still **fails closed**; no authority capability is minted for the real
repository; PR #1373 remains unmerged; smoke seed 9070 remains unauthorized; fixture tests
(`993000–993004`) remain the only executable path. Recognition of the scientific states is
structural — no state is active until a committed, provenance-valid document exists.

## State-to-seed-role matrix (unchanged)

`FIXTURE_TEST_AUTHORIZATION → 993000–993004` · `SMOKE_EXECUTION_AUTHORIZED → 9070` ·
`DEVELOPMENT_EXECUTION_AUTHORIZED → 9071–9073` · `FINAL_EXECUTION_AUTHORIZED → 90760–90764`. Every
cross-role combination fails.

Status: **`AUTHORIZATION_SECURITY_HARDENING_IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT`** — draft
fix-forward; scientific execution remains denied; independent security audit still required.
