from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.utils.telegram_username import normalize_bot_username


class CampaignUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    resource_url: Optional[str] = Field(None, max_length=2048)
    niche_description: Optional[str] = Field(None, max_length=2000)
    keywords: Optional[list[str]] = None


class BotGenerateRequest(BaseModel):
    campaign_id: int
    telegram_account_id: int
    target_url: str = Field(..., min_length=4, max_length=2048)
    keyword: Optional[str] = Field(None, max_length=100)
    redirect_slug: Optional[str] = Field(None, max_length=32)


class BotCreateRequest(BaseModel):
    campaign_id: int
    telegram_account_id: int
    target_url: str = Field(..., min_length=4, max_length=2048)
    display_name: str = Field(..., min_length=1, max_length=64)
    username: str = Field(..., min_length=1, max_length=64)
    description: str = Field("", max_length=512)
    welcome_message: str = Field(..., min_length=1, max_length=2000)
    keyword: Optional[str] = Field(None, max_length=100)
    redirect_slug: Optional[str] = Field(None, max_length=32)
    create_via_botfather: bool = True
    auto_start: bool = False

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        return normalize_bot_username(v or "")


class BotUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=64)
    target_url: Optional[str] = Field(None, min_length=4, max_length=2048)
    description: Optional[str] = Field(None, max_length=512)
    welcome_message: Optional[str] = Field(None, min_length=1, max_length=2000)
    keyword: Optional[str] = Field(None, max_length=100)
    sync_botfather: bool = Field(False, description="Обновить описание/about в BotFather")
