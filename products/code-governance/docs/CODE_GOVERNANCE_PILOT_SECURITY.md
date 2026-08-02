# Pilot Security

> The operator is read-only and shadow-only, and proves it two ways: structurally
> (no write client, no write method) and statically (an AST inspector over the
> adapter + operator boundary). Machine-readable companion:
> `docs/pilot_security_events.json`.

## Static read-only inspection

`scan_paths` / `scan_source` (AST-based, not bare substring matching) detect:
HTTP mutation calls (`.post/.put/.patch/.delete`), direct HTTP clients outside the
approved transport, GitHub mutation endpoints, GraphQL mutations, write scopes,
merge/approval operations, execution-provider imports, and `reserve_once`. It
ignores documentation-only forbidden words (docstrings are skipped) and the
scanner's own deny-list constants. The real adapter+operator boundary scans clean.

## Security events

Immutable `PilotSecurityEvent`s (read-only boundary violation, credential-leak test
failure, unapproved host/endpoint, write permission detected, config integrity
mismatch, adapter identity mismatch, store integrity failure, unexpected
execution-capable symbol) never contain a credential. Critical events abort the
pilot. A stop-condition breach never enables execution or changes policy.
