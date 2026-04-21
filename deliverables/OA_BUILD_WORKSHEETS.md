# OA Build Worksheets — one page per object

**Companion to `OA_BUILD_MANUAL.pdf`.** Print this document (or keep on a second monitor). For each sensor and each bot, there's one page of fields + checkboxes. Tick as you click. When every box on a page is ticked, that object is built correctly.

**Architectural assumption (from `OA_BUILD_MANUAL.pdf`):** pure-native Option Alpha. No TradingView, no webhooks. Shared sensor automations tag each bot with regime state; scanners read the tags.

**Critical rules (read before every session):**
- All 4 sensors built BEFORE any bot (in order A → B → C → D)
- Each bot gets sensors A, B, C attached. Bot 7 also gets D.
- Every bot starts in PAPER mode. Minimum 2 weeks paper (4 weeks for Bot 6).
- Sequential build: don't start Bot 2 until Bot 1 has 2+ weeks clean paper data.

---

## WORKSHEET 0 — Global setup (do first, once)

| # | Check | Done |
|---|---|:---:|
| 1 | Option Alpha account has Lifetime Membership (Supercharged enabled) | ☐ |
| 2 | Top-right shows PAPER mode (switch from LIVE if needed) | ☐ |
| 3 | Brokerage Connection shows `Connected` (Tradier / Schwab / TradeStation) | ☐ |
| 4 | Timezone set to `America/New_York` | ☐ |
| 5 | Account balance recorded: `$__________` | ☐ |
| 6 | Scaling factor from $50k baseline: `_______` (balance ÷ 50,000) | ☐ |
| 7 | PDT Protection default checkbox On | ☐ |

---

# PART A — SHARED SENSORS (build first)

---

## WORKSHEET 1 — SYSTEM Host Bot

Host bot that will contain the 4 shared sensor automations. Never trades.

| Field | Value | Done |
|---|---|:---:|
| Bots → Create New Bot | | ☐ |
| Name | `SYSTEM — Regime Sensor Host` | ☐ |
| Symbols | `SPY` (required placeholder) | ☐ |
| Allocation | `$1,000` | ☐ |
| Total open positions | `0` | ☐ |
| Daily open positions | `0` | ☐ |
| Broker | any connected | ☐ |
| SmartPricing | `Normal` | ☐ |
| Scan Speed | `Standard` | ☐ |
| Click `Create Bot` | — | ☐ |

**Verify:** bot appears in bot list with $1,000 allocation, 0 position limits.

---

## WORKSHEET 2 — Sensor A: Regime Classifier

Inside SYSTEM bot → Automations → New Automation → **Event** → `Make Shared Automation`.

| Field | Value | Done |
|---|---|:---:|
| Automation name | `Sensor A — Regime Classifier` | ☐ |
| Make Shared Automation | Yes | ☐ |
| Trigger type | Recurring Schedule | ☐ |
| Time | `9:45 AM ET` | ☐ |
| Days | Mon Tue Wed Thu Fri | ☐ |
| Skip market holidays | Yes | ☐ |

**Decision flow — build top-to-bottom:**

| Step | Action / Decision | Tag/Value | Done |
|---|---|---|:---:|
| A1 | Action: Untag Bot | `REGIME_GREEN` | ☐ |
| A2 | Action: Untag Bot | `REGIME_ORANGE` | ☐ |
| A3 | Action: Untag Bot | `REGIME_ORANGE_PLUS` | ☐ |
| A4 | Action: Untag Bot | `REGIME_RED` | ☐ |
| A5 | Decision: Symbol Indicator | VIX Last price > `30` | ☐ |
| A5-Yes | Action: Tag Bot | `REGIME_RED` | ☐ |
| A5-Yes | Action: Tag Bot | `REGIME_RED_YESTERDAY` (shadow tag for Sensor B) | ☐ |
| A5-Yes | Action: Tag Bot | `RED_D1` (day-streak counter; optional but recommended) | ☐ |
| A6 | On A5 No branch: Decision: compound OR | see below | ☐ |
| A6a | OR: Symbol Indicator | VIX Last price > `25` | ☐ |
| A6b | OR: Symbol Comparison | VIX > `VIX3M × 1.05` | ☐ |
| A6c | OR: Symbol Price Change | VIX has increased by at least `2 std devs (30-day)` over `5 days` | ☐ |
| A6-Yes | Action: Tag Bot | `REGIME_ORANGE_PLUS` | ☐ |
| A7 | On A6 No branch: Decision: Symbol Indicator | VIX Last price > `20` | ☐ |
| A7-Yes | Action: Tag Bot | `REGIME_ORANGE` | ☐ |
| A8 | On A7 No branch: Action: Tag Bot | `REGIME_GREEN` | ☐ |
| — | Save Automation | — | ☐ |
| — | Toggle Enabled = ON | — | ☐ |

