"""Пайплайн создания ботов для worker."""
import asyncio
from pathlib import Path
from typing import Any, Optional

from app.config import Config
from app.core.exceptions import BadRequestError
from app.domain.services import (
    account_flood_service,
    bot_promo_service,
    bot_service,
    job_history_service,
    job_log_service,
    referral_link_service,
    username_service,
)
from app.infrastructure.ai.provider import AIService, generate_image_bytes
from app.infrastructure.database import repository as db
from app.infrastructure.telegram.botfather_client import (
    create_bot_via_botfather,
    set_bot_about,
    set_bot_description,
    set_bot_photo,
)
from app.infrastructure.telegram.botfather_pacing import (
    batch_cooldown_sec,
    batch_size,
    inter_bot_delay_sec,
    max_server_flood_wait_sec,
    pace_botfather_op,
    post_throttle_delay_sec,
)
from app.infrastructure.telegram.session_loader import load_client_from_tdata
from app.utils.crypto import encrypt_token


FLOOD_MAX_RETRIES = 8


def _format_flood_wait_human(seconds: int) -> str:
    sec = max(0, int(seconds))
    if sec < 60:
        return f"{sec} сек"
    minutes, remainder = divmod(sec, 60)
    if minutes < 60:
        return f"{minutes} мин {remainder} сек" if remainder else f"{minutes} мин"
    hours, mins = divmod(minutes, 60)
    return f"{hours} ч {mins} мин" if mins else f"{hours} ч"


def _should_stop_batch_on_error(exc: Exception) -> bool:
    """Остановить партию: блокировка BotFather или требование паузы от Telegram."""
    details = getattr(exc, "details", None) or {}
    if details.get("botfather_blocked"):
        return True
    if details.get("flood_wait"):
        return True
    msg = (getattr(exc, "message", None) or str(exc)).lower()
    return "telegram требует паузу" in msg or "лимит telegram" in msg

CREATION_STEP_LABELS = {
    "username": "Подбор username",
    "botfather_create": "BotFather",
    "referral_fetch": "Реферальная ссылка",
    "links": "Ссылки",
    "avatar": "Аватар",
    "botfather_texts": "Тексты в BotFather",
    "db_save": "Сохранение",
}


def _format_creation_error(exc: Exception) -> str:
    msg = getattr(exc, "message", None) or str(exc)
    details = getattr(exc, "details", None) or {}
    step = details.get("step")
    if step in CREATION_STEP_LABELS and CREATION_STEP_LABELS[step] not in msg:
        msg = f"{CREATION_STEP_LABELS[step]}: {msg}"
    if details.get("botfather_created"):
        bf_user = details.get("username")
        hint = (
            f" Бот уже создан в BotFather (@{bf_user}) — проверьте API или удалите бота в @BotFather."
            if bf_user
            else " Бот уже создан в BotFather — проверьте настройки или удалите его в @BotFather."
        )
        if hint.strip() not in msg:
            msg += hint
    return msg[:500]


