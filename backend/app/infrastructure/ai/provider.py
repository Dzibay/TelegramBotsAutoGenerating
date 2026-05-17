"""AI: текст (Groq/Ollama) и изображения (Pollinations)."""
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

from app.config import Config
from app.core.exceptions import BadRequestError
from app.core.logging import get_logger
from app.infrastructure.ai.json_utils import extract_json_array, extract_json_object
from app.infrastructure.database import repository as db

logger = get_logger(__name__)


class TextAIProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        ...


class GroqTextProvider(TextAIProvider):
    async def complete(self, system: str, user: str) -> str:
        if not Config.GROQ_API_KEY:
            raise BadRequestError(
                "GROQ_API_KEY не задан. Получите ключ на https://console.groq.com "
                "и добавьте в .env, либо укажите AI_TEXT_PROVIDER=ollama"
            )
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}"},
                json={
                    "model": Config.GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.7,
                },
            )
            if resp.status_code == 403:
                detail = ""
                try:
                    detail = resp.json().get("error", {}).get("message", "")
                except Exception:
                    detail = resp.text[:200]
                raise BadRequestError(
                    "Groq API: доступ запрещён (403). "
                    "Проверьте GROQ_API_KEY на https://console.groq.com — ключ недействителен, "
                    "истёк или заблокирован. "
                    f"{detail}".strip()
                )
            if resp.status_code == 401:
                raise BadRequestError(
                    "Groq API: неверный GROQ_API_KEY (401). Создайте новый ключ на console.groq.com"
                )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


