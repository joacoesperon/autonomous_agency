# 💓 Marketer Heartbeat — Proactive Content Engine

This file defines the autonomous, scheduled tasks that The Marketer executes every 30 minutes without human prompting. These tasks ensure continuous content pipeline operation and proactive brand building.

---

## Heartbeat Cycle (Every 30 Minutes)

### TASK 1: Trend Monitoring (Priority: HIGH)

**Objective:** Stay ahead of market conversations and identify content opportunities

**Actions:**
```bash
1. Search for trending topics in algo trading space
   tavily-search: "algorithmic trading news last 12 hours"
   tavily-search: "crypto bot trading 2026"
   tavily-search: "forex automation trends"
   tavily-search: "Hyperliquid updates"

2. Filter results for relevance:
   ✅ Retail trader pain points
   ✅ Automation/algo trading discussions
   ✅ Market volatility events (opportunity to highlight bot discipline)
   ✅ Competitor product launches (analyze positioning)
   ❌ Pure price speculation
   ❌ Scam/hype content
   ❌ Irrelevant crypto news

3. Identify top 3 content-worthy trends
```

**Evaluation Logic:**
```
For each trend:
├── Relevance Score (1-10): How related to algo trading?
├── Timeliness (1-10): Is this happening now or old news?
├── Educational Value (1-10): Can we teach something valuable?
└── Brand Fit (1-10): Does it align with Jess Trading values?

If Total Score >=30 → Add to content queue
If Total Score <30 → Discard
```

**Output:** Create trend briefing document
```yaml
trend_brief:
  - topic: "Bitcoin volatility spike reaches 80%"
    relevance: 9
    angle: "Why emotional trading fails during high volatility"
    content_type: "educational_post"
    platforms: ["instagram", "x"]
    priority: "high"

  - topic: "New Hyperliquid leverage options"
    relevance: 7
    angle: "How algo traders can automate leverage management"
    content_type: "educational_thread"
    platforms: ["x"]
    priority: "medium"
```

---

### TASK 2: Innovator Sync (Priority: CRITICAL)

**Objective:** Detect new bot releases and trigger product launch workflow

**Actions:**
```bash
1. Check shared memory for Innovator notifications
   file_management: read /shared/product_inventory.yml

2. Compare against last known inventory:
   - If NEW strategy detected → Trigger WORKFLOW 2 (Product Launch)
   - If no new strategies → Continue normal operations

3. For NEW bot detected:
   a. Parse bot data (name, symbol, timeframe, metrics)
   b. Generate multi-format launch campaign (IG story, post, X thread, LinkedIn)
   c. Priority: HIGH (jump to front of approval queue)
   d. Send to HITL approval immediately
```

**Example Detection:**
```
Last Known Inventory:
- EMA50_200_RSI_v1 (2026-03-15)

Current Inventory:
- EMA50_200_RSI_v1 (2026-03-15)
- BreakoutGold_v2 (2026-03-20) ← NEW!

Action: Generate product launch campaign for BreakoutGold_v2
Status: TRIGGERED
```

**Time Constraint:**
```
Goal: From bot approval → launch content drafted in <2 hours
Acceptable: <4 hours
Escalate if: >6 hours (manual intervention needed)
```

---

### TASK 3: Content Generation (Priority: MEDIUM)

**Objective:** Maintain steady content pipeline with 1-2 posts per day target

**Logic:**
```
Check content calendar:
├── Posts published today: [X]
├── Drafts awaiting approval: [X]
├── Target remaining for today: [2 - X]

If target remaining >0:
   → Generate new content (educational or engagement focus)
If target remaining =0:
   → Queue content for tomorrow
If drafts awaiting approval >5:
   → Pause generation (avoid overwhelming owner)
```

**Content Selection Strategy:**
```
Day-of-Week Mix:
├── Monday:    Educational (trend-based from TASK 1)
├── Tuesday:   Product highlight (existing bot showcase)
├── Wednesday: Educational (trading psychology/strategy)
├── Thursday:  Community engagement (UGC or testimonial if available)
├── Friday:    Educational (market analysis)
├── Saturday:  Light content (brand story or motivational)
└── Sunday:    Off (unless product launch)

Override: Product launch content ALWAYS takes priority
```

