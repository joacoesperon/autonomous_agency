# 💓 Marketer Heartbeat — High-Volume Content Engine

This file defines the autonomous, scheduled tasks that The Marketer executes every 30 minutes without human prompting. These tasks ensure continuous, high-volume content pipeline operation.

**Philosophy:** Generate abundantly → Approve selectively → Publish approved

---

## Heartbeat Cycle (Every 30 Minutes)

### TASK 1: Daily Content Generation (Priority: CRITICAL)

**Objective:** Maintain constant content flow using OPTIMIZED pipeline (1 LLM call).

**Target:** 10+ drafts in approval queue at all times

**Actions:**
```bash
1. Check today's content status:
   - Video + derivatives generated today? (YES/NO)
   - Total pieces pending approval: [count]

2. If daily requirement missing:
   → IMMEDIATELY generate using NEW optimized workflow
   → Priority: Use content_script_generator FIRST

3. If all daily content done AND approval queue <10 items:
   → Generate additional content for tomorrow
   → Use next day's content type in rotation

4. Content type selection (rotate daily):
   Day % 7:
   0 (Monday):    Educational (40%)
   1 (Tuesday):   Social Proof (30%)
   2 (Wednesday): Product (20%)
   3 (Thursday):  Community (10%)
   4 (Friday):    Educational (40%)
   5 (Saturday):  Social Proof (30%)
   6 (Sunday):    Product (20% or rest)
```

**NEW OPTIMIZED Generation Process (66% fewer LLM calls):**

```python
# ========================================================================
# STEP 1: Generate Complete Content Package (1 LLM call) ⭐
# ========================================================================

# 1.1 Select topic (optional search)
topic = tavily_search("algorithmic trading news") OR manual_topic

# 1.2 Generate ALL content in ONE call
Use: content_script_generator

# Educational example
package = content_script_generator.generate_educational_package(
    topic="Why emotional trading fails during volatility",
    duration=30
)

# Product example (when Innovator releases new bot)
package = content_script_generator.generate_product_package(
    strategy_name="EMA50_200_RSI_Scalper",
    symbol="EURUSD",
    metrics={"pf": 1.87, "sharpe": 2.34, "dd": 12.5, "win_rate": 68.3},
    backtest_years=10,
    duration=45
)

# package now contains:
# {
#   "video_script": "...",
#   "carousel_points": ["point1", "point2", ..., "point6"],
#   "tweet_points": ["hook", "value1", ..., "cta"]
# }

# ========================================================================
# STEP 2: Generate Video from Script (D-ID API call)
# ========================================================================

video_result = video_generation.execute(
    script=package["video_script"],
    duration=package["estimated_duration"]
)

# Output: video.mp4 (9:16 vertical)

# ========================================================================
# STEP 3: Generate Carousel Images from Points (6 Replicate calls)
# ========================================================================

carousel_images = []
for i, point in enumerate(package["carousel_points"], 1):
    # Generate prompt for this slide
    prompt = dynamic_prompt_generator.execute(
        topic=point,
        style="minimal",
        platform="instagram_post"
    )

    # Generate image
    image = image_generation.execute(
        prompt=prompt["prompt"],
        aspect_ratio="1:1"
    )

    carousel_images.append(image["local_path"])

# Output: 6 images (1080x1080px)

# ========================================================================
# STEP 4: Format Tweets from Points (NO LLM call, just formatting)
# ========================================================================

tweets = []
for point in package["tweet_points"]:
    # Format to ≤280 chars
    tweet = ensure_max_length(point, 280)
    tweets.append(tweet)

# Output: 5 tweets

# ========================================================================
# STEP 5: Send to HITL Approval (Telegram)
# ========================================================================

telegram_hitl.execute({
    "title": f"Daily Content - {content_type} - {date}",
    "items": [
        {
            "type": "video",
            "platforms": ["instagram_reel", "tiktok", "youtube_shorts", "facebook_reel"],
            "media": video_result["local_path"],
            "caption": generate_caption(package["video_script"])
        },
        {
            "type": "carousel",
            "platforms": ["instagram"],
            "media": carousel_images,  # List of 6 images
            "caption": "See slides for key points"
        },
        {
            "type": "thread",
            "platforms": ["twitter"],
            "tweets": tweets  # List of 5 tweets
        }
    ],
    "priority": "normal",
    "metadata": {
        "llm_provider": package["llm_provider"],
        "llm_calls": 2,  # content_script_generator + dynamic_prompt_generator
        "cost_estimate": "$0.16"
    }
})
```

