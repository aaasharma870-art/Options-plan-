# delta-optimizer Bot Suite — Summary

**Generated:** 2026-04-20
**Pipeline:** Phase 0 (data) → 1 (regime) → 2 (gates) → 3 (bot maker) → 4 (portfolio) → 5 (deliverables)

---

## The bots

| Bot | Structure | Underlying | Gate type | Equal wt | Mean-var wt | Role |
|---|---|---|---|---:|---:|---|
| spy-iron-fly-low-vvix | Iron Butterfly | SPY | Aggressive + VVIX<110 + RV5d<12% | 14.3% | **40.0%** | Pin-risk premium when vol-of-vol suppressed |
| spy-tight-ic-aggressive | Iron Condor | SPY | Aggressive | 14.3% | **36.6%** | Always-on short-vol when no kill switches |
| spy-bear-call-post-spike-fade | Bear Call Vertical | SPY | Aggressive + VIX 5d-spike + SPY<5dSMA | 14.3% | **17.3%** | Mean-reversion fade post-spike |
| aryan_optimized_legacy | Iron Condor | SPY | _none — legacy_ | 14.3% | 6.0% | Replaces existing live bot with regime-gated version |
| spy-bull-put-elevated-vol | Bull Put Vertical | SPY | Neutral + VIX>20 + SPY>20dSMA | 14.3% | 0.0% | Vol-crush + drift directional bot |
| spy-ic-regime-recovery | Iron Condor | SPY | Regime RED→GREEN/YELLOW transition | 14.3% | 0.0% | Event-driven entry on regime flips |
| qqq-ic-extension | Iron Condor | QQQ | Neutral | 14.3% | 0.0% | Premium-collection diversifier off SPY surface |

The mean-variance optimizer **zeros out the bottom 3** because their daily-PnL correlation with bots already in the portfolio is > 0.7 — they add risk without commensurate edge. **Recommended deployment: equal-weight all 7** (more robust to chain-modeling artifacts than mean-variance).

## Aggregate portfolio metrics (synthetic-chain backtest, 2023-01-03 → 2026-04-17)

| Method | Sharpe | Max DD | Max DD % | p95 daily loss | Worst day |
|---|---:|---:|---:|---:|---:|
| equal_weight | 5.03 | $1,719 | 3.4% | -0.28% | -$775 |
| risk_parity | 5.14 | $1,258 | 2.5% | -0.20% | -$739 |
| mean_variance (40% cap) | 5.68 | $798 | 1.6% | -0.07% | -$710 |

Starting capital: $50,000. **All four aggregate gates pass for all three methods.** Sharpes are inflated by the synthetic chain (real-data Sharpe likely 1.5-3.0 range — see `validation_summary.md`); relative ranking is meaningful.

## Key stress-test result

**The April 2025 VIX-spike window** (2025-03-15 to 2025-05-15) — equivalent to the period that caused the original $9k blowup that started this project — **is now profitable at +$6,335 with $1,719 max drawdown (3.4%)** under the equal-weight portfolio. The regime gates work as designed.

## How to deploy

1. Read `validation_summary.md` first (caveats matter).
2. Read `regime_monitor.md` (daily process for tracking the regime score).
3. Read `portfolio_kill_switches.md` (account-wide halt conditions).
4. Read `build_order.md` (paper-first sequence).
5. For each bot, read `bots/<bot_id>/{README,oa_build_guide,kill_switches}.md` in that order. Build it in OA. Paper-trade for 2 weeks. Promote to live only after the WR is within ±10pp of expected.
