# FLOW — Solo Leveling Productivity System

A gamified productivity app inspired by **Solo Leveling**, turning daily tasks into quests with RPG progression mechanics — XP, stat allocation, ranks, streaks, a shadow rival, and adaptive difficulty.

![Theme](https://img.shields.io/badge/theme-Solo%20Leveling-00d4ff?style=flat-square)
![Stack](https://img.shields.io/badge/stack-React%20%2B%20FastAPI-00ff88?style=flat-square)

---

## Features

| System | Description |
|---|---|
| **Quest Engine** | Generate quests across 6 domains (Mind, Body, Core, Control, Presence, System) with 4 difficulty tiers |
| **RPG Progression** | Level up, earn XP, allocate skill points to 5 stats (STR, INT, VIT, CHA, MAN) |
| **Rank System** | E → D → C → B → A → S → SS → SSS with rank-specific perks |
| **Shadow Rival** | An AI-paced rival that tracks your optimal pace and pushes you |
| **Adaptive Difficulty** | Quest difficulty adapts to your performance profile per domain |
| **Streak & Penalties** | HP/MP system with fatigue; miss days and face punishment quests |
| **Verification** | Metric-based quest verification (log, output, or metrics) |
| **Analytics** | 7-day performance charts, stat analysis, streak tracking |

## Tech Stack

### Backend
- **FastAPI** — async Python API
- **SQLAlchemy 2.0** — ORM with SQLite (dev) / PostgreSQL (prod)
- **Pydantic v2** — schema validation
- **PyJWT** — authentication
- **uvicorn** — ASGI server

### Frontend
- **React 18** — UI with lazy-loaded pages
- **React Router 6** — client-side routing
- **Vite 5** — build tool + HMR
- **Tailwind CSS 3** — utility classes
- **Axios** — HTTP client
- **Recharts** — data visualization

### Design
- Mobile-first responsive layout (bottom nav on phones, sidebar on desktop)
- Solo Leveling dark cyber aesthetic — Orbitron font, cyan accents, scanline effects
- 44px minimum touch targets, safe-area-inset support
- `prefers-reduced-motion` respected

---

## Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **npm**

### 1. Clone

```bash
git clone <repo-url>
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
# Edit .env with your SECRET_KEY and DATABASE_URL

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

Open **http://localhost:3000** in your browser.

---

## Deploy to Render (Free Tier)

### 1. Create PostgreSQL Database
- Go to [Render Dashboard](https://dashboard.render.com/) → **New** → **PostgreSQL**
- Plan: **Free**
- Note the **Internal Database URL** (starts with `postgresql://...`)

### 2. Create Web Service
- **New** → **Web Service** → Connect your GitHub repo
- **Root Directory**: `backend`
- **Runtime**: Python
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120`

### 3. Set Environment Variables
In the Render web service settings, add these env vars:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Your PostgreSQL Internal Database URL from step 1 |
| `SECRET_KEY` | Generate with: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DEBUG` | `False` |
| `ALLOWED_ORIGINS` | `https://your-frontend.vercel.app` (comma-separated if multiple) |
| `PYTHON_VERSION` | `3.11.6` |
| `GROQ_API_KEY` | *(optional)* Your Groq API key for AI features |
| `REDIS_URL` | *(optional)* Redis URL if you have one (e.g. Upstash) |

### 4. Deploy Frontend (Vercel)
```bash
cd frontend
npm run build
# Deploy dist/ folder to Vercel
```
In Vercel, set: `VITE_API_BASE_URL` = `https://your-backend.onrender.com/api`

### Or use the Blueprint
Push code to GitHub and use `render.yaml` at the repo root for one-click deploy:
```
https://render.com/deploy?repo=<your-github-repo-url>
```

---

## Environment Variables

Create `backend/.env`:

```env
DATABASE_URL=sqlite:///./flow.db
SECRET_KEY=<your-secret-key-at-least-32-chars>
```

---

## Project Structure

```
FLOW/
├── backend/
│   ├── main.py              # Legacy entry point (uvicorn target)
│   ├── requirements.txt
│   ├── .env
│   ├── app/
│   │   ├── main.py          # FastAPI app factory
│   │   ├── config.py        # Pydantic settings
│   │   ├── core/            # Security, startup, exceptions
│   │   ├── db/              # Database engine & session
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── routers/         # API route handlers
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   └── services/        # Business logic (quest generator, etc.)
│   └── tests/
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    └── src/
        ├── App.jsx           # Router + lazy loading
        ├── index.css         # Mobile-first global styles
        ├── api/              # Axios API client
        ├── auth/             # Auth context + hooks
        ├── components/       # Layout, QuestCard, etc.
        ├── hooks/            # Custom React hooks
        ├── pages/            # Dashboard, Quests, Analytics, etc.
        └── router/           # PrivateRoute guard
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Register a new hunter |
| POST | `/api/auth/login` | Login → JWT token |
| GET | `/api/player/profile` | Player stats & rank |
| GET | `/api/quests` | List quests (filterable) |
| POST | `/api/quests` | Create manual quest |
| POST | `/api/quests/{id}/complete` | Complete a quest |
| POST | `/api/quests/{id}/fail` | Fail a quest |
| GET | `/api/domains` | Available quest domains |
| GET | `/api/analytics/overview` | Player analytics |
| GET | `/api/adaptive/daily` | Adaptive quest generation |

---

## License

Private project — all rights reserved.
