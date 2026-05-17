"""Публичный редирект /go/{slug} с подсчётом кликов."""
from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.domain.services import bot_promo_service

router = APIRouter(tags=["redirect"])


@router.get("/go/{slug}")
async def redirect_promo(slug: str):
    info = await bot_promo_service.record_click(slug)
    return RedirectResponse(url=info["target_url"], status_code=302)
