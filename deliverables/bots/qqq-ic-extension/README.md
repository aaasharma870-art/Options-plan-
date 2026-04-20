# QQQ Iron Condor (Class A Extension)

**bot_id:** `qqq-ic-extension`
**Structure:** Iron Condor
**Underlying class:** A
**Role in suite:** Premium-collection diversifier away from SPY surface

## What this bot does
See full thesis: `proposals/2026-04-19-qqq-ic-extension.md`

## Phase 3 backtest (synthetic chain — read with caveats in `validation_summary.md`)
- Win rate: **87.9%**
- Profit factor: 6.86
- Total trades over 825 days: 231
- Total P&L: $75,757
- Max drawdown: $3,678
- CPCV: 4/5 folds win (DSR_z > 1) — cross-period robust

## Phase 4 portfolio weight
- Equal-weight: 14.3%
- Risk-parity: 14.3%
- Mean-variance: **0.0%** (40% per-bot cap)

## Files in this folder
- `README.md` — this file
- `oa_build_guide.md` — every UI field value to type into Option Alpha
- `config.yaml` — machine-readable params (for regeneration)
- `performance.md` — full DSR / CPCV / fold breakdown
- `kill_switches.md` — bot-specific pause conditions