**Test Run** (top-right button): observe which branch fires. Matches today's VIX? ☐

**Verification tomorrow 9:47 AM:** SYSTEM bot's Tags tab shows exactly one REGIME_* tag. ☐

---

## WORKSHEET 3 — Sensor B: Recovery Detector

Inside SYSTEM bot → New Automation → **Event** → Make Shared.

| Field | Value | Done |
|---|---|:---:|
| Automation name | `Sensor B — Recovery Detector` | ☐ |
| Trigger | Recurring, `9:46 AM ET`, M-F | ☐ |

| Step | Action / Decision | Tag/Value | Done |
|---|---|---|:---:|
| B1 | Action: Untag Bot | `REGIME_RECOVERY` | ☐ |
| B2 | Decision: Bot has tag | `REGIME_RED_YESTERDAY` | ☐ |
| B2-Yes | Decision: Bot does NOT have tag | `REGIME_RED` | ☐ |
| B2-Yes-Yes | Action: Tag Bot | `REGIME_RECOVERY` | ☐ |
| B2-Yes-Yes | Action: Untag Bot | `REGIME_RED_YESTERDAY` | ☐ |
| B2-Yes-No | Action: Untag Bot | `REGIME_RED_YESTERDAY` (keep rolled for next day) | ☐ |
| B2-Yes-No | Action: Tag Bot | `REGIME_RED_YESTERDAY` (re-tag for tomorrow) | ☐ |
| — | Save + Enable | — | ☐ |

**Sanity:** Sensor B fires 1 minute after Sensor A so tags are fresh. Don't move the time.

---

## WORKSHEET 4 — Sensor C: Event Blackout

Inside SYSTEM bot → New Automation → Event → Make Shared.

| Field | Value | Done |
|---|---|:---:|
| Automation name | `Sensor C — Event Blackout` | ☐ |
| Trigger | Recurring, `9:30 AM ET`, M-F | ☐ |

| Step | Action / Decision | Value | Done |
|---|---|---|:---:|
| C1 | Action: Untag Bot | `BLACKOUT` | ☐ |
| C2 | Decision: Calendar Event | FOMC Meeting today | ☐ |
| C2-Yes | Action: Tag Bot | `BLACKOUT` | ☐ |
| C3 | On C2 No: Decision: Calendar Event | CPI Release today | ☐ |
| C3-Yes | Action: Tag Bot | `BLACKOUT` | ☐ |
| C4 | On C3 No: Decision: Calendar Event | NFP Release today | ☐ |
| C4-Yes | Action: Tag Bot | `BLACKOUT` | ☐ |
| — | Save + Enable | — | ☐ |

---

## WORKSHEET 5 — Sensor D: Earnings Cluster (for QQQ bot)

Inside SYSTEM bot → New Automation → Event → Make Shared.

| Field | Value | Done |
|---|---|:---:|
| Automation name | `Sensor D — Earnings Cluster` | ☐ |
| Trigger | Recurring, `9:30 AM ET`, M-F | ☐ |

