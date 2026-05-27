-- Дефолтные тексты ботов на уровне кампании
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS default_about_text TEXT;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS default_description TEXT;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS default_welcome_message TEXT;
