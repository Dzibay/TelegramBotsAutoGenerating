-- Краткий профиль бота (BotFather /setabouttext), до 120 символов
ALTER TABLE bots ADD COLUMN IF NOT EXISTS about_text TEXT;
