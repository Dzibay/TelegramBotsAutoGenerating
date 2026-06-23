from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.domain.services import task_service
from app.utils.response import success_response

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    active_only: bool = Query(False),
    campaign_id: int | None = Query(None),
    bot_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: dict = Depends(get_current_user),
):
    tasks = await task_service.list_tasks(
        active_only=active_only,
        campaign_id=campaign_id,
        bot_id=bot_id,
        limit=limit,
        offset=offset,
    )
    return success_response(
        data={
            "tasks": tasks,
            "active_count": await task_service.active_count(),
        }
    )


@router.get("/{task_id}")
async def get_task(task_id: int, _user: dict = Depends(get_current_user)):
    task = await task_service.get_task(task_id)
    return success_response(data={"task": task})


@router.get("/{task_id}/logs")
async def get_task_logs(
    task_id: int,
    after_id: int = Query(0, ge=0),
    min_level: str = Query("info", pattern="^(debug|info)$"),
    _user: dict = Depends(get_current_user),
):
    await task_service.get_task(task_id)
    logs = await task_service.list_logs(task_id, after_id=after_id, min_level=min_level)
    return success_response(data={"logs": logs})


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: int, _user: dict = Depends(get_current_user)):
    task = await task_service.cancel_task(task_id)
    return success_response(data={"task": task}, message="Задача отменена")


@router.post("/{task_id}/retry")
async def retry_task(task_id: int, _user: dict = Depends(get_current_user)):
    task = await task_service.retry_task(task_id)
    return success_response(data={"task": task}, message="Задача поставлена на повтор")
