"""AI: текст (Groq/Ollama) и изображения (Pollinations)."""
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

from app.config import Config
from app.core.exceptions import BadRequestError
from app.core.logging import get_logger
from app.infrastructure.ai.json_utils import extract_json_array, extract_json_object
from app.utils.telegram_username import build_username_from_keyword, normalize_bot_username
from app.infrastructure.ai.prompts import (
    BOT_PROFILE_SYSTEM,
    KEYWORDS_SYSTEM,
    NICHE_ANALYSIS_SYSTEM,
    WELCOME_SYSTEM,
)
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

    async def generate_campaign_keywords(
        self,
        *,
        niche_description: str | None,
        resource_url: str | None,
        count: int = 10,
        existing: list[str] | None = None,
        campaign_id: Optional[int] = None,
    ) -> list[str]:
        """Генерирует список ключевых слов кампании (поисковые фразы для ботов)."""
        count = max(3, min(count, 50))
        existing_clean = [k.strip() for k in (existing or []) if k and k.strip()]

        user = (
            f"Ниша / тематика: {niche_description or 'Telegram-боты и сервисы'}\n"
            f"Рекламируемый сервис: {resource_url or 'не указан'}\n"
            f"Нужно сгенерировать ровно {count} ключевых слов.\n"
        )
        if existing_clean:
            user += f"Уже есть (не повторять): {', '.join(existing_clean)}\n"

        if not self._ai_enabled():
            return self._fallback_keywords(niche_description, count, existing_clean)

        try:
            raw = await self._text.complete(KEYWORDS_SYSTEM, user)
            await self._audit("campaign_keywords", f"{KEYWORDS_SYSTEM}\n---\n{user}", raw, campaign_id=campaign_id)
            items = extract_json_array(raw)
            cleaned = self._clean_keyword_list(items, existing_clean)
            if len(cleaned) >= 3:
                return cleaned[:count]
        except Exception as exc:
            logger.warning("AI campaign keywords failed, fallback: %s", exc)

        return self._fallback_keywords(niche_description, count, existing_clean)

    def _clean_keyword_list(self, items: list, existing: list[str]) -> list[str]:
        seen = {k.lower() for k in existing}
        out: list[str] = []
        for item in items:
            if isinstance(item, dict):
                text = str(item.get("keyword") or item.get("text") or "").strip()
            else:
                text = str(item).strip()
            if not text or len(text) < 2:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(text[:100])
        return out

    def _fallback_keywords(
        self,
        niche_description: str | None,
        count: int,
        existing: list[str],
    ) -> list[str]:
        base_words = []
        for part in (niche_description or "telegram бот помощник").replace(",", " ").split():
            w = part.strip()
            if len(w) > 2:
                base_words.append(w.lower())
        if not base_words:
            base_words = ["бот", "telegram", "помощник", "сервис", "чат"]
        templates = [
            "{w} бот",
            "бот {w}",
            "{w} telegram",
            "найти {w}",
            "{w} онлайн",
        ]
        out = list(existing)
        seen = {k.lower() for k in out}
        i = 0
        while len(out) < count and i < 200:
            w = base_words[i % len(base_words)]
            tpl = templates[i % len(templates)]
            phrase = tpl.format(w=w).strip()
            if phrase.lower() not in seen:
                seen.add(phrase.lower())
                out.append(phrase[:100])
            i += 1
        return out[:count]

    async def analyze_niche(
        self,
        keywords: list[str],
        niche_description: str | None,
        resource_url: str,
        max_bots: int,
        campaign_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        kw_list = [k.strip() for k in keywords if k and k.strip()]
        user = (
            f"Ниша кампании: {niche_description or 'общая'}\n"
            f"Ссылка на сервис: {resource_url or 'не указана'}\n"
            f"Ключевые слова кампании (каждый бот — своё слово): {', '.join(kw_list) or 'не заданы'}\n"
            f"Сгенерируй ровно {max_bots} концептов ботов. "
            "Каждый концепт обязан иметь поле keyword из списка или близкую вариацию."
        )
        if not self._ai_enabled():
            return self._fallback_concepts(kw_list, max_bots, campaign_id)
        try:
            raw = await self._text.complete(NICHE_ANALYSIS_SYSTEM, user)
        except Exception as exc:
            logger.warning("AI niche analysis failed, fallback: %s", exc)
            return self._fallback_concepts(kw_list, max_bots, campaign_id)
        await self._audit("niche_analysis", f"{NICHE_ANALYSIS_SYSTEM}\n---\n{user}", raw, campaign_id=campaign_id)
        try:
            concepts = extract_json_array(raw)
            return self._normalize_concepts(concepts, kw_list, max_bots, campaign_id)
        except Exception as exc:
            logger.warning("AI niche parse failed, fallback: %s", exc)
            return self._fallback_concepts(kw_list, max_bots, campaign_id)

    def _normalize_concepts(
        self,
        concepts: list[dict[str, Any]],
        keywords: list[str],
        max_bots: int,
        campaign_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        used_kw: set[str] = set()
        for i, c in enumerate(concepts):
            if len(out) >= max_bots:
                break
            if not isinstance(c, dict):
                continue
            kw = str(c.get("keyword") or "").strip()
            if not kw and keywords:
                kw = keywords[i % len(keywords)]
            if not kw:
                kw = f"бот {i + 1}"
            used_kw.add(kw.lower())
            ai_hint = c.get("username_hint")
            if ai_hint:
                hint = normalize_bot_username(str(ai_hint))
            else:
                hint = build_username_from_keyword(kw, variant=i, campaign_id=campaign_id)
            out.append(
                {
                    "keyword": kw,
                    "display_name": (c.get("display_name") or f"{kw.title()} Bot")[:64],
                    "description_hint": (c.get("description_hint") or f"Бот по запросу «{kw}»")[:120],
                    "username_hint": hint,
                }
            )
        while len(out) < max_bots:
            fallback = self._fallback_concepts(keywords, max_bots - len(out), campaign_id)
            for c in fallback:
                if c["keyword"].lower() not in used_kw:
                    out.append(c)
                    used_kw.add(c["keyword"].lower())
                if len(out) >= max_bots:
                    break
            if not fallback:
                break
        return out[:max_bots]

    def _fallback_concepts(
        self,
        keywords: list[str],
        max_bots: int,
        campaign_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        concepts = []
        for i, kw in enumerate(keywords):
            if len(concepts) >= max_bots:
                break
            concepts.append(
                {
                    "keyword": kw,
                    "display_name": f"{kw.title()} Bot",
                    "description_hint": f"Бот по теме {kw}",
                    "username_hint": build_username_from_keyword(kw, variant=i, campaign_id=campaign_id),
                }
            )
        while len(concepts) < max_bots and keywords:
            i = len(concepts)
            kw = keywords[i % len(keywords)]
            concepts.append(
                {
                    "keyword": kw,
                    "display_name": f"{kw.title()} {i + 1}",
                    "description_hint": f"Помощник {kw}",
                    "username_hint": build_username_from_keyword(kw, variant=i, campaign_id=campaign_id),
                }
            )
        return concepts[:max_bots]

    async def refine_bot_profile(
        self,
        concept: dict[str, Any],
        niche_description: str | None,
        campaign_id: Optional[int] = None,
    ) -> dict[str, Any]:
        kw = concept.get("keyword", "")
        user = (
            f"Ниша кампании: {niche_description or 'общая'}\n"
            f"Ключевое слово бота (главная тема): {kw}\n"
            f"Концепт: {concept}\n"
            "Весь текст бота должен быть заточен под это ключевое слово."
        )
        hint = concept.get("description_hint", "Telegram bot")
        fallback = {
            "display_name": concept.get("display_name", "My Bot"),
            "description": hint,
            "about_text": (hint[:120] if hint else "Telegram bot")[:120],
            "username": concept.get("username_hint", "my_helper_bot"),
            "avatar_prompt": f"minimal telegram bot icon, {concept.get('keyword', 'app')}",
        }
        if not self._ai_enabled():
            return fallback
        try:
            raw = await self._text.complete(BOT_PROFILE_SYSTEM, user)
            await self._audit("bot_profile", f"{BOT_PROFILE_SYSTEM}\n---\n{user}", raw, campaign_id=campaign_id)
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
        system = f"{WELCOME_SYSTEM} {moved}Сообщение должно естественно использовать ключевое слово."
        user = (
            f"Имя бота: {display_name}\n"
            f"Ключевое слово (поисковый запрос пользователя): {keyword}\n"
            f"Ссылка: {resource_url}\n"
            f"Вариант текста #{variant_index + 1}."
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
