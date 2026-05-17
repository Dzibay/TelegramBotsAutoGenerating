"""Пайплайн создания ботов для worker."""
from pathlib import Path
from typing import Any, Optional

from app.config import Config
from app.domain.services import bot_promo_service, job_log_service
from app.infrastructure.ai.provider import AIService, generate_image_bytes
from app.infrastructure.database import repository as db
from app.infrastructure.telegram.botfather_client import (
    create_bot_via_botfather,
    set_bot_about,
    set_bot_description,
    set_bot_photo,
)
from app.infrastructure.telegram.session_loader import load_client_from_tdata
from app.utils.crypto import encrypt_token


class CreationPipeline:
    def __init__(self, job_id: int, campaign_id: int):
        self.job_id = job_id
        self.campaign_id = campaign_id
        self.ai = AIService()

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

        accounts = await db.fetch_all(
            """
            SELECT * FROM telegram_accounts
            WHERE campaign_id = $1 AND status IN ('ready', 'pending', 'creating')
            ORDER BY id
            """,
            self.campaign_id,
        )
        if not accounts:
            raise ValueError("Нет Telegram-аккаунтов (загрузите tdata ZIP)")

        await self.log(
            f"Старт: кампания «{campaign['title']}», аккаунтов: {len(accounts)}",
            progress="Подготовка",
        )

        total_created = 0
        processed = 0

        for account in accounts:
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

        await db.execute(
            """
            UPDATE creation_jobs
            SET total_bots_created = $2, updated_at = NOW()
            WHERE id = $1
            """,
            self.job_id,
            total_created,
        )

        status = "completed" if total_created > 0 else "failed"
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
        await db.execute(
            "UPDATE campaigns SET status = $2, updated_at = NOW() WHERE id = $1",
            self.campaign_id,
            status,
        )
        await self.log(
            f"Задача завершена. Создано ботов: {total_created}",
            level="info" if total_created else "warn",
            progress="Завершено",
        )

    async def _process_account(self, campaign: dict, account: dict) -> int:
        account_id = account["id"]
        label = account.get("label") or f"Аккаунт #{account_id}"
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
            client, me = await load_client_from_tdata(Path(account["tdata_path"]), session_file)
            phone = getattr(me, "phone", None) or str(me.id)
            await db.execute(
                "UPDATE telegram_accounts SET phone = $2, updated_at = NOW() WHERE id = $1",
                account_id,
                phone,
            )
            await self.log(f"{label}: сессия OK ({phone})", context={"account_id": account_id})

            keywords = list(campaign["keywords"] or [])
            if not keywords:
                keywords = ["bot", "helper", "telegram"]
            resource_url = campaign.get("resource_url") or ""
            await self.log(f"{label}: анализ ниши AI ({slots} ботов)…")
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
        username = profile.get("username", concept.get("username_hint", "my_bot"))

        target_url = (campaign.get("resource_url") or "").strip()
        if not target_url:
            await self.log("Пропуск: у кампании не задан resource_url (ссылка на сервис)", level="warn")
            return None
        target = bot_promo_service.normalize_target_url(target_url)
        slug = bot_promo_service.generate_redirect_slug()
        tracking_url = bot_promo_service.build_tracking_url(slug)
        promo = bot_promo_service.build_promo_texts(
            tracking_url=tracking_url,
            display_name=display_name,
            keyword=keyword,
        )
        description = bot_promo_service.embed_tracking_in_description(
            profile.get("description", "") or promo["description"],
            tracking_url,
            target,
        )

        await self.log(f"BotFather: создание @{username}…")
        result = await create_bot_via_botfather(client, display_name, username)
        token = result["token"]
        username = result["username"]

        welcome = await self.ai.generate_welcome_message(
            tracking_url,
            keyword,
            display_name,
            variant_index,
            campaign_id=self.campaign_id,
            moved_notice=True,
        )
        welcome = bot_promo_service.embed_tracking_in_welcome(welcome, tracking_url, target)

        avatar_path = None
        try:
            prompt = profile.get("avatar_prompt", promo["avatar_prompt"])
            img = await generate_image_bytes(prompt)
            avatar_path = Config.AVATARS_DIR / str(self.campaign_id) / f"{username}.jpg"
            avatar_path.parent.mkdir(parents=True, exist_ok=True)
            avatar_path.write_bytes(img)
            await set_bot_photo(client, username, avatar_path)
        except Exception as exc:
            await self.log(f"Аватар @{username}: {exc}", level="warn")

        await set_bot_description(client, username, description)
        await set_bot_about(client, username, promo["about_text"])

        token_enc = encrypt_token(token)
        row = await db.fetch_one(
            """
            INSERT INTO bots (
                campaign_id, telegram_account_id, keyword, username, display_name,
                description, token_encrypted, avatar_path, welcome_message,
                target_url, redirect_slug, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'active')
            RETURNING id
            """,
            self.campaign_id,
            account_id,
            keyword,
            username,
            display_name,
            description,
            token_enc,
            str(avatar_path) if avatar_path else None,
            welcome,
            target,
            slug,
        )
        bot_id = row["id"]
        await self.log(f"✓ Бот @{username} создан", context={"bot_id": bot_id, "username": username})
        return bot_id
