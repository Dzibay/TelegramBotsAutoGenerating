-- Единый durable-реестр фоновых задач поверх PostgreSQL + Redis wakeup.

CREATE TABLE IF NOT EXISTS async_tasks (
    id BIGSERIAL PRIMARY KEY,
    task_type TEXT NOT NULL
        CHECK (task_type IN ('creation', 'bot_telegram_sync', 'account_prep')),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    priority INT NOT NULL DEFAULT 100,
    campaign_id BIGINT REFERENCES campaigns (id) ON DELETE CASCADE,
    bot_id BIGINT REFERENCES bots (id) ON DELETE CASCADE,
    creation_job_id BIGINT,
    account_ids BIGINT[] NOT NULL DEFAULT '{}',
    dedupe_key TEXT,
    payload JSONB NOT NULL DEFAULT '{}',
    result JSONB,
    progress_message TEXT,
    error_message TEXT,
    claimed_by TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE async_tasks
    ADD COLUMN IF NOT EXISTS priority INT NOT NULL DEFAULT 100;

ALTER TABLE async_tasks
    ADD COLUMN IF NOT EXISTS campaign_id BIGINT REFERENCES campaigns (id) ON DELETE CASCADE;

ALTER TABLE async_tasks
    ADD COLUMN IF NOT EXISTS bot_id BIGINT REFERENCES bots (id) ON DELETE CASCADE;

ALTER TABLE async_tasks
    ADD COLUMN IF NOT EXISTS creation_job_id BIGINT;

ALTER TABLE async_tasks
    ADD COLUMN IF NOT EXISTS account_ids BIGINT[] NOT NULL DEFAULT '{}';

ALTER TABLE async_tasks
    ADD COLUMN IF NOT EXISTS dedupe_key TEXT;

ALTER TABLE async_tasks
    ADD COLUMN IF NOT EXISTS payload JSONB NOT NULL DEFAULT '{}';

ALTER TABLE async_tasks
    ADD COLUMN IF NOT EXISTS result JSONB;

ALTER TABLE async_tasks
    ADD COLUMN IF NOT EXISTS progress_message TEXT;

ALTER TABLE async_tasks
    ADD COLUMN IF NOT EXISTS error_message TEXT;

ALTER TABLE async_tasks
    ADD COLUMN IF NOT EXISTS claimed_by TEXT;

ALTER TABLE async_tasks
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_async_tasks_status_priority
    ON async_tasks (status, priority, id);

CREATE INDEX IF NOT EXISTS idx_async_tasks_campaign
    ON async_tasks (campaign_id, id DESC);

CREATE INDEX IF NOT EXISTS idx_async_tasks_bot
    ON async_tasks (bot_id, id DESC);

CREATE INDEX IF NOT EXISTS idx_async_tasks_account_ids
    ON async_tasks USING GIN (account_ids);

CREATE UNIQUE INDEX IF NOT EXISTS idx_async_tasks_active_dedupe
    ON async_tasks (dedupe_key)
    WHERE dedupe_key IS NOT NULL AND status IN ('queued', 'running');

CREATE TABLE IF NOT EXISTS task_logs (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES async_tasks (id) ON DELETE CASCADE,
    level TEXT NOT NULL DEFAULT 'info'
        CHECK (level IN ('debug', 'info', 'warn', 'error')),
    message TEXT NOT NULL,
    context JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_logs_task_id ON task_logs (task_id, id);

ALTER TABLE creation_jobs
    ADD COLUMN IF NOT EXISTS task_id BIGINT REFERENCES async_tasks (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_creation_jobs_task_id
    ON creation_jobs (task_id);
