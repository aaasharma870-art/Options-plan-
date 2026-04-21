# Deployment Runbook — Getting the Build to Actually Work

**Goal:** the 7-bot delta-optimizer suite correctly built in Option Alpha paper mode, using Options-Claw for repetitive work and your hands for the parts that need to be right the first time.

**Reality this runbook is built on:**
- Options-Claw's Tier 3 (Computer Use) is probabilistic, not deterministic
- OA's UI has shipped changes since Options-Claw was last tested (March 2026)
- The PDF build manual was written against assumed features; some may not exist as described
- Every bot that gets built wrong is 30-60 minutes to find and fix later
- You are trading real money eventually; measure twice, cut once

Do not deviate from the sequence below without a good reason.

---

## PHASE 0 — PRE-FLIGHT (do in one sitting, ~90 min)

### 0.1 Freshen the selector database (15-30 min)

Computer Use relies on `tier2_playwright/ui_selectors.json`. If OA shipped UI updates since March, the selectors are stale.

```powershell
cd C:\Users\aaash\Documents\AryanClawWorkspace\Options-claw
python tier2_playwright/selector_discovery.py
```

Watch the output. Common results:
- `X/Y selectors matched` where X/Y > 90% → good, minor drift
- X/Y < 70% → STOP, UI has changed meaningfully, update selectors or recalibrate

If the script can't even log you in: you need to manually re-authenticate. Run it again after logging in.

**Commit the updated selectors to Options-Claw's repo** before proceeding. If Computer Use corrupts them later, you have a known-good checkpoint.

### 0.2 Verify Anthropic API budget alerts (5 min)

