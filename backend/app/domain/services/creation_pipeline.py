"""Пайплайн создания ботов для worker."""
import asyncio
import re
from pathlib import Path
from typing import Any, Optional

from app.config import Config
from app.core.exceptions import BadRequestError
from app.domain.services import (
    account_flood_service,
    account_service,
    bot_promo_service,
    bot_service,
    job_history_service,
    job_log_service,
    referral_link_service,
    username_service,
)
from app.domain.services.account_session_service import (
    account_lock,
    acquire_cached_client,
    ensure_client_connected,
    release_cached_session,
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
    throttle_pause_total_sec,
)
from app.infrastructure.telegram.session_loader import load_client_from_tdata
from app.utils.crypto import encrypt_token


FLOOD_MAX_RETRIES = 8


def _is_rotate_account_error(exc: Exception) -> bool:
    """Ошибки, при которых в мультиаккаунте пробуем следующий аккаунт."""
    details = getattr(exc, "details", None) or {}
    if details.get("flood_wait") or details.get("botfather_blocked"):
        return True
    if details.get("bots_limit_reached"):
        return True
    msg = (getattr(exc, "message", None) or str(exc)).lower()
    return (
        "botfather не ответил" in msg
        or "timeout" in msg
        or "telegram требует паузу" in msg
        or "лимит telegram" in msg
    )


