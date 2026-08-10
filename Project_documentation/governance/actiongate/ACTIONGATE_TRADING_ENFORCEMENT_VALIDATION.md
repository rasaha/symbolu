# ActionGate — Trading Enforcement & Adversarial Validation

**Status:** Simulation harness (`agentic/trading/enforcement/`) around the trading
decision layer. Synthetic broker/OMS only — no real connectivity.

> **Synthetic governance and execution-control prototype.** It does not predict
> prices, provide investment advice, prove profitable trading, or establish
> regulatory compliance, and is not real-money ready without security, broker,
> legal, regulatory, operational, and risk validation.

---

## 1. Decision vs execution

- **Decision** (`agentic/trading`): whether/how-much/under-what-constraints the
  order may execute → `TradingDecision` + a deterministic order envelope.
- **Execution enforcement** (`agentic/trading/enforcement`): the decision is bound
  into an HMAC-authenticated artifact; a simulated broker adapter re-verifies
  every material fact at submission time and only submits within the authorized
  envelope. **The strategy is never trusted to apply the constraints itself.**

## 2. Authorization artifact contract

`TradingAuthorizationArtifact` is **HMAC-authenticated inside a shared trust
boundary** — an integrity/authenticity tag verified with a shared secret, **not an
independently verifiable asymmetric digital signature** (production would use
asymmetric signing + key custody). It binds: authorization id; tenant; account;
portfolio; actor; strategy + version; model + version; action; side; symbol;
venue; permitted order types; max quantity; max notional; price bounds
(min/max + max deviation); time-in-force; strategy mandate; policy version + hash;
governance version; market-data reference + freshness bound; daily-loss limit;
issued/expiry; nonce; one-time flag; final authority used; approval-required
state.

Only `ALLOW` / `ALLOW_WITH_CONSTRAINTS` (and only executable order actions with a
positive authorized quantity) produce an artifact. `DEFER` / `REQUIRE_APPROVAL` /
`DENY` produce **no executable authorization**.

## 3. Simulated broker / OMS adapter

`SimulatedBroker` holds live `MarketState` (synthetic quotes + timestamps) and
`FirmRiskState` (kill switch, per-account daily loss, account/strategy status),
plus a submitted-order-id set. The adapter queries this **live** state at
execution time so tests can mutate it between authorization and execution.

## 4. Account / strategy / model / order binding

Execution re-checks tenant, account, actor, strategy id + version, model version,
symbol, side, and venue against the artifact — any mismatch is rejected
(`E_TENANT_MISMATCH`, `E_ACCOUNT_MISMATCH`, `E_ACTOR_MISMATCH`,
`E_STRATEGY_MISMATCH`, `E_MODEL_VERSION_MISMATCH`, `E_SYMBOL_MISMATCH`,
`E_SIDE_MISMATCH`, `E_VENUE_MISMATCH`).

## 5. Price and quantity constraints

- order type must be in the permitted set (a limit-only authorization rejects a
  market order → `E_ORDER_TYPE_MISMATCH`);
- submitted quantity ≤ max quantity (`E_QUANTITY_WIDENING`);
- submitted notional ≤ max notional at the max acceptable price
  (`E_NOTIONAL_WIDENING`);
- a limit price outside `[min_price, max_price]` → `E_PRICE_OUT_OF_BOUNDS`; beyond
  the max deviation from the live quote → `E_PRICE_DEVIATION`;
- time-in-force must match (`E_TIF_MISMATCH`).

## 6. Replay and duplicate protection

One-time artifacts carry a nonce consumed on first submission; reuse →
`E_REPLAY_NONCE_USED`. The broker rejects a repeated order id →
`E_DUPLICATE_ORDER`.

## 7. TOCTOU handling

