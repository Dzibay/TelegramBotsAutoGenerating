-- Режим manual_multi для мультиаккаунтного создания ботов
ALTER TABLE creation_jobs
    DROP CONSTRAINT IF EXISTS creation_jobs_job_mode_check;

ALTER TABLE creation_jobs
    ADD CONSTRAINT creation_jobs_job_mode_check
        CHECK (job_mode IS NULL OR job_mode IN ('manual', 'manual_multi', 'planned', 'auto', 'single', 'batch_create'));