def _is_bot_specific_error(exc: Exception) -> bool:
    """Ошибки бота (username и т.д.) — ротация аккаунта не поможет."""
    details = getattr(exc, "details", None) or {}
    msg = (getattr(exc, "message", None) or str(exc)).lower()
    if details.get("step") == "username":
        return True
    if "username" in msg and any(
        token in msg for token in ("занят", "taken", "invalid", "отклонён", "invalid")
    ):
        return True
    if "имя бота отклонено" in msg:
        return True
    return False


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
    """Остановить партию: блокировка BotFather, лимит ботов или пауза Telegram."""
    details = getattr(exc, "details", None) or {}
    if details.get("botfather_blocked"):
        return True
    if details.get("bots_limit_reached"):
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
    "description_picture": "Картинка плаката",
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
        manual_multi: bool = False,
        batch_specs: list[dict[str, Any]] | None = None,
    ):
        self.job_id = job_id
        self.campaign_id = campaign_id
        self.plans = plans or []
        self.manual_plans = manual_plans or []
        self.manual_multi = manual_multi
        self.batch_specs = batch_specs or []
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

    async def _pace_between_bots(
        self,
        processed: int,
        total: int,
        *,
        account_id: int | None = None,
        skip_sleep: bool = False,
        bots_on_account: int | None = None,
    ) -> bool:
        """Пауза между ботами + пакетный cooldown. True = отменено."""
        if processed >= total:
            return False
        delay = inter_bot_delay_sec()
        if delay > 0:
            if account_id:
                await account_flood_service.record_flood_wait(account_id, delay)
                if skip_sleep:
                    await self.log(
                        f"Пауза {delay} сек. на аккаунте #{account_id} "
                        f"(сохранена в БД, без ожидания — следующий аккаунт)…",
                        context={
                            "account_id": account_id,
                            "delay_sec": delay,
                            "pause_type": "inter_bot",
                        },
                    )
                else:
                    await self.log(
                        f"Пауза {delay} сек. на аккаунте #{account_id} "
                        f"(сохранена в БД до следующего бота)…",
                        context={
                            "account_id": account_id,
                            "delay_sec": delay,
                            "pause_type": "inter_bot",
                        },
                    )
            else:
                await self.log(
                    f"Пауза {delay} сек. перед следующим ботом (лимиты BotFather)…",
                )
            await self.log(
                f"Rate limit pacing: inter-bot {delay}s",
                level="debug",
                context={"delay_sec": delay, "processed": processed, "total": total},
            )
            if not skip_sleep and await self._sleep_cancellable(delay):
                return True
        batch_ref = bots_on_account if bots_on_account is not None else processed
        every = batch_size()
        if every > 0 and batch_ref > 0 and batch_ref % every == 0:
            cooldown = batch_cooldown_sec()
            mins = max(1, cooldown // 60)
            if account_id and cooldown > 0:
                await account_flood_service.record_flood_wait(account_id, cooldown)
                if skip_sleep:
                    await self.log(
                        f"Пакетная пауза ~{mins} мин на аккаунте #{account_id} "
                        f"(сохранена в БД, без ожидания)…",
                        level="warn",
                        context={
                            "account_id": account_id,
                            "cooldown_sec": cooldown,
                            "pause_type": "batch_cooldown",
                        },
                    )
                else:
                    await self.log(
                        f"Пакетная пауза ~{mins} мин на аккаунте #{account_id} "
                        f"(сохранена в БД, защита от блокировки)…",
                        level="warn",
                        context={
                            "account_id": account_id,
                            "cooldown_sec": cooldown,
                            "pause_type": "batch_cooldown",
                        },
                    )
            else:
                await self.log(
                    f"Пакетная пауза ~{mins} мин (создано {batch_ref} из {total} — защита от блокировки)…",
                    level="warn",
                )
            await self.log(
                f"Batch cooldown after {batch_ref} bots",
                level="debug",
                context={"cooldown_sec": cooldown, "batch_size": every},
            )
            if not skip_sleep and await self._sleep_cancellable(cooldown):
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

        if self.batch_specs:
            await self._run_batch_create(campaign)
            return

        if self.manual_plans:
            if self.manual_multi:
                await self._run_manual_multi(campaign)
            else:
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

    async def run_single(
        self,
        spec: dict[str, Any],
        *,
        avatar_path: str | None = None,
        description_picture_path: str | None = None,
    ) -> None:
        """Создание одного бота (job_mode=single)."""
        from app.domain.services import job_service

        uname = (spec.get("username") or "?").lstrip("@")
        account_id = int(spec["telegram_account_id"])
        # Подгружаем аккаунт, чтобы в логах была его метка, а не только #id.
        account = await db.fetch_one(
            "SELECT * FROM telegram_accounts WHERE id = $1", account_id
        )
        label = self._account_label(account) if account else f"Аккаунт #{account_id}"
        await self.log(f"Один бот: @{uname} на {label}", progress="Старт")
        await self._wait_account_flood(account_id, label)
        await db.execute(
            "UPDATE telegram_accounts SET status = 'creating', updated_at = NOW() WHERE id = $1",
            account_id,
        )

        avatar_bytes = None
        if avatar_path:
            path = Path(avatar_path)
            if path.is_file():
                avatar_bytes = path.read_bytes()

        description_picture_bytes = None
        if description_picture_path:
            path = Path(description_picture_path)
            if path.is_file():
                description_picture_bytes = path.read_bytes()

        async def on_step(msg: str, step_id: str = "") -> None:
            await self.log(msg, progress=msg[:120], context={"step": step_id} if step_id else None)

        try:
            bot = await bot_service.create_bot(
                    campaign_id=self.campaign_id,
                    telegram_account_id=account_id,
                    target_url=spec["target_url"],
                    display_name=spec["display_name"],
                    username=spec["username"],
                    description=spec.get("description") or "",
                    welcome_message=spec.get("welcome_message") or "",
                    about_text=spec.get("about_text") or "",
                    welcome_button_enabled=spec.get("welcome_button_enabled", True),
                    welcome_button_text=spec.get(
                        "welcome_button_text", bot_promo_service.WELCOME_BUTTON_TEXT_DEFAULT
                    ),
                    keyword=spec.get("keyword"),
                    redirect_slug=spec.get("redirect_slug"),
                    link_mode=spec.get("link_mode") or bot_promo_service.LINK_MODE_REDIRECT,
                    create_via_botfather=spec.get("create_via_botfather", True),
                    auto_start=spec.get("auto_start", False),
                    avatar_bytes=avatar_bytes,
                    generate_avatar=bool(spec.get("generate_avatar", True)) and not avatar_bytes,
                    description_picture_bytes=description_picture_bytes,
                    use_referral_api=spec.get("use_referral_api"),
                    source_username=spec.get("source_username"),
                    on_step=on_step,
                )
            self._record_row_result(spec, 0, "done", bot_id=bot.get("id"))
            await db.execute(
                """
                UPDATE creation_jobs
                SET total_bots_created = 1, processed_accounts = 1, updated_at = NOW()
                WHERE id = $1
                """,
                self.job_id,
            )
            await self.log(
                f"Бот #{bot['id']} @{bot.get('username')} создан на {label}",
                level="success",
                progress="Готово",
                context={
                    "bot_id": bot.get("id"),
                    "username": bot.get("username"),
                    "account_id": account_id,
                    "status": "done",
                },
            )
            await job_history_service.save_result_snapshot(
                self.job_id,
                row_results=self._row_results,
                total_created=1,
                finished_status="completed",
            )
            await db.execute(
                """
                UPDATE creation_jobs
                SET status = 'completed',
                    finished_at = NOW(),
                    progress_message = $2,
                    updated_at = NOW()
                WHERE id = $1
                """,
                self.job_id,
                f"Готово: @{bot.get('username')}",
            )
            await job_service.sync_campaign_status(self.campaign_id)
        except Exception as exc:
            self._record_row_result(spec, 0, "error", error=str(exc)[:300])
            await job_history_service.save_result_snapshot(
                self.job_id,
                row_results=self._row_results,
                total_created=0,
                finished_status="failed",
                error_message=str(exc)[:500],
            )
            raise
        finally:
            acc = await db.fetch_one("SELECT * FROM telegram_accounts WHERE id = $1", account_id)
            acc_status = "ready"
            if acc and int(acc["bots_created"]) >= int(acc["max_bots_limit"]):
                acc_status = "exhausted"
            await db.execute(
                "UPDATE telegram_accounts SET status = $2, updated_at = NOW() WHERE id = $1",
                account_id,
                acc_status,
            )
            if avatar_path:
                try:
                    Path(avatar_path).unlink(missing_ok=True)
                except OSError:
                    pass
            if description_picture_path:
                try:
                    Path(description_picture_path).unlink(missing_ok=True)
                except OSError:
                    pass
            await release_cached_session(self.campaign_id, account_id, force_disconnect=True)

    async def _run_batch_create(self, campaign: dict) -> None:
        """Пакетное создание из POST /bots/batch-create (каждый spec — свой аккаунт)."""
        specs = self.batch_specs
        total = len(specs)
        created_count = 0
        # Аккаунты, исключённые из очереди в этом прогоне (бан BotFather / лимит 20 ботов).
        # Следующие spec'и на этих же аккаунтах пропускаем, не дёргая BotFather повторно.
        skip_accounts: dict[int, str] = {}
        account_labels: dict[int, str] = {}
        await self.log(f"Пакетное создание: {total} бот(ов)", progress=f"0/{total}")

        for idx, spec in enumerate(specs):
            if await self._is_cancelled():
                await self.log("Создание остановлено пользователем", level="warn")
                break

            uname: str = (spec.get("username") or "?").lstrip("@")
            account_id: int = int(spec["telegram_account_id"])

            # Метку аккаунта берём один раз и кэшируем — используется в логах.
            label: str | None = account_labels.get(account_id)
            if label is None:
                account = await self._refresh_multi_account(account_id)
                label = self._account_label(account) if account else f"Аккаунт #{account_id}"
                account_labels[account_id] = label

            # Аккаунт уже забанен/исчерпан в этом прогоне — берём следующий, очередь не рвём.
            if account_id in skip_accounts:
                reason: str = skip_accounts[account_id]
                self._record_row_result(spec, idx, "error", error=reason)
                await self.log(
                    f"[{idx + 1}/{total}] @{uname} — пропуск: {label} ({reason})",
                    level="warn",
                    context={"account_id": account_id, "username": uname, "status": "skipped"},
                )
                continue

            await db.execute(
                """
                UPDATE creation_jobs
                SET processed_accounts = $2, updated_at = NOW()
                WHERE id = $1
                """,
                self.job_id,
                idx + 1,
            )
            await self.log(
                f"[{idx + 1}/{total}] @{uname} — старт на {label}",
                progress=f"{idx}/{total}: @{uname}",
                context={"account_id": account_id, "username": uname, "status": "creating"},
            )

            async def on_step(msg: str, step_id: str = "") -> None:
                await self.log(msg, context={"step": step_id or None, "username": uname})

            try:
                bot = await bot_service.create_bot(
                    campaign_id=self.campaign_id,
                    telegram_account_id=account_id,
                    target_url=spec["target_url"],
                    display_name=spec["display_name"],
                    username=spec["username"],
                    description=spec.get("description") or "",
                    welcome_message=spec.get("welcome_message") or "",
                    about_text=spec.get("about_text") or "",
                    welcome_button_enabled=spec.get("welcome_button_enabled", True),
                    welcome_button_text=spec.get(
                        "welcome_button_text", bot_promo_service.WELCOME_BUTTON_TEXT_DEFAULT
                    ),
                    keyword=spec.get("keyword"),
                    redirect_slug=spec.get("redirect_slug"),
                    link_mode=spec.get("link_mode") or bot_promo_service.LINK_MODE_REDIRECT,
                    create_via_botfather=spec.get("create_via_botfather", True),
                    auto_start=spec.get("auto_start", False),
                    generate_avatar=bool(spec.get("generate_avatar", True)),
                    use_referral_api=spec.get("use_referral_api"),
                    source_username=spec.get("source_username"),
                    on_step=on_step,
                )
                created_count += 1
                self._record_row_result(spec, idx, "done", bot_id=bot.get("id"))
                await self.log(
                    f"[{idx + 1}/{total}] @{uname} — готово на {label} (#{bot.get('id')})",
                    level="success",
                    progress=f"{idx + 1}/{total}",
                    context={"account_id": account_id, "username": uname, "status": "done"},
                )
            except Exception as exc:
                details: dict[str, Any] = getattr(exc, "details", None) or {}

                # Бан BotFather («you cannot create new bots at this time»):
                # помечаем аккаунт забаненным и переходим к следующему аккаунту,
                # не прерывая всю партию.
                if details.get("botfather_blocked"):
                    ban_reason: str = _format_creation_error(exc)
                    await self._mark_account_banned(account_id, label, ban_reason)
                    skip_accounts[account_id] = "аккаунт забанен BotFather"
                    self._record_row_result(spec, idx, "error", error=ban_reason[:300])
                    await self.log(
                        f"[{idx + 1}/{total}] @{uname} — {label} забанен BotFather, "
                        "берём следующий аккаунт",
                        level="error",
                        context={"account_id": account_id, "username": uname, "status": "banned"},
                    )
                    continue

                # Лимит Telegram (на аккаунте уже 20 ботов): помечаем аккаунт
                # исчерпанным и берём следующий аккаунт, очередь не прерываем.
                if details.get("bots_limit_reached"):
                    limit_reason: str = "на аккаунте уже 20 ботов"
                    await self._mark_account_exhausted(account_id, label)
                    skip_accounts[account_id] = limit_reason
                    self._record_row_result(spec, idx, "error", error=limit_reason)
                    await self.log(
                        f"[{idx + 1}/{total}] @{uname} — на аккаунте {label} уже 20 ботов, "
                        "берём следующий аккаунт",
                        level="warn",
                        context={"account_id": account_id, "username": uname, "status": "exhausted"},
                    )
                    continue

                err: str = str(exc)[:300]
                self._record_row_result(spec, idx, "error", error=err)
                await self.log(
                    f"[{idx + 1}/{total}] @{uname} на {label} — {err}",
                    level="error",
                    context={"account_id": account_id, "username": uname, "status": "error"},
                )
                if _should_stop_batch_on_error(exc):
                    await self.log("Остановка партии из-за ограничения Telegram", level="error")
                    break

            if idx + 1 < total:
                if await self._pace_between_bots(idx + 1, total, account_id=account_id):
                    break

        await self.log(
            f"Пакет: создано {created_count} из {total}",
            progress=f"{created_count}/{total}",
        )
        await self._finish_job(created_count, cancelled=await self._is_cancelled())

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

        client = None
        flood_ctx = None
        async with account_lock(account_id):
            try:
                client, _ = await acquire_cached_client(self.campaign_id, account_id, account)
                await self.log(
                    f"Сессия Telethon загружена ({label})",
                    level="debug",
                )

                flood_ctx = account_flood_service.set_flood_account_context(account_id)
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
                        f"[{processed}/{len(plans)}] @{uname} — старт на {label}",
                        progress=f"{processed - 1}/{len(plans)}: @{uname}",
                        context={
                            "row_id": row_id,
                            "plan_index": idx,
                            "username": uname,
                            "account_id": account_id,
                            "status": "creating",
                        },
                    )

                    avatar_bytes = None
                    avatar_path = plan.get("avatar_path")
                    if avatar_path:
                        path = Path(avatar_path)
                        if path.is_file():
                            avatar_bytes = path.read_bytes()

                    description_picture_bytes = None
                    description_picture_path = plan.get("description_picture_path")
                    if description_picture_path:
                        path = Path(description_picture_path)
                        if path.is_file():
                            description_picture_bytes = path.read_bytes()

                    try:
                        bot = await self._create_manual_bot_with_flood_retry(
                            plan,
                            avatar_bytes=avatar_bytes,
                            description_picture_bytes=description_picture_bytes,
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
                            f"[{processed}/{len(plans)}] @{uname} — создан на {label}",
                            level="info",
                            progress=f"{processed}/{len(plans)}: готово",
                            context={
                                "row_id": row_id,
                                "plan_index": idx,
                                "username": uname,
                                "account_id": account_id,
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
                            f"[{processed}/{len(plans)}] @{uname} на {label} — {_format_creation_error(exc)}",
                            level="error",
                            context={
                                "row_id": row_id,
                                "plan_index": idx,
                                "username": uname,
                                "account_id": account_id,
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
                            if details.get("bots_limit_reached"):
                                await self._mark_account_exhausted(account_id, label)
                                reason = "лимит ботов на аккаунте"
                            elif details.get("botfather_blocked"):
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
                        if await self._pace_between_bots(
                            processed, len(plans), account_id=account_id
                        ):
                            await self._mark_remaining_skipped(plans, idx + 1)
                            break
            finally:
                if flood_ctx is not None:
                    account_flood_service.reset_flood_account_context(flood_ctx)
                await release_cached_session(self.campaign_id, account_id, force_disconnect=True)

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

    def _account_label(self, account: dict[str, Any]) -> str:
        label = (account.get("label") or "").strip()
        return label or f"Аккаунт #{account['id']}"

    async def _refresh_multi_account(self, account_id: int) -> dict[str, Any] | None:
        return await db.fetch_one(
            """
            SELECT * FROM telegram_accounts
            WHERE id = $1 AND campaign_id = $2
            """,
            account_id,
            self.campaign_id,
        )

    async def _mark_account_banned(
        self,
        account_id: int,
        label: str,
        reason: str,
    ) -> None:
        await account_service.update_account(
            self.campaign_id,
            account_id,
            is_banned=True,
            patch_banned=True,
        )
        await db.execute(
            """
            UPDATE telegram_accounts
            SET status = 'error', last_error = $2, updated_at = NOW()
            WHERE id = $1
            """,
            account_id,
            reason[:500],
        )
        await self.log(
            f"{label}: аккаунт помечен как забаненный — {reason[:200]}",
            level="error",
            context={"account_id": account_id, "status": "banned"},
        )

    async def _mark_account_exhausted(self, account_id: int, label: str) -> None:
        acc = await db.fetch_one(
            "SELECT max_bots_limit, bots_created FROM telegram_accounts WHERE id = $1",
            account_id,
        )
        limit = int(acc["max_bots_limit"]) if acc else 20
        await db.execute(
            """
            UPDATE telegram_accounts
            SET status = 'exhausted',
                bots_created = GREATEST(bots_created, $2),
                updated_at = NOW()
            WHERE id = $1
            """,
            account_id,
            limit,
        )
        await self.log(
            f"{label}: лимит {limit} ботов — аккаунт исключён из ротации",
            level="warn",
            context={"account_id": account_id, "status": "exhausted"},
        )

    async def _wait_any_account_flood_clear(self, account_ids: list[int]) -> bool:
        """Ждёт, пока у хотя бы одного аккаунта закончится пауза BotFather."""
        while True:
            waits: list[tuple[int, int]] = []
            free_count = 0
            for aid in account_ids:
                rem = await account_flood_service.get_flood_remaining_seconds(aid)
                if rem > 0:
                    waits.append((aid, rem))
                else:
                    free_count += 1
            if free_count > 0 or not waits:
                return False

            wait_sec = min(rem for _, rem in waits)
            human = _format_flood_wait_human(wait_sec)
            await self.log(
                f"Все доступные аккаунты на паузе BotFather — ожидание {human}…",
                level="warn",
                context={"wait_seconds": wait_sec, "status": "waiting"},
            )
            if await self._sleep_cancellable(wait_sec + 1):
                return True
            # Истёкшие паузы сбрасываются в get_flood_remaining_seconds; длинные — остаются в БД.

    async def _get_or_load_client(
        self,
        account_id: int,
        account: dict[str, Any],
        clients: dict[int, Any],
    ) -> Any:
        # ВАЖНО: вызывать под уже захваченным account_lock(account_id). Жнец
        # (reap_stale_cached_sessions) отключает сессию только если lock СВОБОДЕН,
        # поэтому lock должен удерживаться на всё время работы с клиентом, а не
        # только на момент загрузки — иначе бота, создающегося дольше TTL (90с),
        # реально отключит посреди диалога с BotFather.
        cached = clients.get(account_id)
        if cached is not None:
            # Клиент мог быть отключён maintenance-жнецом (idle > TTL) или сетью,
            # пока шли паузы между ботами. Локальный clients-словарь держит ссылку
            # на тот же объект, поэтому без проверки соединения мы бы отдали
            # уже disconnected-клиент и copy-флоу падал бы на первом же get_entity
            # («Cannot send requests while disconnected»). Переподключаем, а если
            # клиент мёртв безнадёжно — перезагружаем сессию заново.
            try:
                await ensure_client_connected(cached)
                return cached
            except Exception as exc:
                clients.pop(account_id, None)
                await self.log(
                    f"Telethon: сессия {self._account_label(account)} отвалилась "
                    f"({exc}) — перезагрузка",
                    level="debug",
                )
        client, _ = await acquire_cached_client(self.campaign_id, account_id, account)
        clients[account_id] = client
        await self.log(
            f"Telethon: сессия загружена для {self._account_label(account)}",
            level="debug",
        )
        return client

    async def _pick_multi_account(
        self,
        account_ids: list[int],
        cursor: int,
        tried: set[int],
    ) -> tuple[dict[str, Any] | None, int]:
        """Следующий аккаунт без паузы и со свободным слотом."""
        n = len(account_ids)
        for step in range(n):
            idx = (cursor + step) % n
            aid = account_ids[idx]
            if aid in tried:
                continue
            account = await self._refresh_multi_account(aid)
            if not account:
                tried.add(aid)
                continue
            if account.get("is_banned"):
                tried.add(aid)
                continue
            if account.get("status") == "exhausted":
                tried.add(aid)
                continue
            if account.get("status") not in ("ready", "creating"):
                tried.add(aid)
                continue
            slots = max(0, int(account["max_bots_limit"]) - int(account["bots_created"]))
            if slots <= 0:
                tried.add(aid)
                continue
            flood_rem = await account_flood_service.get_flood_remaining_seconds(aid)
            if flood_rem > 0:
                continue
            return account, idx + 1
        return None, cursor

    async def _create_manual_bot_once(
        self,
        plan: dict[str, Any],
        *,
        avatar_bytes: Optional[bytes],
        description_picture_bytes: Optional[bytes] = None,
        client,
        account_id: int,
    ) -> dict[str, Any]:
        return await bot_service.create_bot(
            campaign_id=self.campaign_id,
            telegram_account_id=account_id,
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
            description_picture_bytes=description_picture_bytes,
            generate_avatar=bool(plan.get("generate_avatar")) and not avatar_bytes,
            telethon_client=client,
            use_referral_api=plan.get("use_referral_api"),
            source_username=plan.get("source_username"),
            on_step=lambda msg, step: self.log(
                msg,
                context={
                    "row_id": plan.get("row_id"),
                    "username": plan.get("username"),
                    "account_id": account_id,
                    "status": "creating",
                    "step": step or None,
                },
            ),
        )

    async def _handle_multi_account_error(
        self,
        exc: Exception,
        account_id: int,
        label: str,
    ) -> str:
        """Обработка ошибки при ротации: banned / flood / exhausted / rotate."""
        details = getattr(exc, "details", None) or {}
        msg = _format_creation_error(exc)

        if details.get("botfather_blocked"):
            await self._mark_account_banned(account_id, label, msg)
            return "rotate"

        if details.get("bots_limit_reached"):
            await self._mark_account_exhausted(account_id, label)
            return "rotate"

        if details.get("flood_wait"):
            raw_wait = int(details.get("wait_seconds") or 0)
            total_pause = throttle_pause_total_sec(raw_wait)
            if total_pause <= 0:
                return "rotate"
            await account_flood_service.record_flood_wait(account_id, total_pause)
            human = _format_flood_wait_human(total_pause)
            extra = ""
            if post_throttle_delay_sec() > 0 and raw_wait > 0:
                extra = f" (Telegram {raw_wait}s + post-throttle {post_throttle_delay_sec()}s)"
            await self.log(
                f"{label}: лимит BotFather {human}{extra} — следующий аккаунт",
                level="warn",
                context={
                    "account_id": account_id,
                    "wait_seconds": total_pause,
                    "status": "waiting",
                },
            )
            return "rotate"

        if _is_rotate_account_error(exc) and not _is_bot_specific_error(exc):
            raw_wait = 0
            match = re.search(r"(\d+)\s*sec", msg.lower())
            if match:
                raw_wait = max(1, int(match.group(1)))
            total_pause = throttle_pause_total_sec(raw_wait)
            if total_pause <= 0:
                return "rotate"
            await account_flood_service.record_flood_wait(account_id, total_pause)
            await self.log(
                f"{label}: {msg[:160]} — пауза {_format_flood_wait_human(total_pause)}, следующий аккаунт",
                level="warn",
                context={"account_id": account_id, "wait_seconds": total_pause},
            )
            return "rotate"

        return "fail"

    async def _load_multi_job_account_ids(self) -> list[int]:
        """Аккаунты ротации из creation_jobs.account_ids (обновляется во время задачи)."""
        row = await db.fetch_one(
            "SELECT account_ids FROM creation_jobs WHERE id = $1",
            self.job_id,
        )
        raw = (row or {}).get("account_ids") or []
        ids = sorted({int(x) for x in raw if x is not None})
        if not ids:
            rows = await db.fetch_all(
                """
                SELECT id FROM telegram_accounts
                WHERE campaign_id = $1 AND status IN ('ready', 'creating')
                  AND tdata_path IS NOT NULL AND tdata_path != ''
                  AND is_banned = FALSE
                ORDER BY id
                """,
                self.campaign_id,
            )
            return [int(r["id"]) for r in rows]

        rows = await db.fetch_all(
            """
            SELECT id FROM telegram_accounts
            WHERE campaign_id = $1 AND id = ANY($2::bigint[])
              AND is_banned = FALSE
              AND tdata_path IS NOT NULL AND tdata_path != ''
            ORDER BY id
            """,
            self.campaign_id,
            ids,
        )
        return [int(r["id"]) for r in rows]

    async def _refresh_multi_account_pool(
        self,
        known: set[int],
    ) -> list[int]:
        """Читает account_ids из задачи; логирует новые аккаунты."""
        account_ids = await self._load_multi_job_account_ids()
        new_ids = [aid for aid in account_ids if aid not in known]
        if new_ids and known:
            labels: list[str] = []
            for aid in new_ids:
                acc = await self._refresh_multi_account(aid)
                if acc:
                    labels.append(self._account_label(acc))
            if labels:
                await self.log(
                    f"В задачу добавлены аккаунты: {', '.join(labels)}",
                    level="info",
                    context={"account_ids": new_ids, "status": "accounts_added"},
                )
        known.update(account_ids)
        return account_ids

    async def _run_manual_multi(self, campaign: dict) -> None:
        plans = list(self.manual_plans)
        total = len(plans)
        if not total:
            raise ValueError("Пустой план ручного создания")

        known_account_ids: set[int] = set()
        account_ids = await self._refresh_multi_account_pool(known_account_ids)
        if not account_ids:
            raise ValueError("Нет готовых аккаунтов для мультиаккаунтного режима")

        account_rows: list[dict[str, Any]] = []
        for aid in account_ids:
            acc = await self._refresh_multi_account(aid)
            if acc:
                account_rows.append(acc)

        labels = [self._account_label(a) for a in account_rows]
        total_slots = sum(
            max(0, int(a["max_bots_limit"]) - int(a["bots_created"])) for a in account_rows
        )

        # Признак копирования по username — у планов задан source_username.
        is_copy = any(p.get("source_username") for p in plans)
        if is_copy:
            await self.log(
                f"Копирование {total} бот(ов) по username, "
                f"{len(account_ids)} акк. с ротацией: {', '.join(labels)}",
                progress=f"0/{total}",
                context={"mode": "copy", "account_ids": account_ids},
            )
        else:
            await self.log(
                f"Мультиаккаунт: {total} бот(ов), {len(account_ids)} акк.: {', '.join(labels)}",
                progress=f"0/{total}",
            )
        await self.log(
            f"Суммарно свободных слотов: {total_slots}",
            level="debug",
            context={"account_ids": account_ids, "total_slots": total_slots},
        )

        use_referral = bool(plans[0].get("use_referral_api"))
        link_source = (plans[0].get("link_source") or "") if plans else ""
        mode = plans[0].get("link_mode") if plans else bot_promo_service.LINK_MODE_REDIRECT
        mode_label = "с подсчётом переходов" if mode == bot_promo_service.LINK_MODE_REDIRECT else "прямые"
        if use_referral:
            await self.log("Ссылки: автоматически через реферальный API кампании")
        elif link_source == "per_bot":
            await self.log(f"Ссылки: своя для каждого бота ({mode_label})")
        elif link_source == "campaign":
            sample = (plans[0].get("target_url") or "")[:60] if plans else ""
            suffix = f" — {sample}…" if sample else ""
            await self.log(f"Ссылки: из кампании ({mode_label}){suffix}")
        else:
            sample = (plans[0].get("target_url") or "")[:60] if plans else ""
            suffix = f" — {sample}…" if sample else ""
            await self.log(f"Ссылки: общая для партии ({mode_label}){suffix}")

        pending = list(plans)
        created_count = 0
        processed = 0
        account_cursor = 0
        clients: dict[int, Any] = {}
        flood_contexts: dict[int, Any] = {}
        from collections import defaultdict

        account_success_counts: dict[int, int] = defaultdict(int)

        try:
            while pending:
                if await self._is_cancelled():
                    await self.log("Создание остановлено пользователем", level="warn")
                    break

                account_ids = await self._refresh_multi_account_pool(known_account_ids)
                if not account_ids:
                    await self.log(
                        "Нет доступных аккаунтов в задаче — ожидание…",
                        level="warn",
                    )
                    if await self._sleep_cancellable(15):
                        break
                    continue

                plan = pending[0]
                idx = processed
                uname = plan["username"]
                row_id = plan.get("row_id", processed + 1)
                tried_accounts: set[int] = set()
                bot_done = False
                last_error: str | None = None

                await self.log(
                    f"[{processed + 1}/{total}] @{uname} — выбор аккаунта",
                    progress=f"{processed}/{total}: @{uname}",
                    context={
                        "row_id": row_id,
                        "username": uname,
                        "status": "pending",
                    },
                )

                while not bot_done and len(tried_accounts) < len(account_ids):
                    account_ids = await self._refresh_multi_account_pool(known_account_ids)
                    if not account_ids:
                        break
                    account, account_cursor = await self._pick_multi_account(
                        account_ids,
                        account_cursor,
                        tried_accounts,
                    )
                    if account is None:
                        if await self._wait_any_account_flood_clear(account_ids):
                            break
                        live_count = 0
                        for aid in account_ids:
                            if aid in tried_accounts:
                                continue
                            row = await self._refresh_multi_account(aid)
                            if not row or row.get("is_banned"):
                                continue
                            slots = max(
                                0,
                                int(row["max_bots_limit"]) - int(row["bots_created"]),
                            )
                            if slots <= 0 or row.get("status") == "exhausted":
                                continue
                            live_count += 1
                        if live_count == 0:
                            await self.log(
                                f"@{uname}: нет доступных аккаунтов — остановка очереди",
                                level="error",
                            )
                            bot_done = True
                            last_error = "Нет доступных аккаунтов"
                            break
                        continue

                    account_id = int(account["id"])
                    label = self._account_label(account)
                    tried_accounts.add(account_id)

                    await self.log(
                        f"[{processed + 1}/{total}] @{uname} — аккаунт {label}",
                        context={
                            "row_id": row_id,
                            "username": uname,
                            "account_id": account_id,
                            "status": "creating",
                        },
                    )

                    await self._wait_account_flood(account_id, label)
                    await db.execute(
                        "UPDATE telegram_accounts SET status = 'creating', updated_at = NOW() WHERE id = $1",
                        account_id,
                    )

                    avatar_bytes = None
                    avatar_path = plan.get("avatar_path")
                    if avatar_path:
                        path = Path(avatar_path)
                        if path.is_file():
                            avatar_bytes = path.read_bytes()

                    description_picture_bytes = None
                    description_picture_path = plan.get("description_picture_path")
                    if description_picture_path:
                        path = Path(description_picture_path)
                        if path.is_file():
                            description_picture_bytes = path.read_bytes()

                    flood_ctx = flood_contexts.get(account_id)
                    if flood_ctx is None:
                        flood_ctx = account_flood_service.set_flood_account_context(account_id)
                        flood_contexts[account_id] = flood_ctx

                    try:
                        # Держим account_lock на всю загрузку клиента И создание бота:
                        # пока lock захвачен, maintenance-жнец не отключит сессию, даже
                        # если бот создаётся дольше TTL кэша (flood/паузы BotFather).
                        async with account_lock(account_id):
                            client = await self._get_or_load_client(
                                account_id, account, clients
                            )
                            bot = await self._create_manual_bot_once(
                                plan,
                                avatar_bytes=avatar_bytes,
                                description_picture_bytes=description_picture_bytes,
                                client=client,
                                account_id=account_id,
                            )
                        pending.pop(0)
                        processed += 1
                        created_count += 1
                        bot_done = True

                        await db.execute(
                            """
                            UPDATE creation_jobs
                            SET processed_accounts = $2,
                                total_bots_created = $3,
                                updated_at = NOW()
                            WHERE id = $1
                            """,
                            self.job_id,
                            processed,
                            created_count,
                        )
                        await self.log(
                            f"[{processed}/{total}] @{uname} — создан на {label}",
                            level="info",
                            progress=f"{processed}/{total}: готово",
                            context={
                                "row_id": row_id,
                                "username": uname,
                                "account_id": account_id,
                                "status": "done",
                                "bot_id": bot.get("id"),
                            },
                        )
                        self._record_row_result(
                            plan,
                            idx,
                            "done",
                            bot_id=bot.get("id"),
                            account_id=account_id,
                        )

                        acc = await self._refresh_multi_account(account_id)
                        acc_status = "ready"
                        if acc and int(acc["bots_created"]) >= int(acc["max_bots_limit"]):
                            acc_status = "exhausted"
                        await db.execute(
                            "UPDATE telegram_accounts SET status = $2, updated_at = NOW() WHERE id = $1",
                            account_id,
                            acc_status,
                        )

                        account_success_counts[account_id] += 1
                        if pending and await self._pace_between_bots(
                            processed,
                            total,
                            account_id=account_id,
                            skip_sleep=True,
                            bots_on_account=account_success_counts[account_id],
                        ):
                            await self._mark_remaining_skipped(pending, 0)
                            pending.clear()
                            break

                    except BadRequestError as exc:
                        if await self._is_cancelled():
                            break
                        action = await self._handle_multi_account_error(
                            exc, account_id, label
                        )
                        last_error = _format_creation_error(exc)
                        if action == "rotate":
                            acc = await self._refresh_multi_account(account_id)
                            if acc and not acc.get("is_banned"):
                                st = "ready"
                                if int(acc["bots_created"]) >= int(acc["max_bots_limit"]):
                                    st = "exhausted"
                                await db.execute(
                                    "UPDATE telegram_accounts SET status = $2, updated_at = NOW() WHERE id = $1",
                                    account_id,
                                    st,
                                )
                            continue
                        bot_done = True
                    except Exception as exc:
                        if await self._is_cancelled():
                            break
                        last_error = _format_creation_error(exc)
                        await self.log(
                            f"{label}: @{uname} — {last_error}",
                            level="error",
                            context={
                                "row_id": row_id,
                                "username": uname,
                                "account_id": account_id,
                                "status": "error",
                            },
                        )
                        if _is_bot_specific_error(exc):
                            bot_done = True
                        elif _is_rotate_account_error(exc):
                            total_pause = throttle_pause_total_sec(0)
                            if total_pause > 0:
                                await account_flood_service.record_flood_wait(
                                    account_id, total_pause
                                )
                            continue
                        else:
                            bot_done = True

                # Бот не создан — снимаем его с очереди ровно один раз.
                # Успех удаляет plan из pending ВЫШЕ (до bot_done=True), поэтому
                # признак «не создан» — это идентичность головы очереди, а НЕ
                # флаг bot_done. Ошибочные ветки (BadRequestError→fail, bot-specific,
                # «нет доступных аккаунтов») тоже выставляют bot_done=True, и без
                # этого условия бот навсегда застревал в очереди: outer-цикл
                # перезапускал его по кругу без единого лога.
                if pending and pending[0] is plan:
                    pending.pop(0)
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
                    err_msg = last_error or "Не удалось создать на доступных аккаунтах"
                    await self.log(
                        f"[{processed}/{total}] @{uname} — {err_msg}",
                        level="error",
                        context={
                            "row_id": row_id,
                            "username": uname,
                            "status": "error",
                            "error": err_msg,
                        },
                    )
                    self._record_row_result(plan, idx, "error", error=err_msg)

        finally:
            for token in flood_contexts.values():
                account_flood_service.reset_flood_account_context(token)
            for aid in clients:
                await release_cached_session(self.campaign_id, aid, force_disconnect=True)

        await self.log(
            f"Мультиаккаунт: создано {created_count} из {total}",
            progress=f"{processed}/{total}",
        )
        await self._finish_job(created_count, cancelled=await self._is_cancelled())

    async def _create_manual_bot_with_flood_retry(
        self,
        plan: dict[str, Any],
        *,
        avatar_bytes: Optional[bytes],
        description_picture_bytes: Optional[bytes] = None,
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
                    description_picture_bytes=description_picture_bytes,
                    generate_avatar=bool(plan.get("generate_avatar")) and not avatar_bytes,
                    telethon_client=client,
                    use_referral_api=plan.get("use_referral_api"),
                    source_username=plan.get("source_username"),
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
                if details.get("botfather_blocked") or details.get("bots_limit_reached"):
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

        client = None
        created_count = 0
        resource_url = campaign.get("resource_url") or ""

        async with account_lock(account_id):
            try:
                await self._wait_account_flood(account_id, label)
                client, me = await acquire_cached_client(self.campaign_id, account_id, account)
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
                        if await self._pace_between_bots(
                            idx + 1, len(plan_items), account_id=account_id
                        ):
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
                await release_cached_session(self.campaign_id, account_id, force_disconnect=True)

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

        client = None
        created_count = 0

        async with account_lock(account_id):
            try:
                await self._wait_account_flood(account_id, label)
                client, me = await acquire_cached_client(self.campaign_id, account_id, account)
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
                        if await self._pace_between_bots(
                            idx + 1, len(concepts), account_id=account_id
                        ):
                            break

                acc_status = "ready"
                if created_count + int(account["bots_created"]) >= int(account["max_bots_limit"]):
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
                await release_cached_session(self.campaign_id, account_id, force_disconnect=True)

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
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, 'active')
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
            defaults["welcome_button_enabled"],
            defaults["welcome_button_text"],
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
