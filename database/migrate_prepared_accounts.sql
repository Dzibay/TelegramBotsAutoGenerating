-- Пул подготовленных аккаунтов для кампаний

CREATE TABLE IF NOT EXISTS prepared_accounts (
    id BIGSERIAL PRIMARY KEY,
    source_prep_account_id BIGINT REFERENCES account_prep_accounts (id) ON DELETE SET NULL,
    label TEXT,
    tdata_path TEXT NOT NULL,
    phone TEXT,
    username TEXT,
    status TEXT NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'in_use', 'disabled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prepared_accounts_source_prep
    ON prepared_accounts (source_prep_account_id)
    WHERE source_prep_account_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_prepared_accounts_status ON prepared_accounts (status);

ALTER TABLE telegram_accounts
    ADD COLUMN IF NOT EXISTS prepared_account_id BIGINT
    REFERENCES prepared_accounts (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_telegram_accounts_prepared
    ON telegram_accounts (prepared_account_id);
