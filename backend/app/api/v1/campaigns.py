import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from app.constants import HTTPStatus, SuccessMessages
from app.core.dependencies import begin_idempotent_request, get_current_user
from app.core.idempotency import IdempotencyContext, complete_idempotent, fail_idempotent
from app.core.exceptions import BadRequestError
from app.domain.models.bot_models import CampaignUpdateRequest
from app.domain.models.campaign_models import (
    AccountUpdateRequest,
    CampaignCreateRequest,
    GenerateKeywordsRequest,
    StartCreationJobRequest,
    StartManualBulkRequest,
)
from app.domain.services import account_health, account_service, campaign_service, job_service, prepared_account_service
from app.utils.response import success_response

_PREP_ONLY_MSG = (
    "Загрузка ZIP в кампанию отключена. "
    "Сначала подготовьте аккаунты на странице «Подготовка аккаунтов», затем выберите их здесь."
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _idempotent_json(ctx: IdempotencyContext, response: JSONResponse) -> JSONResponse:
    if ctx.replay:
        body = ctx.replay.get("body") or ctx.replay
        status = int(ctx.replay.get("status_code") or 200)
        return JSONResponse(content=body, status_code=status)
    return response


@router.get("")
async def list_campaigns(_user: dict = Depends(get_current_user)):
    items = await campaign_service.list_campaigns()
    return success_response(data={"campaigns": items})


@router.post("", status_code=HTTPStatus.CREATED)
async def create_campaign(
    body: CampaignCreateRequest,
    _user: dict = Depends(get_current_user),
):
    campaign = await campaign_service.create_campaign(
        title=body.title,
        keywords=body.keywords,
        resource_url=body.resource_url,
        niche_description=body.niche_description,
        default_about_text=body.default_about_text,
        default_description=body.default_description,
        default_welcome_message=body.default_welcome_message,
        default_welcome_button_enabled=body.default_welcome_button_enabled,
        default_welcome_button_text=body.default_welcome_button_text,
    )
    return success_response(data={"campaign": campaign}, message=SuccessMessages.CAMPAIGN_CREATED)


@router.post("/create-full", status_code=HTTPStatus.CREATED)
async def create_campaign_full(
    data: str = Form(..., description="JSON CampaignCreateRequest"),
    prepared_account_ids: str = Form("[]", description="JSON-массив id из пула подготовленных"),
    auto_start: str = Form("true"),
    _user: dict = Depends(get_current_user),
):
    """Создание кампании + привязка подготовленных аккаунтов из пула."""
    body = CampaignCreateRequest.model_validate_json(data)
    try:
        ids = json.loads(prepared_account_ids)
        if not isinstance(ids, list):
            raise ValueError("expected array")
        prepared_ids = [int(x) for x in ids]
    except (json.JSONDecodeError, TypeError, ValueError):
        raise BadRequestError("Некорректный список prepared_account_ids")

    campaign = await campaign_service.create_campaign(
        title=body.title,
        keywords=body.keywords,
        resource_url=body.resource_url,
        niche_description=body.niche_description,
        default_about_text=body.default_about_text,
        default_description=body.default_description,
        default_welcome_message=body.default_welcome_message,
        default_welcome_button_enabled=body.default_welcome_button_enabled,
        default_welcome_button_text=body.default_welcome_button_text,
    )
    campaign_id = campaign["id"]

    uploaded: list = []
    verify_summary = None
    if prepared_ids:
        uploaded = await prepared_account_service.attach_to_campaign(campaign_id, prepared_ids)
        verify_result = await account_health.verify_all_accounts(campaign_id)
        verify_summary = {
            "total": verify_result["total"],
            "verified_ok": verify_result["verified_ok"],
            "verified_failed": verify_result["verified_failed"],
        }

    job = None
    if prepared_ids and auto_start.lower() in ("1", "true", "yes", "on"):
        job = await job_service.start_creation_job(campaign_id)

    campaign = await campaign_service.get_campaign(campaign_id)
    return success_response(
        data={
            "campaign": campaign,
            "accounts": uploaded,
            "job": job,
            "verify_summary": verify_summary,
        },
        message=SuccessMessages.CAMPAIGN_CREATED,
    )


@router.patch("/{campaign_id}")
async def update_campaign(
    campaign_id: int,
    body: CampaignUpdateRequest,
    _user: dict = Depends(get_current_user),
):
    campaign = await campaign_service.update_campaign(
        campaign_id,
        title=body.title,
        resource_url=body.resource_url,
        referral_endpoint_url=body.referral_endpoint_url,
        referral_api_key=body.referral_api_key,
        referral_response_field=body.referral_response_field,
        niche_description=body.niche_description,
        keywords=body.keywords,
        default_about_text=body.default_about_text,
        default_description=body.default_description,
        default_welcome_message=body.default_welcome_message,
        default_welcome_button_enabled=body.default_welcome_button_enabled,
        default_welcome_button_text=body.default_welcome_button_text,
    )
    return success_response(data={"campaign": campaign}, message=SuccessMessages.CAMPAIGN_UPDATED)


@router.post("/{campaign_id}/generate-keywords")
async def generate_campaign_keywords(
    campaign_id: int,
    body: GenerateKeywordsRequest,
    _user: dict = Depends(get_current_user),
):
    campaign = await campaign_service.generate_and_save_keywords(
        campaign_id,
        count=body.count,
        merge=body.merge,
    )
    return success_response(
        data={"campaign": campaign, "keywords": campaign.get("keywords", [])},
        message="Ключевые слова сгенерированы",
    )


@router.get("/{campaign_id}/suggest-keyword")
async def suggest_keyword(
    campaign_id: int,
    preferred: Optional[str] = None,
    _user: dict = Depends(get_current_user),
):
    keyword = await campaign_service.suggest_keyword(campaign_id, preferred)
    used = await campaign_service.get_used_keywords(campaign_id)
    campaign = await campaign_service.get_campaign(campaign_id)
    return success_response(
        data={
            "keyword": keyword,
            "keywords": campaign.get("keywords", []),
            "used_keywords": sorted(used),
        }
    )


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: int, _user: dict = Depends(get_current_user)):
    await campaign_service.delete_campaign(campaign_id)
    return success_response(message=SuccessMessages.CAMPAIGN_DELETED)


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: int, _user: dict = Depends(get_current_user)):
    campaign = await campaign_service.get_campaign(campaign_id)
    active_jobs = await job_service.list_active_jobs(campaign_id)
    return success_response(
        data={
            "campaign": campaign,
            "active_job": active_jobs[-1] if active_jobs else None,
            "active_jobs": active_jobs,
        }
    )