At the Anthropic console (https://console.anthropic.com/):
- Set a spending limit at $30 total for this build
- Set alerts at $10, $20, $25
- Confirm email notifications

If a task gets stuck in a loop, cost can compound fast. The budget cap is your safety net.

### 0.3 OA account readiness (10 min)

Log into Option Alpha in a regular browser. Verify:
- [ ] Top-right shows PAPER (switch from LIVE if needed)
- [ ] Brokerage shows CONNECTED for your broker
- [ ] Timezone is America/New_York
- [ ] Account balance noted: `$__________`
- [ ] Scaling factor = balance / 50000 = `_______`

Close the browser afterwards — Options-Claw opens its own session.

### 0.4 Git snapshot Options-Claw (5 min)

```powershell
cd C:\Users\aaash\Documents\AryanClawWorkspace\Options-claw
git add .
git commit -m "Pre-delta-optimizer-build snapshot"
git tag pre-delta-optimizer-build
```

If something goes wrong mid-build and Options-Claw state gets corrupted, `git checkout pre-delta-optimizer-build` restores you.

### 0.5 Task 00 warm-up (5-10 min, $0.50-1)

Run the ONLY task that doesn't create or modify anything:

```powershell
cd C:\Users\aaash\Documents\AryanClawWorkspace\Options-claw
.\tier3_computer_use\run-task-v2.ps1 -TaskFile "C:\Users\aaash\delta-optimizer\deliverables\oa_claw_tasks\00_global_setup.txt"
```

What you're verifying:
- Options-Claw launches the browser successfully
- Computer Use can read your OA dashboard
- It can navigate to Account Settings
- It returns a coherent summary (matches what you saw in step 0.3)
- Cost is in the $0.50-$1 range (not $5+)

If Task 00 fails: FIX BEFORE PROCEEDING. Nothing downstream will work if the foundation is broken.

---

## PHASE 1 — MANUAL BUILD: SYSTEM BOT + SENSOR A (~60-90 min, $0)

**Do this yourself in OA. Do NOT use Computer Use for this phase.**

Why: this is where you catch every spec-vs-reality gap before automation tries to fight it. It's also the only way to gain confidence in what the system is actually doing.

### 1.1 SYSTEM Host Bot (10 min)

Follow Worksheet 1 in `deliverables/OA_BUILD_WORKSHEETS.md`. Create the bot by hand.

**Take screenshots of each screen as you go.** These are your ground-truth reference — if OA's UI differs from the PDF, your screenshots show what it actually looks like for the automation task files to handle.

### 1.2 Sensor A — Regime Classifier (45-60 min)

Follow Worksheet 2 in `deliverables/OA_BUILD_WORKSHEETS.md`.

As you build, verify each of these assumptions against reality. If any FAILS, note the workaround in a file `PHASE_1_FINDINGS.md`:

| Assumption | If it holds | If it fails (workaround) |
|---|---|---|
| "Make Shared Automation" checkbox exists | ✓ | Use shared-automation menu on the automation list page instead |
| Compound OR decision with 3 conditions in one node | ✓ | Use 3 nested decisions, each with YES → same action |
| `Symbol Comparison: VIX × 1.05 vs VIX3M` with multiplier | ✓ | Use absolute threshold: VIX Last > 25 (proxy for 1.05 backwardation) |
| `Symbol Price Change: 2 std devs 30-day` | ✓ | Use `Symbol Price Change: increased by at least 20% over 5 days` |
| `Calendar Event: FOMC Meeting / CPI / NFP` as selectable | ✓ | Use a manual tag you set yourself each morning (`BLACKOUT_MANUAL`) |
| `Bot has tag` + `Bot does NOT have tag` decisions | ✓ | probably holds; critical if not |

**Once Sensor A is built, click Test Run.** It should tag the SYSTEM bot with the correct regime based on today's VIX.

### 1.3 Verification stop — wait ONE trading day (passive)

Do NOT proceed to Phase 2 until you've confirmed Sensor A fires on schedule:

- At 9:47 AM the next trading day, open OA → SYSTEM bot → Tags tab
- Confirm exactly ONE `REGIME_*` tag is present
- Confirm it matches today's VIX (if VIX < 17, should be REGIME_GREEN, etc.)
- Ideally wait 2-3 trading days across different VIX values

**If the tag doesn't appear, or appears wrong, Phase 2 is blocked.** Debug the sensor logic (by hand) until it works.

### 1.4 Write `PHASE_1_FINDINGS.md` (10 min)

Document any spec-vs-reality gaps you encountered. This file feeds into Phase 2 — you'll hand-edit the task files to incorporate these workarounds before Computer Use runs them.

Save this in `deliverables/oa_claw_tasks/PHASE_1_FINDINGS.md`.

---

## PHASE 2 — AUTOMATE REMAINING SENSORS (~60 min, $3-6)

Now Options-Claw gets to drive. But only for Sensors B, C, D — you already built A.

### 2.1 Update task files with your findings

Before running any task, open each of:
- `03_sensor_b_recovery.txt`
- `04_sensor_c_blackout.txt`
- `05_sensor_d_earnings.txt`

Apply the workarounds from `PHASE_1_FINDINGS.md`. For example:
- If "Make Shared Automation" is on the list page, rewrite the step to say so
- If Calendar Event doesn't have FOMC as a selectable type, replace with the manual-tag approach

Pro tip: if you find yourself rewriting 50%+ of a task file, it's faster to just build that sensor by hand too.

### 2.2 Run Sensor B (Task 03), verify, then Sensor C (Task 04), then Sensor D (Task 05)

One at a time. After each:
- Review Computer Use's screenshots
- Open OA yourself and confirm the automation exists with correct fields
- Run Test Run on the new sensor
- Verify its tag behavior matches spec

### 2.3 Verification stop — wait ONE trading day

Next trading morning at 9:47 AM, open OA:
- [ ] SYSTEM bot shows one `REGIME_*` tag (from A)
- [ ] If RED, `REGIME_RED_YESTERDAY` also present (from A)
- [ ] Today's FOMC/CPI/NFP → BLACKOUT tag (from C)
- [ ] Top-5 earnings within 3 days → CLUSTER_RISK (from D)
- [ ] If yesterday RED but today not → `REGIME_RECOVERY` (from B)

**If any sensor isn't firing correctly, fix it BEFORE building any bot.** A broken sensor means broken bots.

---

## PHASE 3 — MANUAL BUILD: BOT 1 (~90 min, $0)

**Build Bot 1 by hand.** Same reasoning as Phase 1: the first of its kind needs to be right, and you learn the OA bot-building flow.

Follow Worksheet 6. Take screenshots. Document any spec-vs-reality gaps for Bots 2-7.

**Critical:** Attach Sensors A, B, C to Bot 1. Verify the attachment. Tomorrow morning, verify Bot 1 has received its REGIME_* tag from the SYSTEM sensors (if shared-automation propagation works, Bot 1's tags tab should match SYSTEM's).

### 3.1 Paper-trade Bot 1 for 4 weeks

This is NOT optional. This is the primary validation that your entire pipeline works.

- Daily 5-min check: any trades? P&L? any errors?
- Weekly summary: running WR, max single loss, total trades
- Compare to the 81.6% predicted WR

After 4 weeks with 10+ trades:
- WR ≥ 70% AND no loss > $400 → promote to Live L1 (25% sizing) via path in EXECUTIVE_BUILD_REPORT.md §13
- WR 60-70% → continue paper
- WR < 60% → **STOP the entire project**. The synthetic calibration is wrong; rebuild the spec before building Bot 2.

---

## PHASE 4 — AUTOMATE BOTS 2-7 (sequential, 2+ weeks per bot)

Only if Bot 1 paper-passed promotion criteria do you continue.

### 4.1 For each of Bots 2-7:

1. Apply `PHASE_1_FINDINGS.md` + any Bot-1-specific spec gaps to the task file
2. Run the task via Computer Use
3. Inspect the result carefully (you're automating now, but you haven't turned off your brain)
4. Verify the bot's automations match the worksheet exactly
5. Let it paper-trade for 2 weeks (4 weeks for Bot 6)
6. If promotion criteria met → enable live at 25%
7. If not met → continue paper OR drop the bot from the suite
8. ONLY THEN move to the next bot

Don't compress. Two weeks per bot is the point. If you skip it, you're not building a system — you're flipping a coin seven times in a row.

---

## WHAT TO DO WHEN COMPUTER USE GETS STUCK

### Scenario A: "UI element X not found"

1. Let it fail (don't force-retry — that burns tokens)
2. Open OA yourself and screenshot the current screen
3. Compare to the task file's description
4. If OA changed UI → update the task file and re-run
5. If element genuinely doesn't exist → update the spec (this is a real finding), note in `PHASE_1_FINDINGS.md`, move on

### Scenario B: "Decision tree loops or doesn't save"

Computer Use sometimes clicks Save before the automation is fully configured. Check OA manually:
1. Does the automation exist?
2. Are all expected decisions present?
3. If yes → accept the partial success, add the missing decisions by hand
4. If no → re-run the task with more aggressive "verify before save" instructions

### Scenario C: "Cost exceeds $5 on a single task"

Stop. Something's wrong. Common causes:
- Selectors stale → Computer Use is exploring instead of clicking
- Task file references OA feature that doesn't exist → CU is trying alternatives
- OA's UI had an unexpected popup/modal that derailed the flow

Abort the task. Debug by hand.

### Scenario D: "Computer Use claims success but OA shows nothing"

Never trust the claim. Always verify by opening OA yourself. If CU says "saved successfully" but the automation doesn't appear in OA's list, it probably never saved. Re-do the task manually.

### Scenario E: "Bot opened a position during paper — but with wrong strikes"

This means the scanner fired but the position criteria produced unexpected selections. Check:
1. Did the regime tag match what you expected?
2. Are the short/long delta targets within OA's available strikes?
3. Is OA's chain liquidity thin today (wider strike spacing)?

If strikes are off by 1 on a $5-wide IC, that's acceptable. If they're off by more, halt the bot and investigate.

---

## BUDGET CHECKPOINTS

Update this table as you go:

| Phase | Budget | Actual | Running total |
|---|---:|---:|---:|
| 0.5 Task 00 | $1 | $___ | $___ |
| 2.2 Task 03 (Sensor B) | $2 | $___ | $___ |
| 2.2 Task 04 (Sensor C) | $2 | $___ | $___ |
| 2.2 Task 05 (Sensor D) | $2 | $___ | $___ |
| 4.1 Task 11 (Bot 2) | $3 | $___ | $___ |
| 4.1 Task 12 (Bot 3) | $3 | $___ | $___ |
| 4.1 Task 13 (Bot 4) | $3 | $___ | $___ |
| 4.1 Task 14 (Bot 5) | $3 | $___ | $___ |
| 4.1 Task 15 (Bot 6) | $3 | $___ | $___ |
| 4.1 Task 16 (Bot 7) | $3 | $___ | $___ |
| **Total** | **$25** | | |

If running total exceeds $35 at any point, STOP and investigate. Costs 40%+ over budget mean something is looping.

---

## ROLLBACK PROCEDURES

### If a sensor is wrong (wrong tag, fires at wrong time)

1. Open OA, navigate to the sensor, disable it
2. Fix by hand
3. Re-enable
4. Wait 1 trading day to verify

### If a bot opens an unexpected position in paper

1. Close the position manually
2. Disable the bot's scanner
3. Inspect the scanner's Test Run to find the decision that fired incorrectly
4. Fix the decision
5. Test Run again
6. Re-enable

### If Options-Claw corrupted the selectors or task files

```powershell
cd C:\Users\aaash\Documents\AryanClawWorkspace\Options-claw
git checkout pre-delta-optimizer-build
```

This resets Options-Claw to the snapshot from Phase 0.4.

### If the WHOLE build went wrong

Delete the SYSTEM bot and all 7 bot shells in OA. Their automations go with them. Start over from Phase 1. This is painful but clean.

---

## REALITY-CHECK DECISION TREE

Ask yourself at each phase:

```
Is Sensor A firing correctly for 2+ trading days?
├── No  → STOP. Do not build any bot. Fix sensor first.
└── Yes → continue

Are all 4 sensors firing correctly for 1+ trading day?
├── No  → STOP. Debug the broken sensors.
└── Yes → build Bot 1 (by hand) and paper

Is Bot 1 paper WR matching the ±15% window (70-85%)?
├── No, below 60%   → STOP the project. Synthetic calibration is wrong.
├── No, above 95%   → STOP. Chain model is too clean; real-chain needed before live.
├── Yes, 70-85%     → promote Bot 1 to Live L1; start Bot 2
└── Yes, 60-70%     → keep Bot 1 in paper; start Bot 2 paper

For each subsequent bot: same decision.

If at Bot 3+ you have 2+ bots diverging from predictions:
→ STOP the suite rollout. Something systemic is wrong with the spec.
→ Fix before building more.
```

---

## THE BOTTOM LINE

The automation is a productivity tool, not a substitute for your attention. The sequence above should produce a correctly-built suite in about 6-8 weeks of calendar time (mostly paper-trade waiting) for less than $30 in API costs.

If you try to run all 14 task files in one evening to "save time," you will spend the next month debugging bots that look right but trade wrong, and the calendar time lost will far exceed the 6-8 weeks you'd have taken to do it right.

Build the first of each kind by hand. Automate the repeat. Wait between phases. When in doubt, stop and think.

---

*Updated: 2026-04-20. Review and update this runbook if any phase consistently produces unexpected results.*
