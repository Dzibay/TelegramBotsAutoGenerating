import json
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel, Field

from app.constants import HTTPStatus
from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequestError
from app.domain.services import prep_job_service, prep_log_service
from app.utils.response import success_response

router = APIRouter(prefix="/account-prep", tags=["account-prep"])


class PrepOptionsModel(BaseModel):
    terminate_sessions: bool = True
    change_password: bool = True
    privacy_restrictions: bool = True


@router.get("/jobs")
async def list_jobs(_user: dict = Depends(get_current_user)):
    jobs = await prep_job_service.list_prep_jobs()
    return success_response(data={"jobs": jobs})


@router.get("/jobs/{job_id}")
async def get_job(job_id: int, _user: dict = Depends(get_current_user)):
    job = await prep_job_service.get_prep_job(job_id)
    accounts = await prep_job_service.list_prep_accounts(job_id)
    return success_response(data={"job": job, "accounts": accounts})


@router.get("/jobs/{job_id}/logs")
async def get_logs(
    job_id: int,
    after_id: int = Query(0, ge=0),
    _user: dict = Depends(get_current_user),
):
    await prep_job_service.get_prep_job(job_id)
    logs = await prep_log_service.list_logs(job_id, after_id=after_id)
    return success_response(data={"logs": logs})


@router.post("/jobs", status_code=HTTPStatus.CREATED)
async def create_prep_job(
    files: List[UploadFile] = File(...),
    options_json: str = Form(
        '{"terminate_sessions":true,"change_password":true,"privacy_restrictions":true}'
    ),
    new_password: Optional[str] = Form(None),
    current_password: Optional[str] = Form(None),
    password_hint: str = Form(""),
    auto_start: str = Form("true"),
    _user: dict = Depends(get_current_user),
):
    if not files:
        raise BadRequestError("Загрузите ZIP с tdata")

    try:
        options = json.loads(options_json)
    except json.JSONDecodeError:
        raise BadRequestError("Некорректный JSON опций")

    tmp_paths: list[Path] = []
    batch: list[tuple[Path, str | None]] = []
    try:
        for f in files:
            suffix = Path(f.filename or "tdata.zip").suffix or ".zip"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(await f.read())
            tmp.close()
            p = Path(tmp.name)
            tmp_paths.append(p)
            batch.append((p, Path(f.filename or "").stem or None))
        job = await prep_job_service.create_prep_job(
            options,
            batch,
            new_password=new_password,
            current_password=current_password,
            password_hint=password_hint,
            auto_start=auto_start.lower() in ("1", "true", "yes", "on"),
        )
    finally:
        for p in tmp_paths:
            p.unlink(missing_ok=True)

    return success_response(data={"job": job}, message="Задача подготовки создана")


@router.post("/jobs/{job_id}/start")
async def start_job(
    job_id: int,
    new_password: Optional[str] = Form(None),
    current_password: Optional[str] = Form(None),
    password_hint: str = Form(""),
    _user: dict = Depends(get_current_user),
):
    job = await prep_job_service.start_prep_job(
        job_id,
        new_password=new_password,
        current_password=current_password,
        password_hint=password_hint,
    )
    return success_response(data={"job": job}, message="Задача запущена")
