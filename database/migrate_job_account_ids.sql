-- Привязка задач к аккаунтам для параллельного запуска на разных аккаунтах

ALTER TABLE creation_jobs
    ADD COLUMN IF NOT EXISTS telegram_account_id BIGINT
        REFERENCES telegram_accounts (id) ON DELETE SET NULL;

ALTER TABLE creation_jobs
    ADD COLUMN IF NOT EXISTS account_ids BIGINT[] NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_creation_jobs_active_campaign
    ON creation_jobs (campaign_id, status)
    WHERE status IN ('queued', 'running');

CREATE INDEX IF NOT EXISTS idx_creation_jobs_account_ids
    ON creation_jobs USING GIN (account_ids);
