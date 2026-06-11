from fastapi import APIRouter, Depends

from app.constants import SuccessMessages
from app.core.dependencies import get_current_user
from app.domain.models.settings_models import BotfatherPacingSettings
from app.domain.services import settings_service
from app.utils.response import success_response

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/botfather-pacing")
async def get_botfather_pacing(_user: dict = Depends(get_current_user)):
    pacing = settings_service.get_botfather_pacing()
    return success_response(data={"botfather_pacing": pacing.model_dump()})


@router.put("/botfather-pacing")
async def update_botfather_pacing(
    body: BotfatherPacingSettings,
    _user: dict = Depends(get_current_user),
):
    pacing = settings_service.update_botfather_pacing(body)
    return success_response(
        data={"botfather_pacing": pacing.model_dump()},
        message=SuccessMessages.SETTINGS_SAVED,
    )
