# OA Build Guide — SPY Bull Put (Elevated VIX + Trend-Up)

## Step-by-step UI instructions

Open Option Alpha → Bots → Create New Bot. Fill in:

### 1. Bot identity
- **Name:** `Spy Bull Put Elevated Vol`
- **Underlyings (Symbols):** `SPY`
- **Allocation (USD):** `$8,000`
- **Position limit:** `3`
- **Scan speed:** `Standard (15 min)` for 30+ DTE, `Fast (1 min)` for 0-7 DTE

### 2. Scanner Automation

**Trigger:** Recurring at scan_time (default 09:45 ET; 10:30 ET for timing-edge bots).

**Decision tree (top-down, all conditions AND'd):**

Regime gates (each is one OA decision branch):
- `vix_level_min` ≥ `20`
- `vix_level_max` ≤ `32`
- `vix_vix3m_max` ≤ `1.0`
- `ivp_min` ≥ `40`
- `spy_above_20d_sma` = `True`
- `regime_score_max` ≤ `4`
- `fomc_cpi_nfp_blackout` = `True`

**Position criteria:**

- Structure: Bull Put Credit Spread
- Short put delta: `0.091` (±0.02 tolerance)
- Long put delta: `0.058` (±0.02 tolerance)
- DTE window: `21-30` days
- Min credit: `$0.40` (reject thin chains)
- Max bid-ask: `$0.15` per leg (liquidity guard)

**Order settings:**

- Order type: `Limit at mid`
- Smart price slippage: `$0.05`
- Quantity: `1` contract(s)

### 3. Exit Automations

- **Profit target:** Close when P&L ≥ `25%` of credit received
- **Stop loss:** Close when P&L ≤ `-1.5× credit` (i.e., losing 150% of credit)
- **Time exit:** Close at `DTE = 7` regardless of P&L
- **Regime flip kill:** If your TradingView webhook signals `regime_score_max=4`, close all positions immediately
- **PDT 1-day wait:** Enable to avoid same-day open-close cycles

### 4. Per-bot kill switches (also see kill_switches.md)

- VIX intraday > `35` → halt new entries for the day
- Account-level drawdown > `5%` from monthly peak → halt all new entries

### 5. Verification before Going Live

1. Set bot to **Paper Trading** mode for 2 weeks minimum.
2. Confirm: WR within ±10pp of expected, no single trade > expected max loss.
3. Compare paper P&L to backtest expectation: any divergence > 30% is a chain-modeling artifact — see `validation_summary.md`.
4. Only then promote to **Live**.
