from typing import Optional

from pydantic import BaseModel, Field


class CampaignCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    niche_description: Optional[str] = Field(None, max_length=2000)
    keywords: list[str] = Field(default_factory=list)
    resource_url: Optional[str] = Field(None, max_length=2048)


class CampaignKeywordsUpdateRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    niche_description: Optional[str] = Field(None, max_length=2000)


class GenerateKeywordsRequest(BaseModel):
    count: int = Field(10, ge=3, le=50)
    merge: bool = Field(True, description="Добавить к существующим, не заменять")


class CampaignResponse(BaseModel):
    id: int
    title: str
    niche_description: Optional[str]
    keywords: list[str]
    resource_url: Optional[str] = None
    status: str
    accounts_count: int = 0
    bots_count: int = 0
    active_bots_count: int = 0
    created_at: str
    updated_at: str


class JobResponse(BaseModel):
    id: int
    campaign_id: int
    status: str
    total_accounts: int
    processed_accounts: int
    total_bots_created: int
    progress_message: Optional[str]
    error_message: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    created_at: str


class BotResponse(BaseModel):
    id: int
    campaign_id: int
    telegram_account_id: Optional[int]
    keyword: Optional[str]
    username: Optional[str]
    display_name: str
    description: Optional[str]
    status: str
    created_at: str
