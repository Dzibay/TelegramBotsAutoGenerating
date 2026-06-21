-- Статус синхронизации профиля бота с BotFather (фоновое обновление после сохранения)
ALTER TABLE bots ADD COLUMN IF NOT EXISTS telegram_sync_status TEXT NOT NULL DEFAULT 'idle';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS telegram_sync_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'bots_telegram_sync_status_check'
    ) THEN
        ALTER TABLE bots
        ADD CONSTRAINT bots_telegram_sync_status_check
        CHECK (telegram_sync_status IN ('idle', 'pending', 'syncing', 'synced', 'failed'));
    END IF;
END $$;

-- Боты с токеном, созданные до миграции: считаем синхронизированными
UPDATE bots
SET telegram_sync_status = 'synced',
    telegram_sync_at = COALESCE(telegram_sync_at, updated_at)
WHERE token_encrypted IS NOT NULL
  AND telegram_sync_status = 'idle';
