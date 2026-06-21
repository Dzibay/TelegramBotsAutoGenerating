"""Пайплайн подготовки аккаунтов (безопасность)."""
import json
from pathlib import Path
from typing import Any, Optional

from app.config import Config
from app.domain.services import bot_service, prep_log_service, prepared_account_service
from app.domain.services.account_session_service import prep_account_lock
from app.infrastructure.telegram.botfather_client import delete_all_bots_via_botfather
from app.infrastructure.database import repository as db
from app.infrastructure.telegram.security_hardening import run_security_steps
from app.infrastructure.telegram.session_loader import load_client_from_tdata


class AccountPrepPipeline:
    def __init__(
        self,
        job_id: int,
        *,
        new_password: str | None = None,
        current_password: str | None = None,
        password_hint: str = "",
    ):
        self.job_id = job_id
        self.new_password = new_password
        self.current_password = current_password
        self.password_hint = password_hint

    async def log(
        self,
        message: str,
        level: str = "info",
        account_id: Optional[int] = None,
        progress: Optional[str] = None,
    ) -> None:
        await prep_log_service.append_log(
            self.job_id,
            message,
            level=level,
            account_id=account_id,
            progress_message=progress or message,
        )

    async def run(self) -> None:
        job = await db.fetch_one("SELECT * FROM account_prep_jobs WHERE id = $1", self.job_id)
        if not job:
            raise ValueError("Задача не найдена")

        options = job.get("options") or {}
        if isinstance(options, str):
            options = json.loads(options)

        accounts = await db.fetch_all(
            "SELECT * FROM account_prep_accounts WHERE job_id = $1 ORDER BY id",
            self.job_id,
        )
        if not accounts:
            raise ValueError("Нет аккаунтов")

        await db.execute(
            """
            UPDATE account_prep_jobs
            SET status = 'running', started_at = NOW(), progress_message = 'Старт', updated_at = NOW()
            WHERE id = $1
            """,
            self.job_id,
        )
        await self.log(f"Старт подготовки {len(accounts)} аккаунтов")

        succeeded = 0
        processed = 0

        for acc in accounts:
            processed += 1
            label = acc.get("label") or f"#{acc['id']}"
            try:
                steps = await self._process_account(acc, options)
                succeeded += 1
                await db.execute(
                    """
                    UPDATE account_prep_accounts
                    SET status = 'completed', steps_done = $2::jsonb, updated_at = NOW()
                    WHERE id = $1
                    """,
                    acc["id"],
                    json.dumps(steps),
                )
                refreshed = await db.fetch_one(
                    "SELECT * FROM account_prep_accounts WHERE id = $1", acc["id"]
                )
                try:
                    pool_acc = await prepared_account_service.register_from_prep_account(
                        refreshed
                    )
                    await self.log(
                        f"✓ {label}: готово, в пуле #{pool_acc['id']}",
                        account_id=acc["id"],
                    )
                except Exception as pool_exc:
                    await self.log(
                        f"✗ {label}: не сохранён в пул: {pool_exc}",
                        level="error",
                        account_id=acc["id"],
                    )
            except Exception as exc:
                await db.execute(
                    """
                    UPDATE account_prep_accounts
                    SET status = 'failed', last_error = $2, updated_at = NOW()
                    WHERE id = $1
                    """,
                    acc["id"],
                    str(exc)[:500],
                )
                await self.log(f"✗ {label}: {exc}", level="error", account_id=acc["id"])

            await db.execute(
                """
                UPDATE account_prep_jobs
                SET processed_accounts = $2, succeeded_accounts = $3, updated_at = NOW()
                WHERE id = $1
                """,
                self.job_id,
                processed,
                succeeded,
            )

        status = "completed" if succeeded > 0 else "failed"
        await db.execute(
            """
            UPDATE account_prep_jobs
            SET status = $2,
                finished_at = NOW(),
                progress_message = $3,
                error_message = CASE WHEN $4 = '' THEN NULL ELSE $4 END,
                updated_at = NOW()
            WHERE id = $1
            """,
            self.job_id,
            status,
            f"Готово: {succeeded}/{len(accounts)}",
            "" if succeeded else "Ни один аккаунт не обработан",
        )
        await self.log(f"Завершено: успешно {succeeded} из {len(accounts)}")

    async def _process_account(self, acc: dict, options: dict[str, Any]) -> list[str]:
        account_id = acc["id"]
        label = acc.get("label") or f"#{account_id}"
        await db.execute(
            "UPDATE account_prep_accounts SET status = 'running', updated_at = NOW() WHERE id = $1",
            account_id,
        )
        await self.log(f"{label}: подключение tdata…", account_id=account_id)

        session_file = Config.PREP_TDATA_DIR / str(self.job_id) / f"{account_id}.session"
        client = None
        async with prep_account_lock(account_id):
            try:
                client, me = await load_client_from_tdata(Path(acc["tdata_path"]), session_file)
                phone = getattr(me, "phone", None) or str(me.id)
                username = getattr(me, "username", None)
                await db.execute(
                    """
                    UPDATE account_prep_accounts
                    SET phone = $2, username = $3, updated_at = NOW()
                    WHERE id = $1
                    """,
                    account_id,
                    phone,
                    username,
                )
                await self.log(f"{label}: сессия OK ({phone})", account_id=account_id)

                steps: list[str] = []
                if options.get("delete_bots", True):
                    await self.log(f"{label}: удаление ботов в Telegram…", account_id=account_id)
                    deleted = await delete_all_bots_via_botfather(client)
                    steps.append(f"delete_bots_telegram:{deleted}")
                    await self.log(
                        f"{label}: удалено ботов в Telegram: {deleted}",
                        account_id=account_id,
                    )
                    db_removed = await bot_service.cleanup_bots_for_phone(phone)
                    if db_removed:
                        steps.append(f"delete_bots_db:{db_removed}")
                        await self.log(
                            f"{label}: удалено записей ботов в БД: {db_removed}",
                            account_id=account_id,
                        )

                if options.get("terminate_sessions", True):
                    await self.log(f"{label}: завершение других сессий…", account_id=account_id)

                if options.get("change_password"):
                    await self.log(f"{label}: смена облачного пароля…", account_id=account_id)

                if options.get("privacy_restrictions", True):
                    await self.log(f"{label}: настройка приватности…", account_id=account_id)

                security_steps = await run_security_steps(
                    client,
                    options,
                    new_password=self.new_password,
                    current_password=self.current_password,
                    password_hint=self.password_hint,
                )
                steps.extend(security_steps)
                return steps
            finally:
                if client:
                    await client.disconnect()
