-- Миграция: логи задач (выполнить на существующей БД)
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