**Performance Metrics:**
```
OLD WORKFLOW:
- LLM calls per cycle: 3 (video_to_carousel + video_to_tweet_thread + prompts)
- Cost per cycle: ~$0.25
- Coherence: Medium (3 separate calls = 3 different contexts)

NEW WORKFLOW:
- LLM calls per cycle: 2 (content_script_generator + dynamic_prompt_generator)
- Cost per cycle: ~$0.16
- Coherence: High (1 unified generation = consistent voice)
- Time saved: ~30% faster
```

**Stop Conditions:**
```
DO NOT generate if:
- >20 drafts awaiting approval (owner backlog)
- Critical system error detected
- Owner flagged "pause content" in settings
- LLM provider unavailable (check shared/brand_config.yml for fallback)

KEEP generating if:
- Approval queue <20 items
- System operational
- No critical alerts
```

**Success Metrics:**
- Daily: 1 video + 1 thread + 1 carousel minimum (12 total pieces)
- Weekly: 40-60 total pieces created
- Approval queue: 10-20 items pending at all times
- LLM cost: <$5/month

---

### TASK 2: Approval Queue & Publishing (Priority: HIGH)

**Objective:** Manage HITL workflow and execute approved publications

**Actions:**
```bash
1. Check approval queue status:
   file_management: read shared/approval_queue.yml

2. Categorize by status:
   ├── Approved (ready to publish) → Execute immediately
   ├── Awaiting Approval (<24h) → Normal, continue
   ├── Awaiting Approval (24-48h) → Send gentle reminder
   ├── Awaiting Approval (>48h) → Archive to expired/, clear from queue
   └── Denied → Move to denied/, analyze feedback for improvement

3. Publish Approved Content:
   For each item with status="approved":

   A. Story:
      social_media_publisher.execute(
          platforms=["instagram"],
          caption=caption,
          media_paths=[story_image],
          content_type="story"
      )

   B. Video (Reel cross-platform):
      social_media_publisher.publish_reel_cross_platform(
          video_path=video_file,
          caption=caption
      )
      # Auto-publishes to: Instagram, TikTok, YouTube Shorts, Facebook

   C. Thread:
      social_media_publisher.execute(
          platforms=["twitter"],
          caption=tweets_list,  # List of 5 tweets
          content_type="thread"
      )

   D. Carousel:
      social_media_publisher.execute(
          platforms=["instagram"],
          caption=caption,
          media_paths=carousel_images,
          content_type="carousel"
      )

4. Log Results:
   - Update published_log.yml with post IDs
   - Update heartbeat_state.yml
   - Track: posts_published_today += [count]

5. Error Handling:
   If publishing fails:
   - Retry once (30-second delay)
   - If still fails → Move to failed_posts/
   - Notify owner: "⚠️ Publishing failed for [ID]: [error]"
   - Continue with other posts (don't let one failure block all)
```

**Reminder Protocol:**
```
For approvals pending 24-48h:
telegram message:
"📌 Content Approval Reminder

You have [X] posts awaiting approval:
1. [Type] for [Platforms] - Created [hours] ago
2. [Type] for [Platforms] - Created [hours] ago
...

[Review Queue]

Note: Content older than 48h will be auto-archived."
```

---

### TASK 3: Trend Monitoring (Priority: MEDIUM)

**Objective:** Stay current with market conversations for content ideas

**Frequency:** Every 2 hours (not every 30min cycle)

