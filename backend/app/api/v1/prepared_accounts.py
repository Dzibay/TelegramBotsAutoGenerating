from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user
from app.domain.services import prepared_account_service
from app.utils.response import success_response


class PreparedAccountUpdateRequest(BaseModel):
    label: Optional[str] = Field(None, max_length=200)
    is_banned: Optional[bool] = None

router = APIRouter(prefix="/prepared-accounts", tags=["prepared-accounts"])


@router.get("")
async def list_prepared_accounts(
    available_only: bool = Query(False, description="Только свободные для кампаний"),
    _user: dict = Depends(get_current_user),
):
    items = await prepared_account_service.list_prepared_accounts(
        available_only=available_only
    )
    return success_response(data={"accounts": items})


@router.get("/{prepared_id}")
async def get_prepared_account(
    prepared_id: int,
    _user: dict = Depends(get_current_user),
):
    account = await prepared_account_service.get_prepared_account(prepared_id)
    return success_response(data={"account": account})


@router.patch("/{prepared_id}")
async def update_prepared_account(
    prepared_id: int,
    body: PreparedAccountUpdateRequest,
    _user: dict = Depends(get_current_user),
):
    account = await prepared_account_service.update_prepared_account(
        prepared_id,
        label=body.label,
        is_banned=body.is_banned,
        patch_label="label" in body.model_fields_set,
        patch_banned="is_banned" in body.model_fields_set,
    )
    return success_response(data={"account": account}, message="Настройки аккаунта обновлены")
