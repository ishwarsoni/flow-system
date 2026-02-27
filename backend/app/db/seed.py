"""Seed quest templates and domains on startup if tables are empty.

Imports the canonical 96 templates from migrate_quest_templates.py
and the 6 domains from app.models.domain.DOMAIN_DEFINITIONS.
Idempotent — only inserts if table is empty.
"""

import logging
import sys
import os
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Ensure the backend root is on sys.path so we can import migrate_quest_templates
_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)


def seed_domains(db: Session) -> int:
    """Seed the 6 power domains if the domains table is empty."""
    from app.models.domain import Domain, DOMAIN_DEFINITIONS

    if db.query(Domain).first():
        return 0  # Already seeded

    count = 0
    for d in DOMAIN_DEFINITIONS:
        db.add(Domain(**d))
        count += 1
    db.commit()
    logger.info("Seeded %d domains", count)
    return count


def seed_quest_templates(db: Session) -> int:
    """Seed the 96 quest templates if the quest_templates table is empty."""
    from app.models.quest_template import QuestTemplate

    if db.query(QuestTemplate).first():
        return 0  # Already seeded

    from migrate_quest_templates import TEMPLATES, XP, AXES, DURATION_CAPS

    count = 0
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
        count += 1

    db.commit()
    logger.info("Seeded %d quest templates", count)
    return count


def seed_all(db: Session) -> None:
    """Run all seed functions."""
    try:
        d = seed_domains(db)
        t = seed_quest_templates(db)
        if d or t:
            logger.info("Seeding complete: %d domains, %d templates", d, t)
    except Exception as e:
        db.rollback()
        logger.error("Seeding failed: %s", e)
        raise
