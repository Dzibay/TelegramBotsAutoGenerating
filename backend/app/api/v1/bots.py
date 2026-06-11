from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from app.constants import HTTPStatus, SuccessMessages
from app.core.dependencies import get_current_user
from app.domain.models.bot_models import (
    BotBatchCreateRequest,
    BotCreateRequest,
    BotGenerateRequest,
    BotUpdateRequest,
    GenerateAvatarPreviewRequest,
)
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
        link_mode=body.link_mode,
    )
    return success_response(data={"draft": draft})


@router.post("/generate-avatar-preview")
async def generate_avatar_preview(
    body: GenerateAvatarPreviewRequest,
    _user: dict = Depends(get_current_user),
):
    from fastapi.responses import Response

    data = await bot_service.generate_avatar_preview(
        prompt=body.prompt,
        keyword=body.keyword,
    )
    return Response(content=data, media_type="image/jpeg")


@router.get("/check-username")
async def check_username(
    username: str = Query(..., min_length=3, max_length=64),
    bot_id: Optional[int] = Query(None),
    _user: dict = Depends(get_current_user),
):
    from app.domain.services import username_service
    from app.utils.telegram_username import normalize_bot_username

    normalized = normalize_bot_username(username)
    taken_db = await username_service.is_username_taken_in_db(normalized, exclude_bot_id=bot_id)
    return success_response(
        data={
            "username": normalized,
            "available_in_app": not taken_db,
        }
    )


@router.get("/{bot_id}/avatar")
async def get_bot_avatar(bot_id: int, _user: dict = Depends(get_current_user)):
    path = await bot_service.get_bot_avatar_path(bot_id)
    return FileResponse(path, media_type="image/jpeg")


@router.get("/{bot_id}")
async def get_bot(bot_id: int, _user: dict = Depends(get_current_user)):
    bot = await bot_service.get_bot(bot_id)
    return success_response(data={"bot": bot})


@router.post("/batch-create", status_code=HTTPStatus.CREATED)
async def create_bots_batch(
    body: BotBatchCreateRequest,
    _user: dict = Depends(get_current_user),
):
    specs = [b.model_dump() for b in body.bots]
    result = await bot_service.create_bots_batch(specs)
    return success_response(data=result, message="Пакетное создание завершено")


@router.post("", status_code=HTTPStatus.CREATED)
async def create_bot(
    data: str = Form(..., description="JSON BotCreateRequest"),
    avatar: Optional[UploadFile] = File(None),
    _user: dict = Depends(get_current_user),
):
    body = BotCreateRequest.model_validate_json(data)
    avatar_bytes = None
    if avatar and avatar.filename:
        avatar_bytes = await avatar.read()
        if len(avatar_bytes) > 5 * 1024 * 1024:
            from app.core.exceptions import BadRequestError

            raise BadRequestError("Аватар не больше 5 МБ")
    bot = await bot_service.create_bot(
        campaign_id=body.campaign_id,
        telegram_account_id=body.telegram_account_id,
        target_url=body.target_url,
        display_name=body.display_name,
        username=body.username,
        description=body.description,
        about_text=body.about_text,
        welcome_message=body.welcome_message,
        welcome_button_enabled=body.welcome_button_enabled,
        welcome_button_text=body.welcome_button_text,
        keyword=body.keyword,
        redirect_slug=body.redirect_slug,
        link_mode=body.link_mode,
        create_via_botfather=body.create_via_botfather,
        auto_start=body.auto_start,
        avatar_bytes=avatar_bytes,
        generate_avatar=body.generate_avatar and not avatar_bytes,
        use_referral_api=body.use_referral_api,
    )
    return success_response(data={"bot": bot}, message=SuccessMessages.BOT_CREATED)


@router.patch("/{bot_id}")
async def update_bot(
    bot_id: int,
    body: BotUpdateRequest,
    _user: dict = Depends(get_current_user),
):
    bot = await bot_service.update_bot(bot_id, **body.model_dump(exclude_unset=True))
    return success_response(data={"bot": bot}, message=SuccessMessages.BOT_UPDATED)


@router.post("/{bot_id}/avatar")
async def upload_bot_avatar(
    bot_id: int,
    avatar: UploadFile = File(...),
    _user: dict = Depends(get_current_user),
):
    from app.core.exceptions import BadRequestError

    avatar_bytes = await avatar.read()
    if len(avatar_bytes) > 5 * 1024 * 1024:
        raise BadRequestError("Аватар не больше 5 МБ")
    bot = await bot_service.update_bot(bot_id, avatar_bytes=avatar_bytes, sync_botfather=True)
    return success_response(data={"bot": bot}, message="Аватар обновлён")


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
