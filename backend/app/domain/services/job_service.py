import json
from pathlib import Path
from typing import Any, Optional

from app.config import Config
from app.constants import ErrorMessages
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.domain.models.campaign_models import StartManualBulkRequest
from app.domain.services import bot_promo_service, campaign_service, referral_link_service
from app.domain.services import job_history_service, task_service
from app.infrastructure.cache.redis_client import get_redis
from app.infrastructure.database import repository as db
from app.utils.telegram_username import normalize_bot_username


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _job_account_ids(row: dict[str, Any]) -> set[int]:
    raw = row.get("account_ids") or []
    ids = {int(x) for x in raw if x is not None}
    primary = row.get("telegram_account_id")
    if primary:
        ids.add(int(primary))
    return ids


def _format_account_label(row: dict[str, Any]) -> str | None:
    label = row.get("account_label")
    if label and str(label).strip():
        return str(label).strip()
    account_ids = _job_account_ids(row)
    if len(account_ids) == 1:
        return f"Аккаунт #{next(iter(account_ids))}"
    if len(account_ids) > 1:
        return f"{len(account_ids)} акк."
    if row.get("job_mode") == "auto":
        return "все аккаунты"
    return None


def _job_row(row: dict[str, Any], *, include_snapshots: bool = False) -> dict[str, Any]:
    summary = job_history_service.job_history_summary(row)
    account_ids = sorted(_job_account_ids(row))
    out = {
        "id": row["id"],
        "task_id": row.get("task_id"),
        "campaign_id": row["campaign_id"],
        "status": row["status"],
        "job_mode": row.get("job_mode"),
        "telegram_account_id": row.get("telegram_account_id"),
        "account_ids": account_ids,
        "account_label": _format_account_label(row),
        "retried_from_job_id": row.get("retried_from_job_id"),
        "total_accounts": row["total_accounts"],
        "processed_accounts": row["processed_accounts"],
        "total_bots_created": row["total_bots_created"],
        "progress_message": row.get("progress_message"),
        "error_message": row.get("error_message"),
        "started_at": _iso(row.get("started_at")),
        "finished_at": _iso(row.get("finished_at")),
        "created_at": _iso(row.get("created_at")),
        "retry_available": summary["retry_available"],
        "retry_count": summary["retry_count"],
        "total_failed": summary["total_failed"],
        "total_skipped": summary["total_skipped"],
    }
    if include_snapshots:
        out["input_snapshot"] = job_history_service.parse_json_field(row.get("input_snapshot"))
        out["result_snapshot"] = job_history_service.parse_json_field(row.get("result_snapshot"))
    return out


async def sync_campaign_status(campaign_id: int) -> None:
    """Статус кампании по активным и завершённым задачам."""
    active = await db.fetch_val(
        """
        SELECT COUNT(*)::int FROM creation_jobs
        WHERE campaign_id = $1 AND status IN ('queued', 'running')
        """,
        campaign_id,
    )
    if active:
        await db.execute(
            "UPDATE campaigns SET status = 'running', updated_at = NOW() WHERE id = $1",
            campaign_id,
        )
        return

    stats = await db.fetch_one(
        """
        SELECT
            COALESCE(SUM(total_bots_created), 0)::int AS total_created,
            BOOL_OR(status = 'failed') AS any_failed
        FROM creation_jobs
        WHERE campaign_id = $1
          AND status IN ('completed', 'failed', 'cancelled')
        """,
        campaign_id,
    )
    total_created = int(stats["total_created"] or 0)
    if total_created > 0:
        camp_status = "completed"
    elif stats["any_failed"]:
        camp_status = "failed"
    else:
        camp_status = "draft"
    await db.execute(
        "UPDATE campaigns SET status = $2, updated_at = NOW() WHERE id = $1",
        campaign_id,
        camp_status,
    )


