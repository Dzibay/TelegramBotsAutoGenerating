from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.constants import HTTPStatus, SuccessMessages
from app.core.dependencies import begin_idempotent_request, get_current_user
from app.core.idempotency import IdempotencyContext, complete_idempotent, fail_idempotent
from app.domain.models.bot_models import (
    BotBatchCreateRequest,
    BotCreateRequest,
    BotGenerateRequest,
    BotImportRequest,
    BotUpdateRequest,
    GenerateAvatarPreviewRequest,
)
from app.domain.services import bot_service, job_service
from app.utils.response import success_response

router = APIRouter(prefix="/bots", tags=["bots"])


def _idempotent_json(ctx: IdempotencyContext, response: JSONResponse) -> JSONResponse:
    if ctx.replay:
        body = ctx.replay.get("body") or ctx.replay
        status = int(ctx.replay.get("status_code") or 200)
        return JSONResponse(content=body, status_code=status)
    return response


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


@router.post("/batch-create", status_code=202)
async def create_bots_batch(
    body: BotBatchCreateRequest,
    idem: IdempotencyContext = Depends(begin_idempotent_request),
    _user: dict = Depends(get_current_user),
):
    if idem.replay:
        return _idempotent_json(idem, JSONResponse(content={}))
    try:
        specs = [b.model_dump() for b in body.bots]
        job = await job_service.start_batch_create_job(specs)
        payload = success_response(
            data={"job": job, "queued": True},
            message="Пакетное создание поставлено в очередь",
        )
        await complete_idempotent(idem, {"status_code": 202, "body": payload})
        return payload
    except Exception:
        await fail_idempotent(idem)
        raise


@router.post("", status_code=202)
async def create_bot(
    data: str = Form(..., description="JSON BotCreateRequest"),
    avatar: Optional[UploadFile] = File(None),
    idem: IdempotencyContext = Depends(begin_idempotent_request),
    _user: dict = Depends(get_current_user),
):
    if idem.replay:
        return _idempotent_json(idem, JSONResponse(content={}))

    body = BotCreateRequest.model_validate_json(data)
    avatar_bytes = None
    if avatar and avatar.filename:
        avatar_bytes = await avatar.read()
        if len(avatar_bytes) > 5 * 1024 * 1024:
            from app.core.exceptions import BadRequestError

            raise BadRequestError("Аватар не больше 5 МБ")

    avatar_path = None
    if avatar_bytes:
        avatar_path = bot_service.save_queued_avatar_bytes(avatar_bytes)

    spec = {
        "campaign_id": body.campaign_id,
        "telegram_account_id": body.telegram_account_id,
        "target_url": body.target_url,
        "display_name": body.display_name,
        "username": body.username,
        "description": body.description,
        "about_text": body.about_text,
        "welcome_message": body.welcome_message,
        "welcome_button_enabled": body.welcome_button_enabled,
        "welcome_button_text": body.welcome_button_text,
        "keyword": body.keyword,
        "redirect_slug": body.redirect_slug,
        "link_mode": body.link_mode,
        "create_via_botfather": body.create_via_botfather,
        "auto_start": body.auto_start,
        "generate_avatar": body.generate_avatar and not avatar_bytes,
        "use_referral_api": body.use_referral_api,
    }

    try:
        job = await job_service.start_single_bot_job(
            body.campaign_id,
            spec,
            avatar_path=avatar_path,
        )
        payload = success_response(
            data={"job": job, "queued": True},
            message="Бот поставлен в очередь создания",
        )
        await complete_idempotent(idem, {"status_code": 202, "body": payload})
        return payload
    except Exception:
        await fail_idempotent(idem)
        raise


@router.post("/import")
async def import_bots(body: BotImportRequest, _user: dict = Depends(get_current_user)):
    result = await bot_service.import_bots_batch(
        campaign_id=body.campaign_id,
        tokens=body.tokens,
    )
    return success_response(
        data=result,
        message=f"Импортировано: {result['imported_count']}, ошибок: {result['failed_count']}",
    )


@router.patch("/{bot_id}")
async def update_bot(
    bot_id: int,
    body: BotUpdateRequest,
    idem: IdempotencyContext = Depends(begin_idempotent_request),
    _user: dict = Depends(get_current_user),
):
    if idem.replay:
        return _idempotent_json(idem, JSONResponse(content={}))

    try:
        bot, sync_job = await bot_service.update_bot(bot_id, **body.model_dump(exclude_unset=True))
        if sync_job:
            task = await bot_service.enqueue_botfather_sync(
                bot_id,
                generate_avatar=sync_job.get("generate_avatar", False),
                upload_avatar=sync_job.get("upload_avatar", False),
            )
            payload = success_response(
                data={"bot": bot, "task": task, "telegram_sync_pending": True},
                message=SuccessMessages.BOT_UPDATED_SYNC_PENDING,
            )
            await complete_idempotent(idem, {"status_code": 200, "body": payload})
            return payload
        payload = success_response(data={"bot": bot}, message=SuccessMessages.BOT_UPDATED)
        await complete_idempotent(idem, {"status_code": 200, "body": payload})
        return payload
    except Exception:
        await fail_idempotent(idem)
        raise


@router.post("/{bot_id}/avatar")
async def upload_bot_avatar(
    bot_id: int,
    avatar: UploadFile = File(...),
    _user: dict = Depends(get_current_user),
):
    avatar_bytes = await avatar.read()
    bot = await bot_service.save_bot_avatar(bot_id, avatar_bytes)
    return success_response(data={"bot": bot}, message="Аватар сохранён")


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
