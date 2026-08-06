# Unseen-identifier protocol control (authorization system removed)

Narrow fix-forward cleanup from default `e30b0efa`. For an internal research experiment the
production-style **security-authorization** layer that had accreted around the unseen-identifier
executable interface was disproportionate and was obstructing the actual scientific work. This change
**removes the security machinery** and keeps only lightweight **experimental-protocol control**.

The distinction:

- **Security authorization** — unnecessary here. Removed.
- **Experimental-protocol control** — still necessary. Retained.

## Removed

- the caller-supplied authorization **record** and **artifact** concept, and their JSON schema /
  digest binding;
- `AuthorizationContext`, the capability registry, `active_authorization`, and mint keys;
- `authorize()` / `validate_authorization_record` and the recognized "authorization states";
- Git-ancestry / repository-authority provenance and any Ed25519 / signed-document plan;
- the `--authorization-record`, `--authorization-artifact`, `--repo-dir`, and `--authority-ref` CLI
  inputs and related environment variables;
- security-forgery tests and the security-specific CI guard.

(PR #1376, which proposed the Git-authority-root and signature machinery, is superseded and left
unmerged; the caller-substitutable authority root it was trying to salvage is simply deleted here
rather than re-engineered.)

## Retained — lightweight experimental safeguards

- **Explicit phase** per invocation: `fixture` / `smoke` / `development` / `final` (a required
  `--phase` flag; no default).
- **Exact seed-role validation**: the seed must belong to the named phase's exact set
  (`fixture → 993000–993004`, `smoke → 9070`, `development → 9071–9073`, `final → 90760–90764`);
  every cross-role pairing is refused.
- **Exactly one seed per invocation**; no wildcard/range/list; **no implicit iteration** over
  reserved seeds.
- A **primitive-level guard** (`require_execution_authorization`, threaded as the declared phase)
  so reserved seeds are never generated implicitly or under the wrong phase — direct
  `generate_split` / `build_pools` / `generate_pool` calls stay fail-closed.
- **Explicit output directory**, **overwrite refusal**, **incomplete-run marker**, and
  **deterministic evidence + replay** (unchanged).
- **Fixture-only CI**: still never trains, generates a reserved cohort, consumes a reserved seed, or
  emits a verdict.

## What "control" means now

There is no cryptographic gate, no secret, and no runtime self-verification of authority. Reserved
runs are governed by the ordinary **reviewed, independently-audited, merged** change plus the
operator's **explicit phase-named invocation**. Final seeds (`90760–90764`) run only when the
operator explicitly directs them with `--phase final`. Nothing scientific is changed: the model
recipe (209,728 params), tokenizer, trainer, task generation, parser, metrics, verdict, the twelve
shortcut baselines and their weighted aggregation, and evidence/replay semantics are all untouched.

Standing invariants preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` ·
`E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`.
