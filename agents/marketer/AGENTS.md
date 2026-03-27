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

1. **Generates content idea** (manual or Tavily trend search)
2. **Generates complete content package in 1 LLM call:**
   - Video script (15-60 seconds)
   - Carousel key points (6-8 slides)
   - Tweet thread key points (5 tweets)
3. **Creates video** with AI avatar speaking the script
4. **Generates 6-8 carousel images** from key points
5. **Formats tweets** from key points (≤280 chars each)
6. **Sends everything to you for approval** via Telegram
7. **Publishes approved content** to all platforms

**Result:** ~12 content pieces per day (1 video + 6 images + 5 tweets) from ONE core generation cycle.

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
The agent uses 10 custom Python skills:

**Core Skills (New Optimized Pipeline):**
- `content_script_generator` ⭐ **NEW** → Generates complete content package in 1 LLM call
- `video_generation` → Creates AI videos with consistent avatar or mascot-led Veo scenes
- `image_generation` → Generates brand-compliant images
- `video_to_carousel` → Converts video to Instagram carousel (5-8 slides)
- `video_to_tweet_thread` → Converts video script to 5-tweet thread
- `dynamic_prompt_generator` → Creates unique image prompts (no templates)

**Supporting Skills:**
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

## Content Generation Workflow (Optimized)

### Step-by-Step Process

```
1. [IDEA GENERATION] (Manual or Tavily search)
   Input: Topic or trend
   Output: Content idea
   Cost: $0 (manual) or $0.01 (Tavily API)

2. [CONTENT_SCRIPT_GENERATOR] ⭐ NEW OPTIMIZED SKILL
   Input: Topic + content_type + duration
   Output: {
     video_script: "30s spoken script",
     carousel_points: ["point1", "point2", ..., "point6"],
     tweet_points: ["hook", "value1", "value2", "value3", "cta"]
   }
   Cost: 1 LLM call (Gemini 2.0 Flash)

3. [VIDEO_GENERATION]
   Input: video_script
   Output: video.mp4 (AI avatar speaking or mascot-led clip)
   Cost: depends on `shared/brand_config.yml` video provider (D-ID by default)

4. [CAROUSEL_IMAGE_GENERATION]
   Input: carousel_points[] (from step 2)
   For each point:
     4a. Generate image prompt (dynamic_prompt_generator)
     4b. Generate image (provider from `shared/brand_config.yml`)
   Output: 6 carousel images
   Cost: depends on configured image provider (Flux by default)

5. [TWEET_FORMATTING]
   Input: tweet_points[] (from step 2)
   Output: 5 formatted tweets (≤280 chars each)
   Cost: 0 LLM calls (pure string formatting)

6. [TELEGRAM_HITL]
   Input: video + carousel + tweets
   Output: Approval request to owner
   Cost: $0 (Telegram API is free)

7. [SOCIAL_MEDIA_PUBLISHER]
   Input: Approved content bundle
   Output: Published to all platforms
   Cost: $0 (platform APIs are free)
```

### Key Optimization

**BEFORE:** 3 separate LLM calls for script extraction
- `video_to_carousel` → Extract carousel points
- `video_to_tweet_thread` → Extract tweet thread
- `dynamic_prompt_generator` → Generate image prompts

**AFTER:** 1 unified LLM call
- `content_script_generator` → Generates ALL content in one shot

**Result:** 66% reduction in LLM calls, more coherent content

---

## LLM & API Usage Table

| Step | Tool | Model/API | Purpose | Calls/Day | Cost/Call | Cost/Day | Cost/Month |
|------|------|-----------|---------|-----------|-----------|----------|------------|
| 1 | Tavily Search | Tavily API | Find trending topics | 0-1 | $0.01 | $0.01 | $0.30 |
| 2 | **content_script_generator** | **Gemini 2.0 Flash** | **Generate script + all points** | **1** | **$0.001** | **$0.001** | **$0.03** |
| 3 | video_generation | Configurable video provider | Text-to-video (AI avatar) | 1 | varies | varies | varies |
| 4a | dynamic_prompt_generator | Gemini 2.0 Flash | Image prompts (batch) | 1 | $0.001 | $0.001 | $0.03 |
| 4b | image_generation | Configurable image provider | Generate carousel images | 6 | varies | varies | varies |
| **TOTAL** | | | | **10** | | **$0.16** | **$4.86** |

¹ Flux Schnell is free but rate-limited. Actual cost depends on the provider selected in `shared/brand_config.yml`.

**Key Takeaway:** LLM costs are negligible. Media cost depends on the configured video/image providers.

### Cost Projections

| Scenario | Content/Day | Videos/Month | LLM Calls/Month | Total Cost/Month |
|----------|-------------|--------------|-----------------|------------------|
| Current (1/day) | 12 pieces | 30 | 90 | $4.86 |
| Scaled (2/day) | 24 pieces | 60 | 180 | $9.72 |
| Scaled (3/day) | 36 pieces | 90 | 270 | $14.58 |

