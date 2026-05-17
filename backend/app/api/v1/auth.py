from fastapi import APIRouter, Depends

from app.constants import SuccessMessages
from app.core.dependencies import get_current_user
from app.domain.models.auth_models import LoginRequest
from app.domain.services import auth_service
from app.utils.jwt import create_access_token
from app.utils.response import success_response

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(data: LoginRequest):
    user = auth_service.login(data.password)
    token = create_access_token(user["id"], user["role"])
    return success_response(
        data={"user": user, "access_token": token},
        message=SuccessMessages.LOGIN_SUCCESS,
    )


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return success_response(data={"user": current_user})