| Step | Action / Decision | Value | Done |
|---|---|---|:---:|
| D1 | Action: Untag Bot | `CLUSTER_RISK` | ☐ |
| D2 | Decision: Symbol Earnings Event | `NVDA` has earnings in next 3 trading days | ☐ |
| D2-Yes | Action: Tag Bot | `CLUSTER_RISK` | ☐ |
| D3 | On D2 No: same decision for | `MSFT` | ☐ |
| D3-Yes | Action: Tag Bot | `CLUSTER_RISK` | ☐ |
| D4 | On D3 No: same decision for | `GOOGL` | ☐ |
| D4-Yes | Action: Tag Bot | `CLUSTER_RISK` | ☐ |
| D5 | On D4 No: same decision for | `META` | ☐ |
| D5-Yes | Action: Tag Bot | `CLUSTER_RISK` | ☐ |
| D6 | On D5 No: same decision for | `AMZN` | ☐ |
| D6-Yes | Action: Tag Bot | `CLUSTER_RISK` | ☐ |
| — | Save + Enable | — | ☐ |

**Fallback:** if OA supports `Symbol Earnings Event(QQQ, 3 days)` with constituent-aggregation, one decision replaces D2-D6. Verify in test run.

---

# PART B — THE 7 BOTS (build sequentially; 2+ weeks paper between each)

---

## WORKSHEET 6 — Bot 1: SPY Iron Fly Low VVIX

**Build order:** FIRST. Highest confidence. Paper 4 weeks minimum.

### Bot Shell

| Field | Value | Done |
|---|---|:---:|
| Name | `1. SPY Iron Fly Low VVIX` | ☐ |
| Symbols | `SPY` | ☐ |
| Allocation | `$7,143` (scale × factor from W0) | ☐ |
| Total open positions | `2` | ☐ |
| Daily open positions | `1` | ☐ |
| SmartPricing | `Normal` | ☐ |
| Scan Speed | `5 min` | ☐ |
| PDT Protection | ON | ☐ |
| Attach Shared Automations | Sensors A, B, C | ☐ |

### Scanner: "IF Entry Scanner"

Trigger: every 5 min, 9:45 AM – 3:45 PM ET.

| # | Decision | Criteria | Done |
|---|---|---|:---:|
| 1 | Bot Tag | Bot has tag `REGIME_GREEN` | ☐ |
| 2 | Bot Tag | Bot does NOT have tag `BLACKOUT` | ☐ |
| 3 | Symbol Indicator | VVIX Last price < `90` | ☐ |
| 4 | Symbol Indicator | SPY IV Rank < `40` | ☐ |
| 5 | Symbol Indicator Comparison | SPY ATR(14) < SMA(ATR(14), 20) (fallback: ATR/price < 1.6%) | ☐ |
| 6 | Bot Tag | Bot does NOT have tag `CLUSTER_RISK` | ☐ |
| 7 | Bot State | Bot open positions < `2` | ☐ |

### Position Criteria (on all-Yes: Open Position)

| Field | Value | Done |
|---|---|:---:|
| Strategy | Iron Butterfly | ☐ |
| Width Match | Enabled | ☐ |
| Short Call Delta | `0.50` ±0.02 | ☐ |
| Short Put Delta | `0.50` ±0.02 | ☐ |
| Long Call Delta | `0.10` | ☐ |
| Long Put Delta | `0.10` | ☐ |
| DTE Window | `30 to 45` days, closest to 35 | ☐ |
| Quantity | `1` contract | ☐ |
| Min Credit | `15%` of spread width | ☐ |
| Bid-Ask Spread Cap | `$0.10` per leg | ☐ |
| Open Interest Min | `500` per leg | ☐ |
| Order Type | SmartPricing Normal | ☐ |
| Order Price Target | Mid at entry | ☐ |

### Exit Options (standard exits panel)

| Field | Value | Done |
|---|---|:---:|
| Profit Target | `25%` of max profit | ☐ |
| Stop Loss | `2.0×` credit received | ☐ |
| Time Exit | `21 DTE` | ☐ |
| PDT Protection | On | ☐ |

### Monitor: "IF Exit Monitor" (every 1 min while position open)

