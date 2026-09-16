from typing import Annotated

from fastapi import APIRouter

from app.dependencies import CurrentUser
from app.schemas import Item

router = APIRouter(prefix="/items", tags=["items"])


@router.post("/", response_model=Item)
async def create_item(item: Item, user: CurrentUser):
    return item


@router.get("/{item_id}")
def read_item(item_id: int, user: CurrentUser):
    return {"item_id": item_id}