Enforcement is a time-of-use re-verification of time-of-check facts against live
broker state: kill switch (`E_KILL_SWITCH_ACTIVE`), account/strategy suspension
(`E_ACCOUNT_SUSPENDED` / `E_STRATEGY_SUSPENDED`), daily-loss crossing
(`E_DAILY_LOSS_BREACHED`), quote staleness (`E_STALE_MARKET_DATA`), and policy
version (`E_POLICY_STALE`). On any material change between authorization and
execution it rejects — re-authorization is required, never silent reuse.

## 8. Stale quote and changing risk-state behavior

The artifact binds a `freshness_bound_seconds` and a `market_data_ref`; at
execution the adapter compares the live quote timestamp to the clock and rejects
if the quote has aged past the bound — even though the quote was fresh at
authorization. The bound daily-loss limit is re-evaluated against the live
per-account loss.

## 9. Adversarial threat model

A caller that will attempt to widen quantity/notional, change symbol/side/account/
venue/strategy/model, convert a limit order to market, price outside bounds, use
an expired or replayed artifact, or execute after a kill switch / loss / staleness
change. Enforcement is deterministic and content-blind; every constraint is a
checked precondition of submission, not advisory metadata.

## 10. Test matrix

`agentic/trading/tests/test_trading_enforcement.py` (19 tests) + governance
(`test_trading_governance.py`, 23 tests):

| # | Attack | Expected |
|---|---|---|
| 18 | increase quantity | `E_QUANTITY_WIDENING` |
| 19 | increase notional | `E_NOTIONAL_WIDENING`/`E_PRICE_OUT_OF_BOUNDS` |
| 20 | change symbol | `E_SYMBOL_MISMATCH` |
| 21 | change account | `E_ACCOUNT_MISMATCH` |
| 22 | change venue | `E_VENUE_MISMATCH` |
| 23 | limit → market | `E_ORDER_TYPE_MISMATCH` |
| 24 | price outside bounds | `E_PRICE_OUT_OF_BOUNDS` |
| 25 | change side / strategy / model | mismatch codes |
| 26/31 | replay / reuse one-time | `E_REPLAY_NONCE_USED` |
| 27 | expired artifact | `E_EXPIRED` |
| 28 | kill switch flip | `E_KILL_SWITCH_ACTIVE` |
| 29 | daily-loss crossing | `E_DAILY_LOSS_BREACHED` |
| 30 | quote goes stale | `E_STALE_MARKET_DATA` |
| 35 | duplicate order id | `E_DUPLICATE_ORDER` |
| 36 | receipt/artifact secrets | none present |
| + | account/strategy suspension, zero-unauthorized metrics | — |

Decision-layer coverage (1–17, 32–34, 37): normal auth, resize, authority modes,
risk/policy hard blocks, caller-label promotion, precedence invariants, and
generic + healthcare backward compatibility.

## 11. Metrics

`HarnessMetrics.to_dict()`: orders allowed / constrained / requiring approval /
denied; hard blocks triggered; scope-widening blocked; replay blocked;
stale-market-data blocked; risk-limit breaches blocked; duplicate orders blocked;
**unauthorized executions (required 0)**; audit-correlation completeness;
model-versus-human disagreement rate. The suite asserts zero unauthorized
executions and full audit correlation.

## 12. Execution receipt

Audit-safe: authorization id; order request id; execution status; tenant/account/
actor/strategy/model safe references; symbol; side; authorized vs submitted
quantity; authorized vs submitted order type; permitted price bounds; submitted
limit price; venue; policy version; timestamp; rejection/mismatch code; audit
correlation id; final authority used. No broker secrets, API credentials, or
proprietary strategy state.

## 13. Limitations and non-claims

- Synthetic data and a simulated broker only; HMAC test key (shared-secret
  authentication, **not** an asymmetric digital signature); no real key custody.
- Passing tests demonstrate mechanical enforcement of *these* constraints against
  *these* attacks in simulation — not profitability, price prediction, regulatory
  compliance, or real-money readiness.
- Best-execution, market-abuse, routing, suitability, and reporting obligations
  are out of scope.
