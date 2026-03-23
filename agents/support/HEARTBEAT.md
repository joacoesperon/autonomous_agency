# 💓 Community Manager Heartbeat — 24/7 Support Pulse

This file defines the autonomous, scheduled tasks that The Community Manager executes every 30 minutes without human prompting. These tasks ensure 24/7 support coverage and proactive community engagement.

---

## Heartbeat Cycle (Every 30 Minutes)

### TASK 1: Inbox Monitoring (Priority: CRITICAL)

**Objective:** Ensure no customer message goes unanswered for >30 minutes (business hours) or >2 hours (off-hours)

**Actions:**
```bash
1. Check all communication channels for new messages
   messaging-gateway: check_inbox({
     platforms: ["instagram_dm", "x_dm", "linkedin_msg", "whop_support"],
     status: "unread",
     time_range: "last_30_minutes"
   })

2. For each new message:
   a. Extract: sender, platform, message text, timestamp
   b. Classify urgency: [Critical / High / Medium / Low]
   c. Classify category: [Pricing / Technical / Refund / General]
   d. Run sentiment analysis: [Score 1-10]

3. Prioritize response queue:
   ├── Critical urgency (refund, angry, red flags) → Respond within 5 min
   ├── High urgency (technical issues) → Respond within 30 min
   ├── Medium urgency (pricing, general) → Respond within 2 hours
   └── Low urgency (compliments, general) → Respond within 12 hours
```

**Response Flow:**
```
For each message:
├── Search knowledge base for answer
│   ├── Confidence >80%? Draft response immediately
│   ├── Confidence 50-80%? Draft tentative response + caveat
│   └── Confidence <50%? Escalate or ask clarifying questions
│
├── Check for red flag keywords
│   └── If detected → Skip auto-response, ESCALATE immediately
│
├── Send response
│   └── Log conversation to history
│
└── If response doesn't resolve:
    └── Prepare for multi-turn conversation (max 3 turns before escalate)
```

**Performance Metrics:**
```
Track per heartbeat:
- Messages received: [X]
- Messages responded: [X]
- Avg response time: [Xmin]
- Escalations triggered: [X]
- KB confidence avg: [XX%]
```

---

### TASK 2: Comment Engagement (Priority: HIGH)

**Objective:** Engage with ALL comments on published posts within 2 hours

**Actions:**
```bash
1. Fetch recent post comments
   messaging-gateway: get_comments({
     platforms: ["instagram", "x", "linkedin"],
     posts: "published_last_7_days",
     status: "unanswered"
   })

2. For each comment:
   a. Classify type: [Question / Compliment / Objection / Negative / Spam]
   b. Prioritize: Questions and Objections first, Compliments second
   c. Generate response using appropriate template

3. Response strategy:
   ├── Questions → Answer from KB or direct to DMs
   ├── Compliments → Brief thank you + brand reinforcement
   ├── Objections → Professional, data-backed response (1-2 replies max)
   ├── Negative → Empathetic acknowledgment + escalate if heated
   └── Spam → No response, flag for owner to hide/delete
```

**Engagement Rules:**
```
DO:
├── Respond to every genuine question
├── Thank every positive comment (even brief)
├── Address objections professionally with data
├── Offer to help via DMs for complex issues
└── Use brand voice (friendly, transparent, professional)

DON'T:
├── Argue with critics (2-reply limit)
├── Delete or hide negative comments (flag for owner)
├── Make promises beyond KB scope
├── Engage with obvious trolls (flag and ignore)
└── Respond to spam (flag for owner)
```

**Escalation Triggers:**
```
ESCALATE if comment:
├── Accuses Jess Trading of scam/fraud
├── Contains legal threats
├── Receives multiple negative replies from others (viral risk)
├── Directly attacks owner personally
└── After 2 professional replies, user still hostile
```

---

### TASK 3: Sentiment Analysis (Priority: MEDIUM)

**Objective:** Monitor overall community mood and flag concerning patterns

**Actions:**
```bash
1. Analyze all interactions in last 24 hours:
   - DMs: sentiment score per conversation
   - Comments: sentiment score per comment
   - Overall tone: Positive / Neutral / Negative / Critical

2. Calculate aggregate sentiment:
   ├── % Positive interactions (score 7-10)
   ├── % Neutral interactions (score 4-6)
   ├── % Negative interactions (score 1-3)
   └── Trend: Improving / Stable / Declining

3. Flag anomalies:
   ├── Spike in negative sentiment (>20% in 24h) → Alert owner
   ├── Recurring complaint pattern (>3 similar issues) → Alert owner + Innovator
   ├── Sudden increase in refund requests → Alert Operator + owner
   └── Positive spike (great for testimonials) → Alert Marketer
```

