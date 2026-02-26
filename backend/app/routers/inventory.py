from fastapi import APIRouter, Depends, HTTPException, status  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from typing import List

from app.db.database import get_db  # type: ignore
from app.dependencies.auth import get_current_user  # type: ignore
from app.models.user import User  # type: ignore
from app.schemas.inventory import PlayerInventoryResponse, UseItemRequest  # type: ignore
from app.services.inventory_service import InventoryService  # type: ignore

router = APIRouter()

@router.get("/", response_model=List[PlayerInventoryResponse])
def get_inventory(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's inventory."""
    return InventoryService.get_inventory(db, current_user.id)

@router.post("/use")
def use_item(
    request: UseItemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Use an item (consume it to apply effect)."""
    return InventoryService.use_item(db, current_user.id, request.item_id)
