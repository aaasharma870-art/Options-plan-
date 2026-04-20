# SPY Bull Put (Elevated VIX + Trend-Up)

**bot_id:** `spy-bull-put-elevated-vol`
**Structure:** Vertical Credit (bull put)
**Underlying class:** A
**Role in suite:** Vol-crush + drift directional bot, post-spike recovery

## What this bot does
See full thesis: `proposals/2026-04-19-spy-bull-put-elevated-vol.md`

## Phase 3 backtest (synthetic chain — read with caveats in `validation_summary.md`)
- Win rate: **94.9%**
- Profit factor: 12.26
- Total trades over 825 days: 214
- Total P&L: $95,437
- Max drawdown: $2,087
- CPCV: 4/5 folds win (DSR_z > 1) — cross-period robust

## Phase 4 portfolio weight
- Equal-weight: 14.3%
- Risk-parity: 11.9%
- Mean-variance: **0.0%** (40% per-bot cap)

## Files in this folder
- `README.md` — this file
- `oa_build_guide.md` — every UI field value to type into Option Alpha
- `config.yaml` — machine-readable params (for regeneration)
- `performance.md` — full DSR / CPCV / fold breakdown
- `kill_switches.md` — bot-specific pause conditions