| # | Decision | Action | Done |
|---|---|---|:---:|
| M1 | Symbol Indicator: VVIX > `120` | Close Position | ☐ |
| M2 | Bot Tag: has `REGIME_RED` | Close Position | ☐ |
| M3 | Bot Tag: has `BLACKOUT` AND Position DTE < `7` | Close Position | ☐ |

### Pre-Flight

| Check | Done |
|---|:---:|
| PAPER mode confirmed (top-right) | ☐ |
| Test Run on scanner shows decisions evaluating | ☐ |
| Screenshot of full config archived as `bot_1_config_YYYY-MM-DD.png` | ☐ |
| Tracking spreadsheet row created for Bot 1 | ☐ |
| Slept on it overnight before enabling | ☐ |

**Paper promotion criteria (4 weeks, min 10 trades):** WR ≥ `70%` AND no loss > `$400` AND cumulative P&L positive.

---

## WORKSHEET 7 — Bot 2: SPY Bear Call Post Spike

**Build order:** SECOND (after Bot 1 has 2 weeks clean paper).

### Bot Shell

| Field | Value | Done |
|---|---|:---:|
| Name | `2. SPY Bear Call Post Spike` | ☐ |
| Symbols | `SPY` | ☐ |
| Allocation | `$7,143` | ☐ |
| Total open positions | `2` | ☐ |
| Daily open positions | `1` | ☐ |
| Scan Speed | `5 min` | ☐ |
| Attach | Sensors A, B, C | ☐ |

### Scanner: "BC Entry Scanner" (every 5 min, 9:45 AM – 3:45 PM)

| # | Decision | Criteria | Done |
|---|---|---|:---:|
| 1 | Bot Tag (OR) | has `REGIME_ORANGE_PLUS` OR has `REGIME_RED` | ☐ |
| 2 | Bot Tag | does NOT have `BLACKOUT` | ☐ |
| 3 | Symbol Price Change | VIX increased ≥ `2 std devs` over `5 days` | ☐ |
| 4 | Symbol Indicator Comparison | SPY price < SPY SMA(5) | ☐ |
| 5 | Symbol Indicator | SPY RSI(2) < `20` | ☐ |
| 6 | Symbol Indicator | SPY IV Rank > `50` | ☐ |
| 7 | Bot State | open positions < `2` | ☐ |

### Position (Open Trade Idea, Short Call Spread)

| Field | Value | Done |
|---|---|:---:|
| Strategy | Short Call Spread (Bear Call) | ☐ |
| Watchlist | none (SPY only) | ☐ |
| DTE Range | `14 to 21` days | ☐ |
| Short Call Delta | `0.16 – 0.22` (target 0.18) | ☐ |
| Width | `$5` | ☐ |
| Min Credit (% width) | `25%` | ☐ |
| Min POP | `70%` | ☐ |
| Min Reward/Risk | `0.33` | ☐ |
| OI Min (all legs) | `200` | ☐ |
| Avoid Earnings | Yes | ☐ |
| Quantity | `1` contract | ☐ |

### Exits

| Field | Value | Done |
|---|---|:---:|
| Profit Target | `35%` of credit | ☐ |
| Stop Loss | `1.5×` credit | ☐ |
| Time Exit | `14 DTE` | ☐ |
| Monitor M1 | VIX < 20 → Close | ☐ |
| Monitor M2 | SPY > SPY SMA(5) × 1.015 → Close | ☐ |
| Monitor M3 | has `REGIME_RED` AND DTE < 10 → Close | ☐ |

**Paper:** WR ≥ `65%`, no loss > `$400`, min 8 trades.

---

## WORKSHEET 8 — Bot 3: Aryan Optimized Legacy IC

**Build order:** THIRD. Replaces existing live bot — pause the old one AFTER 2 weeks clean paper here.

### Bot Shell

| Field | Value | Done |
|---|---|:---:|
| Name | `3. Aryan Optimized Legacy IC` | ☐ |
| Symbols | `SPY` | ☐ |
| Allocation | `$7,143` | ☐ |
| Total open positions | `3` | ☐ |
| Daily open positions | `1` | ☐ |
| Scan Speed | `5 min` | ☐ |
| Attach | Sensors A, B, C | ☐ |