**Generation Process:**
```bash
1. Select content type based on day + backlog
2. If educational → Use trend from TASK 1 or topics library
3. Draft caption (150 words max, brand voice)
4. Generate visual (brand-compliant prompt)
5. Validate visual (color palette check)
6. Bundle for HITL approval
7. Add to approval queue
```

**Stop Conditions:**
```
DO NOT generate if:
- >5 drafts already awaiting approval (owner backlog)
- API quota exhausted for image generation
- Critical brand mention detected (TASK 5)
- Owner flagged "pause content" in settings
```

---

### TASK 4: HITL Queue Management (Priority: HIGH)

**Objective:** Manage approval workflow and follow up on pending content

**Actions:**
```bash
1. Check approval queue status
   file_management: read /agent_squad/marketer/approval_queue.yml

2. Categorize by status:
   ├── Awaiting Approval (<24h) → Normal
   ├── Awaiting Approval (24-48h) → Send gentle reminder
   ├── Awaiting Approval (>48h) → Archive to expired/, clear from queue
   ├── Approved + Scheduled → Monitor until publish time
   └── Published → Track performance for 24h post-publish

3. Send reminders (if needed):
```

**Reminder Message Template:**
```
📌 Content Approval Reminder

You have [X] posts awaiting approval:
1. [Type] for [Platform] - Created [hours ago]
2. [Type] for [Platform] - Created [hours ago]

[Review Queue]

Note: Content older than 48h will be auto-archived.
```

**Scheduled Content Execution:**
```
For each approved post with future publish_at time:
├── Current time >= publish_at?
│   ├── YES → Execute publishing
│   │   ├── postfast: {platform, content}
│   │   ├── Log success/failure
│   │   └── Notify owner: "✅ Published: [content_id]"
│   └── NO → Continue monitoring
```

**Error Handling:**
```
If publishing fails:
├── Retry once (30-second delay)
├── If still fails:
│   ├── Move to /marketer/failed_posts/
│   ├── Notify owner: "⚠️ Publishing failed for [ID]: [error]"
│   └── Request manual intervention
└── Do NOT auto-retry >2 times (avoid spam)
```

---

### TASK 5: Brand Mention Monitoring (Priority: MEDIUM)

**Objective:** Detect brand mentions and potential PR issues early

**Actions:**
```bash
1. Search for brand mentions
   tavily-search: "Jess Trading" last 24 hours
   tavily-search: "Jess Trading review"
   tavily-search: "Jess Trading scam" (negative PR detection)

2. Categorize mentions:
   ├── Positive (testimonial, praise) → Flag for Community Manager
   ├── Neutral (informational) → Monitor
   ├── Negative (complaint, scam accusation) → ESCALATE IMMEDIATELY
   └── No mentions → Normal operation

3. If NEGATIVE mention detected:
   ├── Screenshot/save the mention
   ├── Pause all scheduled content
   ├── Escalate to owner with full context
   ├── Wait for strategy before resuming
```

**Escalation Template (Negative PR):**
```
🚨 NEGATIVE BRAND MENTION DETECTED

Platform: [X / Reddit / Forum / etc]
Content: "[Exact quote or summary]"
User: [@username or Anonymous]
Reach: [Followers / Upvotes / Visibility estimate]

Sentiment Analysis: [Complaint / Scam accusation / Technical issue]

Recommended Actions:
1. [Community Manager to respond professionally]
2. [Owner to review and approve response]
3. [Pause content until resolved]

[Link to Mention] | [Screenshot Attached]
```

---

### TASK 6: Performance Analytics (Priority: LOW)

**Objective:** Track content performance and optimize strategy

**Actions:**
```bash
1. For posts published 24h ago:
   - Fetch engagement metrics (likes, comments, shares, saves)
   - Fetch link clicks (if UTM tracking available)
   - Calculate engagement rate

2. Update performance log:
   file_management: append to /agent_squad/marketer/performance_log.yml

3. Rolling analysis (last 30 days):
   - Top 5 performing posts (by engagement rate)
   - Worst 5 performing posts
   - Avg engagement by content type
   - Avg engagement by platform
   - Best posting times (hour of day)

4. Generate insights:
   - "Educational posts average 4.2% engagement vs 2.8% for product posts"
   - "Instagram Stories get 2x CTR compared to feed posts"
   - "Posts published 7-9 AM EST perform 35% better"
```