async def _find_account_conflicts(
    campaign_id: int,
    account_ids: set[int],
    *,
    is_auto: bool = False,
    exclude_job_id: int | None = None,
    conn=None,
) -> list[dict[str, Any]]:
    query = """
        SELECT j.*, ta.label AS account_label, ta.phone AS account_phone
        FROM creation_jobs j
        LEFT JOIN telegram_accounts ta ON ta.id = j.telegram_account_id
        WHERE j.campaign_id = $1 AND j.status IN ('queued', 'running')
        ORDER BY j.id
    """
    if conn is not None:
        rows = await db.tx_fetch_all(conn, query, campaign_id)
    else:
        rows = await db.fetch_all(query, campaign_id)
    conflicts: list[dict[str, Any]] = []
    for row in rows:
        if exclude_job_id and int(row["id"]) == exclude_job_id:
            continue
        mode = row.get("job_mode")
        job_accounts = _job_account_ids(row)
        if is_auto or mode == "auto":
            conflicts.append(row)
            continue
        if account_ids & job_accounts:
            conflicts.append(row)
    return conflicts


async def _enqueue_creation_payload(payload: dict[str, Any]) -> None:
    if payload.get("task_id"):
        await task_service.signal_task(int(payload["task_id"]))
        return
    redis = get_redis()
    if not redis:
        job_id = payload.get("job_id")
        if job_id:
            await db.execute(
                """
                UPDATE creation_jobs SET status = 'failed', error_message = $2, updated_at = NOW()
                WHERE id = $1
                """,
                job_id,
                "Redis недоступен — worker не получит задачу",
            )
        raise ConflictError("Redis недоступен. Запустите redis или docker compose up redis")
    await redis.lpush(Config.REDIS_JOB_QUEUE, json.dumps(payload))


async def _create_creation_task(
    row: dict[str, Any],
    payload: dict[str, Any],
    *,
    account_ids: set[int],
    exclusive_campaign: bool = False,
    progress_message: str | None = None,
) -> dict[str, Any]:
    task_payload = {
        **payload,
        "exclusive_campaign": exclusive_campaign,
    }
    task = await task_service.enqueue_task(
        task_type=task_service.TASK_TYPE_CREATION,
        payload=task_payload,
        campaign_id=int(row["campaign_id"]),
        creation_job_id=int(row["id"]),
        account_ids=account_ids,
        progress_message=progress_message or row.get("progress_message"),
        signal=False,
    )
    await db.execute(
        """
        UPDATE creation_jobs
        SET task_id = $2, updated_at = NOW()
        WHERE id = $1
        """,
        row["id"],
        task["id"],
    )
    await _enqueue_creation_payload({"task_id": task["id"]})
    return task


async def verify_job_accounts_available(
    job_id: int,
    campaign_id: int,
    account_ids: set[int],
    *,
    is_auto: bool = False,
) -> bool:
    """False = аккаунты заняты другой задачей (нужно отложить)."""
    conflicts = await _find_account_conflicts(
        campaign_id,
        account_ids,
        is_auto=is_auto,
        exclude_job_id=job_id,
    )
    return not conflicts


