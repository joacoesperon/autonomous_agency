# 💓 Innovator Heartbeat — Proactive Pulse

This file defines the autonomous, scheduled tasks that The Innovator executes every 30 minutes without human prompting. These tasks ensure continuous operation and proactive problem detection.

---

## Heartbeat Cycle (Every 30 Minutes)

### TASK 1: System Health Check (Priority: CRITICAL)

**Objective:** Ensure EA_developer pipeline is operational

**Actions:**
```bash
1. Check if Python environment is accessible
   exec: python --version

2. Verify EA_developer can initialize
   exec: python EA_developer/check_setup.py 2>&1 | tail -20

3. Check MT5 connection status (if applicable)
   file_management: cat EA_developer/output/logs/sistema.log | grep -i "mt5" | tail -5

4. Monitor API quota
   exec: python EA_developer/main.py --stats | grep -i "api"
```

**Evaluation Criteria:**
- ✅ Python responds, check_setup passes, MT5 connected (if required), API quota <18/20
- ⚠️ Python OK but check_setup warnings → Log warning, continue
- 🚨 Python fails, MT5 disconnected, or API quota exceeded → Escalate immediately

**Escalation Template:**
```
🚨 INNOVATOR CRITICAL ALERT

Component: [Python/MT5/API]
Status: [Failure details]
Last Successful Run: [Timestamp]
Impact: Cannot generate new strategies

Action Required: Manual intervention needed
Logs: [Attach relevant log excerpt]
```

---

### TASK 2: Pipeline Status Monitoring (Priority: HIGH)

**Objective:** Track ongoing strategy generation and detect stalls

**Actions:**
```bash
1. Check pipeline statistics
   exec: python EA_developer/main.py --stats

2. Parse output for:
   - Total strategies generated (last 7 days)
   - Approval rate
   - Most recent strategy timestamp
   - Current pipeline status (running/idle)

3. Detect anomalies:
   - If NO strategies generated in last 48 hours → Investigate
   - If approval rate <30% for 7 days → Alert owner
   - If pipeline shows "running" for >4 hours → Check for hang
```

**State Machine:**
```
Pipeline States:
├── IDLE → Normal, waiting for next scheduled run
├── RUNNING → Strategy generation in progress (<90 min normal)
├── STALLED → Running >4 hours (investigate logs)
└── ERROR → Last run failed (check error logs)
```

**Auto-Recovery:**
- If STALLED detected → Kill hanging process, restart pipeline
- If ERROR after restart → Escalate to owner

---

### TASK 3: New Strategy Detection (Priority: HIGH)

**Objective:** Identify newly approved strategies and trigger downstream actions

**Actions:**
```bash
1. List approved strategies folder
   file_management: ls -lt EA_developer/output/strategies/aprobadas/ | head -10

2. Compare against last known inventory (stored in memory)

3. For each NEW strategy:
   a. Read the _reporte.txt file
   b. Parse key metrics (PF, Sharpe, DD, Win Rate, etc.)
   c. Validate metrics meet minimum thresholds
   d. Generate executive summary
   e. Update product_inventory.yml
   f. Notify Marketer agent
   g. Notify owner via Telegram
```

**Example Notification to Marketer:**
```yaml
---
message_type: NEW_PRODUCT_READY
strategy_name: "EMA50_200_RSI_v1"
symbol: "EURUSD"
timeframe: "H4"
metrics:
  pf: 1.87
  sharpe: 1.94
  dd: 12.9
  win_rate: 57.7
  net_profit: 8450
files:
  mq5: "EA_developer/output/strategies/aprobadas/EMA50_200_RSI_v1/EMA50_200_RSI_v1.mq5"
  report: "EA_developer/output/strategies/aprobadas/EMA50_200_RSI_v1/EMA50_200_RSI_v1_reporte.txt"
talking_points:
  - "Trend-following strategy for EURUSD H4"
  - "11 years of backtesting (2013-2024)"
  - "Out-of-sample validated: PF 1.71"
  - "Recommended for swing traders"
status: "AWAITING_LAUNCH_CONTENT"
---
```

---

### TASK 4: Inventory Reconciliation (Priority: MEDIUM)

**Objective:** Maintain accurate product catalog and cleanup old files

**Actions:**
```bash
1. Verify product_inventory.yml is in sync with aprobadas/ folder
   - If mismatch → Rebuild inventory from folder scan

2. Check descartadas/ folder size
   - If >50 strategies → Clean strategies older than 90 days

3. Archive old logs
   - Move logs older than 30 days to archive/

4. Database integrity check
   - exec: python EA_developer/main.py --stats
   - Verify record counts match file counts
```

**Cleanup Rules:**
- Keep all approved strategies indefinitely
- Delete rejected strategies >90 days old
- Compress logs >30 days old
- Do NOT delete anything from the last 7 days

---

### TASK 5: Performance Trending (Priority: LOW)

**Objective:** Track quality metrics over time to detect degradation

**Actions:**
```bash
1. Calculate rolling averages (last 30 days):
   - Avg Profit Factor
   - Avg Sharpe Ratio
   - Avg Max Drawdown
   - Approval rate

2. Compare to historical baseline:
   - If Avg PF drops >15% → Alert "Quality degradation detected"
   - If Approval rate drops >20% → Alert "Filter tuning may be needed"

3. Identify trends:
   - Which symbols are most successful?
   - Which timeframes have highest approval?
   - Any systematic failures (e.g., all momentum strategies failing)?
```

