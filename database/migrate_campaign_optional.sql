-- Кампания = название + контейнер; ниша/ключевые слова/ссылка необязательны

ALTER TABLE campaigns ALTER COLUMN resource_url DROP NOT NULL;
ALTER TABLE campaigns ALTER COLUMN resource_url SET DEFAULT NULL;
