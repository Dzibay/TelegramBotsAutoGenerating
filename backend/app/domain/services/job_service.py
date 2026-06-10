import json
from pathlib import Path
from typing import Any, Optional

from app.config import Config
from app.constants import ErrorMessages
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.domain.models.campaign_models import StartManualBulkRequest
from app.domain.services import bot_promo_service, campaign_service
from app.infrastructure.cache.redis_client import get_redis
from app.infrastructure.database import repository as db
from app.utils.telegram_username import normalize_bot_username


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _job_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "campaign_id": row["campaign_id"],
        "status": row["status"],
        "total_accounts": row["total_accounts"],
        "processed_accounts": row["processed_accounts"],
        "total_bots_created": row["total_bots_created"],
        "progress_message": row.get("progress_message"),
        "error_message": row.get("error_message"),
        "started_at": _iso(row.get("started_at")),
        "finished_at": _iso(row.get("finished_at")),
        "created_at": _iso(row.get("created_at")),
    }


async def start_creation_job(
    campaign_id: int,
    plans: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    campaign = await campaign_service.get_campaign(campaign_id)
    if campaign["accounts_count"] < 1:
        raise ConflictError("Добавьте хотя бы один Telegram-аккаунт из пула подготовленных")

    ready_count = await db.fetch_val(
        """
        SELECT COUNT(*)::int FROM telegram_accounts
        WHERE campaign_id = $1 AND status IN ('ready', 'creating')
          AND tdata_path IS NOT NULL AND tdata_path != ''
        """,
        campaign_id,
    )
    if not ready_count:
        error_accounts = await db.fetch_all(
            """
            SELECT id, status, last_error FROM telegram_accounts
            WHERE campaign_id = $1
            """,
            campaign_id,
        )
        if error_accounts:
            sample = error_accounts[0]
            hint = sample.get("last_error") or sample.get("status")
            raise ConflictError(
                "Нет готовых аккаунтов для массового создания. "
                f"Откройте блок «Аккаунты» и нажмите «Проверить все». "
                f"Пример: аккаунт #{sample['id']} — {hint}"
            )
        raise ConflictError(
            "Нет готовых аккаунтов. Добавьте подготовленные аккаунты и нажмите «Проверить все»."
        )

    if not campaign.get("resource_url"):
        raise ConflictError(
            "Укажите ссылку на сервис в настройках кампании — "
            "она нужна для ссылок в ботах"
        )

    plan_list = plans or []
    if not plan_list and not campaign.get("keywords"):
        raise ConflictError(
            "Добавьте план ботов с ключевыми фразами на вкладке «Массово» "
            "или укажите ключевые слова в настройках кампании."
        )
    if plan_list:
        for p in plan_list:
            kw = (p.get("keyword") or "").strip()
            acc_id = p.get("telegram_account_id")
            if not acc_id or not kw:
                raise ConflictError("В плане каждый бот должен иметь аккаунт и ключевую фразу")

    running = await db.fetch_one(
        """
        SELECT id FROM creation_jobs
        WHERE campaign_id = $1 AND status IN ('queued', 'running')
        LIMIT 1
        """,
        campaign_id,
    )
    if running:
        raise ConflictError("Задача для этой кампании уже выполняется")

    if plan_list:
        account_ids = {int(p["telegram_account_id"]) for p in plan_list}
        total_accounts = len(account_ids)
        progress = f"В очереди: {len(plan_list)} бот(ов) по плану"
    else:
        total_accounts = await db.fetch_val(
            "SELECT COUNT(*)::int FROM telegram_accounts WHERE campaign_id = $1",
            campaign_id,
        )
        progress = "В очереди"

    row = await db.fetch_one(
        """
        INSERT INTO creation_jobs (campaign_id, status, total_accounts, progress_message)
        VALUES ($1, 'queued', $2, $3)
        RETURNING *
        """,
        campaign_id,
        total_accounts or 0,
        progress,
    )

    await db.execute(
        "UPDATE campaigns SET status = 'queued', updated_at = NOW() WHERE id = $1",
        campaign_id,
    )

    redis = get_redis()
    if not redis:
        await db.execute(
            """
            UPDATE creation_jobs SET status = 'failed', error_message = $2, updated_at = NOW()
            WHERE id = $1
            """,
            row["id"],
            "Redis недоступен — worker не получит задачу",
        )
        raise ConflictError("Redis недоступен. Запустите redis или docker compose up redis")
    payload: dict[str, Any] = {"job_id": row["id"], "campaign_id": campaign_id}
    if plan_list:
        payload["plans"] = plan_list
    await redis.lpush(Config.REDIS_JOB_QUEUE, json.dumps(payload))

    return _job_row(row)


async def get_active_job(campaign_id: int) -> dict[str, Any] | None:
    row = await db.fetch_one(
        """
        SELECT * FROM creation_jobs
        WHERE campaign_id = $1 AND status IN ('queued', 'running')
        ORDER BY id DESC
        LIMIT 1
        """,
        campaign_id,
    )
    if row:
        return _job_row(row)
    row = await db.fetch_one(
        """
        SELECT * FROM creation_jobs
        WHERE campaign_id = $1
        ORDER BY id DESC
        LIMIT 1
        """,
        campaign_id,
    )
    return _job_row(row) if row else None


async def start_manual_creation_job(
    campaign_id: int,
    *,
    body: StartManualBulkRequest,
    avatars: dict[int, bytes],
) -> dict[str, Any]:
    """Очередь ручного массового создания (worker + логи)."""
    campaign = await campaign_service.get_campaign(campaign_id)
    if campaign["accounts_count"] < 1:
        raise ConflictError("Добавьте хотя бы один Telegram-аккаунт")

    account = await db.fetch_one(
        """
        SELECT * FROM telegram_accounts
        WHERE id = $1 AND campaign_id = $2
        """,
        body.telegram_account_id,
        campaign_id,
    )
    if not account:
        raise BadRequestError("Аккаунт не найден в этой кампании")
    if account.get("status") not in ("ready", "creating") or not account.get("tdata_path"):
        raise ConflictError("Аккаунт не готов к созданию ботов. Проверьте его в разделе «Аккаунты».")

    slots = max(0, int(account["max_bots_limit"]) - int(account["bots_created"]))
    bots = body.bots
    if len(bots) > slots:
        raise ConflictError(
            f"В партии {len(bots)} ботов, свободно слотов на аккаунте: {slots}."
        )

    default_url = bot_promo_service.normalize_target_url(body.default_target_url)
    usernames_seen: set[str] = set()
    manual_plans: list[dict[str, Any]] = []

    for item in bots:
        uname = normalize_bot_username(item.username)
        if not uname:
            raise BadRequestError(f"Некорректный username в строке {item.row_id}")
        key = uname.lower()
        if key in usernames_seen:
            raise BadRequestError(f"Username @{uname} повторяется в партии")
        usernames_seen.add(key)

        row_url = (item.target_url or "").strip() or default_url
        row_url = bot_promo_service.normalize_target_url(row_url)
        manual_plans.append(
            {
                "row_id": item.row_id,
                "telegram_account_id": body.telegram_account_id,
                "display_name": item.display_name.strip(),
                "username": uname,
                "target_url": row_url,
                "description": body.shared_texts.description,
                "about_text": body.shared_texts.about_text or "",
                "welcome_message": body.shared_texts.welcome_message,
                "welcome_button_enabled": body.shared_texts.welcome_button_enabled,
                "welcome_button_text": body.shared_texts.welcome_button_text,
                "link_mode": bot_promo_service.normalize_link_mode(body.link_mode),
                "auto_start": body.auto_start,
                "avatar_path": None,
            }
        )

    running = await db.fetch_one(
        """
        SELECT id FROM creation_jobs
        WHERE campaign_id = $1 AND status IN ('queued', 'running')
        LIMIT 1
        """,
        campaign_id,
    )
    if running:
        raise ConflictError("Задача для этой кампании уже выполняется")

    total = len(manual_plans)
    row = await db.fetch_one(
        """
        INSERT INTO creation_jobs (campaign_id, status, total_accounts, progress_message)
        VALUES ($1, 'queued', $2, $3)
        RETURNING *
        """,
        campaign_id,
        total,
        f"В очереди: {total} бот(ов), ручная партия",
    )
    job_id = row["id"]

    staging = Config.STORAGE_ROOT / "job_staging" / str(job_id)
    staging.mkdir(parents=True, exist_ok=True)
    for plan in manual_plans:
        rid = int(plan["row_id"])
        raw = avatars.get(rid)
        if raw:
            path = staging / f"{rid}.jpg"
            path.write_bytes(raw)
            plan["avatar_path"] = str(path)

    await db.execute(
        "UPDATE campaigns SET status = 'queued', updated_at = NOW() WHERE id = $1",
        campaign_id,
    )

    redis = get_redis()
    if not redis:
        await db.execute(
            """
            UPDATE creation_jobs SET status = 'failed', error_message = $2, updated_at = NOW()
            WHERE id = $1
            """,
            job_id,
            "Redis недоступен — worker не получит задачу",
        )
        raise ConflictError("Redis недоступен. Запустите redis или docker compose up redis")

    payload: dict[str, Any] = {
        "job_id": job_id,
        "campaign_id": campaign_id,
        "mode": "manual",
        "manual_plans": manual_plans,
    }
    await redis.lpush(Config.REDIS_JOB_QUEUE, json.dumps(payload))

    if not campaign.get("resource_url"):
        await campaign_service.update_campaign(campaign_id, resource_url=default_url)

    return _job_row(row)


async def get_job(job_id: int) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM creation_jobs WHERE id = $1", job_id)
    if not row:
        raise NotFoundError(ErrorMessages.JOB_NOT_FOUND)
    return _job_row(row)


async def _reset_creating_accounts(campaign_id: int) -> None:
    await db.execute(
        """
        UPDATE telegram_accounts
        SET status = CASE
            WHEN bots_created >= max_bots_limit THEN 'exhausted'
            ELSE 'ready'
        END,
        updated_at = NOW()
        WHERE campaign_id = $1 AND status = 'creating'
        """,
        campaign_id,
    )


async def cancel_job(job_id: int) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM creation_jobs WHERE id = $1", job_id)
    if not row:
        raise NotFoundError(ErrorMessages.JOB_NOT_FOUND)
    if row["status"] not in ("queued", "running"):
        raise ConflictError("Задача уже завершена и не может быть отменена")

    campaign_id = int(row["campaign_id"])
    total_created = int(row.get("total_bots_created") or 0)

    await db.execute(
        """
        UPDATE creation_jobs
        SET status = 'cancelled',
            finished_at = NOW(),
            progress_message = 'Отменено пользователем',
            updated_at = NOW()
        WHERE id = $1
        """,
        job_id,
    )
    await _reset_creating_accounts(campaign_id)

    camp_status = "completed" if total_created > 0 else "draft"
    await db.execute(
        "UPDATE campaigns SET status = $2, updated_at = NOW() WHERE id = $1",
        campaign_id,
        camp_status,
    )

    from app.domain.services import job_log_service

    await job_log_service.append_log(
        job_id,
        "Задача отменена пользователем",
        level="warn",
        progress_message="Отменено",
    )

    updated = await db.fetch_one("SELECT * FROM creation_jobs WHERE id = $1", job_id)
    return _job_row(updated)