### Scanner: "Legacy IC Entry Scanner"

| # | Decision | Criteria | Done |
|---|---|---|:---:|
| 1 | Bot Tag (OR) | has `REGIME_GREEN` OR has `REGIME_ORANGE` | ☐ |
| 2 | Bot Tag | does NOT have `BLACKOUT` | ☐ |
| 3 | Symbol Indicator | VIX < `25` | ☐ |
| 4 | Symbol Comparison | VIX < VIX3M (contango) | ☐ |
| 5 | Symbol Indicator | SPY IV Rank > `30` | ☐ |
| 6 | Symbol Indicator | SPY ATR(14) / SPY price < `1.8%` | ☐ |
| 7 | Bot State | open positions < `3` | ☐ |

### Position (Trade Idea, Iron Condor)

| Field | Value | Done |
|---|---|:---:|
| Strategy | Iron Condor | ☐ |
| DTE Range | `30 to 45` | ☐ |
| Short Deltas | `0.16 – 0.20` (target 0.18) | ☐ |
| Long Deltas | `0.06 – 0.08` (target 0.07) | ☐ |
| Width | `$5-10`, width-matched | ☐ |
| Min Credit (% width) | `15%` | ☐ |
| Min POP | `65%` | ☐ |
| OI Min per leg | `500` | ☐ |
| Bid-Ask Cap | `$0.08` per leg | ☐ |
| Quantity | `1` contract | ☐ |

### Exits

| Field | Value | Done |
|---|---|:---:|
| Profit Target | `50%` of credit | ☐ |
| Stop Loss | `2.0×` credit | ☐ |
| Time Exit | `21 DTE` | ☐ |
| Monitor M1 | has `REGIME_RED` → Close | ☐ |
| Monitor M2 | SPY within $2 of either short → Close | ☐ |

**Paper:** WR within ±5% of your live bot's historical 77.7%; min 10 trades; max loss ≤ $500.

---

## WORKSHEET 9 — Bot 4: SPY Tight IC Aggressive

**Build order:** FOURTH. Synthetic-inflated; size cautiously.

### Bot Shell

| Field | Value | Done |
|---|---|:---:|
| Name | `4. SPY Tight IC Aggressive` | ☐ |
| Symbols | `SPY` | ☐ |
| Allocation | `$7,143` | ☐ |
| Total open positions | `4` | ☐ |
| Daily open positions | `2` | ☐ |
| Scan Speed | `5 min` | ☐ |
| Attach | Sensors A, B, C | ☐ |

### Scanner: "Tight IC Scanner"

| # | Decision | Criteria | Done |
|---|---|---|:---:|
| 1 | Bot Tag | has `REGIME_GREEN` (STRICT — not ORANGE) | ☐ |
| 2 | Bot Tag | does NOT have `BLACKOUT` | ☐ |
| 3 | Bot Tag | does NOT have `CLUSTER_RISK` | ☐ |
| 4 | Symbol Indicator | SPY IV Rank `20 – 60` | ☐ |
| 5 | Symbol Indicator | VIX < `18` | ☐ |
| 6 | Symbol Comparison | VIX < VIX3M | ☐ |
| 7 | Bot State | open positions < `4` | ☐ |

### Position (Iron Condor)

| Field | Value | Done |
|---|---|:---:|
| Strategy | Iron Condor | ☐ |
| DTE Range | `25 to 35` | ☐ |
| Short Deltas | `0.22 – 0.28` (target 0.25) | ☐ |
| Long Deltas | `0.08 – 0.12` (target 0.10) | ☐ |
| Width | `$5`, matched | ☐ |
| Min Credit | `22%` of width | ☐ |
| Min POP | `60%` | ☐ |
| OI Min | `500` | ☐ |
| Quantity | `1` | ☐ |

### Exits

| Field | Value | Done |
|---|---|:---:|
| Profit Target | `40%` | ☐ |
| Stop Loss | `2.0×` credit | ☐ |
| Time Exit | `21 DTE` | ☐ |
| Touch Exit | SPY within `0.5%` of short strike → Close | ☐ |
| Monitor | any transition to `REGIME_ORANGE_PLUS` → Close all | ☐ |

