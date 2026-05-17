-- Кнопка со ссылкой в стартовом сообщении бота
ALTER TABLE bots ADD COLUMN IF NOT EXISTS welcome_button_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS welcome_button_text TEXT NOT NULL DEFAULT 'Перейти по ссылке';
