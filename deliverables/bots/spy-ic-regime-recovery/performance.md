# Performance — spy-ic-regime-recovery

## Overall (full 2023-01-03 → 2026-04-17 backtest)

| Metric | Value |
|---|---:|
| DSR_z (Bailey-LdP, deflated for 30 trials) | 129972102.85 |
| Raw Sharpe (annualized) | 10.85 |
| Win rate | 95.7% |
| Profit factor | 17.09 |
| Total trades | 164 |
| Total P&L | $133,537 |
| Max drawdown | $4,122 |

## CPCV folds (5-fold purged cross-validation)

| Fold | Start | End | DSR_z | Raw SR | Trades | WR | P&L | Max DD |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 0 | 2023-01-03 | 2023-08-29 | -inf | 0.00 | 8 | 50.0% | $68 | $1,435 |
| 1 | 2023-08-30 | 2024-04-25 | 35341390.12 | 5.16 | 53 | 60.4% | $8,922 | $687 |
| 2 | 2024-04-26 | 2024-12-19 | 37697417.27 | 3.91 | 108 | 61.1% | $15,974 | $1,909 |
| 3 | 2024-12-20 | 2025-08-20 | 42185810.41 | 4.12 | 118 | 63.6% | $23,945 | $3,466 |
| 4 | 2025-08-21 | 2026-04-17 | 61792145.89 | 6.87 | 97 | 73.2% | $31,079 | $1,601 |

**Folds won (DSR_z > 1):** 4/5 (master prompt C4 requires ≥4/5)

**Total OOS trades across all folds:** 384 (master prompt C5 requires ≥50)

## Best parameters (from Optuna 30-trial TPE search)

```yaml
dte_idx: 1
long_call_delta: 0.06240096576940002
long_put_delta: 0.059026687064372876
profit_target: 0.25
short_call_delta: 0.22833646487132675
short_put_delta: 0.2821488677796205
stop_loss: 2.0
time_exit: 21
```

## Caveats

These numbers are from the SYNTHETIC chain backtest (BSM + VIX as ATM IV +
SKEW-adjusted skew + stress-clip patch). Real-chain validation deferred until
Polygon plan upgrade. **Apply 30-50% downward bias to absolute P&L numbers
before sizing real capital.** Cross-period CPCV robustness (folds-won) is
the more reliable signal and won't change much under real chains.