**Actions:**
```bash
1. Search for trending topics:
   tavily_search: "algorithmic trading news last 6 hours"
   tavily_search: "crypto bot trading 2026"
   tavily_search: "forex automation"

2. Filter results for relevance:
   ✅ Retail trader pain points
   ✅ Automation/algo trading discussions
   ✅ Market volatility events
   ✅ Educational opportunities
   ❌ Pure price speculation
   ❌ Hype/scam content

3. Save trend ideas:
   If trend score >=30 (relevance + timeliness + educational value):
   → Save to trends_queue.yml for future content generation
   → Flag if URGENT (breaking news, major market move)

4. Don't interrupt content generation for trends:
   Trends inform topics, but don't block the pipeline
```

---

### TASK 4: Innovator Sync - New Bot Detection (Priority: LOW)

**Objective:** Detect new product launches (infrequent, ~1/month)

**Frequency:** Every 6 hours (not every 30min)

**Actions:**
```bash
1. Check for new strategies:
   file_management: read shared/product_inventory.yml

2. Compare against known_bots in heartbeat_state:
   known_bots: ["EMA50_200_RSI_v1", "BreakoutGold_v2"]
   current_bots: [read from inventory]

3. If NEW bot detected:
   a. Parse bot data: name, symbol, metrics
   b. PRIORITY BOOST → Jump to front of content queue
   c. Generate product launch campaign:
      - Product video (60s)
      - Thread (8 tweets with metrics)
      - Carousel (8 slides)
      - Story ("NEW BOT LAUNCH" design)
   d. Send to HITL with HIGH PRIORITY flag
   e. Update known_bots list

4. If NO new bots:
   → Continue normal operations
   → This is expected (only ~1 bot/month)
```

**Why LOW priority:**
- New bots are rare (~1 per month)
- Not time-sensitive (can wait 6 hours)
- Doesn't block daily content generation
- When detected, auto-boosts to HIGH priority

---

### TASK 5: Performance Tracking (Priority: LOW)

**Objective:** Track engagement metrics and optimize strategy

**Frequency:** Once per day (morning, first heartbeat after 8 AM EST)

**Actions:**
```bash
1. For posts published 24-48h ago:
   - Fetch engagement metrics (likes, comments, shares, saves)
   - Calculate engagement rate
   - Track link clicks (if UTM available)

2. Update performance_log.yml:
   published_log.yml → add engagement data

3. Identify top performers (last 7 days):
   - Top 3 posts by engagement
   - Worst 3 posts by engagement
   - Avg engagement by content type
   - Avg engagement by platform

4. Generate insights:
   "Educational videos average 4.2% engagement vs 2.8% for product"
   "TikTok performing 2x better than Instagram Reels"
   "Carousel posts underperforming - review format"

5. Apply insights:
   - Adjust content type weights if needed
   - Flag underperforming formats
   - Double down on winning content types
```

---

### TASK 6: Brand Mention Monitoring (Priority: MEDIUM)

**Objective:** Detect brand mentions and potential PR issues early

**Frequency:** Every 4 hours

**Actions:**
```bash
1. Search for brand mentions:
   tavily_search: "Jess Trading" last 4 hours
   tavily_search: "Jess Trading review"
   tavily_search: "Jess Trading scam" (negative PR detection)

2. Categorize mentions:
   ├── Positive → Flag for Community Manager (potential testimonial)
   ├── Neutral → Monitor
   ├── Negative → ESCALATE IMMEDIATELY
   └── No mentions → Normal operation

3. If NEGATIVE mention detected:
   🚨 EMERGENCY PROTOCOL:
   a. Screenshot/save the mention
   b. PAUSE all scheduled content
   c. Escalate to owner with full context:
      "🚨 NEGATIVE BRAND MENTION DETECTED

       Platform: [X / Reddit / etc]
       Content: '[exact quote]'
       Reach: [followers/visibility]

       Sentiment: [complaint/scam accusation/technical issue]

       ACTIONS TAKEN:
       - All content paused
       - Awaiting your strategy

       [Link] | [Screenshot]"
   d. Wait for owner strategy before resuming
```

