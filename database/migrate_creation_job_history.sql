-- История задач создания ботов: снимок входных данных и результатов для повтора

ALTER TABLE creation_jobs
    ADD COLUMN IF NOT EXISTS job_mode TEXT;

ALTER TABLE creation_jobs
    DROP CONSTRAINT IF EXISTS creation_jobs_job_mode_check;

ALTER TABLE creation_jobs
    ADD CONSTRAINT creation_jobs_job_mode_check
        CHECK (job_mode IS NULL OR job_mode IN ('manual', 'manual_multi', 'planned', 'auto'));

ALTER TABLE creation_jobs
    ADD COLUMN IF NOT EXISTS input_snapshot JSONB;

ALTER TABLE creation_jobs
    ADD COLUMN IF NOT EXISTS result_snapshot JSONB;

ALTER TABLE creation_jobs
    ADD COLUMN IF NOT EXISTS retried_from_job_id BIGINT
        REFERENCES creation_jobs (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_creation_jobs_campaign_created
    ON creation_jobs (campaign_id, id DESC);