@router.get("/{campaign_id}/bots")
async def list_bots(campaign_id: int, _user: dict = Depends(get_current_user)):
    bots = await campaign_service.list_campaign_bots(campaign_id)
    return success_response(data={"bots": bots})


@router.get("/{campaign_id}/accounts")
async def list_accounts(campaign_id: int, _user: dict = Depends(get_current_user)):
    accounts = await account_service.list_accounts(campaign_id)
    return success_response(data={"accounts": accounts})


@router.post("/{campaign_id}/accounts/from-prepared", status_code=HTTPStatus.CREATED)
async def attach_prepared_accounts(
    campaign_id: int,
    prepared_account_ids: str = Form(..., description="JSON-массив id подготовленных аккаунтов"),
    _user: dict = Depends(get_current_user),
):
    try:
        ids = json.loads(prepared_account_ids)
        prepared_ids = [int(x) for x in ids]
    except (json.JSONDecodeError, TypeError, ValueError):
        raise BadRequestError("Некорректный список prepared_account_ids")
    if not prepared_ids:
        raise BadRequestError("Выберите хотя бы один подготовленный аккаунт")

    accounts = await prepared_account_service.attach_to_campaign(campaign_id, prepared_ids)
    verify_result = await account_health.verify_all_accounts(campaign_id)
    return success_response(
        data={
            "accounts": verify_result["accounts"],
            "verify_summary": {
                "total": verify_result["total"],
                "verified_ok": verify_result["verified_ok"],
                "verified_failed": verify_result["verified_failed"],
            },
        },
        message=SuccessMessages.ACCOUNT_UPLOADED,
    )


@router.post("/{campaign_id}/accounts", status_code=HTTPStatus.CREATED)
async def upload_account(
    campaign_id: int,
    file: UploadFile = File(...),
    label: Optional[str] = Form(None),
    _user: dict = Depends(get_current_user),
):
    raise BadRequestError(_PREP_ONLY_MSG)


@router.post("/{campaign_id}/accounts/batch", status_code=HTTPStatus.CREATED)
async def upload_accounts_batch(
    campaign_id: int,
    files: List[UploadFile] = File(...),
    _user: dict = Depends(get_current_user),
):
    raise BadRequestError(_PREP_ONLY_MSG)