---

## Critical Prompts (Quality Control)

**IMPORTANTE:** Estos son los prompts base que se envían a los LLMs. Si `brand_mascot.enabled: true`, se agrega además una sección dinámica para que el guion pueda ser hablado por la mascota.

---

### 1. Main Content Generation Prompt (content_script_generator)

**Location:** `skills/content_script_generator.py:180-268`
**Model:** Configurable (default: Gemini 2.0 Flash Exp)
**Input:** Topic, content_type, duration, carousel_slides, num_tweets, context
**Output:** JSON con video_script + carousel_points[] + tweet_points[]

**PROMPT COMPLETO (ejemplo con topic="Why algo trading beats emotions", educational, 30s):**

```
You are the content strategist for Jess Trading, a premium algorithmic trading brand.

    Jess Trading Brand Voice:
    - Professional but human (not corporate)
    - Concise and direct (no fluff)
    - Data-driven (lead with metrics when applicable)
    - Transparent (show risks, admit limitations)
    - Aspirational but not hypey
    - Confident, educational, slightly technical
    - FORBIDDEN WORDS: "guaranteed", "100% success", "get rich quick", "never lose", "foolproof", "can't fail"

CONTENT TYPE: educational
GUIDELINES FOR THIS TYPE:
- Focus: Teaching concepts, psychology, or technical aspects of algo trading
- Hook Style: Question or surprising fact
- Metrics Usage: Minimal, use only for context
- CTA Style: Link in bio to learn more


TASK: Generate a complete content package for the following topic:

TOPIC: "Why algo trading beats emotions"

TARGET VIDEO DURATION: 30 seconds

OUTPUT 3 COMPONENTS:

═══════════════════════════════════════════════════════════════

1. VIDEO SCRIPT (30 seconds):

Structure:
- HOOK (first 3-5 seconds): Question or surprising fact
- MAIN CONTENT (next 20 seconds): 3-4 key points, rapid-fire
- CTA (last 5-7 seconds): Link in bio to learn more

Requirements:
- Write EXACTLY for 30 seconds (estimate ~3 words per second)
- Use short, punchy sentences
- Natural spoken language (contractions OK)
- Include verbal pauses with "..." where natural
- NO stage directions, NO [brackets], just pure spoken text
- Professional but conversational

═══════════════════════════════════════════════════════════════

2. CAROUSEL KEY POINTS (6 slides):

Structure:
- Slide 1: Title/Hook (max 8 words, engaging question or statement)
- Slides 2-5: Key insights (each 10-15 words, 1-2 sentences)
- Slide 6: CTA/Conclusion (max 12 words, clear call to action)

Requirements:
- Each point should work as standalone text overlay on an image
- Use simple, impactful language
- Can include 1 emoji per point (optional, use sparingly)
- Extract different angles than the video (complement, don't duplicate)

═══════════════════════════════════════════════════════════════

3. TWEET THREAD KEY POINTS (5 tweets):

Structure:
- Tweet 1: HOOK (attention-grabbing, make them want thread)
- Tweets 2-4: VALUE (insights, data, explanation)
- Tweet 5: CTA + DISCLAIMER (if metrics present)

Requirements:
- Plan for ≤280 characters per tweet (will be formatted later)
- Extract essence, not full sentences (these are KEY POINTS)
- Different perspective than video (repurpose, don't copy)
- No hashtags needed (key points only)

═══════════════════════════════════════════════════════════════

OUTPUT FORMAT (STRICT JSON):

{
  "video_script": "Your 30-second script here...",
  "carousel_points": [
    "Slide 1 text here",
    "Slide 2 text here",
    ...
    "Slide 6 text here"
  ],
  "tweet_points": [
    "Tweet 1 key point",
    "Tweet 2 key point",
    ...
    "Tweet 5 key point"
  ]
}

CRITICAL: Return ONLY valid JSON. No markdown formatting, no ```json```, just the JSON object.

Now generate the content package:
```

**Para modificar este prompt:** Edita `shared/brand_config.yml` (brand_voice, content_types, `brand_mascot`, etc.)

---

### 2. Carousel Image Generation Prompt (video_to_carousel)

**Location:** `skills/video_to_carousel.py:298-338`
**Model:** Replicate/Flux Schnell
**Input:** Carousel point text, slide_type, slide_number
**Output:** Image 1080x1080px

**PROMPT COMPLETO (ejemplo para slide title):**