def _conflict_message(conflicts: list[dict[str, Any]], account_ids: set[int]) -> str:
    if not conflicts:
        return "Задача уже выполняется"
    first = conflicts[0]
    mode = first.get("job_mode")
    if mode == "auto" or not account_ids:
        return "Уже выполняется автоматическая задача — дождитесь завершения или остановите её"
    if len(account_ids) > 3:
        return "Аккаунты заняты другими задачами — дождитесь завершения активных задач"
    label = _format_account_label(first) or f"#{first.get('telegram_account_id') or next(iter(account_ids))}"
    if len(conflicts) == 1:
        return f"На аккаунте «{label}» уже выполняется задача #{first['id']}"
    ids = ", ".join(f"#{c['id']}" for c in conflicts[:3])
    return f"Аккаунты заняты другими задачами: {ids}"


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
          AND is_banned = FALSE
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

    if plan_list:
        account_ids = {int(p["telegram_account_id"]) for p in plan_list}
        banned_rows = await db.fetch_all(
            """
            SELECT id, label, phone FROM telegram_accounts
            WHERE campaign_id = $1 AND id = ANY($2::bigint[]) AND is_banned = TRUE
            """,
            campaign_id,
            list(account_ids),
        )
        if banned_rows:
            sample = banned_rows[0]
            name = (sample.get("label") or "").strip() or f"Аккаунт #{sample['id']}"
            raise ConflictError(
                f"Аккаунт {name} забанен и не может использоваться для создания ботов"
            )
        total_accounts = len(account_ids)
        progress = f"В очереди: {len(plan_list)} бот(ов) по плану"
        job_mode = "planned"
        primary_account_id = None
    else:
        account_ids = set()
        total_accounts = await db.fetch_val(
            "SELECT COUNT(*)::int FROM telegram_accounts WHERE campaign_id = $1",
            campaign_id,
        )
        progress = "В очереди"
        job_mode = "auto"
        primary_account_id = None

    async with db.transaction() as conn:
        await db.tx_execute(conn, "SELECT pg_advisory_xact_lock($1)", campaign_id)
        row = await db.tx_fetch_one(
            conn,
            """
            INSERT INTO creation_jobs (
                campaign_id, status, total_accounts, progress_message, job_mode,
                telegram_account_id, account_ids
            )
            VALUES ($1, 'queued', $2, $3, $4, $5, $6)
            RETURNING *
            """,
            campaign_id,
            total_accounts or 0,
            progress,
            job_mode,
            primary_account_id,
            list(account_ids),
        )

    snapshot = (
        job_history_service.build_planned_input_snapshot(plan_list)
        if plan_list
        else job_history_service.build_auto_input_snapshot()
    )
    await job_history_service.persist_input_snapshot(
        row["id"],
        job_mode=job_mode,
        snapshot=snapshot,
    )

    await db.execute(
        "UPDATE campaigns SET status = 'queued', updated_at = NOW() WHERE id = $1",
        campaign_id,
    )
    await sync_campaign_status(campaign_id)

    payload: dict[str, Any] = {"job_id": row["id"], "campaign_id": campaign_id}
    if plan_list:
        payload["plans"] = plan_list
    await _create_creation_task(
        row,
        payload,
        account_ids=account_ids,
        exclusive_campaign=job_mode == "auto",
        progress_message=progress,
    )

    return _job_row(row)


async def start_single_bot_job(
    campaign_id: int,
    spec: dict[str, Any],
    *,
    avatar_path: str | None = None,
) -> dict[str, Any]:
    """Очередь создания одного бота (job_mode=single)."""
    await campaign_service.get_campaign(campaign_id)
    account_id = int(spec["telegram_account_id"])
    account_ids = {account_id}

    async with db.transaction() as conn:
        await db.tx_execute(conn, "SELECT pg_advisory_xact_lock($1)", campaign_id)
        row = await db.tx_fetch_one(
            conn,
            """
            INSERT INTO creation_jobs (
                campaign_id, status, total_accounts, progress_message, job_mode,
                telegram_account_id, account_ids
            )
            VALUES ($1, 'queued', 1, $2, 'single', $3, $4)
            RETURNING *
            """,
            campaign_id,
            f"В очереди: @{spec.get('username', '?')}",
            account_id,
            list(account_ids),
        )

    job_id = row["id"]
    snapshot = {
        "mode": "single",
        "spec": spec,
        "avatar_path": avatar_path,
    }
    await job_history_service.persist_input_snapshot(job_id, job_mode="single", snapshot=snapshot)
    await sync_campaign_status(campaign_id)

    await _create_creation_task(
        row,
        {
            "job_id": job_id,
            "campaign_id": campaign_id,
            "mode": "single",
            "spec": spec,
            "avatar_path": avatar_path,
        },
        account_ids=account_ids,
        progress_message=f"В очереди: @{spec.get('username', '?')}",
    )
    return _job_row(row)


async def list_active_jobs(campaign_id: int) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        """
        SELECT j.*, ta.label AS account_label, ta.phone AS account_phone
        FROM creation_jobs j
        LEFT JOIN telegram_accounts ta ON ta.id = j.telegram_account_id
        WHERE j.campaign_id = $1 AND j.status IN ('queued', 'running')
        ORDER BY j.id
        """,
        campaign_id,
    )
    return [_job_row(r) for r in rows]


