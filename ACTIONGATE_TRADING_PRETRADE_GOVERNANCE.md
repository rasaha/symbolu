# ActionGate — Stock-Market Pre-Trade Governance (Cash-Equity Pilot)

**Status:** V1 pilot. Self-contained domain package (`agentic/trading/`) around
the unchanged generic ActionGate. Synthetic data only.

> **This is a synthetic governance and execution-control prototype.** It does not
> predict prices, does not provide investment advice, does not prove profitable
> trading, and does not establish regulatory compliance. It is not ready for
> real-money deployment without security, broker, legal, regulatory, operational,
> and risk validation.

---

## 1. Product positioning

**"The strategy proposes the trade. ActionGate determines whether, how much, and
under what constraints it may execute."**

ActionGate is the independent pre-trade authorization, risk-control, and
constrained-execution boundary between a trading strategy / AI model proposing an
order and a broker/exchange/OMS capable of committing capital. It is not a
price-prediction model, a signal generator, or a recommender.

## 2. Strategy vs governor separation

- The **strategy** decides *what it wants* (a proposed order).
- **ActionGate** decides *whether, how much, and under what constraints* it may
  execute — deterministically, from human-authored policy and risk limits, with
  model signals only advisory or stricter-only.
- The proposing model never classifies its own criticality and never downgrades a
  human-configured `SOURCE_OF_TRUTH` decision.

## 3. Critical vs non-critical authority (per-decision)

Authority mode is resolved per request from deterministic facts + human
registries (never the model):

- **`BASELINE`** — bounded, reversible, in-approved-limits, non-risk-increasing
  actions: generate a signal, recommend a trade, cancel an order, reduce/close a
  position, a small cash-equity order inside all limits, a bounded limit-price
  adjustment. Human policy sets the envelope; **model governance may tighten,
  resize, defer, or deny**; every execution stays constrained and audited.
- **`SOURCE_OF_TRUTH`** — change a risk limit, activate an unapproved strategy, an
  unusually large order, approaching/breaching concentration, trading near the
  daily-loss threshold, unapproved symbol/venue/account/strategy/model, stale
  data, kill-switch override, fund transfers, unsupported instruments, post-
  suspension trading. A matched human verdict is dispositive, subject to
  independent hard blocks.
- **Unknown / missing material facts** → conservative `REQUIRE_APPROVAL` (or deny).

## 4. Action taxonomy

`READ_MARKET_DATA`, `GENERATE_SIGNAL`, `RECOMMEND_TRADE`, `PLACE_ORDER`,
`MODIFY_ORDER`, `CANCEL_ORDER`, `INCREASE_POSITION`, `REDUCE_POSITION`,
`CLOSE_POSITION`, `ACTIVATE_STRATEGY`, `HALT_STRATEGY`, `CHANGE_RISK_LIMIT`,
`TRANSFER_FUNDS`. **V1 executes only** cash-equity place/modify/cancel/increase/
reduce/close; derivatives and fund transfers are represented but not executed.

## 5. Risk and policy taxonomy

Human-authored **limits** (`TradingLimits`): preferred/max order quantity, max
order notional, max/absolute-max position, max concentration, max sector
concentration, max daily turnover, max daily loss (+ soft ratio), max quote age,
max price deviation (+ constrained tighter bound), min cash, burst threshold.

Human-authored **approved universe** (`ApprovedUniverse`): accounts, strategies
(id→versions), models (id→versions), exchanges, symbols, venues, permitted
sessions.

Deterministic **criticality/risk derivation** reads the request against these —
action, notional, quantity, projected position, concentration, cash, daily P&L,
turnover, approvals, market-data freshness, session, destination, price
deviation, duplicate/burst, risk-limit change, unsupported features. **Caller
labels (`low_risk`, `non_critical`, `routine`, `approved`, `safe`, `small_order`)
are ignored; caller facts may only promote conservatism.**

## 6. Constrained authorization (`ALLOW_WITH_CONSTRAINTS`)

Central to the product. Example — requested BUY 2,000 shares, market order, above
the order limit → authorized:

