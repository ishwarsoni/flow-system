from sqlalchemy.orm import Session  # type: ignore
from fastapi import HTTPException  # type: ignore
from typing import List, Optional

from app.models.inventory import Item, PlayerInventory, ItemType  # type: ignore
from app.models.user_stats import UserStats  # type: ignore  # For effects affecting stats
from app.schemas.inventory import ItemCreate  # type: ignore

class InventoryService:
    
    @staticmethod
    def get_inventory(db: Session, user_id: int) -> List[PlayerInventory]:
        return db.query(PlayerInventory).filter(PlayerInventory.user_id == user_id).all()

    @staticmethod
    def add_item(db: Session, user_id: int, item_id: int, quantity: int = 1) -> PlayerInventory:
        """Add item to player inventory, respecting stack limits."""
        inventory_item = db.query(PlayerInventory).filter(
            PlayerInventory.user_id == user_id,
            PlayerInventory.item_id == item_id
        ).first()
        
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        if inventory_item:
            # Check stack limit
            new_qty = inventory_item.quantity + quantity
            if new_qty > item.max_stack:
                # Logic for multiple stacks or capping? For now, cap it.
                # Ideally we'd return leftover or make new stack, but for simplicity let's cap.
                # Or meaningful error? Let's just create a new slot if max stack reached?
                # Actually, most games allow multiple stacks. But our model assumes unique (user, item) pair?
                # Ah, my model didn't have unique constraint on (user_id, item_id).
                # But `first()` implies unique.
                # Let's just cap at max_stack for MVP simplicity.
                inventory_item.quantity = min(new_qty, item.max_stack)
            else:
                inventory_item.quantity = new_qty
        else:
            inventory_item = PlayerInventory(
                user_id=user_id,
                item_id=item_id,
                quantity=min(quantity, item.max_stack)
            )
            db.add(inventory_item)
        
        db.commit()
        db.refresh(inventory_item)
        return inventory_item

    @staticmethod
    def remove_item(db: Session, user_id: int, item_id: int, quantity: int = 1) -> bool:
        inventory_item = db.query(PlayerInventory).filter(
            PlayerInventory.user_id == user_id,
            PlayerInventory.item_id == item_id
        ).first()
        
        if not inventory_item or inventory_item.quantity < quantity:
            return False
        
        inventory_item.quantity -= quantity
        if inventory_item.quantity <= 0:
            db.delete(inventory_item)
        
        db.commit()
        return True

    @staticmethod
    def use_item(db: Session, user_id: int, item_id: int) -> dict:
        """Consume an item and apply its effect."""
        # 1. Check ownership
        inv_item = db.query(PlayerInventory).filter(
            PlayerInventory.user_id == user_id,
            PlayerInventory.item_id == item_id
        ).first()
        
        if not inv_item or inv_item.quantity < 1:
            raise HTTPException(status_code=400, detail="Item not found in inventory")
            
        item = inv_item.item
        if item.item_type != ItemType.CONSUMABLE:
            raise HTTPException(status_code=400, detail="This item cannot be used")

        # 2. Apply effect
        effect = item.effect or {}
        effect_type = effect.get("type")
        effect_value = effect.get("value", 0)
        
        user_stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        msg = f"Used {item.name}"
        
        if effect_type == "xp_boost":
            # Apply XP directly for now (boosters logic requires temporal state)
            # Let's just give flat XP
            from app.services.progression_service import ProgressionService, XPChangeType  # type: ignore
            ProgressionService.apply_xp(db, user_id, int(effect_value), XPChangeType.BONUS, reason=f"Used {item.name}")
            msg += f" (+{effect_value} XP)"
            
        elif effect_type == "heal_hp":
            old_hp = user_stats.hp_current
            user_stats.hp_current = min(user_stats.hp_max, user_stats.hp_current + int(effect_value))
            msg += f" (Healed {user_stats.hp_current - old_hp} HP)"
            
        elif effect_type == "restore_mp":
            old_mp = user_stats.mp_current
            user_stats.mp_current = min(user_stats.mp_current + int(effect_value), user_stats.mp_max)
            msg += f" (Restored {user_stats.mp_current - old_mp} MP)"

        elif effect_type == "reduce_fatigue":
            old_fat = user_stats.fatigue
            user_stats.fatigue = max(0.0, user_stats.fatigue - float(effect_value))
            msg += f" (Restored {old_fat - user_stats.fatigue:.1f}% Fatigue)"
            
        else:
            raise HTTPException(status_code=501, detail=f"Unknown effect type: {effect_type}")

        # 3. Consume item
        inv_item.quantity -= 1
        if inv_item.quantity <= 0:
            db.delete(inv_item)
        
        db.commit()
        return {"message": msg, "item": item.name}

    @staticmethod
    def seed_default_items(db: Session):
        """Seed initial items if database is empty."""
        if db.query(Item).first():
            return
            
        defaults = [
            # Potions
            {
                "slug": "potion_hp_small", "name": "Small Health Potion", "description": "Restores 20 HP",
                "item_type": ItemType.CONSUMABLE, "rarity": "common", "icon": "🍷",
                "effect": {"type": "heal_hp", "value": 20}, "coin_value": 50
            },
            {
                "slug": "potion_mp_small", "name": "Small Mana Potion", "description": "Restores 15 MP",
                "item_type": ItemType.CONSUMABLE, "rarity": "common", "icon": "🧪",
                "effect": {"type": "restore_mp", "value": 15}, "coin_value": 50
            },
            {
                "slug": "potion_fatigue", "name": "Energy Drink", "description": "Reduces fatigue by 10%",
                "item_type": ItemType.CONSUMABLE, "rarity": "uncommon", "icon": "⚡",
                "effect": {"type": "reduce_fatigue", "value": 10}, "coin_value": 100
            },
            # XP items
            # {
            #     "slug": "xp_tome_small", "name": "Novice XP Tome", "description": "Grant 500 XP instantly",
            #     "item_type": ItemType.CONSUMABLE, "rarity": "rare", "icon": "📖",
            #     "effect": {"type": "xp_boost", "value": 500}, "coin_value": 250
            # },
        ]
        
        for data in defaults:
            db.add(Item(**data))
        db.commit()
