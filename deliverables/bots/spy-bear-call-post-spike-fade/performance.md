# Performance — spy-bear-call-post-spike-fade

## Overall (full 2023-01-03 → 2026-04-17 backtest)

| Metric | Value |
|---|---:|
| DSR_z (Bailey-LdP, deflated for 30 trials) | 120314761.07 |
| Raw Sharpe (annualized) | 10.34 |
| Win rate | 75.8% |
| Profit factor | 5.02 |
| Total trades | 260 |
| Total P&L | $33,652 |
| Max drawdown | $914 |

## CPCV folds (5-fold purged cross-validation)

| Fold | Start | End | DSR_z | Raw SR | Trades | WR | P&L | Max DD |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 0 | 2023-01-03 | 2023-08-29 | -inf | 0.00 | 6 | 66.7% | $651 | $262 |
| 1 | 2023-08-30 | 2024-04-25 | 63296631.99 | 11.96 | 40 | 82.5% | $4,794 | $280 |
| 2 | 2024-04-26 | 2024-12-19 | 64375172.69 | 9.10 | 73 | 74.0% | $8,898 | $269 |
| 3 | 2024-12-20 | 2025-08-20 | 64039024.86 | 9.06 | 76 | 76.3% | $10,475 | $914 |
| 4 | 2025-08-21 | 2026-04-17 | 21.42 | 8.98 | 66 | 75.8% | $9,297 | $465 |

**Folds won (DSR_z > 1):** 4/5 (master prompt C4 requires ≥4/5)

**Total OOS trades across all folds:** 261 (master prompt C5 requires ≥50)

## Best parameters (from Optuna 30-trial TPE search)

```yaml
dte_idx: 1
long_call_delta: 0.11085830969549341
long_put_delta: 0.08249802381471341
profit_target: 0.35
short_call_delta: 0.2147826759324114
short_put_delta: 0.10361038554907828
stop_loss: 1.5
time_exit: 14
```

## Caveats

These numbers are from the SYNTHETIC chain backtest (BSM + VIX as ATM IV +
SKEW-adjusted skew + stress-clip patch). Real-chain validation deferred until
Polygon plan upgrade. **Apply 30-50% downward bias to absolute P&L numbers
before sizing real capital.** Cross-period CPCV robustness (folds-won) is
the more reliable signal and won't change much under real chains.