class OllamaTextProvider(TextAIProvider):
    async def complete(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{Config.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                json={
                    "model": Config.OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]


def get_text_provider() -> TextAIProvider | None:
    if Config.AI_TEXT_PROVIDER == "none":
        return None
    if Config.AI_TEXT_PROVIDER == "ollama":
        return OllamaTextProvider()
    return GroqTextProvider()


async def generate_image_bytes(prompt: str, width: int = 512, height: int = 512) -> bytes:
    from urllib.parse import quote

    url = (
        f"https://image.pollinations.ai/prompt/{quote(prompt)}"
        f"?width={width}&height={height}&nologo=true"
    )
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


class AIService:
    def __init__(self, text: TextAIProvider | None = None):
        self._text = text if text is not None else get_text_provider()
        self._provider_name = Config.AI_TEXT_PROVIDER

    def _ai_enabled(self) -> bool:
        return self._text is not None and Config.AI_TEXT_PROVIDER != "none"

    async def _audit(
        self,
        kind: str,
        prompt: str,
        response: str,
        campaign_id: Optional[int] = None,
        bot_id: Optional[int] = None,
    ) -> None:
        try:
            await db.execute(
                """
                INSERT INTO ai_generations (campaign_id, bot_id, kind, provider, prompt, response)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                campaign_id,
                bot_id,
                kind,
                self._provider_name,
                prompt[:8000],
                response[:16000],
            )
        except Exception as exc:
            logger.warning("ai_generations insert failed: %s", exc)

    async def analyze_niche(
        self,
        keywords: list[str],
        niche_description: str | None,
        resource_url: str,
        max_bots: int,
        campaign_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        system = (
            "Ты маркетолог Telegram. Верни ТОЛЬКО JSON-массив без пояснений. "
            "Каждый объект: keyword, display_name (до 64 символов), "
            "description_hint (до 120 символов), username_hint (латиница, оканчивается на bot, 5-32 символа)."
        )
        user = (
            f"Ниша: {niche_description or 'общая'}\n"
            f"Ключевые слова: {', '.join(keywords)}\n"
            f"Ресурс: {resource_url}\n"
            f"Сгенерируй ровно {max_bots} уникальных концептов ботов."
        )
        if not self._ai_enabled():
            return self._fallback_concepts(keywords, max_bots)
        try:
            raw = await self._text.complete(system, user)
        except Exception as exc:
            logger.warning("AI niche analysis failed, fallback: %s", exc)
            return self._fallback_concepts(keywords, max_bots)
        await self._audit("niche_analysis", f"{system}\n---\n{user}", raw, campaign_id=campaign_id)
        try:
            return extract_json_array(raw)
        except Exception as exc:
            logger.warning("AI niche parse failed, fallback: %s", exc)
            return self._fallback_concepts(keywords, max_bots)

    def _fallback_concepts(self, keywords: list[str], max_bots: int) -> list[dict[str, Any]]:
        concepts = []
        for i, kw in enumerate(keywords):
            if len(concepts) >= max_bots:
                break
            slug = "".join(c for c in kw.lower() if c.isalnum())[:12] or f"kw{i}"
            concepts.append(
                {
                    "keyword": kw,
                    "display_name": f"{kw.title()} Bot",
                    "description_hint": f"Бот по теме {kw}",
                    "username_hint": f"{slug}_{i}_bot",
                }
            )
        while len(concepts) < max_bots and keywords:
            i = len(concepts)
            kw = keywords[i % len(keywords)]
            slug = "".join(c for c in kw.lower() if c.isalnum())[:10] or "bot"
            concepts.append(
                {
                    "keyword": kw,
                    "display_name": f"{kw.title()} {i + 1}",
                    "description_hint": f"Помощник {kw}",
                    "username_hint": f"{slug}{i}_bot",
                }
            )
        return concepts[:max_bots]

    async def refine_bot_profile(
        self,
        concept: dict[str, Any],
        niche_description: str | None,
        campaign_id: Optional[int] = None,
    ) -> dict[str, Any]:
        system = (
            "Верни ТОЛЬКО JSON-объект: display_name, description (до 512 символов), "
            "username (латиница, уникальный, 5-32 символа, оканчивается на bot), avatar_prompt (англ., для генерации иконки)."
        )
        user = f"Ниша: {niche_description or 'общая'}\nКонцепт: {concept}"
        fallback = {
            "display_name": concept.get("display_name", "My Bot"),
            "description": concept.get("description_hint", "Telegram bot"),
            "username": concept.get("username_hint", "my_helper_bot"),
            "avatar_prompt": f"minimal telegram bot icon, {concept.get('keyword', 'app')}",
        }
        if not self._ai_enabled():
            return fallback
        try:
            raw = await self._text.complete(system, user)
            await self._audit("bot_profile", f"{system}\n---\n{user}", raw, campaign_id=campaign_id)
            try:
                return extract_json_object(raw)
            except Exception:
                return fallback
        except Exception as exc:
            logger.warning("AI bot_profile failed, fallback: %s", exc)
            return fallback

    async def generate_welcome_message(
        self,
        resource_url: str,
        keyword: str,
        display_name: str,
        variant_index: int,
        campaign_id: Optional[int] = None,
        bot_id: Optional[int] = None,
        moved_notice: bool = False,
    ) -> str:
        moved = (
            "Сообщи, что бот переехал на новый сервис. "
            if moved_notice
            else ""
        )
        system = (
            "Напиши одно приветственное сообщение для Telegram-бота на русском, до 400 символов. "
            f"{moved}"
            "Обязательно включи ТОЛЬКО эту ссылку (не меняй её): URL из поля «Ссылка». "
            "Без markdown-заголовков."
        )
        user = (
            f"Бот: {display_name}\nКлючевое слово: {keyword}\nСсылка: {resource_url}\n"
            f"Вариант #{variant_index + 1}."
        )
        if not self._ai_enabled():
            raw = ""
        else:
            try:
                raw = (await self._text.complete(system, user)).strip()
                await self._audit(
                    "welcome_message",
                    f"{system}\n---\n{user}",
                    raw,
                    campaign_id=campaign_id,
                    bot_id=bot_id,
                )
            except Exception as exc:
                logger.warning("AI welcome_message failed: %s", exc)
                raw = ""
        if resource_url and resource_url.strip() and resource_url not in raw:
            raw = f"{raw}\n\n👉 {resource_url.strip()}".strip() if raw else f"👉 {resource_url.strip()}"
        return raw
