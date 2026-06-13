-- История задач создания ботов: снимок входных данных и результатов для повтора

ALTER TABLE creation_jobs
    ADD COLUMN IF NOT EXISTS job_mode TEXT
        CHECK (job_mode IS NULL OR job_mode IN ('manual', 'planned', 'auto'));

ALTER TABLE creation_jobs
    ADD COLUMN IF NOT EXISTS input_snapshot JSONB;

ALTER TABLE creation_jobs
    ADD COLUMN IF NOT EXISTS result_snapshot JSONB;

ALTER TABLE creation_jobs
    ADD COLUMN IF NOT EXISTS retried_from_job_id BIGINT
        REFERENCES creation_jobs (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_creation_jobs_campaign_created
    ON creation_jobs (campaign_id, id DESC);
