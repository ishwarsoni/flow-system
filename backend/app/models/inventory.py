from sqlalchemy import Column, Integer, String, Enum, ForeignKey, Boolean, DateTime, JSON  # type: ignore
from sqlalchemy.orm import relationship  # type: ignore
from sqlalchemy.sql import func  # type: ignore
import enum

from app.db.base import Base  # type: ignore

class ItemRarity(str, enum.Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    MYTHIC = "mythic"

class ItemType(str, enum.Enum):
    CONSUMABLE = "consumable"  # Potions, food
    EQUIPMENT = "equipment"    # Weapons, armor (future)
    MATERIAL = "material"      # Crafting (future)
    KEY = "key"                # Quest items
    BADGE = "badge"            # Achievements/display

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)  # e.g. "xp_potion_small"
    name = Column(String, nullable=False)
    description = Column(String)
    item_type = Column(Enum(ItemType), default=ItemType.CONSUMABLE)
    rarity = Column(Enum(ItemRarity), default=ItemRarity.COMMON)
    
    # Effect definition (e.g. {"type": "xp_boost", "value": 1.5, "duration": 3600})
    effect = Column(JSON, nullable=True)
    
    icon = Column(String)  # Emoji or URL
    max_stack = Column(Integer, default=99)
    is_tradable = Column(Boolean, default=True)
    coin_value = Column(Integer, default=10)  # Sell price
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PlayerInventory(Base):
    __tablename__ = "player_inventory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), index=True, nullable=False)
    
    quantity = Column(Integer, default=1)
    acquired_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", backref="inventory")
    item = relationship("Item")
