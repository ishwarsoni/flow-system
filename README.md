# FLOW — Gamified Productivity System

**Live:** [flow-rpg.tech](https://flow-rpg.tech)

React · FastAPI · PostgreSQL · Groq LLM · Deployed on Render

---

## The Problem

Most productivity apps treat tasks as checkboxes. There's no consequence for skipping a day, no reward for consistency, and no adaptation to how you actually perform. Users start strong and abandon them within weeks because the system doesn't push back.

FLOW is an RPG-style productivity engine that treats every task as a quest with real stakes — XP, stat progression, penalties for failure, adaptive difficulty scaling, and a verification layer that prevents users from gaming their own system.

---

## System Architecture

```
React SPA (Vite)  ──→  FastAPI (async)  ──→  PostgreSQL
     │                      │
     │                 22 services
     │                 12 API routers
     │                 26 database models
     │                      │
     └── Axios + JWT ───────┘
              │
         Groq LLM (optional)
```

The backend is structured as a service layer — routers are thin, business logic lives in dedicated engines. Each engine (difficulty, verification, penalty, progression, abuse detection) operates independently and is composed at the router level.

**Key services:** Quest Generator, Adaptive Difficulty Engine, Verification Engine, Penalty Engine, Abuse Detection, Progression Service, AI Coach, Daily Reset Scheduler.

---

## What Makes This Non-Trivial

### Adaptive Difficulty Engine
Each of the six domains (Mind, Body, Core, Control, Presence, System) maintains an independent difficulty profile. The engine tracks success/failure rates per domain and adjusts quest difficulty accordingly — harder when you're coasting, easier when you're struggling. Periodic push events force users beyond their comfort zone by temporarily raising the difficulty ceiling.

### Quest Generation Pipeline
96 quest templates seeded across 6 domains × 4 difficulty tiers. The generator enforces five uniqueness rules: no duplicate active templates, one quest per domain per day, 48-hour template cooldown, level-gated difficulty access, and auto-cleanup of stale duplicates. All system quests originate from templates — no direct inserts allowed.

### Verification & Trust Scoring
Quests aren't just completed — they're verified. Three verification types (log, metrics, output) map to difficulty tiers. Hard and Extreme quests require quantifiable proof. A trust score tracks player integrity over time, and random spot-check prompts prevent passive completion. The abuse detection service flags speed runs, suspicious timestamp patterns, and stat anomalies.

### 24-Hour Quest Lifecycle
Every quest has a hard 24-hour deadline. A background async scheduler runs every 30 minutes to auto-fail stale quests across all users and apply XP/HP penalties. A lazy evaluation layer does the same per-user when they open the app, ensuring consistency even if the scheduler is delayed. Completed and failed quests are auto-purged after 24 hours — only the XP audit trail survives.

### Penalty & Consequence System
Failure isn't cosmetic. Failed quests deduct XP, drain HP, and can trigger mandatory penalty quests. Broken streaks reset progress. Progressive penalty tiers escalate consequences for repeated inactivity. HP drops to critical levels force conservative play. The system makes skipping feel expensive.

---

## Key Engineering Decisions

| Decision | Why |
|---|---|
| **Service layer, not fat routers** | 22 services keep business logic testable and composable. Routers only handle HTTP concerns. |
| **Template-based quest generation** | Prevents empty/invalid quests. Every system quest traces back to a vetted template with enforced constraints. |
| **Dual cleanup strategy (scheduler + lazy)** | Background scheduler handles bulk expiry; lazy per-user cleanup on API call ensures real-time consistency. Neither alone is sufficient. |
| **SQLite dev / PostgreSQL prod** | Fast local iteration without Docker. Production guard crashes the app at startup if SQLite leaks into prod. |
| **Groq LLM as optional layer** | AI coaching and quest analysis degrade gracefully to rule-based engines when no API key is configured. |
| **JWT with Redis-backed blacklist** | Stateless auth with revocation support. Falls back to in-memory set when Redis is unavailable. |
| **Mobile-first with 44px touch targets** | Built for actual daily use on phones, not just desktop demos. Safe-area-inset support for notched devices. |

---

## Tech Stack

**Backend:** FastAPI, SQLAlchemy 2.0, Pydantic v2, PyJWT, bcrypt, Gunicorn + Uvicorn, Groq SDK

**Frontend:** React 18, React Router 6, Vite 5, Tailwind CSS 3, Axios, Recharts

**Infra:** PostgreSQL (Render), Redis (optional), single-service deployment (backend serves built frontend)

---

## Lessons Learned

1. **Auto-expiry needs two layers.** A background scheduler alone misses edge cases when the process restarts. Lazy evaluation on API calls alone means stale data sits until the user returns. Both together cover all scenarios.

2. **Uniqueness rules compound.** Five generation rules (no duplicate template, one per domain, 48h cooldown, level gate, auto-cleanup) interact in non-obvious ways. Each rule was added to fix a specific duplication bug discovered during testing.

3. **Trust systems need thresholds, not binaries.** Early versions had pass/fail verification. Adding a continuous trust score with spot-check probabilities made the system feel fair without being punitive.

4. **Penalties have to hurt, but not kill.** HP floors at 1 (never zero) and XP floors at 0 prevent death spirals where a bad week makes recovery impossible. The goal is pressure, not despair.

5. **AI features must degrade gracefully.** Groq LLM enriches the experience but the entire system works without it. This was a deliberate architectural choice — external dependencies should enhance, never gate core functionality.

---

## Quick Start

```bash
# Clone
git clone https://github.com/ishwarsoni/flow-system.git && cd FLOW

# Backend
cd backend && python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # Set SECRET_KEY and DATABASE_URL
python -m uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173**. API docs at **http://localhost:8000/docs**.

---

## Deployment

Single-service deploy on Render — the backend builds and serves the frontend static bundle. No separate hosting needed.

**Build:** `cd frontend && npm install && npm run build && cd ../backend && pip install -r requirements.txt`

**Start:** `cd backend && gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`

Required env vars: `DATABASE_URL`, `SECRET_KEY`. Optional: `GROQ_API_KEY`, `REDIS_URL`, `ALLOWED_ORIGINS`.

---

<p align="center">
  <em>"I alone level up."</em>
</p>