async def get_active_job(campaign_id: int) -> dict[str, Any] | None:
    jobs = await list_active_jobs(campaign_id)
    if jobs:
        return jobs[-1]
    row = await db.fetch_one(
        """
        SELECT j.*, ta.label AS account_label, ta.phone AS account_phone
        FROM creation_jobs j
        LEFT JOIN telegram_accounts ta ON ta.id = j.telegram_account_id
        WHERE j.campaign_id = $1
        ORDER BY j.id DESC
        LIMIT 1
        """,
        campaign_id,
    )
    return _job_row(row) if row else None


async def _load_multi_creation_accounts(campaign_id: int) -> list[dict[str, Any]]:
    return await db.fetch_all(
        """
        SELECT * FROM telegram_accounts
        WHERE campaign_id = $1 AND status IN ('ready', 'creating')
          AND tdata_path IS NOT NULL AND tdata_path != ''
          AND is_banned = FALSE
        ORDER BY id
        """,
        campaign_id,
    )


def _account_free_slots(account: dict[str, Any]) -> int:
    return max(0, int(account["max_bots_limit"]) - int(account["bots_created"]))


async def start_manual_creation_job(
    campaign_id: int,
    *,
    body: StartManualBulkRequest,
    avatars: dict[int, bytes],
    retried_from_job_id: int | None = None,
) -> dict[str, Any]:
    """Очередь ручного массового создания (worker + логи)."""
    campaign = await campaign_service.get_campaign(campaign_id)
    if campaign["accounts_count"] < 1:
        raise ConflictError("Добавьте хотя бы один Telegram-аккаунт")

    bots = body.bots
    multi_account = bool(body.multi_account)

    use_referral = (
        body.use_referral_api
        if body.use_referral_api is not None
        else body.link_source == "referral"
        if body.link_source
        else referral_link_service.is_referral_configured(campaign)
    )
    if body.use_referral_api is True and not referral_link_service.is_referral_configured(campaign):
        raise BadRequestError(
            "Реферальный API не настроен в кампании. "
            "Укажите эндпоинт и ключ в настройках или выберите другой источник ссылок."
        )

    link_source = (body.link_source or "").strip()
    if not link_source:
        link_source = "referral" if use_referral else "batch"

    if use_referral:
        raw_default = (body.default_target_url or campaign.get("resource_url") or "").strip()
        default_url = (
            bot_promo_service.normalize_target_url(raw_default)
            if raw_default
            else "https://referral.pending"
        )
    elif link_source == "per_bot":
        missing = [item.row_id for item in bots if not (item.target_url or "").strip()]
        if missing:
            raise BadRequestError(
                f"Укажите ссылку для каждого бота (строки: {', '.join(map(str, missing))})"
            )
        default_url = ""
    elif link_source == "campaign":
        if not campaign.get("resource_url"):
            raise BadRequestError("В кампании не задана ссылка на сервис")
        default_url = bot_promo_service.normalize_target_url(campaign["resource_url"])
    else:
        default_raw = (body.default_target_url or "").strip()
        if not default_raw:
            raise BadRequestError("Укажите общую ссылку для партии")
        default_url = bot_promo_service.normalize_target_url(default_raw)

    if multi_account:
        ready_accounts = await _load_multi_creation_accounts(campaign_id)
        if not ready_accounts:
            raise ConflictError(
                "Нет готовых аккаунтов для мультиаккаунтного режима. "
                "Проверьте аккаунты в разделе «Аккаунты»."
            )
        total_slots = sum(_account_free_slots(a) for a in ready_accounts)
        if len(bots) > total_slots:
            raise ConflictError(
                f"В партии {len(bots)} ботов, суммарно свободно слотов: {total_slots}."
            )
        account_ids = {int(a["id"]) for a in ready_accounts}
        primary_account_id = None
    else:
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
        if account.get("is_banned"):
            raise ConflictError("Аккаунт забанен и не может использоваться для создания ботов")
        if account.get("status") not in ("ready", "creating") or not account.get("tdata_path"):
            raise ConflictError("Аккаунт не готов к созданию ботов. Проверьте его в разделе «Аккаунты».")

        slots = _account_free_slots(account)
        if len(bots) > slots:
            raise ConflictError(
                f"В партии {len(bots)} ботов, свободно слотов на аккаунте: {slots}."
            )
        account_ids = {int(body.telegram_account_id)}
        primary_account_id = int(body.telegram_account_id)

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
        if not row_url:
            raise BadRequestError(f"Укажите ссылку для бота в строке {item.row_id}")
        row_url = bot_promo_service.normalize_target_url(row_url)
        plan_account_id = None if multi_account else primary_account_id
        manual_plans.append(
            {
                "row_id": item.row_id,
                "telegram_account_id": plan_account_id,
                "display_name": item.display_name.strip(),
                "username": uname,
                "target_url": row_url,
                "description": (item.description or body.shared_texts.description).strip(),
                "about_text": (item.about_text or body.shared_texts.about_text or "").strip(),
                "welcome_message": (
                    item.welcome_message or body.shared_texts.welcome_message
                ).strip(),
                "welcome_button_enabled": body.shared_texts.welcome_button_enabled,
                "welcome_button_text": body.shared_texts.welcome_button_text,
                "link_mode": bot_promo_service.normalize_link_mode(body.link_mode),
                "auto_start": body.auto_start,
                "use_referral_api": use_referral,
                "link_source": link_source,
                "avatar_path": None,
                "generate_avatar": bool(item.generate_avatar),
            }
        )

    async with db.transaction() as conn:
        await db.tx_execute(conn, "SELECT pg_advisory_xact_lock($1)", campaign_id)
        total = len(manual_plans)
        job_mode = "manual_multi" if multi_account else "manual"
        progress_msg = (
            f"В очереди: {total} бот(ов), мультиаккаунт"
            if multi_account
            else f"В очереди: {total} бот(ов), ручная партия"
        )
        redis_mode = "manual_multi" if multi_account else "manual"
        row = await db.tx_fetch_one(
            conn,
            """
            INSERT INTO creation_jobs (
                campaign_id, status, total_accounts, progress_message, job_mode,
                retried_from_job_id, telegram_account_id, account_ids
            )
            VALUES ($1, 'queued', $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            campaign_id,
            total,
            progress_msg,
            job_mode,
            retried_from_job_id,
            primary_account_id,
            list(account_ids),
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

    input_snapshot = job_history_service.build_manual_input_snapshot(
        job_id=job_id,
        body=body,
        manual_plans=manual_plans,
        link_source=link_source,
        use_referral=use_referral,
        default_url=default_url,
    )
    await job_history_service.persist_input_snapshot(
        job_id,
        job_mode=job_mode,
        snapshot=input_snapshot,
    )

    await db.execute(
        "UPDATE campaigns SET status = 'queued', updated_at = NOW() WHERE id = $1",
        campaign_id,
    )
    await sync_campaign_status(campaign_id)

    payload: dict[str, Any] = {
        "job_id": job_id,
        "campaign_id": campaign_id,
        "mode": redis_mode,
        "manual_plans": manual_plans,
        "account_ids": list(account_ids),
    }
    await _create_creation_task(
        row,
        payload,
        account_ids=account_ids,
        progress_message=progress_msg,
    )

    if not campaign.get("resource_url"):
        await campaign_service.update_campaign(campaign_id, resource_url=default_url)

    return _job_row(row)


async def get_job(job_id: int, *, include_snapshots: bool = False) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM creation_jobs WHERE id = $1", job_id)
    if not row:
        raise NotFoundError(ErrorMessages.JOB_NOT_FOUND)
    return _job_row(row, include_snapshots=include_snapshots)


async def list_creation_jobs(
    campaign_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    await campaign_service.get_campaign(campaign_id)
    rows = await db.fetch_all(
        """
        SELECT j.*, ta.label AS account_label, ta.phone AS account_phone
        FROM creation_jobs j
        LEFT JOIN telegram_accounts ta ON ta.id = j.telegram_account_id
        WHERE j.campaign_id = $1
        ORDER BY j.id DESC
        LIMIT $2 OFFSET $3
        """,
        campaign_id,
        max(1, min(limit, 100)),
        max(0, offset),
    )
    return [_job_row(r) for r in rows]


async def get_job_snapshot_avatar_path(job_id: int, row_id: int) -> Path:
    row = await db.fetch_one("SELECT * FROM creation_jobs WHERE id = $1", job_id)
    if not row:
        raise NotFoundError(ErrorMessages.JOB_NOT_FOUND)
    input_snapshot = job_history_service.parse_json_field(row.get("input_snapshot"))
    result = job_history_service.parse_json_field(row.get("result_snapshot"))
    retry_payload = (result or {}).get("retry_payload")
    path = job_history_service.resolve_snapshot_avatar_path(
        job_id,
        row_id,
        input_snapshot=input_snapshot,
        retry_payload=retry_payload,
    )
    if not path:
        raise NotFoundError("Аватар не найден в снимке задачи")
    return path


async def retry_creation_job(job_id: int) -> dict[str, Any]:
    row = await db.fetch_one("SELECT * FROM creation_jobs WHERE id = $1", job_id)
    if not row:
        raise NotFoundError(ErrorMessages.JOB_NOT_FOUND)
    result = job_history_service.parse_json_field(row.get("result_snapshot"))
    retry_payload = (result or {}).get("retry_payload")
    if not retry_payload or retry_payload.get("mode") not in ("manual", "manual_multi"):
        raise BadRequestError(
            "Для этой задачи нет сохранённых несозданных ботов. "
            "История доступна только для ручных партий с частичным результатом."
        )
    body = job_history_service.retry_payload_to_request(retry_payload)
    avatars = job_history_service.load_retry_avatars(retry_payload)
    return await start_manual_creation_job(
        int(row["campaign_id"]),
        body=body,
        avatars=avatars,
        retried_from_job_id=job_id,
    )


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
    if row.get("task_id"):
        await db.execute(
            """
            UPDATE async_tasks
            SET status = 'cancelled',
                progress_message = 'Отменено пользователем',
                finished_at = NOW(),
                heartbeat_at = NOW(),
                updated_at = NOW()
            WHERE id = $1 AND status IN ('queued', 'running')
            """,
            row["task_id"],
        )
    await job_history_service.save_result_snapshot(
        job_id,
        row_results=[],
        total_created=total_created,
        finished_status="cancelled",
    )
    await _reset_creating_accounts(campaign_id)
    await sync_campaign_status(campaign_id)

    from app.domain.services import job_log_service

    await job_log_service.append_log(
        job_id,
        "Задача отменена пользователем",
        level="warn",
        progress_message="Отменено",
    )

    updated = await db.fetch_one("SELECT * FROM creation_jobs WHERE id = $1", job_id)
    await task_service.signal_queued_tasks()
    return _job_row(updated)


async def start_batch_create_job(specs: list[dict[str, Any]]) -> dict[str, Any]:
    """Очередь пакетного создания ботов (POST /bots/batch-create)."""
    if not specs:
        raise BadRequestError("Пустой список ботов")

    campaign_ids = {int(s["campaign_id"]) for s in specs}
    if len(campaign_ids) != 1:
        raise BadRequestError("Все боты должны принадлежать одной кампании")
    campaign_id = campaign_ids.pop()
    await campaign_service.get_campaign(campaign_id)

    account_ids: set[int] = set()
    for spec in specs:
        aid = int(spec["telegram_account_id"])
        account = await db.fetch_one(
            "SELECT * FROM telegram_accounts WHERE id = $1 AND campaign_id = $2",
            aid,
            campaign_id,
        )
        if not account:
            raise BadRequestError(f"Аккаунт #{aid} не найден в кампании")
        if account.get("is_banned"):
            raise ConflictError(f"Аккаунт #{aid} забанен")
        if account.get("status") not in ("ready", "creating") or not account.get("tdata_path"):
            raise ConflictError(f"Аккаунт #{aid} не готов к созданию ботов")
        account_ids.add(aid)

    total = len(specs)
    async with db.transaction() as conn:
        await db.tx_execute(conn, "SELECT pg_advisory_xact_lock($1)", campaign_id)
        row = await db.tx_fetch_one(
            conn,
            """
            INSERT INTO creation_jobs (
                campaign_id, status, total_accounts, progress_message, job_mode,
                telegram_account_id, account_ids
            )
            VALUES ($1, 'queued', $2, $3, 'batch_create', $4, $5)
            RETURNING *
            """,
            campaign_id,
            total,
            f"В очереди: пакет из {total} бот(ов)",
            next(iter(account_ids)) if len(account_ids) == 1 else None,
            list(account_ids),
        )

    job_id = row["id"]
    snapshot = {"mode": "batch_create", "specs": specs}
    await job_history_service.persist_input_snapshot(
        job_id, job_mode="batch_create", snapshot=snapshot
    )
    await sync_campaign_status(campaign_id)
    await _create_creation_task(
        row,
        {
            "job_id": job_id,
            "campaign_id": campaign_id,
            "mode": "batch_create",
            "specs": specs,
        },
        account_ids=account_ids,
        progress_message=f"В очереди: пакет из {total} бот(ов)",
    )
    return _job_row(row)


async def add_accounts_to_multi_job(job_id: int, account_ids: list[int]) -> dict[str, Any]:
    """Добавить аккаунты в выполняющуюся мультиаккаунтную задачу."""
    from app.domain.services import job_log_service

    row = await db.fetch_one("SELECT * FROM creation_jobs WHERE id = $1", job_id)
    if not row:
        raise NotFoundError(ErrorMessages.JOB_NOT_FOUND)
    if row.get("job_mode") != "manual_multi":
        raise BadRequestError("Добавление аккаунтов доступно только для мультиаккаунтных задач")
    if row["status"] not in ("queued", "running"):
        raise ConflictError("Задача не выполняется — аккаунты можно добавить только в активную задачу")

    campaign_id = int(row["campaign_id"])
    current = _job_account_ids(row)
    requested = {int(x) for x in account_ids if x is not None}
    if not requested:
        raise BadRequestError("Укажите id аккаунтов")

    added: list[int] = []
    labels: list[str] = []
    for acc_id in sorted(requested):
        if acc_id in current:
            continue
        account = await db.fetch_one(
            """
            SELECT * FROM telegram_accounts
            WHERE id = $1 AND campaign_id = $2
            """,
            acc_id,
            campaign_id,
        )
        if not account:
            raise BadRequestError(f"Аккаунт #{acc_id} не найден в этой кампании")
        if account.get("is_banned"):
            raise ConflictError(f"Аккаунт #{acc_id} забанен")
        if not account.get("tdata_path"):
            raise ConflictError(f"Аккаунт #{acc_id} не готов — нет tdata")
        if account.get("status") not in ("ready", "creating"):
            raise ConflictError(
                f"Аккаунт #{acc_id} не готов к созданию (статус: {account.get('status')})"
            )
        slots = max(0, int(account["max_bots_limit"]) - int(account["bots_created"]))
        if slots <= 0:
            raise ConflictError(f"На аккаунте #{acc_id} нет свободных слотов")

        conflicts = await _find_account_conflicts(
            campaign_id,
            {acc_id},
            exclude_job_id=job_id,
        )
        if conflicts:
            other = conflicts[0]
            raise ConflictError(
                f"Аккаунт #{acc_id} занят задачей #{other['id']}"
            )

        label = (account.get("label") or "").strip() or f"Аккаунт #{acc_id}"
        added.append(acc_id)
        labels.append(label)

    if not added:
        raise BadRequestError("Все указанные аккаунты уже в задаче")

    merged = sorted(current | set(added))
    updated = await db.fetch_one(
        """
        UPDATE creation_jobs
        SET account_ids = $2, updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        job_id,
        merged,
    )

    if updated.get("task_id"):
        await db.execute(
            """
            UPDATE async_tasks
            SET account_ids = $2, updated_at = NOW()
            WHERE id = $1
            """,
            updated["task_id"],
            merged,
        )

    await job_log_service.append_log(
        job_id,
        f"Добавлены аккаунты в ротацию: {', '.join(labels)}",
        level="info",
        context={"account_ids": added, "status": "accounts_added"},
        progress_message=updated.get("progress_message"),
    )

    return _job_row(updated)
