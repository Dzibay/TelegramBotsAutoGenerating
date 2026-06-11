-- Лимит BotFather/Telegram по аккаунту (ожидание до повторного создания)

ALTER TABLE telegram_accounts
    ADD COLUMN IF NOT EXISTS botfather_flood_until TIMESTAMPTZ;

ALTER TABLE telegram_accounts
    ADD COLUMN IF NOT EXISTS botfather_flood_seconds INT;

CREATE INDEX IF NOT EXISTS idx_telegram_accounts_botfather_flood
    ON telegram_accounts (botfather_flood_until)
    WHERE botfather_flood_until IS NOT NULL;
