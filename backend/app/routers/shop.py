from fastapi import APIRouter, Depends, HTTPException, status  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from typing import List, Optional

from app.db.database import get_db  # type: ignore
from app.dependencies.auth import get_current_user  # type: ignore
from app.models.user import User  # type: ignore
from app.schemas.inventory import ItemResponse  # type: ignore
from app.schemas.shop import ShopPurchaseResponse  # type: ignore
from app.services.shop_service import ShopService, ShopException  # type: ignore

router = APIRouter()

@router.get("/items", response_model=List[ItemResponse])
def get_shop_items(
    type: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all items available for purchase."""
    return ShopService.get_items(db, type)

@router.post("/buy/{item_slug}", response_model=ShopPurchaseResponse)
def buy_item(
    item_slug: str,
    quantity: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Buy an item with coins."""
    try:
        result = ShopService.buy_item(current_user.id, item_slug, quantity, db)
        return ShopPurchaseResponse(**result)
    except ShopException as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to purchase item")
