-- Уровень success для успешных шагов (creation_pipeline, UI)

ALTER TABLE job_logs
    DROP CONSTRAINT IF EXISTS job_logs_level_check;

ALTER TABLE job_logs
    ADD CONSTRAINT job_logs_level_check
        CHECK (level IN ('debug', 'info', 'warn', 'error', 'success'));

ALTER TABLE task_logs
    DROP CONSTRAINT IF EXISTS task_logs_level_check;

ALTER TABLE task_logs
    ADD CONSTRAINT task_logs_level_check
        CHECK (level IN ('debug', 'info', 'warn', 'error', 'success'));
