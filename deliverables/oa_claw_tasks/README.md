# Options-Claw Task Files — delta-optimizer Build

These are plain-English task files consumed by your **Options-Claw** automation system (`C:/Users/aaash/Documents/AryanClawWorkspace/Options-claw/`). They instruct the Tier 3 (Computer Use) runner to click through Option Alpha's UI and build every object in the delta-optimizer suite.

## What these task files do — and what they don't

**Do:**
- Tell Options-Claw's Computer Use tier *what* to build in OA, step-by-step
- Cross-reference `deliverables/OA_BUILD_WORKSHEETS.md` for exact field values (no duplication)
- Include safety checkpoints, screenshots, and STOP conditions at every major step
- Force PAPER-mode verification before any bot is created

**Don't:**
- Run the automation themselves — you run them via your Options-Claw orchestrator
- Store your OA credentials — those live in your Options-Claw `.env`
- Know whether OA's current 2026 UI matches the PDF manual exactly — if it has changed, Computer Use may get stuck and STOP (that's intended behavior)

## Before you run ANY of these

1. **Verify Options-Claw still works against current OA UI.** The `ui_selectors.json` may be stale if OA has pushed UI updates since Options-Claw was last tested. Run a quick sanity check:
   ```powershell
   cd C:/Users/aaash/Documents/AryanClawWorkspace/Options-claw
   python tier2_playwright/selector_discovery.py
   ```
   If selectors 404 or Option Alpha's UI has changed structure significantly, update Options-Claw first.

2. **Test the cheapest task first.** Run `00_global_setup.txt` as a warm-up before the heavier ones. That task just verifies account mode and settings — it shouldn't create or modify anything destructive.

3. **Budget.** At $0.50–$2 per complex task (per Options-Claw README), the full 14-task build is ~$7–$28 in Computer Use costs. Keep Anthropic API budget alerts on.

4. **Be present.** Computer Use is not infallible. Every task file has PAUSE POINTS where the runner stops and summarizes what it did. Review each summary before approving "continue" — don't let it run unattended on complex tasks.

## Execution order (strict — do NOT parallelize)

Run these sequentially. Each depends on the previous. Skip none.

| # | File | What it builds | Time est. | Depends on |
|---|---|---|---|---|
| 00 | `00_global_setup.txt` | Verify paper mode, broker, timezone | 5 min | nothing |
| 01 | `01_system_host_bot.txt` | SYSTEM Host Bot (sensor container) | 5 min | 00 |
| 02 | `02_sensor_a_regime.txt` | Sensor A (Regime Classifier) | 60 min | 01 |
| 03 | `03_sensor_b_recovery.txt` | Sensor B (Recovery Detector) | 30 min | 02 |
| 04 | `04_sensor_c_blackout.txt` | Sensor C (Event Blackout) | 20 min | 01 |
| 05 | `05_sensor_d_earnings.txt` | Sensor D (Earnings Cluster) | 20 min | 01 |
| 10 | `10_bot1_iron_fly.txt` | Bot 1: SPY Iron Fly Low VVIX | 90 min | 02-05 |
| 11 | `11_bot2_bear_call.txt` | Bot 2: SPY Bear Call Post Spike | 60 min | 10 paper |
| 12 | `12_bot3_legacy_ic.txt` | Bot 3: Aryan Optimized Legacy IC | 60 min | 11 paper |
| 13 | `13_bot4_tight_ic.txt` | Bot 4: SPY Tight IC Aggressive | 60 min | 12 paper |
| 14 | `14_bot5_bull_put.txt` | Bot 5: SPY Bull Put Elevated Vol | 60 min | 13 paper |
| 15 | `15_bot6_regime_recovery.txt` | Bot 6: SPY IC Regime Recovery | 60 min | 14 paper |
| 16 | `16_bot7_qqq_ic.txt` | Bot 7: QQQ IC Extension | 60 min | 15 paper |

**"Depends on X paper"** means "wait until bot X has completed its 2-week (or 4-week for Bot 6) paper-trade validation period before running the next task file." DO NOT build all 7 bots in one sitting just because the task files are all here. The sequential paper discipline is non-negotiable.

## How to run one

From your Options-Claw root:

```powershell
# Via orchestrator (routes to Computer Use tier)
python -c "
import asyncio
from core.orchestrator import run_task
asyncio.run(run_task(open(r'C:/Users/aaash/delta-optimizer/deliverables/oa_claw_tasks/00_global_setup.txt').read()))
"

# Or via Tier 3 runner directly
cd tier3_computer_use
.\run-task-v2.ps1 -TaskFile C:\Users\aaash\delta-optimizer\deliverables\oa_claw_tasks\00_global_setup.txt
```

## What to do if a task fails mid-execution

Options-Claw tasks are designed to STOP, not fail silently. If Computer Use stops and tells you "UI element X not found" or "unexpected screen":

1. Take the screenshot it produced
2. Check if OA's UI differs from `OA_BUILD_MANUAL.pdf` in that specific screen
3. If it does → update `tier2_playwright/ui_selectors.json` or update this task file and re-run
4. If the field or screen genuinely doesn't exist → the spec needs to be updated (tell me and we'll revise the task file)

Never tell Computer Use to "figure it out" or "try something different" on a trading platform. Stopping and asking is correct behavior.

## Reminders from the manual

- **PAPER MODE, ALWAYS.** Every task file verifies paper mode on entry. If it reports LIVE, the task aborts immediately.
- **Screenshots are not optional.** They're the audit trail. Every major step takes one.
- **Verification checkpoints are explicit.** Each task ends with a checklist that Computer Use must confirm item-by-item before declaring the task complete.

## Files in this directory

```
oa_claw_tasks/
├── README.md                       # this file
├── 00_global_setup.txt             # account mode / broker / timezone check
├── 01_system_host_bot.txt          # SYSTEM bot (sensor container)
├── 02_sensor_a_regime.txt          # Sensor A (Regime Classifier) — most complex
├── 03_sensor_b_recovery.txt        # Sensor B (Recovery Detector)
├── 04_sensor_c_blackout.txt        # Sensor C (Event Blackout)
├── 05_sensor_d_earnings.txt        # Sensor D (Earnings Cluster)
├── 10_bot1_iron_fly.txt            # Bot 1 (highest-confidence, build first)
├── 11_bot2_bear_call.txt           # Bot 2
├── 12_bot3_legacy_ic.txt           # Bot 3 (replaces your existing live bot)
├── 13_bot4_tight_ic.txt            # Bot 4
├── 14_bot5_bull_put.txt            # Bot 5
├── 15_bot6_regime_recovery.txt     # Bot 6 (rare-event; needs 8 weeks paper)
└── 16_bot7_qqq_ic.txt              # Bot 7 (only bot that uses Sensor D)
```
