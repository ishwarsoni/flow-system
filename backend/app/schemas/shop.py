from pydantic import BaseModel  # type: ignore
from app.schemas.inventory import ItemResponse

class ShopPurchaseResponse(BaseModel):
    success: bool
    message: str
    coins_remaining: int
    item: ItemResponse
