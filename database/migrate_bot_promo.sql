-- Промо-ссылки, редирект и счётчик кликов для ботов

ALTER TABLE bots ADD COLUMN IF NOT EXISTS target_url TEXT;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS redirect_slug TEXT;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS click_count BIGINT NOT NULL DEFAULT 0;

CREATE UNIQUE INDEX IF NOT EXISTS idx_bots_redirect_slug ON bots (redirect_slug)
    WHERE redirect_slug IS NOT NULL;
