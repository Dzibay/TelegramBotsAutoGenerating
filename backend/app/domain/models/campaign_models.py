from typing import Optional

from pydantic import BaseModel, Field, model_validator


class AccountUpdateRequest(BaseModel):
    label: Optional[str] = Field(None, max_length=200)
    is_banned: Optional[bool] = None


class CampaignCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    niche_description: Optional[str] = Field(None, max_length=2000)
    keywords: list[str] = Field(default_factory=list)
    resource_url: Optional[str] = Field(None, max_length=2048)
    referral_endpoint_url: Optional[str] = Field(None, max_length=2048)
    referral_api_key: Optional[str] = Field(None, max_length=512)
    referral_response_field: Optional[str] = Field(None, max_length=64)
    default_about_text: Optional[str] = Field(None, max_length=120)
    default_description: Optional[str] = Field(None, max_length=512)
    default_welcome_message: Optional[str] = Field(None, max_length=2000)
    default_welcome_button_enabled: Optional[bool] = True
    default_welcome_button_text: Optional[str] = Field(None, max_length=64)


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


class ManualSharedTexts(BaseModel):
    description: str = Field(..., min_length=1, max_length=512)
    welcome_message: str = Field(..., min_length=1, max_length=2000)
    about_text: Optional[str] = Field(None, max_length=120)
    welcome_button_enabled: bool = True
    welcome_button_text: str = Field("Перейти по ссылке", max_length=64)


class ManualBotItem(BaseModel):
    row_id: int = Field(..., ge=1)
    display_name: str = Field(..., min_length=1, max_length=64)
    username: str = Field(..., min_length=3, max_length=64)
    target_url: Optional[str] = Field(None, max_length=2048)
    description: Optional[str] = Field(None, max_length=512)
    about_text: Optional[str] = Field(None, max_length=120)
    welcome_message: Optional[str] = Field(None, max_length=2000)
    generate_avatar: bool = False


class StartManualBulkRequest(BaseModel):
    """Ручная массовая партия: общие тексты + список ботов."""

    telegram_account_id: Optional[int] = None
    multi_account: bool = Field(
        False,
        description="Ротация по всем готовым аккаунтам кампании",
    )
    default_target_url: Optional[str] = Field(None, max_length=2048)
    link_mode: str = Field("redirect", max_length=32)
    auto_start: bool = True
    use_referral_api: Optional[bool] = Field(
        None,
        description="True — ссылки через API кампании; False — из формы; None — по настройкам кампании",
    )
    link_source: Optional[str] = Field(
        None,
        max_length=32,
        description="referral | per_bot | campaign | batch",
    )
    shared_texts: ManualSharedTexts
    bots: list[ManualBotItem] = Field(..., min_length=1, max_length=100)

    @model_validator(mode="after")
    def _validate_account_mode(self) -> "StartManualBulkRequest":
        if self.multi_account:
            return self
        if not self.telegram_account_id:
            raise ValueError("Укажите telegram_account_id или включите multi_account")
        return self


class AddJobAccountsRequest(BaseModel):
    """Добавить аккаунты в выполняющуюся мультиаккаунтную задачу."""

    account_ids: list[int] = Field(..., min_length=1, max_length=50)
