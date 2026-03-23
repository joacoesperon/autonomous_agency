# 💓 Operator Heartbeat — Financial Monitoring Pulse

This file defines the autonomous, scheduled tasks that The Operator executes every 30 minutes without human prompting. These tasks ensure continuous financial monitoring, fraud detection, and revenue tracking with zero tolerance for errors.

---

## Heartbeat Cycle (Every 30 Minutes)

### TASK 1: Sales Monitoring (Priority: CRITICAL)

**Objective:** Detect every new sale in real-time and process immediately

**Actions:**
```bash
1. Query Whop API for new sales since last heartbeat
   whop_api: get_sales({
     since: last_check_timestamp,
     status: "completed"
   })

2. For each new sale detected:
   a. Extract sale data:
      - purchase_id
      - customer_email
      - product_name
      - amount: $147.00 (or current price)
      - timestamp
      - affiliate_id (if present)
      - payment_method

   b. Validate sale:
      ✅ Amount matches expected price ($147)
      ✅ Product exists in catalog
      ✅ Payment status = "completed"
      ⚠️  If validation fails → Alert owner immediately

   c. Log sale to database:
      file_management: append to /agent_squad/operator/sales_log.yml

   d. Update revenue counters:
      - daily_revenue += $147
      - monthly_revenue += $147
      - total_sales_count += 1

   e. Process affiliate attribution (if applicable):
      → See TASK 3

   f. Notify owner via Telegram:
      → See communication template
```

**Real-Time Notification to Owner:**
```
💰 NEW SALE #[count_today]

Product: [ProductName]
Amount: $147.00
Customer: [first 20 chars of email]
Affiliate: [affiliate_name or "Direct"]

📊 Today: $[total_today] ([X] sales)
📊 Month: $[total_month] ([X] sales)

[View Full Receipt] [View Customer]
```

**Performance Tracking:**
```
Log per heartbeat:
- New sales detected: [X]
- Revenue added: $[Amount]
- Avg time from sale to detection: [seconds]
- API response time: [ms]
```

---

### TASK 2: Refund Request Monitoring (Priority: CRITICAL)

**Objective:** Detect ALL refund requests immediately and escalate to owner within 5 minutes

**Actions:**
```bash
1. Check multiple refund request sources:
   a. Whop platform notifications (webhook)
      whop_api: get_refund_requests({status: "pending"})

   b. Community Manager escalation queue
      file_management: read /shared/escalation_queue.yml
      → Filter: type = "refund_request"

   c. Stripe dispute notifications (chargebacks)
      stripe_api: get_disputes({status: "needs_response"})

2. For EACH refund request:
   a. Assign unique ID: ref_YYYYMMDD_###
   b. Collect full context (see Workflow 2 in AGENTS.md)
   c. Run fraud detection analysis
   d. ESCALATE to owner immediately (NEVER auto-approve)

3. Track escalation status:
   - Time since escalation: [minutes]
   - Owner response: [Awaiting / Approved / Denied]
   - If >24h no response → Send reminder to owner
```

**Fraud Detection Checks:**
```
For each refund request:
├── Customer History:
│   ├── Previous refunds? → FLAG if >0
│   ├── Days since purchase? → FLAG if <1
│   ├── Multiple purchases same IP? → FLAG if >1
│   └── High-risk payment method? → FLAG if detected

├── Pattern Analysis:
│   ├── Refund rate today >10%? → FLAG (systematic issue)
│   ├── Same reason >2 times today? → FLAG (product problem)
│   ├── Affiliate involved? → FLAG (commission fraud risk)
│   └── VPN/proxy detected? → FLAG (abuse)

└── Risk Score: [Low / Medium / High / Critical]
```

**Escalation Message Template:**
```
🚨 REFUND REQUEST [ref_20260320_001]

Risk Level: [LOW/MEDIUM/HIGH/CRITICAL]
Customer: [email]
Product: [BotName]
Amount: $147.00
Purchase Date: [date] ([X] days ago)

Reason: "[Customer's stated reason]"

Support Attempted:
[List of troubleshooting from Community Manager]

Red Flags:
[List any detected or "None"]

Financial Impact:
- Refund: $147.00
- Non-recoverable fees: ~$4.56
- Affiliate commission clawback: $[amount or "$0"]
- Net loss: ~$[amount]

Customer History:
- Total purchases: [X]
- Previous refunds: [X]
- Account age: [X] days

Recommendation:
[Approve / Deny / Offer partial / Offer support extension]

[APPROVE FULL] [APPROVE PARTIAL $X] [DENY] [ESCALATE TO ME]

Conversation: [Link]
```

