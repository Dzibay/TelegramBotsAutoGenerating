from typing import Any, Optional

from app.constants import ErrorMessages
from app.core.exceptions import NotFoundError
from app.infrastructure.database import repository as db


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _campaign_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "niche_description": row.get("niche_description"),
        "keywords": list(row.get("keywords") or []),
        "resource_url": row["resource_url"],
        "status": row["status"],
        "accounts_count": int(row.get("accounts_count") or 0),
        "bots_count": int(row.get("bots_count") or 0),
        "active_bots_count": int(row.get("active_bots_count") or 0),
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


async def create_campaign(
    title: str,
    keywords: list[str],
    resource_url: str,
    niche_description: str | None = None,
) -> dict[str, Any]:
    cleaned_keywords = [k.strip() for k in keywords if k and k.strip()]
    row = await db.fetch_one(
        """
        INSERT INTO campaigns (title, niche_description, keywords, resource_url)
        VALUES ($1, $2, $3::text[], $4)
        RETURNING id, title, niche_description, keywords, resource_url, status, created_at, updated_at
        """,
        title.strip(),
        niche_description,
        cleaned_keywords,
        resource_url.strip(),
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