**Sentiment Report (Daily at 9 AM EST):**
```
Community Manager Daily Sentiment

Period: Last 24 Hours
Total Interactions: [X]

Sentiment Breakdown:
├── Positive: [XX%] (Target: >60%)
├── Neutral:  [XX%]
└── Negative: [XX%] (Target: <15%)

Trend: [↑ Improving / → Stable / ↓ Declining]

Top Positive Themes:
- [Theme 1]
- [Theme 2]

Top Negative Themes:
- [Theme 1]
- [Theme 2]

Noteworthy:
- [Any testimonial-worthy positive feedback]
- [Any concerning negative pattern]

Action Items:
- [KB article to create/update]
- [Issue to escalate]
- [No action needed]
```

**Delivery:** Send to owner (daily), Marketer (weekly summary)

---

### TASK 4: Knowledge Base Maintenance (Priority: LOW)

**Objective:** Keep KB up-to-date and identify content gaps

**Actions:**
```bash
1. Review KB search performance:
   - Questions with low confidence answers (<50%)
   - Questions with NO KB match
   - Frequently asked questions (FAQs)

2. Identify KB gaps:
   - If same question asked >3 times → Suggest new FAQ entry
   - If technical issue has no KB article → Flag for documentation
   - If bot manual missing info users ask about → Note for Innovator

3. Auto-generate FAQ suggestions:
   file_management: append to /agent_squad/support/faq_suggestions.md
```

**Example Gap Detection:**
```
Gap Identified: "VPS setup for MT5"
Frequency: 8 times in last 7 days
Current KB Coverage: None
Suggested Article:
---
Title: "How to Set Up a VPS for 24/7 Bot Operation"
Outline:
- Why VPS? (bots run continuously)
- Free VPS options (broker-provided)
- Paid VPS recommendations (Vultr, DigitalOcean)
- Setup walkthrough (Windows Server MT5 installation)
- Cost estimate
---
Priority: Medium
```

**Monthly KB Review (First Monday):**
```
KB Effectiveness Report

Period: Last 30 Days
Total Support Inquiries: [X]

KB Resolution Rate:
├── Answered directly from KB: [XX%] (Target: >70%)
├── Required escalation: [XX%]
└── No KB match: [XX%]

Suggested Improvements:
1. [New FAQ entry needed]
2. [Existing article to clarify]
3. [Bot manual gap to fill]

Most Searched KB Topics:
1. [Topic] - [X searches]
2. [Topic] - [X searches]
...
```

---

### TASK 5: Escalation Queue Management (Priority: HIGH)

**Objective:** Track escalated issues and ensure owner follow-up

**Actions:**
```bash
1. Review escalation queue status
   file_management: read /shared/escalation_queue.yml

2. For each escalated issue:
   ├── Status: [Awaiting owner / In progress / Resolved]
   ├── Time since escalation: [Hours]
   ├── Urgency: [Critical / High / Medium]

3. Reminder logic:
   ├── Critical + >2h no response → Second reminder to owner
   ├── High + >24h no response → Gentle reminder to owner
   ├── Medium + >48h no response → Archive to backlog
   └── Resolved → Remove from queue, log resolution

4. If user follows up on escalated issue:
   → "Your case has been escalated to our team. They'll reach out within [timeframe]. Thanks for your patience."
```

**Escalation Tracking:**
```yaml
escalation_queue:
  - id: "esc_20260320_001"
    type: "refund_request"
    user: "@username"
    platform: "whop"
    escalated_at: "2026-03-20T14:00:00Z"
    urgency: "critical"
    status: "awaiting_owner"
    owner_notified: true
    reminder_sent: false
    expected_resolution: "24h"

  - id: "esc_20260320_002"
    type: "technical_advanced"
    user: "@user2"
    platform: "instagram_dm"
    escalated_at: "2026-03-20T10:00:00Z"
    urgency: "high"
    status: "in_progress"
    owner_notified: true
    reminder_sent: true
    expected_resolution: "48h"
```

---

### TASK 6: Testimonial Detection (Priority: LOW)

**Objective:** Identify positive user feedback for Marketer to leverage

**Actions:**
```bash
1. Scan recent interactions for testimonial-worthy feedback:
   - Sentiment score >8/10
   - User shares positive results (with specifics)
   - User praises specific aspect of product/service
   - Unsolicited compliments

2. For potential testimonials:
   a. Screenshot/save the message
   b. Note: user, platform, date, exact quote
   c. Flag for Marketer review

3. Send to Marketer queue:
   file_management: append to /agent_squad/marketer/testimonial_candidates.yml
```

**Testimonial Candidate Format:**
```yaml
testimonial_candidates:
  - id: "test_20260320_001"
    user: "@happytrader"
    platform: "instagram_dm"
    date: "2026-03-20"
    sentiment_score: 9
    quote: "Setup was super easy and the bot's been running flawlessly for a week now. Love the transparency with the backtest reports."
    context: "Unsolicited follow-up after purchase"
    permission_requested: false
    approved_for_use: false
```

**Next Step:** Marketer evaluates and requests permission from user if suitable for marketing

---

### TASK 7: Platform Health Check (Priority: MEDIUM)

**Objective:** Ensure all communication channels are operational

