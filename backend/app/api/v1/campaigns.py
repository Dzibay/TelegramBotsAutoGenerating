import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.constants import HTTPStatus, SuccessMessages
from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequestError
from app.domain.models.bot_models import CampaignUpdateRequest
from app.domain.models.campaign_models import (
    CampaignCreateRequest,
    GenerateKeywordsRequest,
    StartCreationJobRequest,
)
from app.domain.services import account_health, account_service, campaign_service, job_service, prepared_account_service
from app.utils.response import success_response

_PREP_ONLY_MSG = (
    "Загрузка ZIP в кампанию отключена. "
    "Сначала подготовьте аккаунты на странице «Подготовка аккаунтов», затем выберите их здесь."
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


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

    if not prepared_ids:
        raise BadRequestError("Выберите хотя бы один подготовленный аккаунт")

    campaign = await campaign_service.create_campaign(
        title=body.title,
        keywords=body.keywords,
        resource_url=body.resource_url,
        niche_description=body.niche_description,
    )
    campaign_id = campaign["id"]

    uploaded = await prepared_account_service.attach_to_campaign(campaign_id, prepared_ids)
    await account_health.verify_all_accounts(campaign_id)

    job = None
    if auto_start.lower() in ("1", "true", "yes", "on"):
        job = await job_service.start_creation_job(campaign_id)

    campaign = await campaign_service.get_campaign(campaign_id)
    return success_response(
        data={"campaign": campaign, "accounts": uploaded, "job": job},
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
        niche_description=body.niche_description,
        keywords=body.keywords,
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
    job = await job_service.get_active_job(campaign_id)
    return success_response(data={"campaign": campaign, "active_job": job})


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
    _user: dict = Depends(get_current_user),
):
    plans = None
    if body and body.plans:
        plans = [p.model_dump() for p in body.plans]
    job = await job_service.start_creation_job(campaign_id, plans=plans)
    return success_response(data={"job": job}, message=SuccessMessages.JOB_STARTED)
