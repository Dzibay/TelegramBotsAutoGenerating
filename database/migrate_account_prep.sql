-- Подготовка аккаунтов (безопасность перед кампаниями)

CREATE TABLE IF NOT EXISTS account_prep_jobs (
    id BIGSERIAL PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    options JSONB NOT NULL DEFAULT '{}',
    total_accounts INT NOT NULL DEFAULT 0,
    processed_accounts INT NOT NULL DEFAULT 0,
    succeeded_accounts INT NOT NULL DEFAULT 0,
    progress_message TEXT,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS account_prep_accounts (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL REFERENCES account_prep_jobs (id) ON DELETE CASCADE,
    label TEXT,
    tdata_path TEXT NOT NULL,
    phone TEXT,
    username TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    steps_done JSONB NOT NULL DEFAULT '[]',
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS account_prep_logs (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL REFERENCES account_prep_jobs (id) ON DELETE CASCADE,
    account_id BIGINT REFERENCES account_prep_accounts (id) ON DELETE SET NULL,
    level TEXT NOT NULL DEFAULT 'info'
        CHECK (level IN ('debug', 'info', 'warn', 'error')),
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_account_prep_accounts_job ON account_prep_accounts (job_id);
CREATE INDEX IF NOT EXISTS idx_account_prep_logs_job ON account_prep_logs (job_id, id);
