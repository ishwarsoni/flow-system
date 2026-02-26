"""AI Task Generation Service — Solo Leveling Style.

Decomposes real-world goals into structured quest chains with XP values,
stat bonuses, and difficulty progressions. Uses built-in rule engine by
default; upgrades to OpenAI GPT if OPENAI_API_KEY is configured.
"""

from __future__ import annotations

import re
import json
import math
from typing import Any
from dataclasses import dataclass, field


# ══════════════════════════════════════════════════════════════════════
# Data model for generated tasks
# ══════════════════════════════════════════════════════════════════════

@dataclass
class GeneratedTask:
    title: str
    description: str
    difficulty: str          # easy | medium | hard | extreme
    primary_stat: str        # strength | intelligence | vitality | charisma | mana
    base_xp_reward: int
    skill_points: int        # awarded to player on completion
    time_limit_minutes: int | None
    week: int                # which week in the progression plan
    day_suggestion: str      # e.g. "Daily", "Mon/Wed/Fri", "Weekend"
    rationale: str           # why this task matters


@dataclass
class GoalAnalysis:
    goal_text: str
    category: str
    subcategory: str
    difficulty_level: str    # beginner | intermediate | advanced
    estimated_weeks: int
    primary_stat: str
    secondary_stat: str
    system_message: str      # Solo Leveling flavor text
    tasks: list[GeneratedTask] = field(default_factory=list)
    xp_summary: dict[str, Any] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════
# Category detection
# ══════════════════════════════════════════════════════════════════════

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "fitness": [
        "workout", "gym", "run", "exercise", "pushup", "pull-up", "squat", "deadlift",
        "bench", "cardio", "hiit", "yoga", "muscle", "weight loss", "bulk", "cut",
        "marathon", "cycling", "swim", "athletic", "body", "physique", "strength training",
        "lose weight", "gain weight", "abs", "core", "flexibility", "endurance",
    ],
    "study": [
        "study", "learn", "course", "degree", "exam", "book", "read", "chapter",
        "math", "science", "history", "programming", "coding", "python", "javascript",
        "algorithm", "data structure", "machine learning", "ai", "university",
        "college", "certification", "skill", "language", "master", "gre", "sat",
        "competitive exam", "upsc", "jee", "neet", "gate",
    ],
    "career": [
        "job", "career", "promotion", "interview", "resume", "portfolio", "project",
        "startup", "business", "freelance", "salary", "network", "linkedin",
        "internship", "application", "hire", "work", "professional", "leadership",
        "management", "entrepreneur", "pitch", "client",
    ],
    "finance": [
        "money", "invest", "saving", "budget", "financial", "stock", "crypto",
        "mutual fund", "debt", "loan", "income", "passive income", "emergency fund",
        "net worth", "rich", "wealth", "tax", "sip", "index fund",
    ],
    "mindset": [
        "discipline", "habit", "meditation", "mindfulness", "focus", "productivity",
        "procrastination", "confidence", "self-improvement", "mental", "anxiety",
        "depression", "stress", "journal", "morning routine", "discipline", "wakeup",
        "sleep", "no-fad", "dopamine detox", "motivation", "mindset",
    ],
    "social": [
        "friend", "social", "relationship", "communication", "public speaking",
        "presentation", "network", "meet", "dating", "family", "conversation",
        "charisma", "influence", "persuasion", "empathy",
    ],
    "creativity": [
        "write", "art", "music", "draw", "paint", "design", "creative", "story",
        "novel", "blog", "youtube", "content", "photography", "video", "game",
        "compose", "sing", "dance", "comedy", "podcast",
    ],
    "health": [
        "diet", "nutrition", "calories", "protein", "water", "sleep", "health",
        "doctor", "medical", "blood pressure", "sugar", "vitamin", "supplement",
        "quit smoking", "alcohol", "addiction", "sober",
    ],
}

STAT_FOR_CATEGORY: dict[str, tuple[str, str]] = {
    "fitness":    ("vitality",      "strength"),
    "study":      ("intelligence",  "mana"),
    "career":     ("intelligence",  "charisma"),
    "finance":    ("intelligence",  "charisma"),
    "mindset":    ("mana",          "strength"),
    "social":     ("charisma",      "mana"),
    "creativity": ("mana",          "intelligence"),
    "health":     ("vitality",      "mana"),
}

SYSTEM_MESSAGES: dict[str, str] = {
    "fitness": "[ SYSTEM ] Physical awakening initiated. Your body is your first dungeon. Break the limit.",
    "study":   "[ SYSTEM ] Knowledge is the blade every Hunter must sharpen. Begin your ascension.",
    "career":  "[ SYSTEM ] The world rewards those who level up. Forge your legacy, Hunter.",
    "finance": "[ SYSTEM ] True power includes sovereignty over resources. Build your treasury.",
    "mindset": "[ SYSTEM ] The mind is the gateway to all dungeons. Discipline is your S-rank skill.",
    "social":  "[ SYSTEM ] Every great Hunter builds a raid party. Strengthen your bonds.",
    "creativity":"[ SYSTEM ] Creation is the highest form of mana. Channel your inner architect.",
    "health":  "[ SYSTEM ] Without a healthy vessel your journey ends here. Restore your HP.",
}

# ══════════════════════════════════════════════════════════════════════
# Solo Leveling quest rewrite templates (rule-engine)
# ══════════════════════════════════════════════════════════════════════

