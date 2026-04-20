# SPY Iron Condor (Regime Recovery)

**bot_id:** `spy-ic-regime-recovery`
**Structure:** Iron Condor
**Underlying class:** A
**Role in suite:** Event-driven entry on RED -> GREEN/YELLOW transitions

## What this bot does
See full thesis: `proposals/2026-04-19-spy-ic-regime-recovery.md`

## Phase 3 backtest (synthetic chain — read with caveats in `validation_summary.md`)
- Win rate: **95.7%**
- Profit factor: 17.09
- Total trades over 825 days: 164
- Total P&L: $133,537
- Max drawdown: $4,122
- CPCV: 4/5 folds win (DSR_z > 1) — cross-period robust

## Phase 4 portfolio weight
- Equal-weight: 14.3%
- Risk-parity: 9.6%
- Mean-variance: **0.0%** (40% per-bot cap)

## Files in this folder
- `README.md` — this file
- `oa_build_guide.md` — every UI field value to type into Option Alpha
- `config.yaml` — machine-readable params (for regeneration)
- `performance.md` — full DSR / CPCV / fold breakdown
- `kill_switches.md` — bot-specific pause conditions
