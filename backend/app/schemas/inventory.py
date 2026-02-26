from typing import Optional, List, Dict, Any
from pydantic import BaseModel  # type: ignore
from datetime import datetime
from app.models.inventory import ItemType, ItemRarity  # type: ignore

class ItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    item_type: ItemType
    rarity: ItemRarity
    effect: Optional[Dict[str, Any]] = None
    icon: Optional[str] = None
    max_stack: int = 99
    coin_value: int = 10

class ItemCreate(ItemBase):
    slug: str

class ItemResponse(ItemBase):
    id: int
    slug: str
    
    class Config:
        from_attributes = True

class PlayerInventoryBase(BaseModel):
    quantity: int

class PlayerInventoryResponse(PlayerInventoryBase):
    id: int
    item: ItemResponse
    acquired_at: datetime
    
    class Config:
        from_attributes = True

class UseItemRequest(BaseModel):
    item_id: int
    amount: int = 1