---

### TASK 7: Content Calendar Adherence (Priority: MEDIUM)

**Objective:** Ensure weekly content mix stays balanced

**Frequency:** Daily check

**Actions:**
```bash
1. Calculate this week's content mix:
   total_posts_this_week = [count]
   educational_count = [X] → [X/total * 100]%
   social_proof_count = [Y] → [Y/total * 100]%
   product_count = [Z] → [Z/total * 100]%
   community_count = [W] → [W/total * 100]%

2. Compare to target (40/30/20/10):
   If deviation >15%:
   → Adjust tomorrow's content type to rebalance
   → Example: If educational is 25% (should be 40%), prioritize educational next

3. Weekly reset (Mondays):
   - Clear weekly counters
   - Generate weekly content plan
   - Submit plan to owner for awareness (not approval):
     "📅 Week of [Date] Content Plan

     Mon: Educational - [topic idea]
     Tue: Social Proof - [testimonial/case study]
     Wed: Product - [bot highlight]
     Thu: Community - [engagement post]
     Fri: Educational - [market analysis]
     Sat: Social Proof - [user result]
     Sun: Product OR rest

     Last week performance:
     - [X] posts published
     - Avg engagement: [Y]%
     - Top performer: [post type]"
```

---

## Heartbeat State Persistence

**Memory Variables to Track:**
```yaml
heartbeat_state:
  last_content_generated: "2026-03-25T14:30:00Z"
  last_queue_check: "2026-03-25T14:30:00Z"
  last_trend_scan: "2026-03-25T12:00:00Z"
  last_innovator_sync: "2026-03-25T08:00:00Z"
  last_analytics_update: "2026-03-25T08:00:00Z"
  last_brand_mention_scan: "2026-03-25T10:00:00Z"

  known_bots:
    - "EMA50_200_RSI_v1"
    - "BreakoutGold_v2"

  content_generated_today:
    story: true
    video: true
    derivatives: true
    total_pieces: 12

  posts_published_today: 8
  drafts_awaiting_approval: 15

  weekly_content_mix:
    educational: 12  # 40%
    social_proof: 9  # 30%
    product: 6       # 20%
    community: 3     # 10%

  content_calendar_status: "balanced"  # or "rebalance_needed"
```

**Persistence:** Save after each heartbeat to `/agents/marketer/heartbeat_state.yml`

---

## Error Handling During Heartbeat

### Non-Critical Errors (Continue Operation)
- Search API temporarily unavailable → Use cached trends
- Image generation fails → Retry next heartbeat, log error
- Analytics fetch timeout → Use cached data

### Critical Errors (Pause & Escalate)
- Cannot access approval queue → HITL system broken
- Negative brand mention detected → Pause all content
- Publishing repeatedly fails (3+ consecutive) → Manual intervention needed
- Owner approval system unresponsive >72h → Escalate

**Escalation Protocol:**
1. Log full error details to shared/logs/marketer_errors.log
2. Pause NEW content generation (not publishing approved content)
3. Send Telegram alert to owner
4. Continue monitoring tasks only
5. Wait for human intervention

---

## Priority Summary

```
┌─────────────────────────────────────────────┐
│ CRITICAL: Content Generation                │
│ Generate daily: story + video + derivatives │
│ Target: 10+ drafts in queue always          │
└─────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────┐
│ HIGH: Approval & Publishing                 │
│ Execute approved content immediately        │
│ Manage queue, send reminders               │
└─────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────┐
│ MEDIUM: Trends, Brand Mentions, Calendar    │
│ Inform content strategy                     │
│ Detect PR issues early                      │
└─────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────┐
│ LOW: New Bots, Performance Analytics        │
│ ~1 bot/month, daily metrics tracking        │
│ Important but not urgent                    │
└─────────────────────────────────────────────┘
```

---

*Heartbeat keeps The Marketer generating, publishing, and optimizing. This is proactive content creation on autopilot.*

**Generate → Approve → Publish → Repeat**

---
