# 🗡️ FLOW — Solo Leveling Productivity System

<p align="center">
  <strong>Turn your daily tasks into quests. Level up in real life.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/theme-Solo%20Leveling-00d4ff?style=for-the-badge" alt="Theme">
  <img src="https://img.shields.io/badge/React-18-61dafb?style=for-the-badge&logo=react" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/deploy-Render-46E3B7?style=for-the-badge&logo=render" alt="Render">
</p>

---

## 🎮 What is FLOW?

FLOW is a **gamified productivity app** inspired by the anime **Solo Leveling**. It transforms your daily tasks into RPG-style quests with a full progression system — XP, stats, ranks, a shadow rival, adaptive difficulty, and an AI coach. Every task you complete makes you stronger. Every day you skip has consequences.

**Live:** [flow-rpg.tech](https://flow-rpg.tech)

---

## ⚔️ Core Systems

### 🏹 Quest Engine
- **6 Power Domains**: Mind, Body, Core, Control, Presence, System
- **4 Difficulty Tiers**: D-tier (easy) → A-tier (extreme) with scaling XP rewards
- **96 Quest Templates** seeded on first startup
- **Manual Quests**: Create custom quests with your own parameters
- **AI-Generated Quests**: Groq LLM generates personalized quests based on your profile
- **Quest Timer**: Real-time countdown with pause/resume
- **Auto-Expiry**: Quests exceeding 24-hour windows are automatically failed (background scheduler)

### 📊 Adaptive Difficulty System
- **Difficulty Profile** per domain tracks your success/failure rate
- **Performance-based scaling**: Quests get harder as you improve, easier if you struggle
- **Constraint levels, risk levels, and cooldown mechanics** per tier
- **Push System**: Periodically pushes you beyond your comfort zone

### 🏆 RPG Progression
- **5 Core Stats**: STR (Strength), INT (Intelligence), VIT (Vitality), CHA (Charisma), MAN (Mana)
- **XP & Leveling**: Earn XP from quests, level up, and allocate stat points
- **Rank System**: E → D → C → B → A → S → SS → SSS ranks with rank-specific perks
- **Progression Tiers**: Multi-phase progression with increasing requirements

### 👤 Shadow Rival
- An AI-paced rival that mirrors your optimal pace
- Tracks XP difference and gives system messages
- Pushes you to maintain consistency

### ✅ Verification Engine
- **3 Verification Types**: Log-based, Output-based, Metric-based
- **Spot Checks**: Random verification challenges to maintain integrity
- **Trust Score**: Player trust profile based on verification accuracy
- **Abuse Detection**: Detects gaming the system (speed runs, suspicious patterns)
- **Audit Flags & Logs**: Full audit trail for quest completions

### ❤️ HP / MP / Fatigue System
- **HP (100)**: Lose HP for failures, gain from completions
- **MP (50)**: Spend MP on special actions
- **Fatigue (0→100)**: Accumulates with overwork, forces rest days
- **Streak Tracking**: Consecutive day streaks with penalties for breaks
- **Penalty Tiers**: Progressive punishment for inactivity

### 🤖 AI Coach
- Powered by **Groq LLM** (optional — works without API key via rule-based engine)
- Personalized coaching based on your stats, streaks, and quest history
- Session logging for tracking advice over time

### 🎒 Inventory & Shop
- **Inventory System**: Collect items from quest rewards
- **Shop**: Purchase items with earned currency

### 📈 Analytics Dashboard
- 7-day XP performance charts (Recharts)
- Domain-wise strength analysis
- Streak history and stat breakdowns
- Progression analytics with trend tracking

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│                   FLOW System                     │
├──────────────────┬───────────────────────────────┤
│    Frontend      │          Backend              │
│    (React SPA)   │        (FastAPI)              │
├──────────────────┼───────────────────────────────┤
│ • Dashboard      │ API Routers:                  │
│ • Quests         │ • /api/auth (register/login)  │
│ • Adaptive       │ • /api/player (profile/stats) │
│ • Analytics      │ • /api/quests (CRUD/complete)  │
│ • Inventory      │ • /api/adaptive (AI quests)   │
│ • Shop           │ • /api/analytics (charts)     │
│ • Login/Register │ • /api/ai (quest generation)  │
│                  │ • /api/coach (AI coaching)     │
│ Components:      │ • /api/domains (6 domains)    │
│ • QuestCard      │ • /api/verification (trust)   │
│ • QuestTimer     │ • /api/admin (management)     │
│ • SpotCheck      │                               │
│ • TrustProfile   │ Services (22):                │
│ • Charts         │ • Quest Generator             │
│                  │ • Adaptive Quest Engine        │
│                  │ • Difficulty Engine            │
│                  │ • Verification Engine          │
│                  │ • Penalty Engine               │
│                  │ • Mindset Engine               │
│                  │ • Progression Service          │
│                  │ • Abuse Detection              │
│                  │ • AI Service (Groq LLM)        │
│                  │ • Lockout Service              │
│                  │ • Daily Reset Service           │
│                  │ • Quest Expiry Scheduler        │
├──────────────────┴───────────────────────────────┤
│              PostgreSQL (Render)                  │
│              26 Models / Tables                   │
└──────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **FastAPI** | Async Python REST API |
| **SQLAlchemy 2.0** | ORM (SQLite dev / PostgreSQL prod) |
| **Pydantic v2** | Request/response validation |
| **PyJWT** | JWT authentication (access + refresh tokens) |
| **bcrypt** | Password hashing |
| **Gunicorn + Uvicorn** | Production ASGI server |
| **Groq SDK** | AI quest generation & coaching (optional) |

### Frontend
| Technology | Purpose |
|---|---|
| **React 18** | UI with lazy-loaded pages |
| **React Router 6** | Client-side SPA routing |
| **Vite 5** | Build tool + HMR |
| **Tailwind CSS 3** | Utility-first styling |
| **Axios** | HTTP client with interceptors |
| **Recharts** | Data visualization charts |
| **Lucide React** | Icon library |

### Design
- **Solo Leveling dark cyber aesthetic** — Orbitron font, cyan/red accents, scanline effects
- **Mobile-first responsive layout** — bottom nav on phones, sidebar on desktop
- **44px minimum touch targets** with safe-area-inset support
- **`prefers-reduced-motion`** respected for accessibility

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **npm**

### 1. Clone

```bash
git clone https://github.com/ishwarsoni/flow-system.git
cd FLOW
```

### 2. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\Activate.ps1
# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env — set SECRET_KEY (min 32 chars) and DATABASE_URL

# Run the server
python -m uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies /api → localhost:8000)
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## ☁️ Deploy to Render (Free Tier)

