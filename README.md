# 🤖 Jess Trading Autonomous Agency

**Automated workforce for 90% operational automation using OpenClaw framework**

This system orchestrates 4 specialized AI agents to automate product development, content marketing, customer support, and financial operations for Jess Trading — a retail algorithmic trading bot platform.

---

## 🎯 What This System Does

**Automates:**
- Trading strategy development (EA_developer pipeline integration)
- Social media content generation (Instagram, X/Twitter, TikTok, YouTube Shorts, Facebook)
- Customer support & engagement (DMs, comments, FAQs)
- Sales tracking & financial reporting (Whop integration)

**Human-in-the-Loop (HITL):**
- ALL content publishing requires owner approval via Telegram
- ALL financial transactions require explicit approval
- Zero autonomous actions on critical operations

**Result:**
- 90% operational automation
- ~30-60 min/day owner time (approvals only)
- 24/7 operations while you sleep, travel, or focus on strategy

**Current State of This Repo:**
- Current OpenClaw path is workspace-based: register `agents/*` with your own OpenClaw install
- Marketer workflow is the most complete agent and now supports configurable video/image providers
- Talking-avatar video generation is implemented for D-ID and HeyGen
- Prompt-based generative video is implemented for Veo on Vertex AI
- Brand mascot scaffolding is available for Veo reference-image workflows
- Scheduling is controlled by `shared/brand_config.yml` plus the marketer heartbeat
- Other agents are still scaffolded and need deeper API integration

---

## 🏗️ System Architecture

### The 4-Agent Squad

```
┌──────────────────────────────────────────────────────────────┐
│                    TELEGRAM GATEWAY                          │
│             (Human-in-the-Loop Approval)                     │
│  All content & financial decisions route through you         │
└──────────────────────────────────────────────────────────────┘
           ▲            ▲            ▲            ▲
           │            │            │            │
    ┌──────┴─────┐ ┌───┴────┐ ┌─────┴─────┐ ┌───┴─────┐
    │ Innovator  │ │Marketer│ │ Community │ │Operator │
    │  (R&D)     │ │(Content│ │  Manager  │ │(Finance)│
    │            │ │ Lead)  │ │ (Support) │ │         │
    └──────┬─────┘ └───┬────┘ └─────┬─────┘ └────┬────┘
           │           │            │            │
           ▼           ▼            ▼            ▼
    ┌──────────────────────────────────────────────┐
    │         EA_developer Pipeline                │
    │   (7 sub-agents: Research → Validate)        │
    └──────────────────────────────────────────────┘
```

### Agent Roles

**1. Innovator (Product Lead)** ✅ **Status: Configured, needs integration**
- Runs EA_developer pipeline every 12 hours
- Generates trading strategies (EURUSD, GBPUSD, XAUUSD, USDJPY)
- Validates with strict quality filters (PF >1.5, Sharpe >1.2, DD <30%)
- Outputs: `.mq5` bot files + comprehensive backtest reports
- Notifies Marketer when new product ready

**2. Marketer (Content Lead)** ✅ **Status: Baseline workflow implemented**
- Monitors trends via Tavily search (crypto, algo trading)
- Generates brand-compliant content (Carbon Black + Neon Green palette)
- Creates multi-platform content (Instagram, X, TikTok, YouTube Shorts, Facebook)
- Video provider configurable via `shared/brand_config.yml`
- Image provider configurable via `shared/brand_config.yml`
- **HITL:** Sends ALL content to Telegram for approval before publishing
- Internal generation cadence: `shared/brand_config.yml -> content_schedule`
- External invocation cadence: user-defined (a common setup is every 30 minutes)

**3. Community Manager (Support Lead)** ⚠️ **Status: Configured, needs API integration**
- Planned support coverage across customer channels once messaging APIs are connected
- Knowledge Base powered responses
- Sentiment analysis & escalation
- <30 min response time (business hours)
- Auto-escalates refunds, angry customers, technical issues

