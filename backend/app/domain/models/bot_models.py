from typing import Optional

from pydantic import BaseModel, Field


class CampaignUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    niche_description: Optional[str] = Field(None, max_length=2000)
    keywords: Optional[list[str]] = None
    resource_url: Optional[str] = Field(None, min_length=4, max_length=2048)


class BotGenerateRequest(BaseModel):
    campaign_id: int
    telegram_account_id: int
    keyword: Optional[str] = Field(None, max_length=100)


class BotCreateRequest(BaseModel):
    campaign_id: int
    telegram_account_id: int
    display_name: str = Field(..., min_length=1, max_length=64)
    username: str = Field(..., min_length=5, max_length=32)
    description: str = Field("", max_length=512)
    welcome_message: str = Field(..., min_length=1, max_length=2000)
    keyword: Optional[str] = Field(None, max_length=100)
    create_via_botfather: bool = True
    auto_start: bool = False


class BotUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=64)
    description: Optional[str] = Field(None, max_length=512)
    welcome_message: Optional[str] = Field(None, min_length=1, max_length=2000)
    keyword: Optional[str] = Field(None, max_length=100)
