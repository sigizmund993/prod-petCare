-- Картинка питомца хранится в самой строке; picture_type — её MIME-тип для отдачи
ALTER TABLE pets ADD COLUMN IF NOT EXISTS picture BYTEA;
ALTER TABLE pets ADD COLUMN IF NOT EXISTS picture_type TEXT;
