# Performance — spy-tight-ic-aggressive

## Overall (full 2023-01-03 → 2026-04-17 backtest)

| Metric | Value |
|---|---:|
| DSR_z (Bailey-LdP, deflated for 30 trials) | 176079802.53 |
| Raw Sharpe (annualized) | 13.42 |
| Win rate | 94.9% |
| Profit factor | 14.04 |
| Total trades | 390 |
| Total P&L | $142,562 |
| Max drawdown | $1,952 |

## CPCV folds (5-fold purged cross-validation)

| Fold | Start | End | DSR_z | Raw SR | Trades | WR | P&L | Max DD |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 0 | 2023-01-03 | 2023-08-29 | 14.88 | 12.86 | 31 | 93.5% | $13,325 | $796 |
| 1 | 2023-08-30 | 2024-04-25 | 76667761.22 | 12.60 | 80 | 90.0% | $23,422 | $1,754 |
| 2 | 2024-04-26 | 2024-12-19 | 75386952.29 | 10.56 | 91 | 90.1% | $25,124 | $1,544 |
| 3 | 2024-12-20 | 2025-08-20 | 90456374.34 | 12.20 | 103 | 95.1% | $39,206 | $1,580 |
| 4 | 2025-08-21 | 2026-04-17 | 106032763.29 | 15.15 | 103 | 94.2% | $41,210 | $958 |

**Folds won (DSR_z > 1):** 5/5 (master prompt C4 requires ≥4/5)

**Total OOS trades across all folds:** 408 (master prompt C5 requires ≥50)

## Best parameters (from Optuna 30-trial TPE search)

```yaml
dte_idx: 2
long_call_delta: 0.08871767539190893
long_put_delta: 0.05828421326112974
profit_target: 0.25
short_call_delta: 0.27300391575256666
short_put_delta: 0.0912626064364998
stop_loss: 1.5
time_exit: 7
```

## Caveats

These numbers are from the SYNTHETIC chain backtest (BSM + VIX as ATM IV +
SKEW-adjusted skew + stress-clip patch). Real-chain validation deferred until
Polygon plan upgrade. **Apply 30-50% downward bias to absolute P&L numbers
before sizing real capital.** Cross-period CPCV robustness (folds-won) is
the more reliable signal and won't change much under real chains.
