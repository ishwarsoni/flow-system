from sqlalchemy.orm import Session  # type: ignore
from typing import List, Optional
from datetime import datetime

from app.models.inventory import Item, ItemType, ItemRarity  # type: ignore
from app.models.user_stats import UserStats  # type: ignore
from app.services.inventory_service import InventoryService
from app.core.exceptions import FLOWException  # type: ignore

class ShopException(FLOWException):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)  # type: ignore

class ShopService:
    @staticmethod
    def get_items(db: Session, item_type: Optional[str] = None) -> List[Item]:
        """List all items available for purchase."""
        query = db.query(Item).filter(Item.is_tradable == True)
        if item_type:
            query = query.filter(Item.item_type == item_type)
        return query.all()

    @staticmethod
    def buy_item(user_id: int, item_slug: str, quantity: int, db: Session) -> dict:
        """Purchase an item with coins."""
        if quantity < 1:
            raise ShopException("Quantity must be at least 1")

        # 1. Get Item
        item = db.query(Item).filter(Item.slug == item_slug).first()
        if not item:
            raise ShopException("Item not found")
        
        if not item.is_tradable:
            raise ShopException("This item cannot be purchased")

        total_cost = item.coin_value * quantity

        # 2. Get User Stats (Coins)
        user_stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
        if not user_stats:
            raise ShopException("User stats not found")
        
        if user_stats.coins < total_cost:
            raise ShopException(f"Insufficient coins. Need {total_cost}, have {user_stats.coins}")

        # 3. Deduct Coins
        user_stats.coins -= total_cost
        
        # 4. Add to Inventory (Validation for stack limit happens here)
        try:
            inventory_item = InventoryService.add_item(user_id, item.id, quantity, db)
        except Exception as e:
            # Rollback acts on transaction block if raised, but we are inside one session logic
            # We should probably check stack limit before deducting coins?
            # InventoryService.add_item might raise exception.
            # If it raises, the whole request transaction will rollback, so coins won't be deducted.
            # That's fine.
            raise ShopException(str(e))

        db.commit()
        db.refresh(user_stats)

        return {
            "success": True,
            "message":f"Purchased {quantity}x {item.name}",
            "item": item,
            "coins_remaining": user_stats.coins,
            "inventory_id": inventory_item.id
        }
