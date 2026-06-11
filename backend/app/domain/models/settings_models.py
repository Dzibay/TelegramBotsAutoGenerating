from pydantic import BaseModel, Field


class BotfatherPacingSettings(BaseModel):
    """Паузы между обращениями к BotFather при массовом создании."""

    inter_bot_delay_sec: int = Field(
        45,
        ge=10,
        le=600,
        description="Пауза между созданием ботов (сек.)",
    )
    op_delay_sec: int = Field(
        4,
        ge=0,
        le=60,
        description="Пауза между командами BotFather внутри одного бота (сек.)",
    )
    conv_delay_sec: int = Field(
        2,
        ge=0,
        le=30,
        description="Пауза перед новым диалогом с BotFather (сек.)",
    )
    batch_size: int = Field(
        5,
        ge=1,
        le=50,
        description="После скольких ботов делать длинную паузу",
    )
    batch_cooldown_sec: int = Field(
        180,
        ge=30,
        le=3600,
        description="Длинная пауза после пакета ботов (сек.)",
    )
    post_throttle_delay_sec: int = Field(
        30,
        ge=0,
        le=600,
        description="Доп. пауза после throttle BotFather (сек.)",
    )
    max_server_flood_wait: int = Field(
        180,
        ge=30,
        le=600,
        description="Макс. ожидание FloodWait от Telegram (сек.)",
    )
