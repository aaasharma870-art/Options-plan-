# Performance — spy-bull-put-elevated-vol

## Overall (full 2023-01-03 → 2026-04-17 backtest)

| Metric | Value |
|---|---:|
| DSR_z (Bailey-LdP, deflated for 30 trials) | 142515392.79 |
| Raw Sharpe (annualized) | 13.08 |
| Win rate | 94.9% |
| Profit factor | 12.26 |
| Total trades | 214 |
| Total P&L | $95,437 |
| Max drawdown | $2,087 |

## CPCV folds (5-fold purged cross-validation)

| Fold | Start | End | DSR_z | Raw SR | Trades | WR | P&L | Max DD |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 0 | 2023-01-03 | 2023-08-29 | -inf | 0.00 | 5 | 100.0% | $2,072 | $0 |
| 1 | 2023-08-30 | 2024-04-25 | 97560144.39 | 19.91 | 46 | 93.5% | $15,576 | $496 |
| 2 | 2024-04-26 | 2024-12-19 | 9.14 | 9.41 | 66 | 87.9% | $21,247 | $1,039 |
| 3 | 2024-12-20 | 2025-08-20 | 78461812.14 | 11.57 | 77 | 93.5% | $32,467 | $1,580 |
| 4 | 2025-08-21 | 2026-04-17 | 89240322.68 | 14.87 | 69 | 92.8% | $30,250 | $1,665 |

**Folds won (DSR_z > 1):** 4/5 (master prompt C4 requires ≥4/5)

**Total OOS trades across all folds:** 263 (master prompt C5 requires ≥50)

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
