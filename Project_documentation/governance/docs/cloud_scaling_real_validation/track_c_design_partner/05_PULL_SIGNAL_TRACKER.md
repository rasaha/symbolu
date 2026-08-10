# Pull-Signal Tracker (Gate 3)

**INTERNAL.** The ledger that decides **Gate 3 — Pull.** It records, per partner, only
the signals that count as **real demand**, plus the **differentiation** leading
indicator. Enthusiasm is not pull; this tracker exists precisely to stop us mistaking a
free read-only pilot for traction (`../MARKET_VALIDATION_90_DAY_PLAN.md` §12).

> Keep it honest: a signal goes in a column **only** when it meets the "counts" bar
> below. Link evidence (email, LOI doc, call note) for every entry. No savings language.

---

## What counts vs. what doesn't (gate before logging)
| Signal | ✅ Counts as real demand | ❌ Vanity (do not log as pull) |
|---|---|---|
| **LOI** | A signed **paid** pilot or letter of intent. | "We'd probably pay" with no document. |
| **Expansion** | **Unprompted** request to add clusters/teams. | We asked "want it elsewhere?" and they said sure. |
| **"Very disappointed"** | "**Very** disappointed if removed" (Sean-Ellis). | "Somewhat" / "nice to have." |
| **Recommend-mode** | Explicit ask to surface recommendations into their path. | "Maybe someday." |
| **Actuation-willingness** | Credible **"we'd let it act (bounded) once trusted."** | Vague "if it were perfect." |
| **Differentiation** | Unprompted **yes**, tied to a concrete episode (told them something existing tooling didn't). | A coached / led "yes," or "this is cool." |

A free read-only pilot, a logo, or a one-time dashboard view is **never** a pull
signal on its own.

---

## Partner status board
Legend: `✅` met (counts) · `~` in progress / soft · `—` not yet · `✗` explicit no.
Differentiation: `Y` / `N` / `?` (unsure or coached — **not** a yes).

| Org | First call | **LOI** | **Expansion** | **Very-disappointed** | **Recommend-mode** | **Actuation-willing** | **Differentiation** | Real-demand count | Notes / evidence |
|---|---|---|---|---|---|---|---|---|---|
| `____` | `____` | — | — | — | — | — | ? | 0 | `link` |
| `____` | `____` | — | — | — | — | — | ? | 0 | `link` |
| `____` | `____` | — | — | — | — | — | ? | 0 | `link` |
| `____` | `____` | — | — | — | — | — | ? | 0 | `link` |
| `____` | `____` | — | — | — | — | — | ? | 0 | `link` |
| `____` | `____` | — | — | — | — | — | ? | 0 | `link` |

*"Real-demand count" = number of the five demand columns met (differentiation is a
leading indicator, tracked separately, not summed here).*

## Signal event log (append-only; one row per signal as it lands)
| Date | Org | Signal type | Counts? | Verbatim / evidence | Logged by |
|---|---|---|---|---|---|
| `____` | `____` | LOI / expansion / very-disappointed / recommend / actuation / differentiation | ✅ / ❌ | `"..."` / `link` | `____` |

---

## Gate-3 roll-up (read the gate off the board, not off vibes)
| Gate-3 metric | Target (plan §9) | Current |
|---|---|---|
| Signed **paid pilot / LOI** | ≥ 1 | `____` |
| **Unprompted** cluster expansion | ≥ 1 | `____` |
| Partners "**very** disappointed if removed" | **≥ 50%** | `__ / __` |
| Explicit **recommend-mode** request | ≥ 1 | `____` |
| Credible **actuation-someday** ("let it act once trusted") | ≥ 1 | `____` |
| **Differentiation = yes** (consistent, unprompted) | majority | `__ / __` |

### Gate-3 reading (per plan §9 / strategy §9)
- **Pull = green (Company signal):** paid LOI **+** expansion **+** ≥50%
  "very disappointed" **+** a consistent differentiation **yes**.
- **Pull = weak (Feature / acquisition signal):** partners keep the free pilot but
  won't pay or expand ("we'd expect it free in Datadog"), **and** differentiation is
  mostly **no** ("we'd have seen it anyway").
- **Pull = red (Research / kill signal):** no LOI, no expansion, low "very
  disappointed," differentiation mostly **no**.

> **Differentiation is the early tell.** Per strategy §8, a consistent "yes" precedes
> LOIs and actuation trust and reinforces the **Company** case; a consistent "no"
> pushes toward **feature/acquisition** — capture it on the first call and watch the
> trend before payment talk.

---

## Anti-self-deception checklist (re-read before reporting Gate 3)
- [ ] Every logged signal links to evidence and clears the "counts" bar.
- [ ] No free-pilot enthusiasm recorded as pull.
- [ ] Differentiation "yes" is **unprompted**, not coached.
- [ ] "Very disappointed" uses the strict Sean-Ellis wording, not paraphrase.
- [ ] No savings claim, no "13.4%", no "validated / production" language anywhere here.
- [ ] Gate-3 status is computed from the board — not asserted from a good call.
