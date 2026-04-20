# OA Build Guide — SPY Tight Iron Condor (Aggressive Gate)

## Step-by-step UI instructions

Open Option Alpha → Bots → Create New Bot. Fill in:

### 1. Bot identity
- **Name:** `Spy Tight Ic Aggressive`
- **Underlyings (Symbols):** `SPY`
- **Allocation (USD):** `$10,000`
- **Position limit:** `4`
- **Scan speed:** `Standard (15 min)` for 30+ DTE, `Fast (1 min)` for 0-7 DTE

### 2. Scanner Automation

**Trigger:** Recurring at scan_time (default 09:45 ET; 10:30 ET for timing-edge bots).

**Decision tree (top-down, all conditions AND'd):**

Regime gates (each is one OA decision branch):
- `vix_level_max` ≤ `28`
- `vix_vix3m_max` ≤ `1.0`
- `vix_10d_high_max` ≤ `35`
- `vix_1d_change_max` ≤ `0.25`
- `ivp_min` ≥ `20`
- `regime_score_max` ≤ `4`
- `earnings_blackout` = `False`
- `fomc_cpi_nfp_blackout` = `True`

**Position criteria:**

- Structure: Iron Condor
- Short call delta: `0.273` (±0.02 tolerance)
- Long call delta: `0.089` (±0.02 tolerance)
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
