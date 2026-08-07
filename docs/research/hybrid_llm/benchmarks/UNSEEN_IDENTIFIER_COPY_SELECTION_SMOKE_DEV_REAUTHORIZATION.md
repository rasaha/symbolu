# Unseen-identifier copy/selection — smoke/development **re**-authorization for the corrected shortcut gate (docs-only)

**Documentation-only. Nothing is executed, generated, trained, or seeded in this record or session.**
Authorization-package readiness marker: **`SMOKE_DEV_REAUTHORIZATION_DRAFT_READY`**.

This record establishes a **fresh** smoke/development execution-authorization that applies **only** to the
newly merged, corrected shortcut-gate implementation. It exists because the shortcut-precheck **decision
rule** changed on default, which **supersedes and invalidates** the prior development evidence. The earlier
`UNSEEN_IDENTIFIER_COPY_SELECTION_SMOKE_DEV_EXECUTION_AUTHORIZATION.md` authorized runs under the *previous*
gate; that authorization's development evidence is no longer current and **may not** be reused as evidence.

Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL`
· `KDA_VALIDATION_BLOCKED`.

## What changed (why re-authorization is required)
The corrective PR **#1379** merged onto default. It narrowly replaces the flat `p̂ ≤ chance + 0.05`
shortcut decision with a **dual condition** — a baseline blocks iff it is **both** practically
(`p̂ > chance + 0.05`, the 0.05 margin unchanged) **and** statistically (exact one-sided binomial
upper tail `P(X ≥ k | n, chance)` rejected under **Holm–Bonferroni** at FWER = 0.05 across all
(split × baseline) comparisons) above the practical bound. Only the boolean `pass`/`all_pass` decision
changes; scores, counts, `chance`, `bound`, the pooled count-weighted aggregation, and all Decision-7
capability gates are unchanged.

* Corrective PR: **#1379** — verdict **`CORRECTIVE_GATE_AUDIT_PASS`** (independent statistical/code audit).
* Audited head (unchanged through merge): `23b90c0256658014cd5f9f5a2943279c99e2aad8`.
* Base at audit: `b73a9f1e3cabe5f26bcc9a3a15f20d5519347baa`.
* Merge commit / **new authoritative default**: `ed95bff68c1d867cec5fdadc97f7bbc3ad9501d4`.
* Corrected implementation: `experiments/unseen_identifier_copy_selection/shortcuts.py`
  (`binom_sf_ge`, `holm_reject`, dual practical + Holm-corrected exact-binomial gate).

## Control model (unchanged — current default)
* every invocation names an explicit **`--phase`** (`fixture` / `smoke` / `development` / `final`);
* the seed must belong to that phase's **exact** role — every cross-role pairing is refused;
* **exactly one** integer `--seed` per invocation — no wildcard / range / comma-list / glob / alias /
  implicit iteration over reserved seeds;
* the **primitive-level fail-closed guard** `require_execution_authorization(seed, phase)` refuses a
  reserved seed unless its exact phase is declared;
* CI and the tests exercise **only** the fixture phase (`993000–993004`).

No crypto gate, secret, per-run token, signed record, authority root, or runtime self-verification is
involved — those mechanisms were removed in PR #1377. Authorization is not a string a program emits; it
is the reviewed, independently-audited, **merged** authorization together with the operator's explicit
phase-named invocation.

## Authorization statement (fresh, corrected-gate only)
> Merged with the operator's explicit authorization, this record authorizes **only** smoke seed 9070 and
> development seeds 9071–9073, run under the **corrected** frozen implementation on default
> `ed95bff68c1d867cec5fdadc97f7bbc3ad9501d4`, via explicit phase-named invocation of the merged CLI
> (`--phase smoke` with `--seed 9070`; `--phase development` with a single seed in 9071–9073).
> **Reserved final seeds 90760–90764 remain PROHIBITED; `--phase final` is not authorized here.**

## Scope — smoke seed 9070
**May** (once run under `--phase smoke`): runtime feasibility · tensor shapes · parser behavior ·
manifest completeness · checkpoint creation · deterministic replay · wall-clock estimate · memory
estimate · shortcut machinery (under the corrected gate) · evidence-path verification.
**May not:** change the protocol / gates / task counts / model / tokenizer / candidate counts;
contribute to a scientific verdict; justify a positive capability claim.

## Scope — development seeds 9071–9073
**May** (once run under `--phase development`): implementation validation · deterministic replication ·
shortcut precheck under the corrected dual-condition gate · resource feasibility · gate-mechanics
validation · discovery of implementation defects.
**May not:** change frozen gates / representation / identifier design / model recipe / output contract /
verdict precedence; inspect or generate reserved final cohorts; support a final capability verdict.

## Explicitly preserved prohibitions and invariants
* **Reserved final seeds 90760–90764 remain PROHIBITED** — not to be opened, generated, inspected, or
  consumed under this or any smoke/development authorization.
* **`--phase final` is not authorized** here; it additionally requires a separate, independently-audited
  final authorization plus a passing shortcut precheck that is out of scope here.
* **No capability verdict is authorized** by this record; no capability/empirical claim is made.
* **No reuse of the previous development verdict as current evidence** — the prior
  `DEVELOPMENT_SHORTCUT_BLOCKED` result was produced under the superseded gate and is invalidated for
  evidentiary purposes by the merged correction.

## Explicitly unchanged (this record alters none of the following)
model architecture · task construction · training recipe · optimizer · seed allocations · final-gate
thresholds · capability-verdict logic.

## Resulting state (once this record is merged on default)
Smoke (9070) and development (9071–9073) execution is **AUTHORIZED** under the **corrected** frozen
implementation and the phase-protocol control model; **final (90760–90764) remains PROHIBITED.** No
execution, seed consumption, capability claim, or empirical-result claim is made by this record —
running the authorized phases is a separate, operator-directed step.

**Next permitted action (after this record lands on default):** rerun smoke `9070` and development
`9071–9073` under the corrected shortcut gate. No reserved final seed may be run.
