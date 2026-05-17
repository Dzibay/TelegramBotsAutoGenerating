-- Режим ссылки в боте: redirect (трекинг /go/) или direct (прямой URL)
ALTER TABLE bots ADD COLUMN IF NOT EXISTS link_mode TEXT NOT NULL DEFAULT 'redirect';

ALTER TABLE bots DROP CONSTRAINT IF EXISTS bots_link_mode_check;
ALTER TABLE bots ADD CONSTRAINT bots_link_mode_check
    CHECK (link_mode IN ('redirect', 'direct'));
