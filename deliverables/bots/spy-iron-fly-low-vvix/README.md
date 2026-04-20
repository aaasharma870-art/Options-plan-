# SPY Iron Butterfly (Low-VVIX Gate)

**bot_id:** `spy-iron-fly-low-vvix`
**Structure:** Iron Butterfly
**Underlying class:** A
**Role in suite:** Pin-risk premium when vol-of-vol is suppressed

## What this bot does
See full thesis: `proposals/2026-04-19-spy-iron-fly-low-vvix.md`

## Phase 3 backtest (synthetic chain — read with caveats in `validation_summary.md`)
- Win rate: **81.6%**
- Profit factor: 5.55
- Total trades over 825 days: 244
- Total P&L: $22,514
- Max drawdown: $481
- CPCV: 4/5 folds win (DSR_z > 1) — cross-period robust

## Phase 4 portfolio weight
- Equal-weight: 14.3%
- Risk-parity: 20.3%
- Mean-variance: **40.0%** (40% per-bot cap)

## Files in this folder
- `README.md` — this file
- `oa_build_guide.md` — every UI field value to type into Option Alpha
- `config.yaml` — machine-readable params (for regeneration)
- `performance.md` — full DSR / CPCV / fold breakdown
- `kill_switches.md` — bot-specific pause conditions