**Weekly Trend Report (Every 7 days):**
```
Innovator Performance Trends

Period: [Last30Days]
Strategies Generated: [X]
Approval Rate: [XX%] (Baseline: [XX%])

Quality Metrics:
├── Avg Profit Factor:  [X.XX] (Baseline: [X.XX])  [↑/↓/→]
├── Avg Sharpe Ratio:   [X.XX] (Baseline: [X.XX])  [↑/↓/→]
├── Avg Max Drawdown:   [XX.X%] (Baseline: [XX.X%]) [↑/↓/→]
└── Avg Win Rate:       [XX.X%] (Baseline: [XX.X%]) [↑/↓/→]

Top Performers:
1. [Symbol] [Timeframe] — [X] approved, Avg PF [X.XX]
2. [Symbol] [Timeframe] — [X] approved, Avg PF [X.XX]

Recommendations:
- [Continue current approach / Focus more on XAUUSD / Adjust filters]
```

---

### TASK 6: Scheduled Pipeline Trigger (Priority: CRITICAL)

**Objective:** Maintain 12-hour generation cycle automatically

**Timing Logic:**
```
Last strategy generation completed at: [Timestamp]
Time elapsed: [Hours]

If elapsed >= 12 hours AND API quota < 18:
   → Trigger new pipeline run
   exec: python EA_developer/main.py --once

If elapsed >= 12 hours AND API quota >= 18:
   → Postpone to next heartbeat (30 min)
   → Log: "Paused due to API quota limit"

If elapsed < 12 hours:
   → Wait (no action)
```

**Pre-Flight Checks Before Triggering:**
1. ✅ MT5 is connected (if required)
2. ✅ API quota available (<18 requests used)
3. ✅ No pipeline currently running
4. ✅ System health checks passing
5. ✅ Disk space available (>5GB free)

**If ANY pre-flight check fails:**
- Log the failure
- Skip this cycle
- Retry on next heartbeat
- If fails 3 consecutive heartbeats → Escalate to owner

---

### TASK 7: Proactive Communication (Priority: MEDIUM)

**Objective:** Keep stakeholders informed without spamming

**Communication Schedule:**

**Immediate Notifications:**
- ✅ New strategy approved → Notify Marketer + Owner
- 🚨 Critical system failure → Notify Owner immediately
- ⚠️ API quota 90% depleted → Warning to Owner

**Daily Digest (Once per day, 9 AM EST):**
```
Good morning,

Innovator Daily Summary:
├── Strategies Generated Last 24h: [X]
├── Approved: [X] | Rejected: [X]
├── Pipeline Status: [Healthy/Warning/Critical]
├── Next Scheduled Run: [Timestamp]
└── API Quota Remaining: [X/20]

[No action required | Action items below]
```

**Weekly Report (Every Monday, 10 AM EST):**
- See TASK 5 output
- Include strategic recommendations

**Monthly Audit (First Monday of month):**
- Complete performance analysis
- ROI calculation (LLM API costs vs strategies approved)
- Recommended filter adjustments

---

## Heartbeat State Persistence

**Memory Variables to Track:**
```yaml
heartbeat_state:
  last_health_check: "2026-03-20T12:30:00Z"
  last_pipeline_trigger: "2026-03-20T06:00:00Z"
  last_strategy_detected: "2026-03-19T18:45:00Z"
  last_inventory_sync: "2026-03-20T12:00:00Z"
  last_trend_report: "2026-03-18T10:00:00Z"

  known_strategies:
    - "EMA50_200_RSI_v1"
    - "BreakoutGold_v2"

  api_quota_today: 12
  consecutive_failures: 0

  alerts_sent_today:
    - "new_strategy_EMA50_200_RSI_v1"

  performance_baseline:
    avg_pf: 1.65
    avg_sharpe: 1.42
    avg_dd: 18.5
    approval_rate: 42.0
```

**Persistence:** Save state after each heartbeat to `/agent_squad/innovator/heartbeat_state.yml`

---

## Error Handling During Heartbeat

### Non-Critical Errors (Continue Operation)
- API quota temporarily unavailable → Skip this heartbeat, retry next
- Log file unreadable → Use default values, flag for manual review
- Inventory sync takes >2 min → Timeout, retry later

### Critical Errors (Escalate Immediately)
- Cannot execute any Python command
- EA_developer folder missing or corrupted
- Persistent API failures (3+ heartbeats)
- Out of disk space

**Escalation Protocol:**
1. Log full error context
2. Send Telegram alert to owner
3. Pause non-essential heartbeat tasks
4. Continue only health monitoring
5. Wait for human intervention

---

## Optimization & Fine-Tuning

**Review this heartbeat configuration monthly:**
- Are 30-minute intervals optimal? (Consider 15 min for faster response)
- Are notifications too frequent? (Adjust thresholds)
- Any tasks that should be hourly instead of every heartbeat?
- API quota management effective?

**Continuous Improvement:**
- Track how often each task triggers an action vs skips
- Measure time taken per task (target <5 sec total heartbeat duration)
- Identify and eliminate redundant checks

---

*Heartbeat keeps The Innovator alive and proactive. This is the pulse of autonomous operation.*
