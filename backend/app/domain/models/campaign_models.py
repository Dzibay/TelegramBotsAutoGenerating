from typing import Optional

from pydantic import BaseModel, Field


class CampaignCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    niche_description: Optional[str] = Field(None, max_length=2000)
    keywords: list[str] = Field(default_factory=list)
    resource_url: Optional[str] = Field(None, max_length=2048)
    default_about_text: Optional[str] = Field(None, max_length=120)
    default_description: Optional[str] = Field(None, max_length=512)
    default_welcome_message: Optional[str] = Field(None, max_length=2000)


class GenerateKeywordsRequest(BaseModel):
    count: int = Field(10, ge=3, le=50)
    merge: bool = Field(True, description="Добавить к существующим, не заменять")


class BotCreationPlanItem(BaseModel):
    """Один бот в плане массового создания: аккаунт + ключевая фраза."""

    telegram_account_id: int
    keyword: str = Field(..., min_length=1, max_length=100)


class StartCreationJobRequest(BaseModel):
    """Опциональный план: только указанные боты с заданными ключевыми словами."""

    plans: list[BotCreationPlanItem] = Field(default_factory=list, max_length=200)