FLOW uses a **single-service deployment** — the backend builds and serves the frontend. No separate static site needed.

### Step 1: Create PostgreSQL Database
1. Go to [Render Dashboard](https://dashboard.render.com) → **+ New** → **PostgreSQL**
2. **Name:** `flow-db`, **Database:** `flow_db`, **User:** `flow_user`
3. **Plan:** Free → **Create Database**
4. Copy the **Internal Database URL** (starts with `postgresql://...`)

### Step 2: Create Web Service
1. **+ New** → **Web Service** → Connect your GitHub repo
2. Configure:

| Setting | Value |
|---|---|
| **Name** | `flow` |
| **Runtime** | Python |
| **Root Directory** | *(leave empty)* |
| **Build Command** | `cd frontend && npm install && npm run build && cd ../backend && pip install -r requirements.txt` |
| **Start Command** | `cd backend && gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120` |

### Step 3: Set Environment Variables

| Variable | Value |
|---|---|
| `DATABASE_URL` | Your PostgreSQL Internal Database URL from Step 1 |
| `SECRET_KEY` | Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DEBUG` | `False` |
| `PYTHON_VERSION` | `3.11.6` |
| `NODE_VERSION` | `20.11.0` |
| `ALLOWED_ORIGINS` | `["https://your-app.onrender.com","https://your-domain.com"]` |
| `GROQ_API_KEY` | *(optional)* Your Groq API key for AI features |
| `REDIS_URL` | *(optional)* Redis URL for token blacklist |

### Step 4: Add Custom Domain (Optional)
1. **Backend service** → **Settings** → **Custom Domains** → Add `your-domain.com`
2. Update DNS records as shown by Render

> ⚠️ **Important:** Render free PostgreSQL expires after **90 days**. Back up your data before expiry:
> ```bash
> pg_dump "YOUR_EXTERNAL_DB_URL" > backup.sql
> ```
> Create a new database and restore: `psql "NEW_DB_URL" < backup.sql`

---

## 🔑 Security Features

- **JWT Authentication** with access tokens (60 min) + refresh tokens (7 days)
- **bcrypt Password Hashing** (never stored in plain text)
- **Account Lockout** — 10 failed attempts → progressive lockout (15 min → 24 hours)
- **Rate Limiting** — 5 login/min, 3 register/min, 120 API calls/min per IP
- **CORS Protection** — explicit allowed origins only
- **CSP Headers** — Content Security Policy with dynamic `connect-src`
- **HSTS** — Strict Transport Security with preload
- **Request Body Limits** — 1MB max request size
- **Token Blacklist** — Redis-backed (or in-memory fallback)
- **Slow Request Logging** — Requests >2s are logged
- **SQLite Block in Production** — App crashes at startup if SQLite is used with `DEBUG=False`

---

## 📡 API Endpoints

### Authentication
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Register a new hunter |
| POST | `/api/auth/login` | Login → JWT tokens |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/logout` | Logout (blacklist token) |
| GET | `/api/auth/me` | Get current user |

### Player
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/player/profile` | Full player profile (stats, rank, rival) |
| GET | `/api/player/stats` | Player stats breakdown |
| POST | `/api/player/allocate-stats` | Allocate stat points |

### Quests
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/quests` | List quests (filterable by status/domain) |
| POST | `/api/quests` | Create a manual quest |
| POST | `/api/quests/generate` | AI-generate a quest |
| POST | `/api/quests/{id}/accept` | Accept a quest |
| POST | `/api/quests/{id}/complete` | Complete a quest |
| POST | `/api/quests/{id}/fail` | Fail a quest |

### Adaptive Quests
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/adaptive/daily` | Get daily adaptive quests |
| GET | `/api/adaptive/difficulty-profile` | View difficulty profile |

### Verification
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/verification/{id}/submit` | Submit quest verification |
| GET | `/api/verification/{id}/status` | Check verification status |

### Analytics
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/analytics/overview` | 7-day analytics overview |
| GET | `/api/analytics/stats` | Detailed stat analysis |

### Other
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/domains` | List all 6 power domains |
| POST | `/api/coach/session` | AI coaching session |
| GET | `/api/inventory` | Player inventory |
| GET | `/api/shop/items` | Shop item catalog |
| GET | `/health` | Deep health check (DB + Redis) |

---

## 📁 Project Structure

```
FLOW/
├── render.yaml              # Render deployment blueprint
├── README.md
│
├── backend/
│   ├── requirements.txt     # Python dependencies
│   ├── .env                 # Local environment variables (not in git)
│   ├── app/
│   │   ├── main.py          # FastAPI app + middleware + SPA serving
│   │   ├── config.py        # Pydantic settings + production guards
│   │   ├── core/
│   │   │   ├── security.py  # JWT + password hashing
│   │   │   ├── startup.py   # DB init + seeding
│   │   │   └── token_blacklist.py  # Redis/memory token store
│   │   ├── db/
│   │   │   ├── database.py  # SQLAlchemy engine + session
│   │   │   └── seed.py      # Seed domains + quest templates
│   │   ├── models/          # 26 SQLAlchemy models
│   │   │   ├── user.py, quest.py, rank.py, domain.py
│   │   │   ├── user_stats.py, quest_template.py, quest_session.py
│   │   │   ├── verification_log.py, player_trust.py, audit_flag.py
│   │   │   ├── difficulty_profile.py, mindset_score.py
│   │   │   ├── penalty_tier.py, progression_tier.py
│   │   │   ├── inventory.py, game_config.py
│   │   │   └── ... (26 total)
│   │   ├── routers/         # 12 API routers
│   │   │   ├── auth.py, player.py, quests.py
│   │   │   ├── adaptive_quests.py, verification.py
│   │   │   ├── analytics.py, ai.py, coach.py
│   │   │   ├── domains.py, inventory.py, shop.py
│   │   │   └── admin.py (internal management)
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   └── services/        # 22 business logic services
│   │       ├── quest_generator.py        # Quest creation engine
│   │       ├── adaptive_quest_service.py # Adaptive difficulty
│   │       ├── difficulty_engine.py      # Per-domain difficulty
│   │       ├── verification_engine.py    # Quest verification
│   │       ├── penalty_engine.py         # Streak penalties
│   │       ├── mindset_engine.py         # Player mindset scoring
│   │       ├── progression_service.py    # Leveling + rank ups
│   │       ├── abuse_detection_service.py # Anti-cheat
│   │       ├── ai_service.py             # Groq LLM integration
│   │       ├── lockout_service.py        # Account lockout
│   │       ├── daily_reset_service.py    # Daily reset logic
│   │       └── quest_expiry_scheduler.py # Background auto-fail
│
└── frontend/
    ├── package.json
    ├── vite.config.js       # Vite config with API proxy
    ├── tailwind.config.js   # Tailwind theme (Solo Leveling colors)
    └── src/
        ├── main.jsx         # React entry point
        ├── App.jsx          # Router + lazy loading
        ├── index.css        # Global styles (mobile-first)
        ├── api/
        │   └── client.js    # Axios instance + token interceptors
        ├── auth/
        │   └── AuthContext.jsx  # Auth state + session restore
        ├── pages/
        │   ├── DashboardPage.jsx      # Status window, stats, rival
        │   ├── QuestsPage.jsx         # Quest list + management
        │   ├── AdaptiveQuestsPage.jsx # AI-driven quest page
        │   ├── AnalyticsPage.jsx      # Charts + performance data
        │   ├── InventoryPage.jsx      # Player inventory
        │   ├── ShopPage.jsx           # In-game shop
        │   ├── LoginPage.jsx          # Hunter authentication
        │   └── RegisterPage.jsx       # New hunter registration
        └── components/
            ├── Layout.jsx            # Sidebar + bottom nav
            ├── QuestCard.jsx         # Quest display card
            ├── QuestTimer.jsx        # Countdown timer
            ├── ActiveQuestPanel.jsx  # Active quest tracker
            ├── GenerateQuestPanel.jsx # AI quest generator UI
            ├── ManualQuestForm.jsx   # Custom quest form
            ├── SpotCheckModal.jsx    # Verification modal
            ├── TrustProfileCard.jsx  # Player trust display
            ├── VerificationBadge.jsx # Trust badge component
            ├── ProfileCard.jsx       # Player profile card
            ├── StreakDisplay.jsx      # Streak counter
            ├── ErrorBoundary.jsx     # React error boundary
            └── charts/              # Recharts components
```

---

## 🎨 Database Models (26 Tables)

| Model | Purpose |
|---|---|
| `User` | Hunter accounts (email, hashed password) |
| `UserStats` | STR, INT, VIT, CHA, MAN stats + level |
| `Quest` | Active/completed/failed quests |
| `QuestTemplate` | 96 pre-built quest templates |
| `QuestSession` | Quest attempt tracking |
| `QuestOutput` | Quest completion proof/output |
| `Domain` | 6 power domains (Mind, Body, etc.) |
| `Rank` | E through SSS rank definitions |
| `DifficultyProfile` | Per-domain difficulty tracking |
| `ProgressionTier` | Multi-phase progression rules |
| `DailyProgress` | Daily activity tracking |
| `XPHistory` | XP earning log |
| `VerificationLog` | Quest verification records |
| `PlayerTrust` | Trust score per player |
| `AuditFlag` | Suspicious activity flags |
| `AuditLog` | Complete audit trail |
| `MindsetScore` | Player mindset evaluation |
| `PenaltyTier` | Progressive penalty levels |
| `AdaptiveQuestSession` | Adaptive quest session data |
| `AICoachLog` | AI coaching session history |
| `Inventory` | Player item inventory |
| `GameConfig` | Dynamic game configuration |
| `UserCustomQuest` | User-created quest definitions |
| `LoginAttempt` | Failed login tracking (lockout) |
| `Goal` | Player goals |

---

## ⚙️ Environment Variables

### Required
| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | Database connection string | `postgresql://user:pass@host/db` (prod) / `sqlite:///./flow.db` (dev) |
| `SECRET_KEY` | JWT signing key (≥32 chars) | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |

### Optional
| Variable | Default | Description |
|---|---|---|
| `DEBUG` | `False` | Enable debug mode (SQLite allowed, verbose logging) |
| `ALLOWED_ORIGINS` | Localhost URLs | CORS allowed origins (JSON array or comma-separated) |
| `GROQ_API_KEY` | `""` | Groq API key for AI quest generation & coaching |
| `REDIS_URL` | `""` | Redis URL for token blacklist (in-memory fallback) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | JWT refresh token lifetime |
| `LOCKOUT_THRESHOLD` | `10` | Failed login attempts before lockout |
| `LOGIN_RATE_LIMIT` | `5/minute` | Max login attempts per IP |
| `REGISTER_RATE_LIMIT` | `3/minute` | Max registrations per IP |

---

## 📄 License

Private project — all rights reserved.

---

<p align="center">
  <em>"I alone level up."</em> — Sung Jin-Woo
</p>
