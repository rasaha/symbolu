# Alpaca MCP Server — Paper Trading Setup

This guide wires the official Alpaca MCP server into Claude Code for this
repository, pointed at **paper trading only**. Live trading is a separate
opt-in and is covered at the end.

The config is already in the repo:

- `.mcp.json` — project-scoped MCP server definition
- `.env.example` — environment variable template (copy to `.env`, never commit)

You only need to do the steps below once per machine.

---

## 1. Prerequisites

- An Alpaca account at <https://app.alpaca.markets>. Paper mode is free and
  requires no KYC.
- [`uv`](https://docs.astral.sh/uv/) installed. This gives you the `uvx`
  command used by `.mcp.json` to run the MCP server in an ephemeral venv.

  ```bash
  # macOS / Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- Claude Code installed and able to open this repo.

---

## 2. Get your paper API keys

1. Sign in at <https://app.alpaca.markets>.
2. Confirm the account switcher at the top-left says **"Paper Trading"**. If
   it says anything else, switch to paper before going further.
3. In the left sidebar click **`API`** (icon: `>_`). This is the paper API
   keys page. **Do not click "Account" → "Individual Account"** — that starts
   the live-account KYC flow, which you do not need for paper trading.
4. Click **"Generate New Key"**.
5. A modal shows two values:
   - **Key ID** — starts with `PK...`
   - **Secret Key** — long random string, **shown only once**
6. Copy both values immediately into a password manager. If you lose the
   secret you must regenerate the key pair.

The base URL for paper is always `https://paper-api.alpaca.markets`. Live is
`https://api.alpaca.markets`. The two environments have separate key pairs —
paper keys cannot touch live and vice versa.

---

## 3. Configure your local environment

From the repo root:

```bash
cp .env.example .env
```

Edit `.env` and fill in the Alpaca section:

```bash
APCA_API_KEY_ID=PK********************
APCA_API_SECRET_KEY=****************************************
APCA_API_BASE_URL=https://paper-api.alpaca.markets
ALPACA_DATA_FEED=iex
```

Notes:

- Leave `APCA_API_BASE_URL` pointed at paper. Do not change it to the live
  endpoint until you have completed section 7.
- `ALPACA_DATA_FEED=iex` is the free data tier. The Algo Trader Plus
  subscription (roughly $99/mo) unlocks `sip` — the full consolidated US
  equities feed. Stay on `iex` until you need broader symbol coverage.
- `.env` is gitignored. Never commit filled-in keys.

You do **not** need to export these variables into your shell. The
`.mcp.json` in this repo launches the server with
`uvx alpaca-mcp-server --env-file .env`, so the server reads `.env`
directly at startup. No `direnv`, no PowerShell loader, no
`[Environment]::SetEnvironmentVariable` dance. Saving `.env` is the
entire "install" step on every machine.

---

## 4. First-run approval in Claude Code

1. Open this repo in Claude Code.
2. On the first session after `.mcp.json` appears, Claude Code prompts you to
   approve the project-scoped MCP servers. Read the prompt, then approve.
   This is a one-time trust decision per repo per machine.
3. If you ever need to reset the approval:

   ```bash
   claude mcp reset-project-choices
   ```

4. Verify the server is loaded:

   ```bash
   claude mcp list
   ```

   You should see an `alpaca` entry with status `connected` (or similar).

---

## 5. Smoke test

Inside a Claude Code session in this repo, ask something like:

> "Using the alpaca MCP server, show me my paper account equity, buying
> power, and any open positions."

You should see the assistant call tools from the `alpaca` namespace and
return values consistent with a fresh paper account (typically $100,000
buying power, no positions).

If it fails, the two most common causes are:

1. Environment variables not exported into the shell where Claude Code is
   running. Fix: `env | grep APCA` — all three vars should appear.
2. `uvx` not on `PATH`. Fix: `which uvx` and reinstall `uv` if missing.

---

## 6. Safety rails before running any strategy

Before you let a bot place orders — even on paper — add these guardrails in
your own code (not in the MCP server):

1. **Explicit mode assertion.** Refuse to start if `APCA_API_BASE_URL` does
   not contain `"paper"` and an opt-in env var like `ALPACA_LIVE_CONFIRMED=1`
   is not set.
2. **Hard notional cap per order** in your `trading/safety/` module,
   independent of the strategy. E.g. reject any order whose `qty * price`
   exceeds a fixed dollar amount.
3. **Drawdown circuit breaker.** A separate process that flattens all
   positions and cancels open orders if equity drops below a threshold.
4. **Kill switch.** A script you can run from anywhere that calls
   `close_all_positions` and `cancel_all_orders`. Do not rely on the web
   dashboard when something is wrong.
5. **Paper-vs-live reconciliation.** On day one of live, run the same
   strategy against both and compare fills. Divergence means your slippage
   model is wrong.

---

## 7. Going live (do NOT do this yet)

Only after you have forward-tested your strategy on paper for a meaningful
period:

1. In the Alpaca dashboard, open the live-account application (`Account` →
   `Open a Live Account` or the `brokerage/new-account` URL). Complete the
   KYC flow: identity, employment, financial profile, disclosures, ID
   upload, and agreements.
2. Wait for approval. Fund the account via ACH or wire.
3. Once the live account is open, generate a **second** key pair from the
   API page — live keys start with `AK...`.
4. Create a second env file, `.env.live`, containing:

   ```bash
   APCA_API_KEY_ID=AK********************
   APCA_API_SECRET_KEY=****************************************
   APCA_API_BASE_URL=https://api.alpaca.markets
   ALPACA_DATA_FEED=iex   # or sip if you have the subscription
   ALPACA_LIVE_CONFIRMED=1
   ```

5. Load `.env.live` only in the shell where you intend to run the live bot.
   Keep it far away from your normal dev shell.
6. Start at a small fraction of your intended capital. Watch the first
   fills manually.

The `.mcp.json` in this repo does not need to change — it reads whichever
keys are in the environment at launch.