- max quantity 400 (preferred cap); **limit order only**; max limit price and
  max slippage (tight `constrained_price_deviation_pct`); approved account/venue
  only; short validity window; one-time execution.

Machine-readable constraints include: max quantity, max notional, permitted side/
symbol/account/venue/order-types, min/max price, max price deviation, TIF
restriction, expiry, one-time-use, strategy/model binding, and prohibition on
widening or onward delegation.

## 7. Hard-block semantics

Routed through the generic fail-closed layer (forbidden capabilities) with an
explicit human-configured rule ID / provenance recorded **separately** from
ordinary LLM denials (`final_authority = HARD_BLOCK`): account/strategy suspended,
kill switch active, symbol/venue/exchange unapproved, unsupported instrument,
stale market data, no actor identity, daily-loss breached, projected position
over absolute max, insufficient cash (cash-only V1), unauthorized risk-limit
change, short/leverage/derivatives in V1, and any attempt to override the hard
block itself.

## 8. Pre-trade integration flow

```
 strategy / model proposes an order
    │  (account, strategy+version, model+version, symbol, side, qty, price, venue, risk state)
    ▼
 TradingGovernanceService.authorize(TradingActionRequest)
    │  1. derive_criticality (deterministic; ignores caller risk labels)
    │  2. adapt → generic AuthorizationRequest (facts, hard-block caps, advisory signals)
    │  3. GovernanceService.authorize (human policy + per-decision mode + hard blocks)
    │  4. compute_order_constraints (deterministic order envelope)
    ▼
 TradingDecision → ALLOW / ALLOW_WITH_CONSTRAINTS / REQUIRE_APPROVAL / DENY
    │  (only ALLOW/ALLOW_WITH_CONSTRAINTS → integrity-bound authorization artifact)
    ▼
 simulated broker/OMS enforcement → submit within the authorized envelope, or reject
```

## 9. Representative truth tables

| Proposal | Facts | Outcome | Mode / authority |
|---|---|---|---|
| small approved limit order | within all limits | ALLOW | baseline |
| BUY 2,000 market | above order limit, approved | ALLOW_WITH_CONSTRAINTS (400, limit-only) | source_of_truth |
| any order | kill switch active | DENY | HARD_BLOCK |
| any order | daily loss breached | DENY | HARD_BLOCK |
| order | unapproved symbol | DENY | HARD_BLOCK |
| order | unapproved model version | REQUIRE_APPROVAL | source_of_truth |
| large approved order | model signals weak | ALLOW_WITH_CONSTRAINTS (human dispositive) | HUMAN_SOURCE_OF_TRUTH |
| small approved order | model signals weak | DENY (model tightened) | baseline |
| order | unsupported instrument / short | DENY | HARD_BLOCK |
| order | missing account/strategy/symbol/quote-ts | REQUIRE_APPROVAL | conservative |

## 10. Pilot metrics

Orders allowed; constrained/resized; requiring approval; denied; hard blocks
triggered; scope-widening attempts blocked; replay attempts blocked;
stale-market-data attempts blocked; risk-limit breaches blocked; duplicate orders
blocked; unauthorized executions (required 0); audit-correlation completeness;
model-versus-human disagreement rate.

## 11. Regulatory and product-boundary caveats

- Not investment advice, not a recommendation engine, not a price model.
- Approvals, identities, session status, and risk state are inputs the
  surrounding systems must supply truthfully; this boundary enforces policy over
  those facts, it does not establish them.
- Best-execution, market-abuse surveillance, order-routing regulation, suitability,
  and reporting obligations are **out of scope** and must be handled by dedicated,
  validated systems.

## 12. Limitations and non-claims

- Synthetic market/account/order data only; no live feed, no real brokerage, HMAC
  test key (shared-secret authentication, not asymmetric signing).
- V1 is cash-equity only; no derivatives, margin, short selling, autonomous
  portfolio management, or financial advice.
- Passing synthetic tests demonstrates governance behavior in simulation — not
  profitability, price-prediction accuracy, regulatory compliance, or real-money
  readiness.