SL_TITLE_PREFIXES: dict[str, list[str]] = {
    "fitness":    ["[ IRON BODY TRIAL ]", "[ PHYSICAL AWAKENING ]", "[ STRENGTH PROTOCOL ]", "[ ENDURANCE GATE ]"],
    "study":      ["[ KNOWLEDGE DUNGEON ]", "[ MENTAL ASCENSION ]", "[ SCHOLAR'S TRIAL ]", "[ WISDOM GATE ]"],
    "career":     ["[ HUNTER'S LEGACY ]", "[ RANK ADVANCEMENT ]", "[ GUILD MISSION ]", "[ CAREER DUNGEON ]"],
    "finance":    ["[ TREASURY RAID ]", "[ WEALTH PROTOCOL ]", "[ RESOURCE DUNGEON ]", "[ COIN DOMINION ]"],
    "mindset":    ["[ DISCIPLINE TRIAL ]", "[ MENTAL FORTRESS ]", "[ SHADOW PROTOCOL ]", "[ WILL DUNGEON ]"],
    "social":     ["[ CHARISMA GATE ]", "[ RAID PARTY TRIAL ]", "[ BOND DUNGEON ]", "[ INFLUENCE PROTOCOL ]"],
    "creativity": ["[ MANA CREATION ]", "[ ARCHITECT'S TRIAL ]", "[ CREATION GATE ]", "[ MANA FORGE ]"],
    "health":     ["[ HP RESTORATION ]", "[ VITALITY DUNGEON ]", "[ VESSEL PROTOCOL ]", "[ LIFE GATE ]"],
}

SL_RATIONALE_TEMPLATES: dict[str, list[str]] = {
    "fitness": [
        "[ SYSTEM ] Foundation Protocol initiated. Your body is an E-Rank dungeon. Begin the clearing.",
        "[ SYSTEM ] Physical ceiling detected. Repetition is the key that breaks the gate.",
        "[ SYSTEM ] Progressive overload is the law of dungeons. Each rep is a floor cleared.",
        "[ SYSTEM ] Endurance trial in progress. True hunters do not rest until the gate closes.",
    ],
    "study": [
        "[ SYSTEM ] Knowledge accumulation phase active. Each chapter is a floor. Ascend.",
        "[ SYSTEM ] Memory consolidation required. The System rewards those who review what they conquer.",
        "[ SYSTEM ] Deep work session initiated. Focus is the mana of the intellectual hunter.",
        "[ SYSTEM ] Error analysis unlocks the hidden path. Study your failures as closely as your victories.",
    ],
    "career": [
        "[ SYSTEM ] Guild rank advancement requires demonstrated skill. Build the portfolio. Prove the power.",
        "[ SYSTEM ] Networking is dungeon scouting. Every contact is a key to a gate.",
        "[ SYSTEM ] Skills are weapons. Sharpen them or be outranked. The System is watching.",
        "[ SYSTEM ] Interview gauntlet detected ahead. Preparation determines survival rate.",
    ],
    "finance": [
        "[ SYSTEM ] Resource management is the mark of an S-Rank hunter. Know your numbers.",
        "[ SYSTEM ] Treasury gates cannot be breached without a map. Build your budget.",
        "[ SYSTEM ] Wealth dungeons favor patience. The System rewards compound effort.",
        "[ SYSTEM ] Financial dungeon break imminent. Emergency fund is your dungeon shield.",
    ],
    "mindset": [
        "[ SYSTEM ] Discipline is not a trait. It is a skill forged in repetition. Begin forging.",
        "[ SYSTEM ] Mental dungeon detected. Focus is the primary stat in this gate.",
        "[ SYSTEM ] Identity rewrite in progress. The System recognizes only who you are today.",
        "[ SYSTEM ] Comfort zone boss identified. Avoidance is how hunters remain E-Rank forever.",
    ],
    "social": [
        "[ SYSTEM ] Raid party construction required. Solo hunters have a level ceiling. Build your guild.",
        "[ SYSTEM ] Charisma is the stat most hunters neglect. The System rewards those who invest.",
        "[ SYSTEM ] Communication dungeon detected. Every conversation is a floor to clear.",
        "[ SYSTEM ] Influence protocol active. Genuine connection is the rarest drop in the game.",
    ],
    "creativity": [
        "[ SYSTEM ] Mana creation cycle initiated. Consume less. Forge more. That is the law.",
        "[ SYSTEM ] Creative dungeon unlocked. Completion beats perfection — always finish the floor.",
        "[ SYSTEM ] Public release detected as final boss. Most creators fail here. Do not.",
        "[ SYSTEM ] Mana reserves depleted by passive consumption. Creation restores the flow.",
    ],
    "health": [
        "[ SYSTEM ] HP regeneration protocol active. Your vessel is the only gear you cannot replace.",
        "[ SYSTEM ] Vitality dungeon cleared through consistency, not intensity. Show up daily.",
        "[ SYSTEM ] Nutrition is equipment maintenance. Neglect it and watch your stats decay.",
        "[ SYSTEM ] Sleep is the most powerful recovery skill in existence. Equip it every night.",
    ],
}


# ══════════════════════════════════════════════════════════════════════
# XP calculation engine
# ══════════════════════════════════════════════════════════════════════

DIFFICULTY_XP: dict[str, int] = {
    "easy": 40,
    "medium": 100,
    "hard": 200,
    "extreme": 350,
}
# Skill points awarded per quest difficulty (spent on STATUS page to upgrade stats)
DIFFICULTY_SP: dict[str, int] = {
    "trivial": 1,
    "easy": 1,
    "medium": 2,
    "hard": 3,
    "extreme": 5,
}


