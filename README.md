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
python -m uvicorn main:app --reload --port 8000
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