**Paper:** WR ≥ `75%` (higher bar — matches synthetic), no loss > $400, min 15 trades.

---

## WORKSHEET 10 — Bot 5: SPY Bull Put Elevated Vol

### Bot Shell

| Field | Value | Done |
|---|---|:---:|
| Name | `5. SPY Bull Put Elevated Vol` | ☐ |
| Symbols | `SPY` | ☐ |
| Allocation | `$7,143` | ☐ |
| Total open positions | `3` | ☐ |
| Daily open positions | `1` | ☐ |
| Scan Speed | `5 min` | ☐ |
| Attach | Sensors A, B, C | ☐ |

### Scanner

| # | Decision | Criteria | Done |
|---|---|---|:---:|
| 1 | Bot Tag (OR) | `REGIME_ORANGE` OR `REGIME_ORANGE_PLUS` | ☐ |
| 2 | Bot Tag | NOT `BLACKOUT` | ☐ |
| 3 | Symbol Indicator | VIX ≥ `20` | ☐ |
| 4 | Symbol Comparison | SPY > SPY SMA(20) daily | ☐ |
| 5 | Symbol Indicator | SPY RSI(14) `40 – 65` | ☐ |
| 6 | Symbol Indicator | SPY IV Rank > `40` | ☐ |
| 7 | Bot State | open positions < `3` | ☐ |

### Position (Trade Idea, Bull Put)

| Field | Value | Done |
|---|---|:---:|
| Strategy | Short Put Spread (Bull Put) | ☐ |
| DTE Range | `30 to 45` | ☐ |
| Short Put Delta | `0.20 – 0.25` | ☐ |
| Width | `$5` | ☐ |
| Min Credit | `28%` of width | ☐ |
| Min POP | `68%` | ☐ |
| OI Min | `300` per leg | ☐ |
| Avoid Earnings | Yes | ☐ |
| Quantity | `1` | ☐ |

### Exits

| Field | Value | Done |
|---|---|:---:|
| Profit Target | `50%` | ☐ |
| Stop Loss | `2.0×` credit | ☐ |
| Time Exit | `21 DTE` | ☐ |
| Monitor M1 | SPY < SPY SMA(20) → Close (trend broken) | ☐ |
| Monitor M2 | has `REGIME_RED` → Close | ☐ |

**Paper:** WR ≥ `75%`, no loss > $400, min 8 trades.

---

## WORKSHEET 11 — Bot 6: SPY IC Regime Recovery

Rare-event bot. **Paper 8 weeks minimum** until 5+ trades.

### Bot Shell

| Field | Value | Done |
|---|---|:---:|
| Name | `6. SPY IC Regime Recovery` | ☐ |
| Symbols | `SPY` | ☐ |
| Allocation | `$7,143` | ☐ |
| Total open positions | `2` | ☐ |
| Daily open positions | `1` | ☐ |
| Scan Speed | `5 min` | ☐ |
| Attach | Sensors A, B, C | ☐ |

### Scanner

| # | Decision | Criteria | Done |
|---|---|---|:---:|
| 1 | Bot Tag | has `REGIME_RECOVERY` | ☐ |
| 2 | Symbol Indicator | VIX < `25` | ☐ |
| 3 | Symbol Price Change | VIX dropped ≥ `15%` from 10-day high | ☐ |
| 4 | Symbol Indicator | SPY IV Rank > `40` | ☐ |
| 5 | Bot Tag | NOT `BLACKOUT` | ☐ |
| 6 | Bot State | open positions < `2` | ☐ |

### Position (Iron Condor)

| Field | Value | Done |
|---|---|:---:|
| Strategy | Iron Condor | ☐ |
| DTE Range | `25 to 40` | ☐ |
| Short Deltas | `0.14 – 0.18` (wider — recovery uncertainty) | ☐ |
| Long Deltas | `0.05 – 0.07` | ☐ |
| Width | `$10` | ☐ |
| Min Credit | `18%` of width | ☐ |
| Quantity | `1` | ☐ |

