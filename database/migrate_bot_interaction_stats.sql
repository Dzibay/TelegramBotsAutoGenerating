-- Статистика нажатий /start в Telegram

ALTER TABLE bots ADD COLUMN IF NOT EXISTS start_count BIGINT NOT NULL DEFAULT 0;
