from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.constants import SuccessMessages
from app.core.dependencies import get_current_user
from app.domain.models.campaign_models import AddJobAccountsRequest
from app.domain.services import job_log_service, job_service
from app.utils.response import success_response

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
async def get_job(
    job_id: int,
    include_snapshots: bool = Query(False),
    _user: dict = Depends(get_current_user),
):
    job = await job_service.get_job(job_id, include_snapshots=include_snapshots)
    return success_response(data={"job": job})


@router.get("/{job_id}/snapshot-avatar/{row_id}")
async def get_job_snapshot_avatar(
    job_id: int,
    row_id: int,
    _user: dict = Depends(get_current_user),
):
    path = await job_service.get_job_snapshot_avatar_path(job_id, row_id)
    return FileResponse(path, media_type="image/jpeg")


@router.post("/{job_id}/retry")
async def retry_job(job_id: int, _user: dict = Depends(get_current_user)):
    job = await job_service.retry_creation_job(job_id)
    return success_response(data={"job": job}, message=SuccessMessages.JOB_STARTED)


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: int, _user: dict = Depends(get_current_user)):
    job = await job_service.cancel_job(job_id)
    return success_response(data={"job": job}, message=SuccessMessages.JOB_CANCELLED)


@router.post("/{job_id}/accounts")
async def add_job_accounts(
    job_id: int,
    body: AddJobAccountsRequest,
    _user: dict = Depends(get_current_user),
):
    job = await job_service.add_accounts_to_multi_job(job_id, body.account_ids)
    return success_response(data={"job": job}, message=SuccessMessages.JOB_ACCOUNTS_ADDED)


@router.get("/{job_id}/logs")
async def get_job_logs(
    job_id: int,
    after_id: int = Query(0, ge=0),
    min_level: str = Query("info", pattern="^(debug|info)$"),
    _user: dict = Depends(get_current_user),
):
    await job_service.get_job(job_id)
    logs = await job_log_service.list_logs(job_id, after_id=after_id, min_level=min_level)
    return success_response(data={"logs": logs})