### Exits

| Field | Value | Done |
|---|---|:---:|
| Profit Target | `40%` | ☐ |
| Stop Loss | `2.0×` credit | ☐ |
| Time Exit | `21 DTE` | ☐ |
| Monitor | has `REGIME_RED` → Close | ☐ |

**Paper:** WR ≥ `65%` AND ≥ 5 trades (may need 8+ weeks) AND no loss > $500.

---

## WORKSHEET 12 — Bot 7: QQQ IC Extension

**The only bot that needs Sensor D attached.**

### Bot Shell

| Field | Value | Done |
|---|---|:---:|
| Name | `7. QQQ IC Extension` | ☐ |
| Symbols | `QQQ` (not SPY) | ☐ |
| Allocation | `$7,143` | ☐ |
| Total open positions | `3` | ☐ |
| Daily open positions | `1` | ☐ |
| Scan Speed | `5 min` | ☐ |
| Attach | Sensors A, B, C, **AND D** | ☐ |

### Scanner

| # | Decision | Criteria | Done |
|---|---|---|:---:|
| 1 | Bot Tag (OR) | `REGIME_GREEN` OR `REGIME_ORANGE` | ☐ |
| 2 | Bot Tag | NOT `BLACKOUT` | ☐ |
| 3 | Bot Tag | NOT `CLUSTER_RISK` (critical) | ☐ |
| 4 | Symbol Indicator | QQQ IV Rank > `30` | ☐ |
| 5 | Symbol Indicator | VIX < `22` | ☐ |
| 6 | Symbol Comparison | VIX < VIX3M | ☐ |
| 7 | Bot State | open positions < `3` | ☐ |

### Position (Iron Condor on QQQ)

| Field | Value | Done |
|---|---|:---:|
| Strategy | Iron Condor | ☐ |
| Symbol | QQQ | ☐ |
| DTE Range | `30 to 45` | ☐ |
| Short Deltas | `0.16 – 0.20` | ☐ |
| Long Deltas | `0.06 – 0.08` | ☐ |
| Width | `$5`, matched | ☐ |
| Min Credit | `18%` of width | ☐ |
| Min POP | `65%` | ☐ |
| OI Min | `300` | ☐ |
| Quantity | `1` | ☐ |

### Exits

| Field | Value | Done |
|---|---|:---:|
| Profit Target | `50%` | ☐ |
| Stop Loss | `2.0×` credit | ☐ |
| Time Exit | `21 DTE` | ☐ |
| Monitor M1 | has `REGIME_RED` → Close | ☐ |
| Monitor M2 | has `CLUSTER_RISK` AND DTE < 14 → Close | ☐ |
| Monitor M3 | QQQ within $3 of short strike → Close | ☐ |

**Paper:** WR ≥ `70%`, no loss > $500, min 10 trades.

---

# MASTER PROGRESS TRACKER

| Object | Built | Tests pass | Enabled (paper) | 2wk paper done | Live L1 | Live L2 | Live L3 | Live Full |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| SYSTEM Host Bot | ☐ | — | — | — | — | — | — | — |
| Sensor A | ☐ | ☐ | ☐ | — | — | — | — | — |
| Sensor B | ☐ | ☐ | ☐ | — | — | — | — | — |
| Sensor C | ☐ | ☐ | ☐ | — | — | — | — | — |
| Sensor D | ☐ | ☐ | ☐ | — | — | — | — | — |
| Bot 1 (iron-fly) | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| Bot 2 (bear-call) | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| Bot 3 (legacy IC) | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| Bot 4 (tight IC) | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| Bot 5 (bull put) | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| Bot 6 (recovery) | ☐ | ☐ | ☐ | ☐(8wk) | ☐ | ☐ | ☐ | ☐ |
| Bot 7 (QQQ IC) | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |

**When you reach "Live Full" on Bot 1 with 90+ days of good data, you're done with the initial deployment phase. Welcome back — we'll review aggregate results and decide whether to migrate from equal-weight toward mean-variance at that point.**