**Refund Status Tracking:**
```
Monitor pending refunds:
├── Awaiting owner approval: [X]
├── Approved, awaiting execution: [X]
├── Completed: [X]
└── Denied: [X]

If refund approved >48h ago and NOT executed:
→ Remind owner: "Refund ref_[ID] approved but not yet processed in Whop"
```

---

### TASK 3: Affiliate Tracking (Priority: HIGH)

**Objective:** Accurately attribute sales to affiliates and track commission obligations

**Actions:**
```bash
1. For each new sale with affiliate_id:
   a. Validate affiliate exists in system
   b. Calculate commission:
      - Sale amount: $147.00
      - Commission rate: 40%
      - Commission owed: $58.80

   c. Log commission:
      file_management: append to /agent_squad/operator/affiliate_commissions_pending.yml
      ---
      affiliate_id: "aff_12345"
      affiliate_name: "@username"
      sale_id: "sale_xyz"
      sale_date: "2026-03-20"
      product: "EMA50_200_RSI_v1"
      sale_amount: 147.00
      commission_rate: 0.40
      commission_owed: 58.80
      status: "pending"
      ---

   d. Update affiliate leaderboard (monthly rankings)

2. If refund processed on affiliate sale:
   a. Find corresponding commission record
   b. Update status: "pending" → "clawed_back"
   c. Deduct from affiliate's pending balance
   d. Note: "Refund on original sale [sale_id]"

3. Monthly payout preparation (last day of month):
   → See TASK 6
```

**Affiliate Leaderboard (Updated Each Sale):**
```yaml
affiliate_leaderboard_march_2026:
  - rank: 1
    affiliate_id: "aff_12345"
    name: "@topaffiliate"
    sales: 23
    revenue_generated: $3,381.00
    commissions_earned: $1,352.40
    refunds: 2
    net_commission: $1,234.80

  - rank: 2
    affiliate_id: "aff_67890"
    name: "@affiliate2"
    sales: 15
    revenue_generated: $2,205.00
    commissions_earned: $882.00
    refunds: 0
    net_commission: $882.00

[Continue for all affiliates]
```

---

### TASK 4: Revenue Reconciliation (Priority: CRITICAL)

**Objective:** Ensure internal records match Whop/Stripe data exactly (zero discrepancy tolerance)

**Actions:**
```bash
1. Every hour (every 2nd heartbeat):
   a. Fetch Whop total sales for current day
      whop_api: get_daily_total({date: today})

   b. Fetch internal sales log total for today
      file_management: sum /agent_squad/operator/sales_log.yml (today)

   c. Compare:
      Whop total: $[Amount]
      Internal total: $[Amount]
      Discrepancy: $[Difference]

   d. If discrepancy ≠ $0:
      ⚠️  ALERT: Revenue mismatch detected
      → Escalate to owner immediately with details
      → Pause all automated reporting until reconciled

2. Fetch Stripe fees for today:
   stripe_api: get_fees({date: today})

3. Calculate actual net revenue:
   Net = Gross sales - Refunds - Stripe fees - Whop fees

4. Update financial dashboard:
   file_management: write to /shared/financial_dashboard.yml
```

**Reconciliation Report (If Discrepancy):**
```
🚨 REVENUE RECONCILIATION ALERT

Discrepancy Detected: $[Amount]

Whop Total (Source of Truth): $[Amount]
Internal Log Total: $[Amount]
Difference: $[Amount]

Possible Causes:
- Missed webhook (sale not logged)
- Duplicate logging (sale counted twice)
- Refund not yet reflected
- Manual sale adjustment in Whop

Action Required:
Please review Whop dashboard and confirm correct total.
I will resync records once verified.

[Resync from Whop] [Investigate Manually]
```

---

### TASK 5: Expense Tracking (Priority: MEDIUM)

**Objective:** Monitor operational costs and maintain positive cash flow

**Actions:**
```bash
1. Track daily expenses (real or estimated):
   a. Gemini API costs:
      - Check usage via API if available
      - Estimate: ~$0 (free tier, but monitor request count)
      - Alert if approaching free tier limit (18/20 calls)

   b. Whop platform fee:
      - Rate: 3.5% + $0.30 per transaction
      - Calculate from today's sales:
        Fee = (sales_count * $0.30) + (total_revenue * 0.035)

   c. Stripe processing fee:
      - Rate: 2.9% + $0.30 per transaction
      - Fetch actual fee from Stripe API (more accurate)

   d. Other costs (if applicable):
      - VPS hosting: $0 (Oracle free tier or local)
      - Domain: ~$1/month
      - Email service: $0 (free tier)

2. Calculate daily expense total:
   Daily expenses = Whop fees + Stripe fees + API costs + Other

3. Update expense log:
   file_management: append to /agent_squad/operator/expense_log.yml

4. Calculate daily profit:
   Net profit = Daily revenue - Daily expenses - Refunds

5. Alert if expense spike:
   If daily expenses >30% of revenue → Alert owner
   If expenses >Revenue → CRITICAL ALERT (burning cash)
```

