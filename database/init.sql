-- Telegram Bots Auto Generating — схема PostgreSQL

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Кампания: одна «волна» создания ботов под нишу и ключевые слова
CREATE TABLE IF NOT EXISTS campaigns (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    niche_description TEXT,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    resource_url TEXT,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'queued', 'running', 'completed', 'failed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Telegram-аккаунты (сессии tdata), привязанные к кампании
CREATE TABLE IF NOT EXISTS telegram_accounts (
    id BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT NOT NULL REFERENCES campaigns (id) ON DELETE CASCADE,
    prepared_account_id BIGINT,
    label TEXT,
    tdata_path TEXT NOT NULL,
    phone TEXT,
    max_bots_limit INT NOT NULL DEFAULT 20,
    bots_created INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'ready', 'creating', 'exhausted', 'error', 'disabled')),
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Созданные боты
CREATE TABLE IF NOT EXISTS bots (
    id BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT NOT NULL REFERENCES campaigns (id) ON DELETE CASCADE,
    telegram_account_id BIGINT REFERENCES telegram_accounts (id) ON DELETE SET NULL,
    keyword TEXT,
    username TEXT,
    display_name TEXT NOT NULL,
    description TEXT,
    about_text TEXT,
    token_encrypted BYTEA,
    avatar_path TEXT,
    welcome_message TEXT NOT NULL,
    welcome_button_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    welcome_button_text TEXT NOT NULL DEFAULT 'Перейти по ссылке',
    target_url TEXT,
    link_mode TEXT NOT NULL DEFAULT 'redirect'
        CHECK (link_mode IN ('redirect', 'direct')),
    redirect_slug TEXT,
    click_count BIGINT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'active', 'stopped', 'failed', 'banned')),
    botfather_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Индекс idx_bots_redirect_slug — в migrate_bot_promo.sql (для уже существующих БД)

-- Фоновая задача создания ботов по кампании
CREATE TABLE IF NOT EXISTS creation_jobs (
    id BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT NOT NULL REFERENCES campaigns (id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    total_accounts INT NOT NULL DEFAULT 0,
    processed_accounts INT NOT NULL DEFAULT 0,
    total_bots_created INT NOT NULL DEFAULT 0,
    progress_message TEXT,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Аудит генераций AI (отладка и повтор при сбоях)
CREATE TABLE IF NOT EXISTS ai_generations (
    id BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT REFERENCES campaigns (id) ON DELETE SET NULL,
    bot_id BIGINT REFERENCES bots (id) ON DELETE SET NULL,
    kind TEXT NOT NULL
        CHECK (kind IN ('niche_analysis', 'bot_profile', 'welcome_message', 'avatar_prompt')),
    provider TEXT NOT NULL,
    prompt TEXT,
    response TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_telegram_accounts_campaign ON telegram_accounts (campaign_id);
CREATE INDEX IF NOT EXISTS idx_bots_campaign ON bots (campaign_id);
CREATE INDEX IF NOT EXISTS idx_bots_status ON bots (status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_creation_jobs_campaign ON creation_jobs (campaign_id);
CREATE INDEX IF NOT EXISTS idx_creation_jobs_status ON creation_jobs (status);

-- Пошаговые логи выполнения задачи (для UI в реальном времени)
CREATE TABLE IF NOT EXISTS job_logs (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL REFERENCES creation_jobs (id) ON DELETE CASCADE,
    level TEXT NOT NULL DEFAULT 'info'
        CHECK (level IN ('debug', 'info', 'warn', 'error')),
    message TEXT NOT NULL,
    context JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_logs_job_id ON job_logs (job_id, id);

-- Подготовка аккаунтов (безопасность)
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

-- Пул подготовленных аккаунтов (после успешной подготовки)
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