```
Instagram carousel title slide, minimalist design.
Carbon Black #101010 solid background.
Large bold text in center: "Why emotions kill your trades?"
Text color: White or Neon Green #45B14F.
Subtle geometric accent (thin lines or dots).
Clean, premium, Apple keynote aesthetic.
Square format 1080x1080px.

STRICT COLOR REQUIREMENTS:
- Background: Carbon Black #101010
- Text: White or Light Gray #A7A7A7
- Accents: Neon Green #45B14F or Electric Blue #2979FF only
```

**Para modificar:** Edita `shared/brand_config.yml` (visual_identity section)

---

### 3. Tweet Thread Extraction Prompt (video_to_tweet_thread)

**Location:** `skills/video_to_tweet_thread.py:128-163`
**Model:** Configurable (legacy skill, usa Gemini 2.0 Flash hardcoded)
**Input:** Video script
**Output:** 5 tweets ≤280 chars

**PROMPT COMPLETO:**

```
You are a social media expert for Jess Trading, a premium algorithmic trading brand.

Jess Trading Brand Voice:
- Professional but human (not corporate)
- Concise and direct (no fluff)
- Data-driven (lead with metrics)
- Transparent (show risks, admit limitations)
- Aspirational but not hypey
- No: "guaranteed", "100%", "get rich quick", hype emojis

Tweet Thread Structure (5 tweets):

Tweet 1: HOOK (Attention-grabber, make them want to read more)
- Max 280 characters
- Question, bold statement, or surprising fact
- No CTA yet

Tweet 2-4: VALUE (Educational insights, data, explanation)
- Each tweet stands alone but flows together
- Lead with facts and metrics
- Use short sentences, impactful

Tweet 5: CTA + DISCLAIMER (Call to action + risk disclosure if needed)
- Clear next step ("Link in bio", "Learn more")
- Include disclaimer if showing metrics: "Past performance ≠ future results"

TASK: Convert the following video script into a 5-tweet thread.

VIDEO SCRIPT:
---
[Script aquí]
---

CONTENT TYPE: educational

REQUIREMENTS:
- Each tweet must be ≤280 characters (STRICT)
- Follow the thread structure above
- Maintain brand voice (professional, concise, transparent)
- No disclaimer needed
- No hashtags (clean threads only)
- Max 1 emoji per tweet (use sparingly)

OUTPUT FORMAT:
Return ONLY the tweets, one per line, numbered 1-5.

Example:
1. The market doesn't wait for you to wake up.
2. In milliseconds, opportunities pass. This is why institutional traders automated decades ago.
3. Today, retail traders have the same advantage. Systematic. Disciplined. Emotion-free.
4. Automation doesn't guarantee profits. But it removes the biggest obstacle: human emotion.
5. Link in bio to explore proven strategies. Past performance ≠ future results.

NOW GENERATE THE THREAD:
```

**Nota:** Este skill está legacy, recomendamos usar `content_script_generator` que ya genera los tweet points.

---

### Prompt Variables (Configurables en brand_config.yml)

Todas estas variables se cargan automáticamente desde `shared/brand_config.yml`:

| Variable | Ubicación en YAML | Uso |
|----------|------------------|-----|
| `brand_name` | `brand_name` | Nombre de marca en prompts |
| `brand_voice` | `brand_voice.characteristics[]` | Lista de características de voz |
| `forbidden_words` | `brand_voice.forbidden_words[]` | Palabras prohibidas |
| `content_types` | `content_types.{type}` | Guidelines por tipo de contenido |
| `color_palette` | `visual_identity.color_palette` | Colores de marca |
| `video_pacing` | `video_settings.script_pacing` | Palabras/segundo, pausas |
| `platform_limits` | `platforms.{platform}` | Límites de caracteres, aspect ratios |

---

### Cómo Modificar Prompts

1. **Cambiar brand voice:**
   ```bash
   vim shared/brand_config.yml
   # Edita brand_voice.characteristics
   ```

2. **Agregar palabras prohibidas:**
   ```yaml
   forbidden_words:
     - "guaranteed"
     - "tu_nueva_palabra"
   ```

3. **Cambiar guidelines de contenido educativo:**
   ```yaml
   content_types:
     educational:
       focus: "Tu nuevo enfoque aquí"
       hook_style: "Tu estilo de hook"
   ```

4. **Reiniciar agent:**
   ```bash
   openclaw restart marketer
   ```

Los cambios se aplican **inmediatamente** sin tocar código Python.

---

### Prompt Review Checklist

Antes de publicar contenido, verifica:

✅ Video scripts incluyen pausas naturales ("...")
✅ No contiene palabras prohibidas (ver `brand_config.yml`)
✅ Contenido de producto incluye disclaimer
✅ Carousel points son legibles sin contexto del video
✅ Brand colors estrictamente respetados en imágenes
✅ Tweets ≤280 caracteres
✅ Tono profesional sin hype

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
cat > shared/approval_queue.yml <<'YAML'
queue: []
archived: []
YAML
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
