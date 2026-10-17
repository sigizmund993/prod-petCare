-- Добавляем хранение изображения непосредственно в PostgreSQL.
ALTER TABLE pet_photos
    ADD COLUMN IF NOT EXISTS photo_data BYTEA,
    ADD COLUMN IF NOT EXISTS content_type TEXT;

-- Старые записи могут продолжать хранить прежний photo_url.
-- Для новых записей изображение будет храниться в photo_data.
ALTER TABLE pet_photos
    ALTER COLUMN photo_url DROP NOT NULL;

CREATE INDEX IF NOT EXISTS pet_photos_pet_id_idx
    ON pet_photos (pet_id);