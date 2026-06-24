-- Картинка плаката «Что может делать этот бот?» (Description Picture в BotFather)
ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS description_picture_path TEXT;
