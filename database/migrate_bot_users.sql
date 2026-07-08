-- Учёт пользователей, которые пишут в ботов (любое сообщение, включая /start)

CREATE TABLE IF NOT EXISTS bot_users (
    id BIGSERIAL PRIMARY KEY,
    bot_id BIGINT NOT NULL REFERENCES bots (id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    message_count BIGINT NOT NULL DEFAULT 0,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (bot_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_bot_users_bot_id ON bot_users (bot_id);

-- Неиспользуемый счётчик заменён таблицей bot_users
ALTER TABLE bots DROP COLUMN IF EXISTS start_count;