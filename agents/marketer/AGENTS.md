# 📈 The Marketer — Technical Documentation (For Humans)

**Last Updated:** 2026-03-25
**Status:** Operational
**OpenClaw Agent:** `marketer`

---

## Overview

The Marketer is an autonomous content generation agent that creates high-volume, multi-platform content for Jess Trading. It generates videos, images, threads, and carousels daily using AI, then sends everything to the owner for approval before publishing.

**Philosophy:** Quantity → Approval → Quality

---

## What It Does

### Daily Workflow
Every day, the Marketer automatically:

1. **Generates 1 Instagram Story** (image, 9:16 format)
2. **Generates 1 Video** (15-60 seconds, vertical)
   - Uses AI avatar with consistent character
   - Publishes to: Instagram Reels, TikTok, YouTube Shorts, Facebook
3. **Derives content from that video:**
   - 5-tweet X/Twitter thread
   - 6-8 slide Instagram carousel
4. **Sends everything to you for approval** via Telegram
5. **Publishes approved content** to all platforms

**Result:** ~12 content pieces per day from one core video.

---

## Content Mix (40/30/20/10 Rule)

- **40% Educational:** Trading psychology, algo trading concepts, how-tos
- **30% Social Proof:** Testimonials, user results, case studies
- **20% Product:** Bot launches, feature showcases, backtest breakdowns
- **10% Community:** Behind-the-scenes, Q&A, engagement posts

The agent automatically rotates through these types daily.

---

## Platforms

✅ **Active:**
- Instagram (stories, posts, carousels, reels)
- X/Twitter (tweets, threads)
- TikTok (short videos)
- YouTube Shorts (short videos)
- Facebook (posts, reels)

❌ **Removed:**
- LinkedIn (no longer part of strategy)

---

## How It Works Technically

### 1. Content Generation
The agent uses 9 custom Python skills:

**New Skills (Video-Based):**
- `video_generation` → Creates AI videos with consistent avatar
- `video_to_tweet_thread` → Converts video script to 5-tweet thread
- `video_to_carousel` → Converts video to Instagram carousel (5-8 slides)
- `dynamic_prompt_generator` → Creates unique image prompts (no templates)

**Existing Skills:**
- `image_generation` → Generates brand-compliant images
- `telegram_hitl` → Sends content for owner approval
- `content_parser` → Extracts metrics from EA reports
- `tavily_search` → Searches web for trends
- `social_media_publisher` → Publishes to platforms (after approval)

### 2. Approval Workflow (HITL)
All content goes through Human-in-the-Loop approval:

```
Generate Content → Bundle Everything → Send to Telegram
                                               ↓
                            You Review (see preview + captions)
                                               ↓
                           Click: [Approve] or [Deny] or [Edit]
                                               ↓
                          If Approved → Publish to All Platforms
```

Nothing publishes without your explicit approval.

### 3. Heartbeat (Autonomous Tasks)
Every 30 minutes, the agent:
- **CRITICAL:** Generates daily content if not done yet
- **HIGH:** Publishes approved content immediately
- **MEDIUM:** Monitors trends, checks for brand mentions
- **LOW:** Checks for new bot launches (~1/month)

---

## Files Structure

```
agents/marketer/
├── IDENTITY.md        ← Agent instructions (read by OpenClaw)
├── HEARTBEAT.md       ← Autonomous 30-min tasks (read by OpenClaw)
├── AGENTS.md          ← This file (human documentation)
└── content/
    ├── drafts/        ← Generated content awaiting approval
    ├── generated/     ← Videos, images, carousels
    ├── expired/       ← Approvals older than 48h
    └── published_log.yml ← History of published content
```

---

## Configuration

### API Keys Required
Set these in `.env`:

