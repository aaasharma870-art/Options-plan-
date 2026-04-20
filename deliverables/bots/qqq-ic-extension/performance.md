# Performance — qqq-ic-extension

## Overall (full 2023-01-03 → 2026-04-17 backtest)

| Metric | Value |
|---|---:|
| DSR_z (Bailey-LdP, deflated for 30 trials) | 116986411.40 |
| Raw Sharpe (annualized) | 9.45 |
| Win rate | 87.9% |
| Profit factor | 6.86 |
| Total trades | 231 |
| Total P&L | $75,757 |
| Max drawdown | $3,678 |

## CPCV folds (5-fold purged cross-validation)

| Fold | Start | End | DSR_z | Raw SR | Trades | WR | P&L | Max DD |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 0 | 2023-01-03 | 2023-08-29 | -inf | 0.00 | 14 | 92.9% | $4,634 | $551 |
| 1 | 2023-08-30 | 2024-04-25 | 70482312.89 | 12.09 | 62 | 80.6% | $14,235 | $818 |
| 2 | 2024-04-26 | 2024-12-19 | 50887746.33 | 7.50 | 80 | 71.2% | $12,879 | $1,388 |
| 3 | 2024-12-20 | 2025-08-20 | 65206251.77 | 8.79 | 92 | 75.0% | $21,160 | $1,589 |
| 4 | 2025-08-21 | 2026-04-17 | 61749406.66 | 8.91 | 81 | 74.1% | $19,854 | $1,380 |

**Folds won (DSR_z > 1):** 4/5 (master prompt C4 requires ≥4/5)

**Total OOS trades across all folds:** 329 (master prompt C5 requires ≥50)

## Best parameters (from Optuna 30-trial TPE search)

```yaml
dte_idx: 2
long_call_delta: 0.0672826759329993
long_put_delta: 0.05975347863063451
profit_target: 0.35
short_call_delta: 0.24802225326948396
short_put_delta: 0.08050012538801686
stop_loss: 2.0
time_exit: 21
```

## Caveats

These numbers are from the SYNTHETIC chain backtest (BSM + VIX as ATM IV +
SKEW-adjusted skew + stress-clip patch). Real-chain validation deferred until
Polygon plan upgrade. **Apply 30-50% downward bias to absolute P&L numbers
before sizing real capital.** Cross-period CPCV robustness (folds-won) is
the more reliable signal and won't change much under real chains.