@router.post("/{campaign_id}/accounts/verify-all")
async def verify_all_accounts(campaign_id: int, _user: dict = Depends(get_current_user)):
    result = await account_health.verify_all_accounts(campaign_id)
    return success_response(data=result)


@router.post("/{campaign_id}/accounts/{account_id}/verify")
async def verify_account(
    campaign_id: int,
    account_id: int,
    _user: dict = Depends(get_current_user),
):
    account = await account_health.verify_account(campaign_id, account_id)
    return success_response(data={"account": account})


@router.get("/{campaign_id}/accounts/{account_id}/bots")
async def list_account_bots(
    campaign_id: int,
    account_id: int,
    _user: dict = Depends(get_current_user),
):
    data = await account_service.list_account_bots(campaign_id, account_id)
    return success_response(data=data)


@router.delete("/{campaign_id}/accounts/{account_id}/bots/{username}")
async def delete_account_bot(
    campaign_id: int,
    account_id: int,
    username: str,
    _user: dict = Depends(get_current_user),
):
    data = await account_service.delete_account_bot(campaign_id, account_id, username)
    return success_response(data=data, message="Бот удалён")


@router.patch("/{campaign_id}/accounts/{account_id}")
async def update_account(
    campaign_id: int,
    account_id: int,
    body: AccountUpdateRequest,
    _user: dict = Depends(get_current_user),
):
    account = await account_service.update_account(
        campaign_id,
        account_id,
        label=body.label,
        is_banned=body.is_banned,
        patch_label="label" in body.model_fields_set,
        patch_banned="is_banned" in body.model_fields_set,
    )
    return success_response(data={"account": account}, message="Настройки аккаунта обновлены")


@router.delete("/{campaign_id}/accounts/{account_id}")
async def remove_account(
    campaign_id: int,
    account_id: int,
    _user: dict = Depends(get_current_user),
):
    await account_service.remove_from_campaign(campaign_id, account_id)
    return success_response(message="Аккаунт удалён из кампании")


@router.post("/{campaign_id}/start")
async def start_campaign(
    campaign_id: int,
    body: StartCreationJobRequest | None = None,
    idem: IdempotencyContext = Depends(begin_idempotent_request),
    _user: dict = Depends(get_current_user),
):
    if idem.replay:
        return _idempotent_json(idem, JSONResponse(content={}))
    plans = None
    if body and body.plans:
        plans = [p.model_dump() for p in body.plans]
    try:
        job = await job_service.start_creation_job(campaign_id, plans=plans)
        payload = success_response(data={"job": job}, message=SuccessMessages.JOB_STARTED)
        await complete_idempotent(idem, {"status_code": 200, "body": payload})
        return payload
    except Exception:
        await fail_idempotent(idem)
        raise


@router.get("/{campaign_id}/jobs")
async def list_campaign_jobs(
    campaign_id: int,
    limit: int = 50,
    offset: int = 0,
    active_only: bool = False,
    _user: dict = Depends(get_current_user),
):
    if active_only:
        jobs = await job_service.list_active_jobs(campaign_id)
    else:
        jobs = await job_service.list_creation_jobs(campaign_id, limit=limit, offset=offset)
    return success_response(data={"jobs": jobs})


@router.post("/{campaign_id}/start-manual-bulk")
async def start_manual_bulk(
    campaign_id: int,
    request: Request,
    idem: IdempotencyContext = Depends(begin_idempotent_request),
    _user: dict = Depends(get_current_user),
):
    if idem.replay:
        return _idempotent_json(idem, JSONResponse(content={}))
    form = await request.form()
    raw = form.get("data")
    if not raw:
        raise BadRequestError("Отсутствует поле data")
    body = StartManualBulkRequest.model_validate_json(raw)
    avatars: dict[int, bytes] = {}
    for key in form.keys():
        if not str(key).startswith("avatar_"):
            continue
        try:
            row_id = int(str(key).split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        upload = form[key]
        if not hasattr(upload, "read"):
            continue
        raw_bytes = await upload.read()
        if len(raw_bytes) > 5 * 1024 * 1024:
            raise BadRequestError(f"Аватар в строке {row_id} больше 5 МБ")
        if raw_bytes:
            avatars[row_id] = raw_bytes
    try:
        job = await job_service.start_manual_creation_job(
            campaign_id,
            body=body,
            avatars=avatars,
        )
        payload = success_response(data={"job": job}, message=SuccessMessages.JOB_STARTED)
        await complete_idempotent(idem, {"status_code": 200, "body": payload})
        return payload
    except Exception:
        await fail_idempotent(idem)
        raise