**Expense Dashboard (Updated Hourly):**
```yaml
daily_expenses_2026_03_20:
  gemini_api: $0.00
  whop_fees: $12.60  # 3 sales @ ($0.30 + 3.5% of $147)
  stripe_fees: $13.17  # 3 sales @ ($0.30 + 2.9% of $147)
  other: $0.03  # Domain prorated
  total: $25.80

daily_revenue: $441.00
daily_refunds: $0.00
daily_net_profit: $415.20

profit_margin: 94.1%  # Excellent
```

---

### TASK 6: Financial Reporting (Priority: MEDIUM)

**Objective:** Generate timely, accurate financial reports for owner decision-making

**Scheduled Reports:**

**Daily Report (Every day at 11 PM EST):**
```bash
# Generate comprehensive daily summary
1. Aggregate all day's data:
   - Sales count & revenue
   - Refunds count & amount
   - Expenses breakdown
   - Net profit
   - Affiliate commissions owed
   - Top-selling product

2. Format report (see AGENTS.md template)

3. Send to owner via Telegram at 11 PM EST

4. Log report to /agent_squad/operator/reports/daily/
```

**Weekly Report (Every Monday at 10 AM EST):**
```bash
# Generate weekly performance summary
1. Aggregate last 7 days:
   - Total sales, revenue
   - Week-over-week growth %
   - Refund rate
   - Top products
   - Affiliate performance
   - Profit margin trend

2. Generate insights and recommendations

3. Send to owner via Telegram

4. Log report to /agent_squad/operator/reports/weekly/
```

**Monthly Report (First day of new month at 9 AM EST):**
```bash
# Generate monthly financial audit
1. Aggregate full month:
   - Total sales & revenue
   - Refunds & refund rate
   - Expense breakdown
   - Net profit & margin
   - Affiliate commissions paid
   - Customer acquisition cost (if available)

2. Generate P&L statement

3. Prepare affiliate payout report (see AGENTS.md Workflow 4)

4. Send comprehensive report to owner

5. Archive to /agent_squad/operator/reports/monthly/
```

**Heartbeat: Monitor Report Schedule**
```
Each heartbeat, check:
├── Is it 11 PM EST? → Generate daily report
├── Is it Monday 10 AM EST? → Generate weekly report
├── Is it 1st of month 9 AM EST? → Generate monthly report
└── Otherwise → Continue other tasks
```

---

### TASK 7: Fraud & Anomaly Detection (Priority: HIGH)

**Objective:** Proactively detect suspicious patterns before they cause financial damage

**Actions:**
```bash
1. Analyze sales patterns:
   a. Sales velocity:
      - Current hour sales vs 24h average
      - If >300% spike → Alert: "Unusual sales spike detected"
      - Could be: Viral moment (good) or bot attack (bad)

   b. Geographic clustering:
      - If all sales from same country/region suddenly → Flag
      - If VPN/proxy pattern detected → Flag

   c. Payment method clustering:
      - If unusual payment method ratio → Flag
      - If multiple failed payments then success → Card testing?

2. Analyze refund patterns:
   a. Refund rate:
      - If refund rate >15% today → Alert
      - If same refund reason >3 times → Systematic product issue

   b. Refund timing:
      - If multiple refunds within hours of purchase → Buyer's remorse or fraud?

   c. Affiliate refunds:
      - If affiliate's referred customers refund >50% → Commission fraud?

3. Analyze expense anomalies:
   a. If API costs spike (Gemini quota exceeded) → Alert
   b. If platform fees don't match expected % → Reconciliation issue
   c. If new expense line item appears → Investigate

4. Compile fraud report (if red flags detected):
```

**Fraud Alert Template:**
```
🚨 FRAUD/ANOMALY ALERT

Type: [Unusual Sales Spike / Refund Pattern / Expense Anomaly]
Severity: [Low / Medium / High / Critical]
Detected: [Timestamp]

Details:
[Specific pattern description]

Data:
[Relevant statistics]

Potential Impact:
[Financial risk estimate]

Recommended Actions:
1. [Immediate action]
2. [Investigation step]
3. [Preventive measure]

[Investigate] [Dismiss as Normal] [Escalate] [Pause Operations]
```

