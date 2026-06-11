"""Запрос уникальной реферальной ссылки у внешнего API после создания бота в BotFather."""
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.exceptions import BadRequestError
from app.core.logging import get_logger
from app.domain.services import bot_promo_service

logger = get_logger(__name__)

_LINK_JSON_KEYS = ("url", "link", "referral_url", "referral_link", "href", "target_url")


def validate_referral_settings(
    endpoint_url: str | None,
    api_key: str | None,
) -> None:
    ep = (endpoint_url or "").strip()
    key = (api_key or "").strip()
    if bool(ep) != bool(key):
        raise BadRequestError(
            "Для реферальных ссылок укажите и эндпоинт, и API-ключ, либо очистите оба поля"
        )


def is_referral_configured(campaign: dict | None) -> bool:
    if not campaign:
        return False
    url = (campaign.get("referral_endpoint_url") or "").strip()
    key = (campaign.get("referral_api_key") or "").strip()
    return bool(url and key)


def referral_preview_link() -> str:
    return "https://example.com/referral"


def _normalize_username(username: str) -> str:
    uname = (username or "").strip().lstrip("@").lower()
    if not uname:
        raise BadRequestError("Username бота пустой — нельзя запросить реферальную ссылку")
    return uname


def _get_nested_str(data: dict, path: str) -> str | None:
    """Достаёт строку по пути вида data.link или referral_url."""
    cur: Any = data
    for part in path.split("."):
        part = part.strip()
        if not part or not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if isinstance(cur, str) and cur.strip():
        return cur.strip()
    return None


def _parse_link_response(resp: httpx.Response, *, response_field: str | None = None) -> str:
    text = (resp.text or "").strip()
    content_type = (resp.headers.get("content-type") or "").lower()
    field = (response_field or "").strip()

    if "json" in content_type or text.startswith("{"):
        try:
            data = resp.json()
        except Exception as exc:
            raise BadRequestError("Эндпоинт вернул некорректный JSON") from exc
        if isinstance(data, str) and data.strip():
            return bot_promo_service.normalize_target_url(data.strip())
        if isinstance(data, dict):
            if field:
                val = _get_nested_str(data, field)
                if val:
                    return bot_promo_service.normalize_target_url(val)
                raise BadRequestError(
                    f"В ответе API нет поля «{field}» со ссылкой"
                )
            for key in _LINK_JSON_KEYS:
                val = data.get(key)
                if isinstance(val, str) and val.strip():
                    return bot_promo_service.normalize_target_url(val.strip())
        raise BadRequestError(
            "Эндпоинт не вернул ссылку (ожидается URL или JSON с полем url/link/referral_url)"
        )

    if text.startswith("http"):
        return bot_promo_service.normalize_target_url(text.split()[0])

    if field:
        raise BadRequestError(
            f"Ответ не JSON — поле «{field}» можно указать только для JSON-ответов"
        )
    raise BadRequestError("Эндпоинт не вернул ссылку (ожидается URL или JSON с полем url/link)")


async def fetch_referral_link(
    endpoint_url: str,
    api_key: str,
    username: str,
    *,
    response_field: str | None = None,
) -> str:
    """POST {"token": username} + заголовок X-API-Key → URL реферальной ссылки."""
    uname = _normalize_username(username)
    endpoint = endpoint_url.strip()
    key = api_key.strip()
    payload = {"token": uname}
    headers = {"X-API-Key": key}

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
    except httpx.TimeoutException as exc:
        raise BadRequestError(
            f"Таймаут при запросе реферальной ссылки для @{uname}. Проверьте эндпоинт."
        ) from exc
    except httpx.HTTPStatusError as exc:
        body = (exc.response.text or "")[:200]
        host = urlparse(endpoint).netloc or endpoint[:48]
        hint = ""
        if exc.response.status_code == 404:
            hint = (
                " Проверьте URL эндпоинта в настройках кампании "
                "или выберите «Ссылки вручную» при массовом создании."
            )
        elif exc.response.status_code in (401, 403):
            hint = " Проверьте API-ключ в настройках кампании."
        raise BadRequestError(
            f"Реферальный API ({host}): HTTP {exc.response.status_code} для @{uname}.{hint} "
            f"Ответ: {body}",
            details={
                "step": "referral_fetch",
                "http_status": exc.response.status_code,
                "username": uname,
                "endpoint_host": host,
            },
        ) from exc
    except httpx.HTTPError as exc:
        raise BadRequestError(
            f"Не удалось получить реферальную ссылку для @{uname}: {exc}"
        ) from exc

    link = _parse_link_response(resp, response_field=response_field)
    logger.info("Referral link for @%s: %s", uname, link[:80])
    return link


async def resolve_bot_links(
    campaign: dict,
    *,
    username: str | None = None,
    target_url: str | None = None,
    link_mode: str = bot_promo_service.LINK_MODE_REDIRECT,
    redirect_slug: str | None = None,
    use_referral_api: bool | None = None,
) -> dict[str, Any]:
    """
    Ссылки для бота. Если включён реферальный API — запрашивает уникальную ссылку по username.
    Иначе — стандартный трекинг / прямая ссылка из target_url.
    """
    use_referral = (
        use_referral_api
        if use_referral_api is not None
        else is_referral_configured(campaign)
    )
    if use_referral:
        if not username:
            raise BadRequestError("Для реферального эндпоинта нужен username бота после создания в BotFather")
        link = await fetch_referral_link(
            campaign["referral_endpoint_url"],
            campaign["referral_api_key"],
            username,
            response_field=campaign.get("referral_response_field"),
        )
        return bot_promo_service.prepare_bot_links(
            link_mode=bot_promo_service.LINK_MODE_DIRECT,
            target_url=link,
            redirect_slug=None,
            ensure_slug=False,
        )

    if not (target_url or "").strip():
        raise BadRequestError(
            "Укажите ссылку на сервис в кампании или настройте эндпоинт реферальных ссылок"
        )
    return bot_promo_service.prepare_bot_links(
        link_mode=link_mode,
        target_url=target_url,
        redirect_slug=redirect_slug,
    )