**Actions:**
```bash
1. Test connectivity to each platform:
   ├── Instagram API: messaging-gateway: ping("instagram")
   ├── X API: messaging-gateway: ping("x")
   ├── LinkedIn API: messaging-gateway: ping("linkedin")
   └── Whop API: messaging-gateway: ping("whop")

2. For each platform:
   ├── Status: [Operational / Degraded / Down]
   ├── Last successful message: [Timestamp]
   ├── Error rate: [%]

3. If any platform DOWN or Degraded:
   ├── Log error details
   ├── Retry connection once
   ├── If still failing → Escalate to owner
   ├── Notify owner: "⚠️ [Platform] API connectivity issue"
```

**Fallback Protocol:**
```
If primary platform fails:
├── Instagram down → Direct users to X or email
├── X down → Direct users to Instagram or email
├── Whop down → Use Telegram for critical support
└── All platforms down → Escalate immediately, use emergency contact form
```

---

## Heartbeat State Persistence

**Memory Variables to Track:**
```yaml
heartbeat_state:
  last_inbox_check: "2026-03-20T14:30:00Z"
  last_comment_scan: "2026-03-20T14:30:00Z"
  last_sentiment_analysis: "2026-03-20T14:00:00Z"
  last_kb_review: "2026-03-18T10:00:00Z"
  last_escalation_check: "2026-03-20T14:30:00Z"
  last_testimonial_scan: "2026-03-20T14:00:00Z"
  last_platform_health: "2026-03-20T14:30:00Z"

  messages_today: 47
  comments_today: 23
  escalations_today: 2

  avg_response_time_today: "18min"
  kb_resolution_rate_today: 73.5

  sentiment_trend: "stable"
  positive_pct_today: 68
  negative_pct_today: 12

  platform_status:
    instagram: "operational"
    x: "operational"
    linkedin: "operational"
    whop: "operational"
```

**Persistence:** Save state after each heartbeat to `/agent_squad/support/heartbeat_state.yml`

---

## Error Handling During Heartbeat

### Non-Critical Errors (Continue Operation)
- Single platform API timeout → Skip that platform this cycle, retry next
- KB search slow (>5 sec) → Use cached responses, flag for optimization
- Sentiment analysis fails → Skip analysis, retry next cycle
- Testimonial detection error → Non-essential, log and continue

### Critical Errors (Escalate Immediately)
- ALL platforms unresponsive → Cannot provide support
- Knowledge base completely inaccessible → Cannot answer questions
- Escalation system broken → Cannot alert owner to critical issues
- Persistent message delivery failures (3+ heartbeats)

**Escalation Protocol:**
1. Log full error context with stack trace
2. Send Telegram alert to owner: "🚨 COMMUNITY MANAGER CRITICAL ERROR"
3. Pause non-essential tasks (testimonials, analytics)
4. Continue monitoring for critical messages (refunds, angry users)
5. Wait for human intervention

---

## Edge Cases & Exceptions

### After-Hours Coverage
```
Business Hours: 9 AM - 11 PM EST
Off-Hours: 11 PM - 9 AM EST

During off-hours:
├── Response time target: <2 hours (vs <30 min during business hours)
├── Critical issues (refund, angry) → Still escalate immediately
├── Non-urgent → Queue for business hours response
└── Auto-response: "Thanks for reaching out. We'll respond within 2 hours. For urgent issues, include 'URGENT' in your message."
```

### High-Volume Scenarios
```
If messages received >50 in single heartbeat:
├── Possible scenarios:
│   ├── Product launch spike (normal)
│   ├── Viral post or mention (good or bad)
│   ├── Service outage (critical)
│   └── Bot spam attack (abuse)
│
├── Actions:
│   ├── Triage by urgency (critical first)
│   ├── Alert owner: "High message volume detected: [X messages]"
│   ├── Sample sentiment to gauge if crisis or success
│   └── If spam detected → Enable stricter filtering
```

### Abusive Users
```
If user sends:
├── >10 messages in 1 hour → Flag as potential spam or crisis
├── Profanity or threats → Escalate immediately
├── Repeated same question after clear answer → Potential bot, flag for owner
└── Multiple accounts from same person → Report to platform, notify owner
```

---

## Optimization & Fine-Tuning

**Review this heartbeat configuration monthly:**
- Is 30-minute interval sufficient for support? (Consider 15 min during business hours)
- KB resolution rate: Target >70%, adjust if consistently below
- Escalation rate: Target <20%, if higher review KB coverage
- Response time: Consistently under target? Can we improve further?

**Continuous Improvement:**
- Track which KB articles get highest usage → Prioritize keeping those updated
- Monitor escalation reasons → Create KB articles to reduce future escalations
- Analyze sentiment trends → Proactively improve common pain points
- Measure user satisfaction → Qualitative feedback through follow-ups

---

*Heartbeat keeps The Community Manager responsive and proactive. Every message matters. Every user feels heard. This is 24/7 support done right.*