---

## Heartbeat State Persistence

**Memory Variables to Track:**
```yaml
heartbeat_state:
  last_sales_check: "2026-03-20T14:30:00Z"
  last_refund_check: "2026-03-20T14:30:00Z"
  last_affiliate_sync: "2026-03-20T14:30:00Z"
  last_reconciliation: "2026-03-20T14:00:00Z"  # Hourly
  last_expense_update: "2026-03-20T14:30:00Z"
  last_report_generated: "2026-03-19T23:00:00Z"  # Daily 11 PM
  last_fraud_scan: "2026-03-20T14:30:00Z"

  daily_metrics:
    date: "2026-03-20"
    sales_count: 3
    revenue: 441.00
    refunds_count: 0
    refunds_amount: 0.00
    expenses: 25.80
    net_profit: 415.20

  monthly_metrics:
    month: "2026-03"
    sales_count: 17
    revenue: 2499.00
    refunds_count: 1
    refunds_amount: 147.00
    expenses: 146.60
    net_profit: 2205.40

  alert_status:
    reconciliation_ok: true
    fraud_detected: false
    api_quota_ok: true
    revenue_healthy: true
```

**Persistence:** Save state after each heartbeat to `/agent_squad/operator/heartbeat_state.yml`

---

## Error Handling During Heartbeat

### Non-Critical Errors (Continue Operation)
- Whop API timeout → Retry once, skip if still fails, log warning
- Stripe API slow response → Wait up to 10sec, use cached data if timeout
- Report generation fails → Log error, send manual notification to owner
- Affiliate leaderboard calculation error → Skip update, retry next heartbeat

### Critical Errors (Escalate Immediately)
- Whop API completely unreachable (cannot detect sales)
- Revenue reconciliation fails 3 heartbeats in a row
- Refund request detected but escalation system broken
- Financial data corruption (logs don't parse)

**Escalation Protocol:**
1. Log full error with stack trace
2. Send Telegram alert: "🚨 OPERATOR CRITICAL ERROR - FINANCIAL MONITORING IMPAIRED"
3. Pause automated reporting (unreliable data)
4. Continue basic monitoring (sales/refund detection only)
5. Wait for owner to investigate and fix

---

## Edge Cases & Exceptions

### Whop Platform Maintenance
```
If Whop returns "503 Service Unavailable":
├── Expected during scheduled maintenance (rare)
├── Do NOT alert owner immediately (could be brief)
├── Wait 15 minutes and retry
├── If still down >30 min → Alert owner: "Whop platform down"
└── Resume normal operation when platform returns
```

### Duplicate Sale Detection
```
If sale appears twice (rare webhook bug):
├── Check internal log for duplicate purchase_id
├── If duplicate detected:
│   └── Do NOT log second time
│   └── Do NOT notify owner again
│   └── Log: "Duplicate sale event ignored: [purchase_id]"
└── Continue normal operation
```

### Partial Refund Handling
```
If owner approves partial refund (e.g., $75 instead of $147):
├── Log as partial refund with amount
├── Update revenue: Deduct only partial amount
├── Affiliate commission: Recalculate proportionally
│   └── Original commission: $58.80 (40% of $147)
│   └── Partial refund: $75
│   └── New commission: $28.80 (40% of $72 remaining)
└── Update all reports with partial refund data
```

### Chargeback/Dispute Handling
```
If Stripe notifies of chargeback:
├── Classify as: "Dispute" not "Refund Request"
├── Immediate escalation (CRITICAL priority)
├── Flag customer account (potential fraud)
├── Provide evidence to owner:
│   ├── Purchase receipt
│   ├── Product delivery confirmation (email with .mq5 file)
│   ├── Support conversation logs
│   └── Stripe dispute form auto-filled
└── Owner submits evidence via Stripe dashboard
```

---

## Optimization & Fine-Tuning

**Review this heartbeat configuration monthly:**
- Is 30-minute interval sufficient for sales monitoring? (Consider real-time webhooks)
- Are reports useful or too detailed? (Adjust based on owner feedback)
- Fraud detection false positive rate? (Tune thresholds)
- API call efficiency? (Batch requests if possible)

**Continuous Improvement:**
- Track time from sale → notification (target <30 seconds)
- Measure reconciliation accuracy (target 100%)
- Monitor refund escalation time (target <5 min from request)
- Analyze fraud detection effectiveness (true positive rate)

---

*Heartbeat keeps The Operator vigilant and precise. Every dollar tracked. Every refund guarded. This is financial discipline on autopilot.*
