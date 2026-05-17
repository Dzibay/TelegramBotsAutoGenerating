from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.constants import HTTPStatus, SuccessMessages
from app.core.dependencies import get_current_user
from app.domain.models.bot_models import BotCreateRequest, BotGenerateRequest, BotUpdateRequest
from app.domain.services import bot_service
from app.utils.response import success_response

router = APIRouter(prefix="/bots", tags=["bots"])


@router.get("")
async def list_bots(
    campaign_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    grouped: bool = Query(False),
    _user: dict = Depends(get_current_user),
):
    if grouped:
        data = await bot_service.list_bots_grouped()
        return success_response(data={"campaigns": data})
    bots = await bot_service.list_bots(campaign_id=campaign_id, status=status)
    return success_response(data={"bots": bots})


@router.post("/generate-draft")
async def generate_draft(body: BotGenerateRequest, _user: dict = Depends(get_current_user)):
    draft = await bot_service.generate_bot_draft(
        body.campaign_id,
        body.telegram_account_id,
        body.target_url,
        keyword=body.keyword,
        redirect_slug=body.redirect_slug,
    )
    return success_response(data={"draft": draft})


@router.get("/{bot_id}")
async def get_bot(bot_id: int, _user: dict = Depends(get_current_user)):
    bot = await bot_service.get_bot(bot_id)
    return success_response(data={"bot": bot})


@router.post("", status_code=HTTPStatus.CREATED)
async def create_bot(body: BotCreateRequest, _user: dict = Depends(get_current_user)):
    bot = await bot_service.create_bot(
        campaign_id=body.campaign_id,
        telegram_account_id=body.telegram_account_id,
        target_url=body.target_url,
        display_name=body.display_name,
        username=body.username,
        description=body.description,
        welcome_message=body.welcome_message,
        keyword=body.keyword,
        redirect_slug=body.redirect_slug,
        create_via_botfather=body.create_via_botfather,
        auto_start=body.auto_start,
    )
    return success_response(data={"bot": bot}, message=SuccessMessages.BOT_CREATED)


@router.patch("/{bot_id}")
async def update_bot(
    bot_id: int,
    body: BotUpdateRequest,
    _user: dict = Depends(get_current_user),
):
    bot = await bot_service.update_bot(
        bot_id,
        display_name=body.display_name,
        target_url=body.target_url,
        description=body.description,
        welcome_message=body.welcome_message,
        keyword=body.keyword,
        sync_botfather=body.sync_botfather,
    )
    return success_response(data={"bot": bot}, message=SuccessMessages.BOT_UPDATED)


@router.delete("/{bot_id}")
async def delete_bot(bot_id: int, _user: dict = Depends(get_current_user)):
    await bot_service.delete_bot(bot_id)
    return success_response(message=SuccessMessages.BOT_DELETED)


@router.post("/{bot_id}/verify")
async def verify_bot(bot_id: int, _user: dict = Depends(get_current_user)):
    result = await bot_service.verify_bot(bot_id)
    return success_response(data=result)


@router.post("/{bot_id}/start")
async def start_bot(bot_id: int, _user: dict = Depends(get_current_user)):
    bot = await bot_service.set_bot_status(bot_id, "active")
    return success_response(data={"bot": bot}, message="Бот запущен")


@router.post("/{bot_id}/stop")
async def stop_bot(bot_id: int, _user: dict = Depends(get_current_user)):
    bot = await bot_service.set_bot_status(bot_id, "stopped")
    return success_response(data={"bot": bot}, message="Бот остановлен")
