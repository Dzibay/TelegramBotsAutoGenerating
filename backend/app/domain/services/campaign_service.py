from typing import Any, Optional

from app.constants import ErrorMessages
from app.core.exceptions import BadRequestError, NotFoundError
from app.domain.services import referral_link_service
from app.infrastructure.database import repository as db


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _optional_text(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _campaign_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "niche_description": row.get("niche_description"),
        "keywords": list(row.get("keywords") or []),
        "resource_url": row.get("resource_url"),
        "referral_endpoint_url": row.get("referral_endpoint_url"),
        "referral_api_key": row.get("referral_api_key"),
        "default_about_text": row.get("default_about_text"),
        "default_description": row.get("default_description"),
        "default_welcome_message": row.get("default_welcome_message"),
        "status": row["status"],
        "accounts_count": int(row.get("accounts_count") or 0),
        "bots_count": int(row.get("bots_count") or 0),
        "active_bots_count": int(row.get("active_bots_count") or 0),
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


async def create_campaign(
    title: str,
    keywords: list[str] | None = None,
    resource_url: str | None = None,
    niche_description: str | None = None,
    *,
    referral_endpoint_url: str | None = None,
    referral_api_key: str | None = None,
    default_about_text: str | None = None,
    default_description: str | None = None,
    default_welcome_message: str | None = None,
) -> dict[str, Any]:
    cleaned_keywords = [k.strip() for k in (keywords or []) if k and k.strip()]
    resource = (resource_url or "").strip() or None
    row = await db.fetch_one(
        """
        INSERT INTO campaigns (
            title, niche_description, keywords, resource_url,
            referral_endpoint_url, referral_api_key,
            default_about_text, default_description, default_welcome_message
        )
        VALUES ($1, $2, $3::text[], $4, $5, $6, $7, $8, $9)
        RETURNING id, title, niche_description, keywords, resource_url,
                  referral_endpoint_url, referral_api_key,
                  default_about_text, default_description, default_welcome_message,
                  status, created_at, updated_at
        """,
        title.strip(),
        niche_description,
        cleaned_keywords,
        resource,
        _optional_text(referral_endpoint_url),
        _optional_text(referral_api_key),
        _optional_text(default_about_text),
        _optional_text(default_description),
        _optional_text(default_welcome_message),
    )
    out = _campaign_row(row)
    out["accounts_count"] = 0
    out["bots_count"] = 0
    out["active_bots_count"] = 0
    return out


async def list_campaigns() -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        """
        SELECT c.*,
               (SELECT COUNT(*)::int FROM telegram_accounts ta WHERE ta.campaign_id = c.id) AS accounts_count,
               (SELECT COUNT(*)::int FROM bots b WHERE b.campaign_id = c.id) AS bots_count,
               (SELECT COUNT(*)::int FROM bots b WHERE b.campaign_id = c.id AND b.status = 'active') AS active_bots_count
        FROM campaigns c
        ORDER BY c.created_at DESC
        """
    )
    return [_campaign_row(r) for r in rows]


async def get_campaign(campaign_id: int) -> dict[str, Any]:
    row = await db.fetch_one(
        """
        SELECT c.*,
               (SELECT COUNT(*)::int FROM telegram_accounts ta WHERE ta.campaign_id = c.id) AS accounts_count,
               (SELECT COUNT(*)::int FROM bots b WHERE b.campaign_id = c.id) AS bots_count,
               (SELECT COUNT(*)::int FROM bots b WHERE b.campaign_id = c.id AND b.status = 'active') AS active_bots_count
        FROM campaigns c
        WHERE c.id = $1
        """,
        campaign_id,
    )
    if not row:
        raise NotFoundError(ErrorMessages.CAMPAIGN_NOT_FOUND)
    return _campaign_row(row)


def _clean_keywords(keywords: list[str] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for k in keywords or []:
        text = (k or "").strip()
        if not text or len(text) < 2:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text[:100])
    return out


