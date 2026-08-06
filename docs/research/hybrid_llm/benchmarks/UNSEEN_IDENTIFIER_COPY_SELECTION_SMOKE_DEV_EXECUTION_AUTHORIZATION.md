# Unseen-identifier copy/selection — smoke/development execution-authorization (docs-only)

**Documentation-only. Nothing is executed, generated, trained, or seeded in this record or session.**
Authorization-package readiness marker: **`SMOKE_DEV_EXECUTION_AUTHORIZATION_DRAFT_READY`**.

Under the current **phase-protocol** control model there is no runtime "execution-authorized" state or
scientific capability verdict to emit. The recognized authorization states of the earlier
cryptographic layer — `SMOKE_EXECUTION_AUTHORIZED`, `DEVELOPMENT_EXECUTION_AUTHORIZED`,
`FINAL_EXECUTION_AUTHORIZED`, `EXECUTION_AUTHORIZED` — were **removed in PR #1377** and no longer
exist. Authorization is not a string a program emits; it is the reviewed, independently-audited,
**merged** authorization together with the operator's explicit **phase-named invocation**.

Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL`
· `KDA_VALIDATION_BLOCKED`.

## Control model (current default)
* every invocation names an explicit **`--phase`** (`fixture` / `smoke` / `development` / `final`);
* the seed must belong to that phase's **exact** role — every cross-role pairing is refused;
* **exactly one** integer `--seed` per invocation — no wildcard / range / comma-list / glob / alias /
  implicit iteration over reserved seeds;
* the **primitive-level fail-closed guard** `require_execution_authorization(seed, phase)` refuses a
  reserved seed unless its exact phase is declared, so reserved seeds are never generated implicitly
  or under the wrong phase;
* CI and the tests exercise **only** the fixture phase (`993000–993004`).

No crypto gate, secret, per-run token, signed record, authority root, or runtime self-verification is
involved — those mechanisms were removed in PR #1377.

## Prerequisite
The independent post-merge implementation-integrity audit
(`…_POST_MERGE_IMPLEMENTATION_AUDIT.md`) concluded
`IMPLEMENTATION_INTEGRITY_CONFIRMED_AFTER_SCOPED_CORRECTIONS` (fail-closed guard strengthening
PR #1372; post-correction re-audit confirmed). The scientific-integrity findings are independent of
the authorization layer and remain valid on the current phase-protocol default `6c8fb71…`.

## Authorization statement
> Merged with the operator's explicit authorization, this record authorizes **only** smoke seed 9070
> and development seeds 9071–9073, run under the frozen implementation via explicit phase-named
> invocation of the merged CLI (`--phase smoke` with `--seed 9070`; `--phase development` with a
> single seed in 9071–9073). **Reserved final seeds 90760–90764 remain prohibited; `--phase final`
> is not authorized here.**

## Scope — smoke seed 9070
**May** (once run under `--phase smoke`): runtime feasibility · tensor shapes · parser behavior ·
manifest completeness · checkpoint creation · deterministic replay · wall-clock estimate · memory
estimate · shortcut machinery · evidence-path verification.
**May not:** change the protocol / gates / task counts / model / tokenizer / candidate counts;
contribute to a scientific verdict; justify a positive capability claim.

## Scope — development seeds 9071–9073
**May** (once run under `--phase development`): implementation validation · deterministic replication ·
shortcut precheck · resource feasibility · gate-mechanics validation · discovery of implementation
defects.
**May not:** change frozen gates / representation / identifier design / model recipe / output
contract / verdict precedence; inspect or generate reserved final cohorts; support a final
capability verdict.

**Reserved final seeds 90760–90764 remain forbidden.** They may not be opened, generated, inspected,
or consumed under this or any smoke/development authorization; `--phase final` is not authorized and
additionally requires a separate, independently-audited final authorization plus a passing shortcut
precheck that is out of scope here.

## Resulting state
Merged on default with operator authorization: **smoke (9070) and development (9071–9073) execution is
AUTHORIZED** under the frozen implementation and the phase-protocol control model; **final
(90760–90764) remains PROHIBITED.** No execution, seed consumption, capability claim, or
empirical-result claim is made by this record — running the authorized phases is a separate,
operator-directed step.
