# OA Build Guide — SPY Iron Butterfly (Low-VVIX Gate)

## Step-by-step UI instructions

Open Option Alpha → Bots → Create New Bot. Fill in:

### 1. Bot identity
- **Name:** `Spy Iron Fly Low Vvix`
- **Underlyings (Symbols):** `SPY`
- **Allocation (USD):** `$6,000`
- **Position limit:** `2`
- **Scan speed:** `Standard (15 min)` for 30+ DTE, `Fast (1 min)` for 0-7 DTE

### 2. Scanner Automation

**Trigger:** Recurring at scan_time (default 09:45 ET; 10:30 ET for timing-edge bots).

**Decision tree (top-down, all conditions AND'd):**

Regime gates (each is one OA decision branch):
- `vix_level_max` ≤ `22`
- `vix_vix3m_max` ≤ `0.95`
- `ivp_min` ≥ `30`
- `vvix_max` ≤ `110`
- `realized_vol_5d_max` ≤ `0.12`
- `regime_score_max` ≤ `2`
- `fomc_cpi_nfp_blackout` = `True`

**Position criteria:**

- Structure: Iron Butterfly (body at ATM, 50Δ on each short leg)
- Long call delta: `0.071` (wing)
- Long put delta: `0.086` (wing)
- DTE window: `45-60` days
- Min credit: `$0.40` (reject thin chains)
- Max bid-ask: `$0.15` per leg (liquidity guard)

**Order settings:**

- Order type: `Limit at mid`
- Smart price slippage: `$0.05`
- Quantity: `1` contract(s)

### 3. Exit Automations

- **Profit target:** Close when P&L ≥ `35%` of credit received
- **Stop loss:** Close when P&L ≤ `-2.0× credit` (i.e., losing 200% of credit)
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
