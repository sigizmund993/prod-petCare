-- Тип записи и оценки корма (для category = 'food')
ALTER TABLE props ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'reminder'
    CHECK (category IN ('reminder', 'food', 'vaccination', 'parasites', 'vet_visit', 'medication'));
ALTER TABLE props ADD COLUMN IF NOT EXISTS liked BOOLEAN;
ALTER TABLE props ADD COLUMN IF NOT EXISTS suitable BOOLEAN;
ALTER TABLE props ADD COLUMN IF NOT EXISTS reactions TEXT[] NOT NULL DEFAULT '{}'
    CHECK (reactions <@ ARRAY['gi', 'allergy', 'other']);

CREATE INDEX IF NOT EXISTS props_category_idx ON props (category);