**4. Operator (Sales & Billing)** ⚠️ **Status: Configured, needs Whop/Stripe integration**
- Real-time Whop sales monitoring
- Affiliate commission tracking (40% per sale = $58.80)
- **MANDATORY approval** for ALL refunds (read-only API keys)
- Daily/weekly/monthly financial reports
- Fraud detection

---

## 🚀 Quick Start (Deploy on New Machine)

### Prerequisites

Install before starting:
- **Node.js** ≥ 18.x → https://nodejs.org
- **Python** ≥ 3.10 → https://python.org
- **Git** (for cloning)

Supported development environment:
- macOS and Linux are the primary supported environments for the current scripts
- Windows would need WSL or some script adjustments
- If you later enable `Innovator`, the `EA_developer` MT5 pipeline still needs a Windows environment with MetaTrader 5 available

### Step 1: Clone Project

```bash
git clone <your-repo> autonomous_agency
cd autonomous_agency/
```

### Step 2: Get API Keys

Required for the default Marketer stack:

**OpenAI API** (current default Marketer profiles: copy + image + video)
- Get at: https://platform.openai.com
- Save: `OPENAI_API_KEY=sk-...`

**Google Gemini API** (optional if you choose a Gemini-based marketer profile)
- Get at: https://aistudio.google.com/app/apikey
- Save: `GEMINI_API_KEY=AIzaSy...`

**Telegram Bot** (HITL approvals)
- Open Telegram → search @BotFather
- Send: `/newbot`
- Follow prompts
- Save: `TELEGRAM_BOT_TOKEN=123456:ABC...`
- Get Chat ID: Send message to your bot, then:
  - Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
  - Find: `"chat":{"id":123456789}`
  - Save: `TELEGRAM_OWNER_CHAT_ID=123456789`

**Tavily API** (Web search - Free tier)
- Get at: https://tavily.com
- Save: `TAVILY_API_KEY=tvly-...`

Optional provider alternatives:
- `ANTHROPIC_API_KEY` for Claude-based marketer copy profiles
- `HEYGEN_API_KEY` for HeyGen avatar-first video profiles
- `GOOGLE_CLOUD_PROJECT` + ADC credentials for Veo on Vertex AI
- `D_ID_API_KEY` for the D-ID baseline avatar profile
- `REPLICATE_API_TOKEN` for Flux / SDXL image profiles
- `SYNTHESIA_API_KEY` for Synthesia
- `RUNWAY_API_KEY` for Runway
- `PIKA_API_KEY` for Pika
- `IDEOGRAM_API_KEY` for Ideogram
- `MIDJOURNEY_API_KEY` for Midjourney

Optional (for other agents):
- Instagram Graph API
- X/Twitter API
- TikTok API / access token
- YouTube Data API
- Facebook Graph API
- Whop API (sales)
- Stripe API (payments)

### Step 3: Run Setup Script

```bash
chmod +x setup.sh
./setup.sh
```

The setup script:
- ✅ Checks prerequisites (Node.js, Python, npm, pip)
- ✅ Installs OpenClaw globally: `npm install -g openclaw`
- ✅ Installs Python dependencies: `pip3 install -r requirements.txt`
- ✅ Creates `.env` from `.env.example`
- ✅ Creates required directories
- ✅ Runs a repo/bootstrap preflight
- ✅ Tests Telegram Gateway
- ✅ Leaves OpenClaw runtime/model selection to the future user

### Step 4: Configure .env

```bash
nano .env
```

