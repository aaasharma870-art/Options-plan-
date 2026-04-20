# SPY Bear Call (Post-Spike Fade)

**bot_id:** `spy-bear-call-post-spike-fade`
**Structure:** Vertical Credit (bear call)
**Underlying class:** A
**Role in suite:** Mean-reversion fade after VIX spike + failed bounce

## What this bot does
See full thesis: `proposals/2026-04-19-spy-bear-call-post-spike-fade.md`

## Phase 3 backtest (synthetic chain — read with caveats in `validation_summary.md`)
- Win rate: **75.8%**
- Profit factor: 5.02
- Total trades over 825 days: 260
- Total P&L: $33,652
- Max drawdown: $914
- CPCV: 4/5 folds win (DSR_z > 1) — cross-period robust

## Phase 4 portfolio weight
- Equal-weight: 14.3%
- Risk-parity: 23.1%
- Mean-variance: **17.3%** (40% per-bot cap)

## Files in this folder
- `README.md` — this file
- `oa_build_guide.md` — every UI field value to type into Option Alpha
- `config.yaml` — machine-readable params (for regeneration)
- `performance.md` — full DSR / CPCV / fold breakdown
- `kill_switches.md` — bot-specific pause conditions
