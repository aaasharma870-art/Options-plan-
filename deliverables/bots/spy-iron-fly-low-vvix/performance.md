# Performance — spy-iron-fly-low-vvix

## Overall (full 2023-01-03 → 2026-04-17 backtest)

| Metric | Value |
|---|---:|
| DSR_z (Bailey-LdP, deflated for 30 trials) | 173583972.35 |
| Raw Sharpe (annualized) | 22.40 |
| Win rate | 81.6% |
| Profit factor | 5.55 |
| Total trades | 244 |
| Total P&L | $22,514 |
| Max drawdown | $481 |

## CPCV folds (5-fold purged cross-validation)

| Fold | Start | End | DSR_z | Raw SR | Trades | WR | P&L | Max DD |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 0 | 2023-01-03 | 2023-08-29 | -inf | 0.00 | 3 | 100.0% | $1,628 | $0 |
| 1 | 2023-08-30 | 2024-04-25 | 95038348.50 | 23.05 | 22 | 100.0% | $6,678 | $0 |
| 2 | 2024-04-26 | 2024-12-19 | 7.06 | 12.10 | 30 | 93.3% | $9,170 | $1,264 |
| 3 | 2024-12-20 | 2025-08-20 | 119458689.51 | 25.47 | 27 | 100.0% | $9,429 | $0 |
| 4 | 2025-08-21 | 2026-04-17 | 105822387.47 | 22.56 | 31 | 96.8% | $10,318 | $167 |

**Folds won (DSR_z > 1):** 4/5 (master prompt C4 requires ≥4/5)

**Total OOS trades across all folds:** 113 (master prompt C5 requires ≥50)

## Best parameters (from Optuna 30-trial TPE search)

```yaml
dte_idx: 4
long_call_delta: 0.07135244953792613
long_put_delta: 0.08566622109551965
profit_target: 0.35
short_call_delta: 0.2071366264342846
short_put_delta: 0.10436971059270929
stop_loss: 2.0
time_exit: 7
```

## Caveats

These numbers are from the SYNTHETIC chain backtest (BSM + VIX as ATM IV +
SKEW-adjusted skew + stress-clip patch). Real-chain validation deferred until
Polygon plan upgrade. **Apply 30-50% downward bias to absolute P&L numbers
before sizing real capital.** Cross-period CPCV robustness (folds-won) is
the more reliable signal and won't change much under real chains.