```bash
# LLM (content generation)
GEMINI_API_KEY=your_key

# Video Generation
D_ID_API_KEY=your_key

# Image Generation
REPLICATE_API_TOKEN=your_token

# Search (trends)
TAVILY_API_KEY=your_key

# HITL Approval
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_OWNER_CHAT_ID=your_chat_id

# Social Media Publishing (optional, for auto-publish after approval)
INSTAGRAM_ACCESS_TOKEN=your_token
X_BEARER_TOKEN=your_token
TIKTOK_ACCESS_TOKEN=your_token
YOUTUBE_API_KEY=your_key
FACEBOOK_ACCESS_TOKEN=your_token
```

---

## Running the Agent

### Start Marketer Agent:
```bash
cd autonomus_agency/
openclaw run marketer
```

The agent will:
1. Start heartbeat (every 30 minutes)
2. Generate first batch of content
3. Send to Telegram for your approval
4. Wait for your response
5. Publish approved content
6. Repeat cycle

---

## Monitoring

### Check logs:
```bash
tail -f shared/logs/marketer.log
```

### Check approval queue:
```bash
cat shared/approval_queue.yml
```

### Check published content:
```bash
cat agents/marketer/content/published_log.yml
```

---

## Troubleshooting

**"No content being generated"**
- Check: `agents/marketer/heartbeat_state.yml`
- Verify: All API keys in `.env`
- Look for errors in: `shared/logs/marketer.log`

**"Content stuck in approval queue"**
- Check Telegram for pending approvals
- Content expires after 48h (auto-archived)
- Send `/pending` to Telegram bot to see queue

**"Publishing failed"**
- Verify social media API tokens
- Check platform-specific API limits
- See `agents/marketer/content/failed_posts/` for details

**"Agent not following content mix"**
- Check: `agents/marketer/heartbeat_state.yml` → `weekly_content_mix`
- Agent auto-rebalances if deviation >15%
- Manually override in heart beat_state if needed

---

## Success Metrics

**Daily Output:**
- Target: 12+ pieces (1 story + 1 video + 1 thread + 1 carousel)
- Minimum: 8 pieces

**Weekly Mix:**
- Educational: ~40%
- Social Proof: ~30%
- Product: ~20%
- Community: ~10%

**Engagement:**
- Track in `published_log.yml`
- Agent analyzes daily and adjusts strategy

---

## Emergency Commands

**Pause all content generation:**
```bash
# Edit heartbeat_state.yml:
content_paused: true
```

**Clear approval queue:**
```bash
> shared/approval_queue.yml
```

**Force regenerate today's content:**
```bash
# Edit heartbeat_state.yml:
content_generated_today:
  story: false
  video: false
  derivatives: false
```

---

## Product Launch (When Innovator Delivers New Bot)

The agent automatically:
1. Detects new bot in `shared/product_inventory.yml`
2. Generates product campaign:
   - 60s product video
   - 8-tweet thread with metrics
   - 8-slide carousel
   - Instagram story announcement
3. Sends to approval with **HIGH PRIORITY** flag
4. You review and approve
5. Publishes across all platforms

---

## FAQs

**Q: Can I edit content before approving?**
A: Yes, click [Edit Caption] in Telegram approval message.

**Q: What if I don't approve within 48h?**
A: Content auto-archives to `expired/` folder. Agent generates fresh content.

**Q: Can I manually trigger content generation?**
A: Yes, but easier to just wait for next heartbeat (every 30min).

**Q: How do I change the content mix percentages?**
A: Edit `agents/marketer/IDENTITY.md` and restart agent.

**Q: Can I disable specific platforms?**
A: Yes, remove from `platforms` list in approval before clicking [Approve].

---

## Further Reading

- **IDENTITY.md** — Full agent instructions and workflows
- **HEARTBEAT.md** — Detailed heartbeat task logic
- **SOUL.md** — Brand guidelines (all agents)
- **../../../README.md** — Overall system architecture

---

*This agent runs autonomously. Your only job: review Telegram approvals daily (5-10 minutes). The agent does the rest.*

---
