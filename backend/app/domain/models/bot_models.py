from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.utils.telegram_username import normalize_bot_username


class CampaignUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    resource_url: Optional[str] = Field(None, max_length=2048)
    referral_endpoint_url: Optional[str] = Field(None, max_length=2048)
    referral_api_key: Optional[str] = Field(None, max_length=512)
    referral_response_field: Optional[str] = Field(None, max_length=64)
    niche_description: Optional[str] = Field(None, max_length=2000)
    keywords: Optional[list[str]] = None
    default_about_text: Optional[str] = Field(None, max_length=120)
    default_description: Optional[str] = Field(None, max_length=512)
    default_welcome_message: Optional[str] = Field(None, max_length=2000)
    default_welcome_button_enabled: Optional[bool] = None
    default_welcome_button_text: Optional[str] = Field(None, max_length=64)


class BotGenerateRequest(BaseModel):
    campaign_id: int
    telegram_account_id: int
    target_url: str = Field(..., min_length=4, max_length=2048)
    keyword: Optional[str] = Field(None, max_length=100)
    redirect_slug: Optional[str] = Field(None, max_length=32)
    link_mode: str = Field("redirect", pattern="^(redirect|direct)$")


class BotCreateRequest(BaseModel):
    campaign_id: int
    telegram_account_id: int
    target_url: str = Field(..., min_length=4, max_length=2048)
    display_name: str = Field(..., min_length=1, max_length=64)
    username: str = Field(..., min_length=1, max_length=64)
    description: str = Field("", max_length=512)
    about_text: str = Field("", max_length=120)
    welcome_message: str = Field(..., min_length=1, max_length=2000)
    welcome_button_enabled: bool = True
    welcome_button_text: str = Field("Перейти по ссылке", min_length=1, max_length=64)
    keyword: Optional[str] = Field(None, max_length=100)
    redirect_slug: Optional[str] = Field(None, max_length=32)
    link_mode: str = Field("redirect", pattern="^(redirect|direct)$")
    create_via_botfather: bool = True
    auto_start: bool = False
    generate_avatar: bool = Field(True, description="Сгенерировать аватар AI, если файл не загружен")
    use_referral_api: Optional[bool] = Field(
        None,
        description="True — ссылки через API кампании; False — из target_url; None — по настройкам кампании",
    )

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        return normalize_bot_username(v or "")


class GenerateAvatarPreviewRequest(BaseModel):
    prompt: Optional[str] = Field(None, max_length=500)
    keyword: Optional[str] = Field(None, max_length=100)


class BotBatchCreateRequest(BaseModel):
    """Пакетное создание ботов после предпросмотра текстов."""

    bots: list[BotCreateRequest] = Field(..., min_length=1, max_length=50)


class BotUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=64)
    target_url: Optional[str] = Field(None, min_length=4, max_length=2048)
    link_mode: Optional[str] = Field(None, pattern="^(redirect|direct)$")
    description: Optional[str] = Field(None, max_length=512)
    about_text: Optional[str] = Field(None, max_length=120)
    welcome_message: Optional[str] = Field(None, min_length=1, max_length=2000)
    welcome_button_enabled: Optional[bool] = None
    welcome_button_text: Optional[str] = Field(None, min_length=1, max_length=64)
    keyword: Optional[str] = Field(None, max_length=100)
    sync_botfather: bool = Field(False, description="Применить имя, описание, about и аватар в BotFather")
    generate_avatar: bool = Field(False, description="Сгенерировать новый аватар AI при sync")
