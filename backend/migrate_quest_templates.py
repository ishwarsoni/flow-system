"""
migrate_quest_templates.py
──────────────────────────
Canonical quest templates for FLOW.

DOMAIN STRUCTURE (no domain may deviate):
  🧠 MIND     — EASY 45-60m study+summary | INTER 90m deep work | HARD 2-3h problem solving | EXTREME 3-4h mastery
  💪 BODY     — Calisthenics only. EASY push-ups/squats/plank | INTER push-ups/pull-ups/core | HARD advanced+volume | EXTREME full-body test
  ⚡ CORE     — EASY sleep+hydration | INTER meal+sleep tracking | HARD energy audit | EXTREME recovery protocol
  🎯 CONTROL  — EASY 45m focus | INTER 2h single-task | HARD 6h discipline | EXTREME 72h challenge
  🗣 PRESENCE — EASY start conversations | INTER cold message/call | HARD presentation | EXTREME lead event
  🧱 SYSTEM   — EASY clean workspace | INTER organize files | HARD financial review | EXTREME 1-year plan

TIER RULES:
  - Hard + Extreme: performance_required=True, metrics mandatory.
  - Extreme: cooldown_hours=24, weekly_limit=3.
  - Duration caps: easy=60 min, intermediate=120 min, hard=180 min, extreme=240 min.
  - 4 variants per (domain, tier) = 96 templates total.

Run: D:/FLOW/.venv/Scripts/python.exe migrate_quest_templates.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("SECRET_KEY", "migrationkeyxxx32chars_xxxxxxxxxxxxx")
os.environ.setdefault("ALGORITHM", "HS256")

import app.models  # noqa
from app.db.database import SessionLocal
from app.models.quest_template import QuestTemplate
from sqlalchemy import text

# XP by tier
XP = {"easy": 100, "intermediate": 200, "hard": 350, "extreme": 550}

# 4-axis parameters per tier
AXES = {
    "easy":         {"constraint_level": 1, "performance_required": False, "risk_level": 1, "cooldown_hours": 0},
    "intermediate": {"constraint_level": 2, "performance_required": False, "risk_level": 2, "cooldown_hours": 0},
    "hard":         {"constraint_level": 3, "performance_required": True,  "risk_level": 3, "cooldown_hours": 0},
    "extreme":      {"constraint_level": 4, "performance_required": True,  "risk_level": 4, "cooldown_hours": 24},
}

DURATION_CAPS = {
    "easy":         60,
    "intermediate": 120,
    "hard":         180,
    "extreme":      240,
}

# (category, tier, title_template, description_template, unit_type, stat_bonus, meta_overrides)
TEMPLATES = [

    # ═══════════════════════════════════════════════════════════════════════
    #  🧠 MIND — Metrics: time, output, accuracy
    # ═══════════════════════════════════════════════════════════════════════

    # ── EASY: 45-60 min study + summary ──────────────────────────────────

    ("mind", "easy",
     "Study 45 min. Write a 3-sentence summary.",
     "Study your current subject for 45 minutes without interruption. "
     "Phone in another room. When done, write a 3-sentence summary of what you covered. "
     "Log: start time, end time, topic studied, summary written.",
     "minutes", {"intelligence": 1.0}, None),

    ("mind", "easy",
     "Read 60 min. Extract 3 key insights.",
     "Read non-fiction or educational material for 60 minutes. "
     "No distractions, no phone. After finishing, write down 3 specific insights. "
     "Log: material read, pages covered, 3 insights, total time.",
     "minutes", {"intelligence": 1.0}, None),

    ("mind", "easy",
     "Flashcard review: 45 min. Track pass rate.",
     "Review flashcards or study notes for 45 minutes. "
     "Minimum 20 cards. Score every card. "
     "Log: cards reviewed, cards correct, pass rate percentage, time spent.",
     "minutes", {"intelligence": 1.0}, None),

    ("mind", "easy",
     "Practice problems: 60 min. Show all work.",
     "Work through practice problems for 60 minutes. Write out every solution step. "
     "No skipping, no shortcuts. "
     "Log: problems attempted, problems solved correctly, accuracy rate, time spent.",
     "minutes", {"intelligence": 1.0}, None),

    # ── INTERMEDIATE: 90 min deep work ───────────────────────────────────

    ("mind", "intermediate",
     "90-min deep work block. Single task. Document output.",
     "Block off 90 minutes for one cognitively demanding task. "
     "No notifications, no task-switching, no phone. "
     "Log: task worked on, output produced (word count / problems solved / pages), "
     "quality self-rating (1-10), total time.",
     "minutes", {"intelligence": 2.0, "focus": 1.0}, None),

    ("mind", "intermediate",
     "Write 500+ words in 90 min. Structured argument.",
     "Spend 90 minutes writing a structured piece: essay, analysis, or technical notes. "
     "Minimum 500 words with clear organisation. "
     "Log: final word count, topic, structure used, time spent.",
     "minutes", {"intelligence": 2.0}, None),

    ("mind", "intermediate",
     "Teach-back session: 90 min. Explain 3 concepts in writing.",
     "Study for 90 minutes and then explain 3 distinct concepts in your own words. "
     "Write each explanation as if teaching someone who knows nothing. "
     "Log: 3 concepts covered, word count per explanation, clarity self-rating (1-10).",
     "minutes", {"intelligence": 2.0, "focus": 1.0}, None),

    ("mind", "intermediate",
     "Solve 10+ problems in 90 min. Log accuracy.",
     "Set a 90-minute timer and solve at least 10 problems in your field. "
     "Show all working. No skipping steps. "
     "Log: problems attempted, problems correct, accuracy rate, average time per problem.",
     "minutes", {"intelligence": 2.0}, None),

    # ── HARD: 2-3h problem solving ───────────────────────────────────────

    ("mind", "hard",
     "2-hour problem set. Log: attempted, solved, error rate.",
     "Complete a structured problem set for 2 hours minimum. "
     "No breaks longer than 5 minutes. Full solutions required. "
     "Metrics: problems attempted, problems solved, error rate %, time spent. "
     "Submit your complete log.",
     "minutes", {"intelligence": 3.0, "focus": 2.0}, {"generates_penalty_quest": True}),

    ("mind", "hard",
     "Research and write 1000+ words. 3-hour session.",
     "Conduct deep research and produce a 1000+ word technical analysis in 3 hours. "
     "Minimum 3 sources. Clear thesis required. "
     "Metrics: word count, sources cited, key claims made, time spent. "
     "Submit word count and 1-paragraph abstract.",
     "minutes", {"intelligence": 3.0}, {"generates_penalty_quest": True}),

    ("mind", "hard",
     "Build a working solution. 2-3 hour session. Test and submit.",
     "Work on a coding, design, or engineering problem for 2-3 hours. "
     "Must produce a working artifact: code, diagram, model, or prototype. "
     "Metrics: problem described, solution built, test results (pass/fail), time per phase. "
     "Submit all four.",
     "minutes", {"intelligence": 3.0, "focus": 2.0}, {"generates_penalty_quest": True}),

    ("mind", "hard",
     "Mock exam: 2-3 hours. Timed. Score yourself.",
     "Complete a full mock exam under strict conditions for 2-3 hours. "
     "No open notes unless the real exam allows it. "
     "Metrics: total questions, score, percentage, weak areas identified. "
     "Submit your graded result.",
     "minutes", {"intelligence": 3.0}, {"generates_penalty_quest": True}),

    # ── EXTREME: 3-4h mastery (24h cooldown) ─────────────────────────────

    ("mind", "extreme",
     "4-hour mastery session. Zero distractions. Prove output.",
     "Lock in for 4 hours on one subject or project. No phone, no social media, "
     "no task-switching. "
     "Metrics: hours logged, total output (words / problems / features built), "
     "accuracy or quality self-rating (1-10), 3-point mastery reflection. "
     "Submit all four.",
     "minutes", {"intelligence": 5.0, "focus": 3.0}, {"generates_penalty_quest": True}),

    ("mind", "extreme",
     "3-hour marathon writing block. 2000+ words. No padding.",
     "Produce 2000+ words of structured written work in a 3-4 hour session. "
     "Every paragraph must contribute. Clear argument or framework required. "
     "Metrics: word count, section breakdown, coherence self-rating (1-10), time. "
     "Submit all four.",
     "minutes", {"intelligence": 5.0}, {"generates_penalty_quest": True}),

    ("mind", "extreme",
     "Build, test, and document a complete solution. 3-4 hours.",
     "Design, build, test, and document a solution to a real problem in 3-4 hours. "
     "Must produce working output with test results and documentation. "
     "Metrics: problem statement, solution description, test results, time per phase. "
     "Submit all four.",
     "minutes", {"intelligence": 5.0, "focus": 3.0}, {"generates_penalty_quest": True}),

    ("mind", "extreme",
     "Full-length exam simulation: 3-4 hours. Graded.",
     "Simulate a full exam under strict conditions for 3-4 hours. "
     "No breaks except scheduled ones. Self-grade honestly. "
     "Metrics: questions attempted, correct answers, score percentage, topics for review. "
     "Submit your graded result.",
     "minutes", {"intelligence": 5.0}, {"generates_penalty_quest": True}),

    # ═══════════════════════════════════════════════════════════════════════
    #  💪 BODY — Calisthenics Only — Metrics: sets, reps, time
    # ═══════════════════════════════════════════════════════════════════════

    # ── EASY: push-ups, squats, plank ────────────────────────────────────

    ("body", "easy",
     "Push-ups, squats, plank circuit. Log every set.",
     "Complete a bodyweight circuit: push-ups, squats, plank holds. "
     "Minimum 3 rounds. Rest no longer than 90 seconds between sets. "
     "Log: sets per exercise, reps per set, plank hold durations, total time.",
     "minutes", {"strength": 1.0, "endurance": 0.5}, None),

    ("body", "easy",
     "Push-up and squat pyramid. Track your peak round.",
     "Complete a push-up and squat pyramid. Start at 5 reps each, "
     "increase by 5 each round until failure. "
     "Log: peak round reached, total push-up reps, total squat reps, total time.",
     "minutes", {"strength": 1.0}, None),

    ("body", "easy",
     "Plank holds + push-up sets. 3 rounds minimum.",
     "Alternate between plank holds (30-60 sec) and push-up sets (10+ reps) "
     "for at least 3 rounds. "
     "Log: plank duration per round, push-up reps per set, total time under tension.",
     "minutes", {"strength": 1.0, "endurance": 0.5}, None),

    ("body", "easy",
     "50 squats + 30 push-ups + 60s plank. Log your splits.",
     "Complete: 50 air squats, 30 push-ups, 60-second plank hold. "
     "Break into sets as needed. "
     "Log: sets used per exercise, time to complete all three, rest time taken.",
     "minutes", {"strength": 1.0}, None),

    # ── INTERMEDIATE: push-ups, pull-ups, core ───────────────────────────

    ("body", "intermediate",
     "Push-ups, pull-ups, core circuit. 5 sets each.",
     "Complete 5 sets each of push-ups, pull-ups (or inverted rows), "
     "and a core exercise (plank or leg raises). "
     "Log: reps per set for each exercise, rest times, total session time.",
     "minutes", {"strength": 2.0, "endurance": 1.0}, None),

    ("body", "intermediate",
     "Push-pull superset: push-ups and pull-ups. 4 rounds + core finisher.",
     "Perform 4 superset rounds of push-ups and pull-ups (or inverted rows). "
     "Minimum 8 reps per exercise per round. Core finisher: 2-minute plank. "
     "Log: reps per round per exercise, plank time, total session time.",
     "minutes", {"strength": 2.0}, None),

    ("body", "intermediate",
     "Max-rep test: push-ups, pull-ups, hanging knee raises.",
     "Test max reps: push-ups (1 set), pull-ups (1 set), hanging knee raises (1 set). "
     "Rest 2 min between. Then 3 working sets of each at ~60% of max. "
     "Log: max reps per exercise, working set reps, total session time.",
     "minutes", {"strength": 2.0, "endurance": 1.0}, None),

    ("body", "intermediate",
     "Core-focused session: plank variations + push-ups + pull-ups.",
     "3 plank variations (front, side L, side R) for 45 sec each. "
     "Then 4 sets of push-ups and 4 sets of pull-ups (or rows). "
     "Log: plank hold times, push-up reps per set, pull-up reps per set, total time.",
     "minutes", {"strength": 2.0, "endurance": 1.0}, None),

    # ── HARD: advanced + volume ──────────────────────────────────────────

    ("body", "hard",
     "High-volume calisthenics: 5 exercises, 5 sets each.",
     "Complete 5 sets of 5 exercises (e.g. diamond push-ups, archer push-ups, "
     "pistol squats, pull-ups, L-sit holds). "
     "Metrics: exercises used, reps per set, total volume (sets x reps), session time. "
     "Submit your complete log.",
     "minutes", {"strength": 3.0, "endurance": 2.0}, {"generates_penalty_quest": True}),

    ("body", "hard",
     "Progressive push-up ladder: 4 variations. Every set logged.",
     "Push-up ladder: standard, wide, diamond, archer. "
     "5 sets per variation. Descending reps (10-8-6-4-2 or similar). "
     "Metrics: reps per set per variation, total push-up volume, max consecutive, time. "
     "Submit full log.",
     "minutes", {"strength": 3.0}, {"generates_penalty_quest": True}),

    ("body", "hard",
     "Pull-up and dip volume session. 6 sets each.",
     "Perform 6 sets each of pull-ups and dips (or elevated push-up substitute). "
     "Progressive overload: add reps or slow tempo each set. "
     "Metrics: reps per set per exercise, total volume, rest times, session time. "
     "Submit full log.",
     "minutes", {"strength": 3.0, "endurance": 2.0}, {"generates_penalty_quest": True}),

    ("body", "hard",
     "Advanced calisthenics AMRAP: 3 x 20-min blocks.",
     "Three 20-minute AMRAP blocks. Each block: different advanced exercise "
     "(muscle-ups, handstand push-ups, pistol squats, or scale to your level). "
     "Metrics: reps per block, exercises used, total reps, perceived exertion (1-10). "
     "Submit all metrics.",
     "minutes", {"strength": 3.0, "endurance": 3.0}, {"generates_penalty_quest": True}),

    # ── EXTREME: full-body test (24h cooldown) ───────────────────────────

    ("body", "extreme",
     "Full-body calisthenics test. 6 exercises, max effort.",
     "Maximum-effort full-body test: push-ups, pull-ups, dips, squats, plank, "
     "and one advanced move of your choice. 6 sets each. "
     "Metrics: exercises, reps per set, total volume, peak set per exercise, session time. "
     "Submit all metrics.",
     "minutes", {"strength": 5.0, "endurance": 3.0}, {"generates_penalty_quest": True}),

    ("body", "extreme",
     "100-rep challenge: 4 exercises. Clock every block.",
     "Complete 100 reps each of push-ups, squats, pull-ups (or rows), "
     "and plank shoulder taps. Break into sets as needed. "
     "Metrics: time per 100-rep block, total session time, sets per exercise, rest taken. "
     "Submit all metrics.",
     "minutes", {"strength": 5.0, "endurance": 4.0}, {"generates_penalty_quest": True}),

    ("body", "extreme",
     "Max-rep to failure: push-ups, pull-ups, squats. One set each.",
     "One all-out max-rep set each of push-ups, pull-ups, and squats. "
     "Full range of motion only. 3-minute rest between exercises. "
     "Metrics: max reps per exercise, time to failure, total reps, rest times. "
     "Submit all metrics.",
     "minutes", {"strength": 5.0}, {"generates_penalty_quest": True}),

    ("body", "extreme",
     "300-rep grind: 3 exercises. Minimum 100 each.",
     "Hit 300 total reps across push-ups, pull-ups (or rows), and squats. "
     "Minimum 100 per exercise. Break into sets as needed. "
     "Metrics: reps per exercise, sets taken, total time, average reps per set. "
     "Submit all metrics.",
     "minutes", {"strength": 5.0, "endurance": 4.0}, {"generates_penalty_quest": True}),

    # ═══════════════════════════════════════════════════════════════════════
    #  ⚡ CORE — Metrics: logs, hours
    # ═══════════════════════════════════════════════════════════════════════

    # ── EASY: sleep + hydration ──────────────────────────────────────────

    ("core", "easy",
     "Log 7h+ sleep and 2L+ water. Submit your numbers.",
     "Track sleep and hydration for today. "
     "Requirements: 7+ hours of sleep last night, 2+ litres of water today. "
     "Log: sleep start time, wake time, total hours, water intake in litres.",
     "tasks", {"vitality": 1.0}, None),

    ("core", "easy",
     "Sleep before midnight. Drink 8 glasses of water. Log both.",
     "Lights out before midnight. 8+ glasses (2L) of water during the day. "
     "Log: bedtime, wake time, total sleep hours, glasses of water consumed.",
     "tasks", {"vitality": 1.0}, None),

    ("core", "easy",
     "Rate sleep quality (1-10). Track water intake hourly.",
     "On waking, rate sleep quality 1-10. Throughout the day, log water every 2 hours. "
     "Aim for 2L+ total. "
     "Log: sleep quality rating, sleep hours, hourly water entries, total litres.",
     "tasks", {"vitality": 1.0}, None),

    ("core", "easy",
     "No caffeine after 2pm. 7h+ sleep. 2L water. Log all three.",
     "Today: no caffeine after 2pm, 7+ hours sleep tonight, 2+ litres water. "
     "Log: last caffeine time, sleep hours, water intake, bedtime energy rating (1-10).",
     "tasks", {"vitality": 1.0}, None),

    # ── INTERMEDIATE: meal + sleep tracking ──────────────────────────────

    ("core", "intermediate",
     "Track all meals and sleep for 3 days. Submit averages.",
     "For 3 consecutive days: log every meal (describe contents) and sleep duration. "
     "Identify your weakest day. "
     "Log: daily meal descriptions, sleep hours per night, 3-day averages.",
     "tasks", {"vitality": 2.0}, None),

    ("core", "intermediate",
     "3 clean meals + 7h sleep for 3 consecutive days.",
     "For 3 days: eat 3 whole-food meals and sleep 7+ hours each night. "
     "No processed food, no skipped meals. "
     "Log: meal descriptions per day, sleep hours per night, compliance rate.",
     "tasks", {"vitality": 2.0}, None),

    ("core", "intermediate",
     "Food journal: log every meal for 5 days. Track sleep each morning.",
     "Keep a food journal for 5 consecutive days. Log every meal and snack. "
     "Each morning, log previous night's sleep hours. "
     "Log: 5 days of meal entries, 5 sleep entries, weakest day identified.",
     "tasks", {"vitality": 2.0}, None),

    ("core", "intermediate",
     "Eliminate junk food for 3 days. Log meals and sleep quality.",
     "For 3 consecutive days: zero junk food, zero alcohol. 3 real meals per day. "
     "Track sleep quality (1-10) each morning. "
     "Log: meal descriptions, sleep quality ratings, overall energy trend.",
     "tasks", {"vitality": 2.0}, None),

    # ── HARD: energy audit ───────────────────────────────────────────────

    ("core", "hard",
     "Full-day energy audit. Rate energy every 2 hours. Find patterns.",
     "Every 2 waking hours, rate energy (1-10) and log what you ate, drank, and did. "
     "At end of day, identify your highest and lowest points and their causes. "
     "Metrics: 6+ energy ratings, meal/hydration log, peak and trough identified, "
     "cause analysis. Submit your full audit.",
     "tasks", {"vitality": 3.0}, {"generates_penalty_quest": True}),

    ("core", "hard",
     "3-day energy and sleep audit. Correlate inputs to output.",
     "For 3 days: log sleep hours, all meals, water intake, caffeine, "
     "and energy rating every 4 hours. "
     "After day 3: write a 1-paragraph analysis of what inputs drove best energy. "
     "Metrics: 3-day logs, average energy per day, analysis paragraph. Submit all.",
     "tasks", {"vitality": 3.0}, {"generates_penalty_quest": True}),

    ("core", "hard",
     "Performance protocol audit: sleep, nutrition, hydration, movement.",
     "Track a complete 24-hour protocol. Rate energy at morning, midday, and evening. "
     "Metrics: sleep hours, all meals (food groups noted), water litres, "
     "movement minutes, 3 energy ratings. Submit all five.",
     "tasks", {"vitality": 3.0, "endurance": 1.0}, {"generates_penalty_quest": True}),

    ("core", "hard",
     "Caffeine and sugar audit. 3 days. Track consumption vs energy.",
     "For 3 days: log every caffeine and sugar intake with times. "
     "Rate energy 1 hour after each intake. Compare to baseline. "
     "Metrics: daily caffeine estimate (mg), sugar servings, energy ratings, "
     "dependency pattern observation. Submit 3-day analysis.",
     "tasks", {"vitality": 3.0}, {"generates_penalty_quest": True}),

    # ── EXTREME: recovery protocol (24h cooldown) ────────────────────────

    ("core", "extreme",
     "7-day recovery protocol: sleep, nutrition, hydration. Daily log.",
     "For 7 consecutive days: 7h+ sleep, 3 clean meals, 3L+ water. "
     "Log all metrics daily. Missing any day = restart. "
     "Metrics: average sleep hours, days fully compliant, day-1 vs day-7 energy (1-10), "
     "total entries. Submit 7-day summary.",
     "tasks", {"vitality": 5.0, "endurance": 3.0}, {"generates_penalty_quest": True}),

    ("core", "extreme",
     "5-day elimination protocol: no caffeine, no alcohol, no sugar.",
     "For 5 days: zero caffeine, zero alcohol, zero added sugar. "
     "Log daily: sleep hours, meals, energy rating (1-10), withdrawal effects. "
     "Metrics: 5-day log, average energy, compliance rate, biggest challenge. "
     "Submit full log.",
     "tasks", {"vitality": 4.0}, {"generates_penalty_quest": True}),

    ("core", "extreme",
     "Sleep optimisation: 7h+ for 7 nights. No screens after 10pm.",
     "7+ hours sleep every night for 7 consecutive nights. No screens after 10pm. "
     "Log: sleep/wake times, screen cutoff compliance, morning energy rating. "
     "Metrics: 7 sleep entries, average hours, compliance rate, energy trend. "
     "Submit complete log.",
     "tasks", {"vitality": 5.0}, {"generates_penalty_quest": True}),

    ("core", "extreme",
     "Full recovery reset: 7 days. Sleep, food, hydration, movement.",
     "7-day protocol: 7h+ sleep, 3 clean meals, 3L water, 20+ min walking daily. "
     "Log all four metrics every day. Rate recovery day 1 and day 7. "
     "Metrics: 7-day log, averages per category, recovery improvement rating. "
     "Submit everything.",
     "tasks", {"vitality": 5.0, "endurance": 3.0}, {"generates_penalty_quest": True}),

    # ═══════════════════════════════════════════════════════════════════════
    #  🎯 CONTROL — Metrics: time, violations
    # ═══════════════════════════════════════════════════════════════════════

    # ── EASY: 45 min focus ───────────────────────────────────────────────

    ("control", "easy",
     "45-min focus block. Phone off. Zero distractions.",
     "Phone in another room. Close all non-essential tabs and apps. "
     "Work on a single task for 45 minutes without interruption. "
     "Log: task, start/end time, violation count (every break in focus).",
     "minutes", {"focus": 1.0}, None),

    ("control", "easy",
     "Single-task session: 45 min. One task only. Log violations.",
     "Choose one task. Work on it for 45 minutes without switching. "
     "No email, no notifications, no social media. "
     "Log: task, time spent, whether you broke focus (yes/no), violation count.",
     "minutes", {"focus": 1.0}, None),

    ("control", "easy",
     "Notification-free work: 45 min. Track every urge.",
     "Turn off all notifications. Work on your most important task for 45 minutes. "
     "Tally every urge to check phone or switch tasks. "
     "Log: task, time, total urges (violations), task completion status.",
     "minutes", {"focus": 1.0}, None),

    ("control", "easy",
     "Pomodoro: 45 min of pure focus. Log any breaks.",
     "Set a 45-minute timer. One task. No breaks, no interruptions. "
     "If you break, note the exact time and reason. "
     "Log: task, total focused time, violation count, cause of each violation.",
     "minutes", {"focus": 1.0}, None),

    # ── INTERMEDIATE: 2h single-task ─────────────────────────────────────

    ("control", "intermediate",
     "2-hour focus block. Single task. No phone. Log output and violations.",
     "Commit to a 2-hour deep focus session on one task. Phone off, notifications off. "
     "No task-switching. "
     "Log: task, output produced, total time, violation count (every focus break).",
     "minutes", {"focus": 2.0, "discipline": 1.0}, None),

    ("control", "intermediate",
     "Complete one priority task in 2 hours. No distractions. Log violations.",
     "Pick your most important task. Work on it exclusively for 2 hours. "
     "Log: task, completion status (% done if not finished), time spent, "
     "violation count (every phone check or task switch).",
     "minutes", {"focus": 2.0}, None),

    ("control", "intermediate",
     "Zero social media for 2 hours. Single task. Track every urge.",
     "Block all social media. Work on one task for 2 hours straight. "
     "Track every reflexive reach for phone or social media. "
     "Log: task, time, total violations, trigger for each urge.",
     "minutes", {"focus": 2.0, "discipline": 1.0}, None),

    ("control", "intermediate",
     "2-hour single-task sprint. Document output and every violation.",
     "One task. 2-hour timer. No breaks, no switching. "
     "Document what you produced and every time you broke focus. "
     "Log: task, output, total time, violation count, reason per violation.",
     "minutes", {"focus": 2.0}, None),

    # ── HARD: 6h discipline ──────────────────────────────────────────────

    ("control", "hard",
     "6-hour phone-free discipline protocol. Hourly logs.",
     "Stay phone-free for 6 consecutive waking hours. Each hour, log: "
     "what you worked on, distractions resisted, output produced. "
     "Metrics: 6 hourly entries, total violations, total tasks completed, "
     "total focused time. Submit your full log.",
     "tasks", {"focus": 3.0, "discipline": 3.0}, {"generates_penalty_quest": True}),

    ("control", "hard",
     "6-hour structured work day. 3 focus blocks. All tracked.",
     "Complete 3 x 2-hour deep work blocks with max 15-minute breaks between. "
     "No phone during any block. Each block on a separate task. "
     "Metrics: block durations, task per block, output per block, total violations. "
     "Submit all three block logs.",
     "tasks", {"focus": 3.0, "discipline": 2.0}, {"generates_penalty_quest": True}),

    ("control", "hard",
     "Distraction audit + 6h clean execution. Log both.",
     "Morning: list your top 5 distractions. Then execute 6 hours of distraction-free work. "
     "Log hourly. "
     "Metrics: distractions listed, 6 hourly logs, total clean hours, total violations. "
     "Submit audit and compliance log.",
     "tasks", {"focus": 3.0, "discipline": 3.0}, {"generates_penalty_quest": True}),

    ("control", "hard",
     "Time-blocked 6-hour schedule. Execute it. Log every deviation.",
     "Write a time-blocked schedule for 6 hours before starting. Execute it fully. "
     "Every deviation is a violation. "
     "Metrics: schedule submitted, blocks completed, blocks missed, total violations, reasons. "
     "Submit schedule and log.",
     "tasks", {"focus": 3.0, "discipline": 2.0}, {"generates_penalty_quest": True}),

    # ── EXTREME: 72h challenge (24h cooldown) ────────────────────────────

    ("control", "extreme",
     "72-hour discipline challenge: no passive consumption. Daily log.",
     "For 72 consecutive hours: no entertainment media (streaming, gaming, scrolling). "
     "Productive screen use only. "
     "Metrics: hours completed, total violations (zero is the goal), "
     "daily productivity output (what you produced each day). Submit 3-day log.",
     "tasks", {"focus": 5.0, "discipline": 5.0}, {"generates_penalty_quest": True}),

    ("control", "extreme",
     "72h single-focus mission. One project, three days.",
     "Dedicate 72 hours to one project or goal. No non-essential media. "
     "Minimum 6 hours focused work per day. "
     "Metrics: daily hours worked, daily output, total violations, project completion %. "
     "Submit 3-day log.",
     "tasks", {"focus": 5.0, "discipline": 5.0}, {"generates_penalty_quest": True}),

    ("control", "extreme",
     "72h phone detox. Max 30 min screen time per day.",
     "For 72 hours: phone screen time max 30 min/day (essential calls only). "
     "Track daily screen time. "
     "Metrics: daily screen time (3 entries), total violations, "
     "what you did instead each day. Submit 3-day log.",
     "tasks", {"focus": 5.0, "discipline": 5.0}, {"generates_penalty_quest": True}),

    ("control", "extreme",
     "72h output streak. Produce tangible work every day. Log violations.",
     "For 72 hours: create deliverable output every day. No passive consumption. "
     "Each day must have a concrete result. "
     "Metrics: daily deliverable described (3 entries), hours per day, "
     "total violations, discipline rating (1-10). Submit 3-day log.",
     "tasks", {"focus": 5.0, "discipline": 5.0}, {"generates_penalty_quest": True}),

    # ═══════════════════════════════════════════════════════════════════════
    #  🗣 PRESENCE — Metrics: proof, feedback
    # ═══════════════════════════════════════════════════════════════════════

    # ── EASY: start conversations ────────────────────────────────────────

    ("presence", "easy",
     "Have 3 real conversations today. Log each one.",
     "Initiate or sustain 3 meaningful conversations. "
     "In person, phone, or video only — no text. "
     "Log: who you spoke to, topic, one takeaway per conversation.",
     "tasks", {"charisma": 1.0}, None),

    ("presence", "easy",
     "Introduce yourself to someone new. Log the interaction.",
     "Start a conversation with someone you have never spoken to. "
     "Minimum 3 exchanges. "
     "Log: where, who, what you discussed, how it felt.",
     "tasks", {"charisma": 1.0}, None),

    ("presence", "easy",
     "Ask 3 people a genuine question today. Log their responses.",
     "Approach 3 different people and ask a genuine, open-ended question. "
     "Listen to their full answer. "
     "Log: who, your question, their response summary, what you learned.",
     "tasks", {"charisma": 1.0}, None),

    ("presence", "easy",
     "Reconnect with someone you haven't spoken to in 3+ months.",
     "Call or meet someone you haven't talked to in 3+ months. "
     "Minimum 5-minute conversation. "
     "Log: who, how long, one thing you learned about them.",
     "tasks", {"charisma": 1.0}, None),

    # ── INTERMEDIATE: cold message / call ────────────────────────────────

    ("presence", "intermediate",
     "Send a cold message to someone in your field. Log the result.",
     "Message or email someone in your field you have never spoken to. "
     "Professional, specific, genuine. "
     "Log: who, your message (screenshot or copy), whether you got a reply.",
     "tasks", {"charisma": 2.0}, None),

    ("presence", "intermediate",
     "Make a cold call. 3+ min if answered. Log the outcome.",
     "Call someone you have never spoken to — professional contact, lead, or peer. "
     "If answered: minimum 3-minute conversation. "
     "Log: who, purpose, outcome, duration.",
     "tasks", {"charisma": 2.0}, None),

    ("presence", "intermediate",
     "Cold outreach: message 5 people in one day. Track replies.",
     "Send personalised messages to 5 people you have never contacted. "
     "No copy-paste — each must be tailored. "
     "Log: names/roles, message summary per person, replies received.",
     "tasks", {"charisma": 2.0}, None),

    ("presence", "intermediate",
     "Make 3 cold calls in one day. Log every attempt and outcome.",
     "Call 3 people you do not know. Each must have a clear purpose. "
     "If no answer, log the attempt and move on. "
     "Log: who, purpose, answered (yes/no), conversation summary, duration.",
     "tasks", {"charisma": 2.0}, None),

    # ── HARD: presentation ───────────────────────────────────────────────

    ("presence", "hard",
     "Deliver a 10-min presentation to a live audience.",
     "Prepare and deliver a 10-minute structured presentation to 2+ people. "
     "Real audience only — no solo recording. "
     "Metrics: duration, audience size, topic, clarity self-rating (1-10), "
     "one piece of feedback received. Submit all five.",
     "tasks", {"charisma": 3.0, "leadership": 2.0}, {"generates_penalty_quest": True}),

    ("presence", "hard",
     "Lead a 20-min meeting or group discussion. Get feedback.",
     "Facilitate a meeting, study group, or discussion for 20+ minutes. "
     "You must lead — not just attend. "
     "Metrics: duration, participants, outcome reached, effectiveness rating (1-10), "
     "one feedback comment. Submit all.",
     "tasks", {"charisma": 3.0, "leadership": 3.0}, {"generates_penalty_quest": True}),

    ("presence", "hard",
     "Record a 5-min explanation video. Share it. Collect feedback.",
     "Record a 5-minute video explaining a topic you know. Share with 1+ person. "
     "Metrics: topic, duration, who you shared with, their feedback (one line), "
     "self-rating (1-10). Submit all.",
     "tasks", {"charisma": 3.0}, {"generates_penalty_quest": True}),

    ("presence", "hard",
     "Teach something to 3+ people for 15 min. Log feedback.",
     "Teach a concept or skill to at least 3 people. In person or live video. "
     "Minimum 15 minutes. "
     "Metrics: topic, audience size, duration, feedback received (1 quote), "
     "clarity self-rating (1-10). Submit all.",
     "tasks", {"charisma": 3.0, "leadership": 2.0}, {"generates_penalty_quest": True}),

    # ── EXTREME: lead event (24h cooldown) ───────────────────────────────

    ("presence", "extreme",
     "Plan and lead a public event for 10+ people.",
     "Organise and run a real event: workshop, meetup, training, or community session. "
     "Minimum 10 attendees. You are organiser and host. "
     "Metrics: event type, attendee count, duration, your responsibilities, "
     "post-event reflection (3 sentences). Submit all five.",
     "tasks", {"charisma": 5.0, "leadership": 5.0}, {"generates_penalty_quest": True}),

    ("presence", "extreme",
     "Speak publicly to 10+ people for 15+ minutes.",
     "Deliver a prepared talk to an audience of 10+ for at least 15 minutes. "
     "Metrics: audience size, duration, topic, one piece of audience feedback, "
     "composure self-rating (1-10). Submit all five.",
     "tasks", {"charisma": 5.0, "leadership": 4.0}, {"generates_penalty_quest": True}),

    ("presence", "extreme",
     "Organise and host a multi-hour group activity. 8+ people.",
     "Plan and host a 2+ hour group activity with 8+ participants. "
     "You lead the agenda, manage the group, close the event. "
     "Metrics: event description, attendee count, duration, "
     "feedback collected (2+ comments), leadership self-rating (1-10). Submit all.",
     "tasks", {"charisma": 5.0, "leadership": 5.0}, {"generates_penalty_quest": True}),

    ("presence", "extreme",
     "Build and pitch a real project to 5+ people. Collect feedback.",
     "Create a real pitch (business idea, proposal, or concept). "
     "Present it to 5+ different people. "
     "Metrics: topic, people pitched, feedback themes (3+), "
     "what you will change based on feedback. Submit all four.",
     "tasks", {"charisma": 5.0, "leadership": 5.0}, {"generates_penalty_quest": True}),

    # ═══════════════════════════════════════════════════════════════════════
    #  🧱 SYSTEM — Metrics: documents
    # ═══════════════════════════════════════════════════════════════════════

    # ── EASY: clean workspace ────────────────────────────────────────────

    ("system", "easy",
     "Clean and organise your workspace. Rate the result.",
     "Clean your physical workspace: desk, shelves, cables, floor. "
     "Everything in its place. "
     "Log: areas cleaned, items removed or reorganised, time taken, result rating (1-10).",
     "tasks", {"discipline": 1.0}, None),

    ("system", "easy",
     "Declutter one area: desk, drawer, or shelf. Before/after log.",
     "Choose one cluttered area. Remove everything, clean, return only essentials. "
     "Log: area chosen, items removed, items kept, time taken.",
     "tasks", {"discipline": 1.0}, None),

    ("system", "easy",
     "Purge inbox: delete or archive 50+ items.",
     "Email inbox, downloads folder, or desktop — clear 50+ items. "
     "Log: area cleaned, items processed, count before/after, time taken.",
     "tasks", {"discipline": 1.0}, None),

    ("system", "easy",
     "Clean your digital desktop and downloads folder. Zero clutter.",
     "Delete, sort, or archive every file on your desktop and in downloads. "
     "Goal: zero random files remaining. "
     "Log: files processed, folders created, items deleted, time taken.",
     "tasks", {"discipline": 1.0}, None),

    # ── INTERMEDIATE: organise files ─────────────────────────────────────

    ("system", "intermediate",
     "Full digital organisation: files, notes, email. 90-min sprint.",
     "Spend 90 minutes organising your digital life: files, cloud storage, notes, email. "
     "Create folders, rename files, delete junk. "
     "Log: areas covered, items processed, folders created, improvement rating (1-10).",
     "tasks", {"discipline": 2.0}, None),

    ("system", "intermediate",
     "Organise all project files. Consistent naming and folder structure.",
     "Take one major project folder. Reorganise: consistent naming, proper folders, "
     "delete duplicates. "
     "Log: project name, files before/after, folders created, time spent.",
     "tasks", {"discipline": 2.0}, None),

    ("system", "intermediate",
     "Review all active projects. Write status on each.",
     "List every active project or open loop. For each: current status, next action, deadline. "
     "Log: total projects, projects with clear next actions, stale projects identified.",
     "tasks", {"discipline": 2.0}, None),

    ("system", "intermediate",
     "Write SOPs for 3 recurring tasks. Step-by-step documents.",
     "Identify 3 tasks you repeat regularly. Write step-by-step standard procedures. "
     "Log: 3 task names, steps per SOP, estimated weekly time saved.",
     "tasks", {"discipline": 2.0}, None),

    # ── HARD: financial review ───────────────────────────────────────────

    ("system", "hard",
     "Monthly financial review: income, expenses, savings rate.",
     "Review finances for the past month. "
     "Metrics: total income, total expenses, savings rate %, "
     "biggest unnecessary expense. Submit all four as a document.",
     "tasks", {"discipline": 3.0}, {"generates_penalty_quest": True}),

    ("system", "hard",
     "Expense audit: categorise all spending. Identify 3 cuts.",
     "Go through every expense from the past month. Categorise each. "
     "Identify top 3 categories and 3 expenses to cut. "
     "Metrics: total spend, category list, top 3 with amounts, 3 cuts. "
     "Submit your audit document.",
     "tasks", {"discipline": 3.0}, {"generates_penalty_quest": True}),

    ("system", "hard",
     "Build a 30-day budget. Track actuals for 1 week.",
     "Create a detailed monthly budget with categories and limits. "
     "Track actual spending for 7 days. "
     "Metrics: budget document, 7-day actuals, variance per category, compliance rate. "
     "Submit budget and log.",
     "tasks", {"discipline": 3.0}, {"generates_penalty_quest": True}),

    ("system", "hard",
     "Net worth calculation + income stream audit.",
     "Calculate current net worth (assets minus liabilities). List all income streams. "
     "Metrics: net worth figure, asset list, liability list, income streams counted, "
     "total monthly income. Submit your financial snapshot document.",
     "tasks", {"discipline": 3.0}, {"generates_penalty_quest": True}),

    # ── EXTREME: 1-year plan (24h cooldown) ──────────────────────────────

    ("system", "extreme",
     "Write your 1-year execution plan. Quarterly goals. Weekly habits.",
     "Comprehensive 1-year plan: 3 most important goals, quarterly milestones per goal, "
     "weekly habits to achieve them, measurement system. "
     "Metrics: 3 goals, quarterly milestones (3 per goal), weekly habits, "
     "measurement method. Submit your plan document.",
     "tasks", {"discipline": 5.0}, {"generates_penalty_quest": True}),

    ("system", "extreme",
     "12-month financial freedom plan. Targets, actions, timeline.",
     "Calculate current position. Set 12-month targets. Define monthly actions. "
     "Build accountability checkpoints. "
     "Metrics: current net worth, 12-month target, monthly action plan, "
     "checkpoint dates. Submit your plan document.",
     "tasks", {"discipline": 5.0}, {"generates_penalty_quest": True}),

    ("system", "extreme",
     "Redesign your daily operating system. Run it for 3 days. Log results.",
     "Build a new daily system: wake time, routines, work blocks, exercise, wind-down, sleep. "
     "Run it for 3 consecutive days. "
     "Metrics: schedule document, 3-day compliance rate, daily energy rating, "
     "one permanent change identified. Submit schedule + 3-day log.",
     "tasks", {"discipline": 5.0}, {"generates_penalty_quest": True}),

    ("system", "extreme",
     "Life bottleneck analysis. Top 3. Solutions. Implement one.",
     "Find the 3 biggest bottlenecks limiting your progress (health, work, systems). "
     "For each: problem, root cause, solution, success metric. "
     "Implement at least one before submitting. "
     "Metrics: 3 bottlenecks documented, solutions proposed, 1 implemented. "
     "Submit your analysis document.",
     "tasks", {"discipline": 5.0}, {"generates_penalty_quest": True}),
]


def main():
    db = SessionLocal()
    try:
        deleted = db.execute(text("DELETE FROM quest_templates")).rowcount
        db.commit()
        print(f"Cleared {deleted} old templates.")

        inserted = 0
        for row in TEMPLATES:
            category, tier, title_tmpl, desc_tmpl, unit_type, stat_bonus, meta_overrides = row
            axes = AXES[tier]
            template = QuestTemplate(
                category=category,
                tier=tier,
                phase="any",
                title_template=title_tmpl,
                description_template=desc_tmpl,
                unit_type=unit_type,
                base_xp=XP[tier],
                stat_bonus=stat_bonus,
                meta_overrides=meta_overrides,
                max_duration_minutes=DURATION_CAPS[tier],
                constraint_level=axes["constraint_level"],
                performance_required=axes["performance_required"],
                risk_level=axes["risk_level"],
                cooldown_hours=axes["cooldown_hours"],
                is_active=True,
                selection_weight=1.0,
            )
            db.add(template)
            inserted += 1

        db.commit()
        print(f"Inserted {inserted} templates (6 domains x 4 tiers x 4 variants).")

        rows = db.execute(text(
            "SELECT category, tier, COUNT(*) as cnt "
            "FROM quest_templates GROUP BY category, tier ORDER BY category, tier"
        )).fetchall()
        print("\n  Domain       Tier           Count")
        print("  " + "-" * 40)
        for r in rows:
            print(f"  {r[0]:<12} {r[1]:<14} {r[2]}")
        print("\nMigration complete.")

    except Exception as exc:
        db.rollback()
        import traceback; traceback.print_exc()
        print(f"FAILED: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
