-- Миграция с шаблона WebAppDefault на Telegram Bots Auto Generating
-- Выполните на существующей БД только если нужно сохранить данные; иначе пересоздайте volume.

DROP TABLE IF EXISTS items CASCADE;
DROP TABLE IF EXISTS users CASCADE;
