# 🤖 Jess Trading Autonomous Agency

**Automated workforce for 90% operational automation using OpenClaw framework**

This system orchestrates 4 specialized AI agents to automate product development, content marketing, customer support, and financial operations for Jess Trading — a retail algorithmic trading bot platform.

---

## 🎯 What This System Does

**Automates:**
- Trading strategy development (EA_developer pipeline integration)
- Social media content generation (Instagram, X/Twitter, LinkedIn)
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

**2. Marketer (Content Lead)** ✅ **Status: Fully implemented**
- Monitors trends via Tavily search (crypto, algo trading)
- Generates brand-compliant content (Carbon Black + Neon Green palette)
- Creates multi-platform content (Instagram, X, LinkedIn)
- AI image generation (Replicate API)
- **HITL:** Sends ALL content to Telegram for approval before publishing
- Heartbeat: Every 30 minutes

**3. Community Manager (Support Lead)** ⚠️ **Status: Configured, needs API integration**
- 24/7 customer support (Instagram, X, LinkedIn DMs)
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

### Step 1: Clone Project

```bash
git clone <your-repo> autonomus_agency
cd autonomus_agency/
```

### Step 2: Get API Keys

Required for Marketer agent (minimum):

**Google Gemini API** (LLM - Free tier)
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

**Replicate API** (Image generation - Free credits)
- Get at: https://replicate.com
- Save: `REPLICATE_API_TOKEN=r8_...`

Optional (for other agents):
- Instagram Graph API
- X/Twitter API
- LinkedIn API
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
- ✅ Validates configuration
- ✅ Tests Telegram Gateway
- ✅ Initializes OpenClaw

### Step 4: Configure .env

```bash
nano .env
```

Add your API keys:
```bash
# Core LLM (required)
GEMINI_API_KEY=your_key_here

# Telegram (required for HITL)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_OWNER_CHAT_ID=your_chat_id

# Services (required for Marketer)
TAVILY_API_KEY=your_key
REPLICATE_API_TOKEN=your_token

# Social Media (optional - for publishing)
INSTAGRAM_ACCESS_TOKEN=your_token
X_API_KEY=your_key
X_ACCESS_TOKEN=your_token
LINKEDIN_ACCESS_TOKEN=your_token

# Financial APIs (optional - read-only)
WHOP_API_KEY_READ=your_key
STRIPE_API_KEY_READ=your_key
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

### Step 5: Start System

**Option A: Start All (Recommended)**
```bash
./start_all.sh
```

This starts:
- Telegram Gateway (HITL approval system)
- Enabled agents (Marketer by default)

To stop: Press `Ctrl+C`

**Option B: Manual (Two Terminals)**

Terminal 1 — Telegram Gateway:
```bash
cd shared/
python3 telegram_gateway.py
```

Terminal 2 — Marketer Agent:
```bash
openclaw run marketer
```

### Step 6: Verify

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
- After 30 minutes, Marketer will search trends and generate content
- You'll receive approval request in Telegram with preview
- Click [Approve] or [Deny]
- Marketer responds based on your decision

---

## ⚙️ Configuration

### Main Config File: `config/openclaw.config.yml`

Defines:
- Agent settings (enabled/disabled, heartbeat intervals)
- LLM configuration (model, temperature, tokens, fallback)
- Skill settings (paths, parameters)
- HITL configuration (Telegram, approval timeouts)
- Security constraints (file boundaries, sandboxing)
- Logging & error handling

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
- `agents/[name]/HEARTBEAT.md` — 30-minute heartbeat tasks

### Custom Skills (Python Tools)

Located in `skills/` directory:
- `telegram_hitl.py` — Send approval requests (HITL)
- `content_parser.py` — Extract metrics from strategy reports
- `visual_validator.py` — Validate brand color palette
- `tavily_search.py` — Web search for trends
- `image_generation.py` — AI image generation (Replicate)
- `social_media_publisher.py` — Publish to social platforms

Each skill has standalone testing: `python3 skills/[skill_name].py`

---

## 📊 How It Works (Marketer Example)

**Every 30 minutes, Marketer:**

1. **Searches trends** using Tavily (e.g., "crypto bot trading 2026")
2. **Generates caption** following brand voice (premium, transparent, no hype)
3. **Creates image** using Replicate with exact brand palette
   - Carbon Black background (#101010)
   - Neon Green highlights (#45B14F)
   - Clean, minimalist fintech aesthetic
4. **Validates image** color compliance (automatic)
5. **Sends to Telegram** for your approval with:
   - Caption preview
   - Image preview
   - Buttons: [Approve] [Deny] [Edit]
6. **Waits 48h** for your decision (timeout if no response)
7. **If approved:** Publishes to Instagram, X, LinkedIn
8. **Logs published** content for analytics

**Your role:** Review on your phone, click [Approve] or [Deny]. That's it.

---

## 🛠️ Deployment Options

### Local Development

```bash
# Terminal 1: Gateway
cd shared/
python3 telegram_gateway.py

# Terminal 2: Agents
openclaw run marketer
# or
./start_all.sh
```

### Production (VPS)

**Option 1: Screen/Tmux**
```bash
# Telegram Gateway
screen -S telegram
cd shared/ && python3 telegram_gateway.py
# Ctrl+A, D to detach

# Marketer Agent
screen -S marketer
openclaw run marketer
# Ctrl+A, D to detach

# Reattach: screen -r telegram
```

**Option 2: Systemd Services (Recommended)**

Create service files:
```bash
# /etc/systemd/system/jess-telegram-gateway.service
[Unit]
Description=Jess Trading Telegram Gateway
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/autonomus_agency/shared
ExecStart=/usr/bin/python3 telegram_gateway.py
Restart=always
RestartSec=10
EnvironmentFile=/path/to/autonomus_agency/.env

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable jess-telegram-gateway
sudo systemctl start jess-telegram-gateway
sudo systemctl status jess-telegram-gateway
```

Repeat for each agent.

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
- Solution: Check `REPLICATE_API_TOKEN` in .env. Verify API credits.

**"Social media publishing failed"**
- Solution: APIs require platform-specific integration:
  - Instagram: Graph API + Business Account
  - X: Twitter API v2 + OAuth
  - LinkedIn: LinkedIn API + Company Page access

### Debug Mode

Enable debug logging in `config/openclaw.config.yml`:
```yaml
logging:
  level: "DEBUG"  # Change from INFO
```

Check logs:
```bash
tail -f shared/logs/*.log
```

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
- `config/openclaw.config.yml` — Main system configuration
- `.env` — Environment variables (API keys)
- `requirements.txt` — Python dependencies

---

## 🎯 Roadmap

### Phase 1: Foundation (Current)
- [x] OpenClaw structure
- [x] Telegram Gateway (HITL)
- [x] Marketer agent (fully functional)
- [x] 6 custom skills
- [x] Deployment scripts
- [ ] Test Marketer end-to-end

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

**Last Updated:** 2026-03-23
**Version:** 1.0.0 (Marketer Operational, Other Agents Configured)

---

*The future of business is autonomous. Welcome to yours.* 🚀
