from fastapi import APIRouter, Depends

from app.constants import HTTPStatus, SuccessMessages
from app.core.dependencies import get_current_user
from app.domain.models.item_models import ItemCreateRequest, ItemUpdateRequest
from app.domain.services import item_service
from app.utils.response import success_response

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/")
async def list_items(current_user: dict = Depends(get_current_user)):
    items = await item_service.list_items(current_user["id"])
    return success_response(data={"items": items})


@router.post("/", status_code=HTTPStatus.CREATED)
async def create_item(
    data: ItemCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    item = await item_service.create_item(
        current_user["id"], data.title, data.description
    )
    return success_response(data={"item": item}, message=SuccessMessages.ITEM_CREATED)


@router.get("/{item_id}")
async def get_item(item_id: int, current_user: dict = Depends(get_current_user)):
    item = await item_service.get_item(current_user["id"], item_id)
    return success_response(data={"item": item})


@router.patch("/{item_id}")
async def update_item(
    item_id: int,
    data: ItemUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    item = await item_service.update_item(
        current_user["id"],
        item_id,
        data.title,
        data.description,
    )
    return success_response(data={"item": item}, message=SuccessMessages.ITEM_UPDATED)


@router.delete("/{item_id}")
async def delete_item(item_id: int, current_user: dict = Depends(get_current_user)):
    await item_service.delete_item(current_user["id"], item_id)
    return success_response(message=SuccessMessages.ITEM_DELETED)