class CreationPipeline:
    def __init__(
        self,
        job_id: int,
        campaign_id: int,
        plans: list[dict[str, Any]] | None = None,
        manual_plans: list[dict[str, Any]] | None = None,
    ):
        self.job_id = job_id
        self.campaign_id = campaign_id
        self.plans = plans or []
        self.manual_plans = manual_plans or []
        self.ai = AIService()
        self._row_results: list[dict[str, Any]] = []

    def _record_row_result(
        self,
        plan: dict[str, Any],
        idx: int,
        status: str,
        **extra: Any,
    ) -> None:
        row_id = plan.get("row_id", idx + 1)
        entry = {
            "row_id": row_id,
            "username": plan.get("username"),
            "status": status,
            **extra,
        }
        for i, existing in enumerate(self._row_results):
            if existing.get("row_id") == row_id:
                self._row_results[i] = entry
                return
        self._row_results.append(entry)

    async def _is_cancelled(self) -> bool:
        status = await db.fetch_val(
            "SELECT status FROM creation_jobs WHERE id = $1",
            self.job_id,
        )
        return status == "cancelled"

    async def _sleep_cancellable(self, seconds: float) -> bool:
        """Sleep in 1s chunks. Returns True if cancelled during wait."""
        remaining = max(0.0, float(seconds))
        while remaining > 0:
            if await self._is_cancelled():
                return True
            step = min(1.0, remaining)
            await asyncio.sleep(step)
            remaining -= step
        return await self._is_cancelled()

    async def _wait_account_flood(self, account_id: int, label: str) -> None:
        if await self._is_cancelled():
            raise BadRequestError("Задача отменена")

        async def _log(msg: str, **kwargs):
            await self.log(msg, **kwargs)

        await account_flood_service.wait_for_flood_clear(
            account_id,
            sleep=self._sleep_cancellable,
            log=_log,
            label=label,
        )
        if await self._is_cancelled():
            raise BadRequestError("Задача отменена")

    async def _mark_remaining_skipped(
        self,
        plans: list[dict[str, Any]],
        start_index: int,
    ) -> None:
        for idx in range(start_index, len(plans)):
            plan = plans[idx]
            row_id = plan.get("row_id", idx + 1)
            uname = plan.get("username", "?")
            self._record_row_result(plan, idx, "skipped")
            await self.log(
                f"@{uname} — пропущен (задача остановлена)",
                level="warn",
                context={
                    "row_id": row_id,
                    "plan_index": idx,
                    "username": uname,
                    "status": "skipped",
                },
            )

    async def _pace_between_bots(self, processed: int, total: int) -> bool:
        """Пауза между ботами + пакетный cooldown. True = отменено."""
        if processed >= total:
            return False
        delay = inter_bot_delay_sec()
        await self.log(
            f"Пауза {delay} сек. перед следующим ботом (лимиты BotFather)…",
        )
        await self.log(
            f"Rate limit pacing: inter-bot {delay}s",
            level="debug",
            context={"delay_sec": delay, "processed": processed, "total": total},
        )
        if await self._sleep_cancellable(delay):
            return True
        every = batch_size()
        if every > 0 and processed > 0 and processed % every == 0:
            cooldown = batch_cooldown_sec()
            mins = max(1, cooldown // 60)
            await self.log(
                f"Пакетная пауза ~{mins} мин (создано {processed} из {total} — защита от блокировки)…",
                level="warn",
            )
            await self.log(
                f"Batch cooldown after {processed} bots",
                level="debug",
                context={"cooldown_sec": cooldown, "batch_size": every},
            )
            if await self._sleep_cancellable(cooldown):
                return True
        return False

    async def log(
        self,
        message: str,
        level: str = "info",
        *,
        progress: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> None:
        await job_log_service.append_log(
            self.job_id,
            message,
            level=level,
            context=context,
            progress_message=progress or message,
        )

    async def run(self) -> None:
        campaign = await db.fetch_one("SELECT * FROM campaigns WHERE id = $1", self.campaign_id)
        if not campaign:
            raise ValueError("Кампания не найдена")

        if self.manual_plans:
            await self._run_manual(campaign)
            return

        if self.plans:
            await self._run_planned(campaign)
            return

        accounts = await db.fetch_all(
            """
            SELECT * FROM telegram_accounts
            WHERE campaign_id = $1 AND status IN ('ready', 'pending', 'creating')
              AND is_banned = FALSE
            ORDER BY id
            """,
            self.campaign_id,
        )
        if not accounts:
            raise ValueError("Нет Telegram-аккаунтов (добавьте из подготовленных)")

        await self.log(
            f"Старт: кампания «{campaign['title']}», аккаунтов: {len(accounts)}",
            progress="Подготовка",
        )

        total_created = 0
        processed = 0

        for account in accounts:
            if await self._is_cancelled():
                await self.log("Создание остановлено пользователем", level="warn")
                break
            processed += 1
            await db.execute(
                """
                UPDATE creation_jobs
                SET processed_accounts = $2, updated_at = NOW()
                WHERE id = $1
                """,
                self.job_id,
                processed,
            )
            try:
                created = await self._process_account(campaign, account)
                total_created += created
            except Exception as exc:
                await self.log(
                    f"Аккаунт #{account['id']}: ошибка — {exc}",
                    level="error",
                )
                await db.execute(
                    """
                    UPDATE telegram_accounts
                    SET status = 'error', last_error = $2, updated_at = NOW()
                    WHERE id = $1
                    """,
                    account["id"],
                    str(exc)[:500],
                )

        await self._finish_job(total_created, cancelled=await self._is_cancelled())

    async def _run_manual(self, campaign: dict) -> None:
        total = len(self.manual_plans)
        if not total:
            raise ValueError("Пустой план ручного создания")

        account_id = int(self.manual_plans[0]["telegram_account_id"])
        account = await db.fetch_one(
            "SELECT * FROM telegram_accounts WHERE id = $1 AND campaign_id = $2",
            account_id,
            self.campaign_id,
        )
        if not account:
            raise ValueError(f"Аккаунт #{account_id} не найден")

        label = account.get("label") or f"Аккаунт #{account_id}"
        slots_left = max(0, int(account["max_bots_limit"]) - int(account["bots_created"]))
        plans = self.manual_plans[:slots_left]

        await self.log(
            f"Ручная партия: {len(plans)} бот(ов) на {label}",
            progress=f"0/{len(plans)}",
        )
        use_referral = bool(plans[0].get("use_referral_api"))
        src = (plans[0].get("link_source") or "") if plans else ""
        mode = plans[0].get("link_mode") if plans else bot_promo_service.LINK_MODE_REDIRECT
        mode_label = "с подсчётом переходов" if mode == bot_promo_service.LINK_MODE_REDIRECT else "прямые"
        if use_referral:
            await self.log("Ссылки: автоматически через реферальный API кампании")
        elif src == "per_bot":
            await self.log(f"Ссылки: своя для каждого бота ({mode_label})")
        elif src == "campaign":
            sample = (plans[0].get("target_url") or "")[:60] if plans else ""
            suffix = f" — {sample}…" if sample else ""
            await self.log(f"Ссылки: из кампании ({mode_label}){suffix}")
        else:
            sample = (plans[0].get("target_url") or "")[:60] if plans else ""
            suffix = f" — {sample}…" if sample else ""
            await self.log(f"Ссылки: общая для партии ({mode_label}){suffix}")
        await self._wait_account_flood(account_id, label)
        await db.execute(
            "UPDATE telegram_accounts SET status = 'creating', updated_at = NOW() WHERE id = $1",
            account_id,
        )

        created_count = 0
        processed = 0
        session_file = Config.STORAGE_ROOT / "sessions" / str(self.campaign_id) / f"{account_id}.session"
        client = None

        try:
            client, _ = await load_client_from_tdata(Path(account["tdata_path"]), session_file)
            await self.log(
                f"Telethon session loaded for account #{account_id}",
                level="debug",
                context={"account_id": account_id, "plans": len(plans)},
            )

            flood_ctx = account_flood_service.set_flood_account_context(account_id)
            try:
                for idx, plan in enumerate(plans):
                    if await self._is_cancelled():
                        await self.log("Создание остановлено пользователем", level="warn")
                        await self._mark_remaining_skipped(plans, idx)
                        break

                    processed += 1
                    uname = plan["username"]
                    row_id = plan.get("row_id", idx + 1)
                    await db.execute(
                        """
                        UPDATE creation_jobs
                        SET processed_accounts = $2, updated_at = NOW()
                        WHERE id = $1
                        """,
                        self.job_id,
                        processed,
                    )
                    await self.log(
                        f"[{processed}/{len(plans)}] @{uname} — старт",
                        progress=f"{processed - 1}/{len(plans)}: @{uname}",
                        context={
                            "row_id": row_id,
                            "plan_index": idx,
                            "username": uname,
                            "status": "creating",
                        },
                    )

                    avatar_bytes = None
                    avatar_path = plan.get("avatar_path")
                    if avatar_path:
                        path = Path(avatar_path)
                        if path.is_file():
                            avatar_bytes = path.read_bytes()

                    try:
                        bot = await self._create_manual_bot_with_flood_retry(
                            plan,
                            avatar_bytes=avatar_bytes,
                            client=client,
                        )
                        if await self._is_cancelled():
                            await self._mark_remaining_skipped(plans, idx + 1)
                            break
                        created_count += 1
                        await db.execute(
                            """
                            UPDATE creation_jobs
                            SET total_bots_created = $2, updated_at = NOW()
                            WHERE id = $1
                            """,
                            self.job_id,
                            created_count,
                        )
                        await self.log(
                            f"[{processed}/{len(plans)}] @{uname} — создан",
                            level="info",
                            progress=f"{processed}/{len(plans)}: готово",
                            context={
                                "row_id": row_id,
                                "plan_index": idx,
                                "username": uname,
                                "status": "done",
                                "bot_id": bot.get("id"),
                            },
                        )
                        self._record_row_result(
                            plan,
                            idx,
                            "done",
                            bot_id=bot.get("id"),
                        )
                    except Exception as exc:
                        if await self._is_cancelled():
                            await self._mark_remaining_skipped(plans, idx)
                            break
                        details = getattr(exc, "details", None) or {}
                        await self.log(
                            f"[{processed}/{len(plans)}] @{uname} — {_format_creation_error(exc)}",
                            level="error",
                            context={
                                "row_id": row_id,
                                "plan_index": idx,
                                "username": uname,
                                "status": "error",
                                "error": _format_creation_error(exc),
                                "step": details.get("step"),
                            },
                        )
                        self._record_row_result(
                            plan,
                            idx,
                            "error",
                            error=_format_creation_error(exc),
                        )
                        if _should_stop_batch_on_error(exc):
                            if details.get("botfather_blocked"):
                                reason = "аккаунт ограничен BotFather"
                            else:
                                reason = "Telegram требует паузу"
                            await self.log(
                                f"Остановка партии — {reason}, следующие боты не создаются",
                                level="error",
                            )
                            await self._mark_remaining_skipped(plans, idx + 1)
                            break

                    if processed < len(plans):
                        if await self._pace_between_bots(processed, len(plans)):
                            await self._mark_remaining_skipped(plans, idx + 1)
                            break
            finally:
                account_flood_service.reset_flood_account_context(flood_ctx)
        finally:
            if client:
                await client.disconnect()

        acc = await db.fetch_one("SELECT * FROM telegram_accounts WHERE id = $1", account_id)
        acc_status = "ready"
        if acc and int(acc["bots_created"]) >= int(acc["max_bots_limit"]):
            acc_status = "exhausted"
        await db.execute(
            "UPDATE telegram_accounts SET status = $2, updated_at = NOW() WHERE id = $1",
            account_id,
            acc_status,
        )
        await self.log(f"{label}: создано {created_count} из {len(plans)}")
        await self._finish_job(created_count, cancelled=await self._is_cancelled())

    async def _create_manual_bot_with_flood_retry(
        self,
        plan: dict[str, Any],
        *,
        avatar_bytes: Optional[bytes],
        client,
    ) -> dict[str, Any]:
        for attempt in range(FLOOD_MAX_RETRIES + 1):
            if await self._is_cancelled():
                raise BadRequestError("Задача отменена")
            try:
                return await bot_service.create_bot(
                    campaign_id=self.campaign_id,
                    telegram_account_id=int(plan["telegram_account_id"]),
                    target_url=plan["target_url"],
                    display_name=plan["display_name"],
                    username=plan["username"],
                    description=plan["description"],
                    about_text=plan.get("about_text") or "",
                    welcome_message=plan["welcome_message"],
                    welcome_button_enabled=bool(plan.get("welcome_button_enabled", True)),
                    welcome_button_text=plan.get("welcome_button_text")
                    or bot_promo_service.WELCOME_BUTTON_TEXT_DEFAULT,
                    keyword=None,
                    link_mode=plan.get("link_mode") or bot_promo_service.LINK_MODE_REDIRECT,
                    create_via_botfather=True,
                    auto_start=bool(plan.get("auto_start", True)),
                    avatar_bytes=avatar_bytes,
                    generate_avatar=False,
                    telethon_client=client,
                    use_referral_api=plan.get("use_referral_api"),
                    on_step=lambda msg, step: self.log(
                        msg,
                        context={
                            "row_id": plan.get("row_id"),
                            "username": plan.get("username"),
                            "status": "creating",
                            "step": step or None,
                        },
                    ),
                )
            except BadRequestError as exc:
                details = exc.details or {}
                if details.get("botfather_blocked"):
                    raise
                wait = int(details.get("wait_seconds") or 0)
                if wait > 0 and details.get("flood_wait"):
                    await account_flood_service.record_flood_wait(
                        int(plan["telegram_account_id"]),
                        wait,
                    )
                max_wait = max_server_flood_wait_sec()
                if wait > max_wait:
                    raise BadRequestError(
                        f"Telegram требует паузу {_format_flood_wait_human(wait)} "
                        f"для @{plan['username']} — больше лимита в настройках "
                        f"({_format_flood_wait_human(max_wait)}). "
                        "Увеличьте «Макс. ожидание FloodWait» в Настройках и перезапустите задачу.",
                        details={**details, "flood_wait": True, "wait_seconds": wait},
                    )
                if details.get("flood_wait") and wait > 0 and attempt < FLOOD_MAX_RETRIES:
                    await self.log(
                        f"Лимит Telegram для @{plan['username']}, "
                        f"пауза {_format_flood_wait_human(wait)}…",
                        level="warn",
                        context={
                            "row_id": plan.get("row_id"),
                            "username": plan["username"],
                            "status": "waiting",
                            "wait_seconds": wait,
                        },
                    )
                    if await self._sleep_cancellable(wait + 2):
                        raise BadRequestError("Задача отменена")
                    await account_flood_service.clear_flood_wait(int(plan["telegram_account_id"]))
                    recovery = post_throttle_delay_sec()
                    if recovery > 0:
                        await self.log(f"Доп. пауза {recovery} сек. после лимита Telegram…")
                        if await self._sleep_cancellable(recovery):
                            raise BadRequestError("Задача отменена")
                    continue
                raise
        raise BadRequestError(f"Не удалось создать @{plan['username']} после пауз лимита Telegram")

    async def _run_planned(self, campaign: dict) -> None:
        from collections import defaultdict

        by_account: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for p in self.plans:
            by_account[int(p["telegram_account_id"])].append(p)

        await self.log(
            f"План: {len(self.plans)} бот(ов) на {len(by_account)} аккаунт(ах)",
            progress="План создания",
        )

        total_created = 0
        processed = 0
        account_ids = sorted(by_account.keys())

        for account_id in account_ids:
            processed += 1
            await db.execute(
                """
                UPDATE creation_jobs
                SET processed_accounts = $2, updated_at = NOW()
                WHERE id = $1
                """,
                self.job_id,
                processed,
            )
            account = await db.fetch_one(
                "SELECT * FROM telegram_accounts WHERE id = $1 AND campaign_id = $2",
                account_id,
                self.campaign_id,
            )
            if not account:
                await self.log(f"Аккаунт #{account_id}: не найден", level="warn")
                continue
            if account.get("is_banned"):
                label = account.get("label") or f"#{account_id}"
                await self.log(f"{label}: пропущен — аккаунт забанен", level="warn")
                continue
            try:
                created = await self._process_account_planned(
                    campaign, account, by_account[account_id]
                )
                total_created += created
            except Exception as exc:
                label = account.get("label") or f"#{account_id}"
                await self.log(f"{label}: ошибка — {exc}", level="error")
                await db.execute(
                    """
                    UPDATE telegram_accounts
                    SET status = 'error', last_error = $2, updated_at = NOW()
                    WHERE id = $1
                    """,
                    account_id,
                    str(exc)[:500],
                )

        await self._finish_job(total_created, cancelled=await self._is_cancelled())

    async def _finish_job(self, total_created: int, *, cancelled: bool = False) -> None:
        await db.execute(
            """
            UPDATE creation_jobs
            SET total_bots_created = $2, updated_at = NOW()
            WHERE id = $1
            """,
            self.job_id,
            total_created,
        )
        if cancelled:
            await job_history_service.save_result_snapshot(
                self.job_id,
                row_results=self._row_results,
                total_created=total_created,
                finished_status="cancelled",
            )
            await db.execute(
                """
                UPDATE creation_jobs
                SET progress_message = $2, updated_at = NOW()
                WHERE id = $1 AND status = 'cancelled'
                """,
                self.job_id,
                f"Отменено. Создано ботов: {total_created}",
            )
            from app.domain.services import job_service

            await job_service.sync_campaign_status(self.campaign_id)
            await self.log(
                f"Задача остановлена. Создано ботов: {total_created}",
                level="warn",
                progress="Отменено",
            )
            return

        status = "completed" if total_created > 0 else "failed"
        error_message = "" if total_created > 0 else "Не удалось создать ни одного бота"
        await job_history_service.save_result_snapshot(
            self.job_id,
            row_results=self._row_results,
            total_created=total_created,
            finished_status=status,
            error_message=error_message or None,
        )
        await db.execute(
            """
            UPDATE creation_jobs
            SET status = $2,
                finished_at = NOW(),
                progress_message = $3,
                error_message = CASE WHEN $4 = '' THEN NULL ELSE $4 END,
                updated_at = NOW()
            WHERE id = $1
            """,
            self.job_id,
            status,
            f"Готово: создано ботов {total_created}",
            "" if total_created > 0 else "Не удалось создать ни одного бота",
        )
        from app.domain.services import job_service

        await job_service.sync_campaign_status(self.campaign_id)
        await self.log(
            f"Задача завершена. Создано ботов: {total_created}",
            level="info" if total_created else "warn",
            progress="Завершено",
        )

    async def _process_account_planned(
        self, campaign: dict, account: dict, plan_items: list[dict[str, Any]]
    ) -> int:
        account_id = account["id"]
        label = account.get("label") or f"Аккаунт #{account_id}"
        if account.get("is_banned"):
            await self.log(f"{label}: пропущен — аккаунт забанен", level="warn")
            return 0
        slots_left = max(0, account["max_bots_limit"] - account["bots_created"])
        if slots_left <= 0:
            await self.log(f"{label}: лимит ботов исчерпан", level="warn")
            return 0

        plan_items = plan_items[:slots_left]
        await db.execute(
            "UPDATE telegram_accounts SET status = 'creating', updated_at = NOW() WHERE id = $1",
            account_id,
        )
        await self.log(f"{label}: план — {len(plan_items)} бот(ов)", progress=f"Аккаунт: {label}")

        session_file = Config.STORAGE_ROOT / "sessions" / str(self.campaign_id) / f"{account_id}.session"
        client = None
        created_count = 0
        resource_url = campaign.get("resource_url") or ""

        try:
            await self._wait_account_flood(account_id, label)
            client, me = await load_client_from_tdata(Path(account["tdata_path"]), session_file)
            phone = getattr(me, "phone", None) or str(me.id)
            await db.execute(
                "UPDATE telegram_accounts SET phone = $2, updated_at = NOW() WHERE id = $1",
                account_id,
                phone,
            )

            for idx, item in enumerate(plan_items):
                kw = (item.get("keyword") or "").strip()
                if not kw:
                    continue
                await self.log(f"{label}: бот #{idx + 1} — «{kw}»")
                concepts = await self.ai.analyze_niche(
                    [kw],
                    campaign.get("niche_description"),
                    resource_url,
                    1,
                    campaign_id=self.campaign_id,
                )
                if not concepts:
                    await self.log(f"{label}: AI не вернул профиль для «{kw}»", level="warn")
                    continue
                concept = concepts[0]
                concept["keyword"] = kw
                try:
                    bot_id = await self._create_single_bot(
                        client, campaign, account_id, concept, idx
                    )
                    if bot_id:
                        created_count += 1
                        await db.execute(
                            """
                            UPDATE telegram_accounts
                            SET bots_created = bots_created + 1, updated_at = NOW()
                            WHERE id = $1
                            """,
                            account_id,
                        )
                except Exception as exc:
                    await self.log(
                        f"{label}: «{kw}» — {exc}",
                        level="error",
                    )
                    if _should_stop_batch_on_error(exc):
                        await self.log(
                            f"{label}: остановка партии — Telegram требует паузу или аккаунт ограничен",
                            level="error",
                        )
                        break
                if idx + 1 < len(plan_items):
                    if await self._pace_between_bots(idx + 1, len(plan_items)):
                        break

            acc_status = "ready"
            if created_count + int(account["bots_created"]) >= account["max_bots_limit"]:
                acc_status = "exhausted"
            await db.execute(
                "UPDATE telegram_accounts SET status = $2, updated_at = NOW() WHERE id = $1",
                account_id,
                acc_status,
            )
            await self.log(f"{label}: создано {created_count} из {len(plan_items)}")
            return created_count
        finally:
            if client:
                await client.disconnect()

    async def _process_account(self, campaign: dict, account: dict) -> int:
        account_id = account["id"]
        label = account.get("label") or f"Аккаунт #{account_id}"
        if account.get("is_banned"):
            await self.log(f"{label}: пропущен — аккаунт забанен", level="warn")
            return 0
        slots = max(0, account["max_bots_limit"] - account["bots_created"])
        if slots <= 0:
            await self.log(f"{label}: лимит ботов исчерпан", level="warn")
            await db.execute(
                "UPDATE telegram_accounts SET status = 'exhausted', updated_at = NOW() WHERE id = $1",
                account_id,
            )
            return 0

        await db.execute(
            "UPDATE telegram_accounts SET status = 'creating', updated_at = NOW() WHERE id = $1",
            account_id,
        )
        await self.log(f"{label}: подключение tdata…", progress=f"Аккаунт: {label}")

        session_file = Config.STORAGE_ROOT / "sessions" / str(self.campaign_id) / f"{account_id}.session"
        client = None
        created_count = 0

        try:
            await self._wait_account_flood(account_id, label)
            client, me = await load_client_from_tdata(Path(account["tdata_path"]), session_file)
            phone = getattr(me, "phone", None) or str(me.id)
            await db.execute(
                "UPDATE telegram_accounts SET phone = $2, updated_at = NOW() WHERE id = $1",
                account_id,
                phone,
            )
            await self.log(f"{label}: сессия OK ({phone})", context={"account_id": account_id})

            keywords = [k.strip() for k in (campaign.get("keywords") or []) if k and k.strip()]
            if not keywords:
                await self.log(
                    f"{label}: пропуск — у кампании нет ключевых слов",
                    level="warn",
                )
                await db.execute(
                    "UPDATE telegram_accounts SET status = 'ready', updated_at = NOW() WHERE id = $1",
                    account_id,
                )
                return 0
            resource_url = campaign.get("resource_url") or ""
            await self.log(
                f"{label}: AI — {slots} ботов по ключевым словам ({len(keywords)} в кампании)…"
            )
            concepts = await self.ai.analyze_niche(
                keywords,
                campaign.get("niche_description"),
                resource_url,
                slots,
                campaign_id=self.campaign_id,
            )
            concepts = concepts[:slots]
            if not concepts:
                raise ValueError("AI не вернул концепты ботов")

            await self.log(f"{label}: получено {len(concepts)} концептов")

            for idx, concept in enumerate(concepts):
                kw = concept.get("keyword", "?")
                await self.log(f"{label}: бот #{idx + 1} — ключевое слово «{kw}»")
                try:
                    bot_id = await self._create_single_bot(
                        client,
                        campaign,
                        account_id,
                        concept,
                        idx,
                    )
                    if bot_id:
                        created_count += 1
                        await db.execute(
                            """
                            UPDATE telegram_accounts
                            SET bots_created = bots_created + 1, updated_at = NOW()
                            WHERE id = $1
                            """,
                            account_id,
                        )
                except Exception as exc:
                    await self.log(
                        f"{label}: бот «{concept.get('display_name', '?')}» — {exc}",
                        level="error",
                    )
                    if _should_stop_batch_on_error(exc):
                        await self.log(
                            f"{label}: остановка партии — Telegram требует паузу или аккаунт ограничен",
                            level="error",
                        )
                        break
                if idx + 1 < len(concepts):
                    if await self._pace_between_bots(idx + 1, len(concepts)):
                        break

            acc_status = "ready"
            if created_count >= account["max_bots_limit"]:
                acc_status = "exhausted"
            elif created_count == 0:
                await db.execute(
                    """
                    UPDATE telegram_accounts
                    SET last_error = $2, updated_at = NOW()
                    WHERE id = $1
                    """,
                    account_id,
                    "Сессия OK, но боты не созданы (см. лог). Аккаунт готов для ручного создания.",
                )
            await db.execute(
                "UPDATE telegram_accounts SET status = $2, updated_at = NOW() WHERE id = $1",
                account_id,
                acc_status,
            )
            await self.log(f"{label}: создано {created_count} ботов")
            return created_count
        finally:
            if client:
                await client.disconnect()

    async def _create_single_bot(
        self,
        client,
        campaign: dict,
        account_id: int,
        concept: dict[str, Any],
        variant_index: int,
    ) -> Optional[int]:
        keyword = concept.get("keyword", "")
        await self.log(f"AI: профиль бота «{concept.get('display_name', keyword)}»…")

        profile = await self.ai.refine_bot_profile(
            concept,
            campaign.get("niche_description"),
            campaign_id=self.campaign_id,
        )
        display_name = profile.get("display_name", "Bot")[:64]
        preferred = profile.get("username") or concept.get("username_hint")
        username = await username_service.allocate_unique_username(
            keyword,
            preferred=preferred,
            campaign_id=self.campaign_id,
            telethon_client=client,
        )

        use_referral = referral_link_service.is_referral_configured(campaign)
        target_url = (campaign.get("resource_url") or "").strip()
        if not use_referral and not target_url:
            await self.log("Пропуск: у кампании не задан resource_url (ссылка на сервис)", level="warn")
            return None

        await self.log(f"BotFather: создание @{username}…")
        await self.log(
            f"BotFather pipeline start @{username}",
            level="debug",
            context={"keyword": keyword, "account_id": account_id, "variant": variant_index},
        )
        reserved = await username_service.get_reserved_usernames()
        username_factory = username_service.make_username_factory(
            keyword,
            preferred=username,
            campaign_id=self.campaign_id,
            reserved=reserved,
        )
        result = await create_bot_via_botfather(
            client,
            display_name,
            username,
            username_factory=username_factory,
        )
        token = result["token"]
        username = result["username"]
        await pace_botfather_op()

        if use_referral:
            await self.log(f"Запрос реферальной ссылки для @{username}…")
        links = await referral_link_service.resolve_bot_links(
            campaign,
            username=username,
            target_url=target_url or None,
            link_mode=bot_promo_service.LINK_MODE_REDIRECT,
        )
        if use_referral:
            await self.log(f"Реферальная ссылка для @{username} получена")
        target = links["target_url"]
        slug = links["redirect_slug"]
        tracking_url = links["tracking_url"]
        public_link = links["public_link"]
        mode = links["link_mode"]
        promo = bot_promo_service.build_promo_texts(
            public_link=public_link,
            display_name=display_name,
            keyword=keyword,
            link_mode=mode,
        )
        texts = bot_promo_service.finalize_bot_texts(
            description=profile.get("description", ""),
            about_text=profile.get("about_text", ""),
            welcome_message=None,
            public_link=public_link,
            link_mode=mode,
            target_url=target,
            tracking_url=tracking_url,
            display_name=display_name,
            keyword=keyword,
            use_promo_welcome=False,
            campaign_defaults=bot_promo_service.campaign_text_defaults(campaign),
        )
        description = texts["description"] or promo["description"]
        about_text = texts["about_text"] or promo["about_text"]

        defaults = bot_promo_service.campaign_text_defaults(campaign)
        try:
            welcome = await self.ai.generate_welcome_message(
                public_link,
                keyword,
                display_name,
                variant_index,
                campaign_id=self.campaign_id,
                moved_notice=True,
            )
            welcome = bot_promo_service.embed_link_in_welcome(
                welcome,
                public_link,
                link_mode=mode,
                target_url=target,
                tracking_url=tracking_url,
            )
            if not welcome.strip():
                if defaults.get("welcome_message"):
                    welcome = bot_promo_service.embed_link_in_welcome(
                        defaults["welcome_message"],
                        public_link,
                        link_mode=mode,
                        target_url=target,
                        tracking_url=tracking_url,
                    )
                else:
                    welcome = promo["welcome_message"]
        except Exception:
            if defaults.get("welcome_message"):
                welcome = bot_promo_service.embed_link_in_welcome(
                    defaults["welcome_message"],
                    public_link,
                    link_mode=mode,
                    target_url=target,
                    tracking_url=tracking_url,
                )
            else:
                welcome = promo["welcome_message"]

        avatar_path = None
        try:
            prompt = profile.get("avatar_prompt", promo["avatar_prompt"])
            img = await generate_image_bytes(prompt)
            avatar_path = Config.AVATARS_DIR / str(self.campaign_id) / f"{username}.jpg"
            avatar_path.parent.mkdir(parents=True, exist_ok=True)
            avatar_path.write_bytes(img)
            await set_bot_photo(client, username, avatar_path)
            await pace_botfather_op()
        except Exception as exc:
            await self.log(f"Аватар @{username}: {exc}", level="warn")

        await set_bot_description(client, username, description)
        await pace_botfather_op()
        await set_bot_about(client, username, about_text)

        token_enc = encrypt_token(token)
        row = await db.fetch_one(
            """
            INSERT INTO bots (
                campaign_id, telegram_account_id, keyword, username, display_name,
                description, about_text, token_encrypted, avatar_path, welcome_message,
                welcome_button_enabled, welcome_button_text,
                target_url, link_mode, redirect_slug, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, TRUE, $11, $12, $13, $14, 'active')
            RETURNING id
            """,
            self.campaign_id,
            account_id,
            keyword,
            username,
            display_name,
            description,
            about_text,
            token_enc,
            str(avatar_path) if avatar_path else None,
            welcome,
            bot_promo_service.WELCOME_BUTTON_TEXT_DEFAULT,
            target,
            mode,
            slug,
        )
        bot_id = row["id"]
        await self.log(f"✓ Бот @{username} создан", context={"bot_id": bot_id, "username": username})
        await self.log(
            f"DB insert bot id={bot_id}",
            level="debug",
            context={"bot_id": bot_id, "username": username, "account_id": account_id},
        )
        return bot_id