Add your API keys:
```bash
# Current default Marketer stack
OPENAI_API_KEY=your_openai_key

# Telegram (required for HITL)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_OWNER_CHAT_ID=your_chat_id

# Optional but recommended for trend discovery
TAVILY_API_KEY=your_key

# Alternative Marketer copy providers
HEYGEN_API_KEY=your_heygen_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_CLOUD_PROJECT=your_gcp_project
GOOGLE_APPLICATION_CREDENTIALS=/abs/path/to/service-account.json
RUNWAY_API_KEY=your_runway_key
D_ID_API_KEY=your_video_key
REPLICATE_API_TOKEN=your_token

# Social Media (optional - only needed for publishing)
INSTAGRAM_ACCESS_TOKEN=your_token
INSTAGRAM_USER_ID=your_instagram_user_id
PUBLIC_MEDIA_BASE_URL=https://media.example.com/
X_API_KEY=your_key
X_API_SECRET=your_secret
X_ACCESS_TOKEN=your_token
X_ACCESS_SECRET=your_secret
TIKTOK_ACCESS_TOKEN=your_token
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret
YOUTUBE_TOKEN_FILE=shared/memory/youtube_token.json
FACEBOOK_ACCESS_TOKEN=your_token
FACEBOOK_PAGE_ID=your_page_id

# Financial APIs (optional - read-only)
WHOP_API_KEY_READ=your_key
STRIPE_API_KEY_READ=your_key
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

### Step 5: Register Agent Workspaces with OpenClaw

The current OpenClaw flow is workspace-based. This repo provides the workspaces; the end user wires them into their own OpenClaw profile.

```bash
python3 register_openclaw_agents.py
```

That script:
- Registers each repo workspace under `agents/*`
- Syncs identity metadata from each `IDENTITY.md`
- Does not change the user's runtime model, bindings, or OpenClaw profile choices

### Step 6: Verify the Repo and Test a Local Agent Turn

Check repo readiness:
```bash
python3 check_system_setup.py --mode runtime
```

Inspect registered agents:
```bash
openclaw agents list --bindings
```

Run a local one-turn smoke test with your own OpenClaw runtime:
```bash
openclaw agent --local --agent marketer --message "status check"
```

Optional: start the Telegram HITL gateway from this repo:
```bash
python3 shared/telegram_gateway.py
```

### Step 7: Verify

**Test Telegram Bot:**
1. Open Telegram
2. Find your bot
3. Send: `/start`
4. Receive: "Jess Trading Agency — HITL Gateway Online"

**Check Logs:**
```bash
tail -f shared/logs/*.log
```

**Wait for First Heartbeat:**
- After the next heartbeat window, Marketer will read `shared/brand_config.yml`
- It will only generate if `content_schedule` says the current slot is active
- You'll receive approval request in Telegram with preview
- Click [Approve] or [Deny]
- Marketer responds based on your decision

---

## ⚙️ Configuration

### Current OpenClaw Integration

The repo no longer assumes control over the user's global OpenClaw runtime config.

What this repo owns:
- agent workspaces under `agents/*`
- shared repo logic, prompts, providers, and Python tooling
- helper scripts like `register_openclaw_agents.py`

What the future user owns:
- their OpenClaw runtime model/provider
- their bindings, channels, gateway, scheduling, and profile config

`config/openclaw.config.yml` is kept only as legacy reference from an older repo workflow.

### Brand + Media Config: `shared/brand_config.yml`

Defines:
- LLM defaults for content skills
- Video generation provider and per-provider settings
- Image generation provider and per-provider settings
- Optional `brand_mascot` settings for consistent mascot-led scenes
- `content_schedule` for generation cadence

### Switching Providers Quickly

The preferred way to switch the `Marketer` stack is now through curated profiles in `shared/brand_config.yml`.

**1. Change the active profiles**

Edit:

```yaml
provider_selections:
  llm: "openai_gpt_5_2_copy"
  image: "openai_gpt_image_1_5_high"
  video: "openai_sora_2_pro_cinematic"
```

This lets you mix providers independently per modality.

Examples:

```yaml
provider_selections:
  llm: "claude_sonnet_4_copy"
  image: "openai_gpt_image_1_5_high"
  video: "google_veo_3_1_cinematic"
```

```yaml
provider_selections:
  llm: "google_gemini_2_5_flash_copy"
  image: "flux_schnell_free"
  video: "d_id_baseline_avatar"
```

**2. Current curated profiles included**

Language:
- `openai_gpt_5_2_copy`
- `openai_gpt_5_2_chat_copy`
- `openai_gpt_5_2_pro_copy`
- `claude_sonnet_4_copy`
- `claude_opus_4_1_copy`
- `google_gemini_2_5_pro_copy`
- `google_gemini_2_5_flash_copy`

Images:
- `openai_gpt_image_1_5_high`
- `openai_gpt_image_1_mini`
- `flux_schnell_free`
- `sdxl_balanced`

Video:
- `openai_sora_2_pro_cinematic`
- `openai_sora_2_fast`
- `google_veo_3_1_cinematic`
- `heygen_avatar_consistent`
- `d_id_baseline_avatar`

**3. Which ones are actually implemented today**

Implemented now:
- LLM: OpenAI, Claude, Gemini
- Image: `openai-image`, `flux`, `sdxl`, legacy `dalle`
- Video: `openai-sora`, `veo`, `heygen`, `d-id`

Configurable placeholders only:
- Image: `midjourney`, `ideogram`
- Video: `synthesia`, `runway`, `pika`

**4. Validate before using the selected marketer stack**

After any switch, run:

```bash
python3 check_system_setup.py --mode runtime
```

That check confirms:
- active LLM/image/video profiles
- required env vars
- whether the selected providers are implemented
- whether the current `Marketer` stack is bootable

Example:
```yaml
brand_mascot:
  enabled: true
  reference_images:
    - "assets/mascot/front.png"
    - "assets/mascot/three_quarter.png"
    - "assets/mascot/profile.png"

video_generation:
  provider: "veo"

image_generation:
  provider: "flux"

content_schedule:
  videos_per_day: 10
  generation_window:
    start: "08:00"
    end: "23:00"
```

For Veo:
- Set `video_generation.provider: "veo"` in `shared/brand_config.yml`
- Configure `GOOGLE_CLOUD_PROJECT`
- Authenticate with Google Application Default Credentials
  You can do that either with `GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json`
  or with `gcloud auth application-default login`
- If using a mascot, set `brand_mascot.enabled: true`
- Add up to 3 mascot reference images in `brand_mascot.reference_images`
- Place those images under `assets/mascot/` or another repo path you control
- Veo prompts are automatically adapted so the mascot stays in trading-related scenes and speaks the generated script

For HeyGen:
- Set `video_generation.provider: "heygen"` in `shared/brand_config.yml`
- Configure `HEYGEN_API_KEY`
- Set `heygen.avatar_id` plus `heygen.voice_id`
- Optional: switch to `character_type: "talking_photo"` and provide `talking_photo_id`

### Brand Identity: `SOUL.md`

**CRITICAL:** All agents read `SOUL.md` for brand guidelines:
- Color palette (Carbon Black #101010, Neon Green #45B14F, Light Gray #A7A7A7, Electric Blue #2979FF)
- Voice & tone (premium, transparent, no hype)
- Core values (transparency, proven strategies, accessibility)
- Behavioral constraints (HITL approval, no sudo, sandbox only)

**Do NOT modify SOUL.md without careful consideration — it defines the entire brand.**

### Agent Identities

Each agent has:
- `agents/[name]/IDENTITY.md` — OpenClaw personality & instructions
- `agents/[name]/AGENTS.md` — Detailed operating manual (human documentation)
- `agents/[name]/HEARTBEAT.md` — recurring-task guide for that workspace

### Custom Skills (Python Tools)

Located in `skills/` directory:
- `telegram_hitl.py` — Send approval requests (HITL)
- `content_parser.py` — Extract metrics from strategy reports
- `tavily_search.py` — Web search for trends
- `video_generation.py` — Configurable AI video generation
- `image_generation.py` — Configurable AI image generation
- `social_media_publisher.py` — Publish to social platforms
- `marketer_runtime.py` — Enforce `content_schedule` and update Marketer state

Each skill has standalone testing: `python3 skills/[skill_name].py`

---

## 📊 How It Works (Marketer Example)

**Whenever the future user invokes Marketer on a recurring cadence:**

1. **Checks `shared/brand_config.yml` + `marketer_runtime`** to decide whether the current slot should generate content
2. **Searches trends** using Tavily when needed
3. **Generates script/caption** following brand voice (premium, transparent, no hype)
4. **Creates media** using the configured providers from `shared/brand_config.yml`
   - Current default video profile: OpenAI Sora 2 Pro
   - Current default image profile: OpenAI GPT Image 1.5 High
   - Brand palette stays centralized
5. **Sends to Telegram** for your approval with:
   - Caption preview
   - Media preview
   - Buttons: [Approve] [Deny] [Edit]
6. **Waits 48h** for your decision (timeout if no response)
7. **If approved:** `shared/telegram_gateway.py` autopublishes the approved bundle and records the result in the queue/state files
8. **Logs queue state** and publication history

**Your role:** Review on your phone, click [Approve] or [Deny]. That's it.

---

## 🛠️ Using This Repo with OpenClaw 2026

### Registering Agents

Use the helper script:

```bash
python3 register_openclaw_agents.py
```

Or do it manually per workspace:

```bash
openclaw agents add marketer --workspace /path/to/repo/agents/marketer --non-interactive
openclaw agents set-identity --agent marketer --identity-file /path/to/repo/agents/marketer/IDENTITY.md
```

Repeat for the agents you want to install.

### Testing One Turn

```bash
openclaw agent --local --agent marketer --message "status check"
```

### Telegram HITL

Run the gateway from this repo only if you want the Telegram approval flow:

```bash
python3 shared/telegram_gateway.py
```

### Scheduling / Gateway / Bindings

The future user still chooses their own OpenClaw profile, runtime model, channel bindings, and external invocation style.
What stays inside this repo:
- Marketer `content_schedule`
- HITL approval queue
- Telegram approval gateway
- autopublish logic after approval

---

## 🐛 Troubleshooting

### Common Issues

**"TELEGRAM_BOT_TOKEN not set"**
- Solution: Edit `.env` and add your bot token from @BotFather

**"openclaw: command not found"**
- Solution: Install globally: `npm install -g openclaw`

**"ModuleNotFoundError: No module named 'telegram'"**
- Solution: Install dependencies: `pip3 install -r requirements.txt`

**"Approval timeout after 48 hours"**
- Solution: Check Telegram for pending requests: `/pending`
- Approve within 48h or content expires

**"Rate limit exceeded for Tavily"**
- Solution: Free tier has daily limits. Reduce search frequency or upgrade

**"Image generation failed"**
- Solution: Check the active image provider in `shared/brand_config.yml`
- Then verify the matching key in `.env` (`REPLICATE_API_TOKEN`, `OPENAI_API_KEY`, etc.)

**"Video generation failed"**
- Solution: Check the active video provider in `shared/brand_config.yml`
- Then verify the matching key in `.env` (`D_ID_API_KEY`, `HEYGEN_API_KEY`, etc.)

**"Social media publishing failed"**
- Solution: Auto-publishing currently targets Instagram, X, TikTok, YouTube Shorts, and Facebook
- APIs require platform-specific integration:
  - Instagram: Graph API + Business Account + public media URL access (`PUBLIC_MEDIA_BASE_URL`) for local generated files
  - X: Twitter API v2 + OAuth
  - TikTok: Business or creator publishing access
  - YouTube Shorts: YouTube Data API + OAuth client + first-run local consent flow
  - Facebook: Graph API + Page access

### Debug Mode

Check repo-side logs:
```bash
tail -f shared/logs/*.log
```

For OpenClaw runtime debugging, use the user's own OpenClaw profile and CLI (`openclaw logs`, `openclaw doctor`, `openclaw config`, etc.).

### Get Help

- **Logs:** Check `shared/logs/` for error messages
- **Agent Manuals:** See `agents/[name]/AGENTS.md` for detailed instructions
- **Skills Testing:** Run skills standalone: `python3 skills/[name].py`

---

## 🔒 Security

### Key Security Features

- **Sandbox Mode:** All agents run in isolated environments
- **Read-Only APIs:** Whop and Stripe use read-only keys
- **HITL Approval:** Zero autonomy on content/financial actions
- **API Key Rotation:** Rotate every 90 days
- **Git Ignore:** `.env` never committed to repo

### File Boundaries

Agents can access:
- `agents/` — Their specific folder
- `skills/` — Custom tools
- `shared/` — Logs, memory, state files
- `EA_developer/` — Read-only (Innovator write access)

Agents CANNOT access:
- `/` , `/etc/`, `/sys/`, `/var/` — System directories
- Other agent folders (no cross-contamination)

### Refund Security

- Operator agent has **READ-ONLY** Whop/Stripe access
- ALL refund requests escalated to owner
- Owner must click [APPROVE REFUND] button
- Every refund logged with timestamp and approval trail
- Fraud detection (repeat refunders, same-day patterns)

---

## 📈 Success Metrics

**Week 1:**
- All agents running without errors
- Telegram approvals working
- Marketer publishes 5-7 posts (after approval)

**Month 1:**
- 40-60 strategies generated (Innovator)
- 25-30 posts published (Marketer)
- >70% support issues resolved without escalation
- <10% refund rate

**Month 3:**
- 90% operations automated
- Revenue growth >10% month-over-month
- 95%+ customer satisfaction
- Agency cost <30% of revenue

---

## 📚 Additional Documentation

**Agent Manuals:**
- `agents/innovator/AGENTS.md` — Product development workflow
- `agents/marketer/AGENTS.md` — Content generation workflow
- `agents/support/AGENTS.md` — Customer support workflow
- `agents/operator/AGENTS.md` — Financial management workflow

**Brand Guidelines:**
- `SOUL.md` — Shared brand identity (all agents)
- `docs/jess_trading_context_guide.md` — Visual identity, product specs

**Configuration:**
- `shared/brand_config.yml` — Main marketer/provider configuration
- `register_openclaw_agents.py` — Current OpenClaw workspace registration helper
- `config/openclaw.config.yml` — Legacy reference from the older repo-runner workflow
- `.env` — Environment variables (API keys)
- `requirements.txt` — Python dependencies

---

## 🎯 Roadmap

### Phase 1: Foundation (Current)
- [x] OpenClaw structure
- [x] Telegram Gateway (HITL)
- [x] Marketer baseline workflow
- [x] Configurable media providers via `shared/brand_config.yml`
- [x] Core custom skills
- [x] OpenClaw 2026 workspace registration helper
- [ ] Test Marketer end-to-end on a clean machine

### Phase 2: Expand Agents
- [ ] Implement Innovator (EA_developer integration)
- [ ] Implement Support (social media APIs)
- [ ] Implement Operator (Whop/Stripe integration)

### Phase 3: Production
- [ ] Systemd service files
- [ ] Monitoring dashboard
- [ ] Automated backups
- [ ] Performance optimization

---

## 📞 Support

- **System Issues:** Check `shared/logs/` for error messages
- **Telegram Bot:** All critical alerts route through your bot
- **Emergency:** System auto-escalates on critical failures

---

## 📄 License

Proprietary — Jess Trading Internal Use Only

---

**Last Updated:** 2026-03-30
**Version:** 1.0.0 (Marketer Operational, Other Agents Configured)

---

*The future of business is autonomous. Welcome to yours.* 🚀
