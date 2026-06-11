-- Эндпоинт для получения уникальной реферальной ссылки на каждого бота
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS referral_endpoint_url TEXT;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS referral_api_key TEXT;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS referral_response_field TEXT;
