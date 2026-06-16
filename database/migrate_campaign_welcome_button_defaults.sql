-- Дефолтные настройки кнопки под приветствием после Start

ALTER TABLE campaigns
    ADD COLUMN IF NOT EXISTS default_welcome_button_enabled BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE campaigns
    ADD COLUMN IF NOT EXISTS default_welcome_button_text TEXT NOT NULL DEFAULT 'Перейти по ссылке';