def calculate_xp(
    difficulty: str,
    duration_minutes: int,
    is_streak_task: bool = False,
    is_habit_building: bool = False,
) -> int:
    base = DIFFICULTY_XP.get(difficulty, 100)
    # Duration bonus: +1 XP per 5 minutes beyond 15
    duration_bonus = max(0, (duration_minutes - 15) // 5) * 1
    streak_bonus = int(base * 0.1) if is_streak_task else 0
    habit_bonus  = int(base * 0.15) if is_habit_building else 0
    return min(base + duration_bonus + streak_bonus + habit_bonus, 500)


# ══════════════════════════════════════════════════════════════════════
# Task template library
# ══════════════════════════════════════════════════════════════════════

TaskTemplate = dict[str, Any]

TASK_TEMPLATES: dict[str, list[TaskTemplate]] = {

    # ── FITNESS ──────────────────────────────────────────────────────
    "fitness": [
        {"week": 1, "title": "10-Minute Morning Activation", "description": "Do 10 minutes of light stretching + 10 pushups to awaken your body each morning. No excuses.", "difficulty": "easy", "primary_stat": "vitality", "duration": 15, "day": "Daily"},
        {"week": 1, "title": "30-Minute Walk / Jog", "description": "30-minute brisk walk or easy jog. Focus on form and breathing. Track distance.", "difficulty": "easy", "primary_stat": "vitality", "duration": 35, "day": "Daily"},
        {"week": 2, "title": "Bodyweight Strength Circuit", "description": "3 rounds: 15 pushups, 15 squats, 10 lunges each leg, 30s plank. Rest 60s between rounds.", "difficulty": "medium", "primary_stat": "strength", "duration": 30, "day": "Mon/Wed/Fri"},
        {"week": 2, "title": "5K Run Target", "description": "Run 3km without stopping. Focus on consistent pace, not speed. Record your time.", "difficulty": "medium", "primary_stat": "vitality", "duration": 25, "day": "Tue/Thu"},
        {"week": 3, "title": "Progressive Overload Training", "description": "Add 2 reps to each exercise from last week. Track every set and rep in a notebook.", "difficulty": "medium", "primary_stat": "strength", "duration": 45, "day": "Mon/Wed/Fri"},
        {"week": 3, "title": "Active Recovery Day", "description": "15 minutes yoga or stretching + 20 min walk. Feed the recovery as hard as the grind.", "difficulty": "easy", "primary_stat": "vitality", "duration": 35, "day": "Tue/Thu"},
        {"week": 4, "title": "Power Hour Training", "description": "60-minute full-body workout: compound lifts or advanced bodyweight. No phone during workout.", "difficulty": "hard", "primary_stat": "strength", "duration": 65, "day": "Mon/Wed/Fri"},
        {"week": 4, "title": "5K Personal Record Attempt", "description": "Run 5K and beat your last time. This is your BOSS RAID. Give everything.", "difficulty": "extreme", "primary_stat": "vitality", "duration": 40, "day": "Sunday"},
    ],

    # ── STUDY ─────────────────────────────────────────────────────────
    "study": [
        {"week": 1, "title": "Build Your Study Command Center", "description": "Set up a distraction-free study space. Phone in another room. Pomodoro timer ready. Study for 25 minutes uninterrupted.", "difficulty": "easy", "primary_stat": "intelligence", "duration": 30, "day": "Daily"},
        {"week": 1, "title": "Active Recall Session", "description": "After each study block, close the book and write everything you remember. Do NOT re-read passively.", "difficulty": "easy", "primary_stat": "intelligence", "duration": 25, "day": "Daily"},
        {"week": 2, "title": "Spaced Repetition Practice", "description": "Create Anki flashcards for the past week's material. Review 20 cards minimum. Build the habit.", "difficulty": "medium", "primary_stat": "intelligence", "duration": 30, "day": "Daily"},
        {"week": 2, "title": "Deep Work Block (2 Hours)", "description": "2 uninterrupted hours on the hardest topic. No music, notifications, or breaks. Full cognitive load.", "difficulty": "medium", "primary_stat": "intelligence", "duration": 125, "day": "Daily"},
        {"week": 3, "title": "Teach-It-Back Exercise", "description": "Explain today's topic out loud as if teaching a 10-year-old. Record yourself. Watch it back.", "difficulty": "medium", "primary_stat": "intelligence", "duration": 30, "day": "Daily"},
        {"week": 3, "title": "Practice Problem Sprint", "description": "Solve 10 practice problems from your weakest area. No looking at solutions first. Struggle is the lesson.", "difficulty": "hard", "primary_stat": "intelligence", "duration": 60, "day": "Daily"},
        {"week": 4, "title": "Mock Exam / Full Test", "description": "Take a full timed mock exam under real conditions. Grade yourself honestly. Analyze every mistake.", "difficulty": "hard", "primary_stat": "intelligence", "duration": 120, "day": "Weekend"},
        {"week": 4, "title": "Error Analysis Boss Battle", "description": "For every wrong answer, write the correct concept 3 times and solve a similar problem correctly. ZERO tolerance for pattern blindness.", "difficulty": "extreme", "primary_stat": "intelligence", "duration": 90, "day": "Weekend"},
    ],

    # ── CAREER ────────────────────────────────────────────────────────
    "career": [
        {"week": 1, "title": "Audit Your Current Position", "description": "Write down: your top 5 skills, 3 weaknesses, and the exact role/title you want in 12 months. Be brutally honest.", "difficulty": "easy", "primary_stat": "intelligence", "duration": 30, "day": "Day 1"},
        {"week": 1, "title": "LinkedIn Profile Overhaul", "description": "Rewrite your LinkedIn headline and summary. Add a strong photo. Request 2 recommendations this week.", "difficulty": "easy", "primary_stat": "charisma", "duration": 60, "day": "Day 2-3"},
        {"week": 2, "title": "Build 1 Portfolio Project", "description": "Start (or finish) one project that demonstrates your target skill. Document it clearly on GitHub/Behance.", "difficulty": "medium", "primary_stat": "intelligence", "duration": 90, "day": "Daily"},
        {"week": 2, "title": "Cold Outreach — 5 Contacts", "description": "Send 5 genuine, personalized messages to people in your target field. Ask for 15-minute calls, not jobs.", "difficulty": "medium", "primary_stat": "charisma", "duration": 45, "day": "Mon/Wed/Fri"},
        {"week": 3, "title": "Interview Prep Gauntlet", "description": "Answer 10 behavioral interview questions using STAR method. Record video. Watch yourself. Improve.", "difficulty": "hard", "primary_stat": "charisma", "duration": 60, "day": "Daily"},
        {"week": 3, "title": "Apply to 3 Dream Roles", "description": "Research, tailor, and submit 3 job applications. Each application must have a custom cover letter.", "difficulty": "hard", "primary_stat": "intelligence", "duration": 90, "day": "Mon/Wed/Fri"},
        {"week": 4, "title": "Mock Interview with a Human", "description": "Do a real mock interview — with a friend, mentor, or paid service. Get brutal feedback. Implement it.", "difficulty": "extreme", "primary_stat": "charisma", "duration": 60, "day": "Weekend"},
        {"week": 4, "title": "Skill Demonstration Project", "description": "Create a public-facing demonstration of your core skill. Post it. Share it. The world must know you exist.", "difficulty": "hard", "primary_stat": "intelligence", "duration": 120, "day": "Weekend"},
    ],

    # ── FINANCE ───────────────────────────────────────────────────────
    "finance": [
        {"week": 1, "title": "Financial Audit — Know Your Numbers", "description": "List every income source, every recurring expense, and your current net worth. No guesses — real numbers.", "difficulty": "easy", "primary_stat": "intelligence", "duration": 45, "day": "Day 1"},
        {"week": 1, "title": "Build the 50/30/20 Budget", "description": "Allocate: 50% needs, 30% wants, 20% savings/investments. Set up automatic transfers today.", "difficulty": "easy", "primary_stat": "intelligence", "duration": 30, "day": "Day 2"},
        {"week": 2, "title": "Eliminate 1 Luxury Expense", "description": "Identify one non-essential subscription or habit costing ₹500+/month. Cancel or reduce it. Redirect the money.", "difficulty": "medium", "primary_stat": "mana", "duration": 20, "day": "Day 8"},
        {"week": 2, "title": "Start Emergency Fund", "description": "Open a dedicated savings account. Transfer the first ₹1,000 automatically. Your first dungeon shield.", "difficulty": "medium", "primary_stat": "intelligence", "duration": 30, "day": "Day 10"},
        {"week": 3, "title": "Research Investment Options", "description": "Study 3 investment vehicles (index funds, PPF, SIP, US stocks). Compare fees, returns, and risk. Choose one.", "difficulty": "medium", "primary_stat": "intelligence", "duration": 60, "day": "Daily"},
        {"week": 3, "title": "Start Investing — ₹500 Minimum", "description": "Make your first actual investment, no matter how small. Time in market beats timing the market.", "difficulty": "hard", "primary_stat": "intelligence", "duration": 30, "day": "Day 18"},
        {"week": 4, "title": "Week 4 Financial Review", "description": "Compare actuals vs budget. Calculate: did you save the goal amount? What did you overspend on? Fix it.", "difficulty": "medium", "primary_stat": "intelligence", "duration": 45, "day": "Day 28"},
        {"week": 4, "title": "12-Month Wealth Plan", "description": "Write a specific 12-month financial goal with numbers. Break it down month by month. Print it. Post it.", "difficulty": "extreme", "primary_stat": "intelligence", "duration": 60, "day": "Day 30"},
    ],

    # ── MINDSET ───────────────────────────────────────────────────────
    "mindset": [
        {"week": 1, "title": "5AM Wake-Up Protocol", "description": "Set alarm for 5AM (or 1 hour earlier than usual). No snooze. Feet on floor in 5 seconds. Jocko rule.", "difficulty": "easy", "primary_stat": "mana", "duration": 5, "day": "Daily"},
        {"week": 1, "title": "10-Minute Mindfulness Sit", "description": "Sit in silence for 10 minutes each morning. Focus only on breath. Thoughts arise — let them pass. No phone.", "difficulty": "easy", "primary_stat": "mana", "duration": 12, "day": "Daily"},
        {"week": 2, "title": "Daily Reflection Journal", "description": "Write 3 things: what you achieved today, one failure and its lesson, and tomorrow's #1 priority. 5 minutes max.", "difficulty": "easy", "primary_stat": "mana", "duration": 8, "day": "Daily"},
        {"week": 2, "title": "Discomfort Challenge Week", "description": "Every day this week: do one thing you genuinely don't want to do. Cold shower, hard conversation, or difficult task first.", "difficulty": "medium", "primary_stat": "strength", "duration": 15, "day": "Daily"},
        {"week": 3, "title": "Deep Work Without Phone", "description": "Work for 90 minutes completely phone-free. Phone in another room. Build the ability to sustain focus under pressure.", "difficulty": "medium", "primary_stat": "mana", "duration": 95, "day": "Daily"},
        {"week": 3, "title": "Identity Statement — Rewrite Yourself", "description": "Write your new identity in present tense: 'I am someone who...' 10 statements. Read them every morning.", "difficulty": "medium", "primary_stat": "mana", "duration": 25, "day": "Day 15"},
        {"week": 4, "title": "30-Day Habit Track Review", "description": "Review your 30-day habit tracker. Identify your #1 pattern holding you back. Make one structural change.", "difficulty": "hard", "primary_stat": "mana", "duration": 30, "day": "Day 29"},
        {"week": 4, "title": "Comfort Zone Boss Raid", "description": "Do the one thing you've been avoiding most — the big scary task you keep postponing. Today it dies.", "difficulty": "extreme", "primary_stat": "strength", "duration": 60, "day": "Day 30"},
    ],

    # ── SOCIAL / RELATIONSHIPS ────────────────────────────────────────
    "social": [
        {"week": 1, "title": "Eye Contact & Presence Drill", "description": "During every conversation today, maintain eye contact 70% of the time. Speak 30% slower. Actually listen.", "difficulty": "easy", "primary_stat": "charisma", "duration": 20, "day": "Daily"},
        {"week": 1, "title": "Reconnect With 3 People", "description": "Send genuine messages to 3 people you've lost touch with. No agenda. Just: 'Thinking of you, how are you?'", "difficulty": "easy", "primary_stat": "charisma", "duration": 20, "day": "Day 2-3"},
        {"week": 2, "title": "Public Speaking Practice", "description": "Record yourself speaking for 3 minutes on any topic. Watch it back with brutal honesty. Redo until proud.", "difficulty": "medium", "primary_stat": "charisma", "duration": 20, "day": "Daily"},
        {"week": 2, "title": "Attend 1 Social Event / Networking Event", "description": "Go to a meetup, workshop, or gathering. Introduce yourself to 3 strangers. Get at least 1 contact.", "difficulty": "medium", "primary_stat": "charisma", "duration": 90, "day": "Weekend"},
        {"week": 3, "title": "Give Deep Value First", "description": "Help someone in your network with zero expectation of return. Share knowledge, make an introduction, give feedback.", "difficulty": "medium", "primary_stat": "charisma", "duration": 30, "day": "Daily"},
        {"week": 3, "title": "Difficult Conversation Practice", "description": "Have one uncomfortable conversation you've been avoiding. Address conflict or give honest feedback kindly.", "difficulty": "hard", "primary_stat": "charisma", "duration": 45, "day": "Day 20"},
        {"week": 4, "title": "5-Minute Talk — Any Room", "description": "Volunteer to speak for 5 minutes at any group setting. Team meeting, class, or toastmasters. Do it.", "difficulty": "extreme", "primary_stat": "charisma", "duration": 10, "day": "Week 4"},
        {"week": 4, "title": "Build Your 'Raid Party'", "description": "Identify 3 people who challenge and inspire you. Make a concrete plan to spend more time with them monthly.", "difficulty": "hard", "primary_stat": "charisma", "duration": 40, "day": "Day 28"},
    ],

    # ── CREATIVITY ────────────────────────────────────────────────────
    "creativity": [
        {"week": 1, "title": "Daily Creation Minimum", "description": "Create something every single day — 500 words, a sketch, a melody, or one design. Quality is not the goal. Momentum is.", "difficulty": "easy", "primary_stat": "mana", "duration": 30, "day": "Daily"},
        {"week": 1, "title": "Consume Less, Create More", "description": "Replace 30 minutes of passive content consumption with 30 minutes of creation. Every day. No exceptions.", "difficulty": "easy", "primary_stat": "mana", "duration": 30, "day": "Daily"},
        {"week": 2, "title": "Finish One Complete Work", "description": "Complete and publish/share one finished piece. Blog post, artwork, short video, song snippet. Done is better than perfect.", "difficulty": "medium", "primary_stat": "mana", "duration": 90, "day": "Wed or Sat"},
        {"week": 2, "title": "Study 1 Master Closely", "description": "Deeply analyze one piece of work by someone at the top of your field. Break down WHY it works. Take notes.", "difficulty": "medium", "primary_stat": "intelligence", "duration": 45, "day": "Daily"},
        {"week": 3, "title": "Publish Publicly — No Excuses", "description": "Share your work publicly this week. Post it. The fear of judgment is the final boss most creators never beat.", "difficulty": "hard", "primary_stat": "charisma", "duration": 15, "day": "Day 18"},
        {"week": 3, "title": "Seek Genuine Critique", "description": "Ask 2 people you respect to critique your recent work honestly. No validation-seeking. Improvements only.", "difficulty": "medium", "primary_stat": "intelligence", "duration": 30, "day": "Day 20"},
        {"week": 4, "title": "Big Creation Project", "description": "Start a long-form project: a short story, full design, detailed composition. Commit 3+ hours this week.", "difficulty": "hard", "primary_stat": "mana", "duration": 180, "day": "Weekend"},
        {"week": 4, "title": "Launch / Release Day", "description": "Release your best work from this month. Write a post about your process. Let the world see it.", "difficulty": "extreme", "primary_stat": "charisma", "duration": 60, "day": "Day 30"},
    ],

    # ── HEALTH ────────────────────────────────────────────────────────
    "health": [
        {"week": 1, "title": "3L Water Protocol", "description": "Drink 3 litres of water today. Track it. Set 3 alarms if needed. Hydration is the cheapest performance upgrade.", "difficulty": "easy", "primary_stat": "vitality", "duration": 5, "day": "Daily"},
        {"week": 1, "title": "8-Hour Sleep Lock", "description": "Set a hard bedtime that allows 8 hours. No screens 30 minutes before. This one habit changes everything.", "difficulty": "easy", "primary_stat": "vitality", "duration": 30, "day": "Daily"},
        {"week": 2, "title": "Whole Food Meal Prep", "description": "Prepare 5 healthy meals in advance for the week. No processed food. Track protein — hit 0.8g per kg of bodyweight.", "difficulty": "medium", "primary_stat": "vitality", "duration": 60, "day": "Sunday"},
        {"week": 2, "title": "Eliminate 1 Harmful Habit", "description": "Identify your #1 health saboteur (junk food, alcohol, late-night scrolling). Eliminate it for 14 days cold turkey.", "difficulty": "medium", "primary_stat": "mana", "duration": 15, "day": "Daily"},
        {"week": 3, "title": "Health Metric Baseline", "description": "Track: resting heart rate, weight, energy levels (1-10), sleep quality. Create your personal health dashboard.", "difficulty": "medium", "primary_stat": "intelligence", "duration": 30, "day": "Day 15"},
        {"week": 3, "title": "No Sugar for 7 Days", "description": "Zero added sugar for 7 consecutive days. Read every label. This phase cleanses your energy system.", "difficulty": "hard", "primary_stat": "vitality", "duration": 10, "day": "Daily"},
        {"week": 4, "title": "Doctor / Full Health Checkup", "description": "Book and attend a full health checkup. Know your actual numbers. Ignorance is not bliss — it's a ticking clock.", "difficulty": "medium", "primary_stat": "vitality", "duration": 120, "day": "Day 25"},
        {"week": 4, "title": "Health Transformation Review", "description": "Compare week 1 vs week 4 metrics. Write what changed and set the next 90-day health target.", "difficulty": "hard", "primary_stat": "intelligence", "duration": 45, "day": "Day 30"},
    ],
}


# ══════════════════════════════════════════════════════════════════════
# Main AI Engine
# ══════════════════════════════════════════════════════════════════════

class AITaskService:
    """Solo Leveling AI Task Generation Engine."""

    @staticmethod
    def detect_category(goal_text: str) -> str:
        """Score each category and return the best match."""
        text = goal_text.lower()
        scores: dict[str, int] = {cat: 0 for cat in CATEGORY_KEYWORDS}
        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    scores[cat] += len(kw.split())   # longer matches score higher
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else "mindset"

    @staticmethod
    def detect_difficulty_level(goal_text: str) -> str:
        beginner_hints = ["beginner", "start", "never", "first time", "new to", "basic", "zero"]
        advanced_hints = ["advanced", "expert", "pro", "master", "already", "experienced", "improve"]
        text = goal_text.lower()
        if any(h in text for h in advanced_hints):
            return "advanced"
        if any(h in text for h in beginner_hints):
            return "beginner"
        return "intermediate"

    @staticmethod
    def extract_timeframe(goal_text: str) -> int:
        """Extract requested weeks from goal text, default 4."""
        patterns = [
            r"(\d+)\s*week",
            r"(\d+)\s*month",
            r"in\s+(\d+)\s*days?",
        ]
        for p in patterns:
            m = re.search(p, goal_text.lower())
            if m:
                n = int(m.group(1))
                if "month" in p:
                    return n * 4
                if "day" in p:
                    return max(1, n // 7)
                return n
        return 4

    @staticmethod
    def build_tasks(
        templates: list[TaskTemplate],
        difficulty_level: str,
        requested_weeks: int,
    ) -> list[GeneratedTask]:
        """Convert templates to GeneratedTask list, scaling for difficulty."""
        scale = {"beginner": 0.8, "intermediate": 1.0, "advanced": 1.2}[difficulty_level]
        tasks: list[GeneratedTask] = []

        # One quest per week — pick the first template for each week number
        seen_weeks: set[int] = set()
        used_templates: list[TaskTemplate] = []
        for tmpl in templates:
            if tmpl["week"] <= requested_weeks and tmpl["week"] not in seen_weeks:
                seen_weeks.add(tmpl["week"])
                used_templates.append(tmpl)

        for tmpl in used_templates:
            diff = tmpl["difficulty"]
            # Scale up difficulty for advanced users
            if difficulty_level == "advanced" and diff == "medium":
                diff = "hard"
            elif difficulty_level == "advanced" and diff == "boss":
                diff = "extreme"
            elif difficulty_level == "beginner" and diff == "hard":
                diff = "medium"
            # map any leftover 'boss' to 'extreme'
            if diff == "boss":
                diff = "extreme"

            duration = tmpl["duration"]
            xp = calculate_xp(diff, duration, is_habit_building=True)
            xp = int(xp * scale)
            sp = DIFFICULTY_SP.get(diff, 1)

            # SL rationale: rotate through category-specific system voice lines
            cat = tmpl.get("primary_stat", "mindset")
            # Map primary stat back to category for rationale templates
            stat_to_cat = {
                "vitality": "fitness", "strength": "fitness",
                "intelligence": "study", "mana": "mindset", "charisma": "social",
            }
            rationale_cat = stat_to_cat.get(tmpl.get("primary_stat", "mana"), "mindset")
            rationale_pool = SL_RATIONALE_TEMPLATES.get(rationale_cat, SL_RATIONALE_TEMPLATES["mindset"])
            rationale = rationale_pool[(tmpl["week"] - 1) % len(rationale_pool)]

            tasks.append(GeneratedTask(
                title=tmpl["title"],
                description=tmpl["description"],
                difficulty=diff,
                primary_stat=tmpl["primary_stat"],
                base_xp_reward=xp,
                skill_points=sp,
                time_limit_minutes=duration + 10 if duration > 20 else None,
                week=tmpl["week"],
                day_suggestion=tmpl["day"],
                rationale=rationale,
            ))

        return tasks

    @staticmethod
    def compute_xp_summary(tasks: list[GeneratedTask]) -> dict[str, Any]:
        total_xp = sum(t.base_xp_reward for t in tasks)
        total_sp = sum(t.skill_points for t in tasks)
        by_week: dict[int, int] = {}
        by_diff: dict[str, int] = {}
        for t in tasks:
            by_week[t.week] = by_week.get(t.week, 0) + t.base_xp_reward
            by_diff[t.difficulty] = by_diff.get(t.difficulty, 0) + 1
        return {
            "total_xp_available": total_xp,
            "total_sp_available": total_sp,
            "tasks_count": len(tasks),
            "xp_per_week": by_week,
            "tasks_by_difficulty": by_diff,
            "estimated_levels_gained": max(1, total_xp // 350),
        }

    @staticmethod
    def extract_duration_minutes(text: str) -> int:
        """Pull a duration in minutes from goal text. Default 60."""
        t = text.lower()
        # hours pattern: 4 hours, 1.5 hours, 2hr, 3h
        m = re.search(r"([\d.]+)\s*(?:hours?|hrs?|h)\b", t)
        if m:
            return max(10, int(float(m.group(1)) * 60))
        # minutes pattern: 45 minutes, 30 min
        m = re.search(r"([\d]+)\s*(?:minutes?|mins?)", t)
        if m:
            return max(5, int(m.group(1)))
        return 60

    @classmethod
    def generate(cls, goal_text: str) -> GoalAnalysis:
        """Produce a single direct quest from the goal text."""
        category = cls.detect_category(goal_text)
        primary_stat, secondary_stat = STAT_FOR_CATEGORY[category]
        duration = cls.extract_duration_minutes(goal_text)
        difficulty = cls.suggest_difficulty(goal_text, "", duration)

        # Build a clean title from the raw input
        raw_title = goal_text.strip().rstrip('.')
        title = raw_title[:1].upper() + raw_title[1:] if raw_title else "Custom Quest"

        sl = cls.sl_rewrite(title, goal_text, category)
        ai = cls.calculate_custom_xp(
            title=title,
            description=goal_text,
            difficulty=difficulty,
            estimated_minutes=duration,
        )

        task = GeneratedTask(
            title=sl["sl_title"],
            description=sl["sl_description"],
            difficulty=difficulty,
            primary_stat=primary_stat,
            base_xp_reward=ai["recommended_xp"],
            skill_points=ai["recommended_sp"],
            time_limit_minutes=duration + 15 if duration > 20 else None,
            week=1,
            day_suggestion="Daily",
            rationale=ai["system_message"],
        )

        xp_summary = {
            "total_xp_available": task.base_xp_reward,
            "total_sp_available": task.skill_points,
            "tasks_count": 1,
            "xp_per_week": {1: task.base_xp_reward},
            "tasks_by_difficulty": {difficulty: 1},
            "estimated_levels_gained": max(1, task.base_xp_reward // 350),
        }

        return GoalAnalysis(
            goal_text=goal_text,
            category=category,
            subcategory=category.title(),
            difficulty_level=difficulty,
            estimated_weeks=1,
            primary_stat=primary_stat,
            secondary_stat=secondary_stat,
            system_message=ai["system_message"],
            tasks=[task],
            xp_summary=xp_summary,
        )

    @classmethod
    def calculate_custom_xp(
        cls,
        title: str,
        description: str,
        difficulty: str,
        estimated_minutes: int,
        category_hint: str = "",
    ) -> dict[str, Any]:
        """Calculate XP and stat recommendation for a user-defined task."""
        xp = calculate_xp(difficulty, estimated_minutes)
        cat = cls.detect_category(f"{title} {description} {category_hint}")
        primary_stat, _ = STAT_FOR_CATEGORY[cat]
        sl = cls.sl_rewrite(title, description, cat)
        return {
            "recommended_xp": xp,
            "recommended_sp": DIFFICULTY_SP.get(difficulty, 1),
            "primary_stat": primary_stat,
            "category_detected": cat,
            "sl_title": sl["sl_title"],
            "sl_description": sl["sl_description"],
            "system_message": SYSTEM_MESSAGES.get(cat, SYSTEM_MESSAGES["mindset"]),
            "xp_breakdown": {
                "base_xp": DIFFICULTY_XP.get(difficulty, 100),
                "duration_bonus": max(0, (estimated_minutes - 15) // 5),
                "habit_bonus": int(DIFFICULTY_XP.get(difficulty, 100) * 0.15),
            },
        }

    @staticmethod
    def suggest_difficulty(title: str, description: str, estimated_minutes: int = 30) -> str:
        """Suggest a difficulty tier from quest text and duration. Returns trivial|easy|medium|hard|extreme."""
        text = (title + " " + description).lower()

        # Keyword intensity scoring
        extreme_hints = ["all day", "100 days", "boss", "brutal", "elite", "extreme", "max effort",
                         "impossible", "s-rank", "legendary", "30 days", "marathon", "ultramarathon"]
        hard_hints    = ["week", "daily for", "30 minutes", "1 hour", "deep work", "mock exam",
                         "interview", "compete", "public speaking", "launch", "release", "publish",
                         "cold", "difficult", "challenge", "advanced"]
        medium_hints  = ["20 minutes", "chapter", "practice", "build", "write", "design", "read",
                         "research", "track", "review", "session", "multiple", "routine"]
        easy_hints    = ["5 minutes", "quick", "simple", "start", "try", "first", "basic",
                         "stretch", "walk", "drink water", "sleep", "journal"]

        score = {
            "extreme": sum(1 for h in extreme_hints if h in text),
            "hard":    sum(1 for h in hard_hints    if h in text),
            "medium":  sum(1 for h in medium_hints  if h in text),
            "easy":    sum(1 for h in easy_hints    if h in text),
        }

        # Duration tiebreaker
        if estimated_minutes >= 120:
            score["hard"] += 2
        elif estimated_minutes >= 60:
            score["medium"] += 2
        elif estimated_minutes >= 30:
            score["medium"] += 1
        elif estimated_minutes <= 10:
            score["easy"] += 2

        # Return highest scoring tier; default to easy if all zero
        ordered = ["extreme", "hard", "medium", "easy"]
        best = max(ordered, key=lambda t: score[t])
        return best if score[best] > 0 else "easy"

    @staticmethod
    def sl_rewrite(title: str, description: str, category: str = "") -> dict[str, str]:
        """Generate a Solo Leveling–voiced title and description from plain user input."""
        import random
        cat = category or "mindset"
        prefixes = SL_TITLE_PREFIXES.get(cat, SL_TITLE_PREFIXES["mindset"])
        # Pick a prefix deterministically (based on title length so same input = same result)
        prefix = prefixes[len(title) % len(prefixes)]

        # Capitalise title words for SL aesthetic
        clean_title = " ".join(w.capitalize() for w in title.strip().split())
        sl_title = f"{prefix} {clean_title}"

        # Build SL description from template
        sys_msg = SYSTEM_MESSAGES.get(cat, SYSTEM_MESSAGES["mindset"])
        if description and len(description) > 15:
            sl_desc = (
                f"{sys_msg.split('. ', 1)[0]}. "
                f"Objective: {description.strip().rstrip('.')}. "
                f"Completion awards stat growth. Failure is recorded."
            )
        else:
            sl_desc = (
                f"{sys_msg} "
                f"The System has assigned this trial: {clean_title}. "
                f"Complete it to progress. No extensions granted."
            )

        return {"sl_title": sl_title, "sl_description": sl_desc}


# ── Optional OpenAI upgrade ───────────────────────────────────────────

def _build_prompt(goal_text: str, base: GoalAnalysis) -> str:
    return (
        f"You are a brutally honest, highly motivating personal development coach "
        f"in the style of the Solo Leveling manhwa System. "
        f"The user's goal is: '{goal_text}'. "
        f"Rewrite each task description to be more specific, actionable, and motivating. "
        f"Keep each under 200 characters. "
        f"Return a JSON object with key 'descriptions' containing an array of strings in the same order. "
        f"Input: {json.dumps([t.description for t in base.tasks])}"
    )


def _try_groq_generate(goal_text: str, api_key: str) -> GoalAnalysis | None:
    """Use Groq (free) to enhance task descriptions."""
    try:
        from groq import Groq  # type: ignore
        client = Groq(api_key=api_key)
        base = AITaskService.generate(goal_text)
        resp = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": _build_prompt(goal_text, base)}],
            response_format={"type": "json_object"},
            max_tokens=2000,
        )
        raw = json.loads(resp.choices[0].message.content or "{}")
        descriptions = raw.get("descriptions", [])
        if isinstance(descriptions, list):
            for i, desc in enumerate(descriptions):
                if i < len(base.tasks):
                    base.tasks[i].description = str(desc)
        return base
    except Exception:
        return None


def _try_openai_generate(goal_text: str, api_key: str) -> GoalAnalysis | None:
    """Use OpenAI to enhance task descriptions."""
    try:
        import openai  # type: ignore
        client = openai.OpenAI(api_key=api_key)
        base = AITaskService.generate(goal_text)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": _build_prompt(goal_text, base)}],
            response_format={"type": "json_object"},
            max_tokens=2000,
        )
        raw = json.loads(resp.choices[0].message.content or "{}")
        descriptions = raw.get("descriptions", [])
        if isinstance(descriptions, list):
            for i, desc in enumerate(descriptions):
                if i < len(base.tasks):
                    base.tasks[i].description = str(desc)
        return base
    except Exception:
        return None


def generate_goal_tasks(
    goal_text: str,
    openai_api_key: str = "",
    groq_api_key: str = "",
) -> GoalAnalysis:
    """Public API — uses Groq > OpenAI > rule engine (priority order)."""
    if groq_api_key:
        result = _try_groq_generate(goal_text, groq_api_key)
        if result:
            return result
    if openai_api_key:
        result = _try_openai_generate(goal_text, openai_api_key)
        if result:
            return result
    return AITaskService.generate(goal_text)
