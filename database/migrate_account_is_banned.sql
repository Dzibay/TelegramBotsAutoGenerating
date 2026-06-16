-- Флаг «аккаунт забанен» (не использовать для создания ботов)

ALTER TABLE prepared_accounts
    ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE telegram_accounts
    ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_prepared_accounts_banned
    ON prepared_accounts (is_banned)
    WHERE is_banned = TRUE;

CREATE INDEX IF NOT EXISTS idx_telegram_accounts_banned
    ON telegram_accounts (is_banned)
    WHERE is_banned = TRUE;