**Weekly Report (Every Monday 10 AM):**
```
Marketer Weekly Analytics

Period: [Last 7 Days]
Posts Published: [X]
Platforms: IG [X] | X [X] | LinkedIn [X]

Top Performer:
- [Post type]: [Engagement %] on [Platform]
- Topic: [Brief description]

Engagement Averages:
├── Instagram: [X%] (Target: 3%)
├── X: [X%] (Target: 2%)
└── LinkedIn: [X%] (Target: 1.5%)

Insights:
- [Data-driven observation #1]
- [Data-driven observation #2]

Recommendations:
- [Actionable adjustment to content strategy]

[View Full Report]
```

**Insights Application:**
- Update content generation weights based on performance data
- Adjust posting times to optimal windows
- Prioritize content types that drive engagement
- Flag underperforming platforms for strategy review

---

### TASK 7: Content Calendar Adherence (Priority: MEDIUM)

**Objective:** Ensure weekly content plan is being executed on schedule

**Actions:**
```bash
1. Load week's content plan
   file_management: read /agent_squad/marketer/content_calendar.yml

2. Check today's planned content vs actual:
   Planned for today: [X posts]
   Published today:   [X posts]
   Awaiting approval: [X posts]

3. Status evaluation:
   ✅ On track (published >= planned)
   ⚠️ Behind (published < planned AND drafts awaiting approval)
   🚨 Blocked (published < planned AND no drafts in queue)

4. If BLOCKED:
   - Generate missing content immediately (priority boost)
   - If persistent blockers → Escalate to owner
```

**Weekly Plan Check (Every Monday):**
```bash
# Generate next week's content plan
1. Review last week's performance (TASK 6 data)
2. Check Innovator calendar (any bot launches expected?)
3. Draft 7-day content plan with mix:
   - 60% educational
   - 30% product showcase
   - 10% community engagement

4. Submit plan to owner for approval:
   telegram_hitl: {
     "message_type": "weekly_content_plan",
     "plan": "[Markdown plan]",
     "approval_options": ["Approve", "Edit", "See Last Week's Data"]
   }
```

---

## Heartbeat State Persistence

**Memory Variables to Track:**
```yaml
heartbeat_state:
  last_trend_scan: "2026-03-20T14:30:00Z"
  last_innovator_sync: "2026-03-20T14:30:00Z"
  last_content_generated: "2026-03-20T13:15:00Z"
  last_queue_check: "2026-03-20T14:30:00Z"
  last_brand_mention_scan: "2026-03-20T14:00:00Z"
  last_analytics_update: "2026-03-20T14:30:00Z"

  known_bots:
    - "EMA50_200_RSI_v1"
    - "BreakoutGold_v2"

  posts_published_today: 2
  drafts_awaiting_approval: 3

  content_calendar_status: "on_track"

  performance_trends:
    avg_engagement_7d: 3.8
    avg_engagement_30d: 3.5
    best_time_to_post: "7-9 AM EST"
    best_performing_type: "educational"
```

**Persistence:** Save state after each heartbeat to `/agent_squad/marketer/heartbeat_state.yml`

---

## Error Handling During Heartbeat

### Non-Critical Errors (Continue Operation)
- Search API temporarily unavailable → Skip trend monitoring this cycle
- Image generation fails → Retry next heartbeat
- Analytics fetch timeout → Use cached data

### Critical Errors (Escalate Immediately)
- Cannot access approval queue → HITL system broken
- Negative brand mention detected → Pause all content
- Publishing repeatedly fails (3+ times) → Manual intervention needed
- Owner approval system unresponsive >48h → Escalate

**Escalation Protocol:**
1. Log full error details
2. Pause content generation (not monitoring)
3. Send Telegram alert to owner
4. Continue monitoring tasks only
5. Wait for human intervention

---

## Optimization & Fine-Tuning

**Review this heartbeat configuration monthly:**
- Is 30-minute interval optimal for content? (Maybe 1-hour for non-urgent tasks?)
- Are we generating too much content for owner to approve? (Adjust threshold)
- Should we auto-publish certain content types? (NO — always require approval)
- Performance analytics frequency: Daily vs weekly?

**Continuous Improvement:**
- Track avg time from draft → approval (optimize for <12h)
- Measure approval rate (target >80%, minimize owner edits)
- Monitor content generation quality (reduce regeneration requests)
- A/B test caption styles and visual prompts

---

*Heartbeat keeps The Marketer generating, monitoring, and optimizing. This is proactive brand building on autopilot.*
