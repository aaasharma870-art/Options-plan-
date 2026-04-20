# SPY Tight Iron Condor (Aggressive Gate)

**bot_id:** `spy-tight-ic-aggressive`
**Structure:** Iron Condor
**Underlying class:** A
**Role in suite:** Always-on short-vol when no kill switches firing

## What this bot does
See full thesis: `proposals/2026-04-19-spy-tight-ic-aggressive.md`

## Phase 3 backtest (synthetic chain — read with caveats in `validation_summary.md`)
- Win rate: **94.9%**
- Profit factor: 14.04
- Total trades over 825 days: 390
- Total P&L: $142,562
- Max drawdown: $1,952
- CPCV: 5/5 folds win (DSR_z > 1) — cross-period robust

## Phase 4 portfolio weight
- Equal-weight: 14.3%
- Risk-parity: 12.4%
- Mean-variance: **36.6%** (40% per-bot cap)

## Files in this folder
- `README.md` — this file
- `oa_build_guide.md` — every UI field value to type into Option Alpha
- `config.yaml` — machine-readable params (for regeneration)
- `performance.md` — full DSR / CPCV / fold breakdown
- `kill_switches.md` — bot-specific pause conditions