async def update_campaign(
    campaign_id: int,
    *,
    title: str | None = None,
    resource_url: str | None = None,
    referral_endpoint_url: str | None = None,
    referral_api_key: str | None = None,
    niche_description: str | None = None,
    keywords: list[str] | None = None,
    default_about_text: str | None = None,
    default_description: str | None = None,
    default_welcome_message: str | None = None,
) -> dict[str, Any]:
    await get_campaign(campaign_id)
    updates = []
    params: list = []
    if title is not None:
        params.append(title.strip())
        updates.append(f"title = ${len(params)}")
    if resource_url is not None:
        resource = resource_url.strip() or None
        params.append(resource)
        updates.append(f"resource_url = ${len(params)}")
    if referral_endpoint_url is not None:
        params.append(_optional_text(referral_endpoint_url))
        updates.append(f"referral_endpoint_url = ${len(params)}")
    if referral_api_key is not None:
        params.append(_optional_text(referral_api_key))
        updates.append(f"referral_api_key = ${len(params)}")
    if niche_description is not None:
        niche = niche_description.strip() or None
        params.append(niche)
        updates.append(f"niche_description = ${len(params)}")
    if keywords is not None:
        cleaned = _clean_keywords(keywords)
        params.append(cleaned)
        updates.append(f"keywords = ${len(params)}::text[]")
    if default_about_text is not None:
        params.append(_optional_text(default_about_text))
        updates.append(f"default_about_text = ${len(params)}")
    if default_description is not None:
        params.append(_optional_text(default_description))
        updates.append(f"default_description = ${len(params)}")
    if default_welcome_message is not None:
        params.append(_optional_text(default_welcome_message))
        updates.append(f"default_welcome_message = ${len(params)}")
    if not updates:
        return await get_campaign(campaign_id)

    current = await get_campaign(campaign_id)
    next_endpoint = (
        _optional_text(referral_endpoint_url)
        if referral_endpoint_url is not None
        else current.get("referral_endpoint_url")
    )
    next_key = (
        _optional_text(referral_api_key)
        if referral_api_key is not None
        else current.get("referral_api_key")
    )
    referral_link_service.validate_referral_settings(next_endpoint, next_key)

    params.append(campaign_id)
    await db.execute(
        f"UPDATE campaigns SET {', '.join(updates)}, updated_at = NOW() WHERE id = ${len(params)}",
        *params,
    )
    return await get_campaign(campaign_id)


async def get_used_keywords(campaign_id: int) -> set[str]:
    rows = await db.fetch_all(
        "SELECT DISTINCT LOWER(TRIM(keyword)) AS kw FROM bots WHERE campaign_id = $1 AND keyword IS NOT NULL",
        campaign_id,
    )
    return {r["kw"] for r in rows if r.get("kw")}


async def suggest_keyword(campaign_id: int, preferred: str | None = None) -> str | None:
    """Предлагает ключевое слово: preferred, иначе первое неиспользованное из кампании."""
    if preferred and preferred.strip():
        return preferred.strip()
    campaign = await get_campaign(campaign_id)
    used = await get_used_keywords(campaign_id)
    for kw in campaign.get("keywords") or []:
        if kw.strip().lower() not in used:
            return kw.strip()
    keywords = campaign.get("keywords") or []
    return keywords[0].strip() if keywords else None


async def generate_and_save_keywords(
    campaign_id: int,
    *,
    count: int = 10,
    merge: bool = True,
) -> dict[str, Any]:
    from app.infrastructure.ai.provider import AIService

    campaign = await get_campaign(campaign_id)
    ai = AIService()
    existing = list(campaign.get("keywords") or []) if merge else []
    generated = await ai.generate_campaign_keywords(
        niche_description=campaign.get("niche_description"),
        resource_url=campaign.get("resource_url"),
        count=count,
        existing=existing,
        campaign_id=campaign_id,
    )
    if merge:
        combined = _clean_keywords(existing + generated)
    else:
        combined = _clean_keywords(generated)
    return await update_campaign(campaign_id, keywords=combined)


async def delete_campaign(campaign_id: int) -> None:
    row = await db.fetch_one("SELECT id FROM campaigns WHERE id = $1", campaign_id)
    if not row:
        raise NotFoundError(ErrorMessages.CAMPAIGN_NOT_FOUND)
    await db.execute(
        """
        UPDATE prepared_accounts
        SET status = 'available', updated_at = NOW()
        WHERE id IN (
            SELECT prepared_account_id FROM telegram_accounts
            WHERE campaign_id = $1 AND prepared_account_id IS NOT NULL
        )
        """,
        campaign_id,
    )
    await db.execute("DELETE FROM campaigns WHERE id = $1", campaign_id)


async def list_campaign_bots(campaign_id: int) -> list[dict[str, Any]]:
    await get_campaign(campaign_id)
    rows = await db.fetch_all(
        """
        SELECT id, campaign_id, telegram_account_id, keyword, username,
               display_name, description, status, created_at
        FROM bots
        WHERE campaign_id = $1
        ORDER BY created_at DESC
        """,
        campaign_id,
    )
    return [
        {
            "id": r["id"],
            "campaign_id": r["campaign_id"],
            "telegram_account_id": r.get("telegram_account_id"),
            "keyword": r.get("keyword"),
            "username": r.get("username"),
            "display_name": r["display_name"],
            "description": r.get("description"),
            "status": r["status"],
            "created_at": _iso(r.get("created_at")),
        }
        for r in rows
    ]
