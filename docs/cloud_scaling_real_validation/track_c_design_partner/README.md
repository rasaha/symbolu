# Track C — Design-Partner Pull: operational collateral

**INTERNAL operating kit. Outreach + measurement, not product.** This folder holds
the five pieces needed to *run* Track C of the 90-day market-validation plan
(`../STRATEGY_IMPLEMENTATION_PLAN.md` §8, `../MARKET_VALIDATION_90_DAY_PLAN.md` §9).
Track C answers **one gate only — Gate 3, Pull:** *will anyone keep / expand / pay /
eventually let it act?* — and surfaces the **differentiation** leading indicator
(*"did the verdict tell you something your existing tooling did not?"*) **before**
any payment or actuation conversation.

Track C is **outreach and templates, not code.** Nothing in this kit changes the
controller, which stays **read-only / zero-write by construction.**

## The kit
| # | File | Audience | Purpose |
|---|---|---|---|
| 1 | `01_PARTNER_BRIEF.md` | **External** — the only doc we hand a partner | One page: who we are, what we read, what we never touch, what we ask, zero risk. |
| 2 | `02_FIRST_INTERVIEW_SCRIPT.md` | Internal (interviewer) | Structured first call, including the verbatim **differentiation question** and how to score it. |
| 3 | `03_DATA_REQUEST_NDA_CHECKLIST.md` | Both | The §5 data asks + NDA / data-handling gate that must close **before** any ingestion. |
| 4 | `04_SRE_ADJUDICATION_WORKSHEET.md` | Partner SRE + us | Per-flag template: true/false, **Tier-A vs Tier-B**, root cause, cost, harmful-FP check. |
| 5 | `05_PULL_SIGNAL_TRACKER.md` | Internal | Gate-3 ledger: LOI / expansion / "very disappointed" / recommend-mode / actuation-willingness / differentiation-yes-no. |

## Discipline (non-negotiable — inherited from the strategy docs)
- **No savings claims, no "13.4%", no "validated / production / customer / real-cluster"
  language** in anything partner-facing. This is a read-only **reliability/safety**
  read; the savings thesis is weak and the live / third-party rungs are not earned yet.
- **Free read-only pilots are not demand.** Only the real-demand signals in the
  tracker count; "this is cool" or a one-time dashboard view is vanity
  (`../MARKET_VALIDATION_90_DAY_PLAN.md` §12).
- **Tier-B is not market evidence.** The worksheet forces a tier on every flag; never
  headline a raw Tier-B count.
- **Pre-registered, no goalpost-moving.** The thresholds these instruments measure
  against are fixed in the 90-day plan **before** partner data — do not retune to a
  flattering answer.
- **Differentiation measured early.** The yes/no answer to *"did the verdict tell you
  something your existing tooling did not — that scaling was not helping?"* is a
  leading, pre-payment indicator — capture it on the **first** call.

## How the pieces flow
```
outreach
  → (1) partner brief
    → (2) first interview .......... capture differentiation yes/no
      → (3) NDA + data request ..... gate closes before any ingestion
        → ingest history (Track B replay)  /  read-only shadow (Track A)
          → flags
            → (4) SRE adjudication .. tier + true/false + cost per flag
              → (5) pull tracker .... rolls up Gate 3 across partners
```

## What "done" looks like for Track C
Per `../MARKET_VALIDATION_90_DAY_PLAN.md` §9, Gate 3 is **green** when there is a
signed **paid pilot / LOI**, at least one **unprompted cluster expansion**,
**≥50% of partners "very disappointed if removed"**, an explicit **recommend-mode**
request, a credible **"we'd let it act once trusted,"** and a consistent
**differentiation = yes**. The tracker (file 5) is where that judgement is read off —
not from enthusiasm, but from the recorded, classified signals.
